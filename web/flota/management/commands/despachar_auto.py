"""Despacho sin personas (flota/autodespacho.py). Sin opciones hace una pasada; --bucle es lo que corre el servicio `despachador`."""
import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from flota import autodespacho

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Agrupa los pedidos en espera y los despacha con las reglas de «Armar despacho»."

    def add_arguments(self, parser):
        parser.add_argument("--bucle", action="store_true", help="Revisa cada DESPACHO_AUTO_INTERVALO_SEG. Exige DESPACHO_AUTO=1.")
        parser.add_argument("--forzar", action="store_true", help="No espera a que los grupos se completen. Solo para una pasada.")

    def _pasada(self, forzar=False):
        r = autodespacho.ejecutar(forzar=forzar)
        for d in r["despachos"]:
            self.stdout.write(f"Despacho N.º {d.despacho_id} con {d.camion_id}: {d.decision_auto}")
        for o in r["omitidos"]:
            self.stdout.write(f"Omitido {o['camion']}: {' '.join(o['mensajes'])}")
        return r

    def handle(self, *args, **opciones):
        if not opciones["bucle"]:
            r = self._pasada(opciones["forzar"])
            self.stdout.write(f"Pasada lista: {len(r['despachos'])} despachos.")
            return
        if not autodespacho.activo():
            raise CommandError("El despacho automático está apagado: define DESPACHO_AUTO=1.")
        self.stdout.write(f"Despacho automático encendido: revisa cada {autodespacho.intervalo_seg()} s.")
        while True:
            close_old_connections()
            try:
                self._pasada()
            except Exception:                  # base reiniciándose o aún sin migrar: la próxima pasada reintenta y el servicio sigue vivo
                log.exception("Falló una pasada del despacho automático")
            time.sleep(autodespacho.intervalo_seg())
