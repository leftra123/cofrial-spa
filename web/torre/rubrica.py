"""Evidencia viva de cada dimensión de la rúbrica del Hito 2. Solo lee. Cada fila se calcula aparte: si una consulta falla, esa fila queda en
«no comprobado» y las demás siguen. «Verificado» solo cuando la evidencia lo sostiene; ante la duda, nunca verde."""
import http.client
import logging
import os
import time
import urllib.request
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db import connection
from django.db.models import Count, Max, Sum, F
from django.utils import timezone

from catalogo.models import Producto
from crm.models import Prospecto, Requerimiento
from flota.models import Telemetria
from pedidos.models import Orden, OrdenItem

log = logging.getLogger(__name__)

VERIFICADO = "verificado"
SIN_EVIDENCIA = "sin_evidencia"
NO_COMPROBADO = "no_comprobado"

LECTURA_VIGENTE_S = 120
VENTANA_BI_DIAS = 7
CAMPOS_IOT = ("camion_id", "temp_camara", "lat", "long", "combustible_pct", "alerta_ruptura_frio")
_MONTO = F("cantidad") * F("precio_unitario_clp")

_IMDS = "http://169.254.169.254/latest"
_cache_ec2 = {"hecho": False, "valor": None}          # caché de proceso: la instancia no cambia mientras corre el contenedor
_cache_grafana = {"hasta": 0.0, "valor": False}


def limpiar_cache():
    _cache_ec2.update(hecho=False, valor=None)
    _cache_grafana.update(hasta=0.0, valor=False)


def instancia_ec2():
    """ID de la instancia EC2 (IMDSv2, 200 ms); si el contenedor no lo alcanza, la variable INSTANCIA_EC2 que escribe provision.sh; si no, None."""
    if not _cache_ec2["hecho"]:
        valor = None
        try:
            pedido = urllib.request.Request(f"{_IMDS}/api/token", method="PUT", headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
            token = urllib.request.urlopen(pedido, timeout=0.2).read().decode()
            pedido = urllib.request.Request(f"{_IMDS}/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": token})
            valor = urllib.request.urlopen(pedido, timeout=0.2).read().decode().strip() or None
        except Exception:
            valor = None
        _cache_ec2.update(hecho=True, valor=valor or os.environ.get("INSTANCIA_EC2") or None)
    return _cache_ec2["valor"]


def _consultar_grafana():
    destino = urlsplit(settings.GRAFANA_INTERNA_URL)
    conexion = http.client.HTTPConnection(destino.hostname, destino.port or 80, timeout=1)
    try:
        conexion.request("GET", "/api/health")
        return conexion.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conexion.close()


def grafana_responde():
    if time.monotonic() >= _cache_grafana["hasta"]:
        _cache_grafana.update(valor=_consultar_grafana(), hasta=time.monotonic() + 30)
    return _cache_grafana["valor"]


def _hora(momento):
    return timezone.localtime(momento).strftime("%d-%m-%Y %H:%M:%S")


def _enmascarar(host):
    return "…" + host[-30:] if len(host) > 30 else host


def _d1():
    host = connection.settings_dict.get("HOST") or ""
    with connection.cursor() as c:
        c.execute("SELECT version(), now() - pg_postmaster_start_time()")
        version, encendida = c.fetchone()
    motor = " ".join(version.split()[:2])
    dias, segundos = encendida.days, encendida.seconds
    evidencia = [f"Motor: {motor}", f"Encendida hace {dias} d {segundos // 3600} h {segundos % 3600 // 60} min"]
    es_rds = host.endswith(".rds.amazonaws.com")
    evidencia.append(f"Host de la base: {_enmascarar(host) if es_rds else 'local (no es RDS)'}")
    if not es_rds:
        return evidencia, SIN_EVIDENCIA
    instancia = instancia_ec2()
    if instancia is None:
        evidencia.append("Instancia EC2: no se pudo leer")
        return evidencia, NO_COMPROBADO
    evidencia.append(f"Instancia EC2: {instancia}")
    return evidencia, VERIFICADO


def _ultimo_por_canal(codigo):
    return (Orden.objects.filter(direccion__cliente__tipo_cliente__codigo=codigo).exclude(numero_oc__startswith="HIS-").aggregate(m=Max("creada_en"))["m"])


def _d2():
    productos = Producto.objects.filter(activo=True).count()
    abiertos = Prospecto.objects.filter(etapa__es_final=False).count()
    evidencia = [f"Productos activos: {productos}", f"Prospectos abiertos: {abiertos}"]
    canales = {}
    for codigo in ("B2B", "B2C"):
        canales[codigo] = _ultimo_por_canal(codigo)
        evidencia.append(f"Último pedido {codigo}: " + (_hora(canales[codigo]) if canales[codigo] else "ninguno (sin contar el historial HIS-)"))
    return evidencia, VERIFICADO if productos and all(canales.values()) else SIN_EVIDENCIA


def _d3():
    ahora = timezone.now()
    reales = Telemetria.objects.filter(forzada=False)
    ultima = reales.order_by("-registrado_en").select_related("camion").first()
    evidencia = ["Campos de la lectura: " + ", ".join(CAMPOS_IOT)]
    if ultima is None:
        evidencia.append("Sin lecturas del simulador" + (" (solo hay lecturas forzadas desde /demo/)" if Telemetria.objects.exists() else ""))
        return evidencia, SIN_EVIDENCIA
    edad = max(0, int((ahora - ultima.registrado_en).total_seconds()))
    reportando = reales.filter(registrado_en__gte=ahora - timedelta(seconds=LECTURA_VIGENTE_S)).values("camion").distinct().count()
    evidencia += [f"Última lectura: camion_id={ultima.camion_id}, temp_camara={ultima.temp_camara}, lat={ultima.lat}, long={ultima.long}, "
                  f"combustible_pct={ultima.combustible_pct}, alerta_ruptura_frio={str(ultima.alerta_ruptura_frio).lower()}",
                  f"Antigüedad: {edad} s ({_hora(ultima.registrado_en)})", f"Camiones reportando en {LECTURA_VIGENTE_S // 60} min: {reportando}"]
    return evidencia, VERIFICADO if edad < LECTURA_VIGENTE_S else SIN_EVIDENCIA


def _d4():
    desde = timezone.now() - timedelta(days=VENTANA_BI_DIAS)
    ventas = Orden.objects.filter(creada_en__gte=desde).exclude(estado_orden__nombre="Cancelada")
    evidencia = [f"Ventana: últimos {VENTANA_BI_DIAS} días (desde {_hora(desde)})"]
    for canal, n, total in (OrdenItem.objects.filter(orden__in=ventas.values("pk")).values_list("orden__direccion__cliente__tipo_cliente__codigo")
                            .annotate(n=Count("orden", distinct=True), t=Sum(_MONTO)).order_by("orden__direccion__cliente__tipo_cliente__codigo")):
        evidencia.append(f"Ventas {canal}: {n} pedidos, ${int(total):,} CLP".replace(",", "."))
    cantidad = ventas.count()
    historial = ventas.filter(numero_oc__startswith="HIS-").count()
    alertas = Telemetria.objects.filter(alerta_ruptura_frio=True, registrado_en__gte=desde).count()
    evidencia += [f"Pedidos en la ventana: {cantidad} ({historial} del historial ilustrativo HIS-)", f"Alertas de ruptura de frío en la ventana: {alertas}"]
    if not grafana_responde():
        evidencia.append("Grafana no responde desde el servidor")
        return evidencia, NO_COMPROBADO
    evidencia.append("Grafana responde desde el servidor")
    return evidencia, VERIFICADO if cantidad > historial else SIN_EVIDENCIA      # el historial ilustrativo no prueba una venta real


def _d5():
    ultimo = (Requerimiento.objects.filter(confianza_ia__isnull=False).select_related("categoria_ia", "categoria_requerimiento").order_by("-creado_en").first())
    proveedores = [nombre for nombre, var in (("Gemini", "GEMINI_API_KEY"), ("Groq", "GROQ_API_KEY")) if os.environ.get(var)]
    de_pago = bool(os.environ.get("ANTHROPIC_API_KEY"))
    evidencia = ["Proveedores gratuitos configurados: " + (", ".join(proveedores) or "ninguno"),
                 "IA de pago (ANTHROPIC_API_KEY): " + ("ACTIVA" if de_pago else "no configurada")]
    if ultimo is None:
        evidencia.append("Sin clasificaciones de IA registradas")
    else:
        categoria = ultimo.categoria_ia or ultimo.categoria_requerimiento
        evidencia.append(f"Última clasificación: {categoria.nombre if categoria else 'sin categoría'}, confianza {ultimo.confianza_ia}, {_hora(ultimo.creado_en)}")
    evidencia.append("La defensa en vivo la hace el equipo")
    return evidencia, VERIFICADO if ultimo is not None and not de_pago else SIN_EVIDENCIA


_FILAS = [
    ("D1", "Despliegue AWS Academy", "EC2 y RDS funcionales, estables y conectados en la nube", "_d1", "/salud/"),
    ("D2", "E-commerce y CRM", "Sitio con carrito, pedidos B2B/B2C y CRM conectados a la BD en la nube", "_d2", "/catalogo/"),
    ("D3", "IoT con Docker en EC2", "Contenedores que inyectan automáticamente los parámetros exigidos", "_d3", "/flota/"),
    ("D4", "Dashboard BI", "Panel conectado en vivo que cruza ventas con cadena de frío", "_d4", "/bi/"),
    ("D5", "IA (costo cero) y defensa", "API pública de IA funcionando + demostración sólida en vivo", "_d5", "/crm/requerimientos/"),
]


def evaluar():
    filas = []
    for dim, titulo, exigencia, calcular, url in _FILAS:
        try:
            evidencia, estado = globals()[calcular]()
        except Exception:
            log.exception("Rúbrica %s: no se pudo comprobar", dim)
            evidencia, estado = ["No se pudo consultar la evidencia"], NO_COMPROBADO
        filas.append({"dim": dim, "titulo": titulo, "exigencia": exigencia, "evidencia": evidencia, "estado": estado, "url": url})
    return filas
