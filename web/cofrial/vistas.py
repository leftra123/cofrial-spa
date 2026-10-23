"""Páginas generales de la tienda: portada, acceso con redirección según rol y registro de clientes particulares."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone

from catalogo.models import Categoria, Producto
from clientes.forms import RegistroB2CForm
from crm import servicios as crm
from flota.models import Camion, Telemetria


def inicio(request):
    ultima = Telemetria.objects.order_by("-registrado_en").first()
    hace = int((timezone.now() - ultima.registrado_en).total_seconds()) if ultima else None
    return render(request, "inicio.html", {
        "n_productos": Producto.objects.filter(activo=True).count(),
        "categorias": Categoria.objects.order_by("nombre"),
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
        return redirect("catalogo")
    return render(request, "cuenta/registro.html", {"form": form})
