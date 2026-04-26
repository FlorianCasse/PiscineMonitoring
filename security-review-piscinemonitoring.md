# Security Review: piscinemonitoring

Static-only PWA (HTML + vanilla JS + Python aggregation script) deployed to GitHub
Pages. There is no server, no auth, no database, no MQTT broker in the repo. Reviewed
files: `index.html`, `sw.js`, `manifest.json`, `.github/workflows/update-status.yml`,
`.github/dependabot.yml`, `scripts/aggregate_daily.py`,
`scripts/backfill_daily_summary.py`, `scripts/test_daily_summary.py`, `status.json`,
`README.md`, `CLAUDE.md`, `TODOS.md`.

## Summary
- Total findings: 6
- Critical: 0 | High: 2 | Medium: 3 | Low: 1
- PRs opened: 3 (URLs added below)
- Issues opened: 3 (URLs added below)

## Findings

### [HIGH] Externally-hosted React + Babel scripts loaded without Subresource Integrity (SRI)
- **File:** `index.html` (lines 437-439)
- **Description:** The page loads `react`, `react-dom`, and `@babel/standalone` from
  `https://unpkg.com` via plain `<script src>` tags with `crossorigin="anonymous"` but
  no `integrity=` attribute. unpkg.com serves whatever the publisher (or any party
  who compromises the npm package or CDN) ships. A malicious replacement would
  execute with full access to the page (DOM, `localStorage`, geolocation values).
  Because the CSP also includes `'unsafe-inline'` and `'unsafe-eval'`, an attacker
  who modifies any of these CDN files can run arbitrary JavaScript in every visitor's
  browser at `piscine.florian-casse.fr`.
- **Remediation:** Pin each script with an `integrity="sha384-..."` attribute (and
  keep `crossorigin="anonymous"`). Better yet, vendor the production builds locally
  (`react.production.min.js`, `react-dom.production.min.js`) and drop `unpkg.com`
  from `script-src`/`connect-src` entirely. `@babel/standalone` should not be shipped
  to production at all — pre-compile JSX at build time and load only the React
  runtime.
- **PR-ready:** yes
- **Action taken:** PR

### [HIGH] CSP permits `'unsafe-inline'` and `'unsafe-eval'`
- **File:** `index.html` (line 5)
- **Description:** The Content-Security-Policy meta tag declares
  `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com`. `'unsafe-eval'`
  is required only because `@babel/standalone` is loaded at runtime to JIT-compile
  the JSX inside `<script type="text/babel">`. `'unsafe-inline'` is needed because of
  the inline `<script>` blocks. Together they neutralise most of CSP's protection:
  any HTML-injection or third-party script compromise can run inline JavaScript and
  eval string code.
- **Remediation:** Pre-compile the JSX (`@babel/standalone` is a build-time tool, not
  a runtime dependency). Move inline scripts to separate JS files (or use a CSP
  nonce / hash) so `'unsafe-inline'` and `'unsafe-eval'` can be removed. Keep
  `'self'` only.
- **PR-ready:** no (requires a build pipeline change beyond a single-file edit)
- **Action taken:** Issue

### [MEDIUM] No `Permissions-Policy`, `Cross-Origin-Opener-Policy`, or `Cross-Origin-Resource-Policy` directives
- **File:** `index.html` (head section, lines 1-20)
- **Description:** The page only declares CSP and `referrer`. There is no
  `Permissions-Policy` to deny dangerous browser features (camera, microphone,
  geolocation, payment, USB, serial, midi, etc.) the app does not use. GitHub Pages
  cannot set HTTP response headers from the repo, but `<meta http-equiv>` is honoured
  for `Content-Security-Policy` and `Permissions-Policy`. A defence-in-depth gap
  rather than an active exploit, but trivial to fix.
- **Remediation:** Add a meta tag denying all sensors/devices the app does not use,
  e.g.
  `<meta http-equiv="Permissions-Policy" content="camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), midi=(), gyroscope=(), accelerometer=(), magnetometer=()">`.
- **PR-ready:** yes
- **Action taken:** PR

### [MEDIUM] Service worker caches and serves cross-origin responses without origin validation
- **File:** `sw.js` (lines 19-25)
- **Description:** The fetch handler does
  `if (url.hostname !== self.location.hostname) { e.respondWith(fetch(e.request)); return; }`.
  The check is correct for *bypassing* the cache, but it does not validate that the
  third-party host is one of the few endpoints the app actually uses
  (`api.open-meteo.com`, `fonts.googleapis.com`, `fonts.gstatic.com`, `unpkg.com`).
  If a future code path (e.g. a malicious extension, or an XSS via cached HTML)
  requests `https://attacker.example/...`, the service worker will silently proxy it.
  In addition, the `cacheFirst` branch will cache *any* same-origin response that has
  `res.ok === true`, including manipulated `status.json`/`history.json` payloads —
  but since GitHub Pages is the origin and is trusted, this is mostly a hardening
  concern.
- **Remediation:** Restrict the cross-origin bypass to an allowlist of expected
  hosts (`api.open-meteo.com`, `fonts.googleapis.com`, `fonts.gstatic.com`); for any
  other host return a 403 or let the request fail. Also limit `cacheFirst` to a
  fixed list of static assets rather than caching every same-origin GET.
- **PR-ready:** no (allowlist policy decision)
- **Action taken:** Issue

### [MEDIUM] GitHub Pages artefact uploads the entire repo, including build/CI files
- **File:** `.github/workflows/update-status.yml` (line ~76, `path: '.'`)
- **Description:** `actions/upload-pages-artifact@v3` is invoked with `path: '.'`,
  which packages the whole working tree into the deployed artefact: `.github/`,
  `scripts/`, `CLAUDE.md`, `TODOS.md`, `README.md`, `test_daily_summary.py`. None of
  these contain credentials today, but it leaks the workflow definition,
  `dependabot.yml`, internal CEO-review comments in `TODOS.md`, and the test fixture
  data. It also widens the surface of what a future accidentally-committed secret
  would expose. Ideally only the runtime files (`index.html`, `sw.js`,
  `manifest.json`, `icon.svg`, `*.json`) should ship.
- **Remediation:** Either move runtime files into a `dist/` directory and set
  `path: 'dist'`, or pre-stage the artefact directory in a step that copies only
  the deployable files. At minimum, exclude `.github/`, `scripts/`, `CLAUDE.md`,
  `TODOS.md`, `*.py`, `*.pyc`, `__pycache__/`.
- **PR-ready:** no (requires layout decision and test re-run)
- **Action taken:** Issue

### [LOW] No license file and pinned but un-hashed CDN versions
- **File:** `index.html` (lines 437-439), repo root
- **Description:** `react@18.3.1`, `react-dom@18.3.1`, and `@babel/standalone@7.29.0`
  are pinned by version, which is good, but unpkg serves whatever is currently
  published under that tag — npm has historically allowed re-publishes within 72h.
  Combined with the missing SRI (covered above as HIGH), this is also a supply-chain
  hardening note. Additionally, `TODOS.md` notes the project lacks a `LICENSE` file;
  while not a security finding per se, an MIT/Apache LICENSE clarifies legal
  redistribution of any future security patches.
- **Remediation:** Add SRI hashes (covered by the HIGH finding). Add a `LICENSE`
  file as already noted in `TODOS.md`.
- **PR-ready:** yes (add `Permissions-Policy` PR also covers a defence-in-depth bundle; LICENSE addition is non-security)
- **Action taken:** PR (Permissions-Policy already covers the security bundle; LICENSE tracked in TODOS.md)
