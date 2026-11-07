"""Alta de cuentas con su rol. La usan el comando `crear_cuenta` y la pantalla del administrador (`/operacion/cuentas/nueva/`):
las reglas viven aquí una sola vez y cada puerta de entrada solo pide los datos y muestra los errores a su manera.

    datos = preparar(usuario, rol, ...)   # valida todo menos la clave; lanza ErrorCuenta con un mensaje claro
    validar_clave(clave, usuario)         # validate_password de Django
    crear(datos, clave)                   # crea usuario, grupo y (según el rol) vendedor, cliente y dirección, todo o nada
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Cliente, Comuna, Direccion, TipoCliente, Vendedor

ROLES = [("cliente-b2b", "Cliente institucional (B2B)"), ("cliente-b2c", "Cliente particular (B2C)"), ("vendedor", "Vendedor"),
         ("gerencia", "Gerencia"), ("despachador", "Despachador"), ("admin", "Administrador")]
GRUPOS = {"vendedor": "vendedores", "gerencia": "gerencia", "despachador": "despachadores"}


class ErrorCuenta(Exception):
    """Un dato no sirve. `campo` es el campo del formulario a corregir (None si es del conjunto); `codigo` deja que cada puerta de
    entrada reescriba el mensaje a su estilo (el comando habla de --opciones; la pantalla, de campos)."""

    def __init__(self, mensaje, campo=None, codigo=None):
        super().__init__(mensaje)
        self.campo, self.codigo = campo, codigo


def validar_clave(clave, usuario=None):
    """La clave pasa los validadores de AUTH_PASSWORD_VALIDATORS. Con `usuario` (aunque no esté guardado) también se compara con su nombre y correo."""
    try:
        validate_password(clave, user=usuario)
    except ValidationError as e:
        raise ErrorCuenta("Clave no válida: " + " ".join(e.messages), campo="clave", codigo="clave")


def preparar(usuario, rol, nombre="", rut=None, direccion=None, comuna="Temuco", vendedor=None):
    """Valida los datos de una cuenta nueva y los deja listos para `crear`. No toca la base."""
    Usuario = get_user_model()
    try:
        Usuario._meta.get_field("username").run_validators(usuario)
    except ValidationError as e:
        raise ErrorCuenta(" ".join(e.messages), campo="usuario", codigo="usuario_invalido")
    if Usuario.objects.filter(username__iexact=usuario).exists():
        raise ErrorCuenta(f"El usuario {usuario} ya existe.", campo="usuario", codigo="existe")
    cliente = rol.startswith("cliente")
    datos = {"usuario": usuario, "rol": rol, "nombre": nombre, "cliente": cliente}
    if cliente:
        if not (nombre and rut and direccion):
            raise ErrorCuenta("Un cliente necesita nombre, RUT y dirección.", codigo="faltan_datos")
        if Cliente.objects.filter(rut=rut).exists():
            raise ErrorCuenta(f"Ya existe un cliente con el RUT {rut}.", campo="rut", codigo="rut_repetido")
        cmn = Comuna.objects.filter(nombre__iexact=comuna).first()
        if not cmn:
            raise ErrorCuenta(f"La comuna «{comuna}» no existe. Disponibles: " + ", ".join(Comuna.objects.values_list("nombre", flat=True)),
                              campo="comuna", codigo="comuna")
        asignado = None
        if vendedor:
            asignado = Vendedor.objects.filter(usuario__username=vendedor).first()
            if not asignado:
                raise ErrorCuenta(f"El vendedor {vendedor} no existe.", campo="vendedor", codigo="vendedor")
        datos.update(rut=rut, direccion=direccion, comuna=cmn, vendedor=asignado,
                     tipo=TipoCliente.objects.get(codigo="B2B" if rol == "cliente-b2b" else "B2C"))
    elif not nombre and rol == "vendedor":
        raise ErrorCuenta("Un vendedor necesita nombre.", campo="nombre", codigo="vendedor_sin_nombre")
    return datos


def crear(datos, clave):
    """Crea la cuenta con todo lo que su rol necesita, o nada. La clave se guarda con set_password (nunca en claro)."""
    Usuario = get_user_model()
    usuario, rol, nombre = datos["usuario"], datos["rol"], datos["nombre"]
    correo = usuario if "@" in usuario else ""
    try:
        with transaction.atomic():
            if rol == "admin":
                u = Usuario.objects.create_superuser(usuario, correo, clave)
            else:
                u = Usuario.objects.create_user(usuario, email=correo, password=clave)
                u.is_staff = not datos["cliente"]           # el personal entra a /admin/ si es superusuario; los clientes no
                u.save(update_fields=["is_staff"])
            if nombre and not datos["cliente"]:
                u.first_name = nombre[:150]
                u.save(update_fields=["first_name"])
            if rol in GRUPOS:
                u.groups.add(Group.objects.get_or_create(name=GRUPOS[rol])[0])
            if rol == "vendedor":
                Vendedor.objects.create(usuario=u, nombre=nombre)
            if datos["cliente"]:
                c = Cliente.objects.create(usuario=u, tipo_cliente=datos["tipo"], vendedor=datos["vendedor"], rut=datos["rut"], nombre=nombre, email=correo)
                Direccion.objects.create(cliente=c, calle_numero=datos["direccion"], comuna=datos["comuna"], es_principal=True)
    except IntegrityError:
        raise ErrorCuenta("La cuenta ya existe: alguien la creó al mismo tiempo.", codigo="existe")
    return u
