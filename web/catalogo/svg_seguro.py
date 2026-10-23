"""Valida y limpia un SVG generado por IA antes de guardarlo: solo formas básicas, sin scripts, enlaces ni estilos externos.

Se reconstruye desde cero con una lista blanca de etiquetas y atributos; lo que no está en la lista se descarta."""
import re
import xml.etree.ElementTree as ET

ETIQUETAS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient",
             "radialgradient", "stop", "title"}
ATRIBUTOS = {"viewbox", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "width", "height", "points", "fill",
             "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity",
             "transform", "id", "offset", "stop-color", "stop-opacity", "gradientunits", "fill-rule", "stroke-dasharray"}
MAX_BYTES = 12_000
MAX_ELEMENTOS = 80
SEGURO = re.compile(r"^[#\w\s.,()%\-+]*$")          # sin url(http...), comillas ni punto y coma dentro de valores


class SvgInvalido(ValueError):
    pass


def _local(nombre):
    return nombre.rsplit("}", 1)[-1].lower()


def limpiar(texto):
    if not texto or len(texto) > MAX_BYTES:
        raise SvgInvalido("vacío o demasiado grande")
    if re.search(r"<!(DOCTYPE|ENTITY)|<\?xml-stylesheet", texto, re.I):
        raise SvgInvalido("contiene DOCTYPE o entidades")
    inicio = texto.lower().find("<svg")
    fin = texto.lower().rfind("</svg>")
    if inicio < 0 or fin < 0:
        raise SvgInvalido("no es un SVG")
    try:
        raiz = ET.fromstring(texto[inicio:fin + 6])
    except ET.ParseError as e:
        raise SvgInvalido(f"XML mal formado: {e}")
    if _local(raiz.tag) != "svg":
        raise SvgInvalido("la raíz no es svg")
    cuenta = 0

    def copiar(el):
        nonlocal cuenta
        etiqueta = _local(el.tag)
        if etiqueta not in ETIQUETAS:
            return None
        cuenta += 1
        if cuenta > MAX_ELEMENTOS:
            raise SvgInvalido("demasiados elementos")
        nuevo = ET.Element(etiqueta)
        for k, v in el.attrib.items():
            k = _local(k)
            if k in ATRIBUTOS and SEGURO.match(v) and "url(" not in v.lower():
                nuevo.set("viewBox" if k == "viewbox" else k, v)
        if etiqueta == "title" and el.text:
            nuevo.text = re.sub(r"[^\w\s.,\-áéíóúñÁÉÍÓÚÑ]", "", el.text)[:80]
        for hijo in el:
            c = copiar(hijo)
            if c is not None:
                nuevo.append(c)
        return nuevo

    limpio = copiar(raiz)
    if cuenta < 3:
        raise SvgInvalido("casi no tiene formas")
    limpio.set("xmlns", "http://www.w3.org/2000/svg")
    if not limpio.get("viewBox"):
        limpio.set("viewBox", "0 0 160 120")
    limpio.attrib.pop("width", None)
    limpio.attrib.pop("height", None)
    return ET.tostring(limpio, encoding="unicode")
