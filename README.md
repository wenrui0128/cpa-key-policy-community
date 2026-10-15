# cpa-key-policy

An API key management plugin for [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI). Configure model access, rate limits, daily and weekly budgets, model aliases and credential groups. Manage keys inside CPA, and optionally deploy CPA Limits to view quota and usage.

Version: **0.5.1-community.2** (prerelease) · [中文说明](README.zh-CN.md)

## Features

- Per-key model access, RPM limits, and daily or weekly budgets.
- Token or per-call pricing, weekly usage by default, and inline weekly-budget editing.
- Shared model aliases with multiple targets and priority or round-robin dispatch.
- Credential selection by account tier or custom group, with weighted scheduling.
- Key creation, editing, rotation and deletion through a web UI or management API.
- An optional monitor for official quota, reset times and key usage, with opt-in official-cycle synchronization.

## Screenshots

CPA Limits:

![CPA Limits dashboard](docs/images/monitor-desktop.png)

Key management inside CPA:

![Key management](docs/images/plugin-desktop.png)

## Install

The supplied binary targets **Linux amd64 / glibc** and has been tested with CPA **8.0.24**. Alpine/musl, arm64 and other environments require a separate build and validation.

1. Download the Linux amd64 ZIP from [Releases](https://github.com/wenrui0128/cpa-key-policy-community/releases) and verify it against `SHA256SUMS`.
2. Place `cpa-key-policy-v0.5.1-community.2.so` in CPA's `plugins.dir`. Keep this filename: CPA derives the plugin ID from it.
3. Enable the plugin in the CPA configuration:

```yaml
plugins:
  enabled: true
  dir: "plugins"
  configs:
    cpa-key-policy:
      enabled: true
      priority: 10
      state_file: "cpa-key-policy-state.json"
      global_weighted_round_robin: false
```

4. Restart CPA and open the management page:

```text
http://<cpa-host>:<port>/v0/resource/plugins/cpa-key-policy/index.html
```

Sign in with the CPA management secret. The page keeps it in memory; reloading requires another login. Use HTTPS for Internet access, or access the management page over an encrypted private network.

For upgrades, back up `state_file`, replace the library and restart CPA. Keep only one key-policy library installed and retain the existing `state_file`, which stores keys, aliases, classification rules and usage.

See [config.example.yaml](config.example.yaml) for a full configuration example.

## Create and use a key

1. Open the Keys page, create a key and select its allowed models or aliases.
2. Set RPM, daily or weekly budgets, and token or per-call prices for the models.
3. Save the complete key returned on creation. It is shown only when created or rotated.
4. Configure the client with CPA's OpenAI-compatible API URL and the new key. Set `model` to an allowed model or alias.

For example, map the alias `fast` to provider `codex` and target model `gpt-5.4-mini`. Clients can then send requests with `model: fast`.

**Do not add plugin-issued keys to CPA's native `api-keys` configuration. Doing so may bypass plugin access controls and budgets.**

### Budgets and billing

- Usage is charged in USD at the configured model prices, subject to daily and weekly limits.
- **A budget of 0 means unlimited.** Unpriced or zero-priced models may incur no budget charge.
- Admission checks use completed usage. There is no reservation for concurrent requests, so final spending can exceed a limit.
- The UI displays weekly usage by default. Daily accounting resets at UTC 00:00.
- `/v1/models` access is an allow/deny setting. When allowed, it returns CPA's global model list rather than a per-key list. Model permissions still apply to inference requests.

### Management pages

| Page | Purpose |
|---|---|
| Keys | Manage keys, model access, RPM and budgets; view usage |
| Mapping → Aliases | Configure shared aliases, targets, dispatch and pricing |
| Mapping → Classification | Configure credential groups and preview matches |
| Model picker | Select models by provider, account tier and custom group |

## Deploy the quota monitor

[CPA Limits](monitor/README.md) is a separate Python service displaying official weekly quota, reset time, per-key budgets and usage, and reset-card expiry. Its browser interface is read-only. Change budgets and key settings in the plugin management UI.

Official-cycle synchronization is disabled by default. Setting `SYNC_OFFICIAL_CYCLE=true` makes all plugin keys follow one Codex account's official weekly cycle. Initial adoption preserves spending. Later confirmed cycles archive earlier usage and retain recorded consumption after the new boundary.

`ESTIMATED_TOTAL` controls only the displayed quota estimate; it does not change key budgets. Official percentages and costs calculated from model prices are tracked separately.

See the [monitor guide](monitor/README.md) for installation, login, HTTPS proxy configuration and settings.

## Model aliases and credential groups

### Aliases

An alias maps a client model name to one or more upstream targets. Multiple keys can reference the same alias.

| Field | Meaning |
|---|---|
| `provider` | CPA provider ID, such as `codex`, `claude`, or an OpenAI-compatible channel's `name` |
| `target_model` | Upstream model ID |
| `group` | Optional credential group |
| `dispatch` | `priority` or `round-robin` |
| `billing_mode` | `tokens` (per-million token pricing) or `per_call` |

Authentication and routing share one target selection per request, keeping the group and target consistent. Non-streaming JSON responses have their top-level `model` rewritten to the alias. Streaming response bodies are unchanged.

For OpenAI-compatible channels, use the channel's CPA `name` as `provider`. Include the target model in the channel's `models` configuration, or CPA may report that no credential is available.

### Credential groups

| Type | `group` value | Source |
|---|---|---|
| Built-in account tier | `free`, `team`, `supported`, etc. | Codex `plan_type`, Antigravity `tier` |
| Custom group | `classify:<name>` | Plugin classification rules |

Custom rules match credential fields such as `filename`, `provider`, `plan_type` and `tier` using regular expressions. A credential can belong to multiple custom groups. Without a match, Codex and Antigravity use built-in tiers; other auth-file providers remain ungrouped. OpenAI-compatible and API-key channels are also ungrouped.

When group filtering is active, the plugin selects credentials within that group. If none are available, it returns `auth_not_found`.

### Weighted scheduling

The scheduler selects the highest available `Priority` tier, then applies smooth weighted round-robin.

- Weight is read from `Weight`, `Attributes.weight` or `Metadata.weight`.
- Missing or invalid values default to `1`; non-positive values stop new requests; the maximum is `1000000`.
- Scheduling state is shared by `provider + model + group + Priority`, so all plugin keys use the same distribution.
- Lower-priority credentials participate only when higher-priority credentials are unavailable or have non-positive weight.
- If CPA does not pass authentication group metadata to the scheduler, plugin keys use a global weighted pool for the current provider and model. Native CPA keys are unaffected.

Setting `global_weighted_round_robin: true` skips group filtering and pools all candidates for the current provider and model. To isolate requests by account tier, leave it `false` and verify that your CPA version passes group metadata.

## Management API

All paths use the prefix `/v0/management/plugins/cpa-key-policy` and require CPA management Bearer authentication.

| Endpoint | Purpose |
|---|---|
| `GET/POST/PATCH/DELETE /keys` | List, create, update and delete keys |
| `POST /keys/rotate?id=…` | Rotate a key |
| `POST /keys/reset-rpm?id=…` | Reset RPM counters |
| `GET /keys/usage?id=…` | Read key usage |
| `GET /status` | Read plugin status |
| `GET/POST/DELETE /aliases` | Manage aliases |
| `GET/POST/DELETE /classify-rules` | Manage classification rules |
| `POST /classify-rules/reorder` | Reorder rules |
| `POST /classify-preview` | Preview group matches |
| `POST /catalog` | Build the model-picker catalog |

With `CPA` set to the CPA base URL and `MANAGEMENT_KEY` set to the management secret:

```bash
curl -X POST "$CPA/v0/management/plugins/cpa-key-policy/keys" \
  -H "Authorization: Bearer $MANAGEMENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "team-a",
    "name": "Team A",
    "rpm": 60,
    "models": [
      {"alias":"fast","provider":"codex","target_model":"gpt-5.4-mini","group":"free"}
    ]
  }'
```

Save `plain_key` from the response; it is returned only once.

## Build from source

Requires Node.js 24+, Go 1.27.2 and a C compiler with cgo support. On Linux amd64:

```bash
make test
make build-linux-amd64
```

Rename the build output when installing:

```bash
install -m 0644 dist/cpa-key-policy_linux_amd64.so \
  "$CPA_PLUGIN_DIR/cpa-key-policy-v0.5.1-community.2.so"
```

Set `CPA_PLUGIN_DIR` to CPA's plugin directory. Use `make build-linux-arm64` on native Linux arm64; runtime compatibility on that platform has not been verified. On Windows, build through WSL/Linux.

For frontend development:

```bash
cd web
npm ci --ignore-scripts
VITE_CPA_BASE=http://127.0.0.1:8317 npm run dev
```

Run `make web-build` before compiling the Go library directly to update the embedded frontend.

## Tests

From the repository root:

```bash
go test ./...
(cd web && npm test && npm run build)
python3 -m unittest discover -s monitor -p 'test_*.py' -v
```

Integration tests require a Linux Docker host and a local CPA 8.0.24 image:

```bash
python3 scripts/test-integration.py
```

Override `CPA_TEST_IMAGE` to select another image. Tests use temporary containers, a dedicated network and mocked official quota responses, then remove their runtime state. See [VALIDATION.md](VALIDATION.md) for compatibility and test coverage, and [SECURITY.md](SECURITY.md) for security configuration.

## Attribution and license

Based on [origin652/cpa-plugin-key-policy](https://github.com/origin652/cpa-plugin-key-policy) v0.5.1, with the original attribution and [MIT license](LICENSE) retained. This repository is a community fork. The [CPA Plugins Store](https://github.com/router-for-me/CLIProxyAPI-Plugins-Store) distributes the upstream version.

See [CHANGELOG.md](CHANGELOG.md) for version history.
