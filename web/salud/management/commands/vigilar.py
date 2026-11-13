"""Vigilante de salud: revisa los componentes y guarda cada resultado (salud/servicios.py).
Sin opciones hace UNA ronda (útil para probar). --bucle es lo que corre el servicio `vigilante` de docker compose."""
import logging
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from salud import servicios

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Revisa web, base, IoT, Grafana, IA y pagos, y guarda el resultado para la página /salud/."

    def add_arguments(self, parser):
        parser.add_argument("--bucle", action="store_true", help="Repite cada SALUD_INTERVALO_SEG (60 por defecto).")
        parser.add_argument("--intervalo", type=int, default=60)

    def handle(self, *args, **opciones):
        pendientes = []
        if not opciones["bucle"]:
            n = servicios.ejecutar_ronda(pendientes)
            self.stdout.write(f"Ronda lista: {n} revisiones, {len(pendientes)} sin guardar.")
            return
        self.stdout.write(f"Vigilante encendido: ronda cada {opciones['intervalo']} s.")
        ultima_poda = None
        while True:
            inicio = time.monotonic()
            close_old_connections()
            try:
                servicios.ejecutar_ronda(pendientes)
                hoy = timezone.localdate()
                if ultima_poda != hoy:
                    servicios.podar()
                    ultima_poda = hoy
            except Exception:                      # el vigilante nunca debe morir: la próxima ronda reintenta
                log.exception("Falló una ronda del vigilante")
            time.sleep(max(1, opciones["intervalo"] - (time.monotonic() - inicio)))
