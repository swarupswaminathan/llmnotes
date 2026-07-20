# Python app image — secrets are injected at runtime, never baked in.
FROM python:3.11-slim

WORKDIR /app

# uv for reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install deps first (better layer cache when only source changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application source (.env is excluded via .dockerignore)
COPY . .

# Pass secrets with: docker run --env-file .env ...
# Or: docker run -e AZURE_API_KEY=... -e AZURE_OPENAI_ENDPOINT=...
CMD ["python", "main.py", "--help"]
