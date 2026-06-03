# Security Review: PiscineMonitoring

**Date:** 2026-06-03
**Branch:** `claude/youthful-goldberg-7EBBN`
**Reviewer:** Claude (claude-opus-4-7)

## Summary
- Total findings: 4
- Critical: 0 | High: 0 | Medium: 2 | Low: 2
- PRs opened: 1 — https://github.com/FlorianCasse/PiscineMonitoring/pull/65
- Issues opened: 3
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/62 (SRI)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/63 (Dependabot)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/64 (CSP)
- Label note: `CRITICAL` and `HIGH` labels do not exist in this repo and were not needed; severities are encoded in issue titles. `Claude`, `security`, `MEDIUM`, `LOW` were applied where applicable.
- Scope checked: HTML/JS (`index.html`, `sw.js`), Python scripts (`scripts/*.py`), JSON data files (`history.json`, `daily_summary.json`, `status.json`), CI workflows (`.github/workflows/update-status.yml`), Dependabot config, manifest, CNAME.

Overall posture is strong for a static GitHub Pages PWA:
- Comprehensive CSP meta tag already in place (default-src 'self', frame-ancestors 'none', object-src 'none').
- No hardcoded secrets, API keys, or credentials in source, config, or JSON data.
- JSON data files contain only sensor readings (water/air temp, kWh, booleans, ISO timestamps). No addresses, names, IPs, MAC addresses, or device IDs.
- Python scripts use no dangerous primitives (no `eval`, `exec`, `pickle`, `subprocess`, `shell=True`, `yaml.load`).
- Service worker correctly bypasses cache for cross-origin requests (Open-Meteo) and uses network-first for data files.
- GitHub Actions workflow uses minimum permissions (`contents: write` only), pinned action versions (`actions/checkout@v4`), and safely passes the dispatch payload via env var rather than shell interpolation (no command injection vector).
- React rendering auto-escapes interpolated values (e.g., `status.reason`), so the JSON-into-DOM flow is XSS-safe by default.
- No `innerHTML`, `outerHTML`, `document.write`, `eval`, `new Function`, or `dangerouslySetInnerHTML` anywhere in JS.

Findings below address hardening gaps and defense-in-depth rather than active exploit paths.

## Findings

### [MEDIUM] Missing Subresource Integrity (SRI) on CDN scripts
- **File:** `index.html` (lines 437-439)
- **Description:** Three third-party scripts are loaded from `unpkg.com` without `integrity` attributes:
  - `react@18.3.1/umd/react.production.min.js`
  - `react-dom@18.3.1/umd/react-dom.production.min.js`
  - `@babel/standalone@7.29.0/babel.min.js`
  Without SRI, a compromise of unpkg.com (or an MITM bypassing TLS on a user's network) could deliver malicious script that executes with the page's origin. The page already grants `'unsafe-inline' 'unsafe-eval'` and reads sensor history from same-origin JSON; a malicious bundle would have full DOM access. The CSP `script-src` allows `https://unpkg.com`, so a tampered response would not be blocked.
- **Remediation:** Add `integrity="sha384-..."` and keep `crossorigin="anonymous"` on each script tag. Generate hashes locally (in an environment with outbound network access) via `curl -s https://unpkg.com/<pkg>/<file> | openssl dgst -sha384 -binary | openssl base64 -A`. Renew when versions are bumped. Hashes must be computed and verified by hand because the review sandbox cannot reach unpkg.com and pasting an unverified hash would break the page.
- **PR-ready:** no (requires live network access to compute and verify SRI hashes against the exact bytes served by unpkg.com)
- **Action taken:** Issue #62 https://github.com/FlorianCasse/PiscineMonitoring/issues/62

### [MEDIUM] Hardcoded default GPS coordinates expose pool location
- **File:** `index.html` (lines 359-360, 414-415)
- **Description:** The dashboard falls back to hardcoded coordinates `lat=43.79, lon=4.83` when `localStorage` is empty. These are passed to the Open-Meteo forecast endpoint and rendered on screen (lines 1208-1209: `{data.location.lat.toFixed(2)}°N` / `°E`). The coordinates point to a specific area in southern France (Nîmes/Camargue), and the production domain is the public CNAME `piscine.florian-casse.fr`, which already discloses the owner's surname. The combination of public domain + identifiable surname + hardcoded fallback coordinates in source rendered to every first-time visitor is a privacy issue (location disclosure of a private residence) even if the user later overrides via the settings drawer.
- **Remediation:** Drop the hardcoded fallback. If `piscine_lat` / `piscine_lon` are not set, skip the Open-Meteo call and omit the coordinate header instead of leaking a default. The forecast section already gracefully handles `meteo == null` (returns null from `fetchMeteo` when lat/lon are falsy).
- **PR-ready:** yes
- **Action taken:** PR #65 https://github.com/FlorianCasse/PiscineMonitoring/pull/65

### [LOW] CDN dependencies not tracked by Dependabot
- **File:** `.github/dependabot.yml`, `index.html`
- **Description:** Dependabot is configured for `github-actions` only. The three pinned unpkg.com scripts (React 18.3.1, ReactDOM 18.3.1, Babel standalone 7.29.0) are not monitored for new releases or known CVEs. There is no `package.json` (pure HTML/JS), so this is the only practical way to be alerted to upstream advisories.
- **Remediation:** Either (a) add a renovate.json or rely on manual review, or (b) accept the gap and add a calendar reminder. Lowest cost: document the manual review cadence in `README.md` and pin to specific commit hashes when SRI is added (covered by finding #1).
- **PR-ready:** no (process / documentation change, not a code fix)
- **Action taken:** Issue #63 https://github.com/FlorianCasse/PiscineMonitoring/issues/63

### [LOW] CSP allows `'unsafe-inline'` and `'unsafe-eval'`
- **File:** `index.html` (line 5)
- **Description:** The CSP `script-src` includes `'unsafe-inline'` (required by the large inline `<script type="text/babel">` block) and `'unsafe-eval'` (required by Babel standalone, which compiles JSX in the browser via `eval`/`Function`). This weakens the CSP's mitigation of injected `<script>` tags or inline event handlers if a same-origin XSS sink ever appears. Currently no such sink exists (no `innerHTML`, no `dangerouslySetInnerHTML`, React auto-escapes), so this is defense-in-depth only.
- **Remediation:** Long-term: precompile JSX at build time, drop Babel standalone, switch to a strict CSP with `nonce-...` or `'strict-dynamic'`. Short-term: nothing actionable without a build step, which contradicts the project's "single static HTML file" architecture. Recommend revisiting if/when `index.html` modularization (already listed in `TODOS.md`) is undertaken.
- **PR-ready:** no (architectural change tracked separately)
- **Action taken:** Issue #64 https://github.com/FlorianCasse/PiscineMonitoring/issues/64

## What was checked
- HTML/JS: `index.html` (1303 lines) — inline scripts, React rendering paths, JSON data sinks, CSP meta tag, third-party script tags.
- Service worker: `sw.js` — cache scope, cross-origin handling, data freshness strategy.
- Python scripts: `apply_payload.py`, `aggregate_daily.py`, `backfill_daily_summary.py`, `test_daily_summary.py` — input parsing, file writes, dangerous primitives, subprocess use.
- JSON data files: sampled `history.json` (320 KB), `daily_summary.json` (12 KB), `status.json` (full) for PII (addresses, names, IPs, MAC/device IDs, tokens, coordinates).
- CI workflows: `.github/workflows/update-status.yml` — permissions, secret handling, payload-to-shell pathway.
- Dependabot: `.github/dependabot.yml` — coverage scope.
- Other config: `manifest.json`, `CNAME`, `.gitignore`, `icon.svg`.
- Out of scope: production GitHub Pages headers (cannot be set on Pages without a CDN proxy); the Home Assistant side of the dispatch (separate codebase); Open-Meteo API trust (already same-origin-isolated by CSP `connect-src`).
