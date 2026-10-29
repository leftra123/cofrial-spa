"""Páginas generales de la tienda: portada, acceso con redirección según rol, registro de clientes y recuperación de la clave."""
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, PasswordResetView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from catalogo.models import Categoria, Producto
from clientes.forms import RegistroB2CForm, RegistroEmpresaForm
from .acceso import inicio_de
from crm import servicios as crm
from flota import servicios as flota
from flota.models import Camion, Despacho, Telemetria


def _imagen_de_categoria(nombre):
    """static/productos/categorias/<nombre en minúsculas y con guiones>.jpg, si existe; si no, la tienda usa la ilustración."""
    ruta = f"productos/categorias/{slugify(nombre)}.jpg"
    return ruta if (Path(settings.BASE_DIR) / "static" / ruta).exists() else None


def inicio(request, portada=False):
    """«/»: la portada es para visitantes. Con la sesión abierta cada cuenta va a su inicio (acceso.inicio_de); `portada=True` (/portada/) la deja ver al personal."""
    if request.user.is_authenticated and not portada:
        destino = inicio_de(request.user)
        if destino != "/":
            return redirect(destino)
    ultima = Telemetria.objects.order_by("-registrado_en").first()
    hace = int((timezone.now() - ultima.registrado_en).total_seconds()) if ultima else None
    return render(request, "inicio.html", {
        "n_productos": Producto.objects.filter(activo=True).count(),
        "categorias": [{"pk": c.pk, "nombre": c.nombre, "imagen": _imagen_de_categoria(c.nombre)} for c in Categoria.objects.order_by("nombre")],
        "portada": (Path(settings.BASE_DIR) / "static" / "img" / "portada.jpg").exists(),
        "n_camiones": Camion.objects.filter(activo=True).count(),
        "hace_seg": hace if hace is not None and hace < 3600 else None})


class FormularioEntrar(AuthenticationForm):
    error_messages = {**AuthenticationForm.error_messages,
                      "invalid_login": "El usuario o la clave no coinciden. Revisa que no tengas las mayúsculas activadas e inténtalo de nuevo."}

    def clean(self):
        """Con la clave correcta pero la cuenta inactiva (una empresa que espera aprobación) se explica eso, no «la clave no coincide»."""
        try:
            return super().clean()
        except forms.ValidationError:
            usuario = get_user_model().objects.filter(username__iexact=(self.cleaned_data.get("username") or "").strip()).first()
            if usuario is not None and not usuario.is_active and usuario.check_password(self.cleaned_data.get("password") or ""):
                raise forms.ValidationError("Tu cuenta aún no está activa. Si la pediste como empresa, el equipo de ventas la revisa y te "
                                            "avisa al correo; mientras tanto puedes ver el catálogo sin ingresar.", code="inactive")
            raise


class Entrar(LoginView):
    template_name = "cuenta/entrar.html"
    authentication_form = FormularioEntrar

    def dispatch(self, request, *args, **kwargs):
        """Con la sesión abierta, /cuenta/entrar/ lleva al inicio de la cuenta. No respeta ?next a propósito: una página que manda al login a quien ya entró haría un bucle."""
        if request.user.is_authenticated:
            return redirect(inicio_de(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Primero el ?next, que Django solo acepta si es del mismo sitio (sin redirecciones abiertas); si no hay, el inicio del rol."""
        return self.get_redirect_url() or inicio_de(self.request.user)


def registro(request):
    if request.user.is_authenticated:
        return redirect(inicio_de(request.user))
    form = RegistroB2CForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.guardar()
        login(request, usuario)
        messages.success(request, "Cuenta creada. Ya puedes comprar con precios para clientes particulares.")
        if not form.ubicada:
            messages.warning(request, "No pudimos ubicar tu dirección en el mapa. Puedes comprar igual; revisaremos la dirección antes de despachar.")
        return redirect("catalogo")
    return render(request, "cuenta/registro.html", {"form": form, "precarga": settings.REGISTRO_PRECARGA})


def registro_empresa(request):
    """Una empresa pide su cuenta: queda pendiente hasta que ventas la aprueba en el CRM (crm/solicitudes)."""
    if request.user.is_authenticated:
        return redirect(inicio_de(request.user))
    form = RegistroEmpresaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cliente = form.guardar()
        return render(request, "cuenta/registro_empresa_enviado.html", {"cliente": cliente, "ubicada": form.ubicada})
    return render(request, "cuenta/registro_empresa.html", {"form": form})


class Recuperar(PasswordResetView):
    """«¿Olvidaste tu clave?»: envía al correo de la cuenta un enlace de un solo uso que dura una hora (PASSWORD_RESET_TIMEOUT).
    Responde lo mismo exista o no la cuenta, para no revelar qué correos están registrados. El enlace usa la dirección pública
    (la primera de DJANGO_CSRF_ORIGINS) y no el Host del pedido, que alguien podría falsificar para que el enlace apunte a su sitio."""
    template_name = "cuenta/recuperar.html"
    email_template_name = "cuenta/recuperar_correo.txt"
    subject_template_name = "cuenta/recuperar_asunto.txt"
    success_url = "/cuenta/recuperar/enviado/"

    def form_valid(self, form):
        if settings.CSRF_TRUSTED_ORIGINS:
            publica = urlsplit(settings.CSRF_TRUSTED_ORIGINS[0])
            self.extra_email_context = {"domain": publica.netloc, "protocol": publica.scheme}
        return super().form_valid(form)


def guia(request):
    """Guía de flujos: qué hace cada perfil, paso a paso, con enlaces y el estado actual del sistema para guiar una demostración."""
    from catalogo.models import AvisoStock, Producto
    en_ruta = Despacho.objects.filter(salida_en__isnull=False, regreso_en__isnull=True).count()
    estado = {"por_despachar": flota.pedidos_por_despachar().count(), "camiones_libres": flota.camiones_libres().count(),
              "en_ruta": en_ruta, "sin_stock": Producto.objects.filter(activo=True, stock_disponible__lte=0).count(),
              "avisos": AvisoStock.objects.filter(atendido_en__isnull=True).count()}
    return render(request, "guia.html", {"estado": estado})


def csrf_fallo(request, reason=""):
    """Un formulario venció (pestaña abierta mucho rato, sesión cerrada en otra pestaña): se explica y se vuelve a donde estaba, en vez de la página seca de Django."""
    from django.utils.http import url_has_allowed_host_and_scheme
    atras = request.META.get("HTTP_REFERER", "")
    if not url_has_allowed_host_and_scheme(atras, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        atras = "/"
    return render(request, "403_csrf.html", {"volver": atras}, status=403)
