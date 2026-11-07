"""Borra la telemetría normal antigua para que la tabla no crezca sin límite (unas 864 000 filas al día con 50 camiones)."""
import os
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from flota.models import Despacho, Telemetria

DIAS_POR_DEFECTO = 7
PAUSA_ENTRE_LOTES_SEG = 0.2      # deja respirar a la base: el simulador y el tablero siguen trabajando mientras tanto


def lecturas_prescindibles(corte):
    """Lecturas normales anteriores al corte. Se conservan las alertas (RN-13 y el tablero), las forzadas de la demostración,
    las tomadas durante un viaje (se cruzan con los reclamos) y la última de cada camión (la usa la flota)."""
    durante_un_viaje = Despacho.objects.filter(camion_id=OuterRef("camion_id"), salida_en__lte=OuterRef("registrado_en")).filter(
        Q(llegada_en__isnull=True) | Q(llegada_en__gte=OuterRef("registrado_en")))
    ultimas = Telemetria.objects.order_by("camion_id", "-registrado_en").distinct("camion_id").values_list("pk", flat=True)
    return (Telemetria.objects.filter(registrado_en__lt=corte, alerta_ruptura_frio=False, forzada=False)
            .exclude(pk__in=list(ultimas)).filter(~Exists(durante_un_viaje)))


class Command(BaseCommand):
    help = "Borra las lecturas normales de telemetría más antiguas que RETENCION_TELEMETRIA_DIAS (7 por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, help="Días que se conservan; por defecto RETENCION_TELEMETRIA_DIAS o 7.")
        parser.add_argument("--lote", type=int, default=5000, help="Filas por borrado.")
        parser.add_argument("--simular", action="store_true", help="Solo cuenta lo que borraría.")

    def _dias(self, opciones):
        valor = opciones["dias"] if opciones["dias"] is not None else os.environ.get("RETENCION_TELEMETRIA_DIAS") or DIAS_POR_DEFECTO
        try:
            dias = int(valor)
        except ValueError:
            raise CommandError(f"Los días de retención deben ser un número entero: {valor!r}")
        if dias < 1:
            raise CommandError("Los días de retención deben ser 1 o más.")
        return dias

    def handle(self, *args, **opciones):
        dias, lote = self._dias(opciones), opciones["lote"]
        if lote < 1:
            raise CommandError("El lote debe ser de 1 fila o más.")
        lecturas = lecturas_prescindibles(timezone.now() - timedelta(days=dias))
        if opciones["simular"]:
            self.stdout.write(f"Se borrarían {lecturas.count()} lecturas de más de {dias} días.")
            return
        borradas, ultimo = 0, 0
        while True:
            ids = list(lecturas.filter(pk__gt=ultimo).order_by("pk").values_list("pk", flat=True)[:lote])
            if ids:
                Telemetria.objects.filter(pk__in=ids).delete()
                borradas, ultimo = borradas + len(ids), ids[-1]
            if len(ids) < lote:
                break
            time.sleep(PAUSA_ENTRE_LOTES_SEG)
        self.stdout.write(self.style.SUCCESS(f"Telemetría podada: {borradas} lecturas de más de {dias} días."))
