# Axiolex local development Makefile
# -----------------------------------------------------------------------------
# Quick reference (most common tasks):
#   make install       -> install Axiolex + server + dev tooling (BM25 lexical only)
#   make colbert       -> add ColBERT extra for semantic/hybrid search
#   make start         -> host mode: Redis container + servers on host (dev)
#   make stop          -> host mode: kill servers + stop Redis container
#   make docker-up     -> docker mode: Axiolex + Redis in containers (prod-like)
#   make docker-down   -> docker mode: stop and remove containers
#   make docker-logs   -> docker mode: tail Axiolex container logs
#   make docker-build  -> docker mode: rebuild the Axiolex image
#   make test          -> execute the full pytest suite (COV=1 adds coverage)
#   make format        -> auto-format Python code and run Ruff fixes
#   make inspector     -> launch MCP Inspector to test tools interactively
# Use the environment variables below to override Redis/tool config on the fly.

.PHONY: install colbert start stop index-refresh \
        test format type-check build clean inspector \
        redis-start redis-wait redis-stop servers-stop \
        docker-up docker-down docker-logs docker-build docker-restart

# Docker container name used for local Redis.
REDIS_CONTAINER ?= axiolex-redis
# Hostname and port used by AXIOLEX to reach Redis.
REDIS_HOST ?= localhost
REDIS_PORT ?= 6380
# Redis DB index reserved for AXIOLEX data.
REDIS_DB ?= 0
# Seconds to wait for Docker Redis readiness.
REDIS_READY_ATTEMPTS ?= 30
# Host port the Axiolex API server binds to. MCP is served at /mcp on the
# same port. Used by `make stop` to kill any process still listening.
API_PORT ?= 9700
# Local files describing tool metadata and MCP providers.
TOOLS_FILE ?= source_files/tools_list.yaml
PROVIDERS_FILE ?= source_files/mcp_providers.yaml
UV ?= uv
# Directory where background server logs are written by `make start`.
LOG_DIR ?= logs
# Env file for docker-compose. Uses the same .env as host-mode development.
# Redis host/port in .env are ignored inside containers (compose hardcodes
# the internal service name). All other vars (TOP_K, HYBRID_ENABLED, API
# keys, etc.) are shared between host and Docker modes.
DOCKER_ENV_FILE ?= .env

export AXIOLEX_REDIS_HOST := $(REDIS_HOST)
export AXIOLEX_REDIS_PORT := $(REDIS_PORT)
export AXIOLEX_REDIS_DB := $(REDIS_DB)
export AXIOLEX_TOOLS_FILE := $(TOOLS_FILE)
export AXIOLEX_MCP_PROVIDERS_FILE := $(PROVIDERS_FILE)

# Install Axiolex with server + dev tooling. The app runs with BM25 lexical
# search out of the box. For semantic/hybrid search, run `make colbert` after.
install:
	$(UV) sync --extra server --extra dev
	@echo ""
	@echo "Done. For semantic/hybrid search, run: make colbert"

# Install the ColBERT extra for semantic/hybrid search on top of `make install`.
colbert:
	$(UV) sync --extra server --extra dev --extra colbert
	@echo ""
	@echo "ColBERT installed. Set AXIOLEX_HYBRID_ENABLED=true in .env to enable."

# make start: Ensures Redis is up (required — Axiolex is a shared service),
# refreshes the catalog (YAML tools + MCP discovery from every enabled
# provider), then launches the API server (which also serves MCP at /mcp)
# in the background. Control returns to the terminal immediately. Fails
# fast if Redis cannot be started. Providers that cannot be discovered are
# logged and skipped (non-fatal). Logs are written to $(LOG_DIR)/api.log.
start:
	$(MAKE) redis-start
	$(MAKE) redis-wait
	$(MAKE) index-refresh
	@mkdir -p $(LOG_DIR)
	@echo "Application / Web running on http://localhost:$(API_PORT)"
	@echo "MCP endpoint running on http://localhost:$(API_PORT)/mcp"
	@echo "AXIOLEX Redis: redis://localhost:$(REDIS_PORT)/$(REDIS_DB)"
	@if grep -qi 'AXIOLEX_HYBRID_ENABLED=true' .env 2>/dev/null; then \
		cache_dir=$$(grep 'AXIOLEX_COLBERT_CACHE_DIR' .env 2>/dev/null | head -1 | cut -d= -f2 | tr -d ' ' | sed "s|~|$$HOME|"); \
		cache_dir=$${cache_dir:-$$HOME/models/fastembed_cache}; \
		if ! ls "$$cache_dir"/models--colbert-* >/dev/null 2>&1; then \
			echo "Downloading ColBERT model (~436MB, first time only)..."; \
			echo "  Progress will appear in $(LOG_DIR)/api.log. Startup is slower until download completes."; \
		else \
			echo "ColBERT model: cached (semantic search ready)"; \
		fi; \
	fi
	@nohup $(UV) run --extra server --extra colbert -- axiolex --config settings.yaml --port $(API_PORT) > $(LOG_DIR)/api.log 2>&1 &
	@echo "Server launched in background. Logs: $(LOG_DIR)/api.log"
	@echo "Stop with: make stop"

# make stop: Kill the API/MCP servers (any process bound to their ports) and
# stop the local Redis container. Safe to run even if nothing is running.
stop: servers-stop redis-stop

# --- Docker Compose mode (Axiolex + Redis in containers) ---------------------
# Uses docker-compose.yml + $(DOCKER_ENV_FILE). Redis is internal to the
# compose network; only the Axiolex HTTP port is exposed to the host.

# Start Axiolex + Redis in containers. Builds the image if needed.
# Uses the same .env file as host-mode `make start`.
docker-up:
	@if [ ! -f $(DOCKER_ENV_FILE) ]; then \
		echo "Creating $(DOCKER_ENV_FILE) from .env.example..."; \
		cp .env.example $(DOCKER_ENV_FILE); \
		echo "Edit $(DOCKER_ENV_FILE) to set API keys, hybrid search, etc."; \
	fi
	docker compose --env-file $(DOCKER_ENV_FILE) up -d --build
	@echo ""
	@echo "Axiolex running on http://localhost:9700"
	@echo "Redis: internal to compose network (not exposed)"
	@echo "Logs: make docker-logs"
	@echo "Stop: make docker-down"

# Stop and remove containers + network. Volumes are preserved.
docker-down:
	docker compose --env-file $(DOCKER_ENV_FILE) down

# Stop and remove containers + network + volumes (full reset).
docker-down-volumes:
	docker compose --env-file $(DOCKER_ENV_FILE) down -v

# Tail Axiolex container logs (Ctrl-C to exit).
docker-logs:
	docker compose --env-file $(DOCKER_ENV_FILE) logs -f axiolex

# Rebuild the Axiolex image without cache.
docker-build:
	docker compose --env-file $(DOCKER_ENV_FILE) build --no-cache

# Restart the Axiolex container (e.g. after editing source_files/*.yaml).
docker-restart:
	docker compose --env-file $(DOCKER_ENV_FILE) restart axiolex

# Pull external tool definitions into Redis so the servers use fresh data.
index-refresh:
	$(UV) run -- axiolex-index refresh

# Run the main pytest suite with verbose test names. Set COV=1 to also
# collect coverage data and generate an HTML report.
test:
	$(UV) run -- pytest tests/ -v $(if $(filter 1,$(COV)),--cov=axiolex --cov-report=html)

# Build the distributable wheel + sdist artifacts.
build:
	@mkdir -p axiolex/source_files
	@cp source_files/tools_list.yaml source_files/mcp_providers.yaml source_files/documents.yaml axiolex/source_files/
	@cp .env.example axiolex/.env.example
	$(UV) build
	@rm -rf axiolex/source_files axiolex/.env.example

# Remove temporary build outputs + Python caches.
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Format Python files with Black, then auto-fix lint issues via Ruff.
format:
	$(UV) run -- black axiolex/
	$(UV) run -- ruff check axiolex/ --fix

# Run mypy static type checks across the axiolex package.
type-check:
	$(UV) run -- mypy axiolex/

# Launch the MCP Inspector to test axiolex_discover_tools, list_namespaces,
# and axiolex_execute_tool interactively in a browser UI. Starts the API
# server on $(API_PORT) if it isn't already running (MCP is served at /mcp
# on the same port). Open the printed URL.
inspector:
	@if ! lsof -ti tcp:$(API_PORT) >/dev/null 2>&1; then \
		echo "API server not running on port $(API_PORT), starting it..."; \
		nohup $(UV) run --extra server --extra colbert -- axiolex \
			--config settings.yaml --port $(API_PORT) \
			> $(LOG_DIR)/api.log 2>&1 & \
		sleep 5; \
		echo "Server started on http://localhost:$(API_PORT)"; \
	else \
		echo "Server already running on port $(API_PORT)"; \
	fi
	@echo "Launching MCP Inspector..."
	npx @modelcontextprotocol/inspector http://localhost:$(API_PORT)/mcp/

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

# Kill any process still listening on the API port.
# Uses `lsof` so it works on macOS and Linux without extra dependencies.
servers-stop:
	@for port in $(API_PORT); do \
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
