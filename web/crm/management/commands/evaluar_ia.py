"""Mide el acierto de la clasificación con IA sobre ejemplos etiquetados (CU-09 exige más de 85 % en la demo)."""
from django.core.management.base import BaseCommand

from crm import ia

CATEGORIAS = ["Consulta de producto", "Reclamo por temperatura", "Atraso en entrega", "Facturación", "Otro"]
EJEMPLOS = [
    ("El pedido llegó con la carga tibia y rechazamos dos cajas", "Reclamo por temperatura"),
    ("La cámara del camión venía a 9 grados, se echó a perder el pollo", "Reclamo por temperatura"),
    ("Los mariscos congelados llegaron blandos, se rompió la cadena de frío", "Reclamo por temperatura"),
    ("El termómetro de la caja marcaba una temperatura muy alta al recibir", "Reclamo por temperatura"),
    ("Mi pedido debía llegar ayer y todavía no aparece", "Atraso en entrega"),
    ("El camión lleva tres horas de retraso, ¿dónde está mi orden?", "Atraso en entrega"),
    ("Necesito saber cuándo entregan, la hora prometida ya pasó", "Atraso en entrega"),
    ("No ha llegado el despacho que pedí para el lunes", "Atraso en entrega"),
    ("¿El lomo vetado viene en cajas de cuántos kilos?", "Consulta de producto"),
    ("¿Tienen filete de salmón sin piel y cuál es su vida útil?", "Consulta de producto"),
    ("Quisiera saber si la pechuga de pollo tiene certificado sanitario", "Consulta de producto"),
    ("¿Venden costillar de cerdo en formato de 10 kilos?", "Consulta de producto"),
    ("La factura de mi última orden viene con el monto equivocado", "Facturación"),
    ("Necesito que me reenvíen la boleta del pedido 12", "Facturación"),
    ("Me cobraron dos veces la misma orden de compra", "Facturación"),
    ("Pido nota de crédito por la factura 4587", "Facturación"),
    ("Quiero felicitar al conductor que entregó hoy", "Otro"),
    ("¿Tienen vacantes de trabajo en la bodega?", "Otro"),
    ("Buenos días, quería hablar con alguien de la gerencia", "Otro"),
    ("Cambió mi teléfono de contacto, ¿cómo lo actualizo?", "Otro"),
]


class Command(BaseCommand):
    help = "Evalúa la IA con 20 mensajes etiquetados y compara con el 85 % que pide el informe."

    def handle(self, *args, **opciones):
        aciertos = fallas = 0
        for texto, esperada in EJEMPLOS:
            try:
                categoria, confianza = ia.clasificar("Consulta", texto, CATEGORIAS)
            except ia.ErrorIA as e:
                fallas += 1
                self.stdout.write(self.style.WARNING(f"SIN RESPUESTA  {texto[:55]}  ({str(e)[:60]})"))
                continue
            ok = categoria == esperada
            aciertos += ok
            self.stdout.write(f"{'OK ' if ok else 'MAL'} {confianza:.2f}  {texto[:55]:<55} -> {categoria}")
        total = len(EJEMPLOS)
        acierto = 100 * aciertos / total
        self.stdout.write(f"\nAcierto: {aciertos}/{total} = {acierto:.0f} %  (sin respuesta: {fallas}). Meta del informe: más de 85 %.")
        if acierto <= 85:
            raise SystemExit(1)
