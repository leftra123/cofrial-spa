"""Mide el desglose con IA sobre 15 mensajes de «no pude recibir mi pedido» (como los escribiría un cliente de La Araucanía), con las APIs reales.

    python manage.py evaluar_desglose              # orden por defecto (Groq y luego Gemini)
    python manage.py evaluar_desglose --orden gemini,groq

Mide el acierto del motivo principal y de la urgencia contra la respuesta esperada. Gasta cuota gratuita (15 llamadas)."""
import os
import time

from django.core.management.base import BaseCommand

from crm import ia

CASOS = [
    ("Fui a recibir y no había nadie en la casa, el camión llegó cuando estábamos en el campo en Lautaro", "nadie_en_casa", "baja"),
    ("Llegó con la carga tibia, la caja de pollo estaba blanda y no la quise recibir", "temperatura_inadecuada", "alta"),
    ("Fueron a otra dirección, a Prieto Norte, y yo estoy en Prieto Sur. El chofer no me contestó el teléfono", "direccion_incorrecta", "media"),
    ("La caja venía rota y la carne se estaba saliendo del envase", "producto_danado", "alta"),
    ("Faltaron 2 cajas de lomo: en la guía decía 5 y llegaron 3", "pedido_incompleto", "media"),
    ("No voy a recibir el pedido porque ya lo compré en otro lado", "rechazo_del_cliente", "baja"),
    ("Llevo toda la tarde esperando, me dijeron entre las 14 y las 16 y ya son las 19", "demora", "media"),
    ("Los mariscos llegaron descongelados y con mal olor, se van a echar a perder y en la casa hay niños", "temperatura_inadecuada", "alta"),
    ("Estaba en el trabajo y no me avisaron antes de venir, nadie recibió en el local", "nadie_en_casa", "baja"),
    ("El pedido dice Av. Alemania 0671 y es 0617, el camión no encontró el lugar y se fue", "direccion_incorrecta", "media"),
    ("Me trajeron salmón en vez del filete de merluza que pedí", "pedido_incompleto", "media"),
    ("Se cortó el camino por la lluvia en Padre Las Casas y recién ahora me llamaron, el camión no pudo pasar", "demora", "media"),
    ("Llegó con el envase de la pechuga hinchado y la fecha vencida", "producto_danado", "alta"),
    ("El conductor llegó pero en el hospital no había nadie en bodega para recibir, quedó afuera", "nadie_en_casa", "baja"),
    ("El termómetro del camión marcaba 9 grados cuando abrimos las cajas, rechazamos todo", "temperatura_inadecuada", "alta"),
]


class Command(BaseCommand):
    help = "Evalúa el desglose de reclamos de entrega con 15 mensajes y mide acierto de motivo y de urgencia."

    def add_arguments(self, p):
        p.add_argument("--orden", help="proveedores en orden, por ejemplo gemini,groq")

    def handle(self, *args, orden=None, **opciones):
        if orden:
            os.environ["IA_DESGLOSE_PROVEEDORES"] = orden
        motivo_ok = urgencia_ok = fallas = 0
        tiempos = []
        for texto, motivo, urgencia in CASOS:
            t = time.monotonic()
            try:
                d = ia.desglosar(texto, "despachado")
            except ia.ErrorIA as e:
                fallas += 1
                self.stdout.write(self.style.WARNING(f"SIN RESPUESTA  {texto[:60]}  ({str(e)[:60]})"))
                continue
            seg = time.monotonic() - t
            tiempos.append(seg)
            m, u = d["motivo_principal"] == motivo, d["urgencia"] == urgencia
            motivo_ok += m
            urgencia_ok += u
            self.stdout.write(f"{'OK ' if m else 'MAL'} motivo  {'OK ' if u else 'MAL'} urgencia  {seg:3.1f}s  {texto[:48]:<48} -> {d['motivo_principal']}/{d['urgencia']}  (esperado {motivo}/{urgencia})")
        n = len(CASOS)
        tiempos.sort()
        self.stdout.write(self.style.SUCCESS(
            f"\nMotivo: {motivo_ok}/{n} = {100 * motivo_ok // n} % · Urgencia: {urgencia_ok}/{n} = {100 * urgencia_ok // n} % · sin respuesta: {fallas}"
            + (f" · latencia mediana {tiempos[len(tiempos) // 2]:.1f} s" if tiempos else "")))
