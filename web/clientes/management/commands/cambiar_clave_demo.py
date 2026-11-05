"""Restablece la clave de las cuentas de demostración. Cada cuenta recibe su clave propia, derivada de DEMO_PASSWORD (o de ADMIN_PASSWORD
para admin@ y eric@) y de su nombre de usuario: la misma que muestra la hoja (python3 web/clientes/cuentas_demo.py). Es un comando
MANUAL: no corre al arrancar el contenedor, para que una clave cambiada desde adentro (administración o «Cambiar mi clave») no se revierta.

    DEMO_PASSWORD=la-base ADMIN_PASSWORD=la-del-admin python manage.py cambiar_clave_demo       # o sin variables: pide la base por teclado
    python manage.py cambiar_clave_demo --cuenta ana@correo.test                                  # solo una cuenta
    python manage.py cambiar_clave_demo --misma                                                   # la misma clave en todas (como antes)

Las reglas de calidad rechazan bases comunes como 12345678; --permitir-clave-debil las omite (solo demostraciones con datos ficticios).
"""
import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from clientes.cuentas_demo import ADMINISTRADORES, USUARIOS as DEMO_USUARIOS, clave_de


class Command(BaseCommand):
    help = "Restablece la clave de las cuentas de demostración: una propia por cuenta, derivada de DEMO_PASSWORD (o --misma)."

    def add_arguments(self, p):
        p.add_argument("--si-hay-clave", action="store_true", help="no hacer nada (sin error) si DEMO_PASSWORD no está definida")
        p.add_argument("--cuenta", help="cambiar solo esta cuenta de demostración")
        p.add_argument("--misma", action="store_true", help="poner la misma clave (DEMO_PASSWORD) en todas, en vez de una propia por cuenta")
        p.add_argument("--permitir-clave-debil", action="store_true",
                       help="no aplicar las reglas de calidad de clave (largo mínimo, claves comunes). Solo para demostraciones con datos ficticios")

    def handle(self, *args, si_hay_clave, permitir_clave_debil, misma=False, cuenta=None, **opciones):
        clave = os.environ.get("DEMO_PASSWORD")
        if not clave:
            if si_hay_clave:
                return
            clave = getpass.getpass("Nueva clave de demostración: ")
        if permitir_clave_debil:
            self.stdout.write(self.style.WARNING("Aviso: se omiten las reglas de calidad de clave; úsese solo en demostraciones con datos ficticios."))
        else:
            try:
                validate_password(clave)
            except ValidationError as e:
                raise CommandError("Clave no válida: " + " ".join(e.messages) + " (para una demostración, --permitir-clave-debil)")
        clave_admin = os.environ.get("ADMIN_PASSWORD") or clave
        if not permitir_clave_debil and clave_admin != clave:
            try:
                validate_password(clave_admin)
            except ValidationError as e:
                raise CommandError("Clave de administrador no válida: " + " ".join(e.messages))
        cuentas = [cuenta] if cuenta else DEMO_USUARIOS
        n = 0
        for u in get_user_model().objects.filter(username__in=cuentas):
            base = clave_admin if u.username in ADMINISTRADORES else clave
            u.set_password(base if misma else clave_de(u.username, base))
            u.save(update_fields=["password"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Clave actualizada en {n} cuenta(s) de demostración" + (" (la misma en todas)." if misma else
                                             " (una propia por cuenta: python3 web/clientes/cuentas_demo.py la muestra).")))
