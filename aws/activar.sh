#!/usr/bin/env bash
# Activa Cofrial al iniciar una sesión NUEVA del Learner Lab: pide las credenciales, enciende la base y las EC2, espera al balanceador y verifica.
#
# Por qué existe: cada sesión del laboratorio (4 horas) termina DETENIENDO (no terminando) las EC2 y la base. Todo lo demás se conserva: red, balanceador,
# IP elástica, certificado, DNS, los destinos del balanceador (las IDs de las instancias no cambian al detener y encender) y las alarmas. Los
# contenedores vuelven solos (restart: unless-stopped). Por eso aquí NO se recrea nada: recrear cambia las IDs y rompe las alarmas.
# Lo único que no se puede automatizar son las credenciales: AWS Academy las crea al pulsar Start Lab y solo se ven en su consola.
#
#   bash aws/activar.sh                  # usa las credenciales actuales si funcionan; si no, pide copiar las nuevas, enciende y verifica
#   bash aws/activar.sh --pegar          # fuerza pegar credenciales nuevas aunque las actuales todavía funcionen
#   bash aws/activar.sh --solo-verificar # no enciende nada: solo revisa cómo está (sirve también a mitad de la sesión)
#
# Variables opcionales: COFRIAL_ESTADO (carpeta .estado vigente), DOMINIO_HTTPS (si no está en secretos.env), ESPERA_SEG (espera máxima al balanceador, 900).
# Es idempotente: con todo ya encendido, solo verifica. No cierra accesos ni toca alarmas; si las alarmas apuntan a instancias que ya no existen, lo avisa.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
P=cofrial
CRED="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"
PROVISION="${PROVISION:-$AQUI/provision.sh}"      # sobrescribible para las pruebas
ESPERA_SEG="${ESPERA_SEG:-900}"; INTERVALO="${INTERVALO:-15}"
PEGAR=0; SOLO_VERIFICAR=0
for a in "$@"; do
  case "$a" in
    --pegar) PEGAR=1;;
    --solo-verificar) SOLO_VERIFICAR=1;;
    -h|--help) sed -n '2,15p' "$0"; exit 0;;
    *) echo "Opción desconocida: $a (usa --pegar, --solo-verificar o --help)"; exit 2;;
  esac
done

log() { printf '\n==> %s\n' "$*"; }
ok() { printf '  ok      %s\n' "$*"; }
mal() { printf '  FALLA   %s\n' "$*"; PROBLEMAS=$((PROBLEMAS+1)); }
nota() { printf '  aviso   %s\n' "$*"; }
PROBLEMAS=0

command -v aws >/dev/null || { echo "Falta la AWS CLI v2."; exit 1; }

# ---------------------------------------------------------------- credenciales
# Funciona de verdad si AWS acepta una consulta de servicio, no solo sts: con el laboratorio terminado sts puede seguir respondiendo.
acceso_ok() { aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text >/dev/null 2>&1; }

pegar_credenciales() {
  command -v pbpaste >/dev/null || { echo "  No hay pbpaste (solo macOS): guarda el bloque [default] en $CRED a mano."; return 1; }
  echo "  1) En AWS Academy abre el Learner Lab y pulsa Start Lab; espera el círculo verde."
  echo "  2) AWS Details > AWS CLI > Show: copia el bloque completo ([default] y las tres claves)."
  if [ -t 0 ]; then read -r -p "  Cuando lo hayas copiado, pulsa Enter: " _ || true; fi
  local tmp; tmp="$(mktemp)"; chmod 600 "$tmp"
  pbpaste | tr -d '\r' > "$tmp"
  local k
  for k in aws_access_key_id aws_secret_access_key aws_session_token; do
    grep -qE "^$k[[:space:]]*=[[:space:]]*[^[:space:]]+" "$tmp" || { rm -f "$tmp"; echo "  Lo copiado no trae $k: copia otra vez el bloque completo desde AWS Details > AWS CLI."; return 1; }
  done
  grep -q '^\[default\]' "$tmp" || { { echo "[default]"; cat "$tmp"; } > "$tmp.n" && mv "$tmp.n" "$tmp"; chmod 600 "$tmp"; }
  # Se prueban ANTES de reemplazar las actuales, y sin que variables de entorno viejas las pisen. Nunca se imprimen los valores.
  local arn
  arn="$(env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u AWS_PROFILE AWS_SHARED_CREDENTIALS_FILE="$tmp" aws sts get-caller-identity --query Arn --output text 2>/dev/null)" \
    || { rm -f "$tmp"; echo "  AWS rechazó esas credenciales (¿de una sesión anterior?). Pulsa Start Lab, espera el círculo verde y copia de nuevo."; return 1; }
  case "$arn" in *assumed-role/runserver/*) rm -f "$tmp"; echo "  Eso son las credenciales del rol 'runserver' de la terminal del laboratorio, que no puede crear ni encender recursos. Copia las de AWS Details > AWS CLI."; return 1;; esac
  mkdir -p "$(dirname "$CRED")"
  if [ -f "$CRED" ]; then cp -p "$CRED" "$CRED.antes"; chmod 600 "$CRED.antes"; fi
  mv "$tmp" "$CRED"; chmod 600 "$CRED"
  # Las variables de entorno tienen prioridad sobre el archivo: se quitan para que valga lo recién guardado.
  unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE
  echo "  Credenciales guardadas en $CRED (las anteriores quedaron en $CRED.antes). Identidad: $arn"
}

log "Credenciales"
if [ "$PEGAR" = 0 ] && acceso_ok; then
  echo "  Las credenciales actuales funcionan: no hace falta pegar otras (usa --pegar para forzarlo)."
else
  for intento in 1 2 3; do
    if pegar_credenciales && acceso_ok; then break; fi
    [ "$intento" = 3 ] && { echo "  No se lograron credenciales válidas tras 3 intentos."; exit 1; }
    echo "  Intento $intento de 3 fallido. Vuelve a copiar el bloque."
    [ -t 0 ] || exit 1      # sin terminal no hay a quién pedirle que copie de nuevo
  done
fi

# ---------------------------------------------------------------- carpeta de estado
# Las claves de la instalación viva (secretos.env, llave SSH, certificado) están en UNA carpeta; con otra, provision.sh generaría claves nuevas.
if [ -z "${COFRIAL_ESTADO:-}" ]; then
  RAIZ="$(git -C "$AQUI" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's#/\.git$##' || true)"
  CAND="$RAIZ/.claude/worktrees/infrastructure-high-availability-bb2676/aws/.estado"
  if [ -f "$AQUI/.estado/secretos.env" ]; then export COFRIAL_ESTADO="$AQUI/.estado"
  elif [ -f "$CAND/secretos.env" ]; then export COFRIAL_ESTADO="$CAND"
  else nota "no encontré la carpeta de estado vigente (secretos.env); defino COFRIAL_ESTADO si hace falta"; fi
fi
[ -n "${COFRIAL_ESTADO:-}" ] && echo "  Estado: $COFRIAL_ESTADO"

# ---------------------------------------------------------------- encender
if [ "$SOLO_VERIFICAR" = 1 ]; then
  log "Solo verificar: no se enciende nada"
else
  log "Encendiendo la base y las EC2 (provision.sh encender; la base tarda varios minutos)"
  set +e; bash "$PROVISION" encender; RC=$?; set -e
  [ "$RC" = 0 ] || nota "provision.sh encender terminó con código $RC; sigo con la verificación para ver qué quedó"
fi

# ---------------------------------------------------------------- esperar al balanceador
log "Esperando a que el balanceador vea sanas las web (hasta $((ESPERA_SEG/60)) minutos)"
TG="$(aws elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo None)"
TOTAL=0; SANOS=0
if [ -z "$TG" ] || [ "$TG" = None ]; then
  mal "no encuentro el grupo de destino ${P}-tg: ¿existe la instalación? (bash aws/provision.sh estado)"
else
  espera=0
  while :; do
    ESTADOS="$(aws elbv2 describe-target-health --target-group-arn "$TG" --query 'TargetHealthDescriptions[].TargetHealth.State' --output text 2>/dev/null || true)"
    TOTAL=0; SANOS=0; for e in $ESTADOS; do TOTAL=$((TOTAL+1)); [ "$e" = healthy ] && SANOS=$((SANOS+1)); done
    [ "$TOTAL" -gt 0 ] && [ "$SANOS" = "$TOTAL" ] && break
    [ "$espera" -ge "$ESPERA_SEG" ] && break
    echo "  sanas $SANOS de $TOTAL..."; sleep "$INTERVALO"; espera=$((espera+INTERVALO))
  done
  if [ "$TOTAL" -ge 2 ] && [ "$SANOS" = "$TOTAL" ]; then ok "balanceador: $SANOS de $TOTAL web sanas"
  elif [ "$TOTAL" -gt 0 ] && [ "$SANOS" = "$TOTAL" ]; then nota "solo hay $TOTAL web en el balanceador (se esperan 2, una por zona): sin alta disponibilidad"
  else mal "balanceador: $SANOS de $TOTAL web sanas tras esperar; mira bash aws/provision.sh estado y los registros de las web (ssh ... docker compose logs web)"; fi
fi

# ---------------------------------------------------------------- verificación desde fuera
log "Verificando desde fuera"
DOM="${DOMINIO_HTTPS:-}"
[ -z "$DOM" ] && [ -n "${COFRIAL_ESTADO:-}" ] && DOM="$({ sed -n 's/^DOMINIO_HTTPS=//p' "$COFRIAL_ESTADO/secretos.env" 2>/dev/null || true; } | tail -1)"
ALB="$(aws elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || echo None)"
codigo() { curl -sLk -m 12 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || echo 000; }
if [ -n "$DOM" ]; then BASE="https://$DOM"; elif [ -n "$ALB" ] && [ "$ALB" != None ]; then BASE="http://$ALB"; nota "sin DOMINIO_HTTPS: verifico por el DNS del balanceador"; else BASE=""; fi
if [ -z "$BASE" ]; then mal "no hay dirección que verificar (ni dominio ni balanceador)"; else
  for ruta in /health /salud/bd/ /; do
    c="$(codigo "$BASE$ruta")"; if [ "$c" = 200 ]; then ok "$BASE$ruta -> 200"; else mal "$BASE$ruta -> $c"; fi
  done
  if [ -n "$DOM" ] && [ "${DOM#www.}" != "$DOM" ]; then
    c="$(codigo "https://${DOM#www.}/")"; if [ "$c" = 200 ]; then ok "https://${DOM#www.}/ (la raíz, por el reenvío de GoDaddy) -> 200"; else nota "https://${DOM#www.}/ -> $c: el reenvío del dominio sin www depende de GoDaddy, no de AWS"; fi
  fi
fi

# ---------------------------------------------------------------- alarmas
log "Alarmas de CloudWatch"
VIVAS="$(aws ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" "Name=instance-state-name,Values=running" --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null || true)"
DE_ALARMAS="$(aws cloudwatch describe-alarms --alarm-name-prefix "$P" --query "MetricAlarms[?Namespace=='AWS/EC2'].Dimensions[0].Value" --output text 2>/dev/null || true)"
VIVAS="$(echo $VIVAS)"      # la CLI separa con tabuladores; con espacios simples el «case» de abajo reconoce cada ID
HUERFANAS=0; for id in $DE_ALARMAS; do case " $VIVAS " in *" $id "*) ;; *) HUERFANAS=$((HUERFANAS+1));; esac; done
if [ "$HUERFANAS" -gt 0 ]; then nota "$HUERFANAS alarma(s) de CPU apuntan a instancias que ya no existen: bash aws/endurecer.sh alarmas --aplicar (pregunta antes de cada comando)"
else ok "las alarmas de CPU apuntan a las instancias vivas"; fi
ALARMADAS="$(aws cloudwatch describe-alarms --alarm-name-prefix "$P" --state-value ALARM --query 'MetricAlarms[].AlarmName' --output text 2>/dev/null || true)"
[ -n "$ALARMADAS" ] && nota "en ALARMA ahora: $ALARMADAS"

# ---------------------------------------------------------------- resumen
log "Máquinas (las IP de la web B y la IoT cambian en cada arranque; solo la web A tiene IP elástica)"
aws ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query "Reservations[].Instances[].[Tags[?Key=='Name']|[0].Value,State.Name,PublicIpAddress]" --output text 2>/dev/null | sort | sed 's/^/  /' || true
echo
if [ "$PROBLEMAS" = 0 ]; then
  echo "LISTO: Cofrial está arriba${DOM:+ en https://$DOM}. La sesión del laboratorio dura 4 horas desde Start Lab: en la sesión siguiente repite esto."
  echo "Prueba completa de la aplicación: python3 aws/verificar.py"
  exit 0
fi
echo "HAY $PROBLEMAS PROBLEMA(S) arriba. Revisa con: bash aws/provision.sh estado"
exit 1
