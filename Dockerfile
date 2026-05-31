# ─── Backend (FastAPI + worker) Docker image ──────────────────────────
# Multi-stage build. Stage 1 installs Python deps into an isolated venv.
# Stage 2 is a slim runtime that copies the venv + source.
#
# Used for BOTH the web service (uvicorn) and the worker service
# (apscheduler), differentiated by Railway's per-service `startCommand` in
# railway.toml — no need for a separate worker Dockerfile.
#
# Build:    docker build -t summit-backend .
# Run web:  docker run -p 8000:8000 summit-backend
# Run wkr:  docker run summit-backend python -m sma.worker.main

FROM python:3.11-slim AS builder

# System deps needed by some Python wheels (cryptography, psycopg) + the
# image+video pipeline (ffmpeg + libs).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Copy only what's needed for dep resolution first (better Docker cache hit rate).
# README.md is required because pyproject.toml's `readme = "README.md"` field
# makes hatchling validate the file at metadata-generation time.
COPY pyproject.toml README.md ./
COPY src/sma/__init__.py src/sma/__init__.py

RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install .

# ─── Runtime stage ────────────────────────────────────────────────────

FROM python:3.11-slim AS runtime

# ffmpeg is needed at runtime for the video assembler.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq5 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Pre-create writable directories so the app (running as non-root) can write
# data files even when no external volume is mounted.
RUN mkdir -p /app/data/usage /app/data/posts_db /app/logs && \
    chown -R app:app /app

COPY --from=builder /venv /venv
COPY --chown=app:app src ./src
COPY --chown=app:app templates ./templates
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app examples ./examples
COPY --chown=app:app assets ./assets
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# NOTE: we deliberately do NOT `USER app` here. The entrypoint starts as root
# so it can chown the runtime-mounted volume, then drops to `app` itself.
EXPOSE 8000

# The entrypoint fixes volume ownership then runs the command as the app user.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default = web service. The worker service overrides this with its start command.
CMD ["alembic upgrade head && uvicorn sma.web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
