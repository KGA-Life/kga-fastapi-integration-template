# syntax=docker/dockerfile:1
# =============================================================================
# kga-fastapi-integration-template — production image
#
# uv-managed FastAPI service. Dependencies are resolved from the committed
# uv.lock (deterministic, --frozen). The app boots without live provider
# credentials; secrets are supplied at runtime via --env-file / -e (never baked
# into the image).
# =============================================================================

# Official uv image with a Python 3.14 runtime already provisioned. The uv
# version is pinned to match `[tool.uv] required-version` in pyproject.toml:
# `uv sync` below reads that pin, so a floating tag would eventually ship a uv
# that fails the required-version check and break the image build (KGA-143).
# Keep this tag's uv version in lockstep with pyproject.toml. (uv publishes its
# Python-runtime images on Debian trixie for this release line.)
FROM ghcr.io/astral-sh/uv:0.10.11-python3.14-trixie-slim

# uv / Python runtime tuning:
#   UV_COMPILE_BYTECODE  — precompile .pyc at install time for faster cold start
#   UV_LINK_MODE=copy    — copy from the uv cache instead of hardlinking
#                          (hardlinks span filesystems poorly inside images)
#   UV_PYTHON_DOWNLOADS=0 — never fetch a Python; use the one in this base image
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# -----------------------------------------------------------------------------
# 1) Dependency layer. Copy ONLY the manifest + lockfile first so this layer is
#    cached and re-run only when dependencies change — not on every code edit.
#    --no-dev drops pytest/ruff; --no-install-project installs deps only (the
#    app/ package is added in the next layer and imported from the workdir).
# -----------------------------------------------------------------------------
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# -----------------------------------------------------------------------------
# 2) Application code. Changes here invalidate only this cheap layer.
# -----------------------------------------------------------------------------
COPY app ./app

# -----------------------------------------------------------------------------
# Token store. Any provider auth token is written to /data so it survives
# container restarts. /data MUST be a mounted volume (named volume in compose,
# or `-v example_token:/data` with docker run) — otherwise the token lives only
# in the container's writable layer and is lost on `docker rm`.
#
# NOTE: TOKEN_STORE_PATH here overrides the repo default (.tokens/...). If you
# pass an --env-file that also sets TOKEN_STORE_PATH, that value wins — keep it
# pointed at /data (see docker-compose.yml, which pins it explicitly).
# -----------------------------------------------------------------------------
ENV TOKEN_STORE_PATH=/data/example_token.json
RUN mkdir -p /data

# Run unprivileged. Own /data (writable token dir) and /app (holds .venv) so the
# non-root user can write the token file. A fresh named volume mounted at /data
# inherits this ownership on first use.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000

# --no-sync: run in the already-baked .venv without re-resolving at startup
# (no network, deterministic).
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
