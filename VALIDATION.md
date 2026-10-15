# Compatibility and testing

Version **0.5.1-community.2**, tested on **2026-10-14**, with source-publication checks updated on **2026-10-15**.

## Tested environment

- Linux amd64 with glibc and CPA 8.0.24.
- Go 1.27.2 with the Debian bookworm C toolchain.
- Node.js 24.18.0.
- Python 3.10.12 for unit tests and Python 3.12 Alpine for monitor container tests.
- Playwright 1.55.0 with Chromium.

The monitor Dockerfile supports a `PYTHON_IMAGE` override. Its default Python 3.13 image was not independently runtime-tested. The distributed plugin library was built with Go 1.27.2.

## Results

| Check | Result |
|---|---|
| Go tests | 195 passing test/subtest records |
| Go race detector and vet | Passed |
| Frontend Vitest | 121 tests passed |
| TypeScript and embedded UI build | Passed |
| npm dependency audit | 0 vulnerabilities reported |
| Go vulnerability audit | No vulnerabilities reported with Go 1.27.2 |
| Monitor Python tests | 37 passed, no skips |
| CPA plugin integration | 14 checks passed |
| Monitor Docker runtime | 8 checks passed; UID 10001 and read-only root filesystem |
| Browser checks | 7 viewport configurations; no horizontal overflow or page exceptions |
| Source privacy regression tests | 2 passed |
| Gitleaks and source checks | Passed |
| Binary checks | No known private identifiers or credential patterns detected |

Integration tests cover plugin discovery, management authentication, embedded UI, first-cycle adoption, repeated synchronization, replay of post-reset completion events, rejection of cycle rollback and account changes, cycle inheritance for new keys, plugin-to-monitor reads, snapshot filtering, query failure and restart persistence.

Browser checks cover 320×800, 375×812, 390×844, 719×800, 844×390, 1080×900 and 1280×1000. They also cover reduced motion, the refresh target size, key-name escaping, stale quota, reset-card states and failed reads.

Detailed reports:

- [CPA integration](docs/integration-validation.json)
- [Monitor container](docs/monitor-container-validation.json)
- [Browser checks](docs/browser-validation.json)

## Coverage limits

Official usage and reset-credit responses are mocked. Tests do not validate a live upstream account, inference, public HTTPS reverse proxies, live reset-card operations or multiple-account aggregation. arm64 and musl runtime compatibility have not been verified. Operating-system container packages were not fully vulnerability-scanned.

Budget enforcement uses finalized usage without reservations for concurrent requests. Zero budgets mean unlimited; zero-priced models may have no billed cost. See [SECURITY.md](SECURITY.md) and the [monitor guide](monitor/README.md) before deployment.
