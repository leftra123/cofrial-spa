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
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
P=cofrial
REPO_URL="${REPO_URL:-https://github.com/leftra123/cofrial-spa.git}"
RAMA="${RAMA:-main}"
ESTADO="$(cd "$(dirname "$0")" && pwd)/.estado"; mkdir -p "$ESTADO"
log() { printf '\n==> %s\n' "$*"; }
q() { aws "$@" --output text; }

command -v aws >/dev/null || { echo "Falta la AWS CLI v2"; exit 1; }
ARN=$(q sts get-caller-identity --query Arn) || { echo "Credenciales inválidas o caducadas: copia las de AWS Details en el Learner Lab"; exit 1; }
echo "Identidad: $ARN"
case "$ARN" in *assumed-role/runserver/*) echo "Estás con el rol 'runserver' de la terminal del laboratorio, que no puede crear VPC, RDS ni EC2. Exporta las llaves de AWS Details (AWS CLI: Show) para usar LabRole y vuelve a ejecutar."; exit 1;; esac

# ---------------------------------------------------------------- destruir
if [ "${1:-}" = "destruir" ]; then
  log "Borrando recursos ${P}-*"
  for id in $(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" "Name=instance-state-name,Values=pending,running,stopped,stopping" --query 'Reservations[].Instances[].InstanceId'); do aws ec2 terminate-instances --instance-ids "$id" >/dev/null; done
  aws ec2 wait instance-terminated --instance-ids $(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-*" --query 'Reservations[].Instances[].InstanceId') 2>/dev/null || true
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
  if ! aws ec2 describe-addresses --max-items 1 >/dev/null 2>&1; then
    echo "AWS rechaza las consultas: la sesión del laboratorio terminó o no está iniciada."
    echo "  1) En AWS Academy abre el Learner Lab y pulsa Start Lab; espera el círculo verde."
    echo "  2) AWS Details > AWS CLI > Show: copia el bloque [default] y guárdalo con:  pbpaste > ~/.aws/credentials"
    echo "  3) Vuelve a ejecutar: bash aws/provision.sh encender"
    exit 1
  fi
  estado_rds() { aws rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "no existe"; }
  estado_ec2() { q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].State.Name' 2>/dev/null || echo "no existe"; }
  id_ec2() { q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].InstanceId'; }
  IP_WEB=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=${P}-eip" --query 'Addresses[0].PublicIp' 2>/dev/null || echo "")
  log "Estado actual"
  echo "  RDS ${P}-db ........ $(estado_rds)"; echo "  EC2 web ............ $(estado_ec2 ${P}-ec2-web)"; echo "  EC2 IoT ............ $(estado_ec2 ${P}-ec2-iot)"; echo "  IP de la aplicación . ${IP_WEB:-desconocida}"
  if [ "$1" = "encender" ]; then
    log "Encendiendo RDS (la base primero)"
    for i in $(seq 1 40); do ST=$(estado_rds); case "$ST" in stopped) aws rds start-db-instance --db-instance-identifier "${P}-db" >/dev/null && break;; available|starting|backing-up|configuring-enhanced-monitoring) break;; "no existe") echo "RDS no existe: ejecuta bash aws/provision.sh"; exit 1;; *) sleep 15;; esac; done
    aws rds wait db-instance-available --db-instance-identifier "${P}-db"
    log "Encendiendo las EC2"
    for n in "${P}-ec2-web" "${P}-ec2-iot"; do
      for i in $(seq 1 30); do ST=$(estado_ec2 $n); case "$ST" in stopped) aws ec2 start-instances --instance-ids "$(id_ec2 $n)" >/dev/null; break;; running|pending) break;; "no existe"|None) echo "$n no existe: ejecuta bash aws/provision.sh"; exit 1;; *) sleep 10;; esac; done
    done
    aws ec2 wait instance-running --instance-ids "$(id_ec2 ${P}-ec2-web)" "$(id_ec2 ${P}-ec2-iot)"
    echo "$IP_WEB" > "$ESTADO/ip.txt"
    log "Esperando a que la aplicación responda en http://$IP_WEB (hasta 10 minutos)"
    for i in $(seq 1 40); do curl -s -m 5 "http://$IP_WEB/salud/" | grep -q ok && { echo "  La aplicación responde. Verifica todo con: python3 aws/verificar.py"; exit 0; }; sleep 15; done
    echo "  La aplicación aún no responde; espera unos minutos y repite: bash aws/provision.sh estado"
  fi
  exit 0
fi

# ---------------------------------------------------------------- recrear-web
# Termina la EC2 web y deja que el resto del script cree una nueva con las claves ACTUALES de aws/.estado/secretos.env
# (GEMINI_API_KEY y GROQ_API_KEY). Sirve para rotar claves sin entrar por SSH. RDS, la red, la IP elástica y la EC2 del IoT
# se conservan; la web queda sin servicio unos 8 minutos.
if [ "${1:-}" = "recrear-web" ]; then
  log "Terminando la EC2 web para recrearla con las claves actuales"
  IDS=$(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-ec2-web" "Name=instance-state-name,Values=pending,running,stopped,stopping" --query 'Reservations[].Instances[].InstanceId')
  if [ -n "$IDS" ] && [ "$IDS" != "None" ]; then aws ec2 terminate-instances --instance-ids $IDS >/dev/null; aws ec2 wait instance-terminated --instance-ids $IDS; fi
fi

# ---------------------------------------------------------------- secretos generados (se guardan solo en aws/.estado)
gen() { openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20; }
[ -f "$ESTADO/secretos.env" ] || cat > "$ESTADO/secretos.env" <<S
DB_PASSWORD=$(gen)
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
DEMO_PASSWORD=$(gen)
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
PRIV_A=$(subred "${P}-privada-a" 10.0.2.0/24 "$AZ_A"); PRIV_B=$(subred "${P}-privada-b" 10.0.3.0/24 "$AZ_B")

IGW=$(q ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC" --query 'InternetGateways[0].InternetGatewayId')
if [ "$IGW" = "None" ]; then IGW=$(q ec2 create-internet-gateway --query InternetGateway.InternetGatewayId); etiqueta "$IGW" "${P}-igw"; aws ec2 attach-internet-gateway --internet-gateway-id "$IGW" --vpc-id "$VPC"; fi
RT=$(buscar describe-route-tables "${P}-rt" --query 'RouteTables[0].RouteTableId')
if [ "$RT" = "None" ]; then
  RT=$(q ec2 create-route-table --vpc-id "$VPC" --query RouteTable.RouteTableId); etiqueta "$RT" "${P}-rt"
  aws ec2 create-route --route-table-id "$RT" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW" >/dev/null
  aws ec2 associate-route-table --route-table-id "$RT" --subnet-id "$PUB" >/dev/null
fi

# ---------------------------------------------------------------- Security Groups encadenados
log "Security Groups"
grupo() { local id; id=$(q ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC" "Name=group-name,Values=$1" --query 'SecurityGroups[0].GroupId'); if [ "$id" = "None" ]; then id=$(q ec2 create-security-group --group-name "$1" --description "$2" --vpc-id "$VPC" --query GroupId); etiqueta "$id" "$1"; fi; echo "$id"; }
regla() { aws ec2 authorize-security-group-ingress --group-id "$1" "${@:2}" >/dev/null 2>&1 || true; }   # ya existente = ignorar
SG_WEB=$(grupo "${P}-sg-web" "Web y Grafana"); SG_IOT=$(grupo "${P}-sg-iot" "Simulador IoT"); SG_RDS=$(grupo "${P}-sg-rds" "RDS solo desde web e IoT")
regla "$SG_WEB" --protocol tcp --port 80 --cidr 0.0.0.0/0
regla "$SG_WEB" --protocol tcp --port 3000 --cidr 0.0.0.0/0
regla "$SG_WEB" --protocol tcp --port 22 --cidr "$MI_IP/32"
regla "$SG_IOT" --protocol tcp --port 22 --cidr "$MI_IP/32"
regla "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_WEB"
regla "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_IOT"

# ---------------------------------------------------------------- RDS
log "RDS PostgreSQL (tarda ~5-10 minutos)"
aws rds describe-db-subnet-groups --db-subnet-group-name "${P}-subnets" >/dev/null 2>&1 || \
  aws rds create-db-subnet-group --db-subnet-group-name "${P}-subnets" --db-subnet-group-description "Cofrial privadas" --subnet-ids "$PRIV_A" "$PRIV_B" >/dev/null
aws rds describe-db-instances --db-instance-identifier "${P}-db" >/dev/null 2>&1 || \
  aws rds create-db-instance --db-instance-identifier "${P}-db" --engine postgres --engine-version 16 --db-instance-class db.t3.micro \
    --allocated-storage 20 --db-name cofrial --master-username cofrial --master-user-password "$DB_PASSWORD" \
    --db-subnet-group-name "${P}-subnets" --vpc-security-group-ids "$SG_RDS" --no-publicly-accessible --no-multi-az \
    --backup-retention-period 1 --no-enable-performance-insights >/dev/null
aws rds wait db-instance-available --db-instance-identifier "${P}-db"
DB_HOST=$(q rds describe-db-instances --db-instance-identifier "${P}-db" --query 'DBInstances[0].Endpoint.Address')

# ---------------------------------------------------------------- EC2
log "EC2 web e IoT"
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
datos() { cat <<U
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker
git clone --branch ${RAMA} ${REPO_URL} /opt/cofrial && cd /opt/cofrial
cat > .env <<E
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=*
DJANGO_CSRF_ORIGINS=http://${EIP}
DB_HOST=${DB_HOST}
DB_PORT=5432
DB_NAME=cofrial
DB_USER=cofrial
DB_PASSWORD=${DB_PASSWORD}
DB_SSLMODE=require
DEMO_PASSWORD=${DEMO_PASSWORD}
GRAFANA_DB_PASSWORD=${GRAFANA_DB_PASSWORD}
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
INTERVALO_SEG=5
PROB_RUPTURA=0.01
GEMINI_API_KEY=${GEMINI_API_KEY:-}
GEMINI_MODELS=${GEMINI_MODELS:-}
GROQ_API_KEY=${GROQ_API_KEY:-}
GROQ_MODELS=${GROQ_MODELS:-}
IA_PROVEEDORES=${IA_PROVEEDORES:-}
E
chmod 600 .env
docker compose -f aws/docker-compose.$1.yml --env-file .env up -d --build
U
}
lanzar() { # nombre tipo subred sg archivo
  local id; id=$(q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopped" --query 'Reservations[0].Instances[0].InstanceId')
  if [ "$id" = "None" ]; then
    datos "$5" > "$ESTADO/userdata-$5.sh"
    id=$(q ec2 run-instances --image-id "$AMI" --instance-type "$2" --key-name "${P}-key" --subnet-id "$3" --security-group-ids "$4" \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' --user-data "file://$ESTADO/userdata-$5.sh" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$1}]" --query 'Instances[0].InstanceId')
  fi; echo "$id"
}
WEB_ID=$(lanzar "${P}-ec2-web" t3.small "$PUB" "$SG_WEB" web)
IOT_ID=$(lanzar "${P}-ec2-iot" t3.micro "$PUB" "$SG_IOT" iot)
aws ec2 wait instance-running --instance-ids "$WEB_ID" "$IOT_ID"
aws ec2 associate-address --instance-id "$WEB_ID" --allocation-id "$EIP_ID" >/dev/null

echo "$EIP" > "$ESTADO/ip.txt"
cat <<R

==> LISTO (los contenedores tardan ~5-8 minutos en construirse la primera vez)
    Aplicación : http://$EIP
    Grafana    : http://$EIP:3000   (admin / clave en $ESTADO/secretos.env)
    Verificar  : curl http://$EIP/salud/
    SSH web    : ssh -i $ESTADO/${P}-key.pem ubuntu@$EIP
    Avance     : ssh ... 'sudo cloud-init status --wait && cd /opt/cofrial && docker compose -f aws/docker-compose.web.yml ps'
    Claves     : $ESTADO/secretos.env (no se sube a git)
    Al terminar la sesión del laboratorio las EC2 se apagan; al encender, los contenedores vuelven solos.
R
