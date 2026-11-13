#!/usr/bin/env bash
# Prueba SIN tocar AWS de aws/endurecer.sh: lo ejecuta contra un `aws` falso que guarda el estado de una instalación descuidada (base sin protección,
# security groups con reglas de más, el 80 sirviendo sin redirigir, chequeo sin base, sin alarmas) y responde las consultas --query con JMESPath real.
# Comprueba que la vista previa no cambia nada, que cada paso con --aplicar hace exactamente lo suyo y que ninguna clave aparece en pantalla ni en comandos.
# No valida los permisos del laboratorio (eso solo lo hace una corrida real).   bash aws/test_endurecer.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c 'import jmespath' 2>/dev/null || { echo "OMITIDA: falta el módulo jmespath (python3 -m pip install jmespath, o PYTHON=/ruta/a/un/python que lo tenga)"; exit 0; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/estado"; LOG="$TMP/llamadas.log"; : > "$LOG"
printf 'DB_PASSWORD=ClaveSecreta123\nDOMINIO_HTTPS=cofrial.example\nGEMINI_API_KEY=\n# comentario\nGROQ_API_KEY=OtraClave456\n' > "$TMP/estado/secretos.env"

cat > "$TMP/estado.json" <<'J'
{"db": {"DBInstanceStatus": "available", "MultiAZ": false, "DeletionProtection": false, "BackupRetentionPeriod": 1, "CopyTagsToSnapshot": false,
        "PubliclyAccessible": false, "StorageEncrypted": false, "AvailabilityZone": "us-east-1a", "SecondaryAvailabilityZone": null,
        "PendingModifiedValues": {}, "DBInstanceArn": "arn:aws:rds:us-east-1:1:db:cofrial-db"},
 "sg": {"sg-alb": [["tcp", 80, 80, ["0.0.0.0/0"], [], []], ["tcp", 443, 443, ["0.0.0.0/0"], [], []]],
        "sg-web": [["tcp", 80, 80, ["0.0.0.0/0"], [], ["sg-alb"]], ["tcp", 443, 443, ["0.0.0.0/0"], [], []], ["tcp", 22, 22, ["190.1.2.3/32"], [], []]],
        "sg-iot": [["tcp", 22, 22, ["190.1.2.3/32"], [], []]],
        "sg-rds": [["tcp", 5432, 5432, ["0.0.0.0/0"], [], ["sg-web", "sg-iot"]], ["-1", null, null, [], [], ["sg-otro"]]]},
 "oyentes": {"80": {"ListenerArn": "arn:l80", "Port": 80, "DefaultActions": [{"Type": "forward"}]},
             "443": {"ListenerArn": "arn:l443", "Port": 443, "SslPolicy": "ELBSecurityPolicy-2016-08", "Certificates": [{"CertificateArn": "arn:cert"}], "DefaultActions": [{"Type": "forward"}]}},
 "tg": {"TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:1:targetgroup/cofrial-tg/abc", "HealthCheckPath": "/salud/"},
 "sanos": ["healthy", "healthy"], "descartar": "false", "alarmas": [], "ssm": {}, "temas": []}
J

cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env PYTHON_REAL
import json, os, re, sys
import jmespath
a = sys.argv[1:]; ruta = os.environ["AWS_ST"]; e = json.load(open(ruta))
def op(n, d=None): return a[a.index(n) + 1] if n in a else d
def texto(v):
    if v is None: return "None"
    if isinstance(v, bool): return str(v)
    if isinstance(v, list):
        if v and all(isinstance(x, list) for x in v): return "\n".join("\t".join(texto(y) for y in x) for x in v)
        return "\t".join(texto(x) for x in v)
    if isinstance(v, dict): return "\t".join(texto(x) for x in v.values())
    return str(v)
def responde(datos):
    c = op("--query"); v = jmespath.search(c, datos) if c else datos
    s = texto(v) if op("--output") == "text" else json.dumps(v)
    if s: print(s)
    sys.exit(0)
def permisos(nombre):
    return [{"IpProtocol": p, "FromPort": d, "ToPort": h, "IpRanges": [{"CidrIp": c} for c in c4], "Ipv6Ranges": [{"CidrIpv6": c} for c in c6],
             "UserIdGroupPairs": [{"GroupId": g} for g in gs]} for p, d, h, c4, c6, gs in e["sg"][nombre]]
servicio, accion = a[0], a[1]
lectura = accion.startswith(("describe-", "get-", "list-")) or accion == "wait"
with open(os.environ["AWS_LOG"], "a") as f: f.write(("LEE " if lectura else "CAMBIA ") + " ".join(a) + "\n")
LB = "arn:aws:elasticloadbalancing:us-east-1:1:loadbalancer/app/cofrial-alb/xyz"
if accion == "get-caller-identity": responde({"Arn": "arn:aws:sts::1:assumed-role/LabRole/x"})
if accion == "describe-db-instances": responde({"DBInstances": [e["db"]]})
if accion == "describe-security-groups":
    if "--group-ids" in a: g = op("--group-ids"); responde({"SecurityGroups": [{"GroupId": g, "IpPermissions": permisos(g)}]})
    n = re.search(r"Values=cofrial-(sg-\w+)", " ".join(a)).group(1); responde({"SecurityGroups": [{"GroupId": n}]})
if accion == "describe-instances": n = re.search(r"Values=(cofrial-ec2-[\w-]+)", " ".join(a)).group(1); responde({"Reservations": [{"Instances": [{"InstanceId": "i-" + n}]}]})
if accion == "describe-load-balancers": responde({"LoadBalancers": [{"LoadBalancerArn": LB, "DNSName": "cofrial-alb-1.us-east-1.elb.amazonaws.com"}]})
if accion == "describe-target-groups": responde({"TargetGroups": [e["tg"]]})
if accion == "describe-listeners": responde({"Listeners": list(e["oyentes"].values())})
if accion == "describe-target-health": responde({"TargetHealthDescriptions": [{"Target": {"Id": f"i-{i}"}, "TargetHealth": {"State": s}} for i, s in enumerate(e["sanos"])]})
if accion == "describe-load-balancer-attributes": responde({"Attributes": [{"Key": "routing.http.drop_invalid_header_fields.enabled", "Value": e["descartar"]}]})
if accion == "describe-certificate": responde({"Certificate": {"DomainName": "cofrial.example", "Type": "IMPORTED", "Issuer": "Let's Encrypt", "Status": "ISSUED", "NotAfter": "2027-02-06"}})
if accion == "list-certificates": responde({"CertificateSummaryList": []})
if accion == "describe-alarms": responde({"MetricAlarms": [{"AlarmName": n, "StateValue": "OK"} for n in e["alarmas"]]})
if accion == "get-parameters-by-path": responde({"Parameters": [{"Name": k, "Value": v} for k, v in e["ssm"].items()]})
if accion == "list-topics": responde({"Topics": [{"TopicArn": t} for t in e["temas"]]})
if accion == "wait": sys.exit(0)
# ---- cambios: se aplican al estado para que la revisión siguiente los vea
if accion == "modify-db-instance":
    for bandera, clave, valor in (("--deletion-protection", "DeletionProtection", True), ("--copy-tags-to-snapshot", "CopyTagsToSnapshot", True),
                                  ("--no-publicly-accessible", "PubliclyAccessible", False), ("--multi-az", "MultiAZ", True)):
        if bandera in a: e["db"][clave] = valor
    if "--backup-retention-period" in a: e["db"]["BackupRetentionPeriod"] = int(op("--backup-retention-period"))
    if "--multi-az" in a: e["db"]["SecondaryAvailabilityZone"] = "us-east-1b"
if accion == "revoke-security-group-ingress":
    g = op("--group-id"); p = op("--ip-permissions"); proto = re.search(r"IpProtocol=([^,]+)", p).group(1); origen = re.search(r"(?:CidrIp|CidrIpv6|GroupId)=([^}]+)", p).group(1)
    for r in e["sg"][g]:
        if r[0] == proto:
            for lista in r[3:]:
                if origen in lista: lista.remove(origen)
    e["sg"][g] = [r for r in e["sg"][g] if r[3] or r[4] or r[5]]
if accion == "modify-listener":
    o = next(v for v in e["oyentes"].values() if v["ListenerArn"] == op("--listener-arn"))
    if "--ssl-policy" in a: o["SslPolicy"] = op("--ssl-policy")
    if "--default-actions" in a: o["DefaultActions"] = [{"Type": "redirect", "RedirectConfig": {"StatusCode": "HTTP_301"}}]
if accion == "modify-load-balancer-attributes": e["descartar"] = "true"
if accion == "modify-target-group": e["tg"]["HealthCheckPath"] = op("--health-check-path")
if accion == "put-metric-alarm": e["alarmas"].append(op("--alarm-name"))
if accion == "create-topic": e["temas"].append("arn:aws:sns:us-east-1:1:" + op("--name"))
if accion == "put-parameter": e["ssm"][op("--name")] = open(op("--value")[len("file://"):]).read()
json.dump(e, open(ruta, "w"))
FAKE
sed -i.bak "1s|PYTHON_REAL|$("$PY" -c 'import sys; print(sys.executable)')|" "$TMP/bin/aws" && rm "$TMP/bin/aws.bak"
printf '#!/bin/sh\ncat "$CURL_RESP"\n' > "$TMP/bin/curl"
printf '#!/bin/sh\ncase "$*" in *elb.amazonaws.com*) echo 10.9.9.1; echo 10.9.9.2;; *) cat "$DIG_DOMINIO";; esac\n' > "$TMP/bin/dig"
chmod +x "$TMP/bin/aws" "$TMP/bin/curl" "$TMP/bin/dig"
echo "404 " > "$TMP/curl.txt"; echo 54.82.100.161 > "$TMP/dig.txt"
export AWS_LOG="$LOG" AWS_ST="$TMP/estado.json" PATH="$TMP/bin:$PATH" COFRIAL_ESTADO="$TMP/estado" CURL_RESP="$TMP/curl.txt" DIG_DOMINIO="$TMP/dig.txt"
SAL="$TMP/salida.txt"
fallo() { echo "FALLO: $1"; echo "--- salida:"; cat "$SAL"; echo "--- cambios pedidos:"; grep '^CAMBIA' "$LOG" || true; exit 1; }
corre() { bash "$AQUI/endurecer.sh" "$@" > "$SAL" 2>&1 </dev/null; }
cambios() { grep -c '^CAMBIA' "$LOG" || true; }
hubo() { grep -q "^CAMBIA .*$1" "$LOG"; }

# 1) revisar ve cada defecto y no cambia nada
corre revisar || fallo "revisar terminó con error"
for esperado in "Multi-AZ desactivado" "sin protección contra borrado" "respaldos automáticos: 1 días" "no se copian a los snapshots" "cifrado en reposo INACTIVO" \
  "cofrial-sg-rds: sobra tcp 5432-5432 desde 0.0.0.0/0" "cofrial-sg-rds: sobra todo el tráfico desde sg-otro" "cofrial-sg-web: sobra tcp 80-80 desde 0.0.0.0/0" \
  "cofrial-sg-web: sobra tcp 443-443 desde 0.0.0.0/0" "el 80 no redirige al 443" "acepta cabeceras inválidas" "chequeo de salud en /salud/" "no hay alarmas"; do
  grep -qF -- "$esperado" "$SAL" || fallo "revisar no informó: $esperado"
done
grep -qF "[ok]    cofrial-sg-rds: tcp 5432 desde sg-web" "$SAL" && grep -qF "[ok]    cofrial-sg-web: tcp 22 desde 190.1.2.3/32" "$SAL" || fallo "revisar no reconoció las reglas correctas"
[ "$(cambios)" = 0 ] || fallo "revisar cambió algo"
echo "ok: revisar informa cada defecto y no cambia nada"

# 2) la vista previa de cada paso muestra los comandos y no ejecuta ninguno; --aplicar sin terminal ni SI=1 tampoco
for paso in rds rds-multiaz https alarmas secretos-subir secretos-bajar acm-dns; do corre "$paso" || fallo "vista previa de $paso con error"; grep -q "vista previa: no se ejecutó" "$SAL" || fallo "$paso no avisó que era vista previa"; done
CORTAR_DOMINIO=1 corre sg || fallo "vista previa de sg con error"
corre rds --aplicar || true; grep -q "no hay terminal para confirmar" "$SAL" || fallo "--aplicar sin terminal debía negarse"
[ "$(cambios)" = 0 ] || fallo "una vista previa (o un --aplicar sin confirmación) cambió algo"
echo "ok: sin --aplicar y sin confirmación ningún paso cambia nada"

# 3) rds: un solo modify con lo que falta, sin tocar Multi-AZ
SI=1 corre rds --aplicar || fallo "rds --aplicar"
hubo "rds modify-db-instance --db-instance-identifier cofrial-db --deletion-protection --backup-retention-period 7 --copy-tags-to-snapshot --apply-immediately" || fallo "rds no pidió protección, 7 días y copia de etiquetas"
hubo "modify-db-instance.*--multi-az" && fallo "el paso rds no debe tocar Multi-AZ"
: > "$LOG"; SI=1 corre rds --aplicar; hubo "modify-db-instance" && fallo "rds repitió un cambio ya hecho"
SI=1 corre rds-multiaz --aplicar || fallo "rds-multiaz --aplicar"; hubo "modify-db-instance --db-instance-identifier cofrial-db --multi-az --apply-immediately" || fallo "no convirtió a Multi-AZ"
grep -q "puede cortar las conexiones" "$SAL" || fallo "rds-multiaz no avisó de la interrupción"
echo "ok: rds aplica solo lo que falta, es idempotente y Multi-AZ va en su propio paso con aviso"

# 4) sg: limpia la base; no cierra las web si el dominio no apunta al balanceador o si no hay destinos sanos
: > "$LOG"; SI=1 corre sg --aplicar && fallo "sg debía detenerse: el dominio no apunta al balanceador"
hubo "revoke-security-group-ingress --group-id sg-rds .*CidrIp=0.0.0.0/0" && hubo "revoke-security-group-ingress --group-id sg-rds --ip-permissions IpProtocol=-1,UserIdGroupPairs=\[{GroupId=sg-otro}\]" || fallo "no quitó las reglas de más de la base"
hubo "revoke-security-group-ingress --group-id sg-web" && fallo "cerró las web aunque el dominio no apunta al balanceador"
grep -q "NO es del balanceador" "$SAL" || fallo "no explicó por qué no cerró las web"
echo 10.9.9.2 > "$TMP/dig.txt"; "$PY" - <<P
import json; r="$TMP/estado.json"; e=json.load(open(r)); e["sanos"]=["unhealthy","unhealthy"]; json.dump(e,open(r,"w"))
P
: > "$LOG"; SI=1 corre sg --aplicar && fallo "sg debía detenerse: no hay destinos sanos"; [ "$(cambios)" = 0 ] || fallo "cambió algo sin destinos sanos"
"$PY" - <<P
import json; r="$TMP/estado.json"; e=json.load(open(r)); e["sanos"]=["healthy","healthy"]; json.dump(e,open(r,"w"))
P
SI=1 corre sg --aplicar || fallo "sg --aplicar con el dominio en el balanceador"
hubo "revoke-security-group-ingress --group-id sg-web .*FromPort=80,ToPort=80,IpRanges=\[{CidrIp=0.0.0.0/0}\]" && hubo "revoke-security-group-ingress --group-id sg-web .*FromPort=443" || fallo "no cerró el 80 y el 443 directos"
grep -E "^CAMBIA .*sg-web" "$LOG" | grep -Eq "GroupId=sg-alb|190.1.2.3" && fallo "quitó una regla que debía quedar (balanceador o SSH del equipo)"
echo "ok: sg deja la base solo para web e IoT y cierra las web solo cuando el balanceador sirve y el dominio ya apunta a él"

# 5) https: TLS 1.2/1.3, 301 y cabeceras inválidas
: > "$LOG"; SI=1 corre https --aplicar || fallo "https --aplicar"
hubo "modify-listener --listener-arn arn:l443 --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06" || fallo "no fijó la política TLS"
hubo "modify-listener --listener-arn arn:l80 --default-actions Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}" || fallo "no puso la redirección 301"
hubo "modify-load-balancer-attributes .*drop_invalid_header_fields.enabled,Value=true" || fallo "no activó el descarte de cabeceras inválidas"
echo "ok: https deja TLS 1.2/1.3, redirección 301 y descarte de cabeceras inválidas"

# 6) salud: solo cambia el chequeo cuando /health ya responde por el balanceador
: > "$LOG"; SI=1 corre salud --aplicar && fallo "salud debía negarse: /health responde 404"; [ "$(cambios)" = 0 ] || fallo "cambió el chequeo con /health en 404"
echo "200 " > "$TMP/curl.txt"; SI=1 corre salud --aplicar || fallo "salud --aplicar"
hubo "modify-target-group .*--health-check-path /health" || fallo "no cambió el chequeo a /health"; grep -q "Para deshacerlo: .*--health-check-path /salud/" "$SAL" || fallo "no dejó el comando para deshacer"
echo "ok: salud cambia el chequeo a /health solo si el código nuevo ya responde, y deja cómo deshacerlo"

# 7) alarmas: CPU de las tres EC2, base (CPU, conexiones, espacio) y balanceador (no sanos, 5xx)
: > "$LOG"; SI=1 corre alarmas --aplicar || fallo "alarmas --aplicar"
[ "$(grep -c '^CAMBIA cloudwatch put-metric-alarm' "$LOG")" = 8 ] || fallo "se esperaban 8 alarmas"
hubo "put-metric-alarm --alarm-name cofrial-rds-conexiones .*--metric-name DatabaseConnections" && hubo "put-metric-alarm --alarm-name cofrial-alb-no-sanos .*UnHealthyHostCount .*Name=TargetGroup,Value=targetgroup/cofrial-tg/abc Name=LoadBalancer,Value=app/cofrial-alb/xyz" || fallo "faltan las alarmas de conexiones o de destinos no sanos"
hubo "sns " && fallo "sin ALARMA_EMAIL no debe crear temas de SNS"
echo "ok: alarmas crea las 8 alarmas (sin SNS si no se pide correo)"

# 8) secretos: los valores no salen por pantalla ni viajan en la línea de comandos
: > "$LOG"; SI=1 corre secretos-subir --aplicar || fallo "secretos-subir --aplicar"
[ "$(grep -c '^CAMBIA ssm put-parameter' "$LOG")" = 3 ] || fallo "debía subir 3 variables (las vacías y los comentarios no)"
grep -q "ClaveSecreta123\|OtraClave456" "$SAL" "$LOG" && fallo "una clave apareció en pantalla o en un comando"
: > "$LOG"; SI=1 corre secretos-bajar --aplicar || fallo "secretos-bajar --aplicar"
grep -q "^DB_PASSWORD=ClaveSecreta123$" "$TMP/estado/secretos.ssm.env" && grep -q "^GROQ_API_KEY=OtraClave456$" "$TMP/estado/secretos.ssm.env" || fallo "secretos-bajar no reconstruyó el archivo"
grep -q "ClaveSecreta123" "$SAL" && fallo "secretos-bajar mostró una clave"
echo "ok: los secretos suben y bajan de Parameter Store sin mostrarse"

# 9) después de todo, la revisión queda limpia (solo la nota del cifrado, que no se cambia desde el script)
: > "$LOG"; corre revisar || fallo "revisar final"
grep -q "Todo lo revisado cumple" "$SAL" || fallo "tras aplicar todos los pasos aún quedan faltas"
grep -q "cifrado en reposo INACTIVO" "$SAL" || fallo "el cifrado debía seguir informado como pendiente de decisión"
[ "$(cambios)" = 0 ] || fallo "la revisión final cambió algo"
echo "ok: tras los pasos, revisar no encuentra faltas y el cifrado queda como decisión pendiente"
echo "TODO OK"
