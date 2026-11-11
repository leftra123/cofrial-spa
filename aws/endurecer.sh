#!/usr/bin/env bash
# Endurece una instalación de Cofrial que YA existe en AWS (la que creó aws/provision.sh), sin recrear nada.
#
# Regla de uso: cada paso MUESTRA los comandos exactos que cambiarían AWS y no ejecuta ninguno. Solo con --aplicar los ejecuta, de a uno
# y preguntando antes de cada uno (SI=1 responde que sí: úsalo solo cuando ya revisaste la vista previa). `revisar` nunca cambia nada.
#
#   bash aws/endurecer.sh revisar                 # solo lectura: qué cumple y qué falta (RDS, security groups, HTTPS, chequeo, alarmas)
#   bash aws/endurecer.sh rds [--aplicar]         # protección contra borrado, respaldos de 7 días, etiquetas en snapshots, sin acceso público
#   bash aws/endurecer.sh rds-multiaz [--aplicar] # convierte la base a Multi-AZ si no lo es (10-20 min; puede haber un corte breve)
#   bash aws/endurecer.sh sg [--aplicar]          # security groups: RDS solo desde web e IoT; las web solo desde el balanceador
#   bash aws/endurecer.sh https [--aplicar]       # oyente 443 con TLS 1.2/1.3, redirección 301 del 80 al 443, cabeceras inválidas descartadas
#   bash aws/endurecer.sh acm-dns [--aplicar]     # pide a ACM un certificado para DOMINIO_HTTPS con validación por DNS y muestra el registro a crear
#   bash aws/endurecer.sh salud [--aplicar]       # el chequeo del balanceador pasa a /health (prueba también la base); exige el código nuevo desplegado
#   bash aws/endurecer.sh alarmas [--aplicar]     # alarmas de CloudWatch: CPU, conexiones y espacio de la base, destinos no sanos y errores 5xx del ALB
#   bash aws/endurecer.sh secretos-subir [--aplicar]   # copia aws/.estado/secretos.env a SSM Parameter Store (SecureString, /cofrial/NOMBRE)
#   bash aws/endurecer.sh secretos-bajar [--aplicar]   # reconstruye el archivo desde SSM en aws/.estado/secretos.ssm.env (no pisa el actual)
#
# Variables: COFRIAL_ESTADO (carpeta .estado vigente si no es la de este checkout), DOMINIO_HTTPS (si no está en secretos.env), CERT_ARN (certificado
# nuevo para el 443), ALARMA_EMAIL (correo que recibe las alarmas; hay que confirmar la suscripción), UMBRAL_CONEXIONES (65), CORTAR_DOMINIO=1.
# Ningún paso imprime ni registra claves. Requisitos: AWS CLI v2 con las credenciales del Learner Lab, curl y, para el dominio, dig.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
P=cofrial
ESTADO="${COFRIAL_ESTADO:-$(cd "$(dirname "$0")" && pwd)/.estado}"
PASO="${1:-ayuda}"; APLICAR=0; for a in "$@"; do [ "$a" = "--aplicar" ] && APLICAR=1; done
FALTAS=0
q() { aws "$@" --output text; }
titulo() { printf '\n==> %s\n' "$*"; }
ok() { printf '  [ok]    %s\n' "$*"; }
falta() { printf '  [FALTA] %s\n' "$*"; FALTAS=$((FALTAS + 1)); }
nota() { printf '  [nota]  %s\n' "$*"; }

# confirmar: 0 = ejecutar. Sin --aplicar nunca; con --aplicar pregunta (o SI=1). La pregunta se lee de la terminal, no de una tubería.
confirmar() {
  if [ "$APLICAR" != 1 ]; then echo "    (vista previa: no se ejecutó; repite el paso con --aplicar)"; return 1; fi
  [ "${SI:-0}" = 1 ] && return 0
  [ -t 0 ] || { echo "    (no se ejecutó: no hay terminal para confirmar; usa SI=1 si ya aprobaste este comando)"; return 1; }
  local r; printf '    ¿Ejecutar? [s/N] '; read -r r; [ "$r" = s ] || [ "$r" = S ] || { echo "    omitido"; return 1; }
}
# mostrar <comando...>: el comando tal como se puede copiar a la terminal (comillas simples solo donde hacen falta).
mostrar() {
  local x; printf '  $'
  for x in "$@"; do case "$x" in *[!A-Za-z0-9_./:=@,+-]*) printf " '%s'" "$(printf '%s' "$x" | sed "s/'/'\\\\''/g")";; *) printf ' %s' "$x";; esac; done; printf '\n'
}
# cambia <qué hace> <comando...>: lo único que modifica AWS pasa por aquí.
cambia() {
  local desc="$1"; shift
  printf '\n  # %s\n' "$desc"; mostrar "$@"
  confirmar || return 0
  "$@" >/dev/null && echo "    hecho"
}

case "$PASO" in ayuda|-h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0;; esac
command -v aws >/dev/null || { echo "Falta la AWS CLI v2"; exit 1; }
ARN=$(q sts get-caller-identity --query Arn 2>/dev/null) || { echo "Credenciales inválidas o caducadas: inicia el laboratorio y guarda las de AWS Details (pbpaste > ~/.aws/credentials)"; exit 1; }
echo "Identidad: $ARN  ·  región $REGION  ·  $([ "$APLICAR" = 1 ] && echo 'MODO APLICAR (pregunta antes de cada comando)' || echo 'vista previa (no cambia nada)')"

# ---------------------------------------------------------------- hechos de la instalación (solo lectura)
DOMINIO="${DOMINIO_HTTPS:-$(sed -n 's/^DOMINIO_HTTPS=//p' "$ESTADO/secretos.env" 2>/dev/null | tail -1)}"
rds() { q rds describe-db-instances --db-instance-identifier "${P}-db" --query "DBInstances[0].$1" 2>/dev/null || echo None; }
sg_id() { q ec2 describe-security-groups --filters "Name=group-name,Values=${P}-sg-$1" --query 'SecurityGroups[0].GroupId' 2>/dev/null || echo None; }
ec2_id() { q ec2 describe-instances --filters "Name=tag:Name,Values=$1" "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].InstanceId' 2>/dev/null || echo None; }
LB_ARN=$(q elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].LoadBalancerArn' 2>/dev/null || echo None)
ALB_DNS=None; TG_ARN=None
if [ "$LB_ARN" != None ]; then
  ALB_DNS=$(q elbv2 describe-load-balancers --load-balancer-arns "$LB_ARN" --query 'LoadBalancers[0].DNSName')
  TG_ARN=$(q elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' 2>/dev/null || echo None)
fi
oyente() { q elbv2 describe-listeners --load-balancer-arn "$LB_ARN" --query 'Listeners[?Port==`'"$1"'`].'"$2"' | [0]' 2>/dev/null || echo None; }
sanos() { q elbv2 describe-target-health --target-group-arn "$TG_ARN" --query "length(TargetHealthDescriptions[?TargetHealth.State=='healthy'])" 2>/dev/null || echo 0; }
codigo() { curl -sk -m 8 -o /dev/null -w '%{http_code} %{redirect_url}' "$1" 2>/dev/null || echo "000"; }
SG_ALB=$(sg_id alb); SG_WEB=$(sg_id web); SG_IOT=$(sg_id iot); SG_RDS=$(sg_id rds)

# ---------------------------------------------------------------- security groups
# reglas <sg>: una línea por regla de entrada: protocolo|desde|hasta|rangos IPv4|rangos IPv6|grupos de origen
reglas() {
  aws ec2 describe-security-groups --group-ids "$1" --output text --query \
    "SecurityGroups[0].IpPermissions[].join('|',[IpProtocol,to_string(FromPort),to_string(ToPort),join(',',IpRanges[].CidrIp),join(',',Ipv6Ranges[].CidrIpv6),join(',',UserIdGroupPairs[].GroupId)])" | tr '\t' '\n'
}
# permitido <grupo> <protocolo> <desde> <hasta> <origen>: ¿la regla es parte del diseño? Todo lo demás sobra.
permitido() {
  case "$1:$2:$3:$4:$5" in
    rds:tcp:5432:5432:"$SG_WEB"|rds:tcp:5432:5432:"$SG_IOT") return 0;;      # la base, solo desde las web y el nodo IoT
    web:tcp:80:80:"$SG_ALB") return 0;;                                       # las web, solo desde el balanceador
    web:tcp:22:22:*.*/32|iot:tcp:22:22:*.*/32) return 0;;                     # SSH, solo desde una dirección concreta (la del equipo)
    alb:tcp:80:80:0.0.0.0/0|alb:tcp:443:443:0.0.0.0/0) return 0;;             # el balanceador es la única entrada pública
  esac
  return 1
}
permiso() {   # la misma regla en el formato de --ip-permissions, para quitarla exactamente
  local base; if [ "$1" = "-1" ]; then base="IpProtocol=-1"; else base="IpProtocol=$1,FromPort=$2,ToPort=$3"; fi
  case "$4" in sg-*) echo "$base,UserIdGroupPairs=[{GroupId=$4}]";; *:*) echo "$base,Ipv6Ranges=[{CidrIpv6=$4}]";; *) echo "$base,IpRanges=[{CidrIp=$4}]";; esac
}
# recorrer_sg <grupo> <sg> <revisar|cerrar>: informa cada regla o propone quitar las que sobran.
recorrer_sg() {
  local tipo="$1" sg="$2" modo="$3" proto de a cidrs cidrs6 grupos o que
  [ "$sg" != None ] || { falta "no existe ${P}-sg-$tipo"; return 0; }
  while IFS='|' read -r proto de a cidrs cidrs6 grupos <&3; do
    [ -n "$proto" ] && [ "$proto" != None ] || continue
    que="$proto $de-$a"; [ "$proto" = "-1" ] && que="todo el tráfico"
    for o in $(echo "$cidrs,$cidrs6,$grupos" | tr ',' ' '); do
      if permitido "$tipo" "$proto" "$de" "$a" "$o"; then
        if [ "$modo" = revisar ]; then ok "${P}-sg-$tipo: $proto $de desde $o"; fi
      elif [ "$modo" = revisar ]; then falta "${P}-sg-$tipo: sobra $que desde $o"
      else cambia "Quitar de ${P}-sg-$tipo la entrada de $que desde $o" aws ec2 revoke-security-group-ingress --group-id "$sg" --ip-permissions "$(permiso "$proto" "$de" "$a" "$o")"
      fi
    done
  done 3<<LISTA
$(reglas "$sg")
LISTA
}
tiene() { reglas "$1" | grep -q "^tcp|$2|$2|.*$3"; }

# ---------------------------------------------------------------- revisar
revisar() {
  titulo "Base de datos (${P}-db)"
  if [ "$(rds DBInstanceStatus)" = None ]; then falta "la base ${P}-db no existe"; else
    echo "  estado: $(rds DBInstanceStatus) · zona $(rds AvailabilityZone) · respaldo en $(rds SecondaryAvailabilityZone)"
    [ "$(rds MultiAZ)" = True ] && ok "Multi-AZ activado" || falta "Multi-AZ desactivado (paso: rds-multiaz)"
    [ "$(rds DeletionProtection)" = True ] && ok "protección contra borrado" || falta "sin protección contra borrado (paso: rds)"
    R=$(rds BackupRetentionPeriod); [ "$R" != None ] && [ "$R" -ge 7 ] && ok "respaldos automáticos: $R días" || falta "respaldos automáticos: $R días, se piden 7 o más (paso: rds)"
    [ "$(rds CopyTagsToSnapshot)" = True ] && ok "las etiquetas se copian a los snapshots" || falta "las etiquetas no se copian a los snapshots (paso: rds)"
    [ "$(rds PubliclyAccessible)" = False ] && ok "sin acceso público" || falta "la instancia es pública (paso: rds)"
    [ "$(rds StorageEncrypted)" = True ] && ok "cifrado en reposo activo" || nota "cifrado en reposo INACTIVO: no se cambia desde aquí (exige snapshot cifrado y restauración; ver aws/README.md, «Cifrado en reposo»)"
    PEND=$(rds PendingModifiedValues); [ -z "$PEND" ] || [ "$PEND" = None ] || nota "cambios pendientes en la base: $PEND"
  fi
  titulo "Security groups"
  recorrer_sg rds "$SG_RDS" revisar; recorrer_sg web "$SG_WEB" revisar; recorrer_sg iot "$SG_IOT" revisar; recorrer_sg alb "$SG_ALB" revisar
  if [ "$SG_RDS" != None ]; then for g in "$SG_WEB" "$SG_IOT"; do tiene "$SG_RDS" 5432 "$g" || falta "${P}-sg-rds no admite el 5432 desde $g"; done; fi
  [ "$SG_WEB" = None ] || tiene "$SG_WEB" 80 "$SG_ALB" || falta "${P}-sg-web no admite el 80 desde el balanceador"
  titulo "Balanceador y HTTPS"
  if [ "$LB_ARN" = None ]; then falta "no existe ${P}-alb"; else
    echo "  DNS: $ALB_DNS · dominio: ${DOMINIO:-sin dominio}"
    CERT=$(oyente 443 'Certificates[0].CertificateArn')
    if [ -z "$CERT" ] || [ "$CERT" = None ]; then falta "no hay oyente 443 (lo crea aws/provision.sh con el certificado)"; else
      ok "oyente 443 · política $(oyente 443 SslPolicy)"
      echo "  certificado: $(q acm describe-certificate --certificate-arn "$CERT" --query 'Certificate.[DomainName,Type,Issuer,Status,NotAfter]' 2>/dev/null | tr '\t' ' ' || echo 'no se pudo leer en ACM')"
    fi
    A80=$(oyente 80 'DefaultActions[0].[Type,RedirectConfig.StatusCode]' | tr '\t' ' ')
    [ "$A80" = "redirect HTTP_301" ] && ok "el 80 redirige al 443 de forma permanente (301)" || falta "el 80 no redirige al 443 (hoy: ${A80:-sin oyente}; paso: https)"
    D=$(q elbv2 describe-load-balancer-attributes --load-balancer-arn "$LB_ARN" --query "Attributes[?Key=='routing.http.drop_invalid_header_fields.enabled'].Value | [0]")
    [ "$D" = true ] && ok "el balanceador descarta cabeceras inválidas" || falta "el balanceador acepta cabeceras inválidas (paso: https)"
    RUTA=$(q elbv2 describe-target-groups --target-group-arns "$TG_ARN" --query 'TargetGroups[0].HealthCheckPath' 2>/dev/null || echo None)
    [ "$RUTA" = /health ] && ok "chequeo de salud en /health (prueba la base)" || falta "chequeo de salud en $RUTA, que no prueba la base (paso: salud)"
    N=$(sanos); [ "$N" -ge 2 ] && ok "$N destinos sanos" || falta "$N destinos sanos (se esperan 2)"
    q elbv2 describe-target-health --target-group-arn "$TG_ARN" --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State]' 2>/dev/null | sed 's/^/    destino: /'
    echo "  http://$ALB_DNS/health  -> $(codigo "http://$ALB_DNS/health")"
    echo "  https://$ALB_DNS/health -> $(codigo "https://$ALB_DNS/health")  (sin validar el certificado: es del dominio, no del DNS del balanceador)"
    if [ -n "$DOMINIO" ]; then
      echo "  https://$DOMINIO/health -> $(curl -s -m 8 -o /dev/null -w '%{http_code}' "https://$DOMINIO/health" 2>/dev/null || echo '000 (no abre o el certificado no es válido para ese nombre)')"
      echo "  cabeceras de https://$DOMINIO/cuenta/entrar/ (las cookies se muestran sin su valor):"
      curl -sI -m 8 "https://$DOMINIO/cuenta/entrar/" 2>/dev/null | grep -iE '^(strict-transport-security|content-security-policy|x-frame-options|x-content-type-options|referrer-policy|set-cookie):' \
        | sed -E 's/^([Ss]et-[Cc]ookie: [^=]+)=[^;]*/\1=…/' | cut -c1-200 | sed 's/^/    /' || true
    fi
  fi
  titulo "Alarmas de CloudWatch"
  AL=$(q cloudwatch describe-alarms --alarm-name-prefix "${P}-" --query 'MetricAlarms[].[AlarmName,StateValue]' 2>/dev/null || true)
  if [ -n "$AL" ]; then echo "$AL" | sed 's/^/  /'; ok "$(echo "$AL" | wc -l | tr -d ' ') alarmas definidas"; else falta "no hay alarmas ${P}-* (paso: alarmas)"; fi
  titulo "Secretos"
  NP=$(q ssm get-parameters-by-path --path "/${P}/" --query 'length(Parameters)' 2>/dev/null || echo "sin permiso")
  nota "parámetros en SSM bajo /${P}/: $NP (las EC2 leen sus claves del .env que escribe provision.sh; SSM es la copia central del equipo)"
  printf '\n%s\n' "$([ "$FALTAS" = 0 ] && echo 'Todo lo revisado cumple.' || echo "Faltan $FALTAS puntos (cada uno indica su paso).")"
}

# ---------------------------------------------------------------- pasos que cambian AWS
paso_rds() {
  [ "$(rds DBInstanceStatus)" != None ] || { echo "La base ${P}-db no existe."; exit 1; }
  local args=()
  [ "$(rds DeletionProtection)" = True ] || args+=(--deletion-protection)
  local r; r=$(rds BackupRetentionPeriod)
  if [ "$r" -lt 7 ]; then args+=(--backup-retention-period 7); [ "$r" = 0 ] && echo "  AVISO: los respaldos automáticos están apagados (0 días); encenderlos reinicia la base (corte de 1-2 minutos)."; fi
  [ "$(rds CopyTagsToSnapshot)" = True ] || args+=(--copy-tags-to-snapshot)
  [ "$(rds PubliclyAccessible)" = False ] || args+=(--no-publicly-accessible)
  if [ ${#args[@]} -eq 0 ]; then ok "la base ya tiene protección contra borrado, 7 días de respaldo, copia de etiquetas y no es pública"; else
    cambia "Base: ${args[*]} (sin corte, salvo el aviso de arriba)" aws rds modify-db-instance --db-instance-identifier "${P}-db" "${args[@]}" --apply-immediately
  fi
  cambia "Etiquetas de la base (las que heredarán los snapshots)" aws rds add-tags-to-resource --resource-name "$(rds DBInstanceArn)" --tags Key=Proyecto,Value=cofrial Key=Entorno,Value=aws-academy
  [ "$(rds StorageEncrypted)" = True ] || nota "cifrado en reposo inactivo: no se toca aquí (ver aws/README.md, «Cifrado en reposo»)"
}
paso_rds_multiaz() {
  if [ "$(rds MultiAZ)" = True ]; then ok "la base ya es Multi-AZ (respaldo en $(rds SecondaryAvailabilityZone))"; return 0; fi
  echo "  AVISO: la conversión tarda 10-20 minutos. La base sigue atendiendo, pero más lenta mientras se copia, y puede cortar las conexiones unos segundos al final."
  cambia "Convertir ${P}-db a Multi-AZ (los datos se conservan; el endpoint no cambia)" aws rds modify-db-instance --db-instance-identifier "${P}-db" --multi-az --apply-immediately
  [ "$APLICAR" = 1 ] && { echo "  esperando a que la base vuelva a «available»…"; sleep 30; aws rds wait db-instance-available --db-instance-identifier "${P}-db"; echo "  Multi-AZ=$(rds MultiAZ)"; } || true
}
paso_sg() {
  for g in "$SG_WEB" "$SG_IOT"; do tiene "$SG_RDS" 5432 "$g" || cambia "Admitir el 5432 de la base desde $g" aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 5432 --source-group "$g"; done
  tiene "$SG_WEB" 80 "$SG_ALB" || cambia "Admitir el 80 de las web desde el balanceador" aws ec2 authorize-security-group-ingress --group-id "$SG_WEB" --protocol tcp --port 80 --source-group "$SG_ALB"
  recorrer_sg rds "$SG_RDS" cerrar; recorrer_sg iot "$SG_IOT" cerrar
  # Cerrar el acceso directo a las web deja al balanceador como única entrada: antes hay que saber que el balanceador sirve y a dónde apunta el dominio.
  if reglas "$SG_WEB" | grep -Eq '^tcp\|(80|443|3000)\|.*0\.0\.0\.0/0'; then
    [ "$(sanos)" -ge 1 ] || { echo "  NO se cierra el acceso directo a las web: el balanceador no tiene ningún destino sano y el sitio quedaría sin entrada."; return 1; }
    if [ -n "$DOMINIO" ] && command -v dig >/dev/null; then
      IPS_ALB=" $(dig +short "$ALB_DNS" | tr '\n' ' ')"; IP_DOM=$(dig +short "$DOMINIO" | tail -1)
      case "$IPS_ALB" in *" $IP_DOM "*) ok "$DOMINIO ($IP_DOM) ya apunta al balanceador";; *)
        echo "  AVISO: $DOMINIO apunta a ${IP_DOM:-ninguna dirección}, que NO es del balanceador ($IPS_ALB). Al cerrar el acceso directo ese nombre deja de abrir"
        echo "         hasta que se apunte al balanceador. Para cerrarlo igual: CORTAR_DOMINIO=1."
        [ "${CORTAR_DOMINIO:-0}" = 1 ] || return 1;;
      esac
    fi
  fi
  recorrer_sg web "$SG_WEB" cerrar
  echo; echo "  Para deshacer el cierre del acceso directo: aws ec2 authorize-security-group-ingress --group-id $SG_WEB --protocol tcp --port 80 --cidr 0.0.0.0/0"
}
paso_https() {
  [ "$LB_ARN" != None ] || { echo "No existe ${P}-alb."; exit 1; }
  local l443 l80 cert; l443=$(oyente 443 ListenerArn); l80=$(oyente 80 ListenerArn)
  if [ -z "$l443" ] || [ "$l443" = None ]; then
    echo "  No hay oyente 443. Lo crea aws/provision.sh: con CERT_ARN, con cert.pem y cert.key en $ESTADO, o con un certificado autofirmado que importa a ACM."; exit 1
  fi
  cert=$(oyente 443 'Certificates[0].CertificateArn')
  if [ -n "${CERT_ARN:-}" ] && [ "$CERT_ARN" != "$cert" ]; then cambia "Usar en el 443 el certificado $CERT_ARN" aws elbv2 modify-listener --listener-arn "$l443" --certificates "CertificateArn=$CERT_ARN"; cert="$CERT_ARN"; fi
  local dom emisor; dom=$(q acm describe-certificate --certificate-arn "$cert" --query Certificate.DomainName 2>/dev/null || echo "?"); emisor=$(q acm describe-certificate --certificate-arn "$cert" --query Certificate.Issuer 2>/dev/null || echo "?")
  if [ "$dom" = "$emisor" ]; then echo "  AVISO: el certificado es AUTOFIRMADO (emisor = $dom). Con la redirección, quien entre por http llega a la advertencia del navegador («La conexión no es privada», NET::ERR_CERT_AUTHORITY_INVALID) y debe aceptarla a mano."; fi
  [ "$(oyente 443 SslPolicy)" = ELBSecurityPolicy-TLS13-1-2-2021-06 ] || cambia "Política TLS del 443: solo TLS 1.2 y 1.3" aws elbv2 modify-listener --listener-arn "$l443" --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06
  if [ "$(oyente 80 'DefaultActions[0].[Type,RedirectConfig.StatusCode]' | tr '\t' ' ')" = "redirect HTTP_301" ]; then ok "el 80 ya redirige al 443 (301)"
  elif [ -z "$l80" ] || [ "$l80" = None ]; then cambia "Oyente 80 que solo redirige al 443 (301)" aws elbv2 create-listener --load-balancer-arn "$LB_ARN" --protocol HTTP --port 80 --default-actions 'Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'
  else cambia "El 80 deja de servir la aplicación y redirige al 443 (301)" aws elbv2 modify-listener --listener-arn "$l80" --default-actions 'Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}'; fi
  [ "$(q elbv2 describe-load-balancer-attributes --load-balancer-arn "$LB_ARN" --query "Attributes[?Key=='routing.http.drop_invalid_header_fields.enabled'].Value | [0]")" = true ] \
    || cambia "El balanceador descarta cabeceras HTTP mal formadas" aws elbv2 modify-load-balancer-attributes --load-balancer-arn "$LB_ARN" --attributes Key=routing.http.drop_invalid_header_fields.enabled,Value=true
}
paso_acm_dns() {
  [ -n "$DOMINIO" ] || { echo "Define DOMINIO_HTTPS (en secretos.env o como variable)."; exit 1; }
  echo "  ACM valida el dominio con un registro CNAME que hay que crear en su zona DNS. Un nombre gratuito de No-IP (webhop.me) no deja crear ese registro:"
  echo "  en ese caso sirve el certificado de Let's Encrypt importado, que vence a los 90 días y no se renueva solo."
  cambia "Pedir a ACM un certificado para $DOMINIO con validación por DNS" aws acm request-certificate --domain-name "$DOMINIO" --validation-method DNS --tags "Key=Name,Value=${P}-cert"
  for c in $(q acm list-certificates --certificate-statuses PENDING_VALIDATION --query "CertificateSummaryList[?DomainName=='$DOMINIO'].CertificateArn" 2>/dev/null); do
    echo "  pendiente: $c"; echo "  registro a crear en el DNS:  $(q acm describe-certificate --certificate-arn "$c" --query 'Certificate.DomainValidationOptions[0].ResourceRecord.[Name,Type,Value]' | tr '\t' ' ')"
    echo "  cuando ACM lo marque «ISSUED»:  CERT_ARN=$c bash aws/endurecer.sh https --aplicar"
  done
}
paso_salud() {
  [ "$TG_ARN" != None ] || { echo "No existe ${P}-tg."; exit 1; }
  local ruta i c; ruta=$(q elbv2 describe-target-groups --target-group-arns "$TG_ARN" --query 'TargetGroups[0].HealthCheckPath')
  if [ "$ruta" = /health ]; then ok "el chequeo ya usa /health"; return 0; fi
  # Si alguna web aún corre el código anterior, /health no existe y el balanceador las daría por caídas: se prueba varias veces (reparte entre las dos).
  for i in 1 2 3 4 5 6; do c=$(codigo "https://$ALB_DNS/health"); case "$c" in 200*) ;; *) echo "  NO se cambia el chequeo: https://$ALB_DNS/health respondió «$c» (intento $i). Despliega antes el código con /health en las dos web."; return 1;; esac; done
  ok "/health respondió 200 en 6 pedidos seguidos por el balanceador"
  cambia "Chequeo de salud del balanceador: de $ruta a /health (prueba también la base)" aws elbv2 modify-target-group --target-group-arn "$TG_ARN" --health-check-path /health
  echo; echo "  Para deshacerlo: aws elbv2 modify-target-group --target-group-arn $TG_ARN --health-check-path $ruta"
}
paso_alarmas() {
  local tema="" acciones=() id n
  if [ -n "${ALARMA_EMAIL:-}" ]; then
    cambia "Tema de SNS para los avisos" aws sns create-topic --name "${P}-alarmas"
    tema=$(q sns list-topics --query "Topics[?ends_with(TopicArn, ':${P}-alarmas')].TopicArn | [0]" 2>/dev/null || echo None)
    if [ -z "$tema" ] || [ "$tema" = None ]; then tema="<ARN del tema ${P}-alarmas>"; fi
    cambia "Suscribir $ALARMA_EMAIL (llega un correo con un enlace que hay que confirmar)" aws sns subscribe --topic-arn "$tema" --protocol email --notification-endpoint "$ALARMA_EMAIL"
    acciones=(--alarm-actions "$tema" --ok-actions "$tema")
  else nota "sin ALARMA_EMAIL: las alarmas quedan visibles en la consola de CloudWatch, sin aviso por correo"; fi
  # alarma <nombre> <qué avisa> <espacio> <métrica> <estadística> <periodo s> <periodos> <umbral> <comparación> <dimensiones...>
  alarma() {
    local nombre="$1" desc="$2" ns="$3" met="$4" est="$5" per="$6" ev="$7" umb="$8" comp="$9"; shift 9
    cambia "$desc" aws cloudwatch put-metric-alarm --alarm-name "$nombre" --alarm-description "$desc" --namespace "$ns" --metric-name "$met" --statistic "$est" \
      --period "$per" --evaluation-periods "$ev" --threshold "$umb" --comparison-operator "$comp" --treat-missing-data notBreaching --dimensions "$@" ${acciones[@]+"${acciones[@]}"}
  }
  for n in web web-b iot; do
    id=$(ec2_id "${P}-ec2-$n"); [ "$id" != None ] || { nota "no existe ${P}-ec2-$n: sin alarma de CPU"; continue; }
    alarma "${P}-ec2-$n-cpu" "CPU de ${P}-ec2-$n sobre 80 % durante 10 minutos" AWS/EC2 CPUUtilization Average 300 2 80 GreaterThanThreshold "Name=InstanceId,Value=$id"
  done
  alarma "${P}-rds-cpu" "CPU de la base sobre 80 % durante 10 minutos" AWS/RDS CPUUtilization Average 300 2 80 GreaterThanThreshold "Name=DBInstanceIdentifier,Value=${P}-db"
  alarma "${P}-rds-conexiones" "Conexiones a la base sobre ${UMBRAL_CONEXIONES:-65} (una db.t3.micro admite cerca de 80)" AWS/RDS DatabaseConnections Maximum 300 2 "${UMBRAL_CONEXIONES:-65}" GreaterThanThreshold "Name=DBInstanceIdentifier,Value=${P}-db"
  alarma "${P}-rds-espacio" "Menos de 2 GB libres en el disco de la base" AWS/RDS FreeStorageSpace Minimum 300 1 2147483648 LessThanThreshold "Name=DBInstanceIdentifier,Value=${P}-db"
  if [ "$LB_ARN" != None ] && [ "$TG_ARN" != None ]; then
    alarma "${P}-alb-no-sanos" "El balanceador tiene al menos un destino web no sano" AWS/ApplicationELB UnHealthyHostCount Maximum 60 2 1 GreaterThanOrEqualToThreshold "Name=TargetGroup,Value=${TG_ARN##*:}" "Name=LoadBalancer,Value=${LB_ARN##*:loadbalancer/}"
    alarma "${P}-alb-5xx" "El balanceador devolvió más de 10 errores 5xx propios en 5 minutos" AWS/ApplicationELB HTTPCode_ELB_5XX_Count Sum 300 1 10 GreaterThanThreshold "Name=LoadBalancer,Value=${LB_ARN##*:loadbalancer/}"
  fi
  echo; echo "  Las alarmas de CPU van atadas al ID de cada EC2: tras recrear-web o recrear-iot hay que repetir este paso."
}
paso_secretos_subir() {
  [ -f "$ESTADO/secretos.env" ] || { echo "No existe $ESTADO/secretos.env (define COFRIAL_ESTADO con la carpeta vigente)."; exit 1; }
  local nombre valor tmp; tmp=$(mktemp); chmod 600 "$tmp"; TMP_SECRETO="$tmp"; trap 'rm -f "${TMP_SECRETO:-}"' EXIT
  while IFS='=' read -r nombre valor <&3; do
    case "$nombre" in ''|\#*) continue;; esac
    [ -n "$valor" ] || continue
    printf '\n  # Guardar %s cifrado en Parameter Store\n  $ aws ssm put-parameter --name /%s/%s --type SecureString --overwrite --value ********\n' "$nombre" "$P" "$nombre"
    confirmar || continue
    printf '%s' "$valor" > "$tmp"       # el valor viaja en un archivo temporal, no en la línea de comandos (no queda en la lista de procesos)
    aws ssm put-parameter --name "/$P/$nombre" --type SecureString --overwrite --value "file://$tmp" >/dev/null && echo "    hecho"
  done 3< "$ESTADO/secretos.env"
}
paso_secretos_bajar() {
  local destino="$ESTADO/secretos.ssm.env"
  printf '\n  # Leer /%s/* de Parameter Store y escribirlo en %s (permisos 600; no pisa secretos.env)\n  $ aws ssm get-parameters-by-path --path /%s/ --with-decryption\n' "$P" "$destino" "$P"
  confirmar || return 0
  mkdir -p "$ESTADO"; ( umask 077; aws ssm get-parameters-by-path --path "/$P/" --with-decryption --query 'Parameters[].[Name,Value]' --output text | sed "s|^/$P/||" | tr '\t' '=' > "$destino" )
  echo "    hecho: $(wc -l < "$destino" | tr -d ' ') variables. Compara sin mostrarlas:  shasum $ESTADO/secretos.env $destino"
}

case "$PASO" in
  revisar) revisar;;
  rds) titulo "Base de datos: protección, respaldos y etiquetas"; paso_rds;;
  rds-multiaz) titulo "Base de datos: Multi-AZ"; paso_rds_multiaz;;
  sg) titulo "Security groups"; paso_sg;;
  https) titulo "HTTPS en el balanceador"; paso_https;;
  acm-dns) titulo "Certificado de ACM con validación por DNS"; paso_acm_dns;;
  salud) titulo "Chequeo de salud del balanceador"; paso_salud;;
  alarmas) titulo "Alarmas de CloudWatch"; paso_alarmas;;
  secretos-subir) titulo "Secretos a SSM Parameter Store"; paso_secretos_subir;;
  secretos-bajar) titulo "Secretos desde SSM Parameter Store"; paso_secretos_bajar;;
  *) echo "Paso desconocido: $PASO"; sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 1;;
esac
