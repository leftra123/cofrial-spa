"""Restablece la clave de las cuentas de demostración. Cada cuenta recibe su clave propia, derivada de DEMO_PASSWORD (o de ADMIN_PASSWORD
para admin@ y eric@) y de su nombre de usuario: la misma que muestra la hoja (python3 web/clientes/cuentas_demo.py). Es un comando
MANUAL: no corre al arrancar el contenedor, para que una clave cambiada desde adentro (administración o «Cambiar mi clave») no se revierta.

    DEMO_PASSWORD=la-base ADMIN_PASSWORD=la-del-admin python manage.py cambiar_clave_demo       # o sin variables: pide la base por teclado
    python manage.py cambiar_clave_demo --cuenta ana@correo.test                                  # solo una cuenta
    python manage.py cambiar_clave_demo --misma                                                   # la misma clave en todas (como antes)
    printf '%s\\n' "$CLAVE" | python manage.py cambiar_clave_demo --clave-stdin --todos-los-activos --permitir-clave-debil
                                                  # la misma clave simple en TODOS los usuarios activos (aws/activar.sh --clave-unica)

Las reglas de calidad rechazan bases comunes como 12345678; --permitir-clave-debil las omite (solo demostraciones con datos ficticios).
"""
import getpass
import os
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from clientes.cuentas_demo import ADMINISTRADORES, USUARIOS as DEMO_USUARIOS, clave_de

LARGO_MINIMO_SIMPLE = 4     # aun con --permitir-clave-debil: una clave de 1 o 2 caracteres no es una clave


class Command(BaseCommand):
    help = "Restablece la clave de las cuentas de demostración: una propia por cuenta, derivada de DEMO_PASSWORD (o --misma, o --todos-los-activos)."

    def add_arguments(self, p):
        p.add_argument("--si-hay-clave", action="store_true", help="no hacer nada (sin error) si DEMO_PASSWORD no está definida")
        p.add_argument("--cuenta", help="cambiar solo esta cuenta de demostración")
        p.add_argument("--misma", action="store_true", help="poner la misma clave (DEMO_PASSWORD) en todas, en vez de una propia por cuenta")
        p.add_argument("--permitir-clave-debil", action="store_true",
                       help="no aplicar las reglas de calidad de clave (largo mínimo, claves comunes). Solo para demostraciones con datos ficticios")
        p.add_argument("--clave-stdin", action="store_true",
                       help="leer la clave nueva de la entrada estándar (una línea): no queda en los argumentos, en el entorno ni en el historial")
        p.add_argument("--todos-los-activos", action="store_true",
                       help="la misma clave para TODOS los usuarios activos (clientes, equipo y administración), no solo las cuentas de demostración")

    def handle(self, *args, si_hay_clave, permitir_clave_debil, misma=False, cuenta=None, clave_stdin=False, todos_los_activos=False, **opciones):
        if todos_los_activos and cuenta:
            raise CommandError("--todos-los-activos no se combina con --cuenta.")
        if clave_stdin:
            clave = sys.stdin.readline().rstrip("\r\n")
            if not clave:
                raise CommandError("No llegó ninguna clave por la entrada estándar.")
        else:
            clave = os.environ.get("DEMO_PASSWORD")
            if not clave:
                if si_hay_clave:
                    return
                clave = getpass.getpass("Nueva clave de demostración: ")
        if todos_los_activos or clave_stdin:
            if len(clave) < LARGO_MINIMO_SIMPLE or any(c.isspace() for c in clave):
                raise CommandError(f"La clave debe tener al menos {LARGO_MINIMO_SIMPLE} caracteres y ningún espacio.")
            # cargar_demo devuelve a su clave propia las cuentas que siguen con DEMO_PASSWORD o ADMIN_PASSWORD (las toma por «sin cambiar»):
            # con una clave igual a esas, la nueva se revertiría en la próxima carga.
            comunes = {v for v in (os.environ.get("DEMO_PASSWORD"), os.environ.get("ADMIN_PASSWORD")) if v}
            if clave in comunes:
                raise CommandError("Esa clave es igual a DEMO_PASSWORD o ADMIN_PASSWORD: cargar_demo la volvería a cambiar. Elige otra.")
        if permitir_clave_debil:
            self.stdout.write(self.style.WARNING("Aviso: se omiten las reglas de calidad de clave; úsese solo en demostraciones con datos ficticios."))
        else:
            try:
                validate_password(clave)
            except ValidationError as e:
                raise CommandError("Clave no válida: " + " ".join(e.messages) + " (para una demostración, --permitir-clave-debil)")
        if todos_los_activos:
            self._a_todos_los_activos(clave)
            return
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

    def _a_todos_los_activos(self, clave):
        """Misma clave en cada usuario activo. Cada uno guarda su propio hash (sal distinta). Nunca imprime la clave."""
        activos = list(get_user_model().objects.filter(is_active=True))
        for u in activos:
            u.set_password(clave)
            u.save(update_fields=["password"])
        equipo = sum(1 for u in activos if u.is_staff or u.is_superuser)
        self.stdout.write(self.style.SUCCESS(f"La misma clave quedó en {len(activos)} usuario(s) activo(s), {equipo} de ellos del equipo o administración."))
        self.stdout.write("Las cuentas bloqueadas por intentos fallidos siguen bloqueadas hasta que pase la ventana (15 min) o se reinicie la web.")
