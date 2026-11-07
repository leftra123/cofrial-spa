"""Tiempo acelerado de la demostración: cuántas veces más rápido avanzan los camiones.

Un viaje real a Angol toma unas 3 horas a 50 km/h, así que en una defensa de minutos no se alcanzaría a ver. Un administrador elige el
multiplicador en /demo/, queda en la tabla ajuste_simulador y el simulador lo lee en cada ciclo, igual que los escenarios: no se recrea ningún
contenedor y un cambio se nota en la lectura siguiente.

Qué cambia y qué no:
  - Cambia solo la velocidad del camión. La hora de llegada usa el mismo multiplicador, por eso sigue diciendo cuándo llegará de verdad.
  - La telemetría sigue entrando cada INTERVALO_SEG con los mismos campos, y las reglas de frío y de despacho son las de siempre.
  - CONFIRMACION_AUTO_SEG no se acelera: lo responde una persona frente a la pantalla, que necesita los mismos segundos a cualquier velocidad.
  - Como el camión avanza varios km por lectura, «está por llegar» se avisa antes, para que el aviso alcance a verse (`umbral_cerca_km`).
"""
from django.conf import settings

from .models import AjusteSimulador

MULTIPLICADORES = (1, 5, 20, 60)     # los mismos de la restricción de la tabla y de iot/simulador.py
NORMAL = 1
CERCA_KM = 2                         # a velocidad normal, «está por llegar» parte a esta distancia
KM_A_ANGOL = 130                     # el ejemplo que muestra /demo/
AVISO_CERCA_SEG = 20                 # con tiempo acelerado, el aviso dura al menos esto: la campanita consulta cada 15 s


class ErrorTiempo(Exception):
    """El multiplicador no se acepta; el mensaje es para mostrarlo en pantalla."""


def multiplicador():
    guardado = AjusteSimulador.objects.filter(pk=AjusteSimulador.UNICO).values_list("multiplicador_tiempo", flat=True).first()
    return guardado or NORMAL


def cambiar(valor, usuario=None):
    """Guarda el multiplicador pedido. Solo se aceptan los de la lista: el valor llega del navegador."""
    if str(valor) not in {str(m) for m in MULTIPLICADORES}:
        raise ErrorTiempo("Ese multiplicador no está en la lista.")
    elegido = int(valor)
    AjusteSimulador.objects.update_or_create(pk=AjusteSimulador.UNICO, defaults={"multiplicador_tiempo": elegido, "actualizado_por": usuario})
    return elegido


def restablecer(usuario=None):
    return cambiar(NORMAL, usuario)


def estado():
    m = multiplicador()
    return {"multiplicador": m, "acelerado": m > NORMAL, "opciones": list(MULTIPLICADORES), "minutos_a_angol": max(1, round(minutos_de_viaje(KM_A_ANGOL, m)))}


def minutos_de_viaje(km, m=None):
    """Minutos reales que tardará el camión en recorrer `km` a la velocidad actual de la simulación."""
    return km / (settings.VELOCIDAD_MEDIA_KMH * (m or multiplicador())) * 60


def umbral_cerca_km(m):
    """Distancia a la que parte «está por llegar». A 60× el camión avanza más de 4 km por lectura y cruzaría los 2 km sin que nadie lo viera."""
    return max(CERCA_KM, round(settings.VELOCIDAD_MEDIA_KMH * m * AVISO_CERCA_SEG / 3600))
