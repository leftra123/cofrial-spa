#!/usr/bin/env bash
# Crea en AWS Academy (Learner Lab) la red, RDS y las dos EC2 de Cofrial, y deja los contenedores arrancando solos.
#
# ESTADO: escrito siguiendo la documentación de la CLI de AWS pero NO ejecutado contra AWS (no hay credenciales en el
# equipo donde se redactó). Ejecútalo paso a paso la primera vez y lee cada mensaje. Es idempotente en lo posible:
# si un recurso con la etiqueta cofrial-* ya existe, lo reutiliza.
#
# Requisitos: AWS CLI v2 con las credenciales del Learner Lab (AWS Details > AWS CLI), openssl y curl.
#   export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...     # las del laboratorio; caducan al cerrarlo
#   export GEMINI_API_KEY=...    # opcional: la clave de la IA (Google AI Studio). Sin ella la IA queda desactivada
#   export MI_IP=...  # opcional: tu IP pública (curl https://checkip.amazonaws.com desde TU computador) para permitir SSH desde ahí;
#                     # si corres el script en la terminal del Learner Lab, sin esto se abriría el SSH solo a la IP del laboratorio
#   bash aws/provision.sh            # crea todo
#   bash aws/provision.sh destruir   # borra todo lo creado (RDS tarda unos minutos)
#   bash aws/provision.sh estado     # muestra si RDS y las EC2 están encendidas
#   bash aws/provision.sh encender   # tras iniciar una sesión nueva del laboratorio: arranca RDS y las EC2
#   bash aws/provision.sh recrear-web  # rota claves de IA: edita aws/.estado/secretos.env y recrea solo la EC2 web
#   bash aws/provision.sh recrear-iot  # recrea solo la EC2 del simulador IoT con el código actual de main (la web y la RDS no se tocan)
#   bash aws/provision.sh cerrar-acceso-directo  # tras apuntar el dominio al balanceador: cierra el 80/443 directo a las EC2 web (solo entra el ALB)
#
# ALTA DISPONIBILIDAD (revisión técnica del 8-nov-2026): Application Load Balancer en dos zonas, DOS EC2 web (una por zona, registradas en el
# grupo de destino del ALB) y RDS Multi-AZ. `recrear-web` es "rodante": recrea una web y espera a que el ALB la dé por sana antes de tocar
# la otra, así el sitio no se corta. Variables opcionales de esta parte:
#   DOMINIO_HTTPS=www.cofrialspa.shop    # nombre público (CN del certificado autofirmado y origen CSRF permitido)
#   CERT_ARN=arn:aws:acm:...             # certificado ya importado en ACM (de confianza). Sin él: aws/.estado/cert.pem + cert.key (+ cert-cadena.pem)
#                                        # se importan; si tampoco están, se genera uno autofirmado (el navegador avisa y el 80 sigue sirviendo)
#   ACTIVAR_HSTS=1                       # con certificado de confianza: cookies seguras y HSTS de un año (irreversible para los navegadores que visiten)
#   RDS_MULTI_AZ=0                       # solo si el laboratorio rechaza Multi-AZ y se decide seguir sin él (el script avisa en voz alta)
#   COFRIAL_ESTADO=/ruta/a/aws/.estado   # carpeta de estado vigente (claves, llave SSH, certificado) cuando no es la de este checkout
#   HSTS_SEG=86400                       # segundos de HSTS cuando Django va en modo HTTPS (un día por defecto; ACTIVAR_HSTS=1 lo deja en un año)
#
# Una instalación que ya existe se endurece con aws/endurecer.sh (protección de la base, respaldos, security groups, chequeo /health y alarmas),
# que muestra cada comando antes de ejecutarlo. Este script deja esas mismas prácticas en las instalaciones nuevas.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
P=cofrial
REPO_URL="${REPO_URL:-https://github.com/leftra123/cofrial-spa.git}"
RAMA="${RAMA:-main}"
ESTADO="${COFRIAL_ESTADO:-$(cd "$(dirname "$0")" && pwd)/.estado}"; mkdir -p "$ESTADO"
log() { printf '\n==> %s\n' "$*"; }
q() { aws "$@" --output text; }

command -v aws >/dev/null || { echo "Falta la AWS CLI v2"; exit 1; }
ARN=$(q sts get-caller-identity --query Arn) || { echo "Credenciales inválidas o caducadas: copia las de AWS Details en el Learner Lab"; exit 1; }
echo "Identidad: $ARN"
case "$ARN" in *assumed-role/runserver/*) echo "Estás con el rol 'runserver' de la terminal del laboratorio, que no puede crear VPC, RDS ni EC2. Exporta las llaves de AWS Details (AWS CLI: Show) para usar LabRole y vuelve a ejecutar."; exit 1;; esac

# ---------------------------------------------------------------- destruir
if [ "${1:-}" = "destruir" ]; then
  log "Borrando recursos ${P}-*"
  LB_ARN=$(aws elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)
  if [ -n "$LB_ARN" ] && [ "$LB_ARN" != "None" ]; then aws elbv2 delete-load-balancer --load-balancer-arn "$LB_ARN"; aws elbv2 wait load-balancers-deleted --load-balancer-arns "$LB_ARN" 2>/dev/null || sleep 60; fi
  TG_ARN=$(aws elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)
  if [ -n "$TG_ARN" ] && [ "$TG_ARN" != "None" ]; then aws elbv2 delete-target-group --target-group-arn "$TG_ARN" || true; fi
  [ -f "$ESTADO/cert-arn.txt" ] && { aws acm delete-certificate --certificate-arn "$(cat "$ESTADO/cert-arn.txt")" 2>/dev/null || true; rm -f "$ESTADO/cert-arn.txt" "$ESTADO/cert-confiable"; }
  for id in $(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" "Name=instance-state-name,Values=pending,running,stopped,stopping" --query 'Reservations[].Instances[].InstanceId'); do aws ec2 terminate-instances --instance-ids "$id" >/dev/null; done
  aws ec2 wait instance-terminated --instance-ids $(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" --query 'Reservations[].Instances[].InstanceId') 2>/dev/null || true
  ALARMAS=$(q cloudwatch describe-alarms --alarm-name-prefix "${P}-" --query 'MetricAlarms[].AlarmName' 2>/dev/null || true)
  [ -n "$ALARMAS" ] && [ "$ALARMAS" != "None" ] && { aws cloudwatch delete-alarms --alarm-names $ALARMAS || true; }
  # La base nace protegida contra borrado: destruir la desprotege a propósito (es el único camino que la borra).
  aws rds modify-db-instance --db-instance-identifier "${P}-db" --no-deletion-protection --apply-immediately >/dev/null 2>&1 || true
  aws rds delete-db-instance --db-instance-identifier "${P}-db" --skip-final-snapshot --delete-automated-backups >/dev/null 2>&1 && aws rds wait db-instance-deleted --db-instance-identifier "${P}-db" || true
  aws rds delete-db-subnet-group --db-subnet-group-name "${P}-subnets" 2>/dev/null || true
  for a in $(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[].AllocationId'); do aws ec2 release-address --allocation-id "$a" || true; done
  VPC=$(q ec2 describe-vpcs --filters "Name=tag:Name,Values=${P}-vpc" --query 'Vpcs[0].VpcId'); if [ "$VPC" != "None" ]; then
    for sg in $(q ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC" --query "SecurityGroups[?GroupName!='default'].GroupId"); do
      aws ec2 revoke-security-group-ingress --group-id "$sg" --ip-permissions "$(aws ec2 describe-security-groups --group-ids "$sg" --query 'SecurityGroups[0].IpPermissions')" >/dev/null 2>&1 || true; done
    for sg in $(q ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC" --query "SecurityGroups[?GroupName!='default'].GroupId"); do aws ec2 delete-security-group --group-id "$sg" || true; done
    for s in $(q ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC" --query 'Subnets[].SubnetId'); do aws ec2 delete-subnet --subnet-id "$s" || true; done
    for rt in $(q ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC" "Name=tag:Name,Values=${P}-rt" --query 'RouteTables[].RouteTableId'); do aws ec2 delete-route-table --route-table-id "$rt" || true; done
    for ig in $(q ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC" --query 'InternetGateways[].InternetGatewayId'); do aws ec2 detach-internet-gateway --internet-gateway-id "$ig" --vpc-id "$VPC"; aws ec2 delete-internet-gateway --internet-gateway-id "$ig"; done
    aws ec2 delete-vpc --vpc-id "$VPC" || true
  fi
  aws ec2 delete-key-pair --key-name "${P}-key" 2>/dev/null || true
  log "Listo. Los archivos de $ESTADO se conservan (puedes borrarlos a mano)."; exit 0
fi

# ---------------------------------------------------------------- estado y encender
# Al terminar la sesión del Learner Lab, AWS detiene las EC2 y RDS. Al iniciar una sesión nueva siguen detenidas: hay que
# encenderlas. `estado` solo muestra cómo están; `encender` arranca RDS y las dos EC2 y espera a que la aplicación responda.
# La IP elástica y los datos se conservan; los contenedores vuelven solos porque tienen reinicio automático.
if [ "${1:-}" = "estado" ] || [ "${1:-}" = "encender" ]; then
  # Con el laboratorio terminado las credenciales aún "existen" pero AWS rechaza todo: se avisa en vez de decir que nada existe.
  if ! aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text >/dev/null 2>&1; then
    echo "AWS rechaza las consultas: la sesión del laboratorio terminó o no está iniciada."
    echo "  1) En AWS Academy abre el Learner Lab y pulsa Start Lab; espera el círculo verde."
    echo "  2) AWS Details > AWS CLI > Show: copia el bloque [default] y guárdalo con:  pbpaste > ~/.aws/credentials"
    echo "  3) Vuelve a ejecutar: bash aws/provision.sh encender"
    exit 1
  fi
  estado_rds() { aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "no existe"; }
  estado_ec2() { q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].State.Name' 2>/dev/null || echo "no existe"; }
  id_ec2() { q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].InstanceId'; }
  # Dirección de la aplicación: el DNS del balanceador; en instalaciones anteriores al ALB, la IP elástica.
  IP_WEB=$(aws elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || echo "")
  if [ -z "$IP_WEB" ] || [ "$IP_WEB" = "None" ]; then IP_WEB=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[0].PublicIp' 2>/dev/null || echo ""); fi
  log "Estado actual"
  echo "  RDS ${P}-db ........ $(estado_rds)  (Multi-AZ, zona principal, zona de respaldo: $(aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].[MultiAZ,AvailabilityZone,SecondaryAvailabilityZone]' --output text 2>/dev/null || echo ?))"
  echo "  EC2 web (zona A) ... $(estado_ec2 ${P}-ec2-web)"; echo "  EC2 web (zona B) ... $(estado_ec2 ${P}-ec2-web-b)"; echo "  EC2 IoT ............ $(estado_ec2 ${P}-ec2-iot)"
  echo "  Aplicación (ALB) ... ${IP_WEB:-desconocida}"
  TG_ARN=$(aws elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)
  if [ -n "$TG_ARN" ] && [ "$TG_ARN" != "None" ]; then aws elbv2 describe-target-health --target-group-arn "$TG_ARN" --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State]' --output text | sed 's/^/    destino del ALB: /'; fi
  if [ "$1" = "encender" ]; then
    log "Encendiendo RDS (la base primero)"
    for i in $(seq 1 40); do ST=$(estado_rds); case "$ST" in stopped) aws rds start-db-instance --db-instance-identifier "${P}-db" >/dev/null && break;; available|starting|backing-up|configuring-enhanced-monitoring) break;; "no existe") echo "RDS no existe: ejecuta bash aws/provision.sh"; exit 1;; *) sleep 15;; esac; done
    aws rds wait db-instance-available --db-instance-identifier "${P}-db"
    log "Encendiendo las EC2"
    IDS_ENCENDER=""
    for n in "${P}-ec2-web" "${P}-ec2-web-b" "${P}-ec2-iot"; do
      for i in $(seq 1 30); do ST=$(estado_ec2 $n); case "$ST" in stopped) aws ec2 start-instances --instance-ids "$(id_ec2 $n)" >/dev/null; break;; running|pending) break;; "no existe"|None) if [ "$n" = "${P}-ec2-web-b" ]; then echo "  (no hay web en la zona B: instalación anterior al balanceador; ejecuta bash aws/provision.sh)"; break; fi; echo "$n no existe: ejecuta bash aws/provision.sh"; exit 1;; *) sleep 10;; esac; done
      ID_N=$(id_ec2 $n 2>/dev/null || echo None); [ -n "$ID_N" ] && [ "$ID_N" != "None" ] && IDS_ENCENDER="$IDS_ENCENDER $ID_N"
    done
    aws ec2 wait instance-running --instance-ids $IDS_ENCENDER
    echo "$IP_WEB" > "$ESTADO/ip.txt"
    log "Esperando a que la aplicación responda en http://$IP_WEB (hasta 10 minutos)"
    # -L -k: con certificado de confianza el 80 del balanceador redirige (301) al 443, y ese certificado es del dominio, no del DNS del balanceador.
    # Sin seguir la redirección este chequeo nunca veía «ok» y daba por caída una aplicación que ya funcionaba.
    for i in $(seq 1 40); do curl -sLk -m 5 "http://$IP_WEB/salud/" | grep -q ok && { echo "  La aplicación responde. Verifica todo con: python3 aws/verificar.py"; exit 0; }; sleep 15; done
    echo "  La aplicación aún no responde; espera unos minutos y repite: bash aws/provision.sh estado"
  fi
  exit 0
fi

# ---------------------------------------------------------------- recrear-web
# Termina la EC2 web y deja que el resto del script cree una nueva con las claves ACTUALES de aws/.estado/secretos.env
# (GEMINI_API_KEY y GROQ_API_KEY). Sirve para rotar claves sin entrar por SSH. RDS, la red, la IP elástica y la EC2 del IoT
# se conservan; la web queda sin servicio unos 8 minutos.
# terminar_ec2 <nombre>: termina SOLO las instancias con esa etiqueta Name (la prueba aws/test_provision.sh la extrae de este archivo)
terminar_ec2() {
  local IDS
  IDS=$(q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopped,stopping" --query 'Reservations[].Instances[].InstanceId')
  if [ -n "$IDS" ] && [ "$IDS" != "None" ]; then aws ec2 terminate-instances --instance-ids $IDS >/dev/null; aws ec2 wait instance-terminated --instance-ids $IDS; fi
}

# cerrar-acceso-directo: instalaciones anteriores al ALB abrían el 80 (y el 443 del Caddy manual) de sg-web a todo internet. Con el dominio
# ya apuntando al balanceador, se cierran: desde entonces a las web solo entra el ALB. Antes de ejecutarlo, comprobar que el dominio abre.
if [ "${1:-}" = "cerrar-acceso-directo" ]; then
  SGW=$(q ec2 describe-security-groups --filters "Name=group-name,Values=${P}-sg-web" --query 'SecurityGroups[0].GroupId')
  for pto in 80 443; do aws ec2 revoke-security-group-ingress --group-id "$SGW" --protocol tcp --port "$pto" --cidr 0.0.0.0/0 >/dev/null 2>&1 && echo "  cerrado: $pto desde 0.0.0.0/0" || echo "  $pto ya estaba cerrado"; done
  echo "Listo: a las EC2 web solo entra el balanceador (la IP elástica vieja ya no abre)."; exit 0
fi

# recrear-web es RODANTE: termina y recrea la web de la zona A; cuando el ALB la da por sana, hace lo mismo con la zona B. Mientras una se
# recrea, la otra sirve (el sitio no se corta). Si la zona B aún no existe, el resto del script la crea junto con la A.
ROLLING_B=0
if [ "${1:-}" = "recrear-web" ]; then
  log "Recreando la web de a una instancia (la otra sigue sirviendo detrás del ALB)"
  B_ANTES=$(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-ec2-web-b" "Name=instance-state-name,Values=pending,running,stopped" --query 'Reservations[0].Instances[0].InstanceId')
  [ "$B_ANTES" != "None" ] && ROLLING_B=1
  terminar_ec2 "${P}-ec2-web"
fi

# ---------------------------------------------------------------- recrear-iot
# Igual que recrear-web pero para la EC2 del simulador IoT: la termina y el resto del script (idempotente) crea una nueva, que construye
# los contenedores de camiones con el código actual de main. NO toca la RDS, la EC2 web ni la IP elástica; la web sigue en servicio y la
# telemetría se corta unos minutos. La IP pública de la EC2 IoT cambia, pero nada depende de ella (la RDS acepta por grupo de seguridad).
if [ "${1:-}" = "recrear-iot" ]; then
  log "Terminando la EC2 IoT para recrearla con el código actual (RDS, web e IP elástica se conservan)"
  terminar_ec2 "${P}-ec2-iot"
fi

# ---------------------------------------------------------------- secretos generados (se guardan solo en aws/.estado)
gen() { openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20; }
# Si la base ya existe en AWS pero aquí no están sus claves, generar otras dejaría a las web nuevas sin conexión a la base: se detiene antes.
if [ ! -f "$ESTADO/secretos.env" ] && aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].DBInstanceStatus' --output text >/dev/null 2>&1; then
  echo "La base ${P}-db ya existe, pero $ESTADO/secretos.env no. Este checkout no tiene las claves de esa instalación."
  echo "Repite el comando con COFRIAL_ESTADO=/ruta/al/aws/.estado vigente (o recupéralas: bash aws/endurecer.sh secretos-bajar --aplicar)."
  exit 1
fi
[ -f "$ESTADO/secretos.env" ] || cat > "$ESTADO/secretos.env" <<S
DB_PASSWORD=$(gen)
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
DEMO_PASSWORD=$(gen)
ADMIN_PASSWORD=$(gen)
GRAFANA_DB_PASSWORD=$(gen)
GRAFANA_PASSWORD=$(gen)
S
chmod 600 "$ESTADO/secretos.env"; . "$ESTADO/secretos.env"
echo "Claves de IA en secretos.env: Gemini=$([ -n "${GEMINI_API_KEY:-}" ] && echo sí || echo NO), Groq=$([ -n "${GROQ_API_KEY:-}" ] && echo sí || echo NO)"
MI_IP="${MI_IP:-$(curl -s https://checkip.amazonaws.com | tr -d '\n')}"; [ -n "$MI_IP" ] || { echo "No pude detectar tu IP pública"; exit 1; }

etiqueta() { aws ec2 create-tags --resources "$1" --tags "Key=Name,Value=$2"; }
buscar() { q ec2 "$1" --filters "Name=tag:Name,Values=$2" "${@:3}"; }

# ---------------------------------------------------------------- red
log "VPC y subredes (región $REGION)"
VPC=$(buscar describe-vpcs "${P}-vpc" --query 'Vpcs[0].VpcId')
if [ "$VPC" = "None" ]; then
  VPC=$(q ec2 create-vpc --cidr-block 10.0.0.0/16 --query Vpc.VpcId); etiqueta "$VPC" "${P}-vpc"
  aws ec2 modify-vpc-attribute --vpc-id "$VPC" --enable-dns-hostnames
fi
AZ_A=$(q ec2 describe-availability-zones --query 'AvailabilityZones[0].ZoneName'); AZ_B=$(q ec2 describe-availability-zones --query 'AvailabilityZones[1].ZoneName')
subred() { local id; id=$(buscar describe-subnets "$1" --query 'Subnets[0].SubnetId'); if [ "$id" = "None" ]; then id=$(q ec2 create-subnet --vpc-id "$VPC" --cidr-block "$2" --availability-zone "$3" --query Subnet.SubnetId); etiqueta "$id" "$1"; fi; echo "$id"; }
PUB=$(subred "${P}-publica" 10.0.1.0/24 "$AZ_A"); aws ec2 modify-subnet-attribute --subnet-id "$PUB" --map-public-ip-on-launch
PUB_B=$(subred "${P}-publica-b" 10.0.4.0/24 "$AZ_B"); aws ec2 modify-subnet-attribute --subnet-id "$PUB_B" --map-public-ip-on-launch   # segunda zona: el ALB exige dos y aquí corre la web B
PRIV_A=$(subred "${P}-privada-a" 10.0.2.0/24 "$AZ_A"); PRIV_B=$(subred "${P}-privada-b" 10.0.3.0/24 "$AZ_B")

IGW=$(q ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC" --query 'InternetGateways[0].InternetGatewayId')
if [ "$IGW" = "None" ]; then IGW=$(q ec2 create-internet-gateway --query InternetGateway.InternetGatewayId); etiqueta "$IGW" "${P}-igw"; aws ec2 attach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"; fi
RT=$(buscar describe-route-tables "${P}-rt" --query 'RouteTables[0].RouteTableId')
if [ "$RT" = "None" ]; then
  RT=$(q ec2 create-route-table --vpc-id "$VPC" --query RouteTable.RouteTableId); etiqueta "$RT" "${P}-rt"
  aws ec2 create-route --route-table-id "$RT" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW" >/dev/null
  aws ec2 associate-route-table --route-table-id "$RT" --subnet-id "$PUB" >/dev/null
fi
aws ec2 associate-route-table --route-table-id "$RT" --subnet-id "$PUB_B" >/dev/null 2>&1 || true   # ya asociada = ignorar

# ---------------------------------------------------------------- Security Groups encadenados
log "Security Groups"
grupo() { local id; id=$(q ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC" "Name=group-name,Values=$1" --query 'SecurityGroups[0].GroupId'); if [ "$id" = "None" ]; then id=$(q ec2 create-security-group --group-name "$1" --description "$2" --vpc-id "$VPC" --query GroupId); etiqueta "$id" "$1"; fi; echo "$id"; }
regla() { aws ec2 authorize-security-group-ingress --group-id "$1" "${@:2}" >/dev/null 2>&1 || true; }   # ya existente = ignorar
SG_ALB=$(grupo "${P}-sg-alb" "Balanceador de carga"); SG_WEB=$(grupo "${P}-sg-web" "Web y Grafana"); SG_IOT=$(grupo "${P}-sg-iot" "Simulador IoT"); SG_RDS=$(grupo "${P}-sg-rds" "RDS solo desde web e IoT")
regla "$SG_ALB" --protocol tcp --port 80 --cidr 0.0.0.0/0
regla "$SG_ALB" --protocol tcp --port 443 --cidr 0.0.0.0/0
# A las web solo entra el balanceador. Las instalaciones anteriores conservan su regla abierta al mundo hasta `cerrar-acceso-directo`.
regla "$SG_WEB" --protocol tcp --port 80 --source-group "$SG_ALB"
# Grafana (3000) NO se publica: confía en la cabecera que le pone la aplicación, así que solo se abre desde /bi/ con sesión y rol.
aws ec2 revoke-security-group-ingress --group-id "$SG_WEB" --protocol tcp --port 3000 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true   # instalaciones previas lo tenían abierto
regla "$SG_WEB" --protocol tcp --port 22 --cidr "$MI_IP/32"
regla "$SG_IOT" --protocol tcp --port 22 --cidr "$MI_IP/32"
regla "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_WEB"
regla "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_IOT"

# ---------------------------------------------------------------- RDS
log "RDS PostgreSQL (tarda ~5-10 minutos)"
aws rds describe-db-subnet-groups --db-subnet-group-name "${P}-subnets" >/dev/null 2>&1 || \
  aws rds create-db-subnet-group --db-subnet-group-name "${P}-subnets" --db-subnet-group-description "Cofrial privadas" --subnet-ids "$PRIV_A" "$PRIV_B" >/dev/null
# Multi-AZ (exigido en la revisión técnica): RDS mantiene una réplica síncrona en la otra zona y conmuta sola si cae la principal; el endpoint no cambia.
RDS_MULTI_AZ="${RDS_MULTI_AZ:-1}"; [ "$RDS_MULTI_AZ" = 1 ] && FLAG_MAZ=--multi-az || FLAG_MAZ=--no-multi-az
if ! aws rds describe-db-instances --db-instance-identifier "${P}-db" >/dev/null 2>&1; then
  aws rds create-db-instance --db-instance-identifier "${P}-db" --engine postgres --engine-version 16 --db-instance-class db.t3.micro \
    --allocated-storage 20 --db-name cofrial --master-username cofrial --master-user-password "$DB_PASSWORD" \
    --db-subnet-group-name "${P}-subnets" --vpc-security-group-ids "$SG_RDS" --no-publicly-accessible "$FLAG_MAZ" \
    --backup-retention-period 7 --copy-tags-to-snapshot --deletion-protection --tags Key=Proyecto,Value=cofrial Key=Entorno,Value=aws-academy \
    --no-enable-performance-insights >/dev/null
elif [ "$RDS_MULTI_AZ" = 1 ] && [ "$(q rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].MultiAZ')" = "False" ]; then
  # Base ya creada en una sola zona: se convierte en el sitio (sin recrearla ni perder datos; unos 10-20 min, con un corte breve al final)
  log "Convirtiendo la RDS existente a Multi-AZ (los datos se conservan)"
  aws rds modify-db-instance --db-instance-identifier "${P}-db" --multi-az --apply-immediately >/dev/null \
    || echo "AVISO: RDS rechazó Multi-AZ. La base sigue en una sola zona; revisa el mensaje y, si el laboratorio no lo permite, repórtalo antes de la defensa."
  sleep 30
fi
aws rds wait db-instance-available --db-instance-identifier "${P}-db"
DB_HOST=$(q rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].Endpoint.Address')

# ---------------------------------------------------------------- Balanceador (ALB)
# Se crea ANTES que las EC2 porque su DNS entra en el .env de la web (orígenes CSRF). Reparte entre las dos web, cada una en su zona, y solo envía
# tráfico a la que responde /health (200 solo si además alcanza la base). Con "stickiness" cada visitante se queda en la misma web: los contadores de intentos viven en la memoria de la instancia.
log "Application Load Balancer en dos zonas (${AZ_A} y ${AZ_B})"
LB_ARN=$(aws elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)
if [ -z "$LB_ARN" ] || [ "$LB_ARN" = "None" ]; then
  LB_ARN=$(q elbv2 create-load-balancer --name "${P}-alb" --type application --scheme internet-facing --subnets "$PUB" "$PUB_B" \
    --security-groups "$SG_ALB" --tags "Key=Name,Value=${P}-alb" --query 'LoadBalancers[0].LoadBalancerArn')
fi
ALB_DNS=$(q elbv2 describe-load-balancers --load-balancer-arns "$LB_ARN" --query 'LoadBalancers[0].DNSName')
TG_ARN=$(aws elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)
if [ -z "$TG_ARN" ] || [ "$TG_ARN" = "None" ]; then
  TG_ARN=$(q elbv2 create-target-group --name "${P}-tg" --protocol HTTP --port 80 --vpc-id "$VPC" --target-type instance \
    --health-check-protocol HTTP --health-check-path /health --health-check-interval-seconds 15 --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 --unhealthy-threshold-count 2 --matcher HttpCode=200 --query 'TargetGroups[0].TargetGroupArn')
fi
aws elbv2 modify-target-group-attributes --target-group-arn "$TG_ARN" --attributes Key=stickiness.enabled,Value=true Key=stickiness.type,Value=lb_cookie \
  Key=stickiness.lb_cookie.duration_seconds,Value=86400 Key=deregistration_delay.timeout_seconds,Value=30 >/dev/null

# Certificado para el 443: el que se pase (CERT_ARN o cert.pem/cert.key) es "de confianza" y activa HTTPS completo (redirección, cookies seguras, HSTS);
# uno autofirmado solo habilita el 443 para mostrar el cifrado y NO fuerza HTTPS (HSTS con un certificado que el navegador rechaza lo dejaría sin acceso).
CERT_CONFIABLE=0
if [ -n "${CERT_ARN:-}" ]; then CERT_CONFIABLE=1
elif [ -f "$ESTADO/cert-arn.txt" ] && aws acm describe-certificate --certificate-arn "$(cat "$ESTADO/cert-arn.txt")" >/dev/null 2>&1; then
  CERT_ARN=$(cat "$ESTADO/cert-arn.txt"); [ -f "$ESTADO/cert-confiable" ] && CERT_CONFIABLE=1
else
  rm -f "$ESTADO/cert-confiable"
  if [ -f "$ESTADO/cert.pem" ] && [ -f "$ESTADO/cert.key" ]; then
    CADENA=(); [ -f "$ESTADO/cert-cadena.pem" ] && CADENA=(--certificate-chain "fileb://$ESTADO/cert-cadena.pem")
    CERT_ARN=$(aws acm import-certificate --certificate "fileb://$ESTADO/cert.pem" --private-key "fileb://$ESTADO/cert.key" ${CADENA[@]+"${CADENA[@]}"} --query CertificateArn --output text 2>/dev/null) && CERT_CONFIABLE=1 || CERT_ARN=""
  else
    CN="${DOMINIO_HTTPS:-cofrial.local}"
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout "$ESTADO/autofirmado.key" -out "$ESTADO/autofirmado.pem" -subj "/CN=$CN" \
      -addext "subjectAltName=DNS:$CN,DNS:$ALB_DNS" >/dev/null 2>&1 \
      || openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout "$ESTADO/autofirmado.key" -out "$ESTADO/autofirmado.pem" -subj "/CN=$CN" >/dev/null 2>&1 || true
    chmod 600 "$ESTADO/autofirmado.key" 2>/dev/null || true
    CERT_ARN=$(aws acm import-certificate --certificate "fileb://$ESTADO/autofirmado.pem" --private-key "fileb://$ESTADO/autofirmado.key" --query CertificateArn --output text 2>/dev/null) || CERT_ARN=""
  fi
  if [ -n "$CERT_ARN" ]; then echo "$CERT_ARN" > "$ESTADO/cert-arn.txt"; [ "$CERT_CONFIABLE" = 1 ] && touch "$ESTADO/cert-confiable"; fi
fi
if [ -z "$CERT_ARN" ]; then echo "AVISO: ACM no aceptó el certificado; el balanceador queda solo con HTTP (80). Pasa CERT_ARN o revisa los permisos del laboratorio."; CERT_CONFIABLE=0; fi
[ "$CERT_CONFIABLE" = 1 ] || echo "AVISO: HTTPS sin certificado de confianza (autofirmado o ausente). Para el dominio real: importa el certificado en ACM y vuelve a ejecutar con CERT_ARN=..."

# Listeners: con certificado de confianza el 80 redirige al 443; si no, el 80 sirve la aplicación y el 443 (si hay certificado) también.
oyente() { aws elbv2 describe-listeners --load-balancer-arn "$LB_ARN" --query 'Listeners[?Port==`'"$1"'`].ListenerArn | [0]' --output text 2>/dev/null || echo None; }
REDIRIGIR='Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'; REENVIAR="Type=forward,TargetGroupArn=$TG_ARN"
ACCION_80="$REENVIAR"; [ "$CERT_CONFIABLE" = 1 ] && ACCION_80="$REDIRIGIR"
L80=$(oyente 80)
if [ -z "$L80" ] || [ "$L80" = "None" ]; then aws elbv2 create-listener --load-balancer-arn "$LB_ARN" --protocol HTTP --port 80 --default-actions "$ACCION_80" >/dev/null
else aws elbv2 modify-listener --listener-arn "$L80" --default-actions "$ACCION_80" >/dev/null; fi
if [ -n "$CERT_ARN" ]; then
  L443=$(oyente 443)
  if [ -z "$L443" ] || [ "$L443" = "None" ]; then
    aws elbv2 create-listener --load-balancer-arn "$LB_ARN" --protocol HTTPS --port 443 --certificates "CertificateArn=$CERT_ARN" \
      --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 --default-actions "$REENVIAR" >/dev/null
  else aws elbv2 modify-listener --listener-arn "$L443" --certificates "CertificateArn=$CERT_ARN" >/dev/null; fi
fi

# Orígenes que Django acepta en los formularios (CSRF): el ALB, el dominio y, si existe de una instalación anterior, la IP elástica.
EIP=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[0].PublicIp' 2>/dev/null || echo None)
# El PRIMER origen es el que la app usa para armar enlaces de correo (recuperar clave): con dominio va primero y con https.
ORIGENES="http://${ALB_DNS},https://${ALB_DNS}"
[ -n "${DOMINIO_HTTPS:-}" ] && ORIGENES="https://${DOMINIO_HTTPS},http://${DOMINIO_HTTPS},$ORIGENES"
[ "$EIP" != "None" ] && [ -n "$EIP" ] && ORIGENES="$ORIGENES,http://${EIP}"
# DJANGO_HTTPS=1 marca las cookies como Secure y anuncia HSTS. Se activa cuando TODO visitante llega por HTTPS: certificado de confianza (el 80 del ALB
# redirige) y las web cerradas al acceso directo (sg-web sin 80 abierto a internet). Si la dirección vieja sigue abierta por HTTP queda en 0: con cookies
# Secure nadie podría iniciar sesión por ella. HSTS parte en un día (HSTS_SEG) y no en un año: el navegador que lo recibe deja de aceptar excepciones de
# certificado para ese nombre durante ese plazo, y el dominio y su certificado todavía pueden cambiar. ACTIVAR_HSTS=1 lo deja en un año.
WEB_ABIERTA=$(q ec2 describe-security-groups --group-ids "$SG_WEB" --query "length(SecurityGroups[0].IpPermissions[?FromPort==\`80\`].IpRanges[?CidrIp=='0.0.0.0/0'][])" 2>/dev/null || echo 1)
HTTPS_DJANGO=0; [ "$CERT_CONFIABLE" = 1 ] && [ "$WEB_ABIERTA" = 0 ] && HTTPS_DJANGO=1
[ "${ACTIVAR_HSTS:-0}" = 1 ] && HSTS_SEG=31536000; HSTS_SEG="${HSTS_SEG:-86400}"
[ "$CERT_CONFIABLE" = 1 ] && [ "$HTTPS_DJANGO" = 0 ] && echo "AVISO: las web aún aceptan el 80 directo desde internet: Django sigue sin cookies Secure ni HSTS. Tras cerrar el acceso directo, repite recrear-web."

# ---------------------------------------------------------------- EC2
log "EC2 web (una por zona) e IoT"
# La imagen de Ubuntu 24.04: primero el parámetro público de SSM; si el rol no puede leerlo (pasa con algunos roles del
# laboratorio), se busca la más reciente publicada por Canonical (propietario 099720109477).
AMI=$(q ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value 2>/dev/null) || AMI=""
if [ -z "$AMI" ] || [ "$AMI" = "None" ]; then
  AMI=$(q ec2 describe-images --owners 099720109477 --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" "Name=state,Values=available" --query 'sort_by(Images,&CreationDate)[-1].ImageId')
fi
[ -n "$AMI" ] && [ "$AMI" != "None" ] || { echo "No pude determinar la imagen de Ubuntu 24.04; define AMI=ami-... a mano"; exit 1; }
if [ ! -f "$ESTADO/${P}-key.pem" ]; then
  aws ec2 delete-key-pair --key-name "${P}-key" 2>/dev/null || true
  aws ec2 create-key-pair --key-name "${P}-key" --query KeyMaterial --output text > "$ESTADO/${P}-key.pem"; chmod 400 "$ESTADO/${P}-key.pem"
fi
EIP_ID=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[0].AllocationId')
if [ "$EIP_ID" = "None" ]; then EIP_ID=$(q ec2 allocate-address --domain vpc --query AllocationId); etiqueta "$EIP_ID" "${P}-eip"; fi
EIP=$(q ec2 describe-addresses --allocation-ids "$EIP_ID" --query 'Addresses[0].PublicIp')

# user-data: instala Docker, clona el repositorio, escribe .env y levanta los contenedores (restart: unless-stopped los revive).
datos() {   # $1 = web|iot (qué compose)   $2 = primario|secundario (solo web: el primario migra la base y corre podador/despachador)
local ROL="${2:-primario}"
cat <<U
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker
git clone --branch ${RAMA} ${REPO_URL} /opt/cofrial && cd /opt/cofrial
# ID de esta instancia (IMDSv2) para la fila D1 de la Torre de control. curl -f falla ante cualquier error HTTP y solo se acepta un ID con su forma
# (i- y hexadecimales): una página de error o un fallo dejan el valor vacío y el arranque sigue, nunca queda basura en .env
TOKEN_IMDS=\$(curl -sf -m 3 --connect-timeout 2 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' || true)
INSTANCIA_EC2=\$(curl -sf -m 3 --connect-timeout 2 -H "X-aws-ec2-metadata-token: \$TOKEN_IMDS" http://169.254.169.254/latest/meta-data/instance-id || true)
[[ "\$INSTANCIA_EC2" =~ ^i-[0-9a-f]+\$ ]] || INSTANCIA_EC2=
cat > .env <<E
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=*
DJANGO_CSRF_ORIGINS=${ORIGENES}
DJANGO_CONFIAR_PROXY=1
DJANGO_HTTPS=${HTTPS_DJANGO}
DJANGO_HSTS_SEG=${HSTS_SEG}
DJANGO_HTTPS_REDIRECT=0
DJANGO_CSP=${DJANGO_CSP:-1}
ROL_WEB=${ROL}
DB_HOST=${DB_HOST}
DB_PORT=5432
DB_NAME=cofrial
DB_USER=cofrial
DB_PASSWORD=${DB_PASSWORD}
DB_SSLMODE=require
INSTANCIA_EC2=\${INSTANCIA_EC2}
DEMO_PASSWORD=${DEMO_PASSWORD}
FORZAR_CARGA_DEMO=${FORZAR_CARGA_DEMO:-0}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-}
GRAFANA_DB_PASSWORD=${GRAFANA_DB_PASSWORD}
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
INTERVALO_SEG=5
PROB_RUPTURA=0.01
GEMINI_API_KEY=${GEMINI_API_KEY:-}
GEMINI_MODELS=${GEMINI_MODELS:-}
GROQ_API_KEY=${GROQ_API_KEY:-}
GROQ_MODELS=${GROQ_MODELS:-}
IA_PROVEEDORES=${IA_PROVEEDORES:-}
EMAIL_HOST=${EMAIL_HOST:-}
EMAIL_PORT=${EMAIL_PORT:-587}
EMAIL_HOST_USER=${EMAIL_HOST_USER:-}
EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD:-}
EMAIL_REMITENTE=${EMAIL_REMITENTE:-}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
CLAUDE_MODELS=${CLAUDE_MODELS:-}
MERCADOPAGO_ACCESS_TOKEN=${MERCADOPAGO_ACCESS_TOKEN:-}
MERCADOPAGO_PUBLIC_KEY=${MERCADOPAGO_PUBLIC_KEY:-}
MERCADOPAGO_PAYER_EMAIL=${MERCADOPAGO_PAYER_EMAIL:-}
E
chmod 600 .env
docker compose -f aws/docker-compose.$1.yml --env-file .env up -d --build
U
}
lanzar() { # nombre tipo subred sg archivo [rol]
  local id ARCH="userdata-$5.sh"; [ "${6:-}" = secundario ] && ARCH="userdata-$5-b.sh"
  id=$(q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopped" --query 'Reservations[0].Instances[0].InstanceId')
  if [ "$id" = "None" ]; then
    datos "$5" "${6:-primario}" > "$ESTADO/$ARCH"
    id=$(q ec2 run-instances --image-id "$AMI" --instance-type "$2" --key-name "${P}-key" --subnet-id "$3" --security-group-ids "$4" \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' --user-data "file://$ESTADO/$ARCH" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$1}]" --query 'Instances[0].InstanceId')
  fi; echo "$id"
}
WEB_ID=$(lanzar "${P}-ec2-web" t3.small "$PUB" "$SG_WEB" web primario)
WEB_B_ID=$(lanzar "${P}-ec2-web-b" t3.small "$PUB_B" "$SG_WEB" web secundario)
IOT_ID=$(lanzar "${P}-ec2-iot" t3.micro "$PUB" "$SG_IOT" iot)
aws ec2 wait instance-running --instance-ids "$WEB_ID" "$WEB_B_ID" "$IOT_ID"
# Instalaciones anteriores al ALB: la IP elástica sigue en la web A para que la dirección vieja abra hasta `cerrar-acceso-directo`.
if [ "$EIP" != "None" ] && [ -n "$EIP" ]; then aws ec2 associate-address --instance-id "$WEB_ID" --allocation-id "$(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[0].AllocationId')" >/dev/null || true; fi

# ---------------------------------------------------------------- destinos del ALB
# sincronizar_destinos: deja registradas en el grupo de destino exactamente las web vigentes (las terminadas se dan de baja).
sincronizar_destinos() {
  local vigentes=" $* " id
  aws elbv2 register-targets --target-group-arn "$TG_ARN" --targets $(for id in "$@"; do echo "Id=$id"; done) >/dev/null
  for id in $(q elbv2 describe-target-health --target-group-arn "$TG_ARN" --query 'TargetHealthDescriptions[].Target.Id'); do
    case "$vigentes" in *" $id "*) ;; *) aws elbv2 deregister-targets --target-group-arn "$TG_ARN" --targets "Id=$id" >/dev/null || true;; esac
  done
}
# esperar_sano <id>...: espera (hasta 15 min) a que el ALB dé por sanas esas instancias; devuelve 1 si no lo logran.
esperar_sano() {
  local i id ok
  for i in $(seq 1 60); do
    ok=1; for id in "$@"; do [ "$(aws elbv2 describe-target-health --target-group-arn "$TG_ARN" --targets "Id=$id" --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text 2>/dev/null)" = healthy ] || ok=0; done
    [ "$ok" = 1 ] && return 0; sleep 15
  done; return 1
}
log "Registrando las web en el ALB y esperando a que respondan el chequeo de salud (la primera vez tardan ~5-8 min en construirse)"
sincronizar_destinos "$WEB_ID" "$WEB_B_ID"
if [ "$ROLLING_B" = 1 ]; then
  esperar_sano "$WEB_ID" || { echo "La web A nueva no se puso sana en 15 min: NO se toca la B (sigue sirviendo con la versión anterior). Revisa: ssh ... 'cd /opt/cofrial && sudo docker compose -f aws/docker-compose.web.yml logs web'"; exit 1; }
  log "Web A sana: ahora se recrea la B"
  terminar_ec2 "${P}-ec2-web-b"
  WEB_B_ID=$(lanzar "${P}-ec2-web-b" t3.small "$PUB_B" "$SG_WEB" web secundario)
  aws ec2 wait instance-running --instance-ids "$WEB_B_ID"
  sincronizar_destinos "$WEB_ID" "$WEB_B_ID"
fi
esperar_sano "$WEB_ID" "$WEB_B_ID" || echo "AVISO: el ALB aún no da por sanas las dos web. Mira: bash aws/provision.sh estado (los contenedores pueden seguir construyéndose)."

echo "$ALB_DNS" > "$ESTADO/ip.txt"; echo "$ALB_DNS" > "$ESTADO/alb.txt"
IP_WEB_A=$(q ec2 describe-instances --instance-ids "$WEB_ID" --query 'Reservations[0].Instances[0].PublicIpAddress'); IP_WEB_B=$(q ec2 describe-instances --instance-ids "$WEB_B_ID" --query 'Reservations[0].Instances[0].PublicIpAddress')
cat <<R

==> LISTO (los contenedores tardan ~5-8 minutos en construirse la primera vez)
    Aplicación : $([ "$CERT_CONFIABLE" = 1 ] && echo https || echo http)://$ALB_DNS   (balanceador en $AZ_A y $AZ_B; $([ "$CERT_CONFIABLE" = 1 ] && echo "el 80 redirige a https://" || echo "https://$ALB_DNS abre con aviso de certificado autofirmado"))
    Dominio    : apuntar ${DOMINIO_HTTPS:-el dominio} al DNS del balanceador (CNAME/ALIAS) y, cuando abra por el dominio, ejecutar: bash aws/provision.sh cerrar-acceso-directo
    Panel BI   : http://$ALB_DNS/bi/   (con sesión de la aplicación: administración edita, gerencia mira; el puerto 3000 no está abierto)
    Verificar  : curl -L http://$ALB_DNS/health   y   python3 aws/verificar.py
    Endurecer  : bash aws/endurecer.sh revisar   (y, tras cada recrear-web o recrear-iot: bash aws/endurecer.sh alarmas --aplicar)
    Base       : RDS Multi-AZ=$(aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].MultiAZ' --output text)  (zona de respaldo: $(aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].SecondaryAvailabilityZone' --output text))
    SSH web A  : ssh -i $ESTADO/${P}-key.pem ubuntu@$IP_WEB_A   (primaria: migra la base, podador y despachador)
    SSH web B  : ssh -i $ESTADO/${P}-key.pem ubuntu@$IP_WEB_B   (secundaria)
    Avance     : ssh ... 'sudo cloud-init status --wait && cd /opt/cofrial && docker compose -f aws/docker-compose.web.yml ps'
    Claves     : $ESTADO/secretos.env (no se sube a git)
    Prueba de caída: bash aws/provision.sh estado; apagar una web desde la consola de EC2 y comprobar que http://$ALB_DNS/salud/ sigue respondiendo.
    Al terminar la sesión del laboratorio las EC2 se apagan; al encender (bash aws/provision.sh encender), los contenedores vuelven solos.
R
