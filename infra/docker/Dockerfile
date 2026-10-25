# Keeper: one image, one process (FastAPI serves the built frontend). Build from the repository root:
#   docker build -f infra/docker/Dockerfile -t keeper .
FROM node:22.11-bookworm-slim AS web
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm ci --prefix frontend --no-audit --no-fund
COPY frontend frontend
COPY .env.example ./
RUN npm run --prefix frontend build

FROM python:3.12.7-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KEEPER_RUNTIME_DIR=/var/lib/keeper APP_HOST=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 keeper
WORKDIR /app
COPY backend/requirements.lock backend/pyproject.toml backend/sandbox-requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.lock
COPY backend backend
RUN pip install --no-cache-dir --no-deps -e backend \
    && pip download --no-cache-dir -r backend/sandbox-requirements.txt -d /opt/keeper/wheels/python-pytest
COPY config config
COPY data data
COPY LICENSE ./
COPY --from=web /src/frontend/dist frontend/dist
COPY infra/docker/entrypoint.sh /usr/local/bin/keeper-entrypoint
RUN mkdir -p /var/lib/keeper && chown -R keeper /var/lib/keeper && chmod +x /usr/local/bin/keeper-entrypoint
USER keeper
EXPOSE 8430
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"APP_PORT\",\"8430\")}/api/v1/health', timeout=4)"
ENTRYPOINT ["keeper-entrypoint"]
