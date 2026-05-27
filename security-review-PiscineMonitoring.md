# Security Review: PiscineMonitoring

**Date:** 2026-05-27
**Reviewer:** Claude (automated security review)
**Repository:** floriancasse/PiscineMonitoring
**Branch reviewed:** main

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 5 |
| LOW | 5 |
| **Total** | **13** |

---

## HIGH Findings

### H-1: CSP allows 'unsafe-eval' enabling code execution attacks
- **File:** `index.html` (line 5)
- **Status:** Issue created (#57)
- **Description:** The Content-Security-Policy includes `'unsafe-eval'` in the `script-src` directive. This is required by @babel/standalone which uses `eval()` to transpile JSX at runtime. However, `'unsafe-eval'` defeats a key CSP protection against XSS.
- **Remediation:** Pre-compile JSX at build time (e.g., using esbuild) and serve plain JS. This removes the need for @babel/standalone entirely, eliminating both `'unsafe-eval'` and the 170KB+ Babel download.

### H-2: CSP allows 'unsafe-inline' scripts
- **File:** `index.html` (line 5)
- **Status:** Issue created (#58)
- **Description:** The Content-Security-Policy includes `'unsafe-inline'` in the `script-src` directive. This weakens XSS protections by allowing inline script blocks. Currently the app uses inline script blocks for its data pipeline.
- **Remediation:** Move inline JavaScript to separate `.js` files and use CSP nonces or hashes instead of `'unsafe-inline'`.

### H-3: CSP allows 'unsafe-inline' styles
- **File:** `index.html` (line 5)
- **Status:** Issue created (#57, related)
- **Description:** The `style-src` directive includes `'unsafe-inline'`, which allows injection of arbitrary CSS. While less severe than script injection, malicious CSS can exfiltrate data via background-image URLs or obscure UI elements for clickjacking.
- **Remediation:** Move inline styles to external stylesheets. Use CSP nonces or hashes for any remaining inline styles.

---

## MEDIUM Findings

### M-1: Babel standalone transpiles JSX in the browser at runtime
- **File:** `index.html` (line 439)
- **Status:** Issue created (#59)
- **Description:** @babel/standalone (7.29.0, 170KB+) is loaded in production to transpile JSX at runtime. This requires `'unsafe-eval'` in CSP, increases page load time, and expands the attack surface.
- **Remediation:** Pre-compile JSX during CI or as a local build step using esbuild. Remove the Babel standalone script and the `'unsafe-eval'` CSP directive.

### M-2: No .gitignore coverage for secrets and environment files
- **File:** `.gitignore`
- **Status:** Fixed in PR #61
- **Description:** The `.gitignore` file did not include patterns for common secret files (`.env`, `*.key`, `*.pem`, `credentials.json`, etc.). This increases the risk of accidentally committing secrets to version control.
- **Remediation:** Added comprehensive secret file patterns to `.gitignore`.

### M-3: No input-size guard on batch payloads
- **File:** `scripts/apply_payload.py`
- **Status:** Fixed in PR #61
- **Description:** The `apply_payload.py` script accepted payloads of arbitrary size with no upper bound on the number of entries. A malicious or malformed dispatch could send thousands of entries, causing excessive I/O and potential resource exhaustion.
- **Remediation:** Added batch size validation (max 100 entries) with clear error messaging.

### M-4: sw_version derived by truncating timestamp (predictable, leaks timing)
- **File:** `scripts/apply_payload.py` (line 119)
- **Status:** Fixed in PR #61
- **Description:** The service worker cache version was derived by stripping non-alphanumeric characters from the timestamp and truncating to 16 characters. This approach is predictable and leaks timing information about when updates occur.
- **Remediation:** Replaced with `hashlib.sha256` hash of the timestamp, producing a deterministic but non-reversible version string.

### M-5: CDN scripts loaded without Subresource Integrity (SRI) hashes
- **File:** `index.html` (lines 437-439)
- **Status:** Not yet addressed
- **Description:** React, ReactDOM, and Babel standalone are loaded from unpkg.com CDN with `crossorigin="anonymous"` but without `integrity` attributes. If the CDN is compromised, malicious scripts could be served.
- **Remediation:** Add `integrity` attributes with SHA-384 hashes for each CDN script. Pin to exact versions (already done) and verify hashes match published builds.

---

## LOW Findings

### L-1: React and ReactDOM versions are slightly outdated
- **File:** `index.html` (line 437)
- **Status:** Issue created (#60)
- **Description:** React 18.3.1 is used. While no critical CVEs are known, React 19 is available and 18.3.x is in maintenance mode.
- **Remediation:** Periodically check for security advisories. Consider updating to latest stable versions.

### L-2: File I/O missing explicit encoding
- **File:** `scripts/apply_payload.py` (multiple lines)
- **Status:** Fixed in PR #61
- **Description:** All `open()` calls lacked explicit `encoding` parameter. On some platforms the default encoding may not be UTF-8, leading to potential data corruption or encoding-related injection vectors.
- **Remediation:** Added `encoding='utf-8'` to all `open()` calls.

### L-3: No rate limiting on repository_dispatch webhook
- **File:** `.github/workflows/update-status.yml`
- **Status:** Not yet addressed
- **Description:** The GitHub Actions workflow triggered by `repository_dispatch` has no rate limiting or deduplication. An attacker with a valid token could flood the workflow with dispatches.
- **Remediation:** Add workflow-level concurrency controls and/or timestamp-based deduplication in the payload processing script.

### L-4: Error messages may leak internal paths
- **File:** `scripts/apply_payload.py`
- **Status:** Not yet addressed
- **Description:** Error messages and print statements include file paths and entry counts that could assist an attacker in understanding the system structure.
- **Remediation:** Ensure error output in production workflows is not publicly visible. Consider structured logging with appropriate log levels.

### L-5: No Content-Security-Policy report-uri or report-to directive
- **File:** `index.html` (line 5)
- **Status:** Not yet addressed
- **Description:** The CSP header does not include `report-uri` or `report-to` directives. CSP violations are silently dropped, providing no visibility into potential attacks or misconfigurations.
- **Remediation:** Add `report-to` directive pointing to a CSP violation reporting endpoint to monitor for policy violations.

---

## Actions Taken

| Finding | Action | Reference |
|---------|--------|-----------|
| H-1: CSP unsafe-eval | Issue created | [#57](https://github.com/FlorianCasse/PiscineMonitoring/issues/57) |
| H-2: CSP unsafe-inline scripts | Issue created | [#58](https://github.com/FlorianCasse/PiscineMonitoring/issues/58) |
| H-3: CSP unsafe-inline styles | Tracked with H-1 | [#57](https://github.com/FlorianCasse/PiscineMonitoring/issues/57) |
| M-1: Babel standalone | Issue created | [#59](https://github.com/FlorianCasse/PiscineMonitoring/issues/59) |
| M-2: .gitignore gaps | Fixed in PR | [#61](https://github.com/FlorianCasse/PiscineMonitoring/pull/61) |
| M-3: No batch size limit | Fixed in PR | [#61](https://github.com/FlorianCasse/PiscineMonitoring/pull/61) |
| M-4: Predictable sw_version | Fixed in PR | [#61](https://github.com/FlorianCasse/PiscineMonitoring/pull/61) |
| M-5: No SRI hashes | Not yet addressed | - |
| L-1: Outdated React | Issue created | [#60](https://github.com/FlorianCasse/PiscineMonitoring/issues/60) |
| L-2: Missing encoding | Fixed in PR | [#61](https://github.com/FlorianCasse/PiscineMonitoring/pull/61) |
| L-3: No rate limiting | Not yet addressed | - |
| L-4: Error message leakage | Not yet addressed | - |
| L-5: No CSP reporting | Not yet addressed | - |
