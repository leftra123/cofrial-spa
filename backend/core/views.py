from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from .models import PrecioProducto, Producto

# Perfil de compra -> lista de precios (tabla lista_precio)
PERFILES = {"b2b": "Institucional B2B", "b2c": "Público B2C"}


def health(request):
    """Comprueba que la app responde y que la BD (local o RDS) es alcanzable."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception as exc:
        db = f"error: {exc.__class__.__name__}"
    return JsonResponse({"app": "ok", "db": db}, status=200 if db == "ok" else 503)


def catalogo(request):
    """Catálogo de refrigerados y congelados con el precio según el perfil (B2B o B2C)."""
    perfil = request.GET.get("perfil", "b2c").lower()
    if perfil not in PERFILES:
        perfil = "b2c"
    precios = dict(
        PrecioProducto.objects.filter(lista_precio__nombre=PERFILES[perfil]).values_list("producto_id", "precio_clp")
    )
    productos = Producto.objects.filter(activo=True).select_related("categoria__rango_temperatura").order_by("categoria__nombre", "nombre")
    items = [
        {"p": p, "rango": p.categoria.rango_temperatura, "precio": precios.get(p.producto_id)}
        for p in productos
    ]
    return render(request, "core/catalogo.html", {"items": items, "perfil": perfil, "lista": PERFILES[perfil]})
