"""Genera con IA (Gemini y Groq, los mismos proveedores del CRM) una ilustración SVG por producto.

    python manage.py generar_ilustraciones               # solo los productos sin foto ni ilustración propia
    python manage.py generar_ilustraciones --todos       # también los que ya tienen foto
    python manage.py generar_ilustraciones --sku PES-MER-5K --rehacer

Cada SVG se valida y se reconstruye con una lista blanca (catalogo/svg_seguro.py) y queda en static/productos/ia/ con el modelo
que lo creó (creditos.json). Se generan una vez y se versionan. En la tienda la prioridad es: foto, ilustración de IA, ilustración
genérica de la categoría. Necesita GEMINI_API_KEY o GROQ_API_KEY."""
import json
import os
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from catalogo.models import Producto
from catalogo.svg_seguro import SvgInvalido, limpiar

EJEMPLO = ('<svg viewBox="0 0 160 120" xmlns="http://www.w3.org/2000/svg"><ellipse cx="80" cy="104" rx="52" ry="7" fill="#0F172A" opacity=".08"/>'
           '<path d="M26 62C24 38 50 22 82 24c34 2 56 20 52 44-3 22-30 34-60 32-28-2-46-14-48-38z" fill="#E8575F"/>'
           '<path d="M34 60C34 44 54 32 80 33c26 1 44 14 41 32-3 16-24 26-48 24-22-2-39-10-39-29z" fill="#F4727A"/>'
           '<path d="M52 58c10-10 28-12 44-6M60 72c14 6 30 4 42-6" stroke="#FFF" stroke-width="3" stroke-linecap="round" fill="none" opacity=".7"/>'
           '<circle cx="104" cy="50" r="6" fill="#FFF" opacity=".75"/></svg>')

PROMPT = """Eres ilustrador de una tienda chilena de carnes y alimentos refrigerados. Dibuja en SVG una ilustración plana y reconocible de:
«{nombre}» ({categoria}). {descripcion}

Reglas estrictas:
- Dibuja SOLO el alimento, grande y centrado, sin marcos, tarjetas, cajas, fondos ni bordes decorativos (fondo transparente).
- Un solo <svg> con viewBox="0 0 160 120". Entre 8 y 30 formas simples (path, circle, ellipse, rect, polygon).
- Debe distinguirse a simple vista de qué alimento se trata: usa su forma, color y rasgos típicos (por ejemplo vetas de grasa, piel, escamas, hueso, láminas, envase).
- Colores realistas del alimento, con una sombra suave ovalada debajo. Sin texto ni letras.
- Sin <script>, <image>, <style>, <foreignObject>, enlaces ni referencias externas.
Ejemplo de estilo y nivel de detalle (un corte de carne roja, NO lo copies; dibuja el producto pedido):
{ejemplo}
Responde SOLO un JSON con esta forma: {{"svg": "<svg ...>...</svg>"}}"""


def _extraer(texto):
    """Saca el SVG de la respuesta: JSON con la clave svg, o el SVG directo si el modelo no respetó el formato."""
    texto = (texto or "").strip()
    try:
        inicio, fin = texto.index("{"), texto.rindex("}")
        return json.loads(texto[inicio:fin + 1])["svg"]
    except (ValueError, KeyError, TypeError):
        return texto


class Command(BaseCommand):
    help = "Genera ilustraciones SVG de productos con IA (Gemini/Groq) y las guarda validadas."

    def add_arguments(self, p):
        p.add_argument("--todos", action="store_true", help="incluye productos que ya tienen foto")
        p.add_argument("--rehacer", action="store_true", help="vuelve a generar aunque ya exista")
        p.add_argument("--sku", help="solo este producto")

    def handle(self, *args, todos, rehacer, sku, **opciones):
        from crm import ia
        os.environ.setdefault("IA_TIMEOUT_SEG", "90")
        os.environ.setdefault("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite")      # el modelo mayor dibuja mejor                 # un SVG tarda mucho más que clasificar un mensaje
        carpeta = Path(settings.BASE_DIR) / "static" / "productos"
        destino = carpeta / "ia"
        destino.mkdir(parents=True, exist_ok=True)
        archivo = destino / "creditos.json"
        creditos = json.loads(archivo.read_text()) if archivo.exists() else {}
        productos = Producto.objects.filter(activo=True).select_related("categoria").order_by("sku")
        if sku:
            productos = productos.filter(sku=sku)
        for p in productos:
            if not (todos or sku) and (carpeta / f"{p.sku}.jpg").exists():
                continue
            if p.sku in creditos and not rehacer:
                continue
            for intento in (1, 2):                                     # un segundo intento si el SVG no pasa la validación
                try:
                    texto = ia._llamar(PROMPT.format(nombre=p.nombre, categoria=p.categoria.nombre, descripcion=p.descripcion, ejemplo=EJEMPLO))
                    svg = limpiar(_extraer(texto))
                    break
                except (ia.ErrorIA, SvgInvalido) as e:
                    svg = None
                    self.stderr.write(f"{p.sku} (intento {intento}): {e}")
            if svg is None:
                continue
            (destino / f"{p.sku}.svg").write_text(svg)
            creditos[p.sku] = {"modelo": ia.ultimo_modelo or "IA", "producto": p.nombre}
            archivo.write_text(json.dumps(creditos, ensure_ascii=False, indent=1))
            self.stdout.write(f"{p.sku}: ilustración creada con {creditos[p.sku]['modelo']} ({len(svg)} bytes)")
            time.sleep(1)
