# ==============================================================================
# InsightForge — Production Multi-Stage Container Definition
# Unified DuckDB Vectorized Analytics Engine, FastAPI REST API, and Web Client
# Strict Invariant: Runs ONLY on Port 8080 (Port 3000 is strictly prohibited)
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

# Set non-buffering, UTF-8 encoding and port invariants
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8080 \
    DATA_DIR=/app/data \
    PATH=/root/.local/bin:$PATH

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Copy application codebase
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data

# Strict Port Invariant: Port 8080
EXPOSE 8080

# Automated Docker Healthcheck against the live engine
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python healthcheck.py || exit 1

# Start InsightForge unified server
CMD ["python", "server.py"]
