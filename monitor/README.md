# CPA Limits monitor

A separate, read-only Python service for the community key-policy plugin. It displays weekly key budgets and usage, official weekly remaining percentage, reset time and unused reset-card expiry. It has no budget editor, key creation route or reset-card consumption route. Use the plugin management UI to change policies.

The screenshots use fabricated data. No account, management secret or downstream API key is bundled. Python 3.10+ is supported; no third-party Python packages are required.

## Local synthetic demo

```bash
python3 init_auth.py --data ./data --username viewer --days 30
DATA_DIR="$PWD/data" DEMO_MODE=true BIND=127.0.0.1 PORT=18765 python3 app.py
```

Open `http://127.0.0.1:18765/` and enter the credentials you just created. Demo mode performs no CPA calls and no upstream calls. Persistent Secure cookies require HTTPS; on localhost browser support varies, and HTTP Basic authentication remains available. Never send passwords over unencrypted public HTTP.

For a Docker demo, initialize credentials as above, then prepare the container ownership and launch:

```bash
sudo chown -R 10001:10001 data
docker compose -f compose.demo.yaml up -d --build
```

## Connect to CPA

1. Install the community plugin in CPA. Only one key-policy billing plugin should be enabled.
2. Copy `.env.example` to `.env`. Set `CPA_BASE` to an address reachable **from the monitor container**. Container localhost points to the monitor, not CPA. Join the monitor to CPA's Docker network when using CPA's service name; alternatively use a reachable host address. The example hostname is a placeholder.
3. Initialize the viewer password with `init_auth.py`. It must contain at least 16 characters. The password is hidden and stored only as a salted PBKDF2 hash. Session duration can be 7–365 days.
4. Create `secrets/cpa_management_key` locally with CPA's management secret. This is the management credential, not a downstream client key. Do not paste it into issues, screenshots or shell command arguments.
5. Set local permissions and start:

```bash
chmod 700 data secrets
chmod 600 secrets/cpa_management_key
sudo chown -R 10001:10001 data secrets
docker compose up -d --build
```

The supplied Compose publishes only `127.0.0.1:18765`. To join an existing CPA network, after setting `CPA_BASE` to its service name, run `docker network connect YOUR_CPA_NETWORK "$(docker compose ps -q monitor)"`, or declare that network in your local Compose file. Authentication applies to every business route regardless of source network. Anonymous `/health` returns only `{"ok":true}` and is a liveness check, not proof of successful quota synchronization.

For Internet access, put an HTTPS reverse proxy in front of the loopback listener, preserve the Host/Authorization/Cookie headers, and add the exact public hostname **including any non-default port** to `ALLOWED_HOSTS`. Proxy every required monitor route (`/`, `/app.js`, `/style.css`, `/api/state`) through authentication; do not expose CPA management routes. Avoid exposing the container port directly.

## Official-cycle synchronization

`SYNC_OFFICIAL_CYCLE=false` is the safe default: the collector displays official quota and never changes the plugin ledger. Set it to `true` only when you want **all plugin keys** to follow the single Codex account's official weekly cycle. The first adoption preserves existing consumption. A later cycle must be observed twice at least 30 seconds apart; the plugin archives old usage and preserves completion events recorded after the new boundary. Changing accounts, rollback, expired quota and query failure preserve the last confirmed values. Polling is every 120 seconds; key statistics poll every 15 seconds.

This option writes only the plugin cycle-sync endpoint. The collector otherwise queries read-only upstream endpoints through CPA's authenticated `api-call` bridge. It requires exactly one enabled Codex account and an identifiable 604800-second weekly window. Multi-account quota aggregation is not implemented. A manual midweek reset can require review if the upstream timestamps do not represent a valid weekly window.

`ESTIMATED_TOTAL` is a display-only estimate, default 1000. Official percentage and key-priced dollars are different units; changing the estimate does not change key budgets. `DISPLAY_TIMEZONE` controls dates, default UTC. Plugin daily accounting still changes at UTC 00:00; the default UI displays weekly consumption.

## Credential maintenance

Stop the monitor before replacing credential files. To change the viewer password, securely remove or move the three auth/session files from `data` and rerun `init_auth.py`; leave `cache.sqlite` intact. Restart the service. Changed password or session secret revokes old cookies. To rotate the CPA management secret, replace only the secret file and restart. Do not publish the data or secrets directories.

Run offline tests with `python3 -m unittest discover -s monitor -p 'test_*.py' -v` from the repository root. Budget enforcement uses finalized usage, not reservations: concurrent requests may exceed a cap. Models with zero pricing do not consume a dollar budget. See the repository security document for the remaining limitations.
