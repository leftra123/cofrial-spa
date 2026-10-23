"""Prueba en vivo la IA externa con la clave del entorno: sirve para verificar GEMINI_API_KEY antes de la demo."""
from django.core.management.base import BaseCommand

from crm import ia
from crm.models import CategoriaRequerimiento


class Command(BaseCommand):
    help = "Clasifica un mensaje de ejemplo con la IA real y muestra categoría y confianza."

    def add_arguments(self, parser):
        parser.add_argument("--texto", default="El camión llegó con la carga tibia y rechazamos dos cajas.")

    def handle(self, *args, texto, **opciones):
        categorias = list(CategoriaRequerimiento.objects.values_list("nombre", flat=True)) or ["Consulta de producto", "Reclamo por temperatura", "Atraso en entrega", "Facturación", "Otro"]
        try:
            categoria, confianza = ia.clasificar("Prueba", texto, categorias)
        except ia.ErrorIA as e:
            self.stdout.write(self.style.ERROR(f"La IA no respondió: {e}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"IA operativa: «{categoria}» con confianza {confianza:.2f} (modelo: {ia.ultimo_modelo})"))
