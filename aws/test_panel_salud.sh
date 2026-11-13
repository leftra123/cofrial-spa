#!/usr/bin/env bash
# Prueba SIN tocar AWS de aws/panel-salud.sh con un `aws` falso: comprueba que arma un JSON válido con las alarmas, las dimensiones del
# balanceador y de la base, que NO depende de IDs de EC2, que la vista previa no crea nada y que los errores salen con código distinto de 0.
#   bash aws/test_panel_salud.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/st"
fallo() { echo "FALLA: $*"; exit 1; }
cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env bash
A="$*"; ST="$AWS_ST"; echo "$A" >> "$ST/llamadas"
case "$A" in
  "sts get-caller-identity"*) echo 111122223333;;
  "elbv2 describe-load-balancers"*) [ -f "$ST/sin-alb" ] && exit 255; echo "arn:aws:elasticloadbalancing:us-east-1:111122223333:loadbalancer/app/cofrial-alb/abc123";;
  "elbv2 describe-target-groups"*) echo "arn:aws:elasticloadbalancing:us-east-1:111122223333:targetgroup/cofrial-tg/def456";;
  "cloudwatch describe-alarms"*) cat "$ST/alarmas" 2>/dev/null || true;;
  "cloudwatch put-dashboard"*) n=""; b=""; set -- "$@"; while [ $# -gt 0 ]; do case "$1" in --dashboard-name) n="$2";; --dashboard-body) b="$2";; esac; shift; done; echo "$n" > "$ST/panel-nombre"; printf '%s' "$b" > "$ST/panel.json"; echo;;
  *) echo "aws falso: no sé qué hacer con: $A" >&2; exit 99;;
esac
FAKE
chmod +x "$TMP/bin/aws"
correr() { set +e; SAL="$(PATH="$TMP/bin:$PATH" AWS_ST="$TMP/st" "$@" 2>&1)"; RC=$?; set -e; }
reset() { rm -f "$TMP/st/"*; printf 'cofrial-alb-5xx\tcofrial-ec2-web-cpu\tcofrial-rds-cpu\n' > "$TMP/st/alarmas"; }

# 1) crear: nombre, JSON válido, alarmas con su ARN, dimensiones y sin IDs de EC2
reset; correr bash "$AQUI/panel-salud.sh"
[ "$RC" = 0 ] || fallo "1: debía salir 0 y salió $RC: $SAL"
[ "$(cat "$TMP/st/panel-nombre")" = cofrial-salud ] || fallo "1: nombre de panel incorrecto"
python3 - "$TMP/st/panel.json" <<'PY' || fallo "1: el JSON del panel no cumple lo esperado"
import json, sys
t = open(sys.argv[1]).read(); d = json.loads(t); w = d["widgets"]
assert [x["type"] for x in w] == ["text", "alarm"] + ["metric"] * 6, [x["type"] for x in w]
al = next(x for x in w if x["type"] == "alarm")["properties"]["alarms"]
assert al == [f"arn:aws:cloudwatch:us-east-1:111122223333:alarm:{n}" for n in ("cofrial-alb-5xx", "cofrial-ec2-web-cpu", "cofrial-rds-cpu")], al
assert "app/cofrial-alb/abc123" in t and "targetgroup/cofrial-tg/def456" in t and "cofrial-db" in t
assert "i-0" not in t and "i-c" not in t, "el panel no debe depender de IDs de EC2"
assert "SEARCH(" in t, "la CPU de las EC2 debe buscarse por métrica"
for x in w:
    assert x["x"] + x["width"] <= 24, x
print("ok")
PY
echo "ok: crea el panel con alarmas, balanceador, base y búsqueda de CPU (sin IDs de EC2)"

# 2) vista previa: imprime JSON y no crea nada
reset; correr bash "$AQUI/panel-salud.sh" --vista-previa
[ "$RC" = 0 ] && ! grep -q "put-dashboard" "$TMP/st/llamadas" || fallo "2: la vista previa no debía llamar a put-dashboard"
echo "$SAL" | grep -q '"widgets"' || fallo "2: la vista previa debía imprimir el JSON"
echo "ok: --vista-previa no crea nada"

# 3) sin alarmas: avisa y sale 0 sin el cuadro de alarmas
reset; : > "$TMP/st/alarmas"; correr bash "$AQUI/panel-salud.sh"
[ "$RC" = 0 ] && echo "$SAL" | grep -q "no hay alarmas" || fallo "3: debía avisar de que no hay alarmas: $SAL"
python3 -c "import json,sys; d=json.load(open('$TMP/st/panel.json')); assert all(x['type']!='alarm' for x in d['widgets'])" || fallo "3: sin alarmas no debía haber cuadro de alarmas"
echo "ok: sin alarmas avisa y arma el resto"

# 4) sin balanceador: falla con mensaje
reset; touch "$TMP/st/sin-alb"; correr bash "$AQUI/panel-salud.sh"
[ "$RC" = 1 ] && echo "$SAL" | grep -q "No encuentro el balanceador" || fallo "4: sin balanceador debía salir 1 con mensaje: $RC $SAL"
echo "ok: sin balanceador sale 1 con mensaje"

# 5) opción desconocida: código 2; nombre propio por variable
reset; correr bash "$AQUI/panel-salud.sh" --nada; [ "$RC" = 2 ] || fallo "5: opción desconocida debía salir 2"
reset; correr env PANEL_NOMBRE=otro bash "$AQUI/panel-salud.sh"; [ "$(cat "$TMP/st/panel-nombre")" = otro ] || fallo "5: PANEL_NOMBRE no se respetó"
echo "ok: opción desconocida -> 2; PANEL_NOMBRE respetado"
echo "TODO OK"
