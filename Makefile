# Axiolex local development Makefile
# -----------------------------------------------------------------------------
# Quick reference (most common tasks):
#   make start     -> start Redis and run both Axiolex servers (no MCP download)
#   make start-full-> start Redis, rebuild the catalog (incl. MCP discovery), run servers
#   make stop      -> kill the API/MCP servers (ports 9700/9701) and stop Redis
#   make test      -> execute the full pytest suite (COV=1 adds coverage)
#   make format    -> auto-format Python code and run Ruff fixes
# Use the environment variables below to override Redis/tool config on the fly.

.PHONY: install dev start start-full stop run-server mcp-run index-refresh \
        test format type-check build clean \
        redis-start redis-wait redis-stop servers-stop

# Docker container name used for local Redis.
REDIS_CONTAINER ?= axiolex-redis
# Hostname and port used by AXIOLEX to reach Redis.
REDIS_HOST ?= localhost
REDIS_PORT ?= 6380
# Redis DB index reserved for AXIOLEX data.
REDIS_DB ?= 0
# Seconds to wait for Docker Redis readiness.
REDIS_READY_ATTEMPTS ?= 30
# Host ports the Axiolex API and MCP servers bind to. Used by `make stop`
# to kill any process still listening on these ports.
API_PORT ?= 9700
MCP_PORT ?= 9701
# Local files describing tool metadata and MCP providers.
TOOLS_FILE ?= source_files/tools_list.yaml
PROVIDERS_FILE ?= source_files/mcp_providers.yaml
UV ?= uv

export AXIOLEX_REDIS_HOST := $(REDIS_HOST)
export AXIOLEX_REDIS_PORT := $(REDIS_PORT)
export AXIOLEX_REDIS_DB := $(REDIS_DB)
export AXIOLEX_TOOLS_FILE := $(TOOLS_FILE)
export AXIOLEX_MCP_PROVIDERS_FILE := $(PROVIDERS_FILE)

# Sync the base package into uv's project-managed .venv.
install:
	$(UV) sync

# Sync all optional capabilities and development tools.
dev:
	$(UV) sync --all-extras

# make start: Ensures Redis is up and runs both Axiolex API and MCP servers in
# parallel. The catalog is NOT refreshed, so no MCP provider is contacted at
# startup. Use this when MCP providers are temporarily unreachable, or when you
# prefer to discover each provider's tools manually via the UI
# (http://localhost:$(API_PORT)/#mcp_providers -> "Retrieve Tools" per provider).
# Run `make index-refresh` separately, or use `make start-full`, to auto-load.
start:
	$(MAKE) redis-start
	$(MAKE) redis-wait
	@echo "Application / Web running on http://localhost:$(API_PORT)"
	@echo "MCP server running on http://localhost:$(MCP_PORT)/mcp"
	@echo "AXIOLEX Redis: redis://localhost:$(REDIS_PORT)/$(REDIS_DB)"
	@echo "Catalog not refreshed: use the UI to retrieve MCP tools, or run 'make index-refresh'."
	$(MAKE) -j2 run-server mcp-run

# make start-full: Like `make start`, but also rebuilds the catalog first
# (YAML tools + discovery from every enabled MCP provider). This is strict:
# any MCP provider listed in source_files/mcp_providers.yaml must be reachable
# at startup (no timeouts/failures), or the command exits. Use `make start` if
# you'd rather load the catalog manually via the UI.
start-full:
	$(MAKE) redis-start
	$(MAKE) redis-wait
	$(MAKE) index-refresh
	@echo "Application / Web running on http://localhost:$(API_PORT)"
	@echo "MCP server running on http://localhost:$(MCP_PORT)/mcp"
	@echo "AXIOLEX Redis: redis://localhost:$(REDIS_PORT)/$(REDIS_DB)"
	$(MAKE) -j2 run-server mcp-run

# make run-server: Serve only the main Axiolex API (without MCP tools
# auto-loading). Override API_PORT to bind a different port, or set RELOAD=1
# to enable auto-reload for active development. Examples:
#   make run-server API_PORT=8080
#   make run-server RELOAD=1
run-server:
	$(UV) run --extra server -- axiolex --config settings.yaml --port $(API_PORT) $(if $(filter 1,$(RELOAD)),--reload)

# make mcp-run: Serve the MCP discovery server (tool provider API).
mcp-run:
	$(UV) run -- axiolex-mcp-server --host 0.0.0.0 --port $(MCP_PORT)

# make stop: Kill the API/MCP servers (any process bound to their ports) and
# stop the local Redis container. Safe to run even if nothing is running.
stop: servers-stop redis-stop

# Pull external tool definitions into Redis so the servers use fresh data.
index-refresh:
	$(UV) run -- axiolex-index refresh

# Run the main pytest suite with verbose test names. Set COV=1 to also
# collect coverage data and generate an HTML report.
test:
	$(UV) run --extra dev -- pytest tests/ -v $(if $(filter 1,$(COV)),--cov=axiolex --cov-report=html)

# Build the distributable wheel + sdist artifacts.
build:
	$(UV) build

# Remove temporary build outputs + Python caches.
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Format Python files with Black, then auto-fix lint issues via Ruff.
format:
	$(UV) run --extra dev -- black axiolex/
	$(UV) run --extra dev -- ruff check axiolex/ --fix

# Run mypy static type checks across the axiolex package.
type-check:
	$(UV) run --extra dev -- mypy axiolex/

# --- Internal plumbing (called by start/stop, rarely invoked directly) --------

# Start (or create) a dedicated Redis container for Axiolex state.
redis-start:
	@docker start $(REDIS_CONTAINER) 2>/dev/null || docker run -d --name $(REDIS_CONTAINER) -p $(REDIS_PORT):6379 redis:7

# Wait until Docker Redis accepts commands before refreshing the index.
redis-wait:
	@for attempt in $$(seq 1 $(REDIS_READY_ATTEMPTS)); do \
		if docker exec $(REDIS_CONTAINER) redis-cli ping >/dev/null 2>&1; then \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Redis did not become ready after $(REDIS_READY_ATTEMPTS) seconds." >&2; \
	exit 1

# Kill any process still listening on the API and MCP ports.
# Uses `lsof` so it works on macOS and Linux without extra dependencies.
servers-stop:
	@for port in $(API_PORT) $(MCP_PORT); do \
		pids=$$(lsof -ti tcp:$$port 2>/dev/null || true); \
		if [ -n "$$pids" ]; then \
			echo "Stopping process(es) on port $$port: $$pids"; \
			echo "$$pids" | xargs kill 2>/dev/null || true; \
		else \
			echo "No process listening on port $$port."; \
		fi; \
	done

# Stop the local Redis container when you're done developing.
redis-stop:
	-docker stop $(REDIS_CONTAINER)
