"""Avisos del equipo interno: lo que cada rol debería atender ahora, para el contador del menú y las notificaciones del navegador.

Se calculan desde los datos y no se guardan: un aviso desaparece cuando el trabajo se hizo, sin marcarlo como leído y sin tablas nuevas.
Cada pestaña lo consulta cada 15 s, así que cada aviso es un solo conteo: nada aquí puede recorrer órdenes ni llamar a la IA.
Por qué consulta periódica y no conexiones abiertas: gunicorn corre con 1 proceso y 16 hilos, y cada conexión abierta ocuparía un hilo."""
from django.db.models import Exists, OuterRef

from crm import servicios as crm
from flota import servicios as flota
from flota.models import Despacho, Telemetria
from pedidos import documentos

DESPACHAN = ("admin", "despachador")          # gerencia consulta: su enlace lleva a Flota y no a armar viajes
VEN_FLOTA = ("admin", "gerencia", "despachador")
COMERCIAL = ("admin", "gerencia", "vendedor")


def _viajes_con_ruptura(usuario, rol):
    """Viajes en curso con una lectura de ruptura de frío desde que salieron. Una alerta de un viaje anterior no cuenta."""
    alerta = Telemetria.objects.filter(camion_id=OuterRef("camion_id"), alerta_ruptura_frio=True, registrado_en__gte=OuterRef("salida_en"))
    viajes = Despacho.objects.filter(salida_en__isnull=False, llegada_en__isnull=True).filter(Exists(alerta))
    if rol != "despachador":              # el vendedor ve solo su cartera; el despachador ve todos los camiones
        viajes = viajes.filter(orden__direccion__cliente__in=crm.clientes_visibles(usuario)).distinct()
    return viajes.count()


def _aviso(id_, n, singular, plural, url, urgente=False):
    return {"id": id_, "n": n, "texto": singular if n == 1 else plural.format(n=n), "url": url, "urgente": urgente}


def avisos_de(usuario, rol):
    """Lista de avisos con novedades para este rol, los urgentes primero. Solo trae enlaces a pantallas que ese rol puede abrir."""
    avisos = []
    if rol in VEN_FLOTA or rol == "vendedor":
        n = _viajes_con_ruptura(usuario, rol)
        if n:
            avisos.append(_aviso("frio", n, "1 viaje en curso con ruptura de frío", "{n} viajes en curso con ruptura de frío", "/crm/alertas/", urgente=True))
    if rol in VEN_FLOTA:
        n = flota.pedidos_por_despachar().count()
        if n:
            avisos.append(_aviso("por_despachar", n, "1 pedido por despachar", "{n} pedidos por despachar", "/flota/despachar/" if rol in DESPACHAN else "/flota/"))
    if rol in COMERCIAL:
        n = crm.solicitudes_empresa().count()
        if n:
            avisos.append(_aviso("solicitudes", n, "1 empresa espera aprobación", "{n} empresas esperan aprobación", "/crm/solicitudes/"))
        n = crm.requerimientos_visibles(usuario).exclude(estado="resuelto").count()
        if n:
            avisos.append(_aviso("reclamos", n, "1 requerimiento por atender", "{n} requerimientos por atender", "/crm/requerimientos/"))
        clientes = crm.clientes_visibles(usuario)
        n = documentos.cuantas_sin_factura(clientes)
        if n:
            avisos.append(_aviso("por_facturar", n, "1 entrega sin facturar", "{n} entregas sin facturar", "/crm/cobranza/"))
        n = documentos.cuantas_facturas_vencidas(clientes)
        if n:
            avisos.append(_aviso("vencidas", n, "1 factura vencida", "{n} facturas vencidas", "/crm/cobranza/"))
    return avisos
