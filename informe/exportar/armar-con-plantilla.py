"""Injerta el contenido generado (docx-js) dentro de la plantilla institucional de INACAP.

La plantilla aporta la portada, el banner del encabezado, la barra del pie, la contraportada, los estilos
y la configuración de página. El contenido generado aporta índices, secciones, tablas y figuras.

    python3 armar-con-plantilla.py generado.docx Carta-1-vert.docx salida.docx "Título" "Subtítulo" "Nombre" "Asignatura" "Profesor" "Fecha"
"""
import re
import sys
import zipfile
from xml.sax.saxutils import escape

gen_path, tpl_path, out_path, titulo, subtitulo, nombre, asignatura, profesor, fecha, carrera = sys.argv[1:11]
zg, zt = zipfile.ZipFile(gen_path), zipfile.ZipFile(tpl_path)
T = {n: zt.read(n) for n in zt.namelist()}
doc_t = T["word/document.xml"].decode("utf-8")
rels_t = T["word/_rels/document.xml.rels"].decode("utf-8")
ct = T["[Content_Types].xml"].decode("utf-8")
styles = T["word/styles.xml"].decode("utf-8")
settings = T["word/settings.xml"].decode("utf-8")

# ------------------------------------------------------------------ contenido generado
gdoc = zg.read("word/document.xml").decode("utf-8")
grels = zg.read("word/_rels/document.xml.rels").decode("utf-8")
cuerpo = gdoc[gdoc.index("<w:body>") + 8:gdoc.rindex("</w:body>")]
fin = cuerpo.rindex("<w:sectPr")
cuerpo = cuerpo[:fin]  # se descarta el cierre del cuerpo; se reemplaza más abajo

# relaciones de imágenes y numeración
rel_items = re.findall(r'<Relationship ([^>]*?)/>', grels)
imagenes, numeracion = {}, None
for it in rel_items:
    rid = re.search(r'Id="([^"]+)"', it).group(1)
    tipo = re.search(r'Type="([^"]+)"', it).group(1)
    destino = re.search(r'Target="([^"]+)"', it).group(1)
    if tipo.endswith("/image"):
        imagenes[rid] = destino
    elif tipo.endswith("/numbering"):
        numeracion = destino

nuevos_rels, medios = [], {}
for k, (rid, destino) in enumerate(imagenes.items(), 1):
    ext = destino.rsplit(".", 1)[-1]
    nuevo = f"media/g_{k}.{ext}"
    medios["word/" + nuevo] = zg.read("word/" + destino)
    nuevos_rels.append(f'<Relationship Id="rIdG{rid[3:]}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{nuevo}"/>')
cuerpo = re.sub(r'r:embed="rId(\d+)"', lambda m: f'r:embed="rIdG{m.group(1)}"', cuerpo)

# estilos: encabezados y párrafo de lista con los identificadores de la plantilla
cuerpo = cuerpo.replace('w:val="Heading1"', 'w:val="Ttulo1"').replace('w:val="Heading2"', 'w:val="Ttulo2"').replace('w:val="Heading3"', 'w:val="Ttulo3"').replace('w:val="ListParagraph"', 'w:val="Prrafodelista"')

# ------------------------------------------------------------------ encabezados y pies
RF = '<w:rFonts w:ascii="Tahoma" w:hAnsi="Tahoma" w:cs="Tahoma"/>'
hdr1 = T["word/header1.xml"].decode("utf-8")
ftr1 = T["word/footer1.xml"].decode("utf-8")
ancho_h = 7780114
def escalar(xml, nuevo_ancho, ancho_ref, alto_ref):
    k = nuevo_ancho / ancho_ref
    xml = re.sub(r'<wp:extent cx="\d+" cy="\d+"/>', f'<wp:extent cx="{nuevo_ancho}" cy="{int(alto_ref * k)}"/>', xml)
    xml = re.sub(r'<a:ext cx="\d+" cy="\d+"/>', f'<a:ext cx="{nuevo_ancho}" cy="{int(alto_ref * k)}"/>', xml)
    return xml
hdr_l = escalar(hdr1, 10058400, 7780114, 1455420)
ftr_l = escalar(ftr1, 10058400, 7806447, 76234)
def con_numero(ftr, derecha):
    parrafo = ('<w:p><w:pPr><w:pStyle w:val="Piedepgina"/><w:ind w:left="0" w:right="%d"/><w:jc w:val="right"/></w:pPr>' % derecha +
               f'<w:r><w:rPr>{RF}<w:color w:val="595959"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
               f'<w:r><w:rPr>{RF}<w:color w:val="595959"/><w:sz w:val="18"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
               f'<w:r><w:rPr>{RF}<w:color w:val="595959"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
               f'<w:r><w:rPr>{RF}<w:color w:val="595959"/><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r>'
               f'<w:r><w:rPr>{RF}<w:color w:val="595959"/><w:sz w:val="18"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r></w:p>')
    i = ftr.index("<w:p>") if "<w:p>" in ftr else ftr.index("<w:p ")
    return ftr[:i] + parrafo + ftr[i:]
partes = {
    "word/headerL.xml": hdr_l,
    "word/footerN.xml": con_numero(ftr1, 851),
    "word/footerLN.xml": con_numero(ftr_l, 851),
}
rels_hf = {
    "word/_rels/headerL.xml.rels": T["word/_rels/header1.xml.rels"],
    "word/_rels/footerN.xml.rels": T["word/_rels/footer1.xml.rels"],
    "word/_rels/footerLN.xml.rels": T["word/_rels/footer1.xml.rels"],
}
nuevos_rels += [
    '<Relationship Id="rIdHL" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="headerL.xml"/>',
    '<Relationship Id="rIdFN" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footerN.xml"/>',
    '<Relationship Id="rIdFL" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footerLN.xml"/>',
]
if numeracion:
    nuevos_rels.append(f'<Relationship Id="rIdGnum" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="{numeracion}"/>')
    medios["word/" + numeracion] = zg.read("word/" + numeracion)

SECT_V = ('<w:sectPr><w:headerReference w:type="default" r:id="rId7"/><w:footerReference w:type="default" r:id="rIdFN"/><w:type w:val="nextPage"/>'
          '<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="0" w:right="851" w:bottom="0" w:left="851" w:header="0" w:footer="0" w:gutter="0"/><w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>')
SECT_H = ('<w:sectPr><w:headerReference w:type="default" r:id="rIdHL"/><w:footerReference w:type="default" r:id="rIdFL"/><w:type w:val="nextPage"/>'
          '<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/><w:pgMar w:top="0" w:right="851" w:bottom="0" w:left="851" w:header="0" w:footer="0" w:gutter="0"/><w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>')
SECT_PORTADA = ('<w:sectPr><w:headerReference w:type="default" r:id="rId7"/><w:footerReference w:type="default" r:id="rId8"/>'
                '<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="0" w:right="851" w:bottom="0" w:left="851" w:header="0" w:footer="0" w:gutter="0"/><w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>')
SECT_FINAL = SECT_PORTADA.replace("<w:pgSz", '<w:type w:val="nextPage"/><w:pgSz', 1)

cuerpo = re.sub(r'<w:sectPr.*?</w:sectPr>', lambda m: SECT_H if 'w:orient="landscape"' in m.group(0) else SECT_V, cuerpo, flags=re.S)

# la última sección del contenido termina en un párrafo propio
cierre_contenido = f'<w:p><w:pPr>{SECT_V}</w:pPr></w:p>'

# ------------------------------------------------------------------ portada y contraportada de la plantilla
raiz = doc_t[:doc_t.index("<w:body>") + 8]
for pref, uri in (("a", "http://schemas.openxmlformats.org/drawingml/2006/main"), ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")):
    if f"xmlns:{pref}=" not in raiz.split(">", 1)[0] + raiz[:raiz.index("<w:body>")]:
        raiz = raiz.replace("<w:document ", f'<w:document xmlns:{pref}="{uri}" ', 1)
cuerpo_t = doc_t[doc_t.index("<w:body>") + 8:doc_t.rindex("</w:body>")]
i_nombre = cuerpo_t.index("NOMBRE:")
fin_campos = cuerpo_t.index("</w:p>", i_nombre) + 6
portada = cuerpo_t[:fin_campos]
portada = portada.replace("TITULO PORTADA TRABAJO", escape(titulo)).replace("Ejemplo de subtítulo", escape(subtitulo))
def campo(texto, etiqueta, valor):
    if not valor:
        return texto
    return texto.replace(f"<w:t>{etiqueta}</w:t>", f'<w:t xml:space="preserve">{etiqueta} {escape(valor)}</w:t>').replace(f'<w:t xml:space="preserve">{etiqueta} </w:t>', f'<w:t xml:space="preserve">{etiqueta} {escape(valor)}</w:t>')
for et, val in (("NOMBRE:", nombre), ("CARRERA:", carrera), ("ASIGNATURA:", asignatura), ("PROFESOR:", profesor), ("FECHA:", fecha)):
    portada = campo(portada, et, val)
# los campos van a 12 pt, como en los informes anteriores del equipo
a = portada.rindex("<w:p ", 0, portada.index("NOMBRE:"))
portada = portada[:a] + portada[a:].replace('<w:cs w:cs="Tahoma"/>', '').replace('w:cs="Tahoma"/></w:rPr>', 'w:cs="Tahoma"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>')
cierre_portada = f'<w:p><w:pPr>{SECT_PORTADA}</w:pPr></w:p>'

# contraportada: la imagen con los logos
i_img = cuerpo_t.rindex("<w:drawing>")
ini_p = max(cuerpo_t.rfind("<w:p ", 0, i_img), cuerpo_t.rfind("<w:p>", 0, i_img))
parrafo_logos = cuerpo_t[ini_p:cuerpo_t.index("</w:p>", i_img) + 6]
vacio = '<w:p><w:pPr><w:ind w:firstLine="2410"/></w:pPr></w:p>'
contraportada = vacio * 2 + parrafo_logos

nuevo_doc = raiz + portada + cierre_portada + cuerpo + cierre_contenido + contraportada + SECT_FINAL + "</w:body></w:document>"

# ------------------------------------------------------------------ estilos y ajustes
def estilo(sid, nombre, ppr, rpr, extra=""):
    return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{nombre}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>{extra}<w:qFormat/>'
            f'<w:pPr>{ppr}</w:pPr><w:rPr>{RF}{rpr}</w:rPr></w:style>')
nuevos_estilos = (
    estilo("Caption", "caption", '<w:keepNext/><w:spacing w:before="240" w:after="80"/>', '<w:b/><w:bCs/><w:sz w:val="22"/><w:szCs w:val="22"/>')
    + estilo("TOC1", "toc 1", '<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="10530"/></w:tabs><w:spacing w:before="60" w:after="40"/>', '<w:b/><w:sz w:val="20"/><w:szCs w:val="20"/>', '<w:uiPriority w:val="39"/>')
    + estilo("TOC2", "toc 2", '<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="10530"/></w:tabs><w:spacing w:after="20"/><w:ind w:left="220"/>', '<w:sz w:val="19"/><w:szCs w:val="19"/>', '<w:uiPriority w:val="39"/>')
    + estilo("TOC3", "toc 3", '<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="10530"/></w:tabs><w:spacing w:after="20"/><w:ind w:left="440"/>', '<w:sz w:val="18"/><w:szCs w:val="18"/>', '<w:uiPriority w:val="39"/>')
    + estilo("TableofFigures", "table of figures", '<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="10530"/></w:tabs><w:spacing w:after="20"/>', '<w:i/><w:sz w:val="18"/><w:szCs w:val="18"/>', '<w:uiPriority w:val="99"/>')
)
styles = styles.replace("</w:styles>", nuevos_estilos + "</w:styles>")
if "w:updateFields" not in settings:
    for ancla in ("<w:hdrShapeDefaults", "<w:footnotePr", "<w:endnotePr", "<w:compat>", "<w:themeFontLang"):
        if ancla in settings:
            settings = settings.replace(ancla, '<w:updateFields w:val="true"/>' + ancla, 1)
            break

contenido = []
for nombre_parte in ("/word/headerL.xml", "/word/footerN.xml", "/word/footerLN.xml"):
    tipo = "header" if "header" in nombre_parte else "footer"
    contenido.append(f'<Override PartName="{nombre_parte}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{tipo}+xml"/>')
if numeracion:
    contenido.append('<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>')
ct = ct.replace("</Types>", "".join(contenido) + "</Types>")
rels_t = rels_t.replace("</Relationships>", "".join(nuevos_rels) + "</Relationships>")

with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", ct)
    for n, b in T.items():
        if n in ("[Content_Types].xml", "word/document.xml", "word/_rels/document.xml.rels", "word/styles.xml", "word/settings.xml"):
            continue
        z.writestr(n, b)
    z.writestr("word/document.xml", nuevo_doc)
    z.writestr("word/_rels/document.xml.rels", rels_t)
    z.writestr("word/styles.xml", styles)
    z.writestr("word/settings.xml", settings)
    for n, x in partes.items():
        z.writestr(n, x)
    for n, x in rels_hf.items():
        z.writestr(n, x)
    for n, b in medios.items():
        z.writestr(n, b)
print(f"Plantilla aplicada: {out_path}")
