# BM25S Retriever Makefile

.PHONY: install dev run test build clean

# Install package in development mode
install:
	pip install -e .

# Install with development dependencies
dev:
	pip install -e ".[dev]"

# Run the server
run:
	axiolex-server --config settings.yaml

# Run with custom port
run-port:
	axiolex-server --config settings.yaml --port 8080

# Run with auto-reload (development)
dev-run:
	axiolex-server --config settings.yaml --reload

# Run tests
test:
	python -m pytest tests/ -v

# Run tests with coverage
test-cov:
	python -m pytest tests/ --cov=axiolex --cov-report=html

# Build package
build:
	python -m build

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
