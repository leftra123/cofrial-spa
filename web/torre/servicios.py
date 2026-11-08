"""Datos de la Torre de control. Solo lee: no escribe en la base ni usa funciones que lo hagan (por eso no se usa `flota.servicios.estado_flota`,
que confirma entregas vencidas, ni `crm.servicios.indicadores`, que consulta cliente por cliente)."""
from datetime import timedelta

from django.db import connection
from django.db.models import F, Max, Sum
from django.utils import timezone

from clientes.models import Cliente, Direccion
from crm import servicios as crm
from catalogo.models import Producto
from crm.models import Interaccion, Prospecto, Requerimiento
from flota import vigente
from flota.models import Despacho, Telemetria
from pedidos.models import Orden, OrdenItem

FRECUENTES = 8
VENTANA_FRECUENTES_DIAS = 90

# Pedidos afectados por una ruptura de frío: copia de AFECTADAS y A_BORDO en grafana/generar_dashboard.py. Si se cambia allá, cambiarla aquí
# para que la cifra de la Torre y la de Grafana sigan coincidiendo.
_A_BORDO = """m.camion_id = d.camion_id AND m.alerta_ruptura_frio AND m.registrado_en >= d.salida_en
  AND m.registrado_en <= COALESCE(CASE WHEN e.nombre = 'Entregada' THEN COALESCE(x.entrega_resuelta_en, d.llegada_en) ELSE d.regreso_en END, now())"""
_RIESGO_HISTORICO = f"""SELECT coalesce(sum(t.total_clp), 0) FROM v_orden o JOIN v_orden_total t USING (orden_id)
JOIN orden x USING (orden_id)
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id
WHERE e.nombre <> 'Cancelada' AND d.salida_en IS NOT NULL AND EXISTS (
  SELECT 1 FROM telemetria m WHERE {_A_BORDO})"""

_MONTO = F("cantidad") * F("precio_unitario_clp")


def _riesgo_actual(camiones_en_alerta):
    """(monto, cliente más expuesto) de los pedidos a bordo, sin entregar, de camiones cuya última lectura trae alerta."""
    if not camiones_en_alerta:
        return 0, None
    ordenes = Orden.objects.filter(despacho__salida_en__isnull=False, despacho__regreso_en__isnull=True,
                                   despacho__camion_id__in=camiones_en_alerta).exclude(estado_orden__nombre__in=["Entregada", "Cancelada"])
    por_cliente = list(OrdenItem.objects.filter(orden__in=ordenes.values("pk")).values("orden__direccion__cliente__nombre")
                       .annotate(total=Sum(_MONTO)).order_by("-total", "orden__direccion__cliente__nombre"))
    if not por_cliente:
        return 0, None
    return sum(f["total"] for f in por_cliente), por_cliente[0]["orden__direccion__cliente__nombre"]


def _ahora(vigentes, alertas):
    ahora = timezone.now()
    ultima = Telemetria.objects.filter(forzada=False).aggregate(m=Max("registrado_en"))["m"]      # las forzadas de /demo/ no prueban que el simulador esté vivo
    riesgo, expuesto = _riesgo_actual(alertas)
    with connection.cursor() as cursor:
        cursor.execute(_RIESGO_HISTORICO)
        historico = int(cursor.fetchone()[0])
    ventas = {"B2B": 0, "B2C": 0}
    for canal, total in (OrdenItem.objects.filter(orden__creada_en__gte=ahora - timedelta(hours=24)).exclude(orden__estado_orden__nombre="Cancelada")
                         .values_list("orden__direccion__cliente__tipo_cliente__codigo").annotate(t=Sum(_MONTO))):
        ventas[canal] = int(total)
    return {
        "ultima_lectura_seg": None if ultima is None else max(0, int((ahora - ultima).total_seconds())),
        "alertas_24h": Telemetria.objects.filter(alerta_ruptura_frio=True, registrado_en__gte=ahora - timedelta(hours=24)).count(),
        "riesgo_actual_clp": int(riesgo),
        "camiones_en_alerta": len(alertas),
        "riesgo_historico_clp": historico,
        "no_concretadas": Orden.objects.filter(estado_orden__nombre="Entrega no concretada").exclude(entrega_motivo="").count(),
        "interacciones": Interaccion.objects.count(),
        "ventas_24h": ventas,
        "simulacion": Telemetria.objects.filter(forzada=True, registrado_en__gte=ahora - timedelta(seconds=vigente.VIGENCIA_FORZADA_S)).exists(),
        "mas_expuesto": expuesto,
    }


def _camiones(vigentes, alertas):
    en_viaje = set(Despacho.objects.filter(salida_en__isnull=False, regreso_en__isnull=True).values_list("camion_id", flat=True))
    return [{"id": cid, "lat": t.lat, "long": t.long, "alerta": cid in alertas}
            for cid, t in sorted(vigentes.items()) if cid in en_viaje or cid in alertas]


def _direcciones(cliente_ids):
    """Dirección principal (o la primera) de cada cliente, con comuna, en una consulta."""
    por_cliente = {}
    for d in Direccion.objects.filter(cliente__in=cliente_ids).select_related("comuna").order_by("cliente_id", "-es_principal", "direccion_id"):
        por_cliente.setdefault(d.cliente_id, d)
    return por_cliente


def _clientes(usuario, ahora):
    """Clientes con segmento y sus pedidos agregados (una consulta), con el nivel calculado en memoria."""
    base = crm.clientes_visibles(usuario).filter(segmento__isnull=False).select_related("segmento")
    return crm._con_pedidos(base, ahora)


def _nivel(c, ahora):
    return crm.nivel_de(c.n_pedidos, c.n_ventana, c.ultimo_pedido, ahora)


def _clientes_mapa(usuario, ahora):
    clientes = list(_clientes(usuario, ahora).order_by("nombre"))
    direcciones = _direcciones([c.pk for c in clientes])
    return [{"nombre": c.nombre, "segmento": c.segmento.nombre, "comuna": d.comuna.nombre, "lat": d.lat, "long": d.long,
             "nivel": _nivel(c, ahora), "url": f"/crm/clientes/{c.pk}/"}
            for c in clientes if (d := direcciones.get(c.pk)) and d.lat is not None and d.long is not None]


def _frecuentes(usuario, ahora):
    top = list(_clientes(usuario, ahora).filter(n_ventana__gt=0).order_by("-n_ventana", "-ultimo_pedido", "nombre")[:FRECUENTES])
    direcciones = _direcciones([c.pk for c in top])
    return [{"nombre": c.nombre, "segmento": c.segmento.nombre, "comuna": direcciones[c.pk].comuna.nombre if c.pk in direcciones else "",
             "pedidos": c.n_ventana, "ultimo": c.ultimo_pedido.isoformat(), "nivel": _nivel(c, ahora), "url": f"/crm/clientes/{c.pk}/"}
            for c in top]


def datos_negocio(usuario):
    """Todo lo que la Torre muestra del negocio, listo para JSON (fechas como texto ISO)."""
    ahora = timezone.now()
    vigentes = vigente.ultimas_vigentes()
    alertas = {cid for cid, t in vigentes.items() if t.alerta_ruptura_frio}
    return {"camiones": _camiones(vigentes, alertas),
            "clientes_mapa": _clientes_mapa(usuario, ahora),
            "frecuentes": _frecuentes(usuario, ahora),
            "embudo": crm.embudo_por_niveles(usuario),
            "ahora": _ahora(vigentes, alertas)}


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def front_back():
    """8.6: un dato vivo y un enlace por componente, tres de cada lado. Reusa de `rubrica` la comprobación de Grafana (con su caché) y la vigencia de
    una lectura; el resto son conteos de una consulta cada uno."""
    from . import rubrica
    ultimo = Requerimiento.objects.filter(confianza_ia__isnull=False).select_related("categoria_ia", "categoria_requerimiento").order_by("-creado_en").first()
    if ultimo is None:
        ia = "Sin clasificaciones todavía"
    else:
        categoria = ultimo.categoria_ia or ultimo.categoria_requerimiento
        ia = f"Última: {categoria.nombre if categoria else 'sin categoría'}, confianza {ultimo.confianza_ia}"
    reportando = (Telemetria.objects.filter(forzada=False, registrado_en__gte=timezone.now() - timedelta(seconds=rubrica.LECTURA_VIGENTE_S))
                  .values("camion").distinct().count())
    en_rds = (connection.settings_dict.get("HOST") or "").endswith(".rds.amazonaws.com")
    return {
        "front": [
            {"nombre": "E-commerce", "dato": _plural(Producto.objects.filter(activo=True).count(), "producto activo", "productos activos"), "url": "/catalogo/"},
            {"nombre": "CRM", "dato": _plural(Prospecto.objects.filter(etapa__es_final=False).count(), "prospecto abierto", "prospectos abiertos"), "url": "/crm/"},
            {"nombre": "IA", "dato": ia, "url": "/crm/ia/"},
        ],
        "back": [
            {"nombre": "AWS", "dato": "Base de datos en RDS" if en_rds else "Base local, no es RDS", "url": "/salud/"},
            {"nombre": "IoT", "dato": _plural(reportando, "camión reportando", "camiones reportando") if reportando
             else f"Sin lecturas en {rubrica.LECTURA_VIGENTE_S // 60} min", "url": "/flota/"},
            {"nombre": "BI", "dato": "Grafana responde" if rubrica.grafana_responde() else "Grafana no responde desde el servidor", "url": "/bi/"},
        ],
    }


def pedido_trazado():
    """8.6: el último pedido real con despacho en viaje o ya salido (nunca `HIS-`), con el cliente, el camión y la última lectura vigente de éste.
    Tres consultas, sin importar cuántos pedidos haya. None si no hay ninguno."""
    orden = (Orden.objects.filter(despacho__salida_en__isnull=False).exclude(numero_oc__startswith="HIS-")
             .select_related("direccion__cliente").order_by("-despacho__salida_en", "-orden_id").first())
    if orden is None:
        return None
    cliente, camion_id = orden.direccion.cliente, orden.despacho.camion_id
    lectura = vigente.ultimas_vigentes().get(camion_id)
    return {"orden_id": orden.pk, "cliente": cliente.nombre, "camion_id": camion_id,
            "temp_camara": None if lectura is None else lectura.temp_camara,
            "alerta": None if lectura is None else bool(lectura.alerta_ruptura_frio),      # None: nadie midió, no es lo mismo que «no»
            "orden_url": f"/crm/clientes/{cliente.pk}/#orden-{orden.pk}",      # la ficha del cliente lista sus pedidos; gerencia no puede abrir /pedidos/<id>/
            "cliente_url": f"/crm/clientes/{cliente.pk}/"}


CACHE_S = 4          # el sondeo es cada 5 s: varias pantallas abiertas comparten una sola consulta


def pulso(usuario, rol=None):
    """Lo que `/torre/pulso/` entrega: datos del negocio, Lectura del momento y rúbrica. Caché de 4 s por rol (solo entran admin y gerencia,
    y ambos ven lo mismo)."""
    from django.core.cache import cache
    from . import lectura, rubrica
    clave = f"torre:pulso:{rol or crm.rol(usuario)}"        # la vista ya sabe el rol (request.rol): evita otra consulta
    datos = cache.get(clave)
    if datos is None:
        datos = datos_negocio(usuario)
        datos.update({"generado_en": timezone.now().isoformat(), "lectura": lectura.redactar(datos["ahora"]), "rubrica": rubrica.evaluar(),
                      "front_back": front_back(), "pedido_trazado": pedido_trazado()})
        cache.set(clave, datos, CACHE_S)
    return datos
