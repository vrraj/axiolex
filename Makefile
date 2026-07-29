# Axiolex local development Makefile
# -----------------------------------------------------------------------------
# Quick reference (most common tasks):
#   make run       -> start Redis, rebuild the catalog, run both Axiolex servers
#   make dev-run   -> run the API with auto-reload for active development
#   make test      -> execute the full pytest suite
#   make model-ensure -> download and verify the pinned optional ColBERT model
#   make format    -> auto-format Python code and run Ruff fixes
# Use the environment variables below to override Redis/tool config on the fly.

.PHONY: install dev run run-server mcp-run redis-start redis-stop redis-status index-refresh index-status model-ensure test build clean

REDIS_CONTAINER ?= axiolex-redis        # Docker container name used for local Redis
REDIS_HOST ?= localhost                 # Hostname the app uses to reach Redis
REDIS_PORT ?= 6380                      # Local port exposed by the Redis container
REDIS_DB ?= 0                           # Redis DB index reserved for Axiolex data
TOOLS_FILE ?= source_files/tools_list.yaml          # Local file describing tool metadata
PROVIDERS_FILE ?= source_files/mcp_providers.yaml   # Local file listing MCP providers
PYTHON ?= venv/bin/python

export AXIOLEX_REDIS_HOST := $(REDIS_HOST)
export AXIOLEX_REDIS_PORT := $(REDIS_PORT)
export AXIOLEX_REDIS_DB := $(REDIS_DB)
export AXIOLEX_TOOLS_FILE := $(TOOLS_FILE)
export AXIOLEX_MCP_PROVIDERS_FILE := $(PROVIDERS_FILE)

# Install package in development mode
install:
	$(PYTHON) -m pip install -e .

# Install with development dependencies
dev:
	$(PYTHON) -m pip install -e ".[dev]"

# make run: Top-level run target that ensures Redis is up, catalog is refreshed, and both
# Axiolex API and MCP servers are started in parallel. This is strict: any MCP
# provider listed in source_files/mcp_providers.yaml must be reachable at startup
# (no timeouts/failures), or the command exits. Use `make run-server` if you need
# to bring up the API/UI if MCP providers are temporarily unavailable. You can then load the catalog manually via the UI.
run: redis-start index-refresh
	$(MAKE) -j2 run-server mcp-run

# make run-server: Serve only the main Axiolex API (without MCP tools auto-loading). You can then load the catalog manually via the UI.
# This is useful when you want to bring up the API/UI without worrying about MCP providers being available.
run-server:
	$(PYTHON) -m axiolex.cli --config settings.yaml

# make mcp-run: Serve the MCP discovery server (tool provider API).
mcp-run:
	$(PYTHON) -m axiolex.mcp.server --host 0.0.0.0 --port 9701

# Start (or create) a dedicated Redis container for Axiolex state.
redis-start:
	@docker start $(REDIS_CONTAINER) 2>/dev/null || docker run -d --name $(REDIS_CONTAINER) -p $(REDIS_PORT):6379 redis:7

# Stop the local Redis container when you're done developing.
redis-stop:
	docker stop $(REDIS_CONTAINER)

# Inspect the Redis container status (helpful while debugging).
redis-status:
	@docker ps -a --filter name=$(REDIS_CONTAINER) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Pull external tool definitions into Redis so the servers use fresh data.
index-refresh:
	$(PYTHON) -m axiolex.index_cli refresh

# Show the state of the cached tool index without modifying it.
index-status:
	$(PYTHON) -m axiolex.index_cli status

# Download/verify the pinned default ColBERT model before enabling hybrid search.
# If AXIOLEX_COLBERT_CACHE_DIR is set, use the same cache location as the app.
model-ensure:
	$(PYTHON) -m axiolex.cli model-ensure $(if $(AXIOLEX_COLBERT_CACHE_DIR),--cache-dir "$(AXIOLEX_COLBERT_CACHE_DIR)")

# Run the API server on a custom port (e.g., when 8080 fits your setup).
run-port:
	$(PYTHON) -m axiolex.cli --config settings.yaml --port 8080

# Development helper: auto-reload on code changes.
dev-run:
	$(PYTHON) -m axiolex.cli --config settings.yaml --reload

# Run the main pytest suite with verbose test names.
test:
	$(PYTHON) -m pytest tests/ -v

# Run pytest while collecting coverage data + HTML report.
test-cov:
	$(PYTHON) -m pytest tests/ --cov=axiolex --cov-report=html

# Build the distributable wheel + sdist artifacts.
build:
	$(PYTHON) -m build

# Remove temporary build outputs + Python caches.
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Format Python files with Black, then auto-fix lint issues via Ruff.
format:
	black axiolex/
	ruff check axiolex/ --fix

# Run mypy static type checks across the axiolex package.
type-check:
	mypy axiolex/

# Quick script to generate sample documents for manual testing.
example:
	python -c "from axiolex.core.config import load_config; from axiolex.core.retriever import Document; import yaml; config = load_config('settings.yaml'); docs = [Document(id='doc1', title='Test Document', content='This is a test document for BM25S retrieval.', keywords=['test', 'document'])]; print('Example documents loaded')"
