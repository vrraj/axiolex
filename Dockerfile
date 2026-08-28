# Axiolex server container
#
# Builds a self-contained image that runs the Axiolex API + MCP servers.
# Redis is NOT included in this image — it is provided externally
# (docker-compose, managed Redis, etc.) and reached via AXIOLEX_REDIS_HOST.
#
# The same image can be used standalone with any Redis instance:
#   docker run -p 9700:9700 -e AXIOLEX_REDIS_HOST=redis.example.com axiolex

# ---------- Stage 1: build dependencies ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed by some wheels (PyStemmer, cryptography, onnxruntime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY axiolex/ ./axiolex/

# Build wheels for the package and all server+colbert dependencies.
# Wheels are installed into /wheels so we can copy them to the runtime stage
# and install them with pip without needing build-essential there.
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir=/wheels \
    ".[server,colbert]"


# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Axiolex"
LABEL org.opencontainers.image.description="Axiolex tool discovery and retrieval server"
LABEL org.opencontainers.image.source="https://github.com/vrraj/axiolex"

# Runtime dependencies for PyStemmer, ONNX Runtime, and general operation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install pre-built wheels (no compiler needed at this stage)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy the application source (needed for UI templates, static assets,
# shipped source_files, and entry-point scripts)
COPY pyproject.toml README.md settings.yaml ./
COPY axiolex/ ./axiolex/
COPY source_files/ ./source_files/

# Create directory for audit logs and ColBERT model cache
RUN mkdir -p /app/logs /app/models

# Default configuration — all overridable by environment variables
ENV AXIOLEX_REDIS_HOST=redis \
    AXIOLEX_REDIS_PORT=6379 \
    AXIOLEX_REDIS_DB=0 \
    AXIOLEX_TOP_K=7 \
    AXIOLEX_HYBRID_ENABLED=false \
    AXIOLEX_LOG_DIR=/app/logs \
    AXIOLEX_COLBERT_CACHE_DIR=/app/models \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 9700

# Health check: hit the /status endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9700/status', timeout=3)" || exit 1

# Refresh the Redis catalog on startup, then launch the API server.
# The MCP server can be run as a separate container with the same image
# using: axiolex-mcp-server --transport streamable-http --host 0.0.0.0 --port 9701
WORKDIR /app
CMD ["sh", "-c", "axiolex-index refresh --allow-partial && axiolex-server --config settings.yaml --host 0.0.0.0 --port 9700"]
