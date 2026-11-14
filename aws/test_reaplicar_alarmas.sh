#!/usr/bin/env bash
# Prueba SIN tocar AWS de aws/reaplicar-alarmas-cpu.sh con un `aws` falso: reapunta solo las alarmas de CPU desfasadas, conserva sus avisos,
# no crea alarmas que no existían, no toca nada en vista previa y falla con código distinto de 0 si AWS rechaza el cambio.
#   bash aws/test_reaplicar_alarmas.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/st"
fallo() { echo "FALLA: $*"; exit 1; }
cat > "$TMP/bin/aws" <<'FAKE'
#!/usr/bin/env bash
A="$*"; ST="$AWS_ST"
nombre_ec2() { echo "$A" | sed -n 's/.*Values=\(cofrial-ec2-[a-z-]*\) .*/\1/p'; }
alarma() { echo "$A" | sed -n 's/.*--alarm-names \([^ ]*\).*/\1/p'; }
leer() { [ -f "$ST/$1" ] && cat "$ST/$1" || echo None; }
case "$A" in
  "ec2 describe-instances"*) leer "inst-$(nombre_ec2)";;
  "cloudwatch describe-alarms"*"Dimensions[0].Value"*) leer "dim-$(alarma)";;
  "cloudwatch describe-alarms"*"OKActions"*) leer "ok-$(alarma)";;
  "cloudwatch describe-alarms"*"AlarmActions"*) leer "acc-$(alarma)";;
  "cloudwatch put-metric-alarm"*) [ -f "$ST/put-falla" ] && { echo "AccessDenied" >&2; exit 255; }; echo "$A" >> "$ST/put.log";;
  *) echo "aws falso: no sé qué hacer con: $A" >&2; exit 99;;
esac
FAKE
chmod +x "$TMP/bin/aws"
reset() {
  rm -f "$TMP/st/"*
  for n in web web-b iot; do echo "i-nueva-$n" > "$TMP/st/inst-cofrial-ec2-$n"; echo "i-nueva-$n" > "$TMP/st/dim-cofrial-ec2-$n-cpu"; done
}
correr() { set +e; SAL="$(PATH="$TMP/bin:$PATH" AWS_ST="$TMP/st" bash "$AQUI/reaplicar-alarmas-cpu.sh" "$@" 2>&1)"; RC=$?; set -e; }

# 1) todo al día: no cambia nada
reset; correr --aplicar
[ "$RC" = 0 ] && [ ! -f "$TMP/st/put.log" ] && echo "$SAL" | grep -q "ya apuntan a las instancias vivas" || fallo "1: con todo al día no debía cambiar nada: $SAL"
echo "ok: alarmas al día -> no toca nada"

# 2) una alarma desfasada: se reapunta SOLO esa, con los mismos parámetros
reset; echo "i-vieja" > "$TMP/st/dim-cofrial-ec2-web-cpu"; correr --aplicar
[ "$RC" = 0 ] || fallo "2: debía salir 0 y salió $RC: $SAL"
[ "$(wc -l < "$TMP/st/put.log" | tr -d ' ')" = 1 ] || fallo "2: debía reapuntar exactamente 1 alarma: $(cat "$TMP/st/put.log")"
grep -q -- "--alarm-name cofrial-ec2-web-cpu" "$TMP/st/put.log" && grep -q "Name=InstanceId,Value=i-nueva-web" "$TMP/st/put.log" || fallo "2: no reapuntó web a la instancia nueva"
grep -q -- "--threshold 80" "$TMP/st/put.log" && grep -q -- "--evaluation-periods 2" "$TMP/st/put.log" && grep -q -- "--treat-missing-data notBreaching" "$TMP/st/put.log" || fallo "2: no conservó los parámetros de endurecer.sh"
echo "$SAL" | grep -q "reapuntada de i-vieja a i-nueva-web" || fallo "2: faltó el mensaje: $SAL"
echo "ok: una alarma desfasada -> se reapunta solo esa, con los mismos parámetros"

# 3) vista previa: no cambia nada y lo dice
reset; echo "i-vieja" > "$TMP/st/dim-cofrial-ec2-web-b-cpu"; correr
[ "$RC" = 0 ] && [ ! -f "$TMP/st/put.log" ] && echo "$SAL" | grep -q "vista previa" || fallo "3: la vista previa no debía cambiar nada: $SAL"
echo "ok: sin --aplicar solo muestra lo que cambiaría"

# 4) la alarma no existe: no la crea (eso es de endurecer.sh)
reset; rm -f "$TMP/st/dim-cofrial-ec2-iot-cpu"; correr --aplicar
[ "$RC" = 0 ] && [ ! -f "$TMP/st/put.log" ] && echo "$SAL" | grep -q "la alarma no existe" || fallo "4: no debía crear una alarma inexistente: $SAL"
echo "ok: alarma inexistente -> no se crea, se avisa"

# 5) conserva los avisos (SNS) de la alarma
reset; echo "i-vieja" > "$TMP/st/dim-cofrial-ec2-iot-cpu"; echo "arn:aws:sns:us-east-1:1:cofrial-alarmas" > "$TMP/st/acc-cofrial-ec2-iot-cpu"; echo "arn:aws:sns:us-east-1:1:cofrial-alarmas" > "$TMP/st/ok-cofrial-ec2-iot-cpu"; correr --aplicar
grep -q -- "--alarm-actions arn:aws:sns:us-east-1:1:cofrial-alarmas" "$TMP/st/put.log" && grep -q -- "--ok-actions arn:aws:sns:us-east-1:1:cofrial-alarmas" "$TMP/st/put.log" || fallo "5: no conservó los avisos de la alarma: $(cat "$TMP/st/put.log")"
echo "ok: conserva los avisos de la alarma"

# 6) sin instancia encendida: no toca su alarma
reset; rm -f "$TMP/st/inst-cofrial-ec2-web-b"; echo "i-vieja" > "$TMP/st/dim-cofrial-ec2-web-b-cpu"; correr --aplicar
[ "$RC" = 0 ] && [ ! -f "$TMP/st/put.log" ] && echo "$SAL" | grep -q "no hay instancia encendida" || fallo "6: sin instancia no debía tocar la alarma: $SAL"
echo "ok: sin instancia encendida -> no toca su alarma"

# 7) AWS rechaza el cambio: sale 1 con el comando manual
reset; echo "i-vieja" > "$TMP/st/dim-cofrial-ec2-web-cpu"; touch "$TMP/st/put-falla"; correr --aplicar
[ "$RC" = 1 ] && echo "$SAL" | grep -q "NO se pudo reapuntar" && echo "$SAL" | grep -q "endurecer.sh alarmas --aplicar" || fallo "7: un rechazo de AWS debía salir 1 con el comando manual: $RC $SAL"
echo "ok: AWS rechaza -> sale 1 y dice qué hacer"

# 8) opción desconocida
reset; correr --nada; [ "$RC" = 2 ] || fallo "8: opción desconocida debía salir 2"
echo "ok: opción desconocida -> código 2"
echo "TODO OK"
