"""Deja «Mi pedido llegó tibio» sin clasificar para clasificarlo en vivo en la defensa. Idempotente; no toca ningún otro requerimiento."""
from django.core.management.base import BaseCommand, CommandError

from clientes.models import Cliente
from clientes.muestra import SUPERMERCADOS_DEL_SUR
from crm import demo_ia


class Command(BaseCommand):
    help = "Crea o deja sin clasificar el requerimiento «Mi pedido llegó tibio» (Supermercados del Sur) de la demostración de la IA."

    def handle(self, *args, **opciones):
        cliente = Cliente.objects.filter(rut=SUPERMERCADOS_DEL_SUR).first()
        if cliente is None:
            raise CommandError("No existe el cliente de la demostración (Supermercados del Sur): carga los datos de demostración primero (FORZAR_CARGA_DEMO=1 o cargar_demo).")
        resultado, otros = demo_ia.restablecer(cliente)
        self.stdout.write(self.style.SUCCESS(f"«{demo_ia.ASUNTO}»: {resultado}."))
        if otros:
            self.stdout.write(self.style.WARNING(f"Hay {otros} más con el mismo asunto de este cliente; no se tocaron."))
