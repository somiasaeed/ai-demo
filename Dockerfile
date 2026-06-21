# ── Stage 1: build dependencies ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy dependency manifests first (leverages Docker layer cache)
COPY pyproject.toml uv.lock ./

# Install into a venv — use copy mode so symlinks work across Docker stages
RUN uv sync --frozen --no-dev --no-install-project --link-mode copy

# ── Stage 2: production image ───────────────────────────────────────────────
FROM python:3.13-slim

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed venv from builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code (samples/photos are runtime-mounted, not baked in — keeps PII out of the image)
COPY hub/ hub/

# Create writable output directory
RUN mkdir -p output && chown appuser:appuser output

# Run as non-root user
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "-m", "uvicorn", "hub.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
