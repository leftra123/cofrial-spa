from .models import Cliente


def demo(request):
    """Datos del selector «Comprar como…» (sustituto temporal del login)."""
    cid = request.session.get("cliente_id")
    return {
        "clientes_demo": Cliente.objects.select_related("tipo_cliente").order_by("nombre"),
        "cliente_sesion": Cliente.objects.filter(pk=cid).first() if cid else None,
    }
