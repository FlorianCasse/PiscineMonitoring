# Security Review: piscinemonitoring

**Date:** 2026-04-23 (re-run — session `KDaey`)
**Branch:** `claude/blissful-turing-KDaey`
**Reviewer:** Claude (automated security review)
**Language/Framework:** Static HTML + React 18 (runtime Babel/JSX) + Service Worker; backend is GitHub Actions (Python stdlib scripts)
**Dependency Manager:** none for runtime (CDN-hosted); `scripts/` is stdlib-only

## Summary
- Total findings: 9 (2 CRITICAL, 4 HIGH, 2 MEDIUM, 1 LOW — all previously identified)
- Critical: 2 | High: 4 | Medium: 2 | Low: 1
- PRs opened this run: 0
- Issues opened this run: 1 meta-tracking issue; all individual findings already have dedicated open Issues

## Context
The repo already has **16 open `Claude`-labeled security Issues** (#2, #4, #10, #11, #12, #13, #14, #15, #16, #17, #18, #20, #21, #22, #23, #24) covering every finding below. Several PRs exist on `claude/*` branches awaiting merge. This run references existing items under **Action taken** rather than opening duplicates.

## Areas Reviewed
- Source: `index.html` (React app with runtime Babel; CSP meta tag; API calls to Open-Meteo)
- Source: `sw.js` (service worker caching of data JSONs + external APIs)
- Scripts: `scripts/aggregate_daily.py`, `scripts/backfill_daily_summary.py` (GitHub Actions ingest)
- CI/CD: `.github/workflows/update-status.yml` (external `repository_dispatch` → commits data files to `main`)
- Data: `history.json` (~320 KB), `daily_summary.json`, `status.json` — publicly committed telemetry
- Config: `manifest.json`, `CNAME`, `.gitignore`

## Findings

### [CRITICAL] CSP allows `'unsafe-eval'` and `'unsafe-inline'`
- **File:** `index.html` — meta CSP near top of `<head>`
- **Description:** CSP neutered by allowing `unsafe-eval` (for runtime Babel JSX compilation) and `unsafe-inline`. Any DOM-injection sink becomes direct script execution.
- **Remediation:** Precompile JSX at build time (Vite/esbuild), drop `@babel/standalone`, remove both CSP escape hatches.
- **PR-ready:** no (requires build-system migration)
- **Action taken:** Existing Issue **#10** (and related **#21**). No duplicate opened.

### [CRITICAL] Missing Subresource Integrity on CDN scripts (unpkg.com)
- **File:** `index.html` — React, React-DOM, and `@babel/standalone` loaded from `unpkg.com` with `crossorigin="anonymous"` but no `integrity=`.
- **Remediation:** Compute SHA-384 for each pinned URL; add `integrity=`; long-term, bundle locally.
- **Action taken:** Existing Issues **#11, #20**. No duplicate opened.

### [HIGH] Runtime JSX compilation via `@babel/standalone`
- **File:** `index.html` (`<script type="text/babel">`)
- **Description:** Requires `'unsafe-eval'` in CSP; ~2 MB download; any compromise to the Babel CDN executes with site origin privileges.
- **Action taken:** Existing Issue **#13** (and coupled with #10/#20). No duplicate opened.

### [HIGH] Telemetry files committed to `main` — no privacy boundary for future sensors
- **Files:** `history.json`, `daily_summary.json`, `status.json`
- **Description:** Every tick commits telemetry to `main`. Current data is low-sensitivity but location is inferable from temperature curves vs. public weather; future sensors (pH, chemistry) would inherit the same public-git pattern.
- **Action taken:** Existing Issue **#12**. No duplicate opened.

### [HIGH] Service worker does not validate origin/status on external fetches
- **File:** `sw.js` (external-hostname branch)
- **Description:** External responses are passed through `fetch` — current code does *not* cache them (good — `cacheFirst` is scoped to same-origin), but the fallback `Response('Offline', 503)` and `return new Response('{}', ...)` for `networkFirst` are fine. The **stored-XSS via poisoned JSON** concern from Issue #14 applies to *same-origin* data files only; a MITM on `main` commits (unlikely on github.io over HTTPS) would need the data-file channel, not the SW fetch.
- **Action taken:** Existing Issue **#14**. No duplicate opened.

### [HIGH] `update-status` workflow writes unverified external payload to `main`
- **File:** `.github/workflows/update-status.yml`
- **Description:** `repository_dispatch` payload from Home Assistant is persisted verbatim to `history.json` / `status.json` with no schema/bounds/HMAC check. A leaked dispatch token → attacker-controlled JSON on `main` → fed into the PWA.
- **Action taken:** Existing Issues **#15, #22**. No duplicate opened.

### [HIGH] Missing SRI on unpkg.com script tags (duplicate of #11)
- **Action taken:** Already tracked as **#20** (newer) and **#11** (earlier). No duplicate opened.

### [MEDIUM] UI exposes precise lat/lon; committed telemetry enables location inference
- **File:** `index.html` (header masthead)
- **Action taken:** Existing Issue **#17**. No duplicate opened.

### [MEDIUM] Inline Python in `update-status.yml` should be extracted
- **File:** `.github/workflows/update-status.yml`
- **Action taken:** Existing Issue **#16**. No duplicate opened.

### [MEDIUM] GitHub Actions pinned to floating major tags (`@v4`, `@v3`, `@v5`)
- **File:** `.github/workflows/update-status.yml`
- **Action taken:** Existing Issue **#2**. No duplicate opened.

### [MEDIUM] PWA manifest `scope: "/"` is permissive (partially addressed)
- **File:** `manifest.json`
- **Action taken:** Existing Issue **#18** — PR on `claude/blissful-turing-YAmif` adds `prefer_related_applications: false`. No duplicate opened.

### [LOW] Missing `Permissions-Policy`, Referrer-Policy fallback, HSTS confirmation
- **File:** `index.html` + GitHub Pages config
- **Action taken:** Existing Issue **#23**. No duplicate opened.

### [LOW] Dependabot only watches `github-actions`; `scripts/` pip deps unmanaged
- **File:** `.github/dependabot.yml`
- **Action taken:** Existing Issue **#24**. No duplicate opened.

### [LOW] Inline `<script>` / `<style>` force `'unsafe-inline'` in CSP
- **File:** `index.html`
- **Action taken:** Existing Issue **#4**. No duplicate opened.

## Findings-per-area check
- Hardcoded secrets: **none** — no tokens in committed files; Home Assistant PAT lives in repo Actions secrets (correct).
- Dependency vulns: runtime deps via unpkg CDN with no pinning beyond version tag and no SRI (#11/#20); scripts are stdlib-only (#24 forward-looking).
- Insecure config: CSP allows `unsafe-eval`/`unsafe-inline` (#10/#21); GitHub Actions on floating tags (#2).
- Injection: DOM XSS via future-unsafe `innerHTML` is mitigated by React rendering, but the CSP gap means *any* sink becomes exploitable (#10). Stored-XSS vector via workflow-committed fields (`reason`, `updated_at`) is a latent risk (#22).
- Service-worker caching: same-origin only; external bypass is intentional (#14 still worth improving).
- File/dir perms: n/a (static hosting).
- Privacy: lat/lon in UI + public telemetry files enable location inference (#12/#17).

## Summary of Existing Open Security Items (`Claude` label)
- **Open Issues:** #2, #4, #10, #11, #12, #13, #14, #15, #16, #17, #18, #20, #21, #22, #23, #24
- **Open branches awaiting review:** `claude/blissful-turing-A6R8b`, `claude/blissful-turing-YAmif`, `claude/blissful-turing-oWKG0`, `claude/security-fix-csp-headers-A6R8b`

## Recommendation
1. **Migrate to a pre-built bundle** (Vite/esbuild) — this single change closes #10, #13, #20, #21, #11 at once.
2. **Add HMAC verification on `repository_dispatch` payload** — closes #15 and hardens #22.
3. **Stop committing telemetry to `main`** — publish to `gh-pages` only; closes #12 and bounds the "future sensors" privacy question.
4. **Pin Actions to SHAs** — #2 is a one-PR win once SHAs are looked up.

Generated by Claude on 2026-04-23.
