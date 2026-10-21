import os

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from core.models import Usuario


class Command(BaseCommand):
    help = "Asigna una contraseña de prueba a los usuarios cliente del script datos_prueba.sql (solo desarrollo)."

    def handle(self, *args, **opts):
        clave = os.environ.get("DEMO_PASSWORD", "Cofrial2026!")
        n = Usuario.objects.filter(rol="cliente", password_hash__startswith="hash-de-prueba").update(password_hash=make_password(clave))
        self.stdout.write(f"Contraseña de prueba asignada a {n} usuario(s): {clave}")
