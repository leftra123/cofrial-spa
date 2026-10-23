"""Descarga una foto referencial por producto desde Wikimedia Commons (API pública: sin cuenta ni clave).

    python manage.py descargar_imagenes            # solo los productos que aún no tienen foto
    python manage.py descargar_imagenes --rehacer  # vuelve a buscar todas

Las fotos quedan en static/productos/ junto con creditos.json (autor, licencia y página de origen), que la tienda muestra
en el detalle del producto. Se descargan una vez y se versionan: la tienda no depende de internet ni de la API al funcionar.
Solo se aceptan licencias libres (dominio público, CC0, CC BY y CC BY-SA)."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "cofrial-spa-academico/1.0 (proyecto INACAP; contacto e.aguayo@edugalvarino.cl)"}
LIBRES = re.compile(r"^(cc0|public domain|pd|cc[- ]by(-sa)?[- ]\d)", re.I)

# Por SKU: términos de búsqueda (en inglés, Commons tiene mucho más material así) y palabra que debe aparecer en el título del archivo
BUSQUEDA = {
    "VAC-LOM-5K": (["raw beef steak", "beef striploin", "sirloin steak raw"], "steak|beef|sirloin|striploin"),
    "POL-PEC-10K": (["raw chicken breast"], "chicken"),
    "CER-COS-5K": (["raw pork ribs", "pork spareribs"], "pork|rib"),
    "PES-FIL-3K": (["raw salmon fillet"], "salmon"),
    "VAC-POS-5K": (["raw beef roast", "beef round raw", "raw beef cut"], "beef|roast|round"),
    "CER-LOM-4K": (["raw pork loin", "pork tenderloin raw", "pork chops raw"], "pork"),
    "COR-PIE-6K": (["raw lamb leg", "lamb meat raw", "leg of lamb"], "lamb"),
    "POL-TRU-8K": (["raw chicken drumsticks", "chicken legs raw"], "chicken|drumstick"),
    "POL-ENT-10K": (["whole raw chicken"], "chicken"),
    "PAV-PEC-5K": (["raw turkey breast", "turkey meat raw", "turkey breast"], "turkey"),
    "MAR-CAM-1K": (["raw shrimp", "peeled shrimp", "prawns raw", "frozen shrimp"], "shrimp|prawn|camar"),
    "VER-MIX-10K": (["frozen mixed vegetables", "frozen vegetables"], "vegetable"),
    "PAP-FRI-10K": (["frozen french fries", "french fries"], "fries|chips"),
    "LAC-QUE-5K": (["gouda cheese slices", "sliced cheese"], "cheese"),
    "EMB-JAM-3K": (["sliced cooked ham", "ham"], "ham"),
    "EMB-LON-4K": (["smoked sausages", "sausages raw", "sausage"], "sausage"),
}
# Sin entrada (no hay foto adecuada y libre en Commons; la tienda muestra la ilustración): carne molida, merluza, mix de mariscos y mantequilla.
EXCLUIR = re.compile(r"dinner|plant|impossible|vegan|restaurant|caf[eé]|queen|bird|coracias|fried|baking|breaded|making|recipe|sandwich|burger|tartare|breading|\(BM|chef|museum", re.I)


def _json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())


def _limpio(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


class Command(BaseCommand):
    help = "Descarga fotos referenciales de Wikimedia Commons (sin clave) y guarda sus créditos."

    def add_arguments(self, p):
        p.add_argument("--rehacer", action="store_true")

    def handle(self, *args, rehacer, **opciones):
        carpeta = Path(settings.BASE_DIR) / "static" / "productos"
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / "creditos.json"
        creditos = json.loads(archivo.read_text()) if archivo.exists() else {}
        for sku, (terminos, exigir) in BUSQUEDA.items():
            if sku in creditos and not rehacer:
                continue
            elegida = None
            for termino in terminos:
                elegida = self._buscar(termino, exigir)
                if elegida:
                    break
                time.sleep(1)
            if not elegida:
                self.stdout.write(f"{sku}: sin foto adecuada (se usará la ilustración)")
                creditos.pop(sku, None)
                (carpeta / f"{sku}.jpg").unlink(missing_ok=True)
                continue
            pag, info, meta, licencia = elegida
            try:
                datos = urllib.request.urlopen(urllib.request.Request(info["thumburl"], headers=UA), timeout=30).read()
            except Exception as e:
                self.stderr.write(f"{sku}: no se pudo descargar ({e})")
                continue
            (carpeta / f"{sku}.jpg").write_bytes(datos)
            creditos[sku] = {"autor": _limpio(meta.get("Artist", {}).get("value")) or "Autor no indicado", "licencia": licencia,
                             "pagina": info.get("descriptionurl"), "titulo": pag["title"].replace("File:", "")}
            self.stdout.write(f"{sku}: {creditos[sku]['titulo']} ({licencia})")
            archivo.write_text(json.dumps(creditos, ensure_ascii=False, indent=1))
            time.sleep(1)

    def _buscar(self, termino, exigir):
        if True:
            consulta = urllib.parse.urlencode({
                "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{termino} filetype:bitmap",
                "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 640})
            try:
                paginas = (_json(f"{API}?{consulta}").get("query") or {}).get("pages", {}).values()
            except Exception as e:
                self.stderr.write(f"«{termino}»: sin respuesta de Commons ({e})")
                return None
            for pag in sorted(paginas, key=lambda x: x.get("index", 99)):
                info = (pag.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                licencia = _limpio(meta.get("LicenseShortName", {}).get("value"))
                titulo = pag["title"]
                if (info.get("mime") == "image/jpeg" and info.get("width", 0) >= 900 and info.get("thumburl")
                        and LIBRES.match(licencia) and re.search(exigir, titulo, re.I) and not EXCLUIR.search(titulo)):
                    return pag, info, meta, licencia
        return None
