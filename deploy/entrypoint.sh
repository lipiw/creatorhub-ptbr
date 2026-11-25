#!/bin/sh
# Sobe como root apenas para: acertar o volume, limpar locks velhos, gerar o hash
# da senha. Depois rebaixa para o usuario "app" e entrega para o supervisord.
set -eu

DATA=/app/data

if [ -z "${CH_PASSWORD:-}" ]; then
    echo "[creatorhub] ERRO: defina CH_PASSWORD (senha do painel e do noVNC)." >&2
    echo "[creatorhub] O painel nao tem login proprio; sem senha qualquer um com a URL publica nas suas contas." >&2
    exit 1
fi
if [ "${#CH_PASSWORD}" -lt 12 ]; then
    echo "[creatorhub] ERRO: CH_PASSWORD precisa ter pelo menos 12 caracteres." >&2
    exit 1
fi

mkdir -p "$DATA" "$DATA/logs"
# o que o proprio entrypoint (root) cria precisa pertencer ao usuario do app
chown -R 1000:1000 "$DATA/logs"

# Volumes novos (ex.: Railway) chegam como root; corrige so quando a posse esta errada.
if [ "$(stat -c %u "$DATA")" != "1000" ]; then
    echo "[creatorhub] acertando posse de $DATA para uid 1000..."
    chown -R 1000:1000 "$DATA"
fi

# Config persistente no volume (edicoes feitas pelo painel sobrevivem a redeploy).
if [ ! -f "$DATA/config.yaml" ]; then
    cp /app/config.example.yaml "$DATA/config.yaml"
    chown 1000:1000 "$DATA/config.yaml"
    echo "[creatorhub] config.yaml criado a partir do exemplo."
fi

# Restos de um desligamento brusco: lock do Xvfb e Singleton* do Chrome.
# O hostname do container muda a cada recriacao e o Chrome interpretaria o lock
# antigo como "perfil em uso em outra maquina". Nenhum navegador esta rodando agora.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix
if [ -d "$DATA/profiles" ]; then
    find "$DATA/profiles" -maxdepth 4 \( -name SingletonLock -o -name SingletonCookie -o -name SingletonSocket \) -exec rm -f {} + 2>/dev/null || true
fi

export CH_USER="${CH_USER:-admin}"
CH_PASSWORD_HASH="$(caddy hash-password --plaintext "$CH_PASSWORD")"
export CH_PASSWORD_HASH
unset CH_PASSWORD

echo "[creatorhub] painel: porta ${PORT:-8080} | usuario: $CH_USER | noVNC em /vnc"
# supervisord fica como root so para poder escrever os logs em /dev/stdout;
# cada programa (Xvfb, Chrome, app, Caddy) roda como "app" via user= no .conf.
exec env HOME=/home/app supervisord -n -c /app/deploy/supervisord.conf
