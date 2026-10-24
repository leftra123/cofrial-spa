"""Páginas generales de la tienda: portada, acceso con redirección según rol y registro de clientes particulares."""
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from catalogo.models import Categoria, Producto
from clientes.forms import RegistroB2CForm
from crm import servicios as crm
from flota.models import Camion, Telemetria


def _imagen_de_categoria(nombre):
    """static/productos/categorias/<nombre en minúsculas y con guiones>.jpg, si existe; si no, la tienda usa la ilustración."""
    ruta = f"productos/categorias/{slugify(nombre)}.jpg"
    return ruta if (Path(settings.BASE_DIR) / "static" / ruta).exists() else None


def inicio(request):
    ultima = Telemetria.objects.order_by("-registrado_en").first()
    hace = int((timezone.now() - ultima.registrado_en).total_seconds()) if ultima else None
    return render(request, "inicio.html", {
        "n_productos": Producto.objects.filter(activo=True).count(),
        "categorias": [{"pk": c.pk, "nombre": c.nombre, "imagen": _imagen_de_categoria(c.nombre)} for c in Categoria.objects.order_by("nombre")],
        "portada": (Path(settings.BASE_DIR) / "static" / "img" / "portada.jpg").exists(),
        "n_camiones": Camion.objects.filter(activo=True).count(),
        "hace_seg": hace if hace is not None and hace < 3600 else None})


class Entrar(LoginView):
    template_name = "cuenta/entrar.html"

    def get_success_url(self):
        destino = self.get_redirect_url()
        if destino:
            return destino
        return "/crm/" if crm.rol(self.request.user) else "/catalogo/"


def registro(request):
    if request.user.is_authenticated:
        return redirect("catalogo")
    form = RegistroB2CForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.guardar()
        login(request, usuario)
        messages.success(request, "Cuenta creada. Ya puedes comprar con precios para clientes particulares.")
        if not form.ubicada:
            messages.warning(request, "No pudimos ubicar tu dirección en el mapa. Puedes comprar igual; revisaremos la dirección antes de despachar.")
        return redirect("catalogo")
    return render(request, "cuenta/registro.html", {"form": form})
