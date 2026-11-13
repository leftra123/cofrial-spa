"""Diagnóstico de un camión a partir de sus últimas lecturas, y revisión técnica.

Qué resuelve: una alerta de frío no siempre es una ruptura de frío. Un equipo que falla sube la temperatura de a poco, porque la carga es
una masa que se entibia con el tiempo. Un sensor que falla marca un salto imposible de un grado a otro entre dos lecturas separadas por
5 segundos, o se queda clavado en un valor sin moverse nunca. El primero pide revisar el equipo y probablemente avisar a los clientes; el
segundo pide revisar el sensor, y la carga puede estar bien (falsa alarma) o mal sin que el sensor lo diga (falso «todo normal»).

Los hechos los calcula este código con reglas fijas y siempre da un texto. Si hay una IA gratuita disponible solo redacta la sugerencia a
partir de esos hechos, y su texto se descarta si menciona un camión que no corresponde; nunca decide ni envía nada. Enviar el camión a
revisión lo hace una persona con un botón (`abrir_revision`). Privacidad: a la IA solo le llegan el código del camión, el rango de frío y
las temperaturas; ni clientes ni direcciones.
"""
import hashlib
import re

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from crm import ia

from .models import Camion, RevisionCamion, Telemetria

LECTURAS = 12              # ventana: 12 lecturas son un minuto de telemetría
SALTO_SENSOR_C = 6.0       # un cambio mayor entre dos lecturas seguidas no lo hace el frío: lo hace un sensor
PEGADO_LECTURAS = 8        # lecturas idénticas seguidas: un sensor vivo siempre oscila algo
CACHE_SEG = 120            # la misma situación no vuelve a consultar a la IA durante 2 minutos

NORMAL, RUPTURA, SENSOR_ALERTA, SENSOR_PEGADO = "normal", "ruptura", "sensor_alerta", "sensor_pegado"


def _g(x):
    return f"{x:.1f}".replace(".", ",")


def _lecturas(camion, camara):
    filas = list(Telemetria.objects.filter(camion=camion, camara=camara).order_by("-registrado_en")[:LECTURAS])
    return filas[::-1]                                  # de la más antigua a la más nueva


def _hechos(camion, camara=1):
    """Qué muestran las últimas lecturas de una cámara, sin interpretarlo todavía."""
    rango = camion.rango_de_camara(camara)
    lecturas = _lecturas(camion, camara)
    temps = [t.temp_camara for t in lecturas]
    saltos = [abs(b - a) for a, b in zip(temps, temps[1:])]
    pegado = len(temps) >= PEGADO_LECTURAS and len(set(temps[-PEGADO_LECTURAS:])) == 1
    return {"rango": rango.nombre, "min": float(rango.temp_min_c), "max": float(rango.temp_max_c), "temps": temps,
            "alerta": bool(lecturas and lecturas[-1].alerta_ruptura_frio), "salto_max": max(saltos) if saltos else 0.0, "pegado": pegado,
            "desde_base": bool(lecturas and not lecturas[-1].forzada)}


def _clasificar(h):
    if h["alerta"]:
        return SENSOR_ALERTA if h["salto_max"] >= SALTO_SENSOR_C else RUPTURA
    return SENSOR_PEGADO if h["pegado"] else NORMAL


def _texto_base(estado, camion, h):
    c = camion.camion_id
    ult = _g(h["temps"][-1]) if h["temps"] else "—"
    if estado == RUPTURA:
        return (f"{c} marca {ult} °C y sube de a poco: la carga se está entibiando y el rango es de {_g(h['min'])} a {_g(h['max'])} °C. "
                f"Parece una falla del equipo de frío. Conviene enviarlo a revisión y avisar a los clientes con pedidos a bordo.")
    if estado == SENSOR_ALERTA:
        return (f"{c} marca {ult} °C, pero la temperatura saltó {_g(h['salto_max'])} °C entre dos lecturas seguidas, algo que el frío no hace. "
                f"Parece una falla del sensor y la carga podría estar bien. Conviene enviarlo a revisión del sensor y confirmar la temperatura de la carga al llegar.")
    if estado == SENSOR_PEGADO:
        return (f"{c} marca {ult} °C en {PEGADO_LECTURAS} lecturas seguidas sin moverse nada. Un sensor sano siempre oscila un poco: "
                f"puede estar pegado y no avisar si la carga se entibia. Conviene enviarlo a revisión del sensor y medir la carga al recibir.")
    return f"{c} marca {ult} °C, dentro del rango de {_g(h['min'])} a {_g(h['max'])} °C. Sin problemas."


ACCIONES = {RUPTURA: ("equipo_frio", "Enviar a revisión del equipo de frío"),
            SENSOR_ALERTA: ("sensor", "Enviar a revisión del sensor"),
            SENSOR_PEGADO: ("sensor", "Enviar a revisión del sensor")}
TITULOS = {RUPTURA: "Ruptura de frío", SENSOR_ALERTA: "Posible falla del sensor (falsa alarma)", SENSOR_PEGADO: "Posible sensor pegado (no avisaría)", NORMAL: "Sin problemas"}


def _prompt(estado, camion, h):
    return ("Eres un asistente de logística en frío. A partir de estos HECHOS ya calculados, escribe en español, en 2 frases cortas, qué le pasa al camión y qué conviene hacer. "
            "No inventes datos, no menciones otros camiones y no prometas nada que no esté en los hechos.\n"
            f"Camión: {camion.camion_id}. Rango de frío: {_g(h['min'])} a {_g(h['max'])} °C. Últimas temperaturas: {', '.join(_g(t) for t in h['temps'][-8:])}.\n"
            f"Diagnóstico del sistema: {TITULOS[estado]}. Salto máximo entre lecturas: {_g(h['salto_max'])} °C. Sensor sin moverse: {'sí' if h['pegado'] else 'no'}.\n"
            f"Acción sugerida: {ACCIONES[estado][1]}.")


def _redactar(estado, camion, h, base, consultar_ia):
    """(texto, por_ia). Una vez redactado, el texto vale CACHE_SEG segundos para esa situación (camión y diagnóstico), aunque las temperaturas
    cambien cada 5 s; así el panel no gasta la cuota gratuita. Solo se llama a la IA si `consultar_ia`; sin IA utilizable, el texto base."""
    clave = "diagnostico_camion_" + hashlib.sha256(f"{camion.camion_id}:{estado}:{h['pegado']}".encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado, True
    if not consultar_ia:
        return base, False
    prompt = _prompt(estado, camion, h)
    try:
        texto = ia.redactar(prompt).strip()
    except ia.ErrorIA:
        return base, False
    if not 0 < len(texto) <= 500 or set(re.findall(r"CAM-\d+", texto)) - {camion.camion_id}:
        return base, False
    cache.set(clave, texto, CACHE_SEG)
    return texto, True


def revision_abierta(camion):
    return RevisionCamion.objects.filter(camion=camion, cerrada_en__isnull=True).select_related("abierta_por").first()


def diagnosticar(camion, con_ia=False):
    """Diagnóstico de un camión: estado, título, texto, quién lo escribió y la acción que se le puede ofrecer a una persona.
    Con dos cámaras se diagnostica la peor (la que está en alerta, si hay una)."""
    camaras = [1, 2] if camion.dos_camaras else [1]
    por_camara = [_hechos(camion, n) for n in camaras]
    estados = [_clasificar(h) for h in por_camara]
    orden = [RUPTURA, SENSOR_ALERTA, SENSOR_PEGADO, NORMAL]
    i = min(range(len(estados)), key=lambda k: orden.index(estados[k]))
    estado, h = estados[i], por_camara[i]
    base = _texto_base(estado, camion, h)
    texto, por_ia = (_redactar(estado, camion, h, base, con_ia) if estado != NORMAL else (base, False))
    revision = revision_abierta(camion)
    accion = None
    if estado != NORMAL and revision is None:
        motivo, etiqueta = ACCIONES[estado]
        accion = {"motivo": motivo, "texto": etiqueta}
    return {"camion": camion.camion_id, "estado": estado, "titulo": TITULOS[estado], "texto": texto, "por_ia": por_ia, "accion": accion,
            "camara": camaras[i] if camion.dos_camaras else None,
            "revision": {"motivo": revision.get_motivo_display(), "desde": timezone.localtime(revision.abierta_en).strftime("%H:%M"),
                         "por": revision.abierta_por.get_full_name() or revision.abierta_por.get_username() if revision.abierta_por else ""} if revision else None}


class ErrorRevision(Exception):
    """No se pudo abrir o cerrar la revisión; el mensaje es para mostrarlo."""


def abrir_revision(camion_id, motivo, usuario):
    """Envía el camión a revisión. El camión sigue su viaje, pero deja de sugerirse y de poder despacharse hasta «Volver a servicio»."""
    if motivo not in dict(RevisionCamion.MOTIVOS):
        raise ErrorRevision("Ese motivo no existe.")
    camion = Camion.objects.filter(pk=camion_id).first()
    if camion is None:
        raise ErrorRevision("Ese camión no existe.")
    h = diagnosticar(camion)
    try:
        with transaction.atomic():
            return RevisionCamion.objects.create(camion=camion, motivo=motivo, nota=h["texto"][:300], abierta_por=usuario)
    except IntegrityError:
        raise ErrorRevision(f"{camion.camion_id} ya está en revisión.")


def cerrar_revision(camion_id, usuario):
    """Vuelve el camión a servicio: puede despacharse de nuevo."""
    n = RevisionCamion.objects.filter(camion_id=camion_id, cerrada_en__isnull=True).update(cerrada_en=timezone.now(), cerrada_por=usuario)
    if not n:
        raise ErrorRevision("Ese camión no está en revisión.")
