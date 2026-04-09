#!/usr/bin/env python3
# One-time backfill: reads history.json, writes daily_summary.json for the available window.
# Usage: python3 scripts/backfill_daily_summary.py
# Safe to run multiple times (upserts by date key, never duplicates).
# Run once after shipping Iteration 3 to seed historical data from the existing 7-day window.

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.aggregate_daily import (
    aggregate_day, upsert, compute_season_start, filter_today_entries, load_summary
)


def main():
    # Load history.json
    history_path = 'history.json'
    if not os.path.exists(history_path):
        print(f'ERROR: {history_path} not found — run from repo root', file=sys.stderr)
        sys.exit(1)

    history = load_summary(history_path)
    history_entries = history.get('entries', [])

    if not history_entries:
        print('history.json has no entries — nothing to backfill')
        return

    # Find all unique local dates in history.json
    dates = set()
    for e in history_entries:
        ts = e.get('ts', '')
        if ts:
            try:
                dates.add(datetime.fromisoformat(ts).date().isoformat())
            except (ValueError, TypeError):
                continue

    if not dates:
        print('No valid timestamps in history.json — nothing to backfill')
        return

    print(f'Backfilling {len(dates)} date(s): {sorted(dates)}')

    # Load existing daily_summary.json (or start fresh)
    summary_path = 'daily_summary.json'
    summary = load_summary(summary_path)

    # Aggregate each date and upsert
    for date_str in sorted(dates):
        today_entries = filter_today_entries(history_entries, date_str)
        if today_entries:
            new_entry = aggregate_day(today_entries)
            if new_entry:
                upsert(summary, new_entry)
                print(
                    f'  {date_str}: avg_water={new_entry["avg_water_c"]}°C, '
                    f'solar={new_entry["solar_kwh_today"]} kWh, '
                    f'swimmable={new_entry["swimmable_minutes"]}min'
                )

    # Update top-level fields
    last_ts = history_entries[-1].get('ts', '') if history_entries else ''
    summary['season_start'] = compute_season_start(summary.get('entries', []))
    summary['updated_at'] = last_ts

    open(summary_path, 'w').write(json.dumps(summary, separators=(',', ':')))
    print(f'\nWrote {len(summary["entries"])} entries to {summary_path}')


if __name__ == '__main__':
    main()
