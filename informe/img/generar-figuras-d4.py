"""Figuras de la dimensión H1-D4: wireframes, user journeys, arquitectura del CRM, estados y casos de uso.

Se ejecuta desde la raíz del repositorio (requiere Google Chrome e internet para Mermaid):

    python3 informe/img/generar-figuras-d4.py

Los wireframes y los journeys son HTML capturado con Chrome sin interfaz; el resto usa Mermaid.
"""
import html
import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
IMG = RAIZ / "informe/img"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

_spec = importlib.util.spec_from_file_location("figuras_d1", IMG / "generar-figuras-d1.py")
_d1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_d1)
render_mermaid = _d1.render_mermaid


def render_html(cuerpo, destino, ancho, alto, escala=1.5):
    """Captura un documento HTML con Chrome sin interfaz."""
    doc = f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body>{cuerpo}</body>'
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "p.html"
        f.write_text(doc, encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={ancho},{alto}",
                        f"--force-device-scale-factor={escala}", "--virtual-time-budget=5000", f"--screenshot={destino}", f"file://{f}"],
                       check=True, capture_output=True)
    print(f"  {destino.name}")


CSS = """
*{box-sizing:border-box} body{margin:0;background:#fff;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;color:#2b2f36;font-size:13px}
.marco{display:flex;gap:18px;padding:16px;background:#f3f4f6;width:1400px}
.ventana{width:1010px;background:#fff;border:1.5px solid #8a93a3;border-radius:8px;overflow:hidden;position:relative}
.barra{background:#dfe3e8;height:30px;display:flex;align-items:center;padding:0 10px;gap:6px;border-bottom:1px solid #b8bfca}
.punto{width:10px;height:10px;border-radius:50%;background:#a6adb9}.url{margin-left:12px;background:#fff;border:1px solid #b8bfca;border-radius:12px;padding:2px 14px;font-size:11px;color:#667}
.leyenda{width:340px;background:#fff;border:1.5px solid #c9ced6;border-radius:8px;padding:14px 16px;font-size:12.5px;line-height:1.4}
.leyenda h3{margin:0 0 8px;font-size:13px}.leyenda p{margin:7px 0;display:flex;gap:8px}.leyenda .num{flex:none}
.n{position:absolute;top:-9px;right:-9px;width:22px;height:22px;border-radius:50%;background:#c0392b;color:#fff;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;border:2px solid #fff;z-index:5}
.n.i{position:static;display:inline-flex;flex:none}
.n.l{right:auto;left:-9px}
.rel{position:relative}
.cab{display:flex;align-items:center;gap:14px;padding:10px 18px;border-bottom:1px solid #d3d8df;background:#fafbfc}
.logo{background:#c9ced6;border:1.5px dashed #8a93a3;padding:6px 14px;font-weight:700;letter-spacing:1px}
.busca{flex:1;border:1.5px solid #b8bfca;border-radius:16px;padding:7px 14px;color:#8a93a3;background:#fff}
.enl{color:#556;margin:0 4px}.chip{border:1.5px solid #8a93a3;border-radius:14px;padding:5px 12px;background:#fff}
.btn{display:inline-block;border:1.5px solid #4a5568;border-radius:6px;padding:7px 16px;background:#e8ecf2;font-weight:600}
.btn.p{background:#4a6fa5;color:#fff;border-color:#3b5a88}.btn.g{background:#fff}.btn.r{background:#fbe3e0;border-color:#c0392b;color:#8e2a1f}
.caja{border:1.5px solid #b8bfca;border-radius:8px;background:#fff}.gris{background:#eceff3}
.img{background:repeating-linear-gradient(45deg,#e6e9ee,#e6e9ee 8px,#dde1e7 8px,#dde1e7 16px);border:1.5px dashed #9aa3b2;display:flex;align-items:center;justify-content:center;color:#7a8394;font-size:11px}
.fila{display:flex;gap:14px}.col{display:flex;flex-direction:column;gap:10px}.pad{padding:18px}
.t{font-weight:700;font-size:15px;margin:0 0 8px}.m{color:#6b7280;font-size:12px}.ins{display:inline-block;border-radius:10px;padding:2px 9px;font-size:11px;font-weight:600}
.azul{background:#dbe6f6;color:#254a80}.verde{background:#d8f0dd;color:#1e6b34}.rojo{background:#f9dcd8;color:#8e2a1f}.amar{background:#fcefc7;color:#7a5b00}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #d3d8df;padding:7px 8px;text-align:left}th{background:#eceff3;font-size:12px}
.lat{width:190px;flex:none}.crm{display:flex;min-height:560px}.menu{width:150px;background:#2f3a4d;color:#dfe5ef;padding:14px 0;flex:none}
.menu div{padding:9px 16px}.menu .act{background:#4a6fa5;color:#fff;font-weight:700}
.kan{display:flex;gap:10px;padding:14px}.kc{flex:1;background:#eef1f5;border-radius:8px;padding:8px;min-width:0}
.kc h4{margin:0 0 8px;font-size:12px;display:flex;justify-content:space-between}.tj{background:#fff;border:1.5px solid #b8bfca;border-radius:6px;padding:8px;margin-bottom:8px;font-size:11.5px}
.tl{display:flex;align-items:center;gap:0;margin:8px 0 14px}.tp{flex:1;text-align:center;font-size:11px;position:relative}.tp i{display:block;width:18px;height:18px;border-radius:50%;background:#d3d8df;margin:0 auto 4px;border:2px solid #fff;box-shadow:0 0 0 1.5px #9aa3b2}
.tp.ok i{background:#4a6fa5}.tp.ya i{background:#fff;box-shadow:0 0 0 3px #4a6fa5}
.mapa{background:#dfe9dd;border:1.5px dashed #8aa08a;height:150px;position:relative}.cam{position:absolute;left:55%;top:48%;background:#c0392b;color:#fff;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:700}
/* journeys */
.jm{width:1900px;padding:20px 24px;background:#fff}.jm h2{margin:0 0 4px;font-size:20px}.jm .sub{color:#5b6472;margin-bottom:12px;font-size:13px}
.jg{display:grid;grid-template-columns:150px repeat(6,1fr);gap:0;border:1.5px solid #8a93a3}
.jg>div{padding:9px 10px;border-bottom:1px solid #d3d8df;border-right:1px solid #d3d8df;font-size:12.5px;line-height:1.35}
.jg .h{background:#2f3a4d;color:#fff;font-weight:700;font-size:13.5px;text-align:center}.jg .r{background:#eef1f5;font-weight:700}
.jg .hoy{background:#fdf0ee}.jg .tobe{background:#eef7ef}.jg .emo{padding:0;border-right:none;grid-column:2/8;height:130px;position:relative}
.jg .emol{height:130px}.leyj{margin-top:10px;font-size:12px;color:#444;display:flex;gap:22px}
"""


def leyenda(items):
    return '<div class="leyenda"><h3>Anotaciones</h3>' + "".join(
        f'<p><span class="n i">{i}</span><span>{t}</span></p>' for i, t in enumerate(items, 1)) + "</div>"


def ventana(url, cuerpo, notas, alto=700):
    return (f'<div class="marco"><div class="ventana" style="min-height:{alto}px"><div class="barra"><span class="punto"></span><span class="punto"></span><span class="punto"></span>'
            f'<span class="url">{url}</span></div>{cuerpo}</div>{leyenda(notas)}</div>')


def N(n):
    return f'<span class="n">{n}</span>'


def NL(n):
    return f'<span class="n l">{n}</span>'


def cabecera(usuario, carrito="Carrito (3)"):
    return (f'<div class="cab"><span class="logo">COFRIAL</span><span class="busca">Buscar productos…</span>'
            f'<span class="enl">Catálogo</span><span class="enl">Mis pedidos</span><span class="chip">{usuario}</span><span class="btn g">{carrito}</span></div>')


def tarjeta(nombre, precio, etq, stock, extra="", dis=False):
    return (f'<div class="caja pad rel" style="width:200px"><div class="img" style="height:90px;margin-bottom:8px">foto</div>'
            f'<div style="font-weight:700;margin-bottom:3px">{nombre}</div><div class="m">{etq}</div>'
            f'<div style="font-size:18px;font-weight:800;margin:4px 0">{precio}</div>{stock}<div style="margin-top:8px"><span class="btn g" style="padding:3px 10px">- 1 +</span> {'<span class="btn" style="padding:4px 10px;background:#e5e7eb;color:#9ca3af;border-color:#d1d5db">Agregar</span>' if dis else '<span class="btn p" style="padding:4px 10px">Agregar</span>'}</div>{extra}</div>')


# ---------------------------------------------------------------------------------------------
# Wireframes del portal
# ---------------------------------------------------------------------------------------------
def w1():
    cuerpo = (f'<div class="cab"><span class="logo">COFRIAL</span><span class="busca">Buscar productos…</span><span class="enl">Seguir mi pedido</span><span class="btn g">Ingresar</span></div>'
              '<div class="pad" style="text-align:center"><div class="img" style="height:120px;margin-bottom:14px">Imagen: cadena de frío monitoreada</div>'
              '<div style="font-size:22px;font-weight:800">Carnes y refrigerados con la temperatura bajo control</div><div class="m" style="margin:6px 0 20px">Elija cómo desea comprar</div>'
              '<div class="fila" style="justify-content:center;gap:30px">'
              f'<div class="caja pad rel" style="width:340px;text-align:left">{N(1)}<div class="t">Soy una institución</div><div class="m">Hospitales, supermercados, ferias y empresas</div><ul style="padding-left:18px;margin:10px 0"><li>Lista de precios institucional</li><li>Pedidos por volumen y orden de compra</li><li>Vendedor asignado</li></ul><span class="btn p">Ingresar con RUT de la empresa</span></div>'
              f'<div class="caja pad rel" style="width:340px;text-align:left">{N(1)}<div class="t">Soy cliente particular</div><div class="m">Compra para el hogar</div><ul style="padding-left:18px;margin:10px 0"><li>Precios públicos</li><li>Compra en pocos pasos</li><li>Seguimiento del despacho</li></ul><span class="btn p">Ver catálogo</span></div></div>'
              f'<div class="fila rel" style="justify-content:center;gap:40px;margin-top:22px">{N(2)}<span class="ins azul">Temperatura monitoreada en cada viaje</span><span class="ins azul">Seguimiento en línea</span><span class="ins azul">Respaldo en la nube</span></div></div>')
    notas = ["El perfil elegido decide la lista de precios: <b>tipo_cliente → lista_precio</b>. Un cliente B2B nunca ve el precio público ni al revés.",
             "Mensajes de confianza que responden al dolor del caso (cadena de frío y trazabilidad). Se alimentan de datos reales, no de texto fijo.",
             "Acceso directo a «Seguir mi pedido» por número de orden, para quien llega desde un correo."]
    return ventana("https://cofrial.example/", cuerpo, notas, 620)


def w2():
    stock = '<span class="ins verde">Stock: 120</span>'
    filtros = (f'<div class="lat col rel">{N(2)}<div class="t">Filtros</div><div><b>Categoría</b><br>[x] Cárnicos refrigerados<br>[x] Congelados<br>[ ] Aves</div>'
               '<div><b>Rango de temperatura</b><br>( ) Refrigerado 0 a 4 °C<br>( ) Congelado -25 a -18 °C</div><div><b>Disponibilidad</b><br>[ ] Solo con stock</div></div>')
    grid = ('<div class="fila" style="flex-wrap:wrap;gap:14px;flex:1">'
            + tarjeta("Lomo vetado de vacuno 5 kg", f'$38.990{N(1)}', "Precio institucional (neto)", stock, f'')
            + tarjeta("Pechuga de pollo 10 kg", "$29.990", "Precio institucional (neto)", '<span class="ins amar">Stock: 8</span>')
            + tarjeta("Mariscos congelados 2 kg", "$21.990", "Precio institucional (neto)", '<span class="ins amar">Stock: 12</span>')
            + tarjeta("Salmón congelado 1 kg", "$14.990", "Precio institucional (neto)", '<span class="ins rojo">Sin stock</span>', N(3), True)
            + '</div>')
    cuerpo = (cabecera("Hospital Regional de Temuco · B2B") + '<div class="pad"><div class="fila" style="justify-content:space-between;align-items:center;margin-bottom:12px">'
              f'<div class="t" style="margin:0">Catálogo de refrigerados</div><span class="btn g rel">Repetir mi último pedido{N(4)}</span></div><div class="fila">{filtros}{grid}</div></div>')
    notas = ["El precio sale de <b>precio_producto</b> según la lista del perfil. La etiqueta indica qué lista se aplica.",
             "El filtro por temperatura usa <b>categoria → rango_temperatura</b>: el cliente institucional compra por requisito de frío.",
             "El stock viene de <b>producto.stock_disponible</b>. Con stock cero, el botón Agregar se deshabilita.",
             "Solo B2B: «Repetir mi último pedido» copia las líneas de la última orden al carrito (compra recurrente)."]
    return ventana("https://cofrial.example/catalogo", cuerpo, notas, 640)


def w3():
    cuerpo = (cabecera("Hospital Regional de Temuco · B2B") + '<div class="pad"><div class="m">Catálogo › Cárnicos refrigerados › Lomo vetado</div>'
              '<div class="fila" style="margin-top:10px;gap:24px"><div class="img" style="width:360px;height:300px">foto del producto</div><div class="col" style="flex:1">'
              '<div style="font-size:20px;font-weight:800">Lomo vetado de vacuno 5 kg</div><div class="m">SKU VAC-LOM-5K · Unidad: caja</div>'
              f'<div class="rel" style="width:max-content">{N(1)}<span class="ins azul" style="font-size:13px">Conservar entre 0 y 4 °C</span></div>'
              f'<div class="rel" style="font-size:26px;font-weight:800;width:max-content">$38.990{N(2)}</div><div class="m">Precio institucional (neto) por caja</div>'
              '<div><span class="ins verde">Stock: 120 cajas</span></div><div class="fila" style="align-items:center"><span class="btn g">- 10 +</span><span class="btn p">Agregar al carrito</span></div>'
              '<div class="caja pad"><b>Descripción</b><br>Corte envasado al vacío. Se despacha en camión refrigerado con registro de temperatura.</div></div></div></div>')
    notas = ["El rango de conservación sale de la categoría (<b>rango_temperatura</b>) y es el mismo que usa la alerta de ruptura de frío.",
             "Precio de la lista del perfil; el B2C vería su precio público.",]
    return ventana("https://cofrial.example/producto/VAC-LOM-5K", cuerpo, notas, 600)


def w4():
    filas = ("<tr><td>Lomo vetado de vacuno 5 kg</td><td>10</td><td>$38.990</td><td>$389.900</td></tr>"
             "<tr><td>Pechuga de pollo 10 kg</td><td>5</td><td>$29.990</td><td>$149.950</td></tr>"
             f"<tr><td>Mariscos congelados 2 kg</td><td><span class='rel' style='padding-right:12px'>20{N(1)}</span></td><td>$21.990</td><td>$439.800</td></tr>")
    cuerpo = (cabecera("Hospital Regional de Temuco · B2B", "Carrito (3)") + '<div class="pad"><div class="t" style="font-size:18px">Mi carrito</div><div class="fila"><div style="flex:1">'
              f'<table><tr><th>Producto</th><th>Cantidad</th><th>Precio unit.</th><th>Subtotal</th></tr>{filas}</table>'
              '<div class="rojo ins" style="margin-top:8px;font-size:12px">Mariscos congelados: solo hay 12 cajas disponibles. Ajuste la cantidad.</div></div>'
              '<div class="caja pad col" style="width:300px;gap:12px">'
              f'<div class="rel"><b>Dirección de entrega</b><br><span class="chip" style="display:inline-block;margin-top:4px">Manuel Montt 115, Temuco ▾</span>{N(3)}</div>'
              f'<div class="rel"><b>N° de orden de compra</b> <span class="m">(solo instituciones)</span><br><span class="busca" style="display:block;margin-top:4px">OC-2026-0457</span>{N(2)}</div>'
              f'<div class="rel" style="font-size:16px"><b>Total:</b> $979.650{N(4)}</div><span class="btn p" style="text-align:center">Confirmar pedido</span></div></div></div>')
    notas = ["Las cantidades se validan contra el stock al confirmar; si falta stock se avisa antes de crear la orden.",
             "El número de orden de compra (<b>orden.numero_oc</b>) aparece solo para el perfil B2B.",
             "Solo se ofrecen las direcciones del propio cliente (<b>direccion.cliente_id</b>).",
             "El total se calcula con las líneas del carrito; no se almacena."]
    return ventana("https://cofrial.example/carrito", cuerpo, notas, 560)


def w5():
    cuerpo = (cabecera("Hospital Regional de Temuco · B2B") + '<div class="pad" style="text-align:center"><div style="font-size:40px">✓</div>'
              f'<div style="font-size:22px;font-weight:800">Pedido recibido</div><div class="m">Orden N.° 1001 · estado: <span class="ins azul rel">Recibida{N(1)}</span></div>'
              '<div class="caja pad" style="width:560px;margin:16px auto;text-align:left"><table><tr><th>Producto</th><th>Cant.</th><th>Subtotal</th></tr>'
              '<tr><td>Lomo vetado de vacuno 5 kg</td><td>10</td><td>$389.900</td></tr><tr><td>Pechuga de pollo 10 kg</td><td>5</td><td>$149.950</td></tr>'
              '<tr><td><b>Total</b></td><td></td><td><b>$539.850</b></td></tr></table><div class="m" style="margin-top:8px">Entrega en Manuel Montt 115, Temuco · OC-2026-0457</div></div>'
              f'<div class="rel caja pad" style="width:560px;margin:0 auto;text-align:left">{N(2)}Su vendedora <b>María Paz Soto</b> ya ve este pedido y lo confirmará.</div>'
              '<div style="margin-top:16px"><span class="btn p">Seguir mi pedido</span> <span class="btn g">Descargar resumen</span></div></div>')
    notas = ["La orden se crea en estado <b>Recibida</b> y el stock ya está descontado (misma transacción).",
             "Para B2B se informa el vendedor asignado (<b>cliente.vendedor_id</b>): el pedido aparece en su CRM al instante."]
    return ventana("https://cofrial.example/pedido/1001/confirmacion", cuerpo, notas, 600)


def w6():
    cuerpo = (cabecera("Hospital Regional de Temuco · B2B") + '<div class="pad"><div class="t" style="font-size:18px">Pedido N.° 1001</div>'
              f'<div class="tl rel">{N(1)}<div class="tp ok"><i></i>Recibida</div><div class="tp ok"><i></i>Confirmada</div><div class="tp ok"><i></i>En preparación</div><div class="tp ya"><i></i><b>Despachada</b></div><div class="tp"><i></i>Entregada</div></div>'
              '<div class="fila"><div class="caja pad" style="flex:1"><b>Camión CAM-01</b> · salió 07:12<div class="mapa" style="margin:8px 0"><span class="cam">CAM-01</span></div><div class="m">Última posición hace 5 segundos</div></div>'
              f'<div class="caja pad rel col" style="width:330px">{N(2)}<b>Temperatura de la cámara</b><div style="font-size:30px;font-weight:800">3,4 °C</div><span class="ins verde">Dentro del rango (0 a 4 °C)</span>'
              '<div class="img" style="height:60px">gráfico de los últimos 60 minutos con la banda 0 a 4 °C</div></div></div>'
              f'<div class="rel rojo caja pad" style="margin-top:12px;background:#fbe9e6;border-color:#c0392b">{N(3)}<b>Aviso:</b> a las 08:40 se detectó una lectura sobre 4 °C durante unos minutos. Su vendedora fue notificada y estamos verificando la carga.</div>'
              f'<div class="rel" style="margin-top:12px;width:max-content">{N(4)}<span class="btn r">Reportar un problema</span></div></div>')
    notas = ["El estado sale de <b>estado_orden</b>; cada cambio queda con fecha y hora.",
             "Posición y temperatura salen de <b>telemetria</b> del camión del despacho (<b>orden.despacho_id → despacho.camion_id</b>).",
             "Si una lectura trae <b>alerta_ruptura_frio</b> durante el viaje de esta orden, el cliente lo ve y el vendedor lo recibe en el CRM.",
             "«Reportar un problema» crea un <b>requerimiento</b>; la IA lo clasifica y llega al CRM."]
    return ventana("https://cofrial.example/pedido/1001", cuerpo, notas, 640)


# ---------------------------------------------------------------------------------------------
# Wireframes del CRM
# ---------------------------------------------------------------------------------------------
def menu(activo):
    items = ["Panel", "Prospectos", "Clientes", "Pedidos web", "Requerimientos", "Reportes"]
    return '<div class="menu"><div style="font-weight:800;letter-spacing:1px;margin-bottom:8px">COFRIAL CRM</div>' + "".join(
        f'<div class="{"act" if i == activo else ""}">{i}</div>' for i in items) + '</div>'


def w7():
    def tj(emp, con, monto, dias, extra=""):
        return f'<div class="tj"><b>{emp}</b><br>{con}<br><span class="m">{monto} · {dias} días en la etapa</span>{extra}</div>'
    cols = [("Prospecto", 4, tj("Clínica Alemana Temuco", "Dra. Pérez", "$1.800.000", 2) + tj("Feria Costanera", "J. Soto", "$600.000", 5)),
            ("Contactado", 3, tj("Hotel Pucón Sur", "L. Reyes", "$900.000", 3)),
            ("Propuesta enviada", 2, tj("Supermercado El Sur", "C. Muñoz", "$2.500.000", 4, '<br><span class="ins amar">Sin respuesta hace 4 días</span>')),
            ("Negociación", 1, tj("Casino Industrial Norte", "P. Vega", "$3.200.000", 6)),
            ("Ganado", 7, ""), ("Perdido", 3, "")]
    col = "".join(f'<div class="kc"><h4><span>{n}</span><span class="ins azul">{c}</span></h4>{t}</div>' for n, c, t in cols)
    cuerpo = ('<div class="crm">' + menu("Prospectos") + '<div style="flex:1"><div class="cab" style="gap:10px"><b style="font-size:16px">Embudo comercial</b><span style="flex:1"></span>'
              f'<span class="chip rel">Vendedora: María Paz Soto ▾{N(3)}</span><span class="btn p">+ Nuevo prospecto</span></div>'
              f'<div class="fila rel" style="padding:12px 14px;gap:12px">{NL(2)}<div class="caja pad" style="flex:1"><span class="m">Prospectos activos</span><div style="font-size:22px;font-weight:800">10</div></div>'
              '<div class="caja pad" style="flex:1"><span class="m">Valor del embudo</span><div style="font-size:22px;font-weight:800">$9.000.000</div></div>'
              '<div class="caja pad" style="flex:1"><span class="m">Conversión del mes</span><div style="font-size:22px;font-weight:800">70 %</div></div></div>'
              f'<div class="kan rel">{NL(1)}{col}</div></div></div>')
    notas = ["Arrastrar una tarjeta cambia la <b>etapa</b>. Al mover a «Perdido» se exige el motivo; al mover a «Ganado» se crea el cliente.",
             "Los indicadores se calculan desde la base de datos (conversión = ganados sobre cerrados del mes).",
             "El vendedor ve solo su cartera; gerencia ve todas. Así la cartera pertenece a la empresa y no a un celular."]
    return ventana("https://cofrial.example/crm/prospectos", cuerpo, notas, 640)


def w8():
    cuerpo = ('<div class="crm">' + menu("Clientes") + '<div style="flex:1" class="pad"><div class="fila" style="justify-content:space-between"><div><div style="font-size:19px;font-weight:800">Hospital Regional de Temuco</div>'
              '<div class="m">RUT 61.973.200-4 · B2B · Vendedora: María Paz Soto</div></div><div class="fila"><span class="btn g">Registrar interacción</span><span class="btn p">Crear pedido a su nombre</span></div></div>'
              f'<div class="caja pad rel" style="margin:12px 0;background:#fbe9e6;border-color:#c0392b">{N(1)}<b>1 pedido afectado por ruptura de frío</b> · Orden 1001 · camión CAM-01 · 08:40. Llame al cliente antes de que reclame.</div>'
              '<div class="fila" style="gap:18px;border-bottom:1.5px solid #d3d8df;margin-bottom:8px"><b style="border-bottom:3px solid #4a6fa5;padding:4px">Pedidos</b><span class="m">Interacciones</span><span class="m">Requerimientos</span><span class="m">Datos</span></div>'
              f'<div class="rel">{N(2)}<table><tr><th>Orden</th><th>Fecha</th><th>Estado</th><th>Total</th><th>Frío</th></tr>'
              '<tr><td>1001</td><td>12-oct</td><td><span class="ins verde">Entregada</span></td><td>$539.850</td><td><span class="ins rojo">Alerta</span></td></tr>'
              '<tr><td>0987</td><td>05-oct</td><td><span class="ins verde">Entregada</span></td><td>$412.300</td><td><span class="ins verde">Sin alertas</span></td></tr>'
              '<tr><td>0954</td><td>28-sep</td><td><span class="ins verde">Entregada</span></td><td>$388.120</td><td><span class="ins verde">Sin alertas</span></td></tr></table></div>'
              f'<div class="m rel" style="margin-top:12px;width:max-content">{NL(3)}Última interacción: llamada · 10-oct · «Se confirma pedido semanal»</div></div></div>')
    notas = ["Las alertas de frío que afectan a pedidos del cliente aparecen en su ficha (consulta 4 de <b>consultas_bi.sql</b>): el vendedor actúa antes del reclamo.",
             "El historial de pedidos viene de <b>v_orden</b> y el estado de <b>estado_orden</b>: el vendedor sigue los pedidos web sin pedirlos por WhatsApp.",
             "Cada llamada, correo o reunión se registra como <b>interaccion</b>: el historial queda en la empresa."]
    return ventana("https://cofrial.example/crm/clientes/15", cuerpo, notas, 640)


def w9():
    filas = ("<tr><td>Llegó tibia la carga</td><td>Hospital Regional</td><td><span class='ins rojo'>Calidad o frío</span> 91 %</td><td><span class='ins azul'>Clasificado</span></td></tr>"
             "<tr><td>Cotización de 200 kg de pollo</td><td>Casino Norte</td><td><span class='ins azul'>Cotización</span> 87 %</td><td><span class='ins azul'>Clasificado</span></td></tr>"
             f"<tr><td>¿Hacen despachos a Villarrica?</td><td>Anónimo</td><td><span class='ins amar'>Sin clasificar</span> {N(3)}</td><td><span class='ins amar'>Pendiente</span></td></tr>"
             "<tr><td>Factura duplicada</td><td>Ana Pérez</td><td><span class='ins azul'>Reclamo</span> 78 %</td><td><span class='ins verde'>Resuelto</span></td></tr>")
    cuerpo = ('<div class="crm">' + menu("Requerimientos") + '<div style="flex:1" class="pad"><div class="fila" style="justify-content:space-between;margin-bottom:10px"><b style="font-size:17px">Bandeja de requerimientos</b>'
              '<div class="fila"><span class="chip">Categoría ▾</span><span class="chip">Estado ▾</span></div></div><div class="fila"><div style="flex:1.4" class="rel">'
              f'{N(1)}<table><tr><th>Asunto</th><th>Cliente</th><th>Categoría (IA)</th><th>Estado</th></tr>{filas}</table></div>'
              f'<div class="caja pad col rel" style="flex:1">{N(2)}<b>Llegó tibia la carga</b><div class="m">Hospital Regional · orden 1001 · hace 12 min</div>'
              '<div class="caja pad gris">El pedido llegó con la cadena de frío cortada. Necesitamos reposición urgente.</div>'
              '<div><b>Categoría sugerida:</b> <span class="ins rojo">Calidad o frío</span> (confianza 91 %)</div>'
              '<div class="fila"><span class="btn g">Reclasificar</span><span class="btn g">Asignar</span><span class="btn p">Marcar resuelto</span></div></div></div></div></div>')
    notas = ["Cada requerimiento muestra la categoría que asignó la IA y su confianza (<b>requerimiento.confianza_ia</b>).",
             "El vendedor puede corregir la categoría: la decisión final es de una persona.",
             "Si la API de IA no responde, el requerimiento queda <b>sin_clasificar</b> y se revisa a mano: el servicio nunca se detiene."]
    return ventana("https://cofrial.example/crm/requerimientos", cuerpo, notas, 640)


# ---------------------------------------------------------------------------------------------
# User journeys
# ---------------------------------------------------------------------------------------------
def journey(titulo, sub, etapas, filas, emo_asis, emo_tobe, indicadores):
    celdas = ['<div class="h"></div>'] + [f'<div class="h">{i + 1}. {e}</div>' for i, e in enumerate(etapas)]
    for nombre, valores, clase in filas:
        celdas.append(f'<div class="r">{nombre}</div>')
        celdas += [f'<div class="{clase}">{v}</div>' for v in valores]

    def pts(v):
        # ancho de cada columna: (1900-48-150-2)/6 aprox 283
        w = (1900 - 48 - 150) / 6
        return " ".join(f"{(i + 0.5) * w:.0f},{110 - (x - 1) * 24:.0f}" for i, x in enumerate(v))
    w = (1900 - 48 - 150) / 6
    circ = lambda v, color: "".join(f'<circle cx="{(i + 0.5) * w:.0f}" cy="{110 - (x - 1) * 24:.0f}" r="6" fill="{color}"/>' for i, x in enumerate(v))
    grafico = (f'<div class="r emol">Emoción del cliente<br><span style="font-weight:400;font-size:11px">arriba: satisfecho<br>abajo: frustrado</span></div>'
               f'<div class="emo"><svg width="{w * 6:.0f}" height="130"><line x1="0" y1="62" x2="{w * 6:.0f}" y2="62" stroke="#c9ced6" stroke-dasharray="4 4"/>'
               f'<polyline points="{pts(emo_asis)}" fill="none" stroke="#c0392b" stroke-width="3" stroke-dasharray="7 5"/>{circ(emo_asis, "#c0392b")}'
               f'<polyline points="{pts(emo_tobe)}" fill="none" stroke="#2e8b57" stroke-width="3"/>{circ(emo_tobe, "#2e8b57")}</svg></div>')
    celdas.append(grafico)
    celdas.append('<div class="r">Indicador</div>' + "".join(f"<div>{v}</div>" for v in indicadores))
    cuerpo = (f'<div class="jm"><h2>{titulo}</h2><div class="sub">{sub}</div><div class="jg">{"".join(celdas)}</div>'
              '<div class="leyj"><span><b style="color:#c0392b">- - -</b> Hoy (AS-IS)</span><span><b style="color:#2e8b57">━━━</b> Con la plataforma (TO-BE)</span></div></div>')
    return cuerpo


def j_b2b():
    return journey(
        "User journey B2B: Marcela Rojas, encargada de abastecimiento del Hospital Regional (persona ficticia)",
        "Objetivo: abastecer cada semana carnes refrigeradas, con trazabilidad de la temperatura y número de orden de compra. Tiene poco tiempo y responde ante auditorías sanitarias.",
        ["Ingresar", "Elegir productos", "Armar el pedido", "Confirmar", "Seguir el despacho", "Recibir y postventa"],
        [("Acción del cliente", ["Entra con la cuenta de su institución", "Filtra por tipo de frío y repite su último pedido", "Define cantidades, dirección y N.° de orden de compra", "Confirma y recibe el número de orden", "Consulta estado, posición y temperatura del camión", "Recibe, confirma y reporta si hay un problema"], ""),
         ("Pantalla", ["Inicio de sesión (W1)", "Catálogo y detalle (W2, W3)", "Carrito (W4)", "Confirmación (W5)", "Seguimiento (W6)", "Seguimiento y requerimiento (W6)"], ""),
         ("Sistema: dato y regla", ["<b>cliente → tipo_cliente → lista de precios institucional</b>", "<b>precio_producto</b> por lista; <b>stock_disponible</b> en línea", "<b>carrito_item</b>; <b>direccion</b> del cliente; <b>numero_oc</b>", "<b>orden</b> y <b>orden_item</b> con precio vigente; stock descontado en una transacción", "<b>orden → despacho → camion → telemetria</b>; <b>alerta_ruptura_frio</b>", "<b>requerimiento</b> clasificado por IA; vendedor notificado"], ""),
         ("Hoy (AS-IS)", ["Llama al vendedor; depende de que conteste", "Pide por correo sin saber si hay stock ni cuál es el precio vigente", "Dicta cantidades y el vendedor las anota a mano", "Espera que el vendedor confirme por WhatsApp", "Llama para preguntar dónde va; nadie sabe la temperatura", "Rechaza la carga y reclama por teléfono; no queda registro"], "hoy"),
         ("Con la plataforma", ["Entra a cualquier hora con su cuenta y ve su lista de precios", "Ve precio y stock reales y repite el pedido anterior en un clic", "Revisa el total y los avisos de stock antes de confirmar", "Recibe número y resumen al instante; el vendedor lo ve en el CRM", "Ve el estado en línea y se le avisa si hay una alerta de frío", "Reporta en el portal; la IA lo clasifica y el vendedor responde"], "tobe")],
        [2, 2, 2, 1.5, 1, 1], [4, 5, 4, 5, 4, 4],
        ["Cuentas activas", "Pedidos repetidos con un clic", "Pedidos sin errores de transcripción", "Pedidos fuera del sistema", "Consultas de estado por teléfono", "Tiempo de primera respuesta"])


def j_b2c():
    return journey(
        "User journey B2C: Ana Pérez, compra para su familia de forma ocasional (persona ficticia)",
        "Objetivo: comprar carnes de calidad sin ir a una tienda ni llamar por teléfono, y saber cuándo llega su pedido. Compra puntual, pago inmediato, sin vendedor asignado.",
        ["Llegar", "Elegir productos", "Carrito y datos", "Pagar y confirmar", "Seguir el pedido", "Postventa"],
        [("Acción del cliente", ["Entra al sitio y elige «Cliente particular»", "Mira el catálogo y los precios públicos", "Agrega productos y crea su cuenta con RUT y correo", "Elige la dirección y paga (pago simulado en el prototipo)", "Revisa el estado del despacho", "Reporta un problema o repite la compra"], ""),
         ("Pantalla", ["Inicio (W1)", "Catálogo y detalle (W2, W3)", "Carrito (W4)", "Confirmación (W5)", "Seguimiento (W6)", "Seguimiento y requerimiento"], ""),
         ("Sistema: dato y regla", ["<b>tipo_cliente B2C → lista pública</b>", "<b>precio_producto</b> de la lista pública; stock en línea", "<b>usuario</b>, <b>cliente</b> y <b>direccion</b> se crean; un solo <b>carrito</b> abierto", "<b>orden</b> en estado Recibida; stock descontado", "<b>estado_orden</b> y <b>telemetria</b> del despacho", "<b>requerimiento</b> clasificado por IA"], ""),
         ("Hoy (AS-IS)", ["No existe canal: compra en tienda o llama", "No conoce precios ni disponibilidad", "Debe dictar sus datos por teléfono", "Coordina el pago y la entrega a mano", "No sabe cuándo llega", "Reclama por teléfono sin respuesta clara"], "hoy"),
         ("Con la plataforma", ["Ve el catálogo sin llamar a nadie", "Compara precios y stock reales", "Crea la cuenta una sola vez, en pocos pasos", "Recibe número de orden y resumen al instante", "Ve el estado y la hora estimada en línea", "Reporta en el portal y recibe una respuesta registrada"], "tobe")],
        [2, 2, 2, 2, 1.5, 2], [4, 4, 4, 5, 4, 4],
        ["Visitas que llegan a la ficha de producto", "Productos agregados al carrito", "Carritos que terminan en una orden", "Órdenes completadas", "Consultas de estado por teléfono", "Requerimientos respondidos a tiempo"])


# ---------------------------------------------------------------------------------------------
# Mermaid: arquitectura del CRM, estados y casos de uso
# ---------------------------------------------------------------------------------------------
ARQ_CRM = """flowchart LR
  classDef usr fill:#eef1f5,stroke:#5a6c86,color:#222
  classDef mod fill:#dbe6f6,stroke:#4a6fa5,color:#222
  classDef reg fill:#fff2cc,stroke:#b8860b,color:#222
  classDef dat fill:#e6f2e6,stroke:#2e8b57,color:#222
  classDef ext fill:#f3e5f5,stroke:#8e44ad,color:#222

  subgraph U["Usuarios"]
    direction TB
    V["Vendedor<br/>clientes, prospectos,<br/>pedidos y requerimientos"]:::usr
    G["Gerencia<br/>reportes y dashboard"]:::usr
    D["Despachador<br/>alertas de frío"]:::usr
    C["Cliente B2B y B2C<br/>portal de compras"]:::usr
  end
  subgraph M["Módulos del CRM"]
    direction TB
    M1["Clientes<br/>ficha, historial, interacciones"]:::mod
    M2["Prospectos<br/>embudo por etapas"]:::mod
    M3["Pedidos web<br/>seguimiento y estado"]:::mod
    M4["Requerimientos<br/>bandeja clasificada por IA"]:::mod
    M5["Alertas de frío<br/>pedidos afectados"]:::mod
    M6["Reportes<br/>conversión, embudo, ventas"]:::mod
  end
  subgraph R["Reglas de negocio"]
    direction TB
    R1["Cartera por vendedor,<br/>permisos por rol"]:::reg
    R2["Motivo obligatorio<br/>al perder"]:::reg
    R3["Ganar crea cliente y<br/>asigna lista de precios"]:::reg
    R4["Alerta de frío avisa al<br/>vendedor del cliente"]:::reg
  end
  DB[("Base de datos central<br/>RDS PostgreSQL")]:::dat
  subgraph X["Fuentes e integraciones"]
    direction TB
    EC["E-commerce"]:::ext
    IOT["Simulador IoT"]:::ext
    IA["API de IA"]:::ext
    BI["Grafana BI"]:::ext
  end

  U --> M
  R -.->|"se aplican en"| M
  M <-->|"lee y escribe"| DB
  EC -->|"órdenes y requerimientos"| DB
  IOT -->|"telemetría"| DB
  M4 <-->|"texto y categoría"| IA
  DB -->|"consultas en vivo"| BI
"""

PIPELINE = """flowchart LR
  classDef etapa fill:#dbe6f6,stroke:#4a6fa5,color:#222
  classDef gana fill:#c9e4cf,stroke:#2e8b57,color:#222,font-weight:bold
  classDef pierde fill:#f9dcd8,stroke:#c0392b,color:#222,font-weight:bold
  classDef ini fill:#eef1f5,stroke:#5a6c86,color:#222

  IN(["Ingreso manual<br/>o por el portal"]):::ini
  subgraph ABIERTAS["Etapas abiertas"]
    direction LR
    P1["1. Prospecto"]:::etapa
    P2["2. Contactado"]:::etapa
    P3["3. Propuesta<br/>enviada"]:::etapa
    P4["4. Negociación"]:::etapa
  end
  G["5. Cliente ganado"]:::gana
  X["6. Perdido"]:::pierde
  CL(["Cliente creado<br/>con su lista de precios"]):::ini

  IN --> P1
  P1 -->|"registrar la primera<br/>interacción"| P2
  P2 -->|"registrar la propuesta"| P3
  P3 -->|"el cliente responde<br/>con condiciones"| P4
  P3 -->|"pide aclaraciones"| P2
  P3 -->|"acepta sin negociar"| G
  P4 -->|"acepta"| G
  ABIERTAS -.->|"motivo obligatorio"| X
  G -->|"se crea el cliente<br/>y se asigna la lista"| CL
"""

ESTADOS_ORDEN = """stateDiagram-v2
  direction LR
  [*] --> Recibida: el cliente confirma, stock descontado
  Recibida --> Confirmada: el vendedor o bodega valida
  Confirmada --> EnPreparacion: bodega prepara
  EnPreparacion --> Despachada: se asigna camión y sale
  Despachada --> Entregada: el cliente recibe
  Recibida --> Cancelada: repone stock
  Confirmada --> Cancelada: repone stock
  EnPreparacion --> Cancelada: repone stock
  Entregada --> [*]
  Cancelada --> [*]
  state "En preparación" as EnPreparacion
"""

CASOS_USO = """flowchart LR
  classDef act fill:#eef1f5,stroke:#5a6c86,color:#222,font-weight:bold
  classDef sis fill:#fff2cc,stroke:#b8860b,color:#222,font-weight:bold
  classDef cu fill:#dbe6f6,stroke:#4a6fa5,color:#222
  classDef crit fill:#c9e4cf,stroke:#2e8b57,color:#222,font-weight:bold

  CL(["Cliente B2B o B2C"]):::act
  VE(["Vendedor"]):::act
  DE(["Despachador"]):::act
  GE(["Gerencia"]):::act
  IOT(["Simulador IoT"]):::sis
  IA(["Servicio de IA"]):::sis

  subgraph EC["E-commerce"]
    direction TB
    CU01(("CU-01<br/>Perfil e inicio<br/>de sesión")):::cu
    CU02(("CU-02<br/>Consultar<br/>catálogo")):::cu
    CU03(("CU-03<br/>Gestionar<br/>carrito")):::cu
    CU04(("CU-04<br/>Generar<br/>una orden")):::crit
    CU05(("CU-05<br/>Seguir<br/>el pedido")):::cu
  end
  subgraph CRM["CRM"]
    direction TB
    CU06(("CU-06<br/>Gestionar<br/>clientes")):::cu
    CU07(("CU-07<br/>Prospectos y<br/>pipeline")):::cu
    CU08(("CU-08<br/>Seguir pedidos<br/>web")):::cu
    CU09(("CU-09<br/>Requerimiento<br/>con IA")):::crit
  end
  subgraph LOG["IoT y BI"]
    direction TB
    CU10(("CU-10<br/>Enviar<br/>telemetría")):::cu
    CU11(("CU-11<br/>Detectar ruptura<br/>de frío")):::crit
    CU12(("CU-12<br/>Monitorear<br/>flota")):::cu
    CU13(("CU-13<br/>Dashboard ventas<br/>y frío")):::cu
  end

  CL --- CU01 & CU02 & CU03 & CU04 & CU05
  CL --- CU09
  VE --- CU06 & CU07 & CU08
  IA --- CU09
  IOT --- CU10
  DE --- CU12
  GE --- CU13
  CU04 -.->|"incluye"| CU03
  CU03 -.->|"incluye"| CU02
  CU10 -.->|"incluye"| CU11
"""


if __name__ == "__main__":
    print("Wireframes:")
    alturas = {1: 660, 2: 840, 3: 640, 4: 600, 5: 640, 6: 680, 7: 680, 8: 680, 9: 680}
    for i, f in enumerate([w1, w2, w3, w4, w5, w6, w7, w8, w9], 1):
        render_html(f(), IMG / f"wf-w{i}.png", 1400, alturas[i])
    print("Journeys:")
    render_html(j_b2b(), IMG / "journey-b2b.png", 1900, 600, 1.2)
    render_html(j_b2c(), IMG / "journey-b2c.png", 1900, 600, 1.2)
    print("Mermaid:")
    render_mermaid(ARQ_CRM, IMG / "crm-arquitectura.png", elk=True)
    render_mermaid(PIPELINE, IMG / "crm-pipeline.png")
    render_mermaid(ESTADOS_ORDEN, IMG / "estados-orden.png")
    render_mermaid(CASOS_USO, IMG / "casos-de-uso.png", elk=True)
