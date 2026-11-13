#!/usr/bin/env bash
# Crea (o actualiza) en CloudWatch el panel «cofrial-salud»: el estado de la aplicación en verde y rojo, alojado por AWS FUERA de las EC2.
#
# Por qué: /health, /salud/ y /salud/bd/ son respuestas de texto que viven en las mismas web que vigilan; si la web cae, no hay nada que
# responda ni pantalla que se ponga roja. Este panel lee las métricas y las alarmas de AWS, así que sigue mostrando aunque las web estén caídas.
#
#   bash aws/panel-salud.sh                 # crea o actualiza el panel y muestra su dirección
#   bash aws/panel-salud.sh --vista-previa  # solo imprime el JSON del panel; no crea nada
#
# Variables opcionales: DOMINIO_HTTPS (se menciona en el panel), PANEL_NOMBRE (por defecto cofrial-salud), AWS_REGION (us-east-1).
# Es idempotente: repetirlo reemplaza el panel. NO depende de los IDs de las EC2 (las gráficas de CPU buscan por métrica), así que
# sigue valiendo después de cada recrear-web. Las alarmas que muestra son las que crea aws/endurecer.sh alarmas.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"; export AWS_DEFAULT_REGION="$REGION"
P=cofrial
NOMBRE="${PANEL_NOMBRE:-cofrial-salud}"
VISTA=0
case "${1:-}" in
  "") ;;
  --vista-previa) VISTA=1;;
  -h|--help) sed -n '2,13p' "$0"; exit 0;;
  *) echo "Opción desconocida: $1 (usa --vista-previa o --help)"; exit 2;;
esac
command -v aws >/dev/null || { echo "Falta la AWS CLI v2."; exit 1; }
command -v python3 >/dev/null || { echo "Falta python3."; exit 1; }

q() { aws "$@" --output text; }
CUENTA="$(q sts get-caller-identity --query Account)" || { echo "Credenciales inválidas o caducadas: pega las nuevas (bash aws/activar.sh)."; exit 1; }
LB_ARN="$(q elbv2 describe-load-balancers --names "${P}-alb" --query 'LoadBalancers[0].LoadBalancerArn' 2>/dev/null || echo None)"
TG_ARN="$(q elbv2 describe-target-groups --names "${P}-tg" --query 'TargetGroups[0].TargetGroupArn' 2>/dev/null || echo None)"
[ "$LB_ARN" != None ] && [ "$TG_ARN" != None ] || { echo "No encuentro el balanceador ${P}-alb o el grupo ${P}-tg: ¿existe la instalación? (bash aws/provision.sh estado)"; exit 1; }
ALARMAS="$(q cloudwatch describe-alarms --alarm-name-prefix "$P" --query 'MetricAlarms[].AlarmName' 2>/dev/null || true)"
[ -n "$ALARMAS" ] || echo "AVISO: no hay alarmas ${P}-* todavía; el panel saldrá sin ese cuadro (bash aws/endurecer.sh alarmas --aplicar)." >&2

DEFINICION="$(REGION="$REGION" CUENTA="$CUENTA" LB="${LB_ARN#*loadbalancer/}" TG="targetgroup/${TG_ARN#*:targetgroup/}" DB="${P}-db" ALARMAS="$ALARMAS" DOM="${DOMINIO_HTTPS:-}" python3 - <<'PY'
import json, os
reg, cuenta, lb, tg, db = (os.environ[k] for k in ("REGION", "CUENTA", "LB", "TG", "DB"))
alarmas = os.environ["ALARMAS"].split()
dom = os.environ.get("DOM", "")
VERDE, ROJO, AZUL, NARANJA = "#2ca02c", "#d62728", "#1f77b4", "#ff7f0e"
sitio = f"https://{dom}/health" if dom else "/health del sitio"
w = []
w.append({"type": "text", "x": 0, "y": 0, "width": 24, "height": 3, "properties": {"markdown":
    "# Salud de Cofrial\n"
    f"**Rojo = algo falla.** Este panel lo aloja AWS fuera de las máquinas: si la web cae, sigue mostrando el problema (el chequeo de texto en {sitio} no puede). "
    "Se actualiza cada minuto. **Qué mirar primero:** el cuadro de alarmas, luego «Web sanas»."}})
if alarmas:
    w.append({"type": "alarm", "x": 0, "y": 3, "width": 24, "height": 4, "properties": {
        "title": "Alarmas (verde = bien, rojo = en alarma, gris = sin datos)",
        "alarms": [f"arn:aws:cloudwatch:{reg}:{cuenta}:alarm:{a}" for a in alarmas]}})
y = 7 if alarmas else 3
def metrica(titulo, x, ancho, metricas, vista="timeSeries", estadistica="Average", periodo=60, extra=None, alto=6):
    p = {"title": titulo, "region": reg, "view": vista, "stat": estadistica, "period": periodo, "metrics": metricas}
    if vista == "timeSeries": p["stacked"] = False
    p.update(extra or {})
    return {"type": "metric", "x": x, "y": y, "width": ancho, "height": alto, "properties": p}
LBD = ["LoadBalancer", lb]; TGD = ["TargetGroup", tg, "LoadBalancer", lb]
w.append(metrica("Web sanas y no sanas (deben ser 2 y 0)", 0, 8, [
    ["AWS/ApplicationELB", "HealthyHostCount", *TGD, {"label": "Sanas", "color": VERDE}],
    ["AWS/ApplicationELB", "UnHealthyHostCount", *TGD, {"label": "No sanas", "color": ROJO}]],
    vista="singleValue", estadistica="Minimum", extra={"setPeriodToTimeRange": False, "sparkline": True}))
w.append(metrica("Errores 5xx (rojo; más de 10 en 5 min dispara la alarma)", 8, 8, [
    ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", *LBD, {"label": "5xx del balanceador", "color": ROJO}],
    ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", *LBD, {"label": "5xx de la aplicación", "color": NARANJA}]],
    estadistica="Sum", periodo=300, extra={"yAxis": {"left": {"min": 0}}, "annotations": {"horizontal": [{"label": "alarma", "value": 10, "color": ROJO}]}}))
w.append(metrica("Peticiones y tiempo de respuesta", 16, 8, [
    ["AWS/ApplicationELB", "RequestCount", *LBD, {"label": "Peticiones", "stat": "Sum", "color": AZUL}],
    ["AWS/ApplicationELB", "TargetResponseTime", *LBD, {"label": "Respuesta (s)", "stat": "Average", "yAxis": "right", "color": NARANJA}]],
    periodo=300))
y += 6
# MAX(SEARCH(...)) y AVG(SEARCH(...)): una sola línea por concepto. Sin el MAX/AVG, cada instancia recreada con recrear-web dejaría su propia
# serie (las métricas de las terminadas siguen en CloudWatch unas semanas) y la leyenda se llenaría de IDs. Por instancia están las alarmas.
BUSQUEDA = "SEARCH('{AWS/EC2,InstanceId} MetricName=\"CPUUtilization\"', 'Average', 300)"
w.append(metrica("CPU de las EC2: la más alta y el promedio (alarma sobre 80 %)", 0, 8, [
    [{"expression": f"MAX({BUSQUEDA})", "id": "cpumax", "label": "La más alta de cualquier EC2", "color": ROJO}],
    [{"expression": f"AVG({BUSQUEDA})", "id": "cpuprom", "label": "Promedio de las EC2", "color": AZUL}]],
    periodo=300, extra={"yAxis": {"left": {"min": 0, "max": 100}}, "annotations": {"horizontal": [{"label": "alarma", "value": 80, "color": ROJO}]}}))
w.append(metrica("Base de datos: CPU y conexiones (alarma sobre 65 conexiones)", 8, 8, [
    ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", db, {"label": "CPU %", "color": AZUL}],
    ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", db, {"label": "Conexiones", "yAxis": "right", "color": NARANJA}]],
    periodo=300))
w.append(metrica("Base de datos: espacio libre (alarma bajo 2 GB)", 16, 8, [
    ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", db, {"label": "Libre (bytes)", "color": VERDE}]],
    estadistica="Minimum", periodo=300, extra={"annotations": {"horizontal": [{"label": "2 GB", "value": 2147483648, "color": ROJO}]}}))
print(json.dumps({"widgets": w}))
PY
)"

if [ "$VISTA" = 1 ]; then echo "$DEFINICION" | python3 -m json.tool; echo "(vista previa: no se creó nada)" >&2; exit 0; fi
aws cloudwatch put-dashboard --dashboard-name "$NOMBRE" --dashboard-body "$DEFINICION" --query 'DashboardValidationMessages' --output text >/dev/null
echo "Panel «$NOMBRE» listo."
echo "  https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards/dashboard/${NOMBRE}"
echo "  (se abre desde la consola de AWS del laboratorio: AWS Academy > AWS)"
