# Multi-stage build; linux/amd64 for the production VM.
# The virtualenv lives in /opt/venv (not /app/.venv) so the dev bind mount of ./backend over /app
# does not hide it (see infra/compose/compose.dev.yml).
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version ./
# --no-default-groups: neither dev tools nor the `ingest` group (PyMuPDF) go into the server image.
RUN uv sync --frozen --no-default-groups --no-install-project
COPY . .
RUN uv sync --frozen --no-default-groups

FROM python:3.14-slim
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /models /run/embedder && chown app:app /models /run/embedder  # embedder volumes start owned by app
WORKDIR /app
COPY --from=build --chown=app:app /opt/venv /opt/venv
COPY --from=build --chown=app:app /app /app
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
