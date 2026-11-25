# syntax=docker/dockerfile:1
# CreatorHub (PT-BR) em container: Chrome real + Xvfb (tela virtual) + noVNC.
# O navegador roda COM janela (headed) dentro de um display virtual — nada abre
# na tela do host. Painel e noVNC saem por um unico Caddy com senha.
FROM caddy:2 AS caddy

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    TZ=America/Sao_Paulo \
    DISPLAY=:99 \
    SCREEN_GEOMETRY=1600x1000x24 \
    CREATORHUB_CONFIG_PATH=/app/data/config.yaml \
    CREATORHUB_LOG_DIR=/app/data/logs \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify openbox supervisor \
        fonts-liberation fonts-noto-color-emoji \
        tzdata ca-certificates curl procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy

WORKDIR /app

# Dependencias Python primeiro (cache de camada).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Chrome estavel real: o app prefere channel="chrome" e so cai no Chromium
# embutido se nao achar. --with-deps instala as libs de sistema.
RUN python -m patchright install --with-deps chrome \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY custom ./custom
COPY scripts ./scripts
COPY config.example.yaml ./config.example.yaml
COPY deploy ./deploy
RUN sed -i 's/\r$//' deploy/* && chmod +x deploy/*.sh

# Politica do Chrome: sem pedido de notificacao/Tradutor/gerenciador de senhas por cima do Facebook
# (no fluxo de publicacao em Paginas eles atrapalhavam o clique no compositor).
RUN mkdir -p /etc/opt/chrome/policies/managed \
    && cp deploy/chrome-policy.json /etc/opt/chrome/policies/managed/creatorhub.json

# Usuario sem privilegio (uid 1000). O entrypoint sobe como root so para
# acertar a posse do volume (Railway monta volumes como root) e entao rebaixa.
RUN useradd --uid 1000 --create-home --shell /bin/bash app \
    && mkdir -p /app/data \
    && chown -R app:app /app /home/app

# Gera o overlay PT-BR no build (ensure_dist tambem regenera no start se preciso).
RUN python scripts/build_ptbr.py && chown -R app:app /app/custom

VOLUME ["/app/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
