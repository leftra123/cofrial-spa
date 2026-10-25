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

# Segundo conjunto, escrito DESPUÉS de fijar el prompt y sin ajustar contra él (registros: formal, coloquial chileno, con faltas).
CASOS_NUEVOS = [
    ("Mediante la presente informo que la recepción de bodega estaba cerrada por inventario y no pudimos recibir la mercadería a la hora acordada", "nadie_en_casa", "baja"),
    ("wn el camion llego pero yo no estaba po, andaba en el banco, que lo traigan mañana nomas", "nadie_en_casa", "baja"),
    ("Las cajas de salmon venian con el hielo todo derretido y el pescado blandito, olia fuerte. Imposible recibirlo", "temperatura_inadecuada", "alta"),
    ("Se nota que el pedido fue golpeado: dos cajas aplastadas y un envase abierto con líquido afuera", "producto_danado", "alta"),
    ("Mi dirección es Pasaje Los Notros 112 en Labranza y el conductor fue a Los Notros de Temuco centro, perdimos la mañana", "direccion_incorrecta", "media"),
    ("Pedí 10 bandejas de pavo y solo bajaron 6, el resto no sé dónde quedó", "pedido_incompleto", "media"),
    ("Cambié de opinión, mi socio ya compró lo mismo y no necesitamos el pedido, disculpen las molestias", "rechazo_del_cliente", "baja"),
    ("Se supone que llegaba antes del mediodía, son las 5 de la tarde y el camión ni aparece, tengo el local lleno de gente esperando", "demora", "media"),
    ("Las hamburguesas llegaron tibias, el chofer dijo que el frio del camion andaba fallando. Mi hijo se enfermó con el almuerzo", "temperatura_inadecuada", "alta"),
    ("El sello de la bolsa de longanizas venia roto y estaban vencidas hace una semana", "producto_danado", "alta"),
    ("Llamé tres veces al número que dejaron y nadie contestó, en la sede no había nadie para firmar y el camión se devolvió", "nadie_en_casa", "baja"),
    ("Llegaron cortes de cerdo en lugar de los de vacuno que figuraban en la orden de compra, ¿pueden corregirlo hoy?", "pedido_incompleto", "media"),
]


class Command(BaseCommand):
    help = "Evalúa el desglose de reclamos de entrega con 15 mensajes y mide acierto de motivo y de urgencia."

    def add_arguments(self, p):
        p.add_argument("--conjunto", choices=["tuneado", "nuevo"], default="tuneado", help="«nuevo» = 12 textos no usados para ajustar el prompt")
        p.add_argument("--orden", help="proveedores en orden, por ejemplo gemini,groq")

    def handle(self, *args, orden=None, conjunto="tuneado", **opciones):
        casos = CASOS_NUEVOS if conjunto == "nuevo" else CASOS
        if orden:
            os.environ["IA_DESGLOSE_PROVEEDORES"] = orden
        motivo_ok = urgencia_ok = fallas = 0
        tiempos = []
        for texto, motivo, urgencia in casos:
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
        n = len(casos)
        tiempos.sort()
        self.stdout.write(self.style.SUCCESS(
            f"\nMotivo: {motivo_ok}/{n} = {100 * motivo_ok // n} % · Urgencia: {urgencia_ok}/{n} = {100 * urgencia_ok // n} % · sin respuesta: {fallas}"
            + (f" · latencia mediana {tiempos[len(tiempos) // 2]:.1f} s" if tiempos else "")))
