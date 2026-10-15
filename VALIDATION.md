# Validation — 2026-10-14

Public edition: **0.5.1-community.2**. Validation used an isolated Linux amd64 Docker host. Existing services and production state were not changed. No production accounts, client keys or usage were copied into the test environment.

| Check | Result |
|---|---|
| Go tests | 195 passing test/subtest records |
| Go race detector | All packages passed |
| Go vet | Passed |
| Frontend Vitest | 121 tests passed |
| TypeScript / single-file hosted UI | Built successfully |
| Locked npm dependencies | `npm audit --audit-level=low`: 0 vulnerabilities |
| Go vulnerability audit | `govulncheck ./...`: no vulnerabilities found with Go 1.27.2 |
| Monitor Python tests | 37 passed; no skips |
| Real CPA plugin integration | 14 checks passed with CPA 8.0.24 |
| Monitor Docker runtime | 8 checks passed; user 10001, read-only root filesystem |
| Browser | 7 viewport configurations, no horizontal overflow or page exceptions |
| Credential scanner | Gitleaks: no leaks found |
| Public-source allowlist | Passed, including built HTML and PNG metadata |
| Binary privacy review | No known private identifiers or credential patterns; Go 1.27.2 marker confirmed |

Tools: Go 1.27.2 / Debian bookworm C toolchain, Node 24.18.0, Python 3.10.12 for unit tests and Python 3.12 Alpine for the monitor container, Playwright 1.55.0 with Chromium. The runtime-image override is supported through Docker's `PYTHON_IMAGE` build argument; the default Python 3.13 image was not independently runtime-tested.

The first Go audit found GO-2026-6613 in Go 1.27.1. The binary was rebuilt with fixed Go 1.27.2 and all Go tests, race checks, vet and the vulnerability audit were repeated. The distributed binary uses the corrected toolchain.

CPA integration confirms: dynamic-library discovery; management authentication; embedded UI; preserving spend on first adoption and repeated sync; replaying post-reset completion events; rejecting rollback/account changes; inheriting the cycle for new keys; real plugin-to-monitor reads; official-response processing with mocked data; snapshot field minimization; preservation on query failure; and restart persistence. Filename discovery requires the installation name `cpa-key-policy-v0.5.1-community.2.so`.

Browser checks cover 320×800, 375×812, 390×844, 719×800, 844×390, 1080×900 and 1280×1000. Reduced-motion settings disable blinking, the refresh target stays at least 44 pixels high, and escaped key names cannot introduce HTML elements or attributes. Zero/unknown/stale reset-card counts, stale official quota and failed network reads preserve the expected view. Synthetic desktop/mobile monitor and plugin-management screenshots are included. Full browser and integration records are in `docs/`.

## Scope limits

Official usage and reset-credit responses were mocked. No real upstream account or inference was used. CPA may perform its own unauthenticated catalog/version refreshes; those are not model inference or official account validation. Public DNS, Lucky, real HTTPS proxy login, live reset-card behavior, multiple accounts, arm64 and musl were not verified in this environment. All screenshots contain synthetic data.

Dollar budget enforcement uses finalized usage and does not reserve concurrent in-flight requests. Zero limits mean unlimited; zero-priced models can have no billed cost. The monitor is a separate service; it does not turn the plugin into a standalone collector. Operating-system container packages were not fully vulnerability-scanned. See SECURITY.md and monitor/README.md before deploying.

## Publication follow-up — 2026-10-15

Runtime plugin behavior and the compiled library are unchanged. Go test setup now uses a disposable working directory so default test ledgers never land in the checkout. Two privacy-regression tests cover ledger filenames, runtime directories and allowed synthetic examples. The publication checklist was refreshed, and source contents, Git staging and author metadata were checked separately before upload.
