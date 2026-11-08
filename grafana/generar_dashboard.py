"""Genera grafana/dashboards/cofrial.json. Editar este archivo y volver a ejecutarlo: python3 grafana/generar_dashboard.py"""
import json
import pathlib

DS = {"type": "postgres", "uid": "cofrial-pg"}
SIN_CANCELADAS = "e.nombre <> 'Cancelada'"
VENTAS = f"""FROM v_orden o JOIN v_orden_total t USING (orden_id)
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id WHERE {SIN_CANCELADAS}"""
# Solo cuenta la cámara en la que viaja la orden. RN-13, igual que crm.servicios.fin_de_exposicion: una orden entregada deja de estar expuesta al recibirse; las demás, al volver el camión.
A_BORDO = """m.camion_id = d.camion_id AND m.camara = x.camara AND m.alerta_ruptura_frio AND m.registrado_en >= d.salida_en
  AND m.registrado_en <= COALESCE(CASE WHEN e.nombre = 'Entregada' THEN COALESCE(x.entrega_resuelta_en, d.llegada_en) ELSE d.regreso_en END, now())"""
AFECTADAS = f"""FROM v_orden o JOIN v_orden_total t USING (orden_id)
JOIN orden x USING (orden_id)
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id
WHERE e.nombre <> 'Cancelada' AND d.salida_en IS NOT NULL AND EXISTS (
  SELECT 1 FROM telemetria m WHERE {A_BORDO})"""

_id = 0


def pesos(expresion):
    """Monto como texto: $3.467.880. Grafana no tiene esa unidad: prefix:$ no separa miles, currency:$ abrevia y locale depende del navegador de quien mira."""
    return f"'$' || replace(to_char({expresion}, 'FM999,999,999,999,990'), ',', '.')"


def consulta(sql, formato="table", ref="A"):
    return {"datasource": DS, "refId": ref, "format": formato, "rawQuery": True, "editorMode": "code", "rawSql": sql}


def panel(titulo, tipo, x, y, w, h, consultas, opciones=None, defaults=None, overrides=None, descripcion=""):
    global _id
    _id += 1
    p = {"id": _id, "title": titulo, "type": tipo, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": consultas, "description": descripcion,
         "fieldConfig": {"defaults": defaults or {}, "overrides": overrides or []}, "options": opciones or {}}
    return p


def stat(titulo, sql, x, y, w=4, rojo_desde=None, descripcion=""):
    d = {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}}
    if rojo_desde is not None:
        d["thresholds"]["steps"].append({"color": "red", "value": rojo_desde})
    return panel(titulo, "stat", x, y, w, 4, [consulta(sql)], {"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "value", "graphMode": "none"}, d, descripcion=descripcion)


def stat_monto(titulo, sql, x, y, w=4, rojo_si_hay_monto=False, descripcion=""):
    """Tarjeta cuyo valor es texto (ver pesos()). Los umbrales no leen texto: el color base es el del monto y una regla deja verde el $0."""
    p = stat(titulo, sql, x, y, w, descripcion=descripcion)
    p["options"]["reduceOptions"]["fields"] = "/.*/"
    if rojo_si_hay_monto:
        p["fieldConfig"]["defaults"]["thresholds"]["steps"][0]["color"] = "red"
        p["fieldConfig"]["defaults"]["mappings"] = [{"type": "regex", "options": {"pattern": "^\\$0$", "result": {"color": "green", "index": 0}}}]
    return p


def tiempo_simulacion(x, y, w):
    """Franja que avisa cuando el tiempo de la demostración está acelerado: sin ella, un camión que cruza la región en minutos parecería un error."""
    p = panel("Tiempo de la simulación", "stat", x, y, w, 2,
              [consulta("SELECT coalesce((SELECT multiplicador_tiempo FROM ajuste_simulador WHERE ajuste_id = 1), 1) AS multiplicador")],
              {"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "value", "graphMode": "none", "textMode": "value"},
              {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 2}]},
               "mappings": [{"type": "value", "options": {"1": {"text": "Tiempo real (1×)", "index": 0}, "5": {"text": "Acelerado 5×", "index": 1},
                                                          "20": {"text": "Acelerado 20×", "index": 2}, "60": {"text": "Acelerado 60×", "index": 3}}}]},
              descripcion="Cuántas veces más rápido avanzan los camiones (se elige en /demo/). Las lecturas siguen entrando cada 5 s.")
    return p


def seccion(titulo, y):
    global _id
    _id += 1
    return {"id": _id, "type": "row", "title": titulo, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


paneles = [
    seccion("1 · Resumen del período: cuánto vendimos y cuánto está en riesgo (el selector de tiempo de arriba a la derecha define el período)", 0),
    stat_monto("Ventas", f"SELECT {pesos('coalesce(sum(t.total_clp),0)')} AS ventas {VENTAS} AND $__timeFilter(o.creada_en)", 0, 1,
         descripcion="Suma de todas las órdenes creadas en el período, B2B y B2C, sin las canceladas."),
    stat("Pedidos", f"SELECT count(*) AS pedidos {VENTAS} AND $__timeFilter(o.creada_en)", 4, 1,
         descripcion="Cantidad de órdenes creadas en el período, sin las canceladas."),
    stat("Alertas (período)", "SELECT count(*) AS alertas FROM telemetria WHERE alerta_ruptura_frio AND $__timeFilter(registrado_en)", 8, 1, rojo_desde=1,
         descripcion="Cuántas veces un camión reportó la cámara fuera de su rango de temperatura durante el período. Cada camión reporta cada 5 s, así que una sola falla suma varias lecturas."),
    stat("En alerta AHORA", "SELECT count(DISTINCT camion_id) AS camiones FROM telemetria WHERE alerta_ruptura_frio AND registrado_en >= now() - interval '30 seconds'", 12, 1, rojo_desde=1,
         descripcion="Camiones con alguna lectura fuera de rango en los últimos 30 segundos (así no parpadea cuando entra una lectura normal entre dos de alerta)."),
    stat("Pedidos afectados", f"SELECT count(*) AS pedidos {AFECTADAS}", 16, 1, rojo_desde=1,
         descripcion="Órdenes despachadas cuyo camión reportó una lectura fuera de rango durante el viaje."),
    stat_monto("Ventas en riesgo", f"SELECT {pesos('coalesce(sum(t.total_clp),0)')} AS en_riesgo {AFECTADAS}", 20, 1, rojo_si_hay_monto=True,
         descripcion="Monto de los pedidos afectados: lo que la ruptura de frío pone en juego."),
    seccion("2 · Cruce de ventas por canal con las alertas de ruptura de frío", 5),
    panel("Ventas vs alertas de frío en el tiempo", "timeseries", 0, 6, 16, 9, [
        consulta(f"SELECT $__timeGroupAlias(o.creada_en,'10m'), o.canal AS metric, sum(t.total_clp) AS value {VENTAS} AND $__timeFilter(o.creada_en) GROUP BY 1,2 ORDER BY 1", "time_series", "A"),
        consulta("SELECT $__timeGroupAlias(registrado_en,'10m'), 'Alertas de frío' AS metric, count(*) AS value FROM telemetria WHERE alerta_ruptura_frio AND $__timeFilter(registrado_en) GROUP BY 1 ORDER BY 1", "time_series", "B")],
        {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
        {"custom": {"drawStyle": "bars", "fillOpacity": 60, "lineWidth": 1}, "unit": "currency:$"},
        [{"matcher": {"id": "byName", "options": "Alertas de frío"},
          "properties": [{"id": "unit", "value": "short"}, {"id": "custom.drawStyle", "value": "line"}, {"id": "custom.axisPlacement", "value": "right"}, {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}},
                         {"id": "custom.lineWidth", "value": 3}, {"id": "custom.fillOpacity", "value": 0}, {"id": "custom.spanNulls", "value": True}]}],
        "Barras = ventas en pesos por canal (eje izquierdo). Línea roja = cantidad de lecturas de alerta de frío (eje derecho). Sirve para ver si los problemas de frío ocurren cuando más se vende."),
    panel("Ventas por canal", "piechart", 16, 6, 8, 9, [consulta(f"SELECT o.canal || ': ' || {pesos('sum(t.total_clp)')} AS canal, sum(t.total_clp) AS ventas {VENTAS} AND $__timeFilter(o.creada_en) GROUP BY o.canal ORDER BY o.canal")],
          {"legend": {"displayMode": "table", "placement": "bottom", "values": ["percent"]}, "tooltip": {"mode": "none"}, "pieType": "donut", "reduceOptions": {"calcs": ["lastNotNull"], "values": True, "fields": "/^ventas$/"}},
          descripcion="Cuánto del total vendido vino de cada canal: B2B (instituciones con lista de precios) y B2C (público general)."),
    seccion("3 · Flota en vivo: 50 camiones en toda La Araucanía, con base en Temuco (se actualiza cada 5 s)", 15),
    tiempo_simulacion(0, 16, 14),
    panel("Posición actual de la flota", "geomap", 0, 18, 14, 13, [consulta("SELECT DISTINCT ON (camion_id) camion_id, lat, \"long\", temp_camara, CASE WHEN alerta_ruptura_frio THEN 1 ELSE 0 END AS estado FROM telemetria WHERE registrado_en >= now() - interval '2 minutes' ORDER BY camion_id, registrado_en DESC, alerta_ruptura_frio DESC")],
          {"view": {"id": "coords", "lat": -38.58, "lon": -72.55, "zoom": 7.6}, "controls": {"showZoom": True, "mouseWheelZoom": True},
           "basemap": {"type": "osm-standard", "name": "Mapa"},
           "layers": [{"type": "markers", "name": "Camiones", "config": {"showLegend": False, "style": {"size": {"fixed": 11, "min": 2, "max": 15}, "opacity": 0.95, "color": {"field": "estado", "fixed": "dark-green"},
                                                                                                  "symbol": {"mode": "fixed", "fixed": "img/icons/marker/circle.svg"}, "text": {"mode": "field", "field": "camion_id", "fixed": ""}, "textConfig": {"fontSize": 10, "offsetY": -12}}},
                       "location": {"mode": "coords", "latitude": "lat", "longitude": "long"}, "tooltip": True}]},
          {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]},
           "mappings": [{"type": "value", "options": {"0": {"text": "Normal", "color": "green", "index": 0}, "1": {"text": "Ruptura de frío", "color": "red", "index": 1}}}]},
          descripcion="Última posición de cada camión que reportó en los últimos 2 minutos. Verde = temperatura normal, rojo = ruptura de frío. Los camiones cercanos al centro hacen reparto urbano en Temuco; los lejanos van o vuelven de ciudades de La Araucanía. Pasa el mouse sobre un camión para ver su temperatura."),
    panel("Temperatura de cámara (camiones elegidos arriba)", "timeseries", 14, 16, 10, 7, [consulta("SELECT registrado_en AS time, CASE WHEN camara = 2 THEN camion_id || ' cámara 2' ELSE camion_id END AS metric, temp_camara AS value FROM telemetria WHERE $__timeFilter(registrado_en) AND camion_id IN ($camion) ORDER BY 1", "time_series")],
          {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}, {"unit": "celsius", "custom": {"lineWidth": 2, "fillOpacity": 0}},
          descripcion="Una línea por camión elegido en el selector «Camión» de la parte superior (por defecto CAM-01 a CAM-03). Una subida brusca fuera del rango del camión es una ruptura de frío."),
    panel("Camiones con más alertas de frío (período)", "bargauge", 14, 23, 10, 8, [consulta("SELECT camion_id AS camion, count(*) AS alertas FROM telemetria WHERE alerta_ruptura_frio AND $__timeFilter(registrado_en) GROUP BY 1 ORDER BY 2 DESC LIMIT 10")],
          {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True, "reduceOptions": {"calcs": ["lastNotNull"], "values": True, "fields": "/^alertas$/"}, "namePlacement": "left"},
          {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "orange", "value": None}, {"color": "red", "value": 10}]}, "min": 0, "noValue": "Ningún camión con alertas en el período"},
          [], "Los 10 camiones con más lecturas fuera de rango. Con una flota de 50 sirve para saber a cuáles revisar primero."),
    seccion("4 · Detalle: qué pedidos se vieron afectados por una ruptura de frío (para llamar al cliente)", 31),
    panel("Pedidos afectados por ruptura de frío", "table", 0, 32, 24, 7, [consulta(f"""SELECT o.orden_id AS "Orden", c.nombre AS "Cliente", o.canal AS "Canal", d.camion_id AS "Camión", count(m.*) AS "Lecturas con alerta", {pesos('t.total_clp')} AS "Monto"
FROM v_orden o JOIN v_orden_total t USING (orden_id) JOIN orden x USING (orden_id) JOIN cliente c ON c.cliente_id = o.cliente_id
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id
JOIN telemetria m ON {A_BORDO}
WHERE d.salida_en IS NOT NULL AND {SIN_CANCELADAS} GROUP BY 1,2,3,4,6 ORDER BY 5 DESC""")],
          {"showHeader": True}, {"custom": {"align": "auto"}, "noValue": "Sin pedidos afectados: ninguna ruptura de frío durante un viaje con pedidos"},
          [{"matcher": {"id": "byName", "options": "Monto"}, "properties": [{"id": "custom.align", "value": "right"}]},
           {"matcher": {"id": "byName", "options": "Lecturas con alerta"}, "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background"}},
                                                                                     {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "orange", "value": None}, {"color": "red", "value": 10}]}}]}],
          "Órdenes despachadas cuyo camión reportó temperatura fuera de rango mientras iba en ruta. Más lecturas con alerta = más tiempo expuesto al calor."),
]

dashboard = {
    "uid": "cofrial-torre", "title": "Cofrial: ventas y cadena de frío", "tags": ["cofrial", "bi"], "timezone": "browser",
    "schemaVersion": 39, "version": 3, "refresh": "5s", "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m"]}, "panels": paneles, "annotations": {"list": []},
    "templating": {"list": [{"name": "camion", "label": "Camión", "type": "query", "datasource": DS, "query": "SELECT camion_id FROM camion ORDER BY 1", "refresh": 1, "multi": True, "includeAll": False,
                             "current": {"selected": True, "text": ["CAM-01", "CAM-02", "CAM-03"], "value": ["CAM-01", "CAM-02", "CAM-03"]}, "sort": 1}]},
    "description": "Tablero en vivo: ventas por canal cruzadas con las alertas de ruptura de frío de la flota."}

destino = pathlib.Path(__file__).parent / "dashboards" / "cofrial.json"
destino.parent.mkdir(exist_ok=True)
destino.write_text(json.dumps(dashboard, ensure_ascii=False, indent=1), encoding="utf-8")
print("Escrito", destino)
