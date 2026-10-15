# Security

## Management access

The plugin's management API requires CPA management authentication. Keep `/v0/management/` and the plugin management page restricted to administrators. An unauthenticated custom bridge to these endpoints would grant administrative access.

Use HTTPS for Internet access, or an encrypted private network. Send keys in the `Authorization` header. Query-string keys can appear in proxy and server logs.

The plugin management page holds the management key in memory. Automatic key reuse requires a readable same-origin parent and a same-origin API base. When entering a different CPA address manually, verify the destination before signing in. CPA's own panel may store credentials separately; its storage behavior is outside this plugin.

Management HTML prevents cross-origin framing, object embedding and base-tag rewriting. Responses include no-store, no-referrer and nosniff headers. Preserve these headers at the reverse proxy. They do not protect against a compromised page on the same origin or a malicious browser extension.

## Key storage

Generated downstream keys use 32 random bytes. The plugin persists SHA-256 hashes and partial previews; complete keys are returned only on creation or rotation. Prefer generated keys over short user-chosen passwords. Hashes and full secrets are omitted from list and detail responses, and short or malformed previews are masked.

State files use owner-only permissions and atomic replacement. Back them up securely: they contain policies, user identifiers and usage records. Further details are in [PRIVACY.md](PRIVACY.md).

## Policy limits

- Do not register plugin-issued keys in CPA's native `api-keys`. Unknown keys can pass through to native authentication and bypass plugin policy if registered there.
- Budget checks use completed consumption. Concurrent requests have no reserved budget and can exceed a cap.
- A zero budget means unlimited. Zero-priced models may produce no budget charge.
- Allowing `/v1/models` returns CPA's global model list. The list is not filtered per Key.
- Official-cycle management endpoints rely on a trusted caller to confirm the cycle. The monitor requires two observations before adopting a new cycle, but upstream format changes may still need review.
- Credentials marked disabled, banned, revoked or unavailable remain excluded from scheduling. Historical error status alone does not exclude an otherwise eligible CPA candidate.

## Monitor access

All business routes require viewer authentication, including requests from private networks. Anonymous `/health` exposes only a liveness result.

The monitor loads the CPA management secret from a local file and does not return it to browsers. Viewers can see Key names, budgets and usage. Share viewer credentials only with people who should see those statistics.

Viewer passwords use salted PBKDF2 hashes. Signed cookies use Secure, HttpOnly, SameSite=Strict and a host-only prefix. Changing the password or session secret revokes existing cookies. Terminate HTTPS at a trusted proxy, configure the exact `ALLOWED_HOSTS`, and preserve authentication and cookie headers. The supplied Compose file exposes a loopback port and runs the service as a non-root user.

The monitor has global failed-password throttling, but no MFA, per-viewer permissions or per-client throttling. Restrict access further at the proxy or private network when those controls are required. Browser routes are read-only; enabling official-cycle synchronization separately authorizes the collector to update plugin cycle state.

Keep the Python runtime and container image updated. Operating-system packages are not covered by the application dependency checks.

## Reporting vulnerabilities

Use private GitHub vulnerability reporting when it is available for this repository. Omit API keys, account files, private endpoints and unredacted logs from public issues. Describe the affected version, expected behavior and reproduction steps using test data.
