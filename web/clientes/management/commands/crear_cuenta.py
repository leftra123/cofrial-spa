"""Crea una cuenta de acceso con su rol. La clave se pide por teclado (no queda en el historial ni en la pantalla).

    python manage.py crear_cuenta jefa@cofrial.test --rol vendedor --nombre "Camila Soto"
    python manage.py crear_cuenta compras@hotel.test --rol cliente-b2b --nombre "Hotel Villarrica" --rut 76.111.222-8 \
        --direccion "Av. Pedro de Valdivia 100" --comuna Temuco --vendedor vendedora@cofrial.cl
    python manage.py crear_cuenta ana2@correo.test --rol cliente-b2c --nombre "Ana Díaz" --rut 11.222.333-9 --direccion "Calle 1 123"

Roles: cliente-b2b, cliente-b2c, vendedor, gerencia, despachador, admin. Para automatizar (por ejemplo en pruebas) la clave
puede venir de la variable CUENTA_CLAVE. Las mismas cuentas se crean desde la web: Operación > Crear cuenta (/operacion/cuentas/nueva/,
solo el administrador) o en /admin/. Las reglas están en clientes/cuentas.py y las comparten las tres puertas.
"""
import getpass
import os

from django.core.management.base import BaseCommand, CommandError

from clientes import cuentas

# Los mensajes de clientes/cuentas.py hablan de campos; aquí se dicen con las opciones de la línea de comandos.
TEXTOS = {"faltan_datos": "Un cliente necesita --nombre, --rut y --direccion.", "vendedor_sin_nombre": "Un vendedor necesita --nombre."}


class Command(BaseCommand):
    help = "Crea una cuenta de acceso (cliente B2B o B2C, vendedor, gerencia, despachador o administrador)."

    def add_arguments(self, p):
        p.add_argument("usuario", help="nombre de usuario; por convención, un correo")
        p.add_argument("--rol", required=True, choices=[r for r, _ in cuentas.ROLES])
        p.add_argument("--nombre", default="", help="nombre de la persona o empresa")
        p.add_argument("--rut", help="RUT del cliente (solo clientes)")
        p.add_argument("--direccion", help="calle y número de entrega (solo clientes)")
        p.add_argument("--comuna", default="Temuco", help="comuna de la dirección (debe existir; por defecto Temuco)")
        p.add_argument("--vendedor", help="usuario del vendedor asignado (clientes B2B)")

    def _clave(self):
        if os.environ.get("CUENTA_CLAVE"):
            clave = os.environ["CUENTA_CLAVE"]
        else:
            clave = getpass.getpass("Clave: ")
            if clave != getpass.getpass("Repite la clave: "):
                raise CommandError("Las claves no coinciden.")
        return clave

    def handle(self, *args, usuario, rol, nombre, rut, direccion, comuna, vendedor, **opciones):
        try:
            datos = cuentas.preparar(usuario, rol, nombre=nombre, rut=rut, direccion=direccion, comuna=comuna, vendedor=vendedor)
            clave = self._clave()                          # se pide recién con los datos ya validados
            cuentas.validar_clave(clave)
            cuentas.crear(datos, clave)
        except cuentas.ErrorCuenta as e:
            texto = TEXTOS.get(e.codigo, str(e))
            if e.codigo == "existe":
                texto += f" Para cambiar su clave: python manage.py changepassword {usuario}"
            raise CommandError(texto)
        self.stdout.write(self.style.SUCCESS(f"Cuenta {usuario} creada con el rol {rol}."))
