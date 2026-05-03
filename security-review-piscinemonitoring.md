# Security Review: piscinemonitoring

## Summary
- Total findings: 12 (all duplicates of existing Open Issues — no net-new findings)
- Critical: 0 | High: 4 | Medium: 5 | Low: 3
- PRs opened: 0 (every PR-ready remediation already has an open PR or parallel branch)
- Issues opened: 1 (meta-tracking)
- Date: 2026-05-03

This is the 5th+ automated security review on this repo. The code on `main` at `5464c8b`
is unchanged in every previously-flagged area. All findings below restate Open Issues
already filed (`#10–#35`). Nine in-flight PRs and parallel branches are already attempting
the PR-ready remediations:

- PR #9, #19, #26, #28, #29, #30, #36 — security hardening branches
- PR #5, #6, #7, #8 — Dependabot version bumps for actions

No new PR was opened in this session: every PR-ready remediation either (a) has an existing
open PR/parallel branch (CSP hardening, SW origin allowlist, status.json validation,
manifest scope, action SHA bumps) or (b) requires offline secret coordination
(HMAC), a build pipeline (Vite/esbuild for SRI + drop `unsafe-eval`), or a network
call (computing SRI hashes from unpkg.com) that the review sandbox cannot perform.
Opening another PR would duplicate review effort for the maintainer.

## Findings

### [HIGH] CSP allows `'unsafe-eval'` and `'unsafe-inline'` in script-src
- **File:** `index.html` (line 5)
- **Description:** `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com` neutralizes CSP as an XSS mitigation. `'unsafe-eval'` is required only because `@babel/standalone` transpiles JSX at runtime. `'unsafe-inline'` is required because the entire app is in inline `<script>` blocks.
- **Remediation:** Move JSX transpilation to a build step (Vite / esbuild). Bundle React + pre-compiled JSX into one same-origin file. Then drop `'unsafe-eval'` from CSP and use script nonces or hashes for inline blocks.
- **PR-ready:** no — requires introducing a build pipeline.
- **Action taken:** Duplicate of Issue #10 / #21 / #32 (all OPEN). No new PR.

### [HIGH] Missing Subresource Integrity on CDN scripts
- **File:** `index.html` (lines 437–439)
- **Description:** Three `unpkg.com` scripts (react, react-dom, @babel/standalone) loaded without `integrity=` attributes. Combined with `'unsafe-eval'` in CSP, a CDN/edge compromise yields full RCE in the page origin.
- **Remediation:** Compute SHA-384 hashes locally with `curl … | openssl dgst -sha384 -binary | openssl base64 -A` and pin them. Better: self-host the bundles (drops the supply-chain dep entirely).
- **PR-ready:** no — review sandbox cannot reach unpkg.com to compute verified hashes; shipping unverified hashes would hard-break the site.
- **Action taken:** Duplicate of Issue #11 / #20 / #31 (all OPEN). No new PR.

### [HIGH] Runtime JSX compilation via `@babel/standalone`
- **File:** `index.html` (line 439, `<script src="…/babel.min.js">` + `<script type="text/babel">` at line 441)
- **Description:** A ~3 MB Babel bundle is downloaded from unpkg.com on every page load and used to `eval()` JSX at runtime. Forces `'unsafe-eval'` in CSP and adds a heavy supply-chain surface.
- **Remediation:** Add a Vite/esbuild build step. Pre-compile JSX, ship plain JS, drop `@babel/standalone` and `'unsafe-eval'`.
- **PR-ready:** no — architectural change.
- **Action taken:** Duplicate of Issue #13 (OPEN). No new PR.

### [HIGH] update-status workflow writes unverified payload to `main` (no HMAC)
- **File:** `.github/workflows/update-status.yml` (lines 24–32, 33–60)
- **Description:** `repository_dispatch.client_payload` is written to `status.json` and appended to `history.json` with no schema/bounds validation and no HMAC signature. A leaked dispatch token (the Home Assistant device runs on a home LAN) lets an attacker poison the data feed. Combined with future code that renders any string field via `innerHTML`, this becomes a stored-XSS vector served from the same origin.
- **Remediation:** (1) Validate field types/bounds in `aggregate_daily.py` (numeric ranges, ISO-8601 timestamp within ±24h, `reason` ≤128 ASCII chars, strict booleans). Reject bad payloads with `exit 1`. (2) Add an application-layer HMAC: HA signs `payload || timestamp` with a shared secret stored as a GitHub Actions secret, the workflow verifies before writing.
- **PR-ready:** no — needs a shared HMAC secret coordinated with Home Assistant. PR #30 partially addresses (validates/canonicalizes status.json).
- **Action taken:** Duplicate of Issue #15 / #22 (OPEN). No new PR.

### [MEDIUM] Pin GitHub Actions to commit SHAs, not floating tags
- **File:** `.github/workflows/update-status.yml` (lines 22, 73, 75, 78)
- **Description:** Workflow runs with `contents: write`, `pages: write`, `id-token: write` and pulls actions by `@v4`/`@v5`/`@v3`. A tag move or maintainer compromise would silently execute attacker code with full repo write + Pages deploy access.
- **Remediation:** Pin each `uses:` to a 40-char commit SHA with a `# vX.Y.Z` comment. Dependabot is already enabled (`.github/dependabot.yml` present) and can keep SHAs current.
- **PR-ready:** no — resolving each SHA requires a live `git ls-remote` that should be verified by the owner against the official release tags.
- **Action taken:** Duplicate of Issue #2 (OPEN). Dependabot PRs #5–#8 are open for version bumps but do not pin to SHA.

### [MEDIUM] Inline Python in update-status workflow
- **File:** `.github/workflows/update-status.yml` (lines 33–60, the heredoc-quoted Python block that appends to `history.json`)
- **Description:** Multi-line Python embedded in YAML. No tests, no type-checking, no schema validation. Magic literal `2016` for trim length. Silent "reset on corruption" can lose data.
- **Remediation:** Move to `scripts/append_history.py` with argparse + tests. Validate payload schema and reject junk (don't write partial state).
- **PR-ready:** yes (no deps change) — but held to avoid breaking the live publish pipeline without an operator present.
- **Action taken:** Duplicate of Issue #16 (OPEN). No new PR.

### [MEDIUM] Missing Permissions-Policy and other defense-in-depth headers
- **File:** `index.html` (`<head>`)
- **Description:** No `Permissions-Policy` meta or equivalent. Several response headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `Cross-Origin-Opener-Policy`) cannot be set on GitHub Pages.
- **Remediation:** Add `<meta http-equiv="Permissions-Policy" content="geolocation=(), camera=(), microphone=(), payment=(), usb=()">`. For HSTS / X-Content-Type-Options, fronting the site with a Cloudflare/Netlify worker is the only path.
- **PR-ready:** no — parallel branches `claude/fix-permissions-policy-guE6b` and `claude/security-fix-permissions-policy-LotRY` already attempt this.
- **Action taken:** Duplicate of Issue #23 / #33 (OPEN). No new PR.

### [MEDIUM] UI exposes precise lat/lon; public telemetry enables location inference
- **File:** `index.html` (header masthead reads `piscine_lat`/`piscine_lon` from localStorage)
- **Description:** Coordinates displayed full-precision in the UI. Combined with public temperature history committed to `main`, anyone can correlate temperature curves with weather stations to refine pool location.
- **Remediation:** Round displayed coords to 1 decimal place (~11 km). Add a privacy notice in README.
- **PR-ready:** no — UX/content choice for the owner.
- **Action taken:** Duplicate of Issue #17 (OPEN). No new PR.

### [MEDIUM] PWA manifest scope permissive
- **File:** `manifest.json`
- **Description:** `start_url: "/"` and `scope: "/"` are fine on the dedicated CNAME domain, but become a problem if ever colocated with another app on the same origin. `prefer_related_applications` not set.
- **Remediation:** Add `"prefer_related_applications": false`. Tighten scope if ever co-hosted.
- **PR-ready:** no — applied in PR on `claude/blissful-turing-YAmif`.
- **Action taken:** Duplicate of Issue #18 (OPEN). No new PR.

### [LOW] Service worker fetch handler bypasses cache for all cross-origin requests
- **File:** `sw.js` (lines 21–26)
- **Description:** `if (url.hostname !== self.location.hostname) { e.respondWith(fetch(e.request)); return; }` — broader than necessary; only Open-Meteo / unpkg / Google Fonts should pass.
- **Remediation:** Allowlist hostnames matching CSP `connect-src` / `script-src` / `font-src` (api.open-meteo.com, fonts.googleapis.com, fonts.gstatic.com, unpkg.com).
- **PR-ready:** no — parallel branches `claude/fix-sw-origin-allowlist-guE6b` and `claude/security-fix-sw-origin-validation-LotRY` (PR #28, PR #26) already attempt this.
- **Action taken:** Duplicate of Issue #14 / #34 (OPEN). No new PR.

### [LOW] IoT telemetry (history.json) publicly readable
- **File:** `history.json`, `daily_summary.json`, `status.json`
- **Description:** By design public. `history.json` exposes pump-on schedule (weak occupancy signal). `daily_summary.json` is retained indefinitely. Future sensor additions (pH, dosing) would also become public history.
- **Remediation:** Owner decision: redact pump-on minutes and/or move publish target off `main` to `gh-pages`. Add `history.json`/`status.json` to `.gitignore`.
- **PR-ready:** no — design decision.
- **Action taken:** Duplicate of Issue #12 / #35 (OPEN). No new PR.

### [LOW] Inline `<script>` and `<style>` blocks force `'unsafe-inline'` in CSP
- **File:** `index.html`
- **Description:** Single-file architecture forces the CSP to allow `'unsafe-inline'`. Any future XSS sink would be directly exploitable.
- **Remediation:** Extract scripts/styles to external files; use SRI-pinned same-origin assets; replace `'unsafe-inline'` with hashes/nonces.
- **PR-ready:** no — touches the entire file structure.
- **Action taken:** Duplicate of Issue #4 (OPEN). No new PR.

## Errors
None. All inspections completed.
