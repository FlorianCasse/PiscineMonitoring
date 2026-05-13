# Security Review: piscinemonitoring

## Summary
- Total findings: 6
- Critical: 0 | High: 1 | Medium: 3 | Low: 2
- PRs opened: 1
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/45
- Issues opened: 5 (URLs filled in below after creation)

## Scope
- Stack: static PWA on GitHub Pages (`piscine.florian-casse.fr`), vanilla JS + in-browser React/Babel from `unpkg.com`, JSON data files updated by GitHub Actions on `repository_dispatch` from Home Assistant.
- Files reviewed:
  - `index.html` (1303 lines — CSP meta, inline JS, in-browser Babel, React UI)
  - `sw.js` (service worker)
  - `manifest.json`
  - `status.json`, `daily_summary.json` (sampled), `history.json` (schema reviewed via README & workflow)
  - `scripts/aggregate_daily.py`, `scripts/backfill_daily_summary.py`
  - `.github/workflows/update-status.yml`
  - `CNAME`, `.gitignore`, `README.md`, `CLAUDE.md`
- Date: 2026-05-13

## Findings

### [HIGH] No Subresource Integrity (SRI) on CDN scripts
- **File:** `index.html` (lines 437–439)
- **Description:** Three production scripts (React 18.3.1, ReactDOM 18.3.1, Babel Standalone 7.29.0) are loaded from `https://unpkg.com/...` without `integrity=` attributes. `unpkg` resolves a semver-pinned URL but ultimately serves arbitrary content from the registry/CDN; a registry takeover, CDN compromise, or upstream tag replacement (`@latest`-style behaviour for malformed paths) would execute attacker-controlled JavaScript with full DOM and `localStorage` access. The existing CSP further permits `'unsafe-inline'` and `'unsafe-eval'` (required by Babel), so any injected script has minimal sandbox.
- **Remediation:** Add `integrity="sha384-..."` attributes (with `crossorigin="anonymous"` already present) on all three `<script src="https://unpkg.com/...">` tags. The hashes should be computed against the exact pinned bytes, e.g. `curl -sL <url> | openssl dgst -sha384 -binary | openssl base64 -A`. Alternatively, vendor the three libraries into the repo (`/vendor/react.min.js`, etc.) which removes the SRI requirement, lets the CSP drop `https://unpkg.com` from `script-src`, and eliminates third-party CDN trust entirely. Self-hosting is recommended given the site is a single-user dashboard.
- **PR-ready:** no (SRI hash computation requires verified network access to the CDN; placeholder hashes would brick production. Logged as issue with instructions.)
- **Action taken:** Issue <ISSUE_SRI_URL>

### [MEDIUM] CSP allows `'unsafe-inline'` and `'unsafe-eval'`
- **File:** `index.html` (line 5)
- **Description:** The CSP meta tag includes `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com` and `style-src 'self' 'unsafe-inline' ...`. `'unsafe-eval'` is required by the in-browser Babel transform (`<script type="text/babel">`), and `'unsafe-inline'` is needed by the inline `<script>` blocks. Both directives defeat most XSS mitigations CSP would otherwise provide.
- **Remediation:** Move the React tree to a pre-built bundle (Vite/esbuild) emitted as a static asset. With pre-compiled JSX, Babel-standalone (and `'unsafe-eval'`) can be removed entirely. Inline scripts can be moved to separate files or hashed (`'sha256-...'` source-list entries) to drop `'unsafe-inline'`. The same build can vendor React, removing the CDN exception. Until then, keep the CSP as the best-effort defence-in-depth it currently is.
- **PR-ready:** no (architectural change — adds a build step)
- **Action taken:** Issue <ISSUE_CSP_URL>

### [MEDIUM] Service worker intercepts every cross-origin request
- **File:** `sw.js` (lines 22–25, original)
- **Description:** The fetch handler called `fetch(e.request)` for every cross-origin URL (Open-Meteo, Google Fonts, unpkg). Although the browser still applies CORS to the result, the SW is in the response chain for traffic it does not own — any future logic change (logging, retry, caching) silently affects third-party traffic. The handler also caught non-GET requests via the cache-first branch, which would serve stale or 503 responses for unsafe methods.
- **Remediation:** Return early from the fetch listener when `url.origin !== self.location.origin` and when `e.request.method !== 'GET'`. The browser handles those requests directly, identical to no SW being installed for that origin.
- **PR-ready:** yes
- **Action taken:** PR #45 https://github.com/FlorianCasse/PiscineMonitoring/pull/45

### [MEDIUM] GitHub Actions writes `status.json` directly from untrusted-ish payload
- **File:** `.github/workflows/update-status.yml` (the "Write status.json from HA payload" step)
- **Description:** `echo "$PAYLOAD" > status.json` writes whatever `toJson(github.event.client_payload)` produces straight to a file that becomes a fetched JSON resource on the live site. The dispatch event requires a token with `repo` scope, so practical exploitability is gated by token control; however the payload is never schema-validated, so a malformed or maliciously crafted dispatch can serve malformed JSON or arbitrary string content (including extremely large payloads) to every visitor. The "Append to history.json" step inlines a Python heredoc that does no validation either, and `aggregate_daily.py` calls `json.loads(os.environ['PAYLOAD'])` without type/range checks.
- **Remediation:** Validate the payload before writing — use a small Python script (or the existing `aggregate_daily.py`) to: (a) parse `PAYLOAD` as JSON, (b) reject if not an object, (c) coerce each known field to its declared type and clamp ranges (`temp_water_c` numeric and in e.g. [-5, 50], `pump_on` strictly boolean, `reason` truncated to N chars), then re-serialise. This both prevents JSON injection / oversized payloads and protects the dashboard JS from type confusion.
- **PR-ready:** no (writing the schema validator deserves discussion of acceptable ranges; better as an issue first)
- **Action taken:** Issue <ISSUE_WORKFLOW_URL>

### [LOW] Approximate pool location committed in source and rendered on screen
- **File:** `index.html` (lines 359–360, 414–415, 1208–1209)
- **Description:** The fallback geolocation is hardcoded as `lat 43.79, lon 4.83` (Saint-Gilles, Gard, France) and rendered in the masthead (`{lat.toFixed(2)}°N` / `{lon.toFixed(2)}°E`). Combined with the CNAME `piscine.florian-casse.fr` (real name) and the public dashboard exposing solar/pump schedules, this discloses the approximate home location and an occupancy heuristic (pump runs, swimmable windows) that could aid physical surveillance.
- **Remediation:** Decide whether the dashboard is intended to be fully public. If yes, accept the trade-off and document it. If not: (a) move coordinate display behind a build-time flag, (b) reduce displayed precision to one decimal (`~11 km`), or (c) gate the entire site behind an auth proxy (Cloudflare Access, Tailscale Funnel, etc.). At minimum, do not render `lat.toFixed(2)°N / lon.toFixed(2)°E` in the masthead.
- **PR-ready:** no (privacy posture decision belongs to the owner)
- **Action taken:** Issue <ISSUE_PRIVACY_URL>

### [LOW] PWA `manifest.json` lacks `id` and `start_url` precision
- **File:** `manifest.json` (whole file)
- **Description:** Missing `id` field means the PWA install identity is tied to `start_url`; if `start_url` changes the installed app fork-installs. Minor hygiene issue — not a vulnerability — but worth noting in a security pass since misconfigured manifests can be abused for install spoofing on shared hosts.
- **Remediation:** Add `"id": "/"` (or a stable opaque identifier). Pin `"start_url": "/?source=pwa"` for analytics if desired.
- **PR-ready:** no (cosmetic)
- **Action taken:** Issue <ISSUE_MANIFEST_URL>

## Notes on data files (informational, not findings)
- `status.json`, `daily_summary.json`, `history.json` contain no credentials, no IP addresses, no sensor MAC/IDs, and no user-identifiable data beyond water/air temperatures, pump on/off, and cumulative solar kWh. No PII in the JSON files themselves. The privacy concern is the combination with `CNAME` (real name) and the displayed coordinates — covered in the LOW finding above.
- The GitHub Actions workflow has no hardcoded secrets and uses only `GITHUB_TOKEN`.
- No `target="_blank"` links, no `innerHTML` / `dangerouslySetInnerHTML` / `eval` calls in the React tree, no mixed-content references — clean on those axes.

## Label note
The MCP tool used to apply labels auto-created severity labels in uppercase (`MEDIUM`) rather than the requested lowercase. The repository's existing `high` label remains lowercase. Owner can rename via `Settings → Labels` if uniform casing is desired.
