# Security Review: piscinemonitoring

Date: 2026-04-27
Repository: `floriancasse/piscinemonitoring` @ `main` (commit `fbc7c5e`)
Reviewer: Claude (autonomous security review)

## Summary
- Total findings: **7**
- Critical: 0 | High: 2 | Medium: 3 | Low: 2
- PRs opened: **2**
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/29 — CSP hardening (medium)
  - https://github.com/FlorianCasse/PiscineMonitoring/pull/30 — status.json safe write (low)
- Issues opened: **5**
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/31 — Missing SRI on CDN scripts (high)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/32 — CSP allows `'unsafe-inline'` and `'unsafe-eval'` (high)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/33 — Missing Permissions-Policy / hardening headers (medium)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/34 — Service worker origin allowlist (low)
  - https://github.com/FlorianCasse/PiscineMonitoring/issues/35 — Public IoT telemetry exposure (low)

## Stack identified
- Static GitHub Pages site (no backend) deployed to `piscine.florian-casse.fr`.
- Frontend: `index.html` (vanilla JS + React 18 + Babel-standalone runtime JSX, all loaded from `unpkg.com`), service worker (`sw.js`).
- Data pipeline: GitHub Actions workflow (`.github/workflows/update-status.yml`) triggered by `repository_dispatch` events from Home Assistant; appends to `history.json` and `daily_summary.json`; writes `status.json`.
- Python aggregation under `scripts/` (no third-party deps).
- No package manager / no JS dependency manifest. Dependabot is enabled for `github-actions` only.

## Findings

### [HIGH] Missing Subresource Integrity on third-party CDN scripts
- **File:** `index.html` (lines 437-439)
- **Description:** React, ReactDOM, and `@babel/standalone` are loaded directly from `https://unpkg.com/...` without `integrity="sha384-..."`. A CDN compromise or path-resolution bug serves arbitrary JS into the page origin. The CSP also allows `'unsafe-inline'` and `'unsafe-eval'`, so injected code runs unimpeded.
- **Remediation:** Pin SRI hashes for each script tag and/or self-host the bundles. Long-term, replace `@babel/standalone` with a build step.
- **PR-ready:** no — requires network fetch to compute hashes and/or build pipeline.
- **Action taken:** Issue https://github.com/FlorianCasse/PiscineMonitoring/issues/31

### [HIGH] CSP allows `'unsafe-inline'` and `'unsafe-eval'` in `script-src`
- **File:** `index.html` (line 5)
- **Description:** `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com` neutralizes CSP as an XSS mitigation. `'unsafe-eval'` is currently required by the runtime Babel transform; `'unsafe-inline'` is required by two large inline `<script>` blocks at lines 114 and 441.
- **Remediation:** Move JSX transpilation to a build step to drop `'unsafe-eval'`. Externalize inline scripts or inject a per-deploy nonce via the existing GitHub Actions `sed` mechanism (similar to `SW_VERSION_PLACEHOLDER`) to drop `'unsafe-inline'`.
- **PR-ready:** no — requires non-trivial refactor / build pipeline introduction.
- **Action taken:** Issue https://github.com/FlorianCasse/PiscineMonitoring/issues/32

### [MEDIUM] CSP missing `form-action` and `upgrade-insecure-requests`
- **File:** `index.html` (line 5)
- **Description:** Without `form-action 'self'`, an injected/legacy form could submit to an attacker-controlled origin. Without `upgrade-insecure-requests`, any future http:// reference is fetched in cleartext.
- **Remediation:** Append both directives to the CSP meta tag at deploy time via the existing `sed` injection step.
- **PR-ready:** yes
- **Action taken:** PR https://github.com/FlorianCasse/PiscineMonitoring/pull/29

### [MEDIUM] Missing `Permissions-Policy` and hardening headers
- **File:** `index.html` (`<head>`)
- **Description:** GitHub Pages does not allow custom HTTP headers. The page does not set a `Permissions-Policy` meta either, so the browser default policy applies for `geolocation`, `camera`, `microphone`, `payment`, `usb`, etc. With CSP weak on script (see HIGH issues), this is one extra layer of defense the site is missing.
- **Remediation:** Add `<meta http-equiv="Permissions-Policy" content="geolocation=(), camera=(), microphone=(), payment=(), usb=(), accelerometer=(), gyroscope=(), magnetometer=()"/>` to `<head>`. Long-term, front the site with a CDN/worker that can set real HTTP headers.
- **PR-ready:** no — multiple parallel branches already exist for this fix (`claude/fix-permissions-policy-guE6b`, `claude/security-fix-permissions-policy-LotRY`); avoiding duplicate PR.
- **Action taken:** Issue https://github.com/FlorianCasse/PiscineMonitoring/issues/33

### [MEDIUM] Babel-standalone runtime JSX transpile (supply-chain × CSP × performance)
- **File:** `index.html` (line 439)
- **Description:** `@babel/standalone@7.29.0` (~3 MB minified) is loaded from `unpkg.com` and used at runtime to compile the inline JSX in `<script type="text/babel">`. This is the root cause of three other findings: it forces `'unsafe-eval'` in CSP, it forces `'unsafe-inline'`, and it makes SRI brittle (any minor Babel version churn breaks the page if hashes are pinned). It is also the largest single download on the site.
- **Remediation:** Add a build step (Vite/esbuild). Output a single `app.js` bundle into the repo, drop the three `unpkg.com` scripts, and tighten CSP accordingly.
- **PR-ready:** no — requires owner sign-off on adding a build pipeline.
- **Action taken:** captured in https://github.com/FlorianCasse/PiscineMonitoring/issues/32 (HIGH unsafe-eval issue).

### [LOW] `status.json` written via shell `echo`, no JSON validation
- **File:** `.github/workflows/update-status.yml` (the "Write status.json from HA payload" step)
- **Description:** `echo "$PAYLOAD" > status.json` writes the raw payload string. If the dispatch sender posts non-JSON or `echo`-special content, the file is corrupted and served to clients until the next dispatch repairs it. Practical exploitability is low (only the repo owner can dispatch via `GITHUB_TOKEN` / a PAT), but validation is cheap.
- **Remediation:** Replace with a Python heredoc that `json.loads()`-validates the payload, asserts `isinstance(data, dict)`, then `json.dump`s it canonically.
- **PR-ready:** yes
- **Action taken:** PR https://github.com/FlorianCasse/PiscineMonitoring/pull/30

### [LOW] Service worker passes through *any* cross-origin request
- **File:** `sw.js` (lines 23-26)
- **Description:** The `fetch` handler accepts any cross-origin URL and proxies it to `fetch()`. A future developer (or compromised bundle) adding requests to a new host gets implicit pass-through. Hard-coded allowlist would mirror CSP and limit blast radius of an XSS via the Babel/CDN paths.
- **Remediation:** Add `ALLOWED_HOSTS` Set with `api.open-meteo.com`, `fonts.googleapis.com`, `fonts.gstatic.com`, `unpkg.com`.
- **PR-ready:** no — multiple parallel branches already exist (`claude/fix-sw-origin-allowlist-guE6b`, `claude/security-fix-sw-origin-validation-LotRY`); avoiding duplicate PR.
- **Action taken:** Issue https://github.com/FlorianCasse/PiscineMonitoring/issues/34

### [LOW] Public IoT telemetry exposure (by design)
- **File:** `history.json`, `daily_summary.json`, `status.json`
- **Description:** `history.json` (~7 days at 5-min cadence) and `daily_summary.json` (cumulative) are publicly readable. Pump-on minutes and outdoor air temperature are weak occupancy signals.
- **Remediation:** Decide explicitly whether full per-5-min history needs to be public; if not, serve only `daily_summary.json` and keep `history.json` private. Otherwise close as wontfix.
- **PR-ready:** no — design decision.
- **Action taken:** Issue https://github.com/FlorianCasse/PiscineMonitoring/issues/35

## Out-of-scope / negative results
- **No hardcoded secrets** found in tracked files (no API keys, tokens, passwords).
- **No SQL / command-injection** sinks in the Python scripts; they only read `os.environ['PAYLOAD']` and parse with `json.loads`. No `subprocess`, `os.system`, `eval`, `exec`, `pickle`, or `yaml.load`.
- **No path traversal** — file paths are hard-coded constants (`history.json`, `daily_summary.json`).
- **No unsafe deserialization** — only `json.loads` from a trusted env var.
- **GitHub Actions workflow uses pinned `@v4`/`@v5`/`@v3`** for `actions/checkout`, `configure-pages`, `upload-pages-artifact`, `deploy-pages`. Dependabot is configured for `github-actions` (weekly). Reasonable.
- **`GITHUB_TOKEN` permissions** in the workflow are scoped to the minimum needed (`contents: write`, `pages: write`, `id-token: write`).
- **`.gitignore`** sensible; no committed `.env` or `.gstack/` artifacts.
- **No mixed-content references** in HTML (all third-party hosts use https://).
- **CSP frame-ancestors 'none'** is set — clickjacking resistance present.
- **Referrer-Policy `strict-origin-when-cross-origin`** is set via meta — good.

## MCP failures
None. All API calls succeeded on first attempt.

---

This report is auto-generated as part of a multi-repo security audit. Owner action required on the linked issues / PRs.
