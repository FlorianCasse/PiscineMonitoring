# Security Review: piscinemonitoring

Static-only PWA (HTML + vanilla JS + Python aggregation script) deployed to GitHub
Pages. There is no server, no auth, no database, no MQTT broker in the repo. Reviewed
files: `index.html`, `sw.js`, `manifest.json`, `.github/workflows/update-status.yml`,
`.github/dependabot.yml`, `scripts/aggregate_daily.py`,
`scripts/backfill_daily_summary.py`, `scripts/test_daily_summary.py`, `status.json`,
`README.md`, `CLAUDE.md`, `TODOS.md`.

## Status: Most findings already tracked by prior reviews — 1 net-new PR opened

This is the 5th+ automated security review on this repo. All previously identified
findings remain present and are tracked by the existing 18+ open issues (notably
#10, #11, #14, #20, #21, #23, etc.). One net-new PR was opened this run that
addresses the SW cross-origin allowlist (MEDIUM); the other findings either map to
existing duplicate issues or already have prior PRs awaiting merge.

## Summary
- Total findings: 6
- Critical: 0 | High: 2 | Medium: 3 | Low: 1
- PRs opened this run: 1
  - PR #28: https://github.com/FlorianCasse/PiscineMonitoring/pull/28
- Issues opened this run: 0 (existing issues already cover all findings)

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
  and drop `unpkg.com` from `script-src`/`connect-src` entirely.
- **PR-ready:** no (requires computing SHA-384 hashes from the live CDN; sandbox cannot reach unpkg.com)
- **Action taken:** Tracked by existing Issue #11 and #20 — no duplicate opened

### [HIGH] CSP permits `'unsafe-inline'` and `'unsafe-eval'`
- **File:** `index.html` (line 5)
- **Description:** The Content-Security-Policy meta tag declares
  `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com`. `'unsafe-eval'`
  is required only because `@babel/standalone` is loaded at runtime to JIT-compile
  the JSX inside `<script type="text/babel">`. `'unsafe-inline'` is needed because of
  the inline `<script>` blocks. Together they neutralise most of CSP's protection.
- **Remediation:** Pre-compile the JSX (`@babel/standalone` is a build-time tool, not
  a runtime dependency). Move inline scripts to separate JS files (or use a CSP
  nonce / hash) so `'unsafe-inline'` and `'unsafe-eval'` can be removed.
- **PR-ready:** no (requires a build pipeline change)
- **Action taken:** Tracked by existing Issue #10 and #21 — no duplicate opened

### [MEDIUM] No `Permissions-Policy`, `Cross-Origin-Opener-Policy`, or `Cross-Origin-Resource-Policy` directives
- **File:** `index.html` (head section, lines 1-20)
- **Description:** The page only declares CSP and `referrer`. There is no
  `Permissions-Policy` to deny dangerous browser features (camera, microphone,
  geolocation, payment, USB, serial, midi, etc.) the app does not use.
- **Remediation:** Add a meta tag denying all sensors/devices the app does not use.
- **PR-ready:** yes
- **Action taken:** Tracked by existing Issue #23 — no duplicate opened. Branch `claude/fix-permissions-policy-guE6b` was created for a future patch but timed out before the fix commit was pushed.

### [MEDIUM] Service worker caches and serves cross-origin responses without origin validation
- **File:** `sw.js` (lines 19-25)
- **Description:** The fetch handler's cross-origin bypass does not validate that the
  third-party host is one of the few endpoints the app actually uses. Any future code
  path requesting `https://attacker.example/...` would be silently proxied by the
  service worker.
- **Remediation:** Restrict the cross-origin bypass to an allowlist of expected
  hosts (`api.open-meteo.com`, `fonts.googleapis.com`, `fonts.gstatic.com`,
  `unpkg.com`); for any other host return 403 / let it fail.
- **PR-ready:** yes
- **Action taken:** PR #28 https://github.com/FlorianCasse/PiscineMonitoring/pull/28 (labels: `Claude`, `MEDIUM`)

### [MEDIUM] GitHub Pages artefact uploads the entire repo, including build/CI files
- **File:** `.github/workflows/update-status.yml` (line ~76, `path: '.'`)
- **Description:** `actions/upload-pages-artifact@v3` is invoked with `path: '.'`,
  which packages the whole working tree into the deployed artefact: `.github/`,
  `scripts/`, `CLAUDE.md`, `TODOS.md`, `README.md`, `test_daily_summary.py`. This
  widens the surface of what a future accidentally-committed secret would expose.
- **Remediation:** Move runtime files into a `dist/` directory and set `path: 'dist'`,
  or pre-stage the artefact directory in a step that copies only the deployable files.
- **PR-ready:** no (requires layout decision and test re-run)
- **Action taken:** Net-new finding — partially related to existing #16 (inline Python in workflow). No duplicate issue opened to follow the consolidation guidance from prior reviews.

### [LOW] No license file and pinned but un-hashed CDN versions
- **File:** `index.html` (lines 437-439), repo root
- **Description:** `react@18.3.1`, `react-dom@18.3.1`, and `@babel/standalone@7.29.0`
  are pinned by version, which is good, but unpkg serves whatever is currently
  published under that tag. Combined with the missing SRI (covered above as HIGH),
  this is also a supply-chain hardening note.
- **Remediation:** Add SRI hashes (covered by the HIGH finding).
- **PR-ready:** no (covered by the HIGH SRI finding)
- **Action taken:** Tracked transitively by existing Issue #11 / #20

## Recommendation

The issue tracker has accumulated **18+ open security issues** plus several meta-issues
(#25, #27). The priority is to **review and merge or close** the existing duplicate
PRs and issues, not to open more. Suggested triage:

1. Merge PR #28 (this run) to close the SW origin-allowlist gap (Issue #14 partial)
2. Close duplicate issues consolidating around: CSP (#10, #21), SRI (#11, #20)
3. Adopt a `SECURITY.md` policy so future automated scans recognize tracked findings
