#!/usr/bin/env bash
# Sigue logs de web y un bloque de la flota (50 camiones repartidos en flota-1…5).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env}"
SERVICES="${*:-web flota-1}"
docker compose --env-file "$ENV_FILE" logs -f --tail=50 $SERVICES
