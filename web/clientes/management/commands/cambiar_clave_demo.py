"""Pone una clave a las cuentas de demostración: DEMO_PASSWORD al personal y a los clientes, y ADMIN_PASSWORD (si está definida) a las
cuentas administradoras (admin@ y eric@). Es un comando MANUAL: ya no corre al arrancar el contenedor, para que una clave cambiada desde
adentro (administración de Django o «Cambiar mi clave») no se revierta en cada reinicio.

    DEMO_PASSWORD=la-nueva ADMIN_PASSWORD=la-del-admin python manage.py cambiar_clave_demo      # o sin variables: pide la clave por teclado
    python manage.py cambiar_clave_demo --cuenta ana@correo.test                                  # solo una cuenta

Las reglas de calidad rechazan claves comunes como 12345678; --permitir-clave-debil las omite (solo demostraciones con datos ficticios).
"""
import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

ADMINISTRADORES = ["admin@cofrial.cl", "eric@cofrial.cl"]
DEMO_USUARIOS = ["admin@cofrial.cl", "felipe@cofrial.cl", "sergio@cofrial.cl", "eric@cofrial.cl", "abastecimiento@hospital.test", "ana@correo.test", "vendedora@cofrial.cl", "vendedor2@cofrial.cl",
                 "gerencia@cofrial.cl", "despacho@cofrial.cl"]


class Command(BaseCommand):
    help = "Cambia la clave de todas las cuentas de demostración a la de DEMO_PASSWORD (o la pide por teclado)."

    def add_arguments(self, p):
        p.add_argument("--si-hay-clave", action="store_true", help="no hacer nada (sin error) si DEMO_PASSWORD no está definida")
        p.add_argument("--cuenta", help="cambiar solo esta cuenta de demostración")
        p.add_argument("--permitir-clave-debil", action="store_true",
                       help="no aplicar las reglas de calidad de clave (largo mínimo, claves comunes). Solo para demostraciones con datos ficticios")

    def handle(self, *args, si_hay_clave, permitir_clave_debil, cuenta=None, **opciones):
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
            u.set_password(clave_admin if u.username in ADMINISTRADORES else clave)
            u.save(update_fields=["password"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Clave actualizada en {n} cuenta(s) de demostración."))
