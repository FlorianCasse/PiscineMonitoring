#!/usr/bin/env python3
# Called from .github/workflows/update-status.yml on every repository_dispatch.
# Reads PAYLOAD env var, updates status.json + history.json + daily_summary.json,
# and bumps the service-worker cache key in sw.js.
#
# Payload formats accepted:
#   batch:  {"entries": [{updated_at, temp_water_c, ...}, ...]}
#   single: {updated_at, temp_water_c, ...}   (legacy — wrapped into entries=[payload])

import hashlib
import json
import os
import re
import sys
from datetime import datetime

from aggregate_daily import (
    aggregate_day,
    compute_season_start,
    filter_today_entries,
    load_summary,
    upsert,
)

HISTORY_FILE = 'history.json'
SUMMARY_FILE = 'daily_summary.json'
STATUS_FILE  = 'status.json'
SW_FILE      = 'sw.js'
HISTORY_MAX_ENTRIES = 2016


def normalize_payload(raw):
    """Return list of entries from either batch or single-entry payload."""
    if isinstance(raw, dict) and isinstance(raw.get('entries'), list):
        return [e for e in raw['entries'] if isinstance(e, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def entry_to_history(p):
    return {
        'ts':                     p.get('updated_at', ''),
        'temp_water_c':           p.get('temp_water_c'),
        'temp_air_c':             p.get('temp_air_c'),
        'pump_on':                p.get('pump_on'),
        'swimmable':              p.get('swimmable'),
        'solar_energy_total_kwh': p.get('solar_energy_total_kwh'),
    }


def bump_sw_version(version):
    if not os.path.exists(SW_FILE):
        return
    sw = open(SW_FILE, encoding='utf-8').read()
    new_sw = re.sub(
        r"const CACHE = 'piscine-[^']+';\br",
        f"const CACHE = 'piscine-{version}';",
        sw,
        count=1,
    )
    if new_sw != sw:
        open(SW_FILE, 'w', encoding='utf-8').write(new_sw)


def main():
    payload_str = os.environ.get('PAYLOAD', '')
    if not payload_str:
        print('ERROR: PAYLOAD env var not set', file=sys.stderr)
        sys.exit(1)

    raw = json.loads(payload_str)
    entries = normalize_payload(raw)
    if not entries:
        print('WARNING: payload contains no entries — nothing to do')
        return

    if len(entries) > 100:
        print(f"ERROR: batch too large ({len(entries)} entries, max 100)", file=sys.stderr)
        sys.exit(1)

    # ── status.json: latest entry only (dashboard reads this) ────────────────
    latest = entries[-1]
    open(STATUS_FILE, 'w', encoding='utf-8').write(json.dumps(latest))

    # ── history.json: append all entries, trim to HISTORY_MAX_ENTRIES ────────
    history = load_summary(HISTORY_FILE)
    history_entries = history.get('entries', [])
    for e in entries:
        history_entries.append(entry_to_history(e))
    if len(history_entries) > HISTORY_MAX_ENTRIES:
        history_entries = history_entries[-HISTORY_MAX_ENTRIES:]
    history['entries'] = history_entries
    history['updated_at'] = history_entries[-1]['ts'] if history_entries else ''
    open(HISTORY_FILE, 'w', encoding='utf-8').write(json.dumps(history))
    print(f"history.json: {len(history_entries)} entries (+{len(entries)})")

    # ── daily_summary.json: re-aggregate every day touched by this batch ─────
    summary = load_summary(SUMMARY_FILE)
    dates_touched = set()
    for e in entries:
        ts = e.get('updated_at', '')
        if not ts:
            continue
        try:
            dates_touched.add(datetime.fromisoformat(ts).date().isoformat())
        except (ValueError, TypeError):
            continue

    for date_str in dates_touched:
        day_entries = filter_today_entries(history_entries, date_str)
        if day_entries:
            new_entry = aggregate_day(day_entries)
            if new_entry:
                upsert(summary, new_entry)

    summary['season_start'] = compute_season_start(summary.get('entries', []))
    summary['updated_at']   = latest.get('updated_at', '')
    open(SUMMARY_FILE, 'w', encoding='utf-8').write(json.dumps(summary, separators=(',', ':')))
    print(f"daily_summary.json: {len(summary['entries'])} days, touched {sorted(dates_touched)}")

    # ── sw.js: bump cache key so clients pick up new data ────────────────────
    version = latest.get('updated_at', '') or datetime.utcnow().isoformat()
    sw_version = hashlib.sha256(version.encode('utf-8')).hexdigest()[:16]
    bump_sw_version(sw_version)
    print(f"sw.js: cache key piscine-{sw_version}")


if __name__ == '__main__':
    main()
