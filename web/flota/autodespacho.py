"""Despacho sin personas: agrupa los pedidos en espera y los despacha con `servicios.despachar`.

Quién decide: este código, con el cálculo de `sugerencias.py` y reglas fijas. La IA solo redacta la explicación después de que el viaje
salió; si falla, queda el texto del código. Apagado por defecto (DESPACHO_AUTO=0): corre en el servicio `despachador` y no en la web,
porque debe funcionar aunque nadie tenga el panel abierto. El porqué se decidió en docs/decisiones.md.

Cuándo sale un viaje: al completar MAX_PARADAS pedidos o cuando su pedido más antiguo lleva DESPACHO_AUTO_ESPERA_MIN minutos. Sin esa
espera saldría un camión por cada pedido y no habría nada que agrupar.
"""
import json
import logging
import os

from django.utils import timezone

from crm import ia
from pedidos.servicios import ErrorDeNegocio

from . import servicios, sugerencias
from .models import Despacho

log = logging.getLogger(__name__)

ESPERA_MIN = 5            # minutos que un pedido puede esperar a que se le sumen otros
INTERVALO_SEG = 60        # cada cuánto revisa el servicio `despachador`
MAX_VIAJES_A_MANO = 3     # tope de la pasada pedida desde el panel: responde dentro del plazo de la web y deja pedidos para el armado manual
MAX_IA_POR_PASADA = 2     # cuida la cuota gratuita y el tiempo de la pasada
PLAZO_IA_SEG = 5


def activo():
    return os.environ.get("DESPACHO_AUTO", "0") == "1"


def _entero(variable, defecto):
    try:
        return max(1, int(os.environ.get(variable) or defecto))
    except ValueError:
        return defecto


def espera_min():
    return _entero("DESPACHO_AUTO_ESPERA_MIN", ESPERA_MIN)


def intervalo_seg():
    return _entero("DESPACHO_AUTO_INTERVALO_SEG", INTERVALO_SEG)


def planificar(forzar=False):
    """(viajes que salen ahora, viajes que siguen agrupándose, resto). No escribe nada. `forzar` no espera a que el grupo se complete."""
    viajes, resto = sugerencias.calcular(automatico=True)
    tope, salen, agrupando = espera_min(), [], []
    for v in viajes:
        if len(v["pedidos"]) >= sugerencias.MAX_PARADAS:
            salen.append({**v, "motivo": f"completó {sugerencias.MAX_PARADAS} paradas"})
        elif v["espera_max_min"] >= tope:
            salen.append({**v, "motivo": f"el pedido más antiguo lleva {v['espera_max_min']} min esperando (el tope es {tope})"})
        elif forzar:
            salen.append({**v, "motivo": "se pidió una pasada a mano, sin esperar a que el grupo se complete"})
        else:
            agrupando.append({**v, "sale_en_min": tope - v["espera_max_min"]})
    return salen, agrupando, resto


def _lista(numeros):
    textos = [str(n) for n in numeros]
    return textos[0] if len(textos) == 1 else f"{', '.join(textos[:-1])} y {textos[-1]}"


def explicar(v):
    """El porqué del viaje en una frase, solo con datos del cálculo. Es lo que queda guardado en el despacho."""
    n, ordenes = len(v["pedidos"]), _lista(p["orden"] for p in v["pedidos"])
    return (f"Salen {n} pedido{'s' if n != 1 else ''} de rango {v['rango'].lower()} ({'órdenes' if n != 1 else 'orden'} {ordenes}) "
            f"porque {v['motivo']}. Camión elegido: {v['nota_camion']}")


def _prompt(v, decision):
    hechos = json.dumps({"camion": v["camion"], "rango": v["rango"], "pedidos": v["pedidos"], "motivo": v["motivo"],
                         "camion_elegido": v["nota_camion"]}, ensure_ascii=False)
    return ("Eres el asistente de despacho de Cofrial SpA, distribuidora chilena de alimentos refrigerados y congelados. "
            "El sistema ya despachó este viaje por su cuenta. Explica al despachador qué decidió y por qué en 1 o 2 frases en español, "
            "sin saludos. Usa SOLO estos hechos; no inventes nada y no menciones nombres de clientes.\n"
            f"Hechos: {hechos}\nDecisión del sistema: {decision}")


def _redactar(despacho, v):
    """Guarda la redacción de la IA. Devuelve False si la IA no está disponible, para no seguir insistiendo en esta pasada."""
    try:
        texto = ia.redactar(_prompt(v, despacho.decision_auto), PLAZO_IA_SEG).strip()
    except ia.ErrorIA:
        return False
    if sugerencias.texto_valido(texto, [v]):
        Despacho.objects.filter(pk=despacho.pk).update(decision_ia=texto)
    return True


def ejecutar(forzar=False, max_viajes=None):
    """Una pasada: despacha lo que corresponde y devuelve {"despachos", "omitidos"}. Un viaje que falla no detiene a los demás: otra
    persona pudo tomar el camión o los pedidos entre el cálculo y este momento, y la próxima pasada vuelve a calcular."""
    salen, _, _ = planificar(forzar)
    despachos, omitidos, ia_disponible = [], [], True
    for v in salen[:max_viajes]:
        try:
            d = servicios.despachar(v["camion"], [p["orden"] for p in v["pedidos"]], decision=explicar(v))
        except ErrorDeNegocio as e:
            log.warning("Despacho automático omitido con %s: %s", v["camion"], " ".join(e.mensajes))
            omitidos.append({"camion": v["camion"], "mensajes": e.mensajes})
            continue
        log.info("Despacho automático N.º %s: %s", d.despacho_id, d.decision_auto)
        despachos.append(d)
        if ia_disponible and len(despachos) <= MAX_IA_POR_PASADA:
            ia_disponible = _redactar(d, v)
    return {"despachos": despachos, "omitidos": omitidos}


def _en_espera(agrupando, resto):
    """Por qué cada pedido sigue esperando, en frases para el panel."""
    lineas = []
    for v in agrupando:
        n = len(v["pedidos"])
        lineas.append(f"{n} pedido{'s' if n != 1 else ''} de rango {v['rango'].lower()} se agrupa{'n' if n != 1 else ''}: "
                      f"sale{'n' if n != 1 else ''} con {v['camion']} en {v['sale_en_min']} min o antes si se completan {sugerencias.MAX_PARADAS} paradas.")
    for s in resto["sin_camion"]:
        lineas.append(f"{s['pedidos']} pedido{'s' if s['pedidos'] != 1 else ''} de rango {s['rango'].lower()} sin camión apto: "
                      "ninguno libre tiene telemetría reciente, combustible suficiente y la cámara sin alerta.")
    if resto["sin_ubicar"]:
        lineas.append(f"Orden N.º {_lista(resto['sin_ubicar'])}: falta ubicarla en el mapa desde «Armar despacho».")
    if resto["mixtos"]:
        lineas.append(f"Orden N.º {_lista(resto['mixtos'])}: mezcla rangos de frío o no tiene productos.")
    if resto["reprogramar"]:
        lineas.append(f"Orden N.º {_lista(resto['reprogramar'])}: entrega no concretada; una persona decide si se reprograma.")
    return lineas


def estado():
    """Lo que muestra el panel: si está encendido, las reglas, los últimos viajes que decidió y qué sigue esperando y por qué."""
    encendido = activo()
    salen, agrupando, resto = planificar(forzar=not encendido)
    recientes = list(Despacho.objects.filter(decision_auto__isnull=False).select_related("camion").order_by("-despacho_id")[:3])
    return {"activo": encendido, "espera_min": espera_min(), "intervalo_seg": intervalo_seg(), "max_paradas": sugerencias.MAX_PARADAS,
            "max_viajes_a_mano": MAX_VIAJES_A_MANO, "listos": len(salen) + len(agrupando), "en_espera": _en_espera(agrupando, resto),
            "decisiones": [{"despacho": d, "texto": d.decision_ia or d.decision_auto, "por_ia": bool(d.decision_ia)} for d in recientes],
            "ahora": timezone.now()}
