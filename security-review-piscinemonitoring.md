# Security Review: piscinemonitoring

**Date:** 2026-04-20
**Scope:** full repo (`index.html`, `sw.js`, `manifest.json`, `scripts/`, data JSON files, GitHub Actions)
**Language/stack:** static PWA, runtime JSX via Babel standalone, Python data-collection scripts, GitHub Actions for updates.

## Summary

- Total findings: 9
- CRITICAL: 2 | HIGH: 4 | MEDIUM: 3 | LOW: 0
- PRs opened: 1 (this PR — report + manifest hardening)
- Issues opened: 9 (one per finding; see "Action taken" per finding)

What was checked: CSP, Subresource Integrity on CDN scripts, service-worker cache/origin behavior, secrets/PII in committed data, GitHub Actions workflow integrity, PWA manifest scope, geolocation exposure.

## Findings

### [CRITICAL] Permissive CSP with `unsafe-eval` and `unsafe-inline`
- **File:** `index.html` (line 6, CSP meta tag)
- **Description:** The CSP `script-src` includes `'unsafe-eval'` and `'unsafe-inline'`, and `style-src` includes `'unsafe-inline'`. This allows arbitrary inline script/eval execution and neutralizes the main XSS defense CSP provides. Any HTML-injection sink (e.g., `innerHTML` with API data) becomes exploitable.
- **Remediation:** Remove `'unsafe-eval'` and `'unsafe-inline'` from `script-src`. Pre-compile the JSX to plain JS at build time (see HIGH "Babel runtime compilation" finding) so `unsafe-eval` is no longer required. For styles, migrate inline styles to external stylesheets or use per-tag nonces.
- **PR-ready:** no (blocked on moving away from runtime Babel)
- **Action taken:** Issue

### [CRITICAL] Missing Subresource Integrity on external CDN scripts
- **File:** `index.html` (React, React-DOM, @babel/standalone `<script>` tags from unpkg.com)
- **Description:** Three production dependencies load from `unpkg.com` without `integrity="sha384-..."` / `crossorigin="anonymous"`. CDN compromise or MITM would inject attacker-controlled JS. Babel standalone is particularly dangerous because it is a runtime compiler.
- **Remediation:** Add SRI hashes to each `<script src="https://unpkg.com/...">` tag and `crossorigin="anonymous"`. Generate hashes with `curl -s URL | openssl dgst -sha384 -binary | openssl base64 -A`. Ideally migrate to a pinned local bundle.
- **PR-ready:** no (requires hashing each pinned artifact — recommend doing at build time)
- **Action taken:** Issue

### [HIGH] Data files committed to repo with no privacy boundary
- **File:** `history.json` (320 KB), `daily_summary.json`, `status.json`
- **Description:** Complete pool telemetry is committed to the public repo via the `update-status` workflow. Temperature/pump status is low-sensitivity today, but any future sensor addition (pH, chemical dosing, geolocation refinement) will leak into git history. Combined with the visible latitude/longitude in the UI, the dataset enables location inference.
- **Remediation:** Move telemetry publishing out of `main` (publish to `gh-pages` without re-committing source, or to object storage). Add `history.json`, `daily_summary.json`, `status.json` to `.gitignore` and stop committing them on `main`.
- **PR-ready:** no (architectural change; also requires scrubbing existing git history)
- **Action taken:** Issue

### [HIGH] Runtime JSX compilation via `@babel/standalone`
- **File:** `index.html` (`<script type="text/babel">` + `@babel/standalone`)
- **Description:** The app ships a full JS compiler to every visitor and compiles JSX at load time. This (a) mandates `unsafe-eval` in CSP, (b) is a large attack surface if Babel itself is ever poisoned, and (c) adds 100–500 ms of startup time. Any XSS sink becomes catastrophic because inline/eval are already allowed by CSP.
- **Remediation:** Pre-compile JSX at build time (`@babel/cli`, esbuild, or Vite) and ship plain JS. Then tighten CSP (remove `unsafe-eval`/`unsafe-inline`).
- **PR-ready:** no (requires introducing a build step)
- **Action taken:** Issue

### [HIGH] Service worker does not validate origin on external fetches
- **File:** `sw.js` (lines ~24–26, network fetch + cache)
- **Description:** The service worker caches external API responses (e.g., Open-Meteo) without checking the response origin or content-type. An attacker able to MITM a user on a hostile network could poison the SW cache with a malicious payload that then persists offline. Cache keys also don't include origin, a subtle cross-origin poisoning vector if more origins are added.
- **Remediation:** In the SW `fetch` handler, validate `new URL(response.url).origin` against an allowlist before `cache.put`. Also skip caching on non-2xx responses and on `fetch` requests that redirect across origins.
- **PR-ready:** yes (localized change in `sw.js`) — but held as Issue in this pass because SW changes require carefully re-checking the full offline flow. Prefer human testing before shipping.
- **Action taken:** Issue

### [HIGH] GitHub Actions writes externally-supplied data back to the repository
- **File:** `.github/workflows/update-status.yml` (git commit + push step)
- **Description:** The workflow accepts a `workflow_dispatch` payload from Home Assistant, writes it into `history.json`/`daily_summary.json`, and pushes back to `main` automatically. There is no schema/bounds validation and no HMAC check on the inbound payload. A leaked dispatch token or tampered Home Assistant host would land attacker-chosen content directly on `main`.
- **Remediation:** Validate payload schema (numeric ranges on temperatures, enum for states) before writing. Sign the dispatch payload with an HMAC secret stored in GitHub Actions and verify in the workflow before accepting data. Consider publishing to `gh-pages` instead of `main` to reduce blast radius.
- **PR-ready:** no (needs HMAC shared secret coordinated with Home Assistant)
- **Action taken:** Issue

### [MEDIUM] Inline Python logic in GitHub Actions workflow
- **File:** `.github/workflows/update-status.yml` (inline `python -c`/here-doc that appends to `history.json`)
- **Description:** Multi-line Python inside YAML is hard to review/test, lacks type-checking, and has no test coverage. It also grows unbounded (`history.json` currently 320 KB and only trimmed to 2016 entries — ~7 days at 5-min cadence).
- **Remediation:** Extract logic to `scripts/append_history.py` with argparse + tests. Add bounds/schema validation (reject out-of-range values, cap array length, `try/except` around JSON parse).
- **PR-ready:** yes (straightforward refactor, no dep changes) — held as Issue here to avoid breaking the live publish pipeline without an operator present.
- **Action taken:** Issue

### [MEDIUM] PWA manifest `start_url` and `scope` are permissive
- **File:** `manifest.json`
- **Description:** `start_url: "/"` and `scope: "/"` are fine for a dedicated domain but risk scope collisions on a multi-app host. Manifest also lacked `prefer_related_applications: false`, leaving that behavior UA-defined.
- **Remediation:** Set `prefer_related_applications: false`. Consider `scope: "/PiscineMonitoring/"` if ever colocated with other apps on the same origin.
- **PR-ready:** yes — applied in this PR (adds `prefer_related_applications: false`).
- **Action taken:** PR (this branch)

### [MEDIUM] UI exposes exact latitude/longitude; historical trend enables geolocation inference
- **File:** `index.html` (header masthead shows `piscine_lat`/`piscine_lon`)
- **Description:** The app displays precise latitude/longitude in the header and stores them in `localStorage`. Coordinates are per-user (not committed), but combined with the publicly committed temperature history, anyone who knows the UI URL can correlate temperature trends with public weather data to refine pool location.
- **Remediation:** Round displayed coordinates to 1 decimal place (≈11 km precision); add a short privacy notice explaining that coordinates are stored locally only; document that telemetry in the repo is public.
- **PR-ready:** no (UX/content change — should go through the owner)
- **Action taken:** Issue

## Labels Note

`CRITICAL` and `HIGH` labels do not exist on this repository and the MCP toolchain used to run this review cannot create labels. Issues opened from this review use the subset of required labels that exist in the repo (`Claude`, `security`, plus `MEDIUM`/`LOW` where applicable). The severity of each issue is also stated in the issue title. Recommend creating `CRITICAL` and `HIGH` labels manually so future reviews can label fully.
