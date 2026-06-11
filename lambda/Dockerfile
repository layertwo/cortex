FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY src/ src/
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "python", "-m", "src.entrypoint.container"]
