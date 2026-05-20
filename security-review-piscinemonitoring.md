# Security Review: PiscineMonitoring

_Last review: 2026-05-20_

## Summary
- Total findings: 10
- Critical: 0 | High: 2 | Medium: 6 | Low: 2
- PRs opened: 1 (consolidated on `claude/youthful-goldberg-TSC54`)
- Issues opened: 4 (findings that need a maintainer decision or a build artifact that this environment cannot produce)

## Findings

### [HIGH] No Subresource Integrity on unpkg React/ReactDOM/Babel scripts
- **File:** `index.html` (lines 437-439)
- **Description:** Three external production scripts (React 18.3.1, ReactDOM 18.3.1, @babel/standalone 7.29.0) are loaded from unpkg.com without `integrity=` attributes. A unpkg / CDN compromise or any cache-poisoning attack on the path lets an attacker substitute malicious code that runs in the page origin with full CSP `'unsafe-inline'`/`'unsafe-eval'` allowances.
- **Remediation:** Compute sha384 hashes for each pinned version (`curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`) and add `integrity="sha384-..." crossorigin="anonymous"` to each `<script>` tag.
- **PR-ready:** no (this environment cannot reach unpkg.com to generate trustworthy hashes; the hash must come from a host that can fetch the file)
- **Action taken:** Issue filed.

### [HIGH] CSP allows `'unsafe-inline'` and `'unsafe-eval'`
- **File:** `index.html` (line 5)
- **Description:** The CSP `script-src` includes `'unsafe-inline'` and `'unsafe-eval'`. Both are required because the page compiles JSX at runtime via Babel standalone; removing them needs a build step.
- **Remediation:** Move to a precompile step (e.g. esbuild/vite producing a static `app.js`); drop Babel standalone; tighten CSP to `script-src 'self'` (and the cdnjs/unpkg origins behind SRI). This is a structural change.
- **PR-ready:** no (architectural refactor)
- **Action taken:** Issue filed.

### [MEDIUM] Unpinned external library versions (no SRI)
- **File:** `index.html` (lines 437-439)
- **Description:** Versions are pinned in URL paths but without cryptographic guarantees; rolls into finding #1.
- **Remediation:** Addressed by adding SRI hashes (finding #1) or by self-hosting the libraries.
- **PR-ready:** no
- **Action taken:** Tracked alongside the SRI Issue.

### [MEDIUM] No coordinate validation / no Open-Meteo request deduplication
- **File:** `index.html` (lines 132-143, 359-360, 414-415)
- **Description:** `fetchMeteo()` accepts arbitrary lat/lon read from `localStorage` and is invoked from multiple call sites and every 5 minutes from a setInterval. There is no validation that the values fall within [-90, 90] / [-180, 180], and no in-flight deduplication, so the API can be hammered.
- **Remediation:** Validate ranges with `Number.isFinite()` and explicit bounds; memoize `fetchMeteo` for 5 minutes keyed on the rounded coordinate pair.
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.

### [MEDIUM] GitHub Actions use mutable version tags rather than pinned SHAs
- **File:** `.github/workflows/update-status.yml`
- **Description:** `actions/checkout@v4`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4` are referenced by major version. A maintainer of any of those actions can push a new tag with malicious code that this workflow would pick up.
- **Remediation:** Pin each `uses:` line to a full commit SHA; Dependabot can keep them up to date.
- **PR-ready:** no (this environment cannot reliably resolve the upstream SHAs for the major actions outside the MCP scope)
- **Action taken:** Issue filed.

### [MEDIUM] Workflow grants write permissions at the top level
- **File:** `.github/workflows/update-status.yml` (lines 11-14)
- **Description:** `contents: write`, `pages: write`, `id-token: write` are declared at the workflow level, applying to every future job/step.
- **Remediation:** Scope the permissions to the `deploy` job only and declare `permissions: {}` at the top level to deny by default.
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.

### [MEDIUM] Untrusted `client_payload` is written to `status.json` and to `history.json` with no schema validation
- **File:** `.github/workflows/update-status.yml` (the two heredoc Python steps)
- **Description:** The first step uses `echo "$PAYLOAD" > status.json` so any caller of the `repository_dispatch` webhook controls the full content of `status.json` (including injecting arbitrary JSON fields). The history-append step accepts whatever types are in the payload. The webhook is gated by a GitHub token but is otherwise treated as trusted input.
- **Remediation:** Replace the `echo` with a Python heredoc that validates each field against a fixed allowlist and type set, writing only normalised values. Same allowlist for history entries.
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.

### [MEDIUM] Service worker caches data files with no max age
- **File:** `sw.js` (`networkFirst` function)
- **Description:** When the network fails, the SW returns the cached body indefinitely. If a user is offline for days and reconnects, the dashboard silently displays stale data. The 503 fallback also returns `{}` rather than the `{entries: []}` shape consumers expect.
- **Remediation:** Stamp every cached response with a `x-cached-at` header on `put`; on read, treat anything older than 24h as missing. Return `{"entries": []}` for both the no-cache and stale-cache fallback.
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.

### [LOW] localStorage coordinates were not validated before being used
- **File:** `index.html` (lines 359-360, 414-415)
- **Description:** A stored-XSS attacker could set `piscine_lat`/`piscine_lon` to arbitrary numeric values and cause unexpected API behaviour.
- **Remediation:** Range-check inside the getter sites, with safe defaults.
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.

### [LOW] No deduplication or throttle on Open-Meteo calls
- **File:** `index.html` (`loadHouseData` / `fetchMeteo`)
- **Description:** Concurrent calls trigger overlapping fetches; the 5-minute setInterval refresh combined with manual reload can multiply the request count.
- **Remediation:** Memoize Promise for 5 minutes (same fix as MEDIUM #4).
- **PR-ready:** yes
- **Action taken:** Fixed in consolidated PR on `claude/youthful-goldberg-TSC54`.
