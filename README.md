# PiscineMonitoring

Real-time pool dashboard powered by Home Assistant + GitHub Pages. Updates every 5 minutes via GitHub Actions.

## HA dispatch payload

Home Assistant triggers a `repository_dispatch` event with this payload:

```json
{
  "event_type": "update_pool_status",
  "client_payload": {
    "updated_at":              "2026-04-09T14:30:00+02:00",
    "temp_water_c":            17.4,
    "temp_air_c":              22.1,
    "pump_on":                 true,
    "pump_power_w":            750,
    "swimmable":               false,
    "solar_power_w":           2800,
    "solar_energy_total_kwh":  11582.4,
    "sensors_ok":              true,
    "reason":                  "Température trop basse"
  }
}
```

**Notes:**
- `solar_energy_total_kwh` is the cumulative lifetime counter from the inverter (not daily production).
- `updated_at` must include a UTC offset (e.g. `+02:00`) — used by the Python aggregation to determine local calendar date.
- `swimmable` and `pump_on` are booleans, not strings.

## GitHub Actions setup

The workflow in `.github/workflows/update-status.yml` runs on every `repository_dispatch` event.

Required permissions (already set in the workflow file):
- `contents: write` — for committing `history.json` + `daily_summary.json`
- `pages: write` + `id-token: write` — for deploying GitHub Pages

No additional secrets needed beyond `GITHUB_TOKEN` (automatic).

Enable GitHub Pages in repo settings: **Settings → Pages → Source → GitHub Actions**.

## localStorage keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `lastStatus` | JSON string | — | Cached `status.json` for offline fallback |
| `piscine_tab` | string | `aujourdhui` | Active top-level tab |
| `piscine_sub_tab` | string | `saison` | Active Historique sub-tab |
| `piscine_tariff` | number | `0.22` | Energy tariff in €/kWh |
| `piscine_lat` | number | — | Pool latitude (decimal degrees) |
| `piscine_lon` | number | — | Pool longitude (decimal degrees) |
| `openmeteo_forecast` | JSON string | — | Cached Open-Meteo response (6h TTL) |

## Local development

`fetch()` fails on `file://` protocol. Serve from a local HTTP server:

```bash
python3 -m http.server 8080
# then open http://localhost:8080
```

The `daily_summary.json` file is committed to the repo. If you need synthetic data to test charts locally:

```bash
python3 scripts/backfill_daily_summary.py   # seeds from history.json
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/aggregate_daily.py` | Aggregation module (called by Actions workflow) |
| `scripts/test_daily_summary.py` | Test suite — run before merging: `python3 scripts/test_daily_summary.py` |
| `scripts/backfill_daily_summary.py` | One-time backfill from history.json |
