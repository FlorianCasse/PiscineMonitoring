# PiscineMonitoring

Real-time pool dashboard powered by Home Assistant + GitHub Pages. Home Assistant may
dispatch readings every 30 minutes, but GitHub Actions only processes the four payloads
containing a reading at 00:00, 06:00, 12:00, or 18:00 local time.

## HA dispatch payload

Home Assistant triggers a `repository_dispatch` event with a **batch** of recent readings:

```json
{
  "event_type": "update_pool_status",
  "client_payload": {
    "entries": [
      {
        "updated_at":              "2026-04-09T14:00:00+02:00",
        "temp_water_c":            17.2,
        "temp_air_c":              21.8,
        "pump_on":                 true,
        "swimmable":               false,
        "solar_energy_total_kwh":  11581.9
      },
      {
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
    ]
  }
}
```

The last entry of `entries` becomes the new `status.json` (what the dashboard reads). Each
entry is appended to `history.json`. The legacy single-payload format (fields at the top
of `client_payload`, no `entries` array) is still accepted and treated as a 1-entry batch.

**Notes:**
- `solar_energy_total_kwh` is the cumulative lifetime counter from the inverter (not daily production).
- `updated_at` must include a UTC offset (e.g. `+02:00`) — used by the Python aggregation to determine local calendar date.
- `swimmable` and `pump_on` are booleans, not strings.

## GitHub Actions setup

The workflow in `.github/workflows/update-status.yml` is triggered by every
`repository_dispatch` event, but its job only starts when the serialized payload contains
an `updated_at` timestamp at 00:00, 06:00, 12:00, or 18:00 local time. Other workflow runs
are marked as skipped before a runner is allocated. The filter searches the full payload,
so both the batch and legacy single-reading formats are supported.

With the current single-reading payloads, only four measurements per day are stored.
Intermediate readings are intentionally discarded, so detailed daily duration metrics
such as pump-on and swimmable minutes are approximate.

The workflow only needs `contents: write` (commit data files); GitHub Pages is deployed by
the built-in `pages-build-deployment` workflow which is free (not counted against Actions
minutes). No additional secrets needed beyond `GITHUB_TOKEN` (automatic).

Enable GitHub Pages in repo settings: **Settings → Pages → Source → Deploy from a branch
→ `main` / `/` (root)**. Do NOT pick "GitHub Actions" — that mode bills extra minutes.

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
| `scripts/apply_payload.py` | Workflow entry-point — reads `PAYLOAD`, updates status/history/summary/sw.js |
| `scripts/aggregate_daily.py` | Aggregation helpers (pure functions, imported by `apply_payload.py`) |
| `scripts/test_daily_summary.py` | Test suite — run before merging: `python3 scripts/test_daily_summary.py` |
| `scripts/backfill_daily_summary.py` | One-time backfill from history.json |
