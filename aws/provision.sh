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
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
P=cofrial
REPO_URL="${REPO_URL:-https://github.com/leftra123/cofrial-spa.git}"
RAMA="${RAMA:-main}"
ESTADO="$(cd "$(dirname "$0")" && pwd)/.estado"; mkdir -p "$ESTADO"
log() { printf '\n==> %s\n' "$*"; }
q() { aws "$@" --output text; }

command -v aws >/dev/null || { echo "Falta la AWS CLI v2"; exit 1; }
q sts get-caller-identity --query Arn >/dev/null || { echo "Credenciales inválidas o caducadas: copia las de AWS Details en el Learner Lab"; exit 1; }

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
AMI=$(q ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value)
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
GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}
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
