# Image des Vereinsportals: ein Container mit App, Anmeldung und SQLite (Datenverzeichnis /data als Volume).

# Frontend: Icons und htmx aus npm kopieren, CSS mit Tailwind und DaisyUI bauen (liest die Templates nach Klassen)
FROM node:26.13.1-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY scripts/vendor.mjs scripts/
# Ganz portal/, damit Tailwind die Templates aller Apps findet (@source in portal/assets/app.css)
COPY portal portal
RUN npm run vendor

FROM python:3.15.2-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY manage.py gunicorn.conf.py docker-entrypoint.sh ./
COPY portal portal
COPY --from=assets /app/portal/static/vendor portal/static/vendor
RUN PORTAL_SECRET_KEY=build PORTAL_DATA_DIR=/tmp/build python manage.py collectstatic --noinput -v0 \
    && rm -rf /tmp/build \
    && useradd --system --uid 10001 --home-dir /data portal \
    && mkdir -p /data && chown portal /data

ARG VERSION=dev
ENV PORTAL_DATA_DIR=/data \
    PORTAL_VERSION=${VERSION}
LABEL org.opencontainers.image.title="judo-portal" \
      org.opencontainers.image.description="Vereinsportal der Judo-Abteilung im Wedeler TSV e.V." \
      org.opencontainers.image.version=${VERSION}
USER 10001
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
ENTRYPOINT ["./docker-entrypoint.sh"]
