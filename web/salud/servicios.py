"""Registrar revisiones y leerlas para la página. La página solo muestra lo que hay en `chequeo_servicio`."""
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from . import chequeos
from .catalogo import CADA, GRUPOS, NOMBRES
from .models import ChequeoServicio

log = logging.getLogger("cofrial.salud")

DIAS = 90
RETENCION_DIAS = 100
UMBRAL_ROJO = 0.05                  # un día (u hora) se pinta rojo si al menos el 5 % de sus revisiones fallaron; con menos de eso, amarillo
HUECO_MAX_SEG = 300                 # entre dos revisiones de «base» más que esto = el monitor (el laboratorio) estuvo apagado
MIN_DEGRADADO_MIN = 5
ORDEN = {"ok": 0, "degradado": 1, "caido": 2}


def ejecutar_ronda(pendientes, ahora=None):
    """Hace las revisiones que tocan y las guarda. `pendientes` es la lista de filas aún no guardadas (la base pudo estar caída en la ronda anterior):
    se guardan después con su hora original. Devuelve cuántas revisiones se hicieron."""
    ahora = ahora or timezone.now()
    try:
        ultimas = dict(ChequeoServicio.objects.filter(momento__gte=ahora - timedelta(hours=1)).values_list("servicio").annotate(u=Max("momento")))
    except DatabaseError:
        ultimas = {}
    for fila in pendientes:
        ultimas[fila.servicio] = max(ultimas.get(fila.servicio, fila.momento), fila.momento)
    hechas = 0
    for clave, revisar in chequeos.REVISIONES.items():
        previa = ultimas.get(clave)
        if previa and (ahora - previa).total_seconds() < CADA[clave] - 5:
            continue
        try:
            r = revisar()
        except Exception:                                     # una revisión con error propio no debe tumbar a las demás
            log.exception("Falló la revisión de %s", clave)
            r = (chequeos.CAIDO, None, "error del vigilante")
        if r is None:
            continue
        estado, ms, detalle = r
        pendientes.append(ChequeoServicio(servicio=clave, momento=timezone.now(), estado=estado, ms=ms, detalle=detalle[:80]))
        hechas += 1
    guardar(pendientes)
    return hechas


def guardar(pendientes):
    """Guarda lo pendiente; si la base no responde lo conserva (hasta 2000 filas) para la próxima ronda."""
    if not pendientes:
        return
    try:
        ChequeoServicio.objects.bulk_create(pendientes)
        pendientes.clear()
    except DatabaseError:
        log.warning("La base no respondió: %d revisiones quedan pendientes", len(pendientes))
        del pendientes[:-2000]


def podar(ahora=None):
    corte = (ahora or timezone.now()) - timedelta(days=RETENCION_DIAS)
    return ChequeoServicio.objects.filter(momento__lt=corte).delete()[0]


# ---------- lectura ----------

def _estado_cubo(total, caidos, degradados):
    if not total:
        return "sin"
    if caidos / total >= UMBRAL_ROJO:
        return "caido"
    return "degradado" if caidos or degradados else "ok"


def _combinar(estados, modo):
    """Estado de un grupo a partir de los de sus componentes en un mismo día u hora."""
    conocidos = [e for e in estados if e != "sin"]
    if not conocidos:
        return "sin"
    if modo == "respaldo":
        if all(e == "caido" for e in conocidos):
            return "caido"
        return "ok" if all(e == "ok" for e in conocidos) else "degradado"
    return max(conocidos, key=ORDEN.get)


def _agregar(desde, funcion):
    """{servicio: {cubo: (total, caidos, degradados)}} con un solo GROUP BY."""
    filas = (ChequeoServicio.objects.filter(momento__gte=desde).annotate(c=funcion("momento")).values("servicio", "c")
             .annotate(total=Count("pk"), caidos=Count("pk", filter=Q(estado="caido")), degradados=Count("pk", filter=Q(estado="degradado"))))
    out = defaultdict(dict)
    for f in filas:
        out[f["servicio"]][f["c"]] = (f["total"], f["caidos"], f["degradados"])
    return out


def _barras(cubos_por_servicio, claves, modo, etiquetas):
    """Una barra por cubo (día u hora), combinando los componentes `claves`. etiquetas = lista ordenada de cubos."""
    barras = []
    for cubo in etiquetas:
        estados, total, caidos = [], 0, 0
        for k in claves:
            t, c, d = cubos_por_servicio.get(k, {}).get(cubo, (0, 0, 0))
            estados.append(_estado_cubo(t, c, d))
            total += t
            caidos += c
        barras.append({"cubo": cubo, "estado": _combinar(estados, modo), "revisiones": total, "caidas": caidos})
    return barras


def _disponibilidad(cubos, claves, modo):
    """% de revisiones sin caída en la ventana. En «respaldo» se toma el mejor componente: con uno en pie, el servicio responde."""
    cifras = []
    for k in claves:
        total = sum(t for t, _, _ in cubos.get(k, {}).values())
        caidos = sum(c for _, c, _ in cubos.get(k, {}).values())
        if total:
            cifras.append((total - caidos) / total)
    if not cifras:
        return None
    return max(cifras) if modo == "respaldo" else min(cifras)


def _incidentes(ahora, dias=7):
    """Tramos seguidos de revisiones no operativas por componente, y huecos en que no hubo registro. Más reciente primero."""
    desde = ahora - timedelta(days=dias)
    filas = (ChequeoServicio.objects.filter(momento__gte=desde).exclude(estado="ok").order_by("servicio", "momento")
             .values_list("servicio", "momento", "estado", "detalle"))
    # una revisión OK corta el tramo: se necesita saber cuándo volvió. Se busca la primera OK posterior a cada tramo.
    tramos, actual = [], {}
    for servicio, momento, estado, detalle in filas:
        t = actual.get(servicio)
        paso = CADA.get(servicio, 60) * 2.5
        if t and (momento - t["fin"]).total_seconds() <= paso:
            t["fin"] = momento
            if ORDEN[estado] > ORDEN[t["estado"]]:
                t["estado"] = estado
            if detalle:
                t["detalle"] = detalle
        else:
            t = {"servicio": servicio, "nombre": NOMBRES.get(servicio, servicio), "inicio": momento, "fin": momento, "estado": estado, "detalle": detalle}
            actual[servicio] = t
            tramos.append(t)
    for t in tramos:
        t["fin"] = t["fin"] + timedelta(seconds=CADA.get(t["servicio"], 60))
        t["en_curso"] = (ahora - t["fin"]).total_seconds() <= CADA.get(t["servicio"], 60) * 2
        t["minutos"] = max(1, round((t["fin"] - t["inicio"]).total_seconds() / 60))
    tramos = [t for t in tramos if t["estado"] == "caido" or t["minutos"] >= MIN_DEGRADADO_MIN]      # un tropiezo de un minuto en amarillo cuenta en la barra, no en esta lista
    huecos = []
    previo = None
    for (m,) in ChequeoServicio.objects.filter(servicio="base", momento__gte=desde).order_by("momento").values_list("momento"):
        if previo and (m - previo).total_seconds() > HUECO_MAX_SEG:
            huecos.append({"servicio": "_hueco", "nombre": "Sin registros del monitor", "inicio": previo, "fin": m, "estado": "sin",
                           "detalle": "el laboratorio estuvo apagado o el monitor detenido", "en_curso": False,
                           "minutos": round((m - previo).total_seconds() / 60)})
        previo = m
    if previo and (ahora - previo).total_seconds() > HUECO_MAX_SEG:
        huecos.append({"servicio": "_hueco", "nombre": "Sin registros del monitor", "inicio": previo, "fin": ahora, "estado": "sin",
                       "detalle": "el monitor no ha registrado nada desde entonces", "en_curso": True,
                       "minutos": round((ahora - previo).total_seconds() / 60)})
    return sorted(tramos + huecos, key=lambda x: x["inicio"], reverse=True)[:40]


def panel(ahora=None):
    """Todo lo que dibuja la página. Se cachea 30 s: la página es pública y no debe consultar la base en cada visita."""
    ahora = ahora or timezone.now()
    llave = "salud:panel"
    guardado = cache.get(llave)
    if guardado is not None:
        return guardado
    hoy = timezone.localdate(ahora)
    dias = [hoy - timedelta(days=i) for i in range(DIAS - 1, -1, -1)]
    inicio_dias = timezone.make_aware(datetime.combine(dias[0], time.min))
    por_dia = _agregar(inicio_dias, TruncDate)
    hora_actual = ahora.replace(minute=0, second=0, microsecond=0)
    horas = [hora_actual - timedelta(hours=i) for i in range(23, -1, -1)]
    por_hora = _agregar(horas[0], TruncHour)
    # estado actual por componente: la última fila de cada uno
    ultimo = {}
    for s, m, e, d, ms in ChequeoServicio.objects.filter(momento__gte=ahora - timedelta(hours=1)).order_by("momento").values_list("servicio", "momento", "estado", "detalle", "ms"):
        ultimo[s] = {"momento": m, "estado": e, "detalle": d, "ms": ms}

    grupos = []
    for g in GRUPOS:
        claves = [c for c, _, _ in g["componentes"] if c in por_dia or c in ultimo]
        if not claves:
            continue                                            # componente que nunca se registró (sin clave configurada): no se muestra
        componentes = []
        for clave, nombre, cada in g["componentes"]:
            if clave not in claves:
                continue
            u = ultimo.get(clave)
            vigente = bool(u) and (ahora - u["momento"]).total_seconds() <= cada * 2.5
            componentes.append({
                "clave": clave, "nombre": nombre,
                "estado": u["estado"] if vigente else "sin", "detalle": u["detalle"] if vigente else "sin registros recientes",
                "ms": u["ms"] if vigente else None,
                "barras": _barras(por_dia, [clave], "peor", dias), "horas": _barras(por_hora, [clave], "peor", [h for h in horas]),
                "disponibilidad": _disponibilidad(por_dia, [clave], "peor")})
        estado = _combinar([c["estado"] for c in componentes], g["modo"])
        grupos.append({"id": g["id"], "nombre": g["nombre"], "descripcion": g["descripcion"], "componentes": componentes, "estado": estado,
                       "barras": _barras(por_dia, claves, g["modo"], dias), "horas": _barras(por_hora, claves, g["modo"], horas),
                       "disponibilidad": _disponibilidad(por_dia, claves, g["modo"]), "respaldo": g["modo"] == "respaldo"})
    ultima_global = max((u["momento"] for u in ultimo.values()), default=None)
    datos = {"grupos": grupos, "incidentes": _incidentes(ahora), "dias": dias, "horas": horas, "ahora": ahora,
             "ultima_revision": ultima_global, "monitor_activo": bool(ultima_global) and (ahora - ultima_global).total_seconds() <= HUECO_MAX_SEG,
             "problemas": [(g, c) for g in grupos for c in g["componentes"] if c["estado"] in ("degradado", "caido")]}
    cache.set(llave, datos, 30)
    return datos
