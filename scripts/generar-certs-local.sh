#!/usr/bin/env bash
# Certificados de confianza local (mkcert) para Caddy + https://localhost:8443
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/certs"
mkdir -p "$CERT_DIR"

if ! command -v mkcert >/dev/null 2>&1; then
  echo "Falta mkcert. En macOS: brew install mkcert nss && mkcert -install"
  exit 1
fi

mkcert -install 2>/dev/null || true
mkcert -cert-file "$CERT_DIR/local.pem" -key-file "$CERT_DIR/local-key.pem" localhost 127.0.0.1 ::1

echo ""
echo "Certificados en $CERT_DIR (ignorados por git)."
echo "Levanta la pila con HTTPS:"
echo "  cd $ROOT"
echo "  docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build web caddy"
echo "Tienda y checkout MP: https://localhost:${HTTPS_PUERTO:-8443}"
