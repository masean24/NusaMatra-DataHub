# =============================================================================
# Nusa Matra Data Hub — Dockerfile
# Optimized for Coolify & Container Deployments
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, database migrations, data fixtures, and seed scripts
COPY app/ app/
COPY data/ data/
COPY migrations/ migrations/
COPY scripts/ scripts/

# The DEMO database is deterministic and can be baked into the image. The LIVE
# database must live on a persistent volume: rebuilding it on every image would
# destroy historical snapshots and break pinned Evidence Passport links.
RUN rm -f data/nusa_matra_demo.db data/nusa_matra_live.db data/telemetry.db data/telemetry.db-wal data/telemetry.db-shm
RUN python data/seed_db.py
RUN chmod +x scripts/entrypoint.sh

# Expose default port (Coolify detects this automatically for port mapping)
EXPOSE 8000

# Container healthcheck for Coolify / Docker orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/api/v1/health')" || exit 1

# Seed LIVE when the persistent volume is empty or its active snapshot predates
# the current SSGI 2024 / education 2025 series, then retire restricted
# indicators (idempotent) before serving traffic.
CMD ["sh", "scripts/entrypoint.sh"]
