# RestfulTTS: Kokoro TTS over REST, MCP and a web UI (CPU only)
FROM docker.io/library/python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project
COPY src ./src
RUN uv sync --locked

FROM docker.io/library/python:3.12-slim
RUN useradd --system --uid 1000 --home-dir /data restfultts \
    && mkdir -p /data && chown restfultts /data
COPY --from=build /app /app
ENV PATH=/app/.venv/bin:$PATH \
    HF_HOME=/data/hf \
    RESTFULTTS_DATA_DIR=/data \
    RESTFULTTS_HOST=0.0.0.0 \
    RESTFULTTS_PORT=8000 \
    RESTFULTTS_PRELOAD=de,en,fr,it
USER restfultts
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/static/app.css'); sys.exit(0)"
CMD ["restfultts", "serve"]
