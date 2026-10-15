# Security and privacy

This is a privileged CPA management plugin, not a public client dashboard. Every management API must remain behind CPA management authentication. The static HTML resource is public code; it contains no embedded management secret, production endpoint or account data. The plugin relies on CPA to authenticate its management hooks and must not be mounted behind an unauthenticated custom bridge.

## Credentials

- Generated downstream keys use 32 random bytes. Only SHA-256 hashes and partial previews are persisted. Prefer generated keys; hashing a short user-chosen password does not make it a strong API key.
- List/detail API responses omit key hashes and complete secrets. Short secrets, malformed imported previews and older plaintext previews are masked. Complete generated keys are returned only when created or rotated.
- The plugin session holds the management key in memory. It does not write that key to localStorage. The main CPA panel may separately remember a management key with reversible obfuscation; this is not encryption and is outside this plugin's storage policy.
- Automatic reuse requires a readable same-origin parent and same-origin API base. Explicit login still allows a user-selected CPA origin, so verify the destination before entering a key.
- Use HTTPS for direct Internet management, or an encrypted private tunnel for HTTP. Do not put API keys in URLs: compatibility query-key support remains available, and upstream/proxy URL logs can expose those keys. Prefer the Authorization header.
- State files use owner-only permissions and atomic replacement, but contain usage and account identifiers. Never publish a runtime state file, even if it contains hashes rather than plaintext.

## Network behavior

The Go plugin has no telemetry, HTTP listener or independent outbound HTTP client. Host CPA handles upstream calls. The frontend sends privileged requests only to its selected CPA base.

The existing optional price-reference feature reads a public LiteLLM JSON file on raw.githubusercontent.com when opening the key editor. It uses plain fetch rather than the authenticated API client, sends no account, key, model selection or prompt, omits cookies and referrers, and rejects redirects. The external service can still see the browser's connection IP. Blocking this public host disables price suggestions and does not prevent manual pricing. No third-party executable script or font is loaded.

Management HTML disallows cross-origin framing, object embedding and base-tag URL rewriting, and sends no-store, no-referrer and nosniff response headers. A reverse proxy must preserve these headers. They do not protect against a compromised same-origin CPA page or browser extension.

## Known operating limits

- Official-cycle endpoints accept a cycle confirmed by a trusted management caller; the optional monitor queries official quota and requires two observations for a new cycle, but upstream interface changes can still require manual review. Use a stable, non-sensitive account label and a synchronizer that confirms resets before submitting them.
- Budget checks use finalized consumption. Concurrent/in-flight calls can exceed a limit because reservation is not implemented. Zero budget means unlimited. Models with zero pricing can have zero billed cost.
- A historical error flag does not exclude a candidate already filtered by CPA. Disabled, banned, revoked and unavailable candidates remain excluded.
- Unknown keys can fall through to CPA's native API-key provider. Never register plugin-issued keys again as native CPA API keys, or clients may bypass policy.
- Allowing /v1/models exposes CPA's global model list, not a per-key filtered list.
- Runtime key edits, logs, backups and screenshots may contain private data. They are excluded from the source package and must remain excluded from future commits.

## Rechecking before publishing

Run python3 scripts/check-public-source.py and a dedicated credential scanner using .gitleaks.toml, then npm audit in web and govulncheck for Go. Rebuild the embedded UI and scan it too. Use a new repository containing only this source package; do not copy an existing private repository's Git history. Review any additional files and URLs manually. Scanner results are a dated check, not a guarantee against all unknown vulnerabilities or future changes.

For a suspected vulnerability, use the repository owner's private GitHub security reporting option when available. Never include real keys, account files, logs or private endpoints in a public issue.

## Optional monitor

All monitor business routes require viewer authentication even on a private network. The management secret is loaded from a local secret file and never returned to the browser. Public snapshots omit official account identifiers, reset-card IDs/profile fields, full key material, credential previews and cycle history. Authorized viewers still see key display names, budgets and usage; use non-sensitive names when sharing access.

Viewer passwords are salted PBKDF2 hashes. Signed cookies use Secure, HttpOnly, SameSite=Strict and a host-only prefix; changing credentials or the session secret revokes cookies. HTTPS must terminate at a trusted proxy. The loopback-only Compose port, strict Host allowlist, CSP and global failed-password throttling supplement authentication. There is no MFA, per-viewer authorization or per-client throttle. Keep CPA management private, and restrict the read-only dashboard to intended viewers.

Demo mode contains fabricated data and makes no external calls. Live mode accesses only official usage/reset-credit endpoints through CPA. Explicit cycle synchronization changes the ledger, even though the browser exposes no write routes. Python security maintenance depends on your runtime image; no full OS image vulnerability scan is included in this release.
