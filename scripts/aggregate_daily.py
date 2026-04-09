#!/usr/bin/env python3
# daily_summary.json schema — one entry per calendar day (upserted, never pruned)
# {
#   "date": "YYYY-MM-DD",  -- LOCAL date from HA timestamp offset (NOT UTC)
#   "avg_water_c": float,  -- average pool temperature (°C)
#   "min_water_c": float,
#   "max_water_c": float,
#   "avg_air_c": float,    -- average outdoor air temperature (°C)
#   "min_air_c": float,
#   "max_air_c": float,
#   "solar_kwh_today": float | null,  -- DELTA: max-min of solar_energy_total_kwh
#                                     -- (cumulative lifetime counter, NOT daily value)
#                                     -- null if fewer than 2 valid readings, or delta == 0.0
#   "swimmable_minutes": int,         -- count(swimmable==True entries) * 5
#   "pump_on_minutes": int            -- count(pump_on==True entries) * 5
# }
# To add a new field: always make it optional, always default to None.

import json
import os
import sys
from datetime import datetime


def aggregate_day(entries):
    """
    Compute a daily_summary entry from a list of history.json entries for a single day.

    Args:
        entries: list of dicts with keys: ts, temp_water_c, temp_air_c,
                 solar_energy_total_kwh, swimmable, pump_on

    Returns:
        dict with daily_summary fields, or None if entries is empty.
    """
    if not entries:
        return None

    # Use local date from the first entry's HA timestamp offset
    date_str = datetime.fromisoformat(entries[0]['ts']).date().isoformat()

    # Temperature stats
    water_vals = [e['temp_water_c'] for e in entries if e.get('temp_water_c') is not None]
    air_vals   = [e['temp_air_c']   for e in entries if e.get('temp_air_c')   is not None]

    avg_water_c = round(sum(water_vals) / len(water_vals), 2) if water_vals else None
    min_water_c = round(min(water_vals), 2)                   if water_vals else None
    max_water_c = round(max(water_vals), 2)                   if water_vals else None
    avg_air_c   = round(sum(air_vals)   / len(air_vals),   2) if air_vals   else None
    min_air_c   = round(min(air_vals),   2)                   if air_vals   else None
    max_air_c   = round(max(air_vals),   2)                   if air_vals   else None

    # Solar: delta (max - min) of cumulative lifetime counter
    solar_vals = [e['solar_energy_total_kwh'] for e in entries
                  if e.get('solar_energy_total_kwh') is not None]
    if len(solar_vals) >= 2:
        delta = round(max(solar_vals) - min(solar_vals), 3)
        solar_kwh_today = delta if delta > 0.0 else None  # 0.0 = no production, treat as null
    else:
        solar_kwh_today = None

    # Swimmable and pump minutes (5-min cadence assumed)
    swimmable_minutes = sum(1 for e in entries if e.get('swimmable') is True) * 5
    pump_on_minutes   = sum(1 for e in entries if e.get('pump_on')   is True) * 5

    return {
        'date':              date_str,
        'avg_water_c':       avg_water_c,
        'min_water_c':       min_water_c,
        'max_water_c':       max_water_c,
        'avg_air_c':         avg_air_c,
        'min_air_c':         min_air_c,
        'max_air_c':         max_air_c,
        'solar_kwh_today':   solar_kwh_today,
        'swimmable_minutes': swimmable_minutes,
        'pump_on_minutes':   pump_on_minutes,
    }


def upsert(summary, new_entry):
    """
    Insert or replace an entry in summary by date key.

    Args:
        summary: dict with 'entries' list (existing daily_summary.json content)
        new_entry: dict with 'date' key

    Returns:
        updated summary dict (mutates in place)
    """
    entries = summary.setdefault('entries', [])
    date = new_entry['date']
    for i, e in enumerate(entries):
        if e.get('date') == date:
            entries[i] = new_entry
            return summary
    entries.append(new_entry)
    return summary


def compute_season_start(entries):
    """
    Find the first entry in the current year where month >= 4.
    Falls back to today's date if not found.
    """
    current_year = str(datetime.now().year)
    candidates = [
        e['date'] for e in entries
        if e.get('date', '').startswith(current_year)
        and int(e['date'][5:7]) >= 4
    ]
    return min(candidates) if candidates else datetime.now().date().isoformat()


def filter_today_entries(history_entries, today_str):
    """Return history.json entries whose local calendar date equals today_str."""
    result = []
    for e in history_entries:
        ts = e.get('ts', '')
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts).date().isoformat() == today_str:
                result.append(e)
        except (ValueError, TypeError):
            continue
    return result


def load_json(filepath):
    """Load a JSON file, returning an empty dict on missing or corrupt file."""
    if os.path.exists(filepath):
        try:
            return json.loads(open(filepath).read())
        except (json.JSONDecodeError, ValueError):
            print(f"WARNING: {filepath} corrupt — resetting", file=sys.stderr)
    return {}


def load_summary(filepath):
    """Load daily_summary.json, returning empty structure on missing or corrupt file."""
    data = load_json(filepath)
    if 'entries' not in data:
        return {'entries': [], 'season_start': None, 'updated_at': ''}
    return data


if __name__ == '__main__':
    # Called from update-status.yml — reads PAYLOAD env var, updates daily_summary.json
    payload_str = os.environ.get('PAYLOAD', '')
    if not payload_str:
        print('ERROR: PAYLOAD env var not set', file=sys.stderr)
        sys.exit(1)

    payload = json.loads(payload_str)

    ts = payload.get('updated_at', '')
    if not ts:
        print('WARNING: updated_at missing in payload — skipping daily_summary update')
        sys.exit(0)

    try:
        today_str = datetime.fromisoformat(ts).date().isoformat()
    except (ValueError, TypeError):
        print(f"WARNING: invalid updated_at '{ts}' — skipping daily_summary update")
        sys.exit(0)

    # Load history.json (already updated by the Append step before us)
    history = load_summary('history.json')
    history_entries = history.get('entries', [])

    # Load existing daily_summary.json
    summary = load_summary('daily_summary.json')

    # Aggregate today's entries and upsert
    today_entries = filter_today_entries(history_entries, today_str)
    if today_entries:
        new_entry = aggregate_day(today_entries)
        if new_entry:
            upsert(summary, new_entry)

    # Update top-level fields
    summary['season_start'] = compute_season_start(summary.get('entries', []))
    summary['updated_at'] = ts

    open('daily_summary.json', 'w').write(json.dumps(summary, separators=(',', ':')))

    entry = next((e for e in summary['entries'] if e.get('date') == today_str), {})
    print(
        f"daily_summary.json: date={today_str}, "
        f"avg_water={entry.get('avg_water_c')}°C, "
        f"solar_kwh={entry.get('solar_kwh_today')}, "
        f"swimmable={entry.get('swimmable_minutes')}min, "
        f"pump={entry.get('pump_on_minutes')}min, "
        f"entries_total={len(summary['entries'])}"
    )
