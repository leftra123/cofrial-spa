"""Crea una cuenta de acceso con su rol. La clave se pide por teclado (no queda en el historial ni en la pantalla).

    python manage.py crear_cuenta jefa@cofrial.test --rol vendedor --nombre "Camila Soto"
    python manage.py crear_cuenta compras@hotel.test --rol cliente-b2b --nombre "Hotel Villarrica" --rut 76.111.222-3 \
        --direccion "Av. Pedro de Valdivia 100" --comuna Temuco --vendedor vendedora@cofrial.test
    python manage.py crear_cuenta ana2@correo.test --rol cliente-b2c --nombre "Ana Díaz" --rut 11.222.333-4 --direccion "Calle 1 123"

Roles: cliente-b2b, cliente-b2c, vendedor, gerencia, despachador, admin. Para automatizar (por ejemplo en pruebas) la clave
puede venir de la variable CUENTA_CLAVE. Las mismas cuentas se pueden crear desde la web de administración (/admin/).
"""
import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente, Comuna, Direccion, TipoCliente, Vendedor

GRUPOS = {"vendedor": "vendedores", "gerencia": "gerencia", "despachador": "despachadores"}


class Command(BaseCommand):
    help = "Crea una cuenta de acceso (cliente B2B o B2C, vendedor, gerencia, despachador o administrador)."

    def add_arguments(self, p):
        p.add_argument("usuario", help="nombre de usuario; por convención, un correo")
        p.add_argument("--rol", required=True, choices=["cliente-b2b", "cliente-b2c", "vendedor", "gerencia", "despachador", "admin"])
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
        try:
            validate_password(clave)
        except ValidationError as e:
            raise CommandError("Clave no válida: " + " ".join(e.messages))
        return clave

    def handle(self, *args, usuario, rol, nombre, rut, direccion, comuna, vendedor, **opciones):
        Usuario = get_user_model()
        if Usuario.objects.filter(username=usuario).exists():
            raise CommandError(f"El usuario {usuario} ya existe. Para cambiar su clave: python manage.py changepassword {usuario}")
        cliente = rol.startswith("cliente")
        if cliente:
            if not (nombre and rut and direccion):
                raise CommandError("Un cliente necesita --nombre, --rut y --direccion.")
            if Cliente.objects.filter(rut=rut).exists():
                raise CommandError(f"Ya existe un cliente con el RUT {rut}.")
            cmn = Comuna.objects.filter(nombre__iexact=comuna).first()
            if not cmn:
                raise CommandError(f"La comuna «{comuna}» no existe. Disponibles: " + ", ".join(Comuna.objects.values_list("nombre", flat=True)))
            tipo = TipoCliente.objects.get(codigo="B2B" if rol == "cliente-b2b" else "B2C")
            asignado = None
            if vendedor:
                asignado = Vendedor.objects.filter(usuario__username=vendedor).first()
                if not asignado:
                    raise CommandError(f"El vendedor {vendedor} no existe.")
        elif not nombre and rol == "vendedor":
            raise CommandError("Un vendedor necesita --nombre.")
        clave = self._clave()

        if rol == "admin":
            u = Usuario.objects.create_superuser(usuario, usuario if "@" in usuario else "", clave)
        else:
            u = Usuario.objects.create_user(usuario, email=usuario if "@" in usuario else "", password=clave)
            u.is_staff = not cliente           # el personal entra a /admin/; los clientes no
            u.save(update_fields=["is_staff"])
        if rol in GRUPOS:
            u.groups.add(Group.objects.get_or_create(name=GRUPOS[rol])[0])
        if rol == "vendedor":
            Vendedor.objects.create(usuario=u, nombre=nombre)
        if cliente:
            c = Cliente.objects.create(usuario=u, tipo_cliente=tipo, vendedor=asignado, rut=rut, nombre=nombre, email=usuario if "@" in usuario else "")
            Direccion.objects.create(cliente=c, calle_numero=direccion, comuna=cmn, es_principal=True)
        self.stdout.write(self.style.SUCCESS(f"Cuenta {usuario} creada con el rol {rol}."))
