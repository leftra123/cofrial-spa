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
#   bash aws/activar.sh --clave-unica    # además pone UNA clave simple, igual para todos los usuarios activos (la pide sin mostrarla)
#   bash aws/activar.sh --sin-clave-unica # no pregunta por la clave única (para correrlo sin terminal)
#   bash aws/activar.sh --abrir-ssh      # permite abrir el puerto 22 solo para tu IP mientras se pone la clave única (se cierra al terminar)
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
PEGAR=0; SOLO_VERIFICAR=0; CLAVE_UNICA=0; PREGUNTAR_CLAVE=1; ABRIR_SSH=0
for a in "$@"; do
  case "$a" in
    --pegar) PEGAR=1;;
    --solo-verificar) SOLO_VERIFICAR=1;;
    --clave-unica) CLAVE_UNICA=1;;
    --sin-clave-unica) PREGUNTAR_CLAVE=0;;
    --abrir-ssh) ABRIR_SSH=1;;
    -h|--help) sed -n '2,19p' "$0"; exit 0;;
    *) echo "Opción desconocida: $a (usa --pegar, --solo-verificar, --clave-unica, --sin-clave-unica, --abrir-ssh o --help)"; exit 2;;
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

# ---------------------------------------------------------------- clave única para todos los usuarios activos (opcional)
# Misma clave simple en todas las cuentas activas, para no perder claves entre stacks y copias de secretos.env. La clave viaja por la entrada
# estándar de ssh hasta `manage.py cambiar_clave_demo --clave-stdin`: nunca queda en un argumento, en el entorno ni en el historial.
# Ojo: es una clave débil y compartida, incluso en las cuentas del equipo y de administración de un sitio público. Solo para esta demostración.
SG_ABIERTO=""; CIDR_ABIERTO=""
cerrar_ssh_abierto() {
  [ -n "$SG_ABIERTO" ] || return 0
  aws ec2 revoke-security-group-ingress --group-id "$SG_ABIERTO" --protocol tcp --port 22 --cidr "$CIDR_ABIERTO" >/dev/null 2>&1 \
    && echo "  Puerto 22 cerrado otra vez para $CIDR_ABIERTO." || echo "  AVISO: no pude cerrar el puerto 22 para $CIDR_ABIERTO: revísalo en el grupo ${P}-sg-web."
  SG_ABIERTO=""
}
trap cerrar_ssh_abierto EXIT

poner_clave_unica() {
  local c1="" c2="" key id_web ip_web clavehost kh mi_ip sg r i alcanza=0 salida rc
  if [ -t 0 ]; then
    read -r -s -p "  Clave simple para TODOS los usuarios activos (mínimo 4 caracteres, sin espacios; no se muestra): " c1; echo
    read -r -s -p "  Repítela: " c2; echo
    [ "$c1" = "$c2" ] || { echo "  No coinciden: no se cambió nada."; return 1; }
  else
    IFS= read -r c1 || true      # sin terminal (pruebas, automatización): una línea por la entrada estándar
  fi
  if [ "${#c1}" -lt 4 ] || [[ "$c1" =~ [[:space:]] ]]; then echo "  La clave debe tener al menos 4 caracteres y ningún espacio: no se cambió nada."; return 1; fi
  key="${COFRIAL_ESTADO:-}/cofrial-key.pem"
  [ -f "$key" ] || { echo "  No encuentro la llave SSH ($key). Define COFRIAL_ESTADO con la carpeta de estado vigente."; return 1; }
  read -r id_web ip_web < <(aws ec2 describe-instances --filters "Name=tag:Name,Values=${P}-ec2-web" "Name=instance-state-name,Values=running" \
      --query 'Reservations[0].Instances[0].[InstanceId,PublicIpAddress]' --output text 2>/dev/null || echo "None None")
  { [ -n "${ip_web:-}" ] && [ "$ip_web" != None ]; } || { echo "  La web A no está encendida: no puedo conectarme."; return 1; }
  # La huella de la máquina sale de la consola de EC2 (AWS la imprime al crearla): se verifica de verdad, sin desactivar la comprobación.
  clavehost="$(aws ec2 get-console-output --instance-id "$id_web" --latest --query Output --output text 2>/dev/null | grep -E '^ssh-ed25519 ' | head -1 | awk '{print $1" "$2}' || true)"
  [ -n "$clavehost" ] || { echo "  AWS no me dio la huella de la máquina; no me conecto sin verificarla."; return 1; }
  kh="$(mktemp)"; echo "$ip_web $clavehost" > "$kh"
  local OPT=(-i "$key" -o ConnectTimeout=10 -o BatchMode=yes -o UserKnownHostsFile="$kh" -o StrictHostKeyChecking=yes -o LogLevel=ERROR)
  if ssh "${OPT[@]}" "ubuntu@$ip_web" true </dev/null 2>/dev/null; then alcanza=1; else
    mi_ip="$(curl -s -m 8 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]')"
    sg="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${P}-sg-web" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)"
    echo "  El puerto 22 de la web no responde desde tu IP (${mi_ip:-desconocida}): la lista de IPs permitidas no la incluye."
    r=""
    if [ "$ABRIR_SSH" = 1 ]; then r=s
    elif [ -t 0 ]; then read -r -p "  ¿Abrir el puerto 22 de ${P}-sg-web solo para ${mi_ip:-tu IP}/32 mientras dure este paso (se cierra al terminar)? [s/N] " r; fi
    if [ "$r" = s ] || [ "$r" = S ]; then
      if [ -z "$mi_ip" ] || [ "$sg" = None ]; then echo "  No pude saber tu IP o el grupo de seguridad."; rm -f "$kh"; return 1; fi
      aws ec2 authorize-security-group-ingress --group-id "$sg" --protocol tcp --port 22 --cidr "$mi_ip/32" >/dev/null 2>&1 || true
      SG_ABIERTO="$sg"; CIDR_ABIERTO="$mi_ip/32"; echo "  Puerto 22 abierto para $CIDR_ABIERTO."
      for i in 1 2 3 4; do sleep "${INTERVALO_SSH:-4}"; if ssh "${OPT[@]}" "ubuntu@$ip_web" true </dev/null 2>/dev/null; then alcanza=1; break; fi; done
    else
      echo "  Para abrirlo tú: aws ec2 authorize-security-group-ingress --group-id ${sg} --protocol tcp --port 22 --cidr ${mi_ip:-TU_IP}/32   (y ciérralo después con revoke-security-group-ingress), o repite con --abrir-ssh."
    fi
  fi
  [ "$alcanza" = 1 ] || { echo "  No pude conectarme por SSH: no se cambió ninguna clave."; rm -f "$kh"; cerrar_ssh_abierto; return 1; }
  set +e
  salida="$(printf '%s\n' "$c1" | ssh "${OPT[@]}" "ubuntu@$ip_web" 'cd /opt/cofrial && sudo docker compose -f aws/docker-compose.web.yml --env-file .env exec -T web python manage.py cambiar_clave_demo --clave-stdin --todos-los-activos --permitir-clave-debil' 2>&1)"; rc=$?
  set -e
  rm -f "$kh"; cerrar_ssh_abierto
  echo "$salida" | sed 's/^/  /'
  [ "$rc" = 0 ] || { echo "  El comando falló (código $rc): puede que no se haya cambiado ninguna clave."; return 1; }
  return 0
}

if [ "$PROBLEMAS" = 0 ]; then
  QUIERE=0
  if [ "$CLAVE_UNICA" = 1 ]; then QUIERE=1
  elif [ "$PREGUNTAR_CLAVE" = 1 ] && [ "$SOLO_VERIFICAR" = 0 ] && [ -t 0 ]; then
    echo; read -r -p "¿Poner una clave simple, igual para todos los usuarios activos? [s/N] " r_cu || true
    if [ "${r_cu:-}" = s ] || [ "${r_cu:-}" = S ]; then QUIERE=1; fi
  fi
  if [ "$QUIERE" = 1 ]; then
    log "Clave única para todos los usuarios activos"
    if poner_clave_unica; then ok "la misma clave quedó en todos los usuarios activos (se prueba entrando al sitio con ella)"; else mal "no se pudo poner la clave única"; fi
  fi
fi

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
