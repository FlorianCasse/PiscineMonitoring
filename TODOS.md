# PiscineMonitoring — Deferred TODOs

## From Iteration 3 CEO Review (2026-04-09)

### Year-over-year temperature comparison
**What:** Once daily_summary.json has 2+ full seasons, add a comparison view:
"April 2026 vs April 2027" — water temp overlay for the same date range in different years.
**Why:** The architecture already supports it (entries are dated). The dataset builds automatically.
Just needs 12+ months of data before it's useful.
**Effort:** S/M (human: ~4h / CC: ~20min)
**Priority:** P3 — revisit after first full season (autumn 2026)
**Depends on:** 1+ year of daily_summary.json data

### Forecast accuracy tracking
**What:** Each day, store `predicted_water_c` alongside the actual in daily_summary.json.
Display an accuracy score in the forecast section: "Mes prévisions: 87% précises (±1.5°C)."
**Why:** Makes the weather forecast trustworthy rather than magic. Also reveals when thermal
inertia assumptions break down (heat waves, sudden cold fronts).
**Effort:** S (human: 2h / CC: ~15min)
**Priority:** P2 — useful once the forecast is live for 2+ weeks
**Depends on:** Iteration 3 weather forecast feature being live

### Configurable pump wattage in settings drawer
**What:** Add a "Puissance pompe (kW)" field to the settings drawer (default 0.75).
Current cost formula hardcodes 0.75 kW, which may be wrong for the user's actual pump.
**Why:** Energy cost estimates are meaningless with a wrong wattage constant.
The settings drawer is already being built in Iteration 3 — one extra field.
**Effort:** XS (human: 30min / CC: ~5min)
**Priority:** P2 — add to Iteration 4 settings cleanup pass
**Depends on:** Iteration 3 settings drawer (energy cost)

## From Iteration 3 DX Review (2026-04-09)

### index.html modularization
**What:** Split the single-file `index.html` into separate JS modules (e.g., `charts.js`,
`settings.js`, `forecast.js`). After Iteration 3, index.html will be ~47KB of inline JS.
**Why:** Codex flagged this as the top structural DX risk for cold returns. A single file
mixing UI, i18n, fetch, derived logic, SVG rendering, and localStorage management is
hard to navigate after 6+ months.
**Effort:** M (human: ~4h / CC: ~20min)
**Priority:** P3 — post Iteration 3, when the scope is stable
**Depends on:** Iteration 3 complete and stable for at least one season

### Add MIT license + GitHub repo topics
**What:** Add `LICENSE` file (MIT) and set GitHub repo description + topics
(home-automation, pool-monitoring, home-assistant, github-pages).
**Why:** Without a license, forks are legally ambiguous. Without topics, the repo is
invisible in GitHub search.
**Effort:** XS (human: 5min / CC: 1min)
**Priority:** P3 — cosmetic but costs nothing

## Previously deferred

- Push notifications (ntfy.sh) — user explicitly skipped in Iteration 3
- pH/chlorine sensor integration — blocked on hardware purchase
- Seasonal mode (reduce staleness threshold in winter) — low priority
- LFS for history.json if git history becomes unwieldy (>1 year of data)
