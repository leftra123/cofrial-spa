from django.shortcuts import render

from clientes.models import Cliente, TipoCliente

from .models import PrecioProducto, Producto


def lista_del_visitante(request):
    """Cliente con sesión: la lista de su tipo (B2B institucional o B2C público). Visitante: la pública B2C."""
    if request.user.is_authenticated:
        cliente = Cliente.objects.select_related("tipo_cliente").filter(usuario=request.user).first()
        if cliente:
            return cliente.tipo_cliente
    return TipoCliente.objects.select_related("lista_precio").filter(codigo="B2C").first()


def listado(request):
    perfil = lista_del_visitante(request)
    precios = {}
    if perfil:
        precios = dict(PrecioProducto.objects.filter(lista_precio=perfil.lista_precio).values_list("producto_id", "precio_clp"))
    productos = Producto.objects.filter(activo=True).select_related("categoria__rango_temperatura").order_by("categoria__nombre", "nombre")
    filas = [(p, precios.get(p.producto_id)) for p in productos]
    return render(request, "catalogo/listado.html", {"filas": filas, "perfil": perfil})
