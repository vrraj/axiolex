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

For local dev and enterprise, the HTTP pattern (`"url": "http://localhost:9700/mcp"`)
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

---

## Simplify tool catalog management

**Status:** Implemented (branch `catalog-freshness`, 2026-09-23)
**Priority:** High (correctness — current UI is misleading)

### The model (one sentence)

> Redis is the only catalog. Tools enter it in exactly two ways: the local
> YAML registry (`source_files/tools_list.yaml`) or live provider discovery.
> The search index always follows the catalog automatically.

### Problems today

1. **Add Tool is a trap.** `POST /documents` appends to the admin
   retriever's in-memory list only. The tool is never written to
   `tools_list.yaml` or Redis, is invisible to `axiolex_discover_tools`
   (separate read-only retriever), cannot be executed (`/execute` resolves
   from Redis), and disappears on restart.
2. **Delete Tool is a silent no-op.** `DELETE /documents/{id}` removes the
   doc from the in-memory list, then calls `_load_and_index_documents()`,
   which reloads from Redis and brings the tool right back.
3. **Reload Index and Reindex are redundant.** Both call the same
   `_load_and_index_documents()`; neither does provider discovery.
4. **First-search latency after catalog changes.** The discovery retriever
   rebuilds lazily on the next search after a catalog version bump.

### Plan

| # | Change | Effect |
| --- | --- | --- |
| 1 | Remove the traps (UI + API): **Add Tool** modal, `POST /documents`, `DELETE /documents/{id}`, per-tool **Delete** buttons, and the `POST /index` bulk endpoint — all write only to in-memory admin state: invisible to real discovery, gone on restart or reindex | Kills the traps. Note: these are public REST endpoints — flag as **breaking** in release notes (replacement: `POST /catalog/refresh` + sync endpoint) |
| 2 | Remove **Reload Index** (dead duplicate); rename **Reindex** → **Sync & Reindex** with tooltip: "Re-reads tools_list.yaml and rebuilds search indexes. For provider changes use Retrieve Tools." | One honest button for local registry changes. Verify `refresh_local_yaml_cache()` bumps the catalog version so the discovery retriever follows |
| 3 | Add **Refresh Catalog** button → `POST /catalog/refresh`; display the per-provider diff in the result (e.g., "tavily_mcp: +5, aina_markets: +4") | Full re-discovery: YAML + all providers + diff shown to the admin |
| 4 | After any catalog write — Retrieve Tools, Refresh Catalog, provider disable/delete, Sync & Reindex — eagerly rebuild the discovery retriever via a new public `rebuild_index_now()` wrapper, run through `asyncio.to_thread()` so it doesn't block the event loop | Kills first-search latency spike. Version-check lazy reload stays as fallback for out-of-process writers (CLI, second instance) |
| 5 | README: short "Catalog management" section documenting the model + button table | Anyone can understand catalog management |
| 6 | Tests: dead endpoints gone, reindex still works, eager rebuild fires after Retrieve Tools | Regression safety |

Note: for the Sync & Reindex tooltip to be honest, the endpoint must
actually re-read `tools_list.yaml` (via `refresh_local_yaml_cache()`)
before rebuilding — verify this when implementing, and that the catalog
version bumps so the discovery retriever follows.

### Resulting admin surface

| Button | Does | Use when |
| --- | --- | --- |
| Sync & Reindex | YAML → Redis → rebuild | Edited `tools_list.yaml` |
| Retrieve Tools (per provider) | Live discovery → Redis → rebuild | Provider added/changed |
| Refresh Catalog | All sources → Redis → rebuild, with diff | Bulk refresh, CI/CD |

### Scope

| Component | Change |
| --- | --- |
| `axiolex/api/routes.py` | Remove `POST /documents`, `DELETE /documents/{id}`, `POST /index`, `/documents/reload`; keep/rename `/documents/reindex-bm25s` (or rename path to `/catalog/sync`) |
| `axiolex/core/retriever.py` | Add public `rebuild_index_now()` wrapper for `_load_and_index_documents()` |
| `axiolex/services/mcp_service.py` | Eager rebuild via `asyncio.to_thread()` after Retrieve Tools / provider disable/delete |
| `axiolex/ui/templates/tool-router.html` | Remove Add Tool modal, Reload Index button, per-tool Delete buttons; rename Reindex → Sync & Reindex with tooltip; add Refresh Catalog button |
| `axiolex/ui/static/assets/app.js` | Remove add/delete/reload/index handlers; rename reindex handler; add refresh handler with diff display |
| `README.md` | Short "Catalog management" section with the model + button table; breaking-change note for removed REST endpoints |
| Tests | Update tests referencing removed endpoints; add eager-rebuild test |

Branch: `catalog-freshness`. Release notes: flag removed REST endpoints as breaking.

### Future (out of scope for this task)

- A real UI CRUD for local tools that writes `tools_list.yaml` and triggers
  the refresh path (if admins eventually need it).

