#!/usr/bin/env bash
# Estado rápido del entorno Docker local (desde la raíz del repo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Falta $ENV_FILE — copia .env.example y completa DB_PASSWORD y DEMO_PASSWORD."
  exit 1
fi

echo "=== Colima / Docker ==="
if command -v colima >/dev/null 2>&1; then
  colima status 2>&1 | head -3 || true
else
  echo "(colima no instalado; usa Docker Desktop u otro motor)"
fi

echo
echo "=== Git ==="
git log -1 --oneline
git status -sb

echo
echo "=== Contenedores ==="
docker compose --env-file "$ENV_FILE" ps

echo
echo "=== HTTP ==="
for url in \
  "http://localhost:8000/catalogo/" \
  "http://localhost:8000/salud/" \
  "http://localhost:3000/"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null || echo "err")
  printf "  %-42s %s\n" "$url" "$code"
done

echo
echo "=== URLs ==="
echo "  Portal:  http://localhost:8000/catalogo/"
echo "  CRM:     http://localhost:8000/crm/"
echo "  Flota:   http://localhost:8000/flota/"
echo "  Grafana: http://localhost:3000"
echo "  Demo:    contraseña en DEMO_PASSWORD de $ENV_FILE (p. ej. ana@correo.test, admin@cofrial.cl)"
echo
echo "Logs en vivo:  ./scripts/logs-local.sh"
