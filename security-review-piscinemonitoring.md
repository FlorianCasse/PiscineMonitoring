# Security Review: piscinemonitoring

_Reviewed 2026-04-17 against default branch `main` @ `a694ebab43f91181b0755e8a5c7868b537f8b31a`._

## Summary
- Total findings: 4
- Critical: 0 | High: 0 | Medium: 2 | Low: 2
- PRs opened: 0
- Issues opened: 4
  - #1 [MEDIUM] Add Content-Security-Policy meta tag — https://github.com/FlorianCasse/PiscineMonitoring/issues/1
  - #2 [MEDIUM] Pin GitHub Actions to commit SHAs — https://github.com/FlorianCasse/PiscineMonitoring/issues/2
  - #3 [LOW] innerHTML defense-in-depth — https://github.com/FlorianCasse/PiscineMonitoring/issues/3
  - #4 [LOW] Inline script/style force `'unsafe-inline'` — https://github.com/FlorianCasse/PiscineMonitoring/issues/4

All Issues carry the `security`, `Claude`, and severity labels.

## Scope Reviewed

### Files
- `index.html` (74 KB, full file) — inline `<style>` + inline `<script>` app code, all DOM sinks (`innerHTML`, `textContent`), all `fetch` calls, all `localStorage` keys, all event handlers.
- `sw.js` — service worker cache strategy, cross-origin passthrough, cache naming.
- `manifest.json` — PWA manifest (no concerns).
- `icon.svg` — static asset.
- `scripts/aggregate_daily.py` — daily summary aggregation called by CI. Inspected `json.loads`, file I/O, no eval/exec/subprocess/pickle.
- `scripts/backfill_daily_summary.py` — one-time backfill. Same clean pattern.
- `scripts/test_daily_summary.py` — unit tests.
- `.github/workflows/update-status.yml` — the sole CI workflow (repository_dispatch → write status.json + history.json → deploy Pages).
- `.gitignore`, `README.md`, `CLAUDE.md`, `TODOS.md`, `CNAME`.
- Data files (`status.json`, `history.json`, `daily_summary.json`) — structurally inspected, no secrets.

### Dependency manifests
None in the repo. The frontend has zero external runtime dependencies (no npm, no CDN `<script>`). The only external HTTP endpoint is `https://api.open-meteo.com/v1/forecast` (public, no key). Python scripts use only the standard library.

### Threat model checked
- Hardcoded secrets / tokens / credentials: **none found**.
- Injection (SQL/command/template/path): **N/A** — no SQL, no shell construction from user input, no templating.
- Unsafe deserialization / `eval` / `exec` / `pickle`: **none found**.
- Insecure deserialization in Python: `json.loads` only, with `try/except` fallbacks.
- Workflow `run:` steps: payload is passed via `env:` (safe) rather than `${{ ... }}` interpolation into the shell. `echo "$PAYLOAD" > status.json` is quoted and `toJson`-escaped — no command injection.
- `GITHUB_SHA` expansion in `sed` — GitHub guarantees 40-char hex, safe.
- Service worker scope / caching: passes cross-origin through, caches local only, invalidates on each deploy via SHA-prefixed cache name.
- `localStorage` consumers: `tariff`/`lat`/`lon` parsed with `parseFloat` + `isNaN` guard before use in URL construction (`index.html:1638`) — no injection.
- CORS / headers / auth: N/A (static site, no backend).
- File permissions: N/A (no executable artifacts shipped).
- IoT concerns (MQTT/WiFi creds/OTA): **out of scope** — this repo is the dashboard only; sensor ingestion lives on the Home Assistant side.

## Findings

### [MEDIUM] Missing Content-Security-Policy on public Pages site
- **File:** `index.html` (head, lines 4–5)
- **Description:** The page has no CSP header or meta. No immediate exploit today (no CDNs, one inline script), but any future XSS sink or accidental third-party inclusion has no defense-in-depth layer. Adding CSP also reinforces the companion innerHTML finding.
- **Remediation:** Insert after `<meta charset="UTF-8">`:
  ```html
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.open-meteo.com; manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  ```
  `'unsafe-inline'` is required until the companion "inline script/style" finding is resolved.
- **PR-ready:** no — `index.html` is 74 KB, exceeds inline push size in the current tool channel. The patch above is precise and single-file; apply manually in under a minute.
- **Action taken:** Issue #1 — https://github.com/FlorianCasse/PiscineMonitoring/issues/1

### [MEDIUM] GitHub Actions pinned to floating major tags
- **File:** `.github/workflows/update-status.yml` (lines 22, 73, 75, 78)
- **Description:** Four third-party actions (`actions/checkout@v4`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`) run with `contents: write`, `pages: write`, and `id-token: write`. A compromised action account or moved tag would execute arbitrary code with repo write access. OSSF Scorecard and GitHub's hardening guide recommend pinning to 40-char commit SHAs.
- **Remediation:** Replace each `@vN` with `@<sha> # vN.x.x` (resolve the SHA from the action's releases page at pin time). Add a `.github/dependabot.yml` with `package-ecosystem: github-actions` so SHA bumps become reviewed PRs.
- **PR-ready:** no — SHAs must be resolved live against the upstream repos at pin time and verified by the owner.
- **Action taken:** Issue #2 — https://github.com/FlorianCasse/PiscineMonitoring/issues/2

### [LOW] innerHTML used with concatenated data (defense-in-depth fragility)
- **File:** `index.html` (lines 1077, 1348, 1354, 1366, 1374, 1405, 1432, 1455, 1474, 1486, 1495, 1522, 1558, 1615, 1620, 1649, 1654)
- **Description:** Multiple `.innerHTML =` sinks concatenate strings from `history.json`, `daily_summary.json`, and `t(...)`. All current values are numeric, ISO-date, or developer-controlled translations, so there is no exploitable XSS today. The one potentially user-influenced field (`status.reason`) is correctly rendered via `.textContent` at line 969. The risk is future drift: any new string field reaching one of these sinks would become a stored XSS.
- **Remediation:** Prefer DOM construction (`createElement` + `textContent`), or introduce and uniformly apply an `esc()` HTML-escape helper, or add a CI grep that fails when new `innerHTML =` sinks are added without review.
- **PR-ready:** no — touches many lines in a large file; better as a dedicated refactor.
- **Action taken:** Issue #3 — https://github.com/FlorianCasse/PiscineMonitoring/issues/3

### [LOW] Inline `<script>` and `<style>` blocks force `'unsafe-inline'` in CSP
- **File:** `index.html` (inline `<style>` near line 12, inline `<script>` at line 657)
- **Description:** Because the entire app is inline, any CSP (see finding #1) must keep `'unsafe-inline'` on `script-src` and `style-src`, which negates the main anti-XSS benefit of CSP. Adopting a nonce-based CSP (the existing workflow already `sed`-substitutes `SW_VERSION_PLACEHOLDER` — add a `CSP_NONCE_PLACEHOLDER` in the same step) or moving to external `app.js`/`app.css` would close this.
- **Remediation:** Implement per-deploy nonce via the existing workflow `sed` step, or split out external files per the DX modularization TODO.
- **PR-ready:** no — structural change, best bundled with the DX modularization work already noted in `TODOS.md`.
- **Action taken:** Issue #4 — https://github.com/FlorianCasse/PiscineMonitoring/issues/4

## Overall posture
Strong. No secrets, no server-side attack surface, no dangerous deserialization, no shell/command injection vectors, clean parametrization of the one external API call (Open-Meteo). The four findings are all hardening, not exploitable bugs. The Python aggregation code is concise and has a unit-test suite. The workflow correctly uses `env:`-passed payloads to avoid command-injection pitfalls.

## Notes / caveats
- The `Claude` label did not pre-exist on the repo (`get_label` returned 404). The four Issues above were created with `labels: ["security", "Claude", "<severity>"]`; GitHub auto-created the missing labels at write time.
- A stale branch `claude/security-fix-csp-headers-A6R8b` exists from a prior resumed review run — it sits at the same SHA as `main` (no commits). Safe to delete; it was created in anticipation of a CSP fix PR that could not be pushed due to the inline-size limit described in finding #1.
