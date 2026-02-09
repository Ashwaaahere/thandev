# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (minimal for backend)
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    postgresql-client \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
# Copy requirements first for better caching
COPY requirements.txt .
# Copy local dependencies
COPY thandev_schemas_pkg ./thandev_schemas_pkg

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user first (needed for COPY --chown)
RUN useradd --create-home --shell /bin/bash app

# Copy application code with app user ownership
COPY --chown=app:app . .

# Copy entrypoint script with executable permissions (overwrites the one from COPY . .)
# Use COPY --chmod to set executable permission at build time
COPY --chown=app:app --chmod=755 entrypoint.sh /app/entrypoint.sh

# Copy fix script with executable permissions (included in COPY . . but ensure correct permissions)
COPY --chown=app:app --chmod=755 fix_alembic_version_column.py /app/fix_alembic_version_column.py

# Switch to non-root user
USER app

# Expose port (default 8000, but can be overridden via PORT env var)
EXPOSE 8000

# Health check (uses PORT env var or defaults to 8000)
# Note: Azure Container Apps will use its own health probes, this is for local Docker
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/health || exit 1'

# Start the application via entrypoint script
# Entrypoint handles: DB wait, then uvicorn
# Migrations are handled by Fly.io release_command (see fly.toml)
ENTRYPOINT ["/app/entrypoint.sh"]
