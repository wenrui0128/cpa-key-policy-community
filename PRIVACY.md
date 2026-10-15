# Data and privacy

## Local data

| Component | Stored data | Location |
|---|---|---|
| Plugin | Key hashes and partial previews, display names, policies, aliases, classification rules and usage | Configured `state_file` |
| Monitor | Viewer password hash and session configuration | Monitor `data` directory |
| Monitor | Cached quota and usage | `data/cache.sqlite` |
| Monitor | CPA management secret | Local secret file mounted into the container |

Generated downstream keys are returned in full only when created or rotated. The plugin stores hashes and partial previews. The plugin management page keeps its management secret in memory rather than localStorage.

Monitor login cookies are signed and bound to the viewer password. Changing the password or session secret invalidates existing cookies.

Keep state files, monitor data, secret files, logs and backups outside version control. Use protected storage for backups; usage records and display names may identify users even without complete API keys.

## What viewers can see

Authenticated monitor viewers can see Key display names, budgets and usage, official remaining percentage, reset time and reset-card expiry. Viewer access grants access to those statistics.

Monitor snapshots omit official account identifiers, reset-card IDs and profile fields, complete key material, credential previews and cycle history. The CPA management secret is read by the service and is not sent to the browser.

## External requests

- CPA handles upstream model requests. The Go plugin has no independent HTTP listener, outbound HTTP client or telemetry.
- The plugin management page sends management requests to its selected CPA address.
- The optional price-reference feature fetches public LiteLLM pricing from `raw.githubusercontent.com`. It sends no account, API key, model selection or prompt, omits cookies and referrers, and rejects redirects. The remote server can observe the browser's connection IP. Manual pricing remains available if the request is blocked.
- In live mode, the monitor reads official usage and reset-credit data through CPA. With official-cycle synchronization enabled, it also updates the plugin's cycle state.
- Demo mode uses sample data and does not run the collectors.

No third-party executable script or font is loaded by the plugin management page.

## Examples and screenshots

Repository examples and screenshots use demonstration data. Before sharing your own screenshots, logs or bug reports, remove credentials, account identifiers, service addresses and any usage details you do not want to disclose.

See [SECURITY.md](SECURITY.md) for authentication and deployment guidance.
