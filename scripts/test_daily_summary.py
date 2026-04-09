#!/usr/bin/env python3
# Run: python3 scripts/test_daily_summary.py
# All tests must pass before merging Iteration 3.

import sys
import os

# Allow import from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.aggregate_daily import aggregate_day, upsert, compute_season_start, filter_today_entries

PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name, msg):
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}: {msg}')


# ── 1. Solar delta: uses max-min, NOT the raw cumulative total ─────────────────
def test_solar_delta():
    entries = [
        {'ts': '2026-04-09T08:00:00+02:00', 'temp_water_c': 16.0, 'temp_air_c': 18.0,
         'solar_energy_total_kwh': 11574.0, 'swimmable': False, 'pump_on': True},
        {'ts': '2026-04-09T18:00:00+02:00', 'temp_water_c': 17.0, 'temp_air_c': 22.0,
         'solar_energy_total_kwh': 11580.4, 'swimmable': False, 'pump_on': True},
    ]
    result = aggregate_day(entries)
    assert result is not None, 'aggregate_day returned None'
    expected = 6.4
    actual = result['solar_kwh_today']
    if abs(actual - expected) < 0.01:
        ok('solar_delta')
    else:
        fail('solar_delta', f'expected {expected}, got {actual}')


# ── 2. Single solar reading → null (not 0.0) ──────────────────────────────────
def test_solar_null_on_single_reading():
    entries = [
        {'ts': '2026-04-09T08:00:00+02:00', 'temp_water_c': 16.0, 'temp_air_c': 18.0,
         'solar_energy_total_kwh': 11574.0, 'swimmable': False, 'pump_on': False},
    ]
    result = aggregate_day(entries)
    if result['solar_kwh_today'] is None:
        ok('solar_null_single_reading')
    else:
        fail('solar_null_single_reading', f'expected None, got {result["solar_kwh_today"]}')


# ── 3. Two identical solar readings (delta=0.0) → null ────────────────────────
def test_solar_zero_is_null():
    entries = [
        {'ts': '2026-04-09T08:00:00+02:00', 'temp_water_c': 16.0, 'temp_air_c': 18.0,
         'solar_energy_total_kwh': 11574.0, 'swimmable': False, 'pump_on': False},
        {'ts': '2026-04-09T18:00:00+02:00', 'temp_water_c': 17.0, 'temp_air_c': 22.0,
         'solar_energy_total_kwh': 11574.0, 'swimmable': False, 'pump_on': False},
    ]
    result = aggregate_day(entries)
    if result['solar_kwh_today'] is None:
        ok('solar_zero_is_null')
    else:
        fail('solar_zero_is_null', f'expected None, got {result["solar_kwh_today"]}')


# ── 4. Timezone: +02:00 offset, 01:30 UTC → 2026-04-09 local, NOT 2026-04-08 ──
def test_timezone_local_date():
    # 2026-04-09T01:30:00+02:00 = 2026-04-08T23:30:00 UTC
    # Local date must be 2026-04-09 (not 2026-04-08)
    entries = [
        {'ts': '2026-04-09T01:30:00+02:00', 'temp_water_c': 15.0, 'temp_air_c': 10.0,
         'solar_energy_total_kwh': None, 'swimmable': False, 'pump_on': False},
    ]
    result = aggregate_day(entries)
    if result['date'] == '2026-04-09':
        ok('timezone_local_date')
    else:
        fail('timezone_local_date', f'expected 2026-04-09, got {result["date"]}')


# ── 5. Upsert replaces, does NOT append duplicate ─────────────────────────────
def test_upsert_replaces_not_appends():
    summary = {'entries': [{'date': '2026-04-09', 'avg_water_c': 14.0}]}
    new_entry = {'date': '2026-04-09', 'avg_water_c': 16.0}
    result = upsert(summary, new_entry)
    if len(result['entries']) != 1:
        fail('upsert_replaces', f'expected 1 entry, got {len(result["entries"])}')
    elif result['entries'][0]['avg_water_c'] != 16.0:
        fail('upsert_replaces', f'expected avg_water_c=16.0, got {result["entries"][0]["avg_water_c"]}')
    else:
        ok('upsert_replaces_not_appends')


# ── 6. swimmable_minutes counts True entries × 5 ─────────────────────────────
def test_swimmable_minutes():
    entries = [
        {'ts': '2026-04-09T10:00:00+02:00', 'temp_water_c': 21.0, 'temp_air_c': 25.0,
         'solar_energy_total_kwh': None, 'swimmable': True,  'pump_on': True},
        {'ts': '2026-04-09T10:05:00+02:00', 'temp_water_c': 21.1, 'temp_air_c': 25.1,
         'solar_energy_total_kwh': None, 'swimmable': True,  'pump_on': True},
        {'ts': '2026-04-09T10:10:00+02:00', 'temp_water_c': 21.0, 'temp_air_c': 25.0,
         'solar_energy_total_kwh': None, 'swimmable': False, 'pump_on': True},
    ]
    result = aggregate_day(entries)
    if result['swimmable_minutes'] == 10:
        ok('swimmable_minutes')
    else:
        fail('swimmable_minutes', f'expected 10, got {result["swimmable_minutes"]}')


# ── 7. season_start: first entry in current year with month >= 4 ──────────────
def test_season_start_detection():
    from datetime import datetime
    year = str(datetime.now().year)
    entries = [
        {'date': f'{year}-03-25'},  # March — excluded
        {'date': f'{year}-04-01'},  # April — should be season_start
        {'date': f'{year}-04-09'},
        {'date': f'{year}-05-01'},
    ]
    result = compute_season_start(entries)
    if result == f'{year}-04-01':
        ok('season_start_detection')
    else:
        fail('season_start_detection', f'expected {year}-04-01, got {result}')


# ── 8. filter_today_entries: only returns matching local date ─────────────────
def test_filter_today_entries():
    history_entries = [
        {'ts': '2026-04-09T08:00:00+02:00', 'temp_water_c': 16.0},  # today
        {'ts': '2026-04-09T18:00:00+02:00', 'temp_water_c': 17.0},  # today
        {'ts': '2026-04-08T20:00:00+02:00', 'temp_water_c': 15.0},  # yesterday
        {'ts': '',                           'temp_water_c': 14.0},  # empty ts
    ]
    result = filter_today_entries(history_entries, '2026-04-09')
    if len(result) == 2:
        ok('filter_today_entries')
    else:
        fail('filter_today_entries', f'expected 2 entries, got {len(result)}')


if __name__ == '__main__':
    print('Running daily_summary tests...')
    test_solar_delta()
    test_solar_null_on_single_reading()
    test_solar_zero_is_null()
    test_timezone_local_date()
    test_upsert_replaces_not_appends()
    test_swimmable_minutes()
    test_season_start_detection()
    test_filter_today_entries()
    print(f'\n{PASS} passed, {FAIL} failed')
    sys.exit(0 if FAIL == 0 else 1)
