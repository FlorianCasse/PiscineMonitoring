# Security Review: piscinemonitoring

## Summary
- Total findings: 7
- Critical: 0 | High: 3 | Medium: 3 | Low: 1
- PRs opened: 2
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/38
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/39
- Issues opened: 5
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/40
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/41
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/42
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/43
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/44

## Findings

### [HIGH] Third-party CDN scripts loaded without Subresource Integrity
- **File:** `index.html` (lines 437-439)
- **Description:** React 18.3.1, ReactDOM 18.3.1, and `@babel/standalone` 7.29.0 are loaded from `https://unpkg.com/...` without `integrity=` (SRI) attributes. Compromise of unpkg or an on-path attacker who can substitute these JS bundles obtains full JavaScript execution on `piscine.florian-casse.fr`. The CSP allows `'unsafe-eval'` and `'unsafe-inline'`, so there is no defence-in-depth backstop.
- **Remediation:** Self-host the three libraries OR add `integrity="sha384-..."` to each `<script>` tag. Strongest fix: pre-transpile JSX at deploy time and drop Babel-standalone (which would also let CSP drop `'unsafe-eval'`).
- **PR-ready:** no
- **Action taken:** Issue #40 https://github.com/FlorianCasse/PiscineMonitoring/issues/40

### [HIGH] CSP allows 'unsafe-inline' and 'unsafe-eval' in script-src
- **File:** `index.html` (line 5)
- **Description:** `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com` neutralises CSP as an XSS mitigation. Required today only because Babel-standalone runs in the browser and the page contains large inline scripts. Any future regression that introduces an XSS sink (e.g. `dangerouslySetInnerHTML`) becomes immediately exploitable.
- **Remediation:** Pre-transpile JSX in CI, externalise inline scripts, then tighten CSP to `script-src 'self';`.
- **PR-ready:** no
- **Action taken:** Issue #41 https://github.com/FlorianCasse/PiscineMonitoring/issues/41

### [HIGH] GitHub Pages artifact uploads the entire repository
- **File:** `.github/workflows/update-status.yml` (final `actions/upload-pages-artifact@v3` step, `path: '.'`)
- **Description:** Setting `path: '.'` packages every tracked file (including `.github/`, `scripts/`, `CLAUDE.md`, `TODOS.md`, `README.md`, `.gitignore`) and serves them publicly via GitHub Pages. This leaks repository internals and makes any future accidentally-committed sensitive file (notes, tokens, internal scripts) immediately publicly fetchable.
- **Remediation:** Stage only the runtime files (`index.html`, `sw.js`, `manifest.json`, `icon.svg`, `CNAME`, the three data JSONs) into a `_site/` directory, then upload `_site/`.
- **PR-ready:** yes
- **Action taken:** PR #39 https://github.com/FlorianCasse/PiscineMonitoring/pull/39

### [MEDIUM] Service worker caches potentially-poisoned responses
- **File:** `sw.js` (full file)
- **Description:** Original `cacheFirst` / `networkFirst` only checked `res.ok` before writing to cache, and the same-origin gate compared `hostname` rather than full origin. A redirected or opaque response could be served (and historically cached). Also handled all request methods, not just GET.
- **Remediation:** Restrict caching to GET requests only and require `res.type === 'basic' && !res.redirected && res.ok` before writing to the cache. Switch the bypass check from `hostname` to full `origin`.
- **PR-ready:** yes
- **Action taken:** PR #38 https://github.com/FlorianCasse/PiscineMonitoring/pull/38

### [MEDIUM] No validation of `repository_dispatch` payload before writing to repo
- **File:** `.github/workflows/update-status.yml` ("Write status.json from HA payload" / "Append to history.json" / "Update daily_summary.json"); `scripts/aggregate_daily.py`
- **Description:** The workflow writes the raw `client_payload` to `status.json` and reads selected fields into `history.json` / `daily_summary.json` without validating types, ranges, key allow-list, or timestamp freshness. Any holder of a PAT authorised to dispatch the event can poison data, inject arbitrarily long strings into `reason`, or skew the rolling history. `toJson()` prevents shell command injection, but data integrity is unprotected.
- **Remediation:** Validate keys against an allow-list, enforce numeric ranges and timestamp window, strip control characters from `reason`, reject unknown keys. Audit and minimise the dispatch token's scope.
- **PR-ready:** no
- **Action taken:** Issue #42 https://github.com/FlorianCasse/PiscineMonitoring/issues/42

### [MEDIUM] No Permissions-Policy declared
- **File:** `index.html` (`<head>`)
- **Description:** No `Permissions-Policy` meta or response header. If an attacker gains script execution (XSS or compromised CDN), they can request camera, mic, geolocation, USB, payment, etc. None are needed by this read-only dashboard.
- **Remediation:** Add `<meta http-equiv="Permissions-Policy" content="accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=(), interest-cohort=()"/>` to `<head>`. Better as an HTTP header on the Pages response if configurable.
- **PR-ready:** no
- **Action taken:** Issue #43 https://github.com/FlorianCasse/PiscineMonitoring/issues/43

### [LOW] Approximate home coordinates hardcoded in client source
- **File:** `index.html` (lines 359-361 and 414-416)
- **Description:** `43.79, 4.83` (Nîmes/Vauvert area) is the hardcoded fallback for the Open-Meteo lat/lon. Combined with the public CNAME `piscine.florian-casse.fr` and live `pump_on` / `swimmable` telemetry, an observer can derive a town-scale home location and approximate occupancy patterns.
- **Remediation:** Move weather lookup server-side in the workflow and embed results in `status.json`, OR coarsen the default to one decimal (~10 km), OR ask for user `navigator.geolocation` consent.
- **PR-ready:** no
- **Action taken:** Issue #44 https://github.com/FlorianCasse/PiscineMonitoring/issues/44
