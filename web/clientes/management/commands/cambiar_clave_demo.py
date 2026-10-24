"""Pone una misma clave a todas las cuentas de demostración. Sirve para rotarla (por ejemplo, tras compartirla por error).

    DEMO_PASSWORD=la-nueva python manage.py cambiar_clave_demo      # o sin variable: la pide por teclado

Las reglas de calidad rechazan claves como 123456; --permitir-clave-debil las omite (solo demostraciones con datos ficticios).
En AWS el contenedor web lo ejecuta en cada arranque si DEMO_PASSWORD está definida, así que basta cambiar esa variable en
aws/.estado/secretos.env y ejecutar `bash aws/provision.sh recrear-web`. Solo toca las cuentas de demostración listadas aquí.
"""
import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

DEMO_USUARIOS = ["admin@cofrial.cl", "abastecimiento@hospital.test", "ana@correo.test", "vendedora@cofrial.cl", "vendedor2@cofrial.cl",
                 "gerencia@cofrial.cl", "despacho@cofrial.cl"]


class Command(BaseCommand):
    help = "Cambia la clave de todas las cuentas de demostración a la de DEMO_PASSWORD (o la pide por teclado)."

    def add_arguments(self, p):
        p.add_argument("--si-hay-clave", action="store_true", help="no hacer nada (sin error) si DEMO_PASSWORD no está definida")
        p.add_argument("--permitir-clave-debil", action="store_true",
                       help="no aplicar las reglas de calidad de clave (largo mínimo, claves comunes). Solo para demostraciones con datos ficticios")

    def handle(self, *args, si_hay_clave, permitir_clave_debil, **opciones):
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
        n = 0
        for u in get_user_model().objects.filter(username__in=DEMO_USUARIOS):
            u.set_password(clave)
            u.save(update_fields=["password"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Clave actualizada en {n} cuenta(s) de demostración."))
