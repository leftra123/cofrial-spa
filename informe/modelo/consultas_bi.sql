-- Consultas de ejemplo para el dashboard de Grafana. Cruzan ventas por canal con alertas de cadena de frío.

-- 1. Ventas por día y canal (B2B / B2C), en pesos.
SELECT date_trunc('day', o.creada_en) AS dia, o.canal,
       t.total_clp AS ventas_clp_orden, o.orden_id
FROM v_orden o
JOIN v_orden_total t ON t.orden_id = o.orden_id
WHERE o.estado_orden_id <> (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Cancelada')
ORDER BY 1, 2;

-- 1b. Resumen por día y canal.
SELECT date_trunc('day', o.creada_en) AS dia, o.canal, sum(t.total_clp) AS ventas_clp, count(*) AS ordenes
FROM v_orden o JOIN v_orden_total t ON t.orden_id = o.orden_id
WHERE o.estado_orden_id <> (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Cancelada')
GROUP BY 1, 2 ORDER BY 1, 2;

-- 2. Alertas de ruptura de frío por día y camión.
SELECT date_trunc('day', registrado_en) AS dia, camion_id, count(*) AS lecturas_en_alerta
FROM telemetria WHERE alerta_ruptura_frio GROUP BY 1, 2 ORDER BY 1, 2;

-- 3. Cruce: ventas por día junto a las alertas del mismo día.
WITH v AS (
  SELECT date_trunc('day', o.creada_en) AS dia, sum(t.total_clp) AS ventas_clp
  FROM orden o JOIN v_orden_total t ON t.orden_id = o.orden_id GROUP BY 1),
a AS (
  SELECT date_trunc('day', registrado_en) AS dia, count(*) AS alertas
  FROM telemetria WHERE alerta_ruptura_frio GROUP BY 1)
SELECT coalesce(v.dia, a.dia) AS dia, coalesce(v.ventas_clp, 0) AS ventas_clp, coalesce(a.alertas, 0) AS alertas
FROM v FULL JOIN a ON a.dia = v.dia ORDER BY 1;

-- 4. Órdenes cuyo despacho tuvo una alerta de frío durante el viaje (alimenta al CRM).
SELECT DISTINCT o.orden_id, c.nombre AS cliente, d.camion_id
FROM v_orden o
JOIN cliente c ON c.cliente_id = o.cliente_id
JOIN despacho d ON d.despacho_id = o.despacho_id
JOIN telemetria t ON t.camion_id = d.camion_id AND t.alerta_ruptura_frio
 AND t.registrado_en BETWEEN d.salida_en AND coalesce(d.llegada_en, now());

-- 5. Control de consistencia: lecturas cuya alerta no coincide con el rango del camión (debe dar 0 filas).
SELECT t.telemetria_id, t.camion_id, t.temp_camara, t.alerta_ruptura_frio
FROM telemetria t
JOIN camion ca ON ca.camion_id = t.camion_id
JOIN rango_temperatura r ON r.rango_temperatura_id = ca.rango_temperatura_id
WHERE t.alerta_ruptura_frio <> (t.temp_camara < r.temp_min_c OR t.temp_camara > r.temp_max_c);
