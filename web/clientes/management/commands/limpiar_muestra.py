"""Deshace la siembra de clientes de muestra e historial (clientes/muestra.py): pedidos HIS-, sus facturas y pagos, clientes de muestra y prospectos nuevos."""
from django.core.management.base import BaseCommand

from clientes import muestra


class Command(BaseCommand):
    help = "Borra los clientes de muestra, su historial de pedidos (HIS-) y los prospectos nuevos de la Torre de control."

    def handle(self, *args, **opciones):
        for clave, cantidad in muestra.limpiar().items():
            self.stdout.write(f"{clave}: {cantidad}")
