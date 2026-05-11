# =============================================================================
# Multi-stage Dockerfile for the Support Orchestrator service.
#
# Stage 1 (builder): install all deps into a clean /venv from pyproject.toml.
# Stage 2 (runtime): copy the venv + app sources to a slim image, run as a
#                    non-root user, expose 8000, with a HEALTHCHECK that
#                    probes /api/v1/health.
#
# Build:   docker build -t support-orchestrator .
# Run:     docker run --rm -p 8000:8000 --env-file .env support-orchestrator
# Compose: docker compose up --build
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1 — builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build deps for any compiled wheels (pydantic-core, etc.). Removed after pip.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only the metadata first so dependency resolution caches across rebuilds
# when only source code changed.
COPY pyproject.toml README.md ./
COPY app/ ./app/

RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install .

# -----------------------------------------------------------------------------
# Stage 2 — runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH"

# Non-root user for runtime
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /home/app --create-home app

# Copy the prepared venv and source from the builder stage.
COPY --from=builder /venv /venv
COPY --from=builder /build/app /srv/app/app

WORKDIR /srv/app
USER app

EXPOSE 8000

# Probe the service health endpoint; uses Python stdlib (no curl needed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
