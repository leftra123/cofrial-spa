"""Figuras de la dimensión H1-D1: árbol de problemas, ciclo de refuerzo y procesos BPMN AS-IS y TO-BE.

Se ejecuta desde la raíz del repositorio:

    python3 informe/img/generar-figuras-d1.py

Genera los archivos .drawio editables y los exporta a PNG con draw.io Desktop (comando `drawio`).
El árbol de problemas y el ciclo de refuerzo usan Mermaid, renderizado con Google Chrome sin interfaz.
"""
import html
import re
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

RAIZ = Path(__file__).resolve().parents[2]
IMG = RAIZ / "informe/img"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
DRAWIO = "/Applications/draw.io.app/Contents/MacOS/draw.io"

# ---------------------------------------------------------------------------------------------
# Mermaid (árbol de problemas y ciclo de refuerzo)
# ---------------------------------------------------------------------------------------------
ARBOL = """flowchart BT
  classDef causa fill:#fde8e8,stroke:#c0392b,color:#222
  classDef central fill:#fff2cc,stroke:#b8860b,color:#222,font-weight:bold
  classDef efecto fill:#e3eefc,stroke:#2c6fbb,color:#222
  classDef fin fill:#2c6fbb,stroke:#1b4a80,color:#fff,font-weight:bold

  C1["Servidor único en bodega,<br/>sin redundancia ni respaldos"]:::causa
  C2["Contabilidad en sistema cerrado<br/>e inventario en Excel locales"]:::causa
  C3["50 camiones sin GPS<br/>ni sensor de temperatura"]:::causa
  C4["Coordinación por WhatsApp<br/>y llamadas (Shadow IT)"]:::causa
  C5["Sin sitio transaccional<br/>ni CRM"]:::causa
  C6["Cartera de clientes en<br/>celulares personales"]:::causa

  P["PROBLEMA CENTRAL<br/>No existe un dato único, en línea y confiable<br/>de la operación"]:::central

  E1["Riesgo de pérdida total<br/>de datos"]:::efecto
  E2["Inventario descuadrado<br/>de forma permanente"]:::efecto
  E3["Ruptura de frío no detectada:<br/>mermas millonarias semanales"]:::efecto
  E4["Entregas fallidas"]:::efecto
  E5["Pedidos perdidos o<br/>mal registrados"]:::efecto
  E6["Sin embudo de ventas<br/>ni métricas de conversión"]:::efecto
  E7["Dependencia de las personas:<br/>la cartera se va con el vendedor"]:::efecto
  F["Riesgo de quiebra técnica frente a<br/>competidores digitalizados"]:::fin

  C1 --> P
  C2 --> P
  C3 --> P
  C4 --> P
  C5 --> P
  C6 --> P
  P --> E1
  P --> E2
  P --> E3
  P --> E4
  P --> E5
  P --> E6
  P --> E7
  E1 --> F
  E2 --> F
  E3 --> F
  E4 --> F
  E5 --> F
  E6 --> F
  E7 --> F
"""

CICLO = """flowchart TB
  classDef paso fill:#fde8e8,stroke:#c0392b,color:#222
  classDef clave fill:#fff2cc,stroke:#b8860b,color:#222,font-weight:bold

  A["El pedido llega por<br/>WhatsApp, llamada o correo"]:::paso
  B["Nadie lo registra en<br/>un sistema común"]:::paso
  C["Bodega no lo ve; el stock en Excel<br/>no coincide con contabilidad"]:::paso
  D["El camión sale sin GPS<br/>ni registro de temperatura"]:::paso
  E["La ruptura de frío o la entrega<br/>fallida no se detecta a tiempo"]:::clave
  F["Merma y cliente molesto"]:::paso
  G["Más llamadas y reclamos<br/>por canales informales"]:::paso

  A --> B --> C --> D --> E --> F --> G --> A
"""


def render_mermaid(codigo, destino, escala=2):
    """Dibuja un diagrama Mermaid y lo captura con Chrome, ajustando la ventana al tamaño real."""
    if not CHROME.exists():
        raise SystemExit("No se encontró Google Chrome para renderizar Mermaid")
    pagina = (
        '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff;padding:20px">'
        f'<pre class="mermaid">{html.escape(codigo)}</pre>'
        '<script type="module">'
        'import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
        'mermaid.initialize({startOnLoad:false,theme:"neutral",flowchart:{useMaxWidth:false,htmlLabels:true,curve:"basis"}});'
        'await mermaid.run();const b=document.querySelector("svg").getBoundingClientRect();'
        'document.title=Math.ceil(b.width)+"x"+Math.ceil(b.height);</script></body>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "m.html"
        f.write_text(pagina, encoding="utf-8")
        base = [str(CHROME), "--headless=new", "--disable-gpu", "--virtual-time-budget=30000"]
        medida = subprocess.run(base + ["--dump-dom", f"file://{f}"], capture_output=True, text=True).stdout
        m = re.search(r"<title>(\d+)x(\d+)</title>", medida)
        ancho, alto = (int(m.group(1)) + 60, int(m.group(2)) + 60) if m else (2400, 1600)
        subprocess.run(base + ["--hide-scrollbars", f"--window-size={ancho},{alto}",
                               f"--force-device-scale-factor={escala}", f"--screenshot={destino}", f"file://{f}"],
                       check=True, capture_output=True)
    print(f"  {destino.name}")


# ---------------------------------------------------------------------------------------------
# BPMN con draw.io
# ---------------------------------------------------------------------------------------------
ANCHO_TAREA, ALTO_TAREA = 130, 62
PASO_COL = 178
X0 = 190
ALTO_CARRIL = 200
ESTILO = {
    "inicio": "ellipse;html=1;aspect=fixed;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;fontSize=11;",
    "fin": "ellipse;html=1;aspect=fixed;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=4;verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;fontSize=11;",
    "evento": "ellipse;shape=doubleEllipse;html=1;aspect=fixed;fillColor=#ffe6cc;strokeColor=#d79b00;strokeWidth=2;verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;fontSize=11;",
    "tarea": "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;arcSize=12;",
    "compuerta": "rhombus;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=2;verticalLabelPosition=top;verticalAlign=bottom;labelPosition=center;align=center;fontSize=12;fontStyle=1;",
    "compuerta_b": "rhombus;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=2;verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;fontSize=12;fontStyle=1;",
}
TAMANO = {"inicio": (36, 36), "fin": (36, 36), "evento": (36, 36), "tarea": (ANCHO_TAREA, ALTO_TAREA), "compuerta": (52, 52), "compuerta_b": (52, 52)}


def construir_bpmn(titulo, carriles, nodos, flujos, dolores=None):
    """nodos: id -> (carril, columna, tipo, texto[, dy, dolor]); flujos: (origen, destino[, etiqueta, salida, entrada])."""
    celdas = []
    pos = {}
    n_col = max(n[1] for n in nodos.values()) + 1
    ancho = X0 + n_col * PASO_COL
    alto_total = 80 + len(carriles) * ALTO_CARRIL + (60 + 24 * len(dolores) if dolores else 20)
    celdas.append(f'<mxCell id="bg" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=none;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="{ancho + 40}" height="{alto_total}" as="geometry" /></mxCell>')
    celdas.append(f'<mxCell id="titulo" value={quoteattr("<b>" + titulo + "</b>")} style="text;html=1;align=left;verticalAlign=middle;fontSize=16;" vertex="1" parent="1"><mxGeometry x="20" y="10" width="{ancho}" height="30" as="geometry" /></mxCell>')
    for i, nombre in enumerate(carriles):
        y = 60 + i * ALTO_CARRIL
        relleno = "#F7F9FC" if i % 2 == 0 else "#FFFFFF"
        celdas.append(
            f'<mxCell id="carril{i}" value={quoteattr(nombre)} style="swimlane;horizontal=0;whiteSpace=wrap;html=1;startSize=34;fillColor={relleno};strokeColor=#5A6C86;fontStyle=1;fontSize=12;swimlaneFillColor={relleno};" vertex="1" parent="1">'
            f'<mxGeometry x="20" y="{y}" width="{ancho}" height="{ALTO_CARRIL}" as="geometry" /></mxCell>')
    for nid, spec in nodos.items():
        carril, col, tipo, texto = spec[:4]
        dy = spec[4] if len(spec) > 4 else 0
        w, h = TAMANO[tipo]
        cx = X0 + col * PASO_COL + ANCHO_TAREA / 2
        cy = 60 + carril * ALTO_CARRIL + ALTO_CARRIL / 2 + dy
        x, y = cx - w / 2, cy - h / 2
        pos[nid] = (x, y, w, h, carril, col)
        celdas.append(f'<mxCell id="{nid}" value={quoteattr(texto)} style={quoteattr(ESTILO[tipo])} vertex="1" parent="1"><mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}" as="geometry" /></mxCell>')
        if len(spec) > 5 and spec[5]:
            celdas.append(
                f'<mxCell id="dolor_{nid}" value="{spec[5]}" style="ellipse;html=1;aspect=fixed;fillColor=#c0392b;strokeColor=#ffffff;fontColor=#ffffff;fontStyle=1;fontSize=12;" vertex="1" parent="1">'
                f'<mxGeometry x="{x + w - 14:.0f}" y="{y - 12:.0f}" width="26" height="26" as="geometry" /></mxCell>')
    for k, f in enumerate(flujos):
        o, d = f[0], f[1]
        etiqueta = f[2] if len(f) > 2 else ""
        salida = f[3] if len(f) > 3 and f[3] else None
        entrada = f[4] if len(f) > 4 and f[4] else None
        _, _, _, _, co, cc = pos[o]
        _, _, _, _, cd, cdc = pos[d]
        if salida is None or entrada is None:
            if co == cd:
                salida, entrada = salida or (1, 0.5), entrada or (0, 0.5)
            elif cdc > cc:
                salida = salida or (1, 0.5)
                entrada = entrada or ((0.5, 0) if cd > co else (0.5, 1))
            else:
                salida = salida or ((0.5, 1) if cd > co else (0.5, 0))
                entrada = entrada or ((0.5, 0) if cd > co else (0.5, 1))
        estilo = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;strokeWidth=1.6;strokeColor=#333333;"
                  f"exitX={salida[0]};exitY={salida[1]};exitDx=0;exitDy=0;entryX={entrada[0]};entryY={entrada[1]};entryDx=0;entryDy=0;"
                  + ("labelBackgroundColor=#FFFFFF;fontSize=12;fontStyle=1;" if etiqueta else ""))
        celdas.append(f'<mxCell id="f{k}" value={quoteattr(etiqueta)} style={quoteattr(estilo)} edge="1" parent="1" source="{o}" target="{d}"><mxGeometry relative="1" as="geometry" /></mxCell>')
    if dolores:
        y0 = 60 + len(carriles) * ALTO_CARRIL + 14
        texto = "<b>Puntos de dolor</b><br/>" + "<br/>".join(f'<b style="color:#c0392b">{n}</b>  {t}' for n, t in dolores)
        celdas.append(f'<mxCell id="leyenda" value={quoteattr(texto)} style="text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;fontSize=12;" vertex="1" parent="1"><mxGeometry x="20" y="{y0}" width="{ancho}" height="{30 + 24 * len(dolores)}" as="geometry" /></mxCell>')
    ids = re.findall(r'<mxCell id="([^"]+)"', "".join(celdas))
    assert len(ids) == len(set(ids)), "ids repetidos"
    return ('<mxfile><diagram id="bpmn" name="BPMN"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{ancho + 40}" pageHeight="{alto_total}" math="0" shadow="0"><root><mxCell id="0" /><mxCell id="1" parent="0" />' + "".join(celdas) + "</root></mxGraphModel></diagram></mxfile>")


# ---------------------------------------------------------------------------------------------
# Procesos
# ---------------------------------------------------------------------------------------------
PROCESOS = {}

PROCESOS["p1-asis"] = dict(
    titulo="Proceso 1 AS-IS: pedido de un cliente institucional (B2B)",
    carriles=["Cliente institucional", "Vendedor", "Bodega", "Contabilidad"],
    nodos={
        "s": (0, 0, "inicio", "Necesita abastecerse"),
        "t1": (0, 1, "tarea", "Llama o envía un correo con el pedido"),
        "t2": (1, 2, "tarea", "Anota el pedido en su celular o en papel", 0, "1"),
        "t3": (1, 3, "tarea", "Avisa a bodega por WhatsApp", 0, "2"),
        "t4": (2, 4, "tarea", "Revisa el stock en su Excel local", 0, "3"),
        "g": (2, 5, "compuerta_b", "¿Hay stock?"),
        "t5": (1, 6, "tarea", "Llama al cliente y renegocia"),
        "e2": (1, 7, "fin", "Pedido perdido o ajustado"),
        "t6": (2, 6, "tarea", "Prepara el pedido"),
        "t7": (3, 7, "tarea", "Factura en un sistema cerrado y vuelve a digitar", 0, "4"),
        "t8": (2, 8, "tarea", "Despacha sin seguimiento", 0, "5"),
        "e1": (0, 9, "fin", "Pedido recibido"),
    },
    flujos=[("s", "t1"), ("t1", "t2"), ("t2", "t3"), ("t3", "t4"), ("t4", "g"),
            ("g", "t5", "No", (0.5, 0), (0, 0.5)), ("t5", "e2"),
            ("g", "t6", "Sí"), ("t6", "t7", "", (1, 0.5), (0.5, 0)), ("t7", "t8", "", (1, 0.5), (0.5, 1)),
            ("t8", "e1", "", (1, 0.5), (0, 0.5))],
    dolores=[("1", "Registro informal: el pedido vive en un celular o en papel."),
             ("2", "Canal no oficial: WhatsApp personal como medio de coordinación entre vendedor y bodega."),
             ("3", "Stock descuadrado: el Excel de bodega no coincide con contabilidad."),
             ("4", "Doble digitación: contabilidad vuelve a ingresar el pedido en un sistema cerrado sin enlace."),
             ("5", "Sin seguimiento: nadie sabe dónde está el pedido ni en qué condiciones viaja.")],
)

PROCESOS["p1-tobe"] = dict(
    titulo="Proceso 1 TO-BE: pedido B2B en la plataforma",
    carriles=["Cliente institucional", "E-commerce", "CRM", "Bodega", "Base de datos (RDS)"],
    nodos={
        "s": (0, 0, "inicio", "Necesita abastecerse"),
        "a1": (0, 1, "tarea", "Inicia sesión con perfil B2B"),
        "a2": (1, 2, "tarea", "Muestra el catálogo con la lista de precios institucional"),
        "a3": (0, 3, "tarea", "Arma el carrito y confirma la orden"),
        "g": (1, 4, "compuerta", "¿Hay stock?"),
        "a4": (1, 5, "tarea", "Informa y ofrece una alternativa", 55),
        "e2": (1, 6, "fin", "Orden no generada", 55),
        "r1": (4, 5, "tarea", "Registra la orden y descuenta el stock"),
        "c1": (2, 6, "tarea", "Orden visible para el vendedor asignado"),
        "b1": (3, 6, "tarea", "Ve la orden y prepara el pedido"),
        "b2": (3, 7, "tarea", "Asigna camión y despacha"),
        "e1": (0, 8, "fin", "Pedido entregado y con seguimiento"),
    },
    flujos=[("s", "a1"), ("a1", "a2", "", (1, 0.5), (0.5, 0)), ("a2", "a3", "", (1, 0.5), (0.5, 1)), ("a3", "g", "", (1, 0.5), (0, 0.5)),
            ("g", "a4", "No", (1, 0.5), (0, 0.5)), ("a4", "e2"),
            ("g", "r1", "Sí", (0.5, 1), (0, 0.5)),
            ("r1", "c1", "", (1, 0.5), (0, 0.5)), ("r1", "b1", "", (1, 0.5), (0, 0.5)),
            ("b1", "b2"), ("b2", "e1", "", (1, 0.5), (0, 0.5)), ("c1", "e1", "", (1, 0.5), (0, 0.5))],
)

PROCESOS["p2-asis"] = dict(
    titulo="Proceso 2 AS-IS: despacho con cadena de frío",
    carriles=["Despachador", "Conductor", "Cliente"],
    nodos={
        "s": (0, 0, "inicio", "Pedido listo para despachar"),
        "d1": (0, 1, "tarea", "Asigna la ruta por teléfono o WhatsApp", 0, "1"),
        "k1": (1, 2, "tarea", "Sale sin registro de temperatura ni GPS", 0, "2"),
        "i1": (1, 3, "evento", "La temperatura sube y nadie lo detecta", 0, "3"),
        "k2": (1, 4, "tarea", "Llega donde el cliente"),
        "g": (2, 5, "compuerta", "¿Carga en condiciones?"),
        "e1": (2, 6, "fin", "Entrega recibida", -55),
        "k3": (2, 6, "tarea", "Rechaza la carga", 55),
        "e2": (2, 7, "fin", "Merma", 55, "4"),
    },
    flujos=[("s", "d1"), ("d1", "k1", "", (1, 0.5), (0.5, 0)), ("k1", "i1"), ("i1", "k2"),
            ("k2", "g", "", (1, 0.5), (0, 0.5)),
            ("g", "e1", "Sí", (1, 0.5), (0, 0.5)),
            ("g", "k3", "No", (0.5, 1), (0, 0.5)), ("k3", "e2")],
    dolores=[("1", "Coordinación por canales informales: la ruta se asigna por teléfono o WhatsApp."),
             ("2", "Última milla a ciegas: sin GPS ni registro de temperatura."),
             ("3", "Ruptura de frío no detectada: nadie se entera hasta que el cliente abre la carga."),
             ("4", "Pérdida: la carga rechazada se convierte en merma y en un cliente molesto.")],
)

PROCESOS["p2-tobe"] = dict(
    titulo="Proceso 2 TO-BE: despacho con telemetría y alerta de frío",
    carriles=["Camión (IoT)", "Plataforma", "Despachador", "Cliente"],
    nodos={
        "s": (0, 0, "inicio", "Camión sale a ruta"),
        "a1": (0, 1, "tarea", "Envía telemetría cada pocos segundos"),
        "a2": (1, 2, "tarea", "Guarda la lectura en la base de datos"),
        "g": (1, 3, "compuerta_b", "¿Fuera de rango?"),
        "a3": (1, 4, "tarea", "Marca alerta_ruptura_frio = verdadero", 60),
        "a4": (2, 5, "tarea", "Ve la alerta en la torre de control y el dashboard"),
        "a5": (2, 6, "tarea", "Desvía o reprograma antes de entregar"),
        "j": (1, 7, "compuerta", "", 0),
        "a6": (1, 8, "tarea", "Actualiza el estado del pedido"),
        "a7": (3, 9, "tarea", "Ve el estado en el portal y recibe la carga"),
        "e1": (3, 10, "fin", "Entrega con trazabilidad"),
    },
    flujos=[("s", "a1"), ("a1", "a2", "", (1, 0.5), (0.5, 0)), ("a2", "g"),
            ("g", "a3", "Sí", (1, 0.5), (0, 0.5)), ("a3", "a4", "", (1, 0.5), (0.5, 0)), ("a4", "a5"),
            ("a5", "j", "", (1, 0.5), (0.5, 1)),
            ("g", "j", "No", (0.5, 0), (0.5, 0)),
            ("j", "a6"), ("a6", "a7", "", (1, 0.5), (0.5, 0)), ("a7", "e1")],
)

PROCESOS["p3-asis"] = dict(
    titulo="Proceso 3 AS-IS: gestión comercial de prospectos",
    carriles=["Vendedor", "Prospecto o cliente"],
    nodos={
        "s": (1, 0, "inicio", "Surge un contacto comercial"),
        "v1": (0, 1, "tarea", "Guarda el contacto en su celular", 0, "1"),
        "v2": (0, 2, "tarea", "Contacta por llamada o WhatsApp", 0, "2"),
        "v3": (0, 3, "tarea", "Envía la cotización por correo o WhatsApp", 0, "3"),
        "g": (1, 4, "compuerta_b", "¿Acepta?"),
        "v4": (0, 5, "tarea", "Anota el pedido en papel o en el celular"),
        "e1": (0, 6, "fin", "Pedido (proceso 1)"),
        "e2": (1, 5, "fin", "Prospecto perdido sin dejar rastro", 20, "4"),
    },
    flujos=[("s", "v1", "", (1, 0.5), (0.5, 1)), ("v1", "v2"), ("v2", "v3"), ("v3", "g", "", (1, 0.5), (0, 0.5)),
            ("g", "v4", "Sí", (0.5, 0), (0, 0.5)), ("v4", "e1"),
            ("g", "e2", "No", (1, 0.5), (0, 0.5))],
    dolores=[("1", "Cartera personal: los contactos viven en el celular del vendedor y se van con él."),
             ("2", "Canales informales: sin registro de lo conversado."),
             ("3", "Sin etapas ni métricas: nadie sabe cuántos prospectos hay ni en qué punto están."),
             ("4", "Pérdidas sin motivo registrado: no se aprende de las ventas no concretadas.")],
)

PROCESOS["p3-tobe"] = dict(
    titulo="Proceso 3 TO-BE: embudo comercial en el CRM",
    carriles=["Prospecto", "IA (servicio externo)", "CRM", "Vendedor", "Gerencia"],
    nodos={
        "s": (0, 0, "inicio", "Consulta en el portal o es ingresado"),
        "a1": (0, 1, "tarea", "Envía su requerimiento"),
        "i1": (1, 2, "tarea", "Clasifica el requerimiento"),
        "c1": (2, 3, "tarea", "Registra el prospecto y asigna vendedor"),
        "v1": (3, 4, "tarea", "Contacta y registra la interacción"),
        "v2": (3, 5, "tarea", "Envía la propuesta"),
        "v3": (3, 6, "tarea", "Negocia"),
        "g": (3, 7, "compuerta_b", "¿Acepta?"),
        "c2": (2, 8, "tarea", "Convierte en cliente (Cliente ganado)", -55),
        "c3": (2, 8, "tarea", "Cierra como Perdido, con el motivo", 55),
        "j": (2, 9, "compuerta", ""),
        "m1": (4, 10, "tarea", "Consulta la conversión en el dashboard"),
        "e1": (4, 11, "fin", "Cartera medida"),
    },
    flujos=[("s", "a1"), ("a1", "i1", "", (1, 0.5), (0.5, 0)), ("i1", "c1", "", (1, 0.5), (0.5, 0)),
            ("c1", "v1", "", (1, 0.5), (0.5, 0)), ("v1", "v2"), ("v2", "v3"), ("v3", "g"),
            ("g", "c2", "Sí", (0.5, 0), (0, 0.5)), ("g", "c3", "No", (1, 0.5), (0.5, 1)),
            ("c2", "j", "", (1, 0.5), (0.5, 0)), ("c3", "j", "", (1, 0.5), (0.5, 1)),
            ("j", "m1", "", (1, 0.5), (0.5, 0)), ("m1", "e1")],
)


def exportar_drawio(archivo):
    subprocess.run([DRAWIO, "-x", "-f", "png", "-e", "-b", "10", "-s", "1", "-o", str(archivo.with_suffix(".drawio.png")), str(archivo)],
                   check=True, capture_output=True)


if __name__ == "__main__":
    print("Mermaid:")
    render_mermaid(ARBOL, IMG / "d1-arbol-problemas.png")
    render_mermaid(CICLO, IMG / "d1-ciclo-refuerzo.png")
    print("BPMN:")
    for clave, p in PROCESOS.items():
        xml = construir_bpmn(p["titulo"], p["carriles"], p["nodos"], p["flujos"], p.get("dolores"))
        archivo = IMG / f"bpmn-{clave}.drawio"
        archivo.write_text(xml, encoding="utf-8")
        exportar_drawio(archivo)
        print(f"  {archivo.name}")
