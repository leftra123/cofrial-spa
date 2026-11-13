#!/usr/bin/env bash
# Prueba SIN tocar AWS de la alta disponibilidad de provision.sh: ejecuta el script completo contra un `aws` falso con estado (recuerda lo que
# se crea) y comprueba que arma el balanceador en dos zonas, las dos web (primaria y secundaria), RDS Multi-AZ y el rodaje de `recrear-web`.
# No valida la semántica real de AWS (eso solo lo hace una corrida en el laboratorio), pero atrapa errores de flujo, variables y orden.
#   bash aws/test_provision_ha.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/st" "$TMP/aws"; cp "$AQUI/provision.sh" "$TMP/aws/provision.sh"
LOG="$TMP/llamadas.log"; : > "$LOG"

cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env bash
A="$*"; echo "$A" >> "$AWS_LOG"; ST="$AWS_ST"
nombre() { echo "$A" | sed -n "s/.*Values=\\(cofrial-[a-z0-9-]*\\).*/\\1/p" | head -1; }
tag() { echo "$A" | sed -n 's/.*Key=Name,Value=\([^] ,}]*\).*/\1/p' | head -1; }
case "$A" in
  "sts get-caller-identity"*) echo "arn:aws:sts::1:assumed-role/LabRole/x";;
  "ec2 describe-vpcs"*) [ -f "$ST/cofrial-vpc" ] && cat "$ST/cofrial-vpc" || echo None;;
  "ec2 create-vpc"*) echo vpc-1;;
  "ec2 create-tags"*) id=$(echo "$A" | sed -n 's/.*--resources \([^ ]*\).*/\1/p'); n=$(echo "$A" | sed -n 's/.*Value=\([^ ]*\)$/\1/p'); echo "$id" > "$ST/$n";;
  "ec2 describe-availability-zones"*"[0]"*) echo us-east-1a;;
  "ec2 describe-availability-zones"*"[1]"*) echo us-east-1b;;
  "ec2 describe-subnets"*|"ec2 describe-route-tables"*|"ec2 describe-internet-gateways --filters Name=tag"*) n=$(nombre); [ -f "$ST/$n" ] && cat "$ST/$n" || echo None;;
  "ec2 describe-internet-gateways"*) [ -f "$ST/cofrial-igw" ] && cat "$ST/cofrial-igw" || echo None;;
  "ec2 create-subnet"*) echo "subnet-$RANDOM";;
  "ec2 create-internet-gateway"*) echo igw-1;;
  "ec2 create-route-table"*) echo rtb-1;;
  "ec2 describe-security-groups --group-ids"*) cat "$ST/web-abierta" 2>/dev/null || echo 0;;
  "ec2 describe-security-groups"*) n=$(echo "$A" | sed -n 's/.*group-name,Values=\([^ ]*\).*/\1/p'); [ -f "$ST/$n" ] && cat "$ST/$n" || echo None;;
  "ec2 create-security-group"*) n=$(echo "$A" | sed -n 's/.*--group-name \([^ ]*\).*/\1/p'); echo "sg-$n";;
  "ssm get-parameter"*|"ec2 describe-images"*) echo ami-1;;
  "ec2 create-key-pair"*) echo KEYMATERIAL;;
  "ec2 describe-addresses"*) echo None;;
  "ec2 describe-instances"*"--instance-ids"*) echo 1.2.3.4;;
  "ec2 describe-instances"*) n=$(nombre); [ -f "$ST/inst-$n" ] && cat "$ST/inst-$n" || echo None;;
  "ec2 run-instances"*) n=$(tag); id="i-$n-$RANDOM"; echo "$id" > "$ST/inst-$n"; echo "$id"; echo "$A" | grep -o 'file://[^ ]*' >> "$ST/userdatas";;
  "ec2 terminate-instances"*) rm -f "$ST"/inst-"$(echo "$A" | sed -n 's/.*--instance-ids i-\(cofrial-ec2-[a-z]*\(-b\)\?\).*/\1/p')" 2>/dev/null; id=$(echo "$A" | sed -n 's/.*--instance-ids \([^ ]*\).*/\1/p'); for f in "$ST"/inst-*; do [ "$(cat "$f")" = "$id" ] && rm -f "$f"; done;;
  "rds describe-db-instances"*"MultiAZ"*"SecondaryAvailabilityZone"*) echo "True us-east-1a us-east-1b";;
  "rds describe-db-instances"*"SecondaryAvailabilityZone"*) echo us-east-1b;;
  "rds describe-db-instances"*"MultiAZ"*) cat "$ST/rds-maz" 2>/dev/null || echo False;;
  "rds describe-db-instances"*"Endpoint"*) echo db.test.rds.amazonaws.com;;
  "rds describe-db-instances"*) [ -f "$ST/rds" ] || exit 255; echo available;;
  "rds create-db-instance"*) touch "$ST/rds"; case "$A" in *--no-multi-az*) echo False > "$ST/rds-maz";; *--multi-az*) echo True > "$ST/rds-maz";; esac;;
  "rds modify-db-instance"*) echo True > "$ST/rds-maz";;
  "rds describe-db-subnet-groups"*) exit 255;;
  "elbv2 describe-load-balancers --names"*) [ -f "$ST/alb" ] || exit 255; echo arn:alb;;
  "elbv2 describe-load-balancers"*) echo cofrial-alb-123.us-east-1.elb.amazonaws.com;;
  "elbv2 create-load-balancer"*) touch "$ST/alb"; echo arn:alb;;
  "elbv2 describe-target-groups"*) [ -f "$ST/tg" ] || exit 255; echo arn:tg;;
  "elbv2 create-target-group"*) touch "$ST/tg"; echo arn:tg;;
  "elbv2 describe-listeners"*) p=$(echo "$A" | grep -o 'Port==`[0-9]*`' | grep -o '[0-9]*'); [ -f "$ST/L$p" ] && echo arn:l$p || echo None;;
  "elbv2 create-listener"*) p=$(echo "$A" | sed -n 's/.*--port \([0-9]*\).*/\1/p'); touch "$ST/L$p";;
  "elbv2 describe-target-health"*"Target.Id"*) cat "$ST/destinos" 2>/dev/null || true;;
  "elbv2 describe-target-health"*) echo healthy;;
  "elbv2 register-targets"*) echo "$A" | grep -o 'Id=[^ ]*' | sed 's/Id=//' | tr '\n' ' ' > "$ST/destinos";;
  "acm import-certificate"*) echo arn:aws:acm:us-east-1:1:certificate/abc;;
  "acm describe-certificate"*) exit 0;;
esac
exit 0
FAKE
chmod +x "$TMP/bin/aws"
export AWS_LOG="$LOG" AWS_ST="$TMP/st" PATH="$TMP/bin:$PATH" MI_IP=1.1.1.1 DOMINIO_HTTPS=cofrialspa.webhop.me
fallo() { echo "FALLO: $1"; echo "--- últimas llamadas:"; tail -25 "$LOG"; exit 1; }
corre() { ( cd "$TMP/aws" && bash provision.sh "$@" ) > "$TMP/salida.txt" 2>&1 || { cat "$TMP/salida.txt"; fallo "provision.sh $* terminó con error"; }; }

# 1) instalación nueva
corre
grep -q "rds create-db-instance.* --multi-az" "$LOG" || fallo "RDS no se creó Multi-AZ"
grep -q "elbv2 create-load-balancer.*--subnets subnet-[0-9]* subnet-[0-9]*" "$LOG" || fallo "el ALB no recibió dos subredes"
grep -q "elbv2 create-target-group.*--health-check-path /health " "$LOG" || fallo "el grupo de destino no chequea /health"
grep -q "rds create-db-instance.*--backup-retention-period 7 --copy-tags-to-snapshot --deletion-protection" "$LOG" || fallo "la RDS nueva no nace con respaldos de 7 días, copia de etiquetas y protección contra borrado"
grep -q "rds create-db-instance.*--no-publicly-accessible" "$LOG" || fallo "la RDS nueva sería pública"
grep -q "elbv2 create-listener.*--port 80" "$LOG" && grep -q "elbv2 create-listener.*--port 443" "$LOG" || fallo "faltan los listeners 80 y 443"
grep -q "authorize-security-group-ingress --group-id sg-cofrial-sg-web --protocol tcp --port 80 --source-group sg-cofrial-sg-alb" "$LOG" || fallo "sg-web no abre el 80 solo al ALB"
grep -q "authorize-security-group-ingress --group-id sg-cofrial-sg-web --protocol tcp --port 80 --cidr 0.0.0.0/0" "$LOG" && fallo "sg-web quedó abierto al mundo"
[ "$(grep -c 'ec2 run-instances' "$LOG")" = 3 ] || fallo "debían lanzarse 3 EC2 (web A, web B, IoT)"
UD_A="$TMP/aws/.estado/userdata-web.sh"; UD_B="$TMP/aws/.estado/userdata-web-b.sh"
[ -f "$UD_A" ] && [ -f "$UD_B" ] || fallo "faltan los user-data de las dos web"
grep -q "^ROL_WEB=primario" "$UD_A" && grep -q "^ROL_WEB=secundario" "$UD_B" || fallo "los roles de las web no son primario/secundario"
grep -q "^DJANGO_CONFIAR_PROXY=1" "$UD_B" || fallo "falta DJANGO_CONFIAR_PROXY=1"
grep -q "^DJANGO_CSRF_ORIGINS=https://cofrialspa.webhop.me,http://cofrialspa.webhop.me,http://cofrial-alb-123.us-east-1.elb.amazonaws.com,https://cofrial-alb-123.us-east-1.elb.amazonaws.com" "$UD_A" || fallo "orígenes CSRF incorrectos: $(grep CSRF "$UD_A")"
grep -q "^DJANGO_HTTPS=0" "$UD_A" || fallo "con certificado autofirmado no debe activarse HSTS (DJANGO_HTTPS=1)"
grep -q "aviso de certificado" "$TMP/salida.txt" || fallo "el resumen no avisa del certificado autofirmado"
[ "$(cat "$TMP/aws/.estado/ip.txt")" = "cofrial-alb-123.us-east-1.elb.amazonaws.com" ] || fallo "ip.txt debe contener el DNS del ALB"
echo "ok: instalación nueva = ALB en 2 zonas, 2 web (primaria/secundaria), RDS Multi-AZ, sg-web solo desde el ALB, orígenes CSRF y HTTPS sin HSTS con certificado autofirmado"

# 2) segunda corrida: idempotente (no crea nada de nuevo)
: > "$LOG"; corre
grep -Eq "run-instances|create-load-balancer|create-db-instance|create-target-group|create-listener" "$LOG" && fallo "la segunda corrida volvió a crear recursos"
echo "ok: segunda corrida idempotente"

# 3) recrear-web rodante: termina A, espera, termina B
: > "$LOG"; corre recrear-web
N_TERM=$(grep -c "terminate-instances" "$LOG"); [ "$N_TERM" = 2 ] || fallo "recrear-web debía terminar 2 instancias (A y luego B), terminó $N_TERM"
[ "$(grep -c 'ec2 run-instances' "$LOG")" = 2 ] || fallo "recrear-web debía lanzar 2 web nuevas"
POS_A=$(grep -n "terminate-instances" "$LOG" | sed -n 1p | cut -d: -f1); POS_SANA=$(grep -n "describe-target-health.*Id=i-cofrial-ec2-web-" "$LOG" | sed -n 1p | cut -d: -f1)
POS_B=$(grep -n "terminate-instances" "$LOG" | sed -n 2p | cut -d: -f1)
[ "$POS_A" -lt "$POS_B" ] || fallo "orden de terminación incorrecto"
awk -v a="$POS_A" -v b="$POS_B" 'NR>a && NR<b && /describe-target-health.*--targets Id=/ {f=1} END{exit !f}' "$LOG" || fallo "no esperó a que la web A estuviera sana antes de terminar la B"
grep -q "rds create-db-instance\|modify-db-instance" "$LOG" && fallo "recrear-web tocó la RDS"
echo "ok: recrear-web es rodante (A, espera de salud, luego B) y no toca RDS"

# 4) RDS existente en una sola zona se convierte a Multi-AZ sin recrearla
echo False > "$TMP/st/rds-maz"; : > "$LOG"; corre
grep -q "rds modify-db-instance.*--multi-az --apply-immediately" "$LOG" || fallo "no convirtió la RDS existente a Multi-AZ"
grep -q "create-db-instance" "$LOG" && fallo "recreó la RDS en vez de modificarla"
echo "ok: RDS Single-AZ existente se modifica a Multi-AZ (sin recrear)"

# 5) cerrar-acceso-directo y subcomandos documentados
: > "$LOG"; corre cerrar-acceso-directo
grep -q "revoke-security-group-ingress.*--port 80 --cidr 0.0.0.0/0" "$LOG" && grep -q "revoke-security-group-ingress.*--port 443 --cidr 0.0.0.0/0" "$LOG" || fallo "cerrar-acceso-directo no revoca 80 y 443"
grep -q "bash aws/provision.sh cerrar-acceso-directo" "$AQUI/provision.sh" || fallo "cerrar-acceso-directo no está documentado"
echo "ok: cerrar-acceso-directo revoca 80 y 443 abiertos al mundo"

# 6) modo HTTPS de Django: solo con certificado de confianza y las web cerradas al acceso directo
: > "$LOG"; CERT_ARN=arn:aws:acm:us-east-1:1:certificate/confiable corre recrear-web
grep -q "^DJANGO_HTTPS=1" "$UD_A" && grep -q "^DJANGO_HSTS_SEG=86400" "$UD_B" || fallo "con certificado de confianza y web cerradas debía activarse DJANGO_HTTPS=1 con HSTS de un día: $(grep -E 'DJANGO_HTTPS=|HSTS' "$UD_A" | tr '\n' ' ')"
grep -q "^DJANGO_CSP=1" "$UD_A" || fallo "falta DJANGO_CSP en el .env de la web"
echo 1 > "$TMP/st/web-abierta"; : > "$LOG"; CERT_ARN=arn:aws:acm:us-east-1:1:certificate/confiable corre recrear-web
grep -q "^DJANGO_HTTPS=0" "$UD_A" || fallo "con el 80 de las web abierto a internet no deben activarse las cookies Secure"
grep -q "Django sigue sin cookies Secure" "$TMP/salida.txt" || fallo "no avisó de que el acceso directo impide el modo HTTPS"
echo "ok: cookies Secure y HSTS solo cuando todo llega por HTTPS (certificado de confianza y web cerradas al acceso directo)"

# 7) con la base creada y sin sus claves locales, no se generan claves nuevas
rm "$TMP/aws/.estado/secretos.env"; : > "$LOG"
( cd "$TMP/aws" && bash provision.sh ) > "$TMP/salida.txt" 2>&1 && fallo "debió detenerse: la base existe y faltan sus claves"
grep -q "no tiene las claves de esa instalación" "$TMP/salida.txt" || fallo "no explicó por qué se detuvo"
grep -Eq "run-instances|create-db-instance|terminate-instances" "$LOG" && fallo "tocó recursos pese a faltar las claves"
echo "ok: sin las claves de una base que ya existe, el script se detiene sin tocar nada"
echo "TODO OK"
