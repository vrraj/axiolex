# AxioLex — Backlog / To-Do

Tasks identified during development that are deferred to a future phase.
Each entry describes the problem, the proposed approach, and the scope.

---

## stdio config-dir resolution + CLI secret management

**Status:** Not started
**Priority:** Medium (enables air-gapped / no-server deployments)
**Related incident:** Claude Desktop `axiolex_execute_tool` 401 failure (2026-08-31)

### Problem

When Claude Desktop spawns Axiolex as a stdio MCP server, the subprocess
inherits Claude Desktop's environment:

- **CWD is `/`** — relative paths like `source_files/mcp_secrets.enc` and
  `logs/` resolve to `/source_files/...` and `/logs/` (read-only on macOS).
- **No `.env` loading** — `server.py` `main()` does not call `load_dotenv()`
  (unlike `cli.py` and `index_cli.py`), so `AXIOLEX_SECRET_MASTER_KEY`,
  Redis config, and other settings are not available.
- **No API keys in OS env** — provider API keys now live only in the encrypted
  store (`source_files/mcp_secrets.enc`), which the stdio process cannot find.

Result: the stdio server cannot decrypt provider credentials, cannot reach
Redis (no host/port), and cannot write audit logs. Tool execution fails with
opaque errors (e.g. `401 Unauthorized` from upstream providers).

### Why HTTP is the recommended path

For local dev and enterprise, the HTTP pattern (`"url": "http://localhost:9701/mcp"`)
avoids all of these issues — the server process (started via `make start` or
Docker) loads `.env` and resolves all paths relative to the project root.
See `docs/claude-mcp.md` for the recommended setup.

The stdio pattern is only needed for air-gapped machines or environments
where a persistent server is not possible. This task makes that pattern work
without requiring secrets in the OS environment.

### Proposed approach

**1. Config directory resolution**

The server discovers its configuration from a standard location, with an
env-var override for dev/CI/Docker:

| Priority | Source | Example |
| --- | --- | --- |
| 1 | `AXIOLEX_CONFIG_DIR` env var (dev / CI / Docker volume) | `/Users/raj/dev/axiolex` |
| 2 | Platform standard location | `~/.config/axiolex/` (Linux), `~/Library/Application Support/axiolex/` (mac), `%APPDATA%\axiolex\` (Win) |
| 3 | CWD (current behavior, unchanged for `make start` / Docker / tests) | repo root |

Inside the config dir:

```
axiolex.env          ← master key, Redis host/port, non-secret settings (file mode 0600)
mcp_secrets.enc      ← encrypted provider API keys (AES-256-GCM)
logs/                ← audit logs
```

**2. `load_dotenv()` in `server.py` `main()`**

Load `axiolex.env` from the resolved config dir. This file contains only
non-secret settings + the master key (KEK). Provider API keys are NOT in
this file — they are decrypted from `mcp_secrets.enc` into process memory
at runtime by `resolve_secret()`.

**3. Path resolution updates**

- `secret_store.py`: resolve `mcp_secrets.enc` from config dir (not relative CWD)
- `service.py`: resolve `AXIOLEX_LOG_DIR` from config dir (not relative CWD)
- `namespace_service.py`: resolve `namespaces.yaml` from config dir if not in CWD

**4. CLI commands for secret management**

```
axiolex init                              # create config dir, generate master key, write axiolex.env
axiolex secret set <provider_id>          # prompt for key, encrypt to mcp_secrets.enc
axiolex secret get <provider_id>          # print whether a secret exists (never print the value)
axiolex secret delete <provider_id>       # remove from encrypted store
axiolex secret list                       # list provider IDs that have secrets
```

These complement the existing web UI and REST endpoints for environments
where the UI is not running.

### Enterprise deployment note

For enterprise, the **HTTP pattern is the standard** — one central server,
N desktops connecting via URL, no secrets on any desktop. The stdio
config-dir work is for the air-gapped / no-server niche only.

Per-desktop master keys mean each machine is independently provisioned.
A shared master key across desktops would create a fleet-wide single point
of failure (one stolen laptop → all API keys compromised). Different keys
per desktop means per-machine provisioning. Neither is ideal for scale,
which is why HTTP remains the recommended enterprise pattern.

### Scope

| Component | Change |
| --- | --- |
| `axiolex/mcp/server.py` | Add config-dir resolution + `load_dotenv()` in `main()` |
| `axiolex/mcp/secret_store.py` | Resolve `mcp_secrets.enc` from config dir |
| `axiolex/mcp/execution/service.py` | Resolve log dir from config dir |
| `axiolex/services/namespace_service.py` | Resolve `namespaces.yaml` from config dir |
| `axiolex/cli.py` (or new `axiolex/config_cli.py`) | Add `init`, `secret set/get/delete/list` subcommands |
| `docs/claude-mcp.md` | Update stdio section to remove "current limitation" note |
| `docs/technical_architecture.md` | Update client connection patterns table |
| Tests | Config-dir resolution, CLI commands, stdio bootstrap |

### Out of scope (future phases)

- Secrets-manager integration (AWS Secrets Manager, Vault) for master key
  retrieval — replaces the `axiolex.env` file read with a pluggable provider.
- Per-client encryption / key distribution protocol for fleet-scale stdio.
- In-memory cache backend (separate task — see Redis requirement discussions).
