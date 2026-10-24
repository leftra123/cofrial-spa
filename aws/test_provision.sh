#!/usr/bin/env bash
# Prueba SIN tocar AWS de la lógica de `recrear-iot` y `recrear-web`: usa un `aws` falso que anota cada llamada y comprueba que se
# termina únicamente la instancia pedida y que no hay ninguna llamada a RDS, a la IP elástica ni a la otra EC2.
#   bash aws/test_provision.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
LOG="$TMP/llamadas.log"; : > "$LOG"

# aws falso: devuelve un id distinto según la etiqueta Name pedida y registra todo lo que recibe
cat > "$TMP/aws" <<'FAKE'
#!/usr/bin/env bash
echo "$*" >> "$AWS_LOG"
case "$*" in
  *"describe-instances"*"cofrial-ec2-iot"*) echo "i-IOT0001";;
  *"describe-instances"*"cofrial-ec2-web"*) echo "i-WEB0001";;
esac
exit 0
FAKE
chmod +x "$TMP/aws"
export AWS_LOG="$LOG" PATH="$TMP:$PATH"

# se extraen de provision.sh las definiciones reales de `q` y `terminar_ec2` (no una copia)
P=cofrial
eval "$(grep -E '^q\(\) ' "$AQUI/provision.sh")"
eval "$(sed -n '/^terminar_ec2() {/,/^}/p' "$AQUI/provision.sh")"

fallo() { echo "FALLO: $1"; echo "--- llamadas:"; cat "$LOG"; exit 1; }

terminar_ec2 "${P}-ec2-iot"
grep -q "terminate-instances --instance-ids i-IOT0001" "$LOG" || fallo "no terminó la EC2 IoT"
grep -q "i-WEB0001" "$LOG" && fallo "tocó la EC2 web al recrear la IoT"
grep -Eq "rds|release-address|associate-address|describe-addresses|delete-" "$LOG" && fallo "tocó RDS, la IP elástica o borró algo"
echo "ok: recrear-iot termina solo cofrial-ec2-iot (i-IOT0001) y no toca RDS, IP elástica ni la web"

: > "$LOG"
terminar_ec2 "${P}-ec2-web"
grep -q "terminate-instances --instance-ids i-WEB0001" "$LOG" || fallo "no terminó la EC2 web"
grep -q "i-IOT0001" "$LOG" && fallo "tocó la EC2 IoT al recrear la web"
echo "ok: recrear-web termina solo cofrial-ec2-web (i-WEB0001)"

# el subcomando existe y está documentado
grep -q 'if \[ "${1:-}" = "recrear-iot" \]' "$AQUI/provision.sh" || fallo "falta el subcomando recrear-iot"
grep -q 'bash aws/provision.sh recrear-iot' "$AQUI/provision.sh" || fallo "recrear-iot no está documentado en el encabezado"
bash -n "$AQUI/provision.sh" || fallo "provision.sh tiene errores de sintaxis"
echo "ok: el subcomando existe, está documentado y el script no tiene errores de sintaxis"
