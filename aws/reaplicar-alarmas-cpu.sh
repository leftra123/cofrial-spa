#!/usr/bin/env bash
# Reapunta las alarmas de CPU de las EC2 (cofrial-ec2-web-cpu, cofrial-ec2-web-b-cpu, cofrial-ec2-iot-cpu) a las instancias que viven AHORA.
#
# Por qué: una alarma de CPU se ata al ID de la instancia, y recrear-web o recrear-iot cambian los IDs: la alarma queda apuntando a una máquina que
# ya no existe y, sin datos, nunca avisa. Este script solo REAPUNTA alarmas que ya existen (mismos parámetros que aws/endurecer.sh alarmas, y conserva
# sus acciones de aviso si las tienen); no crea alarmas nuevas: si una no existe, lo dice y deja su creación a `endurecer.sh alarmas`.
#
#   bash aws/reaplicar-alarmas-cpu.sh            # vista previa: muestra qué cambiaría
#   bash aws/reaplicar-alarmas-cpu.sh --aplicar  # reapunta las que estén desfasadas
#
# Lo llaman solos `provision.sh recrear-web|recrear-iot` (al terminar) y, con tu consentimiento, `activar.sh`.
set -euo pipefail

export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
P=cofrial
APLICAR=0
case "${1:-}" in
  "") ;;
  --aplicar) APLICAR=1;;
  -h|--help) sed -n '2,12p' "$0"; exit 0;;
  *) echo "Opción desconocida: $1 (usa --aplicar o --help)"; exit 2;;
esac
command -v aws >/dev/null || { echo "Falta la AWS CLI v2."; exit 1; }

q() { aws "$@" --output text 2>/dev/null; }
cambios=0; fallos=0
for n in web web-b iot; do
  alarma="${P}-ec2-$n-cpu"
  id="$(q ec2 describe-instances --filters "Name=tag:Name,Values=${P}-ec2-$n" "Name=instance-state-name,Values=running,pending" --query 'Reservations[0].Instances[0].InstanceId' || echo None)"
  if [ -z "$id" ] || [ "$id" = None ]; then echo "  ${P}-ec2-$n: no hay instancia encendida, no toco su alarma."; continue; fi
  actual="$(q cloudwatch describe-alarms --alarm-names "$alarma" --query 'MetricAlarms[0].Dimensions[0].Value' || echo None)"
  if [ -z "$actual" ] || [ "$actual" = None ]; then echo "  $alarma: la alarma no existe (la crea: bash aws/endurecer.sh alarmas --aplicar)."; continue; fi
  if [ "$actual" = "$id" ]; then echo "  $alarma: ya apunta a $id."; continue; fi
  cambios=$((cambios+1))
  # Se conservan los avisos (SNS) que tuviera la alarma; cada lista vacía se omite.
  extra=()
  alarm_actions="$(q cloudwatch describe-alarms --alarm-names "$alarma" --query 'MetricAlarms[0].AlarmActions' || true)"
  ok_actions="$(q cloudwatch describe-alarms --alarm-names "$alarma" --query 'MetricAlarms[0].OKActions' || true)"
  [ -n "$alarm_actions" ] && [ "$alarm_actions" != None ] && extra+=(--alarm-actions $alarm_actions)
  [ -n "$ok_actions" ] && [ "$ok_actions" != None ] && extra+=(--ok-actions $ok_actions)
  if [ "$APLICAR" = 1 ]; then
    if aws cloudwatch put-metric-alarm --alarm-name "$alarma" --alarm-description "CPU de ${P}-ec2-$n sobre 80 % durante 10 minutos" --namespace AWS/EC2 \
        --metric-name CPUUtilization --statistic Average --period 300 --evaluation-periods 2 --threshold 80 --comparison-operator GreaterThanThreshold \
        --treat-missing-data notBreaching --dimensions "Name=InstanceId,Value=$id" ${extra[@]+"${extra[@]}"} >/dev/null 2>&1
    then echo "  $alarma: reapuntada de $actual a $id."; else echo "  $alarma: NO se pudo reapuntar (¿permisos?). Prueba: bash aws/endurecer.sh alarmas --aplicar"; fallos=$((fallos+1)); fi
  else echo "  $alarma: apunta a $actual y debería apuntar a $id (vista previa: repite con --aplicar)."; fi
done
[ "$cambios" = 0 ] && echo "  Las alarmas de CPU ya apuntan a las instancias vivas."
[ "$fallos" = 0 ]
