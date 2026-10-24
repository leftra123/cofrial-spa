"""Genera grafana/dashboards/cofrial.json. Editar este archivo y volver a ejecutarlo: python3 grafana/generar_dashboard.py"""
import json
import pathlib

DS = {"type": "postgres", "uid": "cofrial-pg"}
SIN_CANCELADAS = "e.nombre <> 'Cancelada'"
VENTAS = f"""FROM v_orden o JOIN v_orden_total t USING (orden_id)
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id WHERE {SIN_CANCELADAS}"""
AFECTADAS = """FROM v_orden o JOIN v_orden_total t USING (orden_id)
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id
WHERE e.nombre <> 'Cancelada' AND d.salida_en IS NOT NULL AND EXISTS (
  SELECT 1 FROM telemetria m WHERE m.camion_id = d.camion_id AND m.alerta_ruptura_frio
  AND m.registrado_en >= d.salida_en AND m.registrado_en <= COALESCE(d.llegada_en, now()))"""

_id = 0


def consulta(sql, formato="table", ref="A"):
    return {"datasource": DS, "refId": ref, "format": formato, "rawQuery": True, "editorMode": "code", "rawSql": sql}


def panel(titulo, tipo, x, y, w, h, consultas, opciones=None, defaults=None, overrides=None, descripcion=""):
    global _id
    _id += 1
    p = {"id": _id, "title": titulo, "type": tipo, "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": consultas, "description": descripcion,
         "fieldConfig": {"defaults": defaults or {}, "overrides": overrides or []}, "options": opciones or {}}
    return p


def stat(titulo, sql, x, y, w=4, unidad=None, rojo_desde=None, descripcion=""):
    d = {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}}
    if unidad:
        d["unit"] = unidad
    if rojo_desde is not None:
        d["thresholds"]["steps"].append({"color": "red", "value": rojo_desde})
    return panel(titulo, "stat", x, y, w, 4, [consulta(sql)], {"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "value", "graphMode": "none"}, d, descripcion=descripcion)


paneles = [
    stat("Ventas del período (CLP)", f"SELECT coalesce(sum(t.total_clp),0) AS ventas {VENTAS} AND $__timeFilter(o.creada_en)", 0, 0, unidad="prefix:$"),
    stat("Pedidos del período", f"SELECT count(*) AS pedidos {VENTAS} AND $__timeFilter(o.creada_en)", 4, 0),
    stat("Lecturas con alerta de frío", "SELECT count(*) AS alertas FROM telemetria WHERE alerta_ruptura_frio AND $__timeFilter(registrado_en)", 8, 0, rojo_desde=1),
    stat("Camiones en alerta ahora", "SELECT count(DISTINCT camion_id) AS camiones FROM telemetria WHERE alerta_ruptura_frio AND registrado_en >= now() - interval '30 seconds'", 12, 0, rojo_desde=1,
         descripcion="Camiones con alguna lectura fuera de rango en los últimos 30 segundos (así no parpadea cuando entra una lectura normal entre dos de alerta)."),
    stat("Pedidos afectados por ruptura de frío", f"SELECT count(*) AS pedidos {AFECTADAS}", 16, 0, rojo_desde=1,
         descripcion="Órdenes despachadas cuyo camión reportó una lectura fuera de rango durante el viaje."),
    stat("Ventas en riesgo (CLP)", f"SELECT coalesce(sum(t.total_clp),0) AS en_riesgo {AFECTADAS}", 20, 0, unidad="prefix:$", rojo_desde=1,
         descripcion="Monto de los pedidos afectados: lo que la ruptura de frío pone en juego."),
    panel("Ventas vs alertas de frío en el tiempo", "timeseries", 0, 4, 16, 9, [
        consulta(f"SELECT $__timeGroupAlias(o.creada_en,'10m'), o.canal AS metric, sum(t.total_clp) AS value {VENTAS} AND $__timeFilter(o.creada_en) GROUP BY 1,2 ORDER BY 1", "time_series", "A"),
        consulta("SELECT $__timeGroupAlias(registrado_en,'10m'), 'Alertas de frío' AS metric, count(*) AS value FROM telemetria WHERE alerta_ruptura_frio AND $__timeFilter(registrado_en) GROUP BY 1 ORDER BY 1", "time_series", "B")],
        {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
        {"custom": {"drawStyle": "bars", "fillOpacity": 60, "lineWidth": 1}, "unit": "short"},
        [{"matcher": {"id": "byName", "options": "Alertas de frío"},
          "properties": [{"id": "custom.drawStyle", "value": "line"}, {"id": "custom.axisPlacement", "value": "right"}, {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}},
                         {"id": "custom.lineWidth", "value": 3}, {"id": "custom.fillOpacity", "value": 0}, {"id": "custom.spanNulls", "value": True}]}],
        "Cruce pedido por la pauta: las ventas de cada canal junto a las alertas de ruptura de frío, en la misma línea de tiempo."),
    panel("Ventas por canal", "piechart", 16, 4, 8, 9, [consulta(f"SELECT o.canal AS canal, sum(t.total_clp) AS ventas {VENTAS} AND $__timeFilter(o.creada_en) GROUP BY 1")],
          {"legend": {"displayMode": "table", "placement": "bottom", "values": ["value", "percent"]}, "pieType": "donut", "reduceOptions": {"calcs": ["lastNotNull"], "values": True, "fields": "/^ventas$/"}},
          {"unit": "prefix:$"}),
    panel("Temperatura de cámara por camión (°C)", "timeseries", 0, 13, 16, 9, [consulta("SELECT registrado_en AS time, camion_id AS metric, temp_camara AS value FROM telemetria WHERE $__timeFilter(registrado_en) ORDER BY 1", "time_series")],
          {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}, {"unit": "celsius", "custom": {"lineWidth": 2, "fillOpacity": 0}}),
    panel("Posición actual de la flota", "geomap", 16, 13, 8, 9, [consulta("SELECT DISTINCT ON (camion_id) camion_id, lat, \"long\", temp_camara, alerta_ruptura_frio FROM telemetria ORDER BY camion_id, registrado_en DESC")],
          {"view": {"id": "coords", "lat": -38.7459, "lon": -72.6000, "zoom": 11}, "controls": {"showZoom": True, "mouseWheelZoom": True},
           "basemap": {"type": "osm-standard", "name": "Mapa"},
           "layers": [{"type": "markers", "name": "Camiones", "config": {"showLegend": True, "style": {"size": {"fixed": 9, "min": 2, "max": 15}, "color": {"field": "temp_camara", "fixed": "dark-green"},
                                                                                                  "symbol": {"mode": "fixed", "fixed": "img/icons/marker/circle.svg"}, "text": {"mode": "field", "field": "camion_id", "fixed": ""}, "textConfig": {"fontSize": 12, "offsetY": -12}}},
                       "location": {"mode": "coords", "latitude": "lat", "longitude": "long"}, "tooltip": True}]},
          {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": "blue", "value": None}, {"color": "green", "value": -10}, {"color": "orange", "value": 4}, {"color": "red", "value": 8}]}}),
    panel("Pedidos afectados por ruptura de frío", "table", 0, 22, 24, 7, [consulta("""SELECT o.orden_id AS "Orden", c.nombre AS "Cliente", o.canal AS "Canal", d.camion_id AS "Camión", count(m.*) AS "Lecturas con alerta", t.total_clp AS "Monto (CLP)"
FROM v_orden o JOIN v_orden_total t USING (orden_id) JOIN cliente c ON c.cliente_id = o.cliente_id
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN telemetria m ON m.camion_id = d.camion_id AND m.alerta_ruptura_frio AND m.registrado_en >= d.salida_en AND m.registrado_en <= COALESCE(d.llegada_en, now())
WHERE d.salida_en IS NOT NULL GROUP BY 1,2,3,4,6 ORDER BY 5 DESC""")],
          {"showHeader": True}, {"custom": {"align": "auto"}},
          [{"matcher": {"id": "byName", "options": "Monto (CLP)"}, "properties": [{"id": "unit", "value": "prefix:$"}]},
           {"matcher": {"id": "byName", "options": "Lecturas con alerta"}, "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background"}},
                                                                                     {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "orange", "value": None}, {"color": "red", "value": 10}]}}]}]),
]

dashboard = {
    "uid": "cofrial-torre", "title": "Cofrial: ventas y cadena de frío", "tags": ["cofrial", "bi"], "timezone": "browser",
    "schemaVersion": 39, "version": 1, "refresh": "5s", "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m"]}, "panels": paneles, "annotations": {"list": []}, "templating": {"list": []},
    "description": "Tablero en vivo: ventas por canal cruzadas con las alertas de ruptura de frío de la flota."}

destino = pathlib.Path(__file__).parent / "dashboards" / "cofrial.json"
destino.parent.mkdir(exist_ok=True)
destino.write_text(json.dumps(dashboard, ensure_ascii=False, indent=1), encoding="utf-8")
print("Escrito", destino)
