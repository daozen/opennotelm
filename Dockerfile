FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
COPY tools/npm_notices.mjs /build/tools/npm_notices.mjs
RUN node /build/tools/npm_notices.mjs /build/frontend /build/frontend/dist/third-party

FROM ghcr.io/astral-sh/uv:0.12.6 AS uv
FROM python:3.12-slim-trixie AS xml-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config zlib1g-dev && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
RUN uv pip install --system setuptools==80.9.0 wheel==0.45.1
COPY uv.lock ./
COPY tools/native_xml_sources.json tools/fetch_xml_sources.py tools/build_xml_wheel.sh ./tools/
RUN bash tools/build_xml_wheel.sh

FROM xml-builder AS audio-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends libmp3lame-dev && rm -rf /var/lib/apt/lists/*
COPY tools/native_audio_source.json tools/fetch_audio_source.py tools/build_audio_runtime.sh ./tools/
RUN bash tools/build_audio_runtime.sh

FROM python:3.12-slim-trixie AS runtime
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data FRONTEND_DIR=/app/frontend/dist UV_CACHE_DIR=/tmp/uv-cache PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
COPY pyproject.toml uv.lock ./
COPY README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY docs/DEPENDENCIES.json docs/THIRD_PARTY_NOTICES.zh-CN.md ./docs/
RUN uv sync --locked --no-dev --no-install-project && .venv/bin/playwright install --with-deps chromium \
    && apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto-core libmp3lame0 \
    && apt-get purge -y xvfb xserver-common && python -m pip uninstall -y pip \
    && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home app \
    && mkdir -p /app/data && chown -R app:app /app/data
COPY --from=audio-builder /build/audio/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=audio-builder /build/audio/licenses/ /app/licenses/native-audio/
COPY tools/check_audio_runtime.py ./tools/
RUN .venv/bin/python tools/check_audio_runtime.py
COPY backend/ ./backend/
RUN uv sync --locked --no-dev
COPY tools/debian_security_packages.json tools/install_debian_security.py ./tools/
RUN python tools/install_debian_security.py
# These administrative/terminal tools are not part of the application runtime.
RUN rm -f /usr/bin/mount /usr/bin/umount /usr/bin/nsenter /usr/bin/infocmp
COPY --from=xml-builder /build/licenses/ /app/licenses/native-xml/
COPY tools/check_xml_runtime.py ./tools/
RUN --mount=type=bind,from=xml-builder,source=/build/wheels,target=/tmp/xml-wheels \
    uv pip install --python .venv/bin/python --no-deps --reinstall /tmp/xml-wheels/*.whl \
    && .venv/bin/python tools/check_xml_runtime.py
COPY tools/python_notices.py tools/browser_notices.py ./tools/
COPY tools/probe_security_runtime.py tools/container_runtime_review.json ./tools/
RUN .venv/bin/python tools/python_notices.py --output /app/licenses/python
RUN .venv/bin/python tools/browser_notices.py --output /app/licenses/browser
RUN rm -rf /tmp/uv-cache
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/api/health')"]
CMD ["/app/.venv/bin/uvicorn", "opennotelm.main:app", "--host", "0.0.0.0", "--port", "3000", "--no-access-log"]
