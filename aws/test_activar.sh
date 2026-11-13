#!/usr/bin/env bash
# Prueba SIN tocar AWS de aws/activar.sh: ejecuta el script contra un `aws`, un `curl` y un `pbpaste` falsos, y un provision.sh de mentira que solo anota
# que se le llamó. Comprueba el flujo (credenciales, encender, espera, verificación) y que nunca se pierdan ni se impriman las credenciales.
# No valida la semántica real de AWS: eso solo lo hace una sesión de laboratorio.
#   bash aws/test_activar.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/st" "$TMP/home/.aws" "$TMP/estado"
: > "$TMP/estado/cofrial-key.pem"      # la llave SSH (falsa) que busca --clave-unica
fallo() { echo "FALLA: $*"; exit 1; }

# aws falso: las credenciales «buenas» son las que traen aws_session_token=bueno; «runserver» imita el rol de la terminal del laboratorio.
cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env bash
A="$*"; F="${AWS_SHARED_CREDENTIALS_FILE:-/nada}"; ST="$AWS_ST"
tok() { grep -h '^aws_session_token' "$F" 2>/dev/null | head -1 | sed 's/.*= *//'; }
case "$A" in
  "ec2 describe-instances"*"Values=cofrial-ec2-web "*"Instances[0].[InstanceId"*) printf 'i-web\t1.1.1.1\n';;
  "ec2 get-console-output"*) if [ -f "$ST/sin-huella" ]; then echo "(sin huella)"; else printf 'x\nssh-ed25519 AAAAFAKE root@ip\n'; fi;;
  "ec2 describe-security-groups"*) echo sg-web;;
  "ec2 authorize-security-group-ingress"*) touch "$ST/ssh-abierto"; echo "$A" >> "$ST/sg-llamadas";;
  "ec2 revoke-security-group-ingress"*) echo "$A" >> "$ST/sg-llamadas";;
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
cat > "$TMP/bin/ssh" <<'FAKE'
#!/usr/bin/env bash
# ssh falso: anota los argumentos y la entrada estándar; «true» es la prueba de conexión; el comando real imprime lo que imprimiría cambiar_clave_demo.
echo "$*" >> "$AWS_ST/ssh-args"
for a in "$@"; do case "$a" in UserKnownHostsFile=*) cp "${a#UserKnownHostsFile=}" "$AWS_ST/known_hosts" 2>/dev/null || true;; esac; done
ultimo="${@: -1}"
restar() { f="$AWS_ST/$1"; n=$(cat "$f" 2>/dev/null || echo 0); [ "$n" -gt 0 ] || return 1; echo $((n-1)) > "$f"; return 0; }
if [ "$ultimo" = true ]; then
  if restar ssh-fallos-true; then echo "ssh: connect to host: Operation timed out" >&2; exit 255; fi
  if [ -f "$AWS_ST/ssh-bloqueado" ] && [ ! -f "$AWS_ST/ssh-abierto" ]; then echo "ssh: connect to host: Operation timed out" >&2; exit 255; fi
  exit 0
fi
if restar ssh-fallos-real; then echo "ssh: connect to host: Operation timed out" >&2; exit 255; fi
cat > "$AWS_ST/ssh-stdin"
echo "La misma clave quedó en 3 usuario(s) activo(s), 2 de ellos del equipo o administración."
FAKE
cat > "$TMP/bin/curl" <<'FAKE'
#!/usr/bin/env bash
for a in "$@"; do u="$a"; done
case "$u" in *checkip*) echo -n 203.0.113.9; exit 0;; esac
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
cat > "$TMP/reaplicar.sh" <<'FAKE'
#!/usr/bin/env bash
echo "reaplicar $*" >> "$AWS_ST/reaplicar.log"; echo "cofrial-ec2-web-cpu: reapuntada de i-vieja a i-nueva."
FAKE
chmod +x "$TMP/bin/"* "$TMP/provision.sh" "$TMP/reaplicar.sh"
export INTERVALO_SSH=0      # sin esperas entre reintentos de ssh

BUENAS=$'[default]\naws_access_key_id=AKIAFALSA\naws_secret_access_key=SECRETO-NO-IMPRIMIR\naws_session_token=bueno\n'
MALAS=$'[default]\naws_access_key_id=AKIAVIEJA\naws_secret_access_key=SECRETO-VIEJO\naws_session_token=malo\n'
reset() {
  rm -f "$TMP/st/"* "$TMP/home/.aws/"*; echo "healthy healthy" > "$TMP/st/targets"; printf 'i-web\ti-webb\ti-iot\n' > "$TMP/st/alarmas-ids"
  printf '%s' "$1" > "$TMP/cred"; chmod 600 "$TMP/cred"
}
correr() {  # correr [opciones]: guarda la salida en $SAL y el código en $RC (la entrada estándar es $ENTRADA, vacía por defecto)
  set +e
  SAL="$(env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN PATH="$TMP/bin:$PATH" HOME="$TMP/home" AWS_ST="$TMP/st" AWS_SHARED_CREDENTIALS_FILE="$TMP/cred" \
    PROVISION="$TMP/provision.sh" REAPLICAR_ALARMAS="$TMP/reaplicar.sh" COFRIAL_ESTADO="$TMP/estado" DOMINIO_HTTPS=www.cofrial.test ESPERA_SEG=0 INTERVALO=0 PB_ARCHIVO="$TMP/portapapeles" \
    bash "$AQUI/activar.sh" "$@" 2>&1 <<< "${ENTRADA-}")"; RC=$?
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
echo "$SAL" | grep -q "2 alarma(s)" && echo "$SAL" | grep -q "reaplicar-alarmas-cpu.sh --aplicar" || fallo "8: no avisó de las alarmas huérfanas: $SAL"
[ ! -f "$TMP/st/reaplicar.log" ] || fallo "8: sin consentimiento no debía reapuntar las alarmas"
echo "ok: alarmas huérfanas -> avisa cómo reapuntarlas y no toca nada sin consentimiento"

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
# 12) --clave-unica: la clave viaja por la entrada estándar de ssh, con la huella verificada, y no se imprime ni queda en argumentos
reset "$BUENAS"; ENTRADA="clave-simple-77" correr --clave-unica
[ "$RC" = 0 ] || fallo "12: --clave-unica debía salir 0 y salió $RC: $SAL"
grep -q "clave-simple-77" "$TMP/st/ssh-stdin" || fallo "12: la clave no llegó por la entrada estándar de ssh"
if grep -q "clave-simple-77" "$TMP/st/ssh-args"; then fallo "12: la clave apareció en los argumentos de ssh"; fi
if echo "$SAL" | grep -q "clave-simple-77"; then fallo "12: la clave se imprimió en la salida"; fi
grep -q "ssh-ed25519 AAAAFAKE" "$TMP/st/known_hosts" && grep -q "^1.1.1.1 " "$TMP/st/known_hosts" || fallo "12: no se usó la huella de la consola de EC2 para esa IP"
grep -q "StrictHostKeyChecking=yes" "$TMP/st/ssh-args" || fallo "12: la comprobación de la huella debía quedar activa"
grep -q -- "--todos-los-activos" "$TMP/st/ssh-args" && grep -q -- "--clave-stdin" "$TMP/st/ssh-args" || fallo "12: el comando remoto no usó --clave-stdin --todos-los-activos"
echo "$SAL" | grep -q "la misma clave quedó en todos los usuarios activos" || fallo "12: faltó el resultado: $SAL"
echo "ok: --clave-unica -> clave por stdin de ssh, huella verificada, sin imprimirla ni dejarla en argumentos"

# 13) clave demasiado corta: no se conecta a nada
reset "$BUENAS"; ENTRADA="abc" correr --clave-unica
[ "$RC" = 1 ] && [ ! -f "$TMP/st/ssh-args" ] && echo "$SAL" | grep -q "al menos 4 caracteres" || fallo "13: una clave corta debía rechazarse sin llamar a ssh: $RC $SAL"
echo "ok: clave corta -> rechazada antes de conectarse"

# 14) sin la huella de la máquina no se conecta (no hay alternativa insegura)
reset "$BUENAS"; touch "$TMP/st/sin-huella"; ENTRADA="clave-simple-77" correr --clave-unica
[ "$RC" = 1 ] && [ ! -f "$TMP/st/ssh-args" ] && echo "$SAL" | grep -q "sin verificarla" || fallo "14: sin huella debía negarse a conectar: $RC $SAL"
echo "ok: sin huella verificable -> no se conecta"

# 15) puerto 22 cerrado para tu IP sin --abrir-ssh: avisa el comando, no toca la seguridad ni envía la clave
reset "$BUENAS"; touch "$TMP/st/ssh-bloqueado"; ENTRADA="clave-simple-77" correr --clave-unica
[ "$RC" = 1 ] || fallo "15: con el 22 cerrado debía salir 1 y salió $RC"
[ ! -f "$TMP/st/sg-llamadas" ] || fallo "15: no debía tocar el grupo de seguridad sin consentimiento"
[ ! -f "$TMP/st/ssh-stdin" ] || fallo "15: no debía enviar la clave si no hay conexión"
echo "$SAL" | grep -q "authorize-security-group-ingress" && echo "$SAL" | grep -q "203.0.113.9/32" || fallo "15: faltó el comando para abrir el puerto a mano: $SAL"
echo "ok: 22 cerrado -> explica cómo abrirlo, sin tocar la seguridad ni enviar la clave"

# 16) con --abrir-ssh: abre solo tu IP, usa la conexión y lo cierra al terminar
reset "$BUENAS"; touch "$TMP/st/ssh-bloqueado"; ENTRADA="clave-simple-77" INTERVALO_SSH=0 correr --clave-unica --abrir-ssh
[ "$RC" = 0 ] || fallo "16: debía salir 0 y salió $RC: $SAL"
grep -q "authorize-security-group-ingress --group-id sg-web --protocol tcp --port 22 --cidr 203.0.113.9/32" "$TMP/st/sg-llamadas" || fallo "16: no abrió el 22 solo para la IP"
grep -q "revoke-security-group-ingress --group-id sg-web --protocol tcp --port 22 --cidr 203.0.113.9/32" "$TMP/st/sg-llamadas" || fallo "16: no cerró el 22 al terminar"
grep -q "clave-simple-77" "$TMP/st/ssh-stdin" || fallo "16: la clave no llegó"
echo "ok: --abrir-ssh -> abre solo tu IP, cambia la clave y vuelve a cerrar"

# 17) sin la opción y sin terminal no pregunta ni cambia ninguna clave
reset "$BUENAS"; correr
[ "$RC" = 0 ] && [ ! -f "$TMP/st/ssh-args" ] || fallo "17: por defecto no debía conectarse a nada"
echo "ok: sin --clave-unica y sin terminal no toca ninguna clave"
# 18) --arreglar-alarmas: reapunta con el script, solo con consentimiento explícito
reset "$BUENAS"; printf 'i-vieja1\ti-vieja2\ti-iot\n' > "$TMP/st/alarmas-ids"; correr --arreglar-alarmas
[ "$RC" = 0 ] || fallo "18: debía salir 0 y salió $RC: $SAL"
grep -q "reaplicar --aplicar" "$TMP/st/reaplicar.log" || fallo "18: debía llamar al script de alarmas con --aplicar"
echo "$SAL" | grep -q "alarmas de CPU reapuntadas" || fallo "18: faltó el resultado: $SAL"
echo "ok: --arreglar-alarmas -> reapunta las alarmas desfasadas"

# 19) la conexión ssh es intermitente (la IP de salida cambia): se reintenta sin abrir el puerto 22 ni tocar la seguridad
reset "$BUENAS"; echo 2 > "$TMP/st/ssh-fallos-true"; ENTRADA="clave-simple-77" correr --clave-unica
[ "$RC" = 0 ] || fallo "19: con fallos intermitentes de conexión debía salir 0 y salió $RC: $SAL"
[ ! -f "$TMP/st/sg-llamadas" ] || fallo "19: un fallo intermitente no justifica abrir el puerto 22"
grep -q "clave-simple-77" "$TMP/st/ssh-stdin" || fallo "19: la clave no llegó tras los reintentos"
echo "ok: conexión intermitente -> reintenta y no abre el puerto 22"

# 20) el comando real pierde la conexión una vez: se reintenta y la clave se envía por la conexión que sí abrió
reset "$BUENAS"; echo 1 > "$TMP/st/ssh-fallos-real"; ENTRADA="clave-simple-77" correr --clave-unica
[ "$RC" = 0 ] || fallo "20: debía salir 0 tras reintentar y salió $RC: $SAL"
echo "$SAL" | grep -q "La conexión falló (intento 1 de" || fallo "20: no avisó del reintento: $SAL"
[ "$(grep -c 'cambiar_clave_demo' "$TMP/st/ssh-args")" = 2 ] || fallo "20: debía intentar el comando dos veces"
grep -q "clave-simple-77" "$TMP/st/ssh-stdin" && ! grep -q "clave-simple-77" "$TMP/st/ssh-args" && ! echo "$SAL" | grep -q "clave-simple-77" || fallo "20: la clave solo debe ir por stdin"
echo "ok: el comando real se reintenta y la clave nunca va en argumentos ni en la salida"
echo "TODO OK"
