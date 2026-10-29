# Image der PWA mit Caddy (ADR 0010). Build-Kontext ist frontend/:
#   docker build -t judo-portal-web frontend
# Caddy liefert die PWA aus und leitet /api ans Backend und /auth an Keycloak weiter.
# Nur HTTP auf :8080, TLS macht der vorgelagerte Reverse Proxy.

FROM node:24.22.2-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2.11.7-alpine
LABEL org.opencontainers.image.title="judo-portal-web" \
      org.opencontainers.image.description="WTSV Judo Portal – PWA mit Caddy"
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/frontend/browser /srv
# Caddy schreibt Zustand nach XDG_DATA_HOME/XDG_CONFIG_HOME (/data, /config), die gehören dem Laufzeitnutzer.
RUN addgroup -S -g 10001 portal && adduser -S -u 10001 -G portal -H portal \
    && chown -R portal:portal /data /config
USER 10001
EXPOSE 8080
