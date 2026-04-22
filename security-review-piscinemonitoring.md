# Security Review: PiscineMonitoring

Date: 2026-04-21
Reviewer: Claude (autonomous)
Scope: static PWA on GitHub Pages — `index.html`, `sw.js`, `manifest.json`, JSON data files, `scripts/*.py`, `.github/workflows/*`.

## Summary
- Total findings: 7
- Critical: 0 | High: 3 | Medium: 1 | Low: 2 | Info: 1
- PRs opened: 1
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/19
- Issues opened: 5
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/20
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/21
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/22
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/23
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/24

Labels used: `Claude`, `security`, `MEDIUM`, `LOW`. `CRITICAL` and `HIGH` labels do not exist in the repo — per the fallback rule, those findings carry a `[Claude] [HIGH]` title prefix.

No hardcoded secrets, tokens, or API keys were found in any file. No XSS sinks (`innerHTML`, `document.write`, `dangerouslySetInnerHTML`, etc.) are present — data is rendered exclusively via React JSX, which escapes by default. No `eval` / `new Function` calls in application code (the `'unsafe-eval'` CSP directive is needed only because `@babel/standalone` uses them internally to transpile `<script type="text/babel">` at runtime — see finding H2). All Python scripts under `scripts/` are stdlib-only, use `json.loads` (no `pickle`, no `os.system`, no `shell=True`), and do not accept untrusted CLI input.

## Findings

### [HIGH] Actions pinned by mutable tag; workflow-level write permissions
- **File:** `.github/workflows/update-status.yml` (lines 25, 66, 68, 71)
- **Description:** Every `uses:` pins to a tag (`actions/checkout@v4`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`). Tags are mutable — a compromised or coerced maintainer can retag a malicious commit onto `v4`, and it will silently run with `contents: write` + `pages: write` + `id-token: write` on the repo's default branch. Additionally, those write permissions were declared at the workflow level, so any future job added to this file inherits them automatically.
- **Remediation:** Pin each action to an immutable commit SHA with a `# vX.Y.Z` trailing comment. Default workflow permissions to `contents: read` and scope write permissions to the single job that needs them.
- **PR-ready:** yes
- **Action taken:** PR #19 — https://github.com/FlorianCasse/PiscineMonitoring/pull/19

### [HIGH] Service worker opportunistically cached any same-origin GET
- **File:** `sw.js` (lines 20-32)
- **Description:** The `fetch` handler used `cacheFirst` for every same-origin GET that did not match the three known data-JSON paths. This meant any future URL at the same origin — a mistyped endpoint, a preview/staging path, an inadvertently published file — would be cached and served offline, potentially forever (until the cache key rotates via `SW_VERSION_PLACEHOLDER`). This creates cache-poisoning / stale-content risk.
- **Remediation:** Handle only same-origin `GET` requests; cache-first strictly for the allowlisted static shell (`/`, `index.html`, `manifest.json`, `icon.svg`, `sw.js`, any `.html`); network-first strictly for the three data JSONs; let everything else fall through to the network untouched. Additionally only persist responses with `res.type === 'basic'` to block opaque cross-origin responses.
- **PR-ready:** yes
- **Action taken:** PR #19 — https://github.com/FlorianCasse/PiscineMonitoring/pull/19

### [HIGH] Missing Subresource Integrity on `unpkg.com` scripts
- **File:** `index.html` (lines 437, 438, 439)
- **Description:** `react@18.3.1`, `react-dom@18.3.1`, and `@babel/standalone@7.29.0` are loaded from `unpkg.com` with `crossorigin="anonymous"` but no `integrity=` attribute. CSP explicitly whitelists `https://unpkg.com` in `script-src` alongside `'unsafe-eval'` and `'unsafe-inline'`. Any compromise of unpkg.com (or the upstream npm tarballs) directly yields JavaScript execution in the `piscine.florian-casse.fr` origin.
- **Remediation:** Compute SHA-384 hashes locally and add `integrity="sha384-..."` to each script tag. Best fix: remove `@babel/standalone` by pre-compiling JSX at build time (also closes finding H2).
- **PR-ready:** no (sandbox running this review cannot reach unpkg.com to compute verified hashes; shipping unverified hashes would break the site)
- **Action taken:** Issue #20 — https://github.com/FlorianCasse/PiscineMonitoring/issues/20

### [HIGH] CSP uses `'unsafe-eval'` and `'unsafe-inline'` in `script-src`
- **File:** `index.html` (line 5)
- **Description:** The CSP meta allows `'unsafe-eval'` (for `@babel/standalone` runtime JSX compilation) and `'unsafe-inline'` (for the two inline `<script>` blocks). `'unsafe-inline'` in `script-src` largely neutralises CSP's XSS mitigation benefit; `'unsafe-eval'` enables string-to-code execution.
- **Remediation:** Introduce a build step (Vite / esbuild) to pre-compile JSX and bundle React into a same-origin script. Move the two inline `<script>` blocks into same-origin files. Target CSP drops to `script-src 'self'`.
- **PR-ready:** no (structural refactor — out of scope for a bounded security pass)
- **Action taken:** Issue #21 — https://github.com/FlorianCasse/PiscineMonitoring/issues/21

### [MEDIUM] `repository_dispatch` payload persisted & served without authenticity/shape validation
- **File:** `.github/workflows/update-status.yml` (steps: "Write status.json", "Append to history.json")
- **Description:** `github.event.client_payload` is written straight to `status.json` and its fields appended to `history.json`. The served PWA then reads those JSON files. There is no HMAC on the payload and no per-field type / bound checks. If the Home Assistant host or the dispatching token leak, an attacker can poison the site's data feed. A future rendering regression that interpolates `reason` / `updated_at` via `innerHTML` would become stored XSS.
- **Remediation:** The accompanying PR adds a minimal "is this valid JSON" check before `status.json` is written. Full fix: add per-field type/bounds validation in the Python steps, and ideally an HMAC on `payload||timestamp` verified against an `Actions secret`.
- **PR-ready:** partial (JSON-parse validation landed in PR #19; deeper schema & HMAC tracked in issue)
- **Action taken:** PR #19 (partial) + Issue #22 — https://github.com/FlorianCasse/PiscineMonitoring/issues/22

### [LOW] No `Permissions-Policy` / other optional hardening headers
- **File:** `index.html`
- **Description:** The page does not declare a `Permissions-Policy` disabling unused features (geolocation, camera, mic, payment, etc.). GitHub Pages does not let us set arbitrary HTTP response headers, so meta-tag equivalents are the only lever.
- **Remediation:** Add a `<meta http-equiv="Permissions-Policy" content="geolocation=(), camera=(), ...">` and `<meta http-equiv="X-Content-Type-Options" content="nosniff">`. Confirm "Enforce HTTPS" is enabled for the custom domain in repo Settings → Pages (gives HSTS from GitHub's edge).
- **PR-ready:** no (held back because `Permissions-Policy` via meta only works in some browsers and could be cargo-culting without real benefit — opened as tracked issue for maintainer decision)
- **Action taken:** Issue #23 — https://github.com/FlorianCasse/PiscineMonitoring/issues/23

### [LOW] Dependabot config scopes only `github-actions`
- **File:** `.github/dependabot.yml`
- **Description:** Only the `github-actions` ecosystem is tracked. If a Python dependency is ever added to `scripts/`, it will not be updated by Dependabot.
- **Remediation:** Keep the Python scripts stdlib-only (add a CI assertion) or add `scripts/requirements.txt` and a `pip` entry to `.github/dependabot.yml`.
- **PR-ready:** no (forward-looking — no pip deps exist today)
- **Action taken:** Issue #24 — https://github.com/FlorianCasse/PiscineMonitoring/issues/24

### [INFO] No hardcoded secrets or XSS sinks
- **File:** entire tree
- **Description:** Grep for `(api[_-]?key|secret|token|password|bearer|Authorization)` across `index.html`, `sw.js`, `manifest.json`, `scripts/*.py`, `.github/workflows/*.yml` returned no matches. Grep for `innerHTML|outerHTML|document.write|dangerouslySetInnerHTML|eval|new Function` in application code returned no matches (the `eval` mention in line 5 of `index.html` is the CSP policy text itself — see H2). Open-Meteo API is called anonymously without a key (none is required).
- **Remediation:** none — record of a clean result for the scope.
- **PR-ready:** n/a
- **Action taken:** none
