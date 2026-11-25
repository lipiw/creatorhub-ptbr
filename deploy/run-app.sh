#!/bin/sh
# Espera o display virtual e sobe o CreatorHub preso ao loopback.
# --no-proxy-headers: o middleware do projeto exige que o PEER seja loopback;
# se o uvicorn confiasse no X-Forwarded-For do Caddy, o IP real do cliente
# (celular, etc.) viraria o peer e tudo daria 403.
set -eu
i=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
    i=$((i + 1))
    [ "$i" -gt 100 ] && { echo "Xvfb nao subiu" >&2; exit 1; }
    sleep 0.2
done
cd /app
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --log-level info
