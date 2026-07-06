# Use the official Astral uv image with Python 3.11 pre-installed on Debian Slim
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy python project configuration for caching layers
COPY pyproject.toml uv.lock ./

# Synchronize python dependencies using the buildx uv cache mount for lightning-fast rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy project source and tools
COPY src/ src/
COPY install.py README.md RULEMASTER.md ./

# Download and parse rulebook PDF and secret scripts politely, utilizing buildx mount cache to bypass network bottlenecks
RUN --mount=type=cache,target=/app/build_cache \
    # 1. Retrieve or download Rulebook PDF \
    if [ -f /app/build_cache/Rulebook_20.pdf ]; then \
      echo "✨ [Build Cache] Using cached Rulebook PDF..."; \
      cp /app/build_cache/Rulebook_20.pdf ./Rulebook_20.pdf; \
    else \
      echo "🌐 [Download] Downloading official Rulebook PDF..."; \
      curl -L -o Rulebook_20.pdf "https://awakenrealms.com/images/download/etherfields/ENG/Etherfields_Rulebook_20_280x280mm-PAGES-20.pdf" && \
      cp Rulebook_20.pdf /app/build_cache/Rulebook_20.pdf; \
    fi && \
    \
    # 2. Retrieve cached raw secret scripts if present to bypass polite throttling network delays \
    if [ -f /app/build_cache/secret_scripts_cache.json ]; then \
      echo "✨ [Build Cache] Using cached secret scripts database..."; \
      cp /app/build_cache/secret_scripts_cache.json ./secret_scripts_cache.json; \
    fi && \
    \
    # 3. Regenerate pages & index \
    echo "[Process] Slicing pages and compiling index..." && \
    ETHERFIELDS_LOCAL_DIR=/app uv run python src/rulebook_tool.py --force && \
    \
    # 4. Rebuild secret scripts cache (reads local file if present, otherwise politely downloads shards) \
    echo "[Process] Compiling secret scripts..." && \
    ETHERFIELDS_LOCAL_DIR=/app uv run python src/secret_scripts_tool.py --update-cache && \
    \
    # 5. Persist the generated raw cache back to the mount cache \
    cp secret_scripts_cache.json /app/build_cache/secret_scripts_cache.json

# Configure ETHERFIELDS_LOCAL_DIR to the mount path
ENV ETHERFIELDS_LOCAL_DIR=/app/data
RUN mkdir -p /app/data

# Declare mount volume for logs, topics, and configs
VOLUME ["/app/data"]

# Expose MCP stdio transport by default
ENTRYPOINT ["uv", "run", "python", "src/mcp_server.py"]
