# CPA Limits

A quota dashboard for the community key-policy plugin. It displays official weekly quota and reset time, per-key budgets and usage, and unused reset-card expiry. Change key settings and budgets in the CPA plugin management page.

Requires Python 3.10+ with no third-party Python packages, or Docker Compose.

## Try the demo

From the `monitor` directory:

```bash
python3 init_auth.py --data ./data --username viewer --days 30
DATA_DIR="$PWD/data" DEMO_MODE=true BIND=127.0.0.1 PORT=18765 python3 app.py
```

Open `http://127.0.0.1:18765/` and sign in with the credentials you created. Choose a password of at least 16 characters. Demo mode displays sample data without connecting to CPA.

For a Docker demo, initialize credentials as above, then run:

```bash
sudo chown -R 10001:10001 data
docker compose -f compose.demo.yaml up -d --build
```

Persistent login uses Secure cookies and requires HTTPS. Browser support on HTTP localhost varies; HTTP Basic authentication is also available for local testing.

## Connect to CPA

Install and enable the community plugin in CPA first. Keep only one key-policy library installed.

From the `monitor` directory:

1. Copy `.env.example` to `.env` and set `CPA_BASE` to a CPA address reachable from inside the monitor container. For example, use CPA's service name on a shared Docker network. `127.0.0.1` inside the container points to the monitor itself.
2. Run `python3 init_auth.py --data ./data --username viewer --days 30` to create viewer credentials. The session duration can be 7–365 days. Password entry is hidden, and the password is stored as a salted PBKDF2 hash.
3. Create the `secrets` directory and place CPA's management secret in `secrets/cpa_management_key`, using a local editor or a secret-management tool. Use the management secret, not a downstream client key.
4. Set permissions and start the service:

```bash
chmod 700 data secrets
chmod 600 secrets/cpa_management_key
sudo chown -R 10001:10001 data secrets
docker compose up -d --build
```

The container runs as UID/GID `10001` and publishes `127.0.0.1:18765`. If CPA uses a separate Compose project, declare its Docker network as an external network in your local Compose configuration. For a temporary connection, use:

```bash
docker network connect YOUR_CPA_NETWORK "$(docker compose ps -q monitor)"
```

Declare the network in Compose for it to survive container recreation.

## HTTPS reverse proxy

Configure an HTTPS reverse proxy to forward the dashboard hostname to `http://127.0.0.1:18765`. If the proxy runs in another container, use a shared network and the monitor service address instead of container localhost.

- Add the exact public hostname to `ALLOWED_HOSTS`, including the port when it is not 443.
- Preserve the request's `Host`, `Authorization` and `Cookie` headers, and the response's `Set-Cookie` and security headers.
- Forward all monitor routes, including `/`, `/app.js`, `/style.css` and `/api/state`.
- Keep CPA management endpoints on a separate, restricted address.

All business routes require viewer authentication. Anonymous `/health` returns only `{"ok":true}`; it confirms that the web service is running, not that quota synchronization is working. Avoid exposing the container port directly to the Internet.

## Settings

| Variable | Default | Purpose |
|---|---|---|
| `CPA_BASE` | Set in `.env` | CPA base URL reachable from the monitor |
| `SYNC_OFFICIAL_CYCLE` | `false` | Synchronize all plugin keys to the official weekly cycle |
| `ESTIMATED_TOTAL` | `1000` | Total quota estimate used for display |
| `DISPLAY_TIMEZONE` | `UTC` | Timezone for displayed dates |
| `ALLOWED_HOSTS` | Set in `.env` | Allowed request hosts, including non-default ports |
| `DEMO_MODE` | `false` | Display sample data without collecting live quota |

Changing `ESTIMATED_TOTAL` does not change key budgets. Official quota percentages and model-priced dollar amounts are separate measurements. Display timezone settings do not affect plugin daily accounting, which resets at UTC 00:00.

### Official-cycle synchronization

With `SYNC_OFFICIAL_CYCLE=false`, the monitor reads quota and usage without changing the plugin ledger.

Set it to `true` to make **all plugin keys** follow one Codex account's official weekly cycle:

- First adoption preserves existing spending.
- A new cycle must appear in two observations at least 30 seconds apart.
- Once confirmed, the plugin archives earlier usage and retains completion events recorded after the new cycle boundary.
- Query failures, expired quota, cycle rollback or account mismatch preserve the last confirmed values.

Official quota is polled every 120 seconds; key statistics every 15 seconds. Synchronization requires exactly one enabled Codex account and an identifiable 604800-second weekly window. Multiple-account aggregation is not supported. A manual midweek reset may need review if the reported timestamps do not form a valid weekly window.

The browser has no write controls. The collector uses CPA's authenticated `api-call` bridge for official usage and reset-credit queries; enabling cycle synchronization also allows it to call the plugin's cycle-sync endpoint.

## Change credentials

Stop the monitor before replacing credential files.

To change the viewer password, move these files from `data` into a protected backup location, then rerun `init_auth.py`:

- `loopback-auth.json`
- `public-session.json`
- `public-session-secret`

Keep `cache.sqlite` in place, restore UID/GID `10001` ownership if using Docker, and restart. Changing the password or session secret invalidates existing login cookies.

To rotate the CPA management secret, replace `secrets/cpa_management_key`, retain its permissions and restart the monitor.

## Troubleshooting

| Symptom | Check |
|---|---|
| CPA connection fails | Confirm `CPA_BASE` is reachable from inside the container and both services share the expected network |
| Request is rejected by host validation | Add the browser's exact hostname and port to `ALLOWED_HOSTS` |
| Persistent login does not work | Use HTTPS and check that the proxy preserves cookies |
| Service is healthy but quota is stale | Check the management secret, selected Codex account and collector logs |
| Budget stays unchanged after editing the total estimate | Edit the Key budget in the plugin; `ESTIMATED_TOTAL` affects display only |

## Tests

From the repository root:

```bash
python3 -m unittest discover -s monitor -p 'test_*.py' -v
```

See [SECURITY.md](../SECURITY.md) for authentication and budget-enforcement limits, and [PRIVACY.md](../PRIVACY.md) for stored data and external requests.
