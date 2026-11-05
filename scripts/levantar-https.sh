#!/usr/bin/env bash
# Levanta web + Caddy TLS para probar Mercado Pago en https://localhost:8443
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f certs/local.pem || ! -f certs/local-key.pem ]]; then
  if command -v mkcert >/dev/null 2>&1; then
    "$ROOT/scripts/generar-certs-local.sh"
  else
    echo "Generando certificado autofirmado (acepta la excepción en el navegador o instala mkcert)."
    mkdir -p certs
    openssl req -x509 -newkey rsa:2048 -keyout certs/local-key.pem -out certs/local.pem -days 825 -nodes -subj "/CN=localhost"
  fi
fi

docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build web caddy
echo "Tienda: https://localhost:${HTTPS_PUERTO:-8443}"
