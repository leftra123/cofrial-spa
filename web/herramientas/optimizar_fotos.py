"""Optimiza las fotos de web/static: deja el JPG original más liviano (es el respaldo) y genera variantes AVIF
`<nombre>-<ancho>.avif` que las plantillas ofrecen con srcset. Se corre en el computador del equipo; el resultado se
versiona y la EC2 no necesita Pillow.

    pip install pillow pillow-avif-plugin
    python herramientas/optimizar_fotos.py

Es idempotente: una foto cuyo JPG ya cabe en el ancho de respaldo no se vuelve a comprimir (evita pérdida acumulada).
"""
import io
from pathlib import Path

from PIL import Image
import pillow_avif  # noqa: F401  (registra el formato AVIF en Pillow)

ESTATICOS = Path(__file__).resolve().parent.parent / "static"
# (carpeta, anchos AVIF, ancho máximo del JPG de respaldo)
GRUPOS = [
    ("productos/propias", (400, 800), 560),
    ("productos", (), 400),                  # fotos de Commons: solo respaldo si no hay imagen propia, sin AVIF
    ("productos/categorias", (400,), 406),
    ("img/portada.jpg", (800, 1672), 1000),    # una sola foto de portada
]
CALIDAD_AVIF, CALIDAD_JPG = 50, 68


def avif(im, ancho):
    im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS) if im.width > ancho else im
    b = io.BytesIO(); im.save(b, "AVIF", quality=CALIDAD_AVIF, speed=4); return b.getvalue()


def procesar(ruta, anchos, ancho_jpg):
    with Image.open(ruta) as original:
        im = original.convert("RGB")
    for a in anchos:
        destino = ruta.with_name(f"{ruta.stem}-{a}.avif")
        if a <= im.width and not destino.exists():
            destino.write_bytes(avif(im, a))
    if im.width > ancho_jpg:
        r = im.resize((ancho_jpg, round(im.height * ancho_jpg / im.width)), Image.LANCZOS)
        r.save(ruta, "JPEG", quality=CALIDAD_JPG, optimize=True, progressive=True)


def main():
    for carpeta, anchos, ancho_jpg in GRUPOS:
        base = ESTATICOS / carpeta
        archivos = [base] if base.is_file() else sorted(base.glob("*.jpg"))
        for ruta in archivos:
            antes = ruta.stat().st_size; procesar(ruta, anchos, ancho_jpg)
            print(f"{ruta.relative_to(ESTATICOS)}: {antes // 1024} KB -> {ruta.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
