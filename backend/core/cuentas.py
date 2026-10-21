"""Cuentas de clientes: inicio de sesión, registro B2C y protección de las vistas.

Se usa la tabla `usuario` del modelo de datos (contraseña con los hashers de Django, PBKDF2).
La sesión guarda solo `usuario_id`.
"""
import re
from functools import wraps

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Cliente, Direccion, TipoCliente, Usuario

MAX_INTENTOS = 5
VENTANA_SEG = 15 * 60
# Hash de relleno: se verifica igual cuando el correo no existe, para no revelar qué cuentas hay por el tiempo de respuesta
_HASH_RELLENO = make_password("relleno-no-valido")


class ErrorCuenta(Exception):
    pass


def normalizar_rut(texto):
    """Devuelve el RUT como 12345678-5 si el dígito verificador es correcto; si no, None."""
    limpio = re.sub(r"[^0-9kK]", "", texto or "").upper()
    if len(limpio) < 2 or not limpio[:-1].isdigit():
        return None
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma, mult = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - suma % 11
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    if dv != esperado:
        return None
    n = int(cuerpo)
    return f"{n:,}".replace(",", ".") + "-" + dv


def cliente_de_sesion(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return None
    return Cliente.objects.select_related("tipo_cliente").filter(usuario_id=uid).first()


def login_requerido(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if cliente_de_sesion(request) is None:
            return redirect(f"{reverse('entrar')}?next={request.get_full_path()}")
        return vista(request, *args, **kwargs)
    return envoltura


def destino_seguro(request, destino, por_defecto="catalogo"):
    """Evita redirecciones abiertas: solo se acepta una ruta de este mismo sitio."""
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return reverse(por_defecto)


def _clave_intentos(request, email):
    ip = request.META.get("REMOTE_ADDR", "")
    return f"login:{ip}:{email.lower()}"


def iniciar_sesion(request, email, password):
    email = (email or "").strip()
    clave = _clave_intentos(request, email)
    if cache.get(clave, 0) >= MAX_INTENTOS:
        raise ErrorCuenta("Demasiados intentos. Espera 15 minutos antes de volver a probar.")
    usuario = Usuario.objects.filter(email__iexact=email, activo=True, rol="cliente").first()
    ok = check_password(password or "", usuario.password_hash if usuario else _HASH_RELLENO)
    if not (usuario and ok):
        cache.set(clave, cache.get(clave, 0) + 1, VENTANA_SEG)
        raise ErrorCuenta("El correo o la contraseña no coinciden.")
    cache.delete(clave)
    request.session.cycle_key()  # nueva sesión al entrar: evita la fijación de sesión
    request.session["usuario_id"] = usuario.usuario_id


def cerrar_sesion(request):
    request.session.flush()


def registrar_b2c(nombre, rut, email, password, calle_numero, comuna_id):
    """Cuenta rápida de un cliente particular (B2C). Los B2B los crea Cofrial con el RUT de la empresa."""
    nombre, email, calle_numero = (nombre or "").strip(), (email or "").strip().lower(), (calle_numero or "").strip()
    rut_ok = normalizar_rut(rut)
    if not nombre or not calle_numero or not comuna_id:
        raise ErrorCuenta("Completa tu nombre, dirección y comuna.")
    if rut_ok is None:
        raise ErrorCuenta("El RUT no es válido.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ErrorCuenta("Escribe un correo válido.")
    try:
        validate_password(password)
    except ValidationError as exc:
        raise ErrorCuenta(" ".join(exc.messages))
    tipo = TipoCliente.objects.get(codigo="B2C")
    try:
        with transaction.atomic():
            usuario = Usuario.objects.create(email=email, password_hash=make_password(password), rol="cliente")
            cliente = Cliente.objects.create(usuario_id=usuario.usuario_id, tipo_cliente=tipo, rut=rut_ok, nombre=nombre, email=email)
            Direccion.objects.create(cliente=cliente, calle_numero=calle_numero, comuna_id=comuna_id, es_principal=True)
    except IntegrityError:
        raise ErrorCuenta("Ya existe una cuenta con ese correo o RUT.")
    return usuario
