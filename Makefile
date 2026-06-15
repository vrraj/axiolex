# Axiolex local development Makefile

.PHONY: install dev run run-server mcp-run redis-start redis-stop redis-status index-refresh index-status test build clean

REDIS_CONTAINER ?= axiolex-redis
REDIS_HOST ?= localhost
REDIS_PORT ?= 6380
REDIS_DB ?= 0
TOOLS_FILE ?= source_files/tools_list.yaml
PROVIDERS_FILE ?= source_files/mcp_providers.yaml
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

# Start Redis, build the complete local catalog, then run both Axiolex servers.
run: redis-start index-refresh
	$(MAKE) -j2 run-server mcp-run

run-server:
	$(PYTHON) -m axiolex.cli --config settings.yaml

# Run the MCP tool discovery server
mcp-run:
	$(PYTHON) -m axiolex.mcp.server --host 0.0.0.0 --port 9701

# Start the dedicated local Axiolex Redis container.
redis-start:
	@docker start $(REDIS_CONTAINER) 2>/dev/null || docker run -d --name $(REDIS_CONTAINER) -p $(REDIS_PORT):6379 redis:7

redis-stop:
	docker stop $(REDIS_CONTAINER)

redis-status:
	@docker ps -a --filter name=$(REDIS_CONTAINER) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Rebuild the externally managed Redis tool catalog
index-refresh:
	$(PYTHON) -m axiolex.index_cli refresh

index-status:
	$(PYTHON) -m axiolex.index_cli status

# Run with custom port
run-port:
	$(PYTHON) -m axiolex.cli --config settings.yaml --port 8080

# Run with auto-reload (development)
dev-run:
	$(PYTHON) -m axiolex.cli --config settings.yaml --reload

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v

# Run tests with coverage
test-cov:
	$(PYTHON) -m pytest tests/ --cov=axiolex --cov-report=html

# Build package
build:
	$(PYTHON) -m build

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Format code
format:
	black axiolex/
	ruff check axiolex/ --fix

# Type check
type-check:
	mypy axiolex/

# Create example documents
example:
	python -c "from axiolex.core.config import load_config; from axiolex.core.retriever import Document; import yaml; config = load_config('settings.yaml'); docs = [Document(id='doc1', title='Test Document', content='This is a test document for BM25S retrieval.', keywords=['test', 'document'])]; print('Example documents loaded')"
