# ---------- Builder stage ----------
FROM python:3.12-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching
# (this layer only rebuilds when pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev

# ---------- Runtime stage ----------
FROM python:3.12-slim

WORKDIR /app

# cairosvg renders certificates through libcairo, and needs a real font on disk
# to draw the text with
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy the fully-built app (venv + source) from the builder stage
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Run migrations, then start the API.

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]