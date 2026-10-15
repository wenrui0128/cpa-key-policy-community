# Changelog

## Unreleased

- Reorganize installation and usage guides in English and Chinese, and clarify monitor setup and upgrade instructions.

## 0.5.1-community.2

- Add CPA Limits, an optional quota monitor with a pixel-terminal interface, demo mode, reset-card expiry and configurable quota estimates and display timezone.
- Add persistent HTTPS login with signed, password-bound cookies. Require authentication on all business routes.
- Add opt-in official-cycle synchronization for all plugin keys. Preserve confirmed values on query failure, expired data, cycle rollback or account mismatch.
- Fix scheduling for eligible CPA candidates with historical errors while continuing to exclude disabled, banned, revoked and unavailable credentials.
- Fix quote escaping in monitor key labels and omit account references, credential previews and cycle history from snapshots.
- Build with Go 1.27.2 and update frontend dependencies.
- Add isolated CPA integration tests, container checks and desktop/mobile browser coverage.

## 0.5.1-community.1

Based on [origin652/cpa-plugin-key-policy](https://github.com/origin652/cpa-plugin-key-policy) v0.5.1 under the MIT license.

- Show weekly usage by default on key cards and usage details.
- Add remaining-budget bars and inline weekly-budget editing.
- Place navigation beside the plugin title.
- Add management endpoints for adopting confirmed official cycles. Preserve usage on first adoption; archive earlier usage and replay post-boundary events on later cycles.
- Mask short user-supplied keys and reduce preview exposure for medium-length keys.
- Restrict automatic saved-key reuse to a readable same-origin parent and same-origin API base.
- Reject API URLs with embedded credentials, query parameters or fragments. Clear in-memory sessions after failed login.
- Disable redirects, referrers and cookies for credential verification and public-pricing requests.
- Add framing, caching, referrer and MIME-sniffing protections to management HTML.
- Update the frontend lockfile and replace the single-file build dependency with a local build hook.
- Add CI validation with read-only repository permissions and pinned actions. Generate binary artifacts on manual dispatch.
