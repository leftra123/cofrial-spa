#!/usr/bin/env bash
# Prueba SIN tocar AWS de aws/activar.sh: ejecuta el script contra un `aws`, un `curl` y un `pbpaste` falsos, y un provision.sh de mentira que solo anota
# que se le llamó. Comprueba el flujo (credenciales, encender, espera, verificación) y que nunca se pierdan ni se impriman las credenciales.
# No valida la semántica real de AWS: eso solo lo hace una sesión de laboratorio.
#   bash aws/test_activar.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/st" "$TMP/home/.aws" "$TMP/estado"
fallo() { echo "FALLA: $*"; exit 1; }

# aws falso: las credenciales «buenas» son las que traen aws_session_token=bueno; «runserver» imita el rol de la terminal del laboratorio.
cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env bash
A="$*"; F="${AWS_SHARED_CREDENTIALS_FILE:-/nada}"; ST="$AWS_ST"
tok() { grep -h '^aws_session_token' "$F" 2>/dev/null | head -1 | sed 's/.*= *//'; }
case "$A" in
  "sts get-caller-identity"*) case "$(tok)" in bueno) echo "arn:aws:sts::1:assumed-role/LabRole/u";; runserver) echo "arn:aws:sts::1:assumed-role/runserver/u";; *) exit 255;; esac;;
  "ec2 describe-vpcs"*) [ "$(tok)" = bueno ] && echo vpc-1 || exit 255;;
  "elbv2 describe-target-groups"*) echo arn:tg;;
  "elbv2 describe-target-health"*) cat "$ST/targets";;
  "elbv2 describe-load-balancers"*) echo alb.example.elb.amazonaws.com;;
  "ec2 describe-instances"*"InstanceId"*) printf 'i-web\ti-webb\ti-iot\n';;     # la CLI real separa con tabuladores
  "ec2 describe-instances"*) printf 'cofrial-ec2-web\trunning\t1.1.1.1\ncofrial-ec2-iot\trunning\t3.3.3.3\n';;
  "cloudwatch describe-alarms"*"--state-value ALARM"*) cat "$ST/en-alarma" 2>/dev/null || true;;
  "cloudwatch describe-alarms"*) cat "$ST/alarmas-ids";;
  *) echo "aws falso: no sé qué hacer con: $A" >&2; exit 99;;
esac
FAKE
cat > "$TMP/bin/curl" <<'FAKE'
#!/usr/bin/env bash
for a in "$@"; do u="$a"; done
if [ -f "$AWS_ST/curl-falla" ] && echo "$u" | grep -q "$(cat "$AWS_ST/curl-falla")"; then echo -n 500; else echo -n 200; fi
FAKE
cat > "$TMP/bin/pbpaste" <<'FAKE'
#!/usr/bin/env bash
echo llamado >> "$AWS_ST/pb-llamado"; cat "$PB_ARCHIVO"
FAKE
cat > "$TMP/provision.sh" <<'FAKE'
#!/usr/bin/env bash
echo "provision $*" >> "$AWS_ST/provision.log"; exit "${PROV_RC:-0}"
FAKE
chmod +x "$TMP/bin/"* "$TMP/provision.sh"

BUENAS=$'[default]\naws_access_key_id=AKIAFALSA\naws_secret_access_key=SECRETO-NO-IMPRIMIR\naws_session_token=bueno\n'
MALAS=$'[default]\naws_access_key_id=AKIAVIEJA\naws_secret_access_key=SECRETO-VIEJO\naws_session_token=malo\n'
reset() {
  rm -f "$TMP/st/"* "$TMP/home/.aws/"*; echo "healthy healthy" > "$TMP/st/targets"; printf 'i-web\ti-webb\ti-iot\n' > "$TMP/st/alarmas-ids"
  printf '%s' "$1" > "$TMP/cred"; chmod 600 "$TMP/cred"
}
correr() {  # correr [opciones]: guarda la salida en $SAL y el código en $RC
  set +e
  SAL="$(env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN PATH="$TMP/bin:$PATH" HOME="$TMP/home" AWS_ST="$TMP/st" AWS_SHARED_CREDENTIALS_FILE="$TMP/cred" \
    PROVISION="$TMP/provision.sh" COFRIAL_ESTADO="$TMP/estado" DOMINIO_HTTPS=www.cofrial.test ESPERA_SEG=0 INTERVALO=0 PB_ARCHIVO="$TMP/portapapeles" \
    bash "$AQUI/activar.sh" "$@" 2>&1 </dev/null)"; RC=$?
  set -e
}
sin_secretos() { echo "$SAL" | grep -q "SECRETO" && fallo "$1: la salida imprimió una clave"; return 0; }

# 1) credenciales vigentes y todo sano: no pega nada, enciende, verifica y sale 0
reset "$BUENAS"; correr
[ "$RC" = 0 ] || fallo "1: con todo sano debía salir 0 y salió $RC: $SAL"
[ ! -f "$TMP/st/pb-llamado" ] || fallo "1: no debía leer el portapapeles con credenciales vigentes"
grep -q "provision encender" "$TMP/st/provision.log" || fallo "1: debía llamar a provision.sh encender"
echo "$SAL" | grep -q "LISTO" || fallo "1: faltó el LISTO: $SAL"; sin_secretos 1
echo "$SAL" | grep -q "las alarmas de CPU apuntan a las instancias vivas" || fallo "1: con alarmas al día no debía avisar de alarmas huérfanas: $SAL"
echo "ok: credenciales vigentes -> no pide pegar, enciende y verifica"

# 2) credenciales vencidas + bloque bueno en el portapapeles: lo guarda (0600), conserva las anteriores y sigue
reset "$MALAS"; printf '%s' "$BUENAS" > "$TMP/portapapeles"; correr
[ "$RC" = 0 ] || fallo "2: debía salir 0 con el bloque bueno y salió $RC: $SAL"
grep -q "aws_session_token=bueno" "$TMP/cred" || fallo "2: no guardó las credenciales nuevas"
[ -f "$TMP/cred.antes" ] && grep -q SECRETO-VIEJO "$TMP/cred.antes" || fallo "2: no dejó copia de las anteriores"
[ "$(stat -f %Lp "$TMP/cred" 2>/dev/null || stat -c %a "$TMP/cred")" = 600 ] || fallo "2: las credenciales no quedaron con permiso 600"
grep -q "provision encender" "$TMP/st/provision.log" || fallo "2: no encendió tras pegar"; sin_secretos 2
echo "ok: credenciales vencidas -> las pega, valida, guarda con 600 y conserva las anteriores"

# 3) bloque incompleto (sin token): rechaza, NO toca las credenciales actuales y no enciende
reset "$MALAS"; printf '[default]\naws_access_key_id=AKIAX\naws_secret_access_key=SECRETO-NO-IMPRIMIR\n' > "$TMP/portapapeles"; correr
[ "$RC" != 0 ] || fallo "3: un bloque incompleto debía fallar"
grep -q SECRETO-VIEJO "$TMP/cred" || fallo "3: sobrescribió las credenciales con un bloque incompleto"
[ ! -f "$TMP/st/provision.log" ] || fallo "3: no debía encender sin credenciales válidas"
echo "$SAL" | grep -q "aws_session_token" || fallo "3: no dijo qué clave faltaba"; sin_secretos 3
echo "ok: bloque incompleto -> rechazado, credenciales anteriores intactas, nada se enciende"

# 4) credenciales del rol runserver: rechazadas con explicación
reset "$MALAS"; printf '[default]\naws_access_key_id=AKIAX\naws_secret_access_key=SECRETO-NO-IMPRIMIR\naws_session_token=runserver\n' > "$TMP/portapapeles"; correr
[ "$RC" != 0 ] || fallo "4: el rol runserver debía rechazarse"
echo "$SAL" | grep -q "runserver" || fallo "4: no explicó lo del rol runserver"
grep -q SECRETO-VIEJO "$TMP/cred" || fallo "4: sobrescribió las credenciales con las de runserver"; sin_secretos 4
echo "ok: rol runserver -> rechazado sin tocar nada"

# 5) un bloque sin la línea [default] se acepta (se agrega la cabecera)
reset "$MALAS"; printf 'aws_access_key_id=AKIAX\naws_secret_access_key=SECRETO-NO-IMPRIMIR\naws_session_token=bueno\n' > "$TMP/portapapeles"; correr
[ "$RC" = 0 ] && head -1 "$TMP/cred" | grep -q '^\[default\]' || fallo "5: debía agregar [default] y seguir: $SAL"
echo "ok: bloque sin [default] -> se agrega la cabecera"

# 6) una web no sana tras esperar: sale 1 y lo dice
reset "$BUENAS"; echo "healthy unhealthy" > "$TMP/st/targets"; correr
[ "$RC" = 1 ] || fallo "6: con una web no sana debía salir 1 y salió $RC"
echo "$SAL" | grep -q "FALLA" && echo "$SAL" | grep -q "1 de 2" || fallo "6: no informó 1 de 2 sanas: $SAL"
echo "ok: web no sana -> sale 1 con el detalle"

# 7) el dominio no responde: sale 1
reset "$BUENAS"; echo "cofrial.test/health" > "$TMP/st/curl-falla"; correr
[ "$RC" = 1 ] && echo "$SAL" | grep -q "/health -> 500" || fallo "7: debía fallar con /health -> 500: $SAL"
echo "ok: /health del dominio caído -> sale 1"

# 8) alarmas de CPU atadas a instancias que ya no existen: avisa del comando, no falla
reset "$BUENAS"; printf 'i-vieja1\ti-vieja2\ti-iot\n' > "$TMP/st/alarmas-ids"; correr
[ "$RC" = 0 ] || fallo "8: las alarmas huérfanas solo avisan; salió $RC"
echo "$SAL" | grep -q "2 alarma(s)" && echo "$SAL" | grep -q "endurecer.sh alarmas --aplicar" || fallo "8: no avisó de las alarmas huérfanas: $SAL"
echo "ok: alarmas huérfanas -> avisa cómo reaplicarlas, sin fallar"

# 9) --solo-verificar no enciende nada
reset "$BUENAS"; correr --solo-verificar
[ "$RC" = 0 ] && [ ! -f "$TMP/st/provision.log" ] || fallo "9: --solo-verificar no debía llamar a provision.sh"
echo "ok: --solo-verificar no enciende"

# 10) --pegar fuerza pegar aunque las actuales sirvan
reset "$BUENAS"; printf '%s' "$BUENAS" > "$TMP/portapapeles"; correr --pegar
[ -f "$TMP/st/pb-llamado" ] || fallo "10: --pegar debía leer el portapapeles"
echo "ok: --pegar fuerza leer el portapapeles"

# 11) opción desconocida: sale 2
reset "$BUENAS"; correr --nada
[ "$RC" = 2 ] || fallo "11: una opción desconocida debía salir 2 y salió $RC"
echo "ok: opción desconocida -> código 2"
echo "TODO OK"
