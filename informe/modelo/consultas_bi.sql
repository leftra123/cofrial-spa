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

-- 6. Conversión del mes: prospectos ganados sobre cerrados (ganados + perdidos).
SELECT date_trunc('month', p.cerrado_en) AS mes,
       count(*) FILTER (WHERE e.es_ganada) AS ganados,
       count(*) FILTER (WHERE NOT e.es_ganada) AS perdidos,
       round(100.0 * count(*) FILTER (WHERE e.es_ganada) / count(*), 1) AS conversion_pct
FROM prospecto p JOIN etapa_pipeline e ON e.etapa_id = p.etapa_id
WHERE p.cerrado_en IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- 7. Valor del embudo abierto por etapa.
SELECT e.nombre AS etapa, count(*) AS prospectos, coalesce(sum(p.monto_estimado_clp), 0) AS valor_clp
FROM prospecto p JOIN etapa_pipeline e ON e.etapa_id = p.etapa_id
WHERE NOT e.es_final GROUP BY e.nombre, e.orden_etapa ORDER BY e.orden_etapa;

-- 8. Prospectos abiertos sin actividad en los últimos 7 días.
SELECT p.prospecto_id, p.empresa, max(i.registrada_en) AS ultima_interaccion
FROM prospecto p
JOIN etapa_pipeline e ON e.etapa_id = p.etapa_id AND NOT e.es_final
LEFT JOIN interaccion i ON i.prospecto_id = p.prospecto_id
GROUP BY p.prospecto_id, p.empresa
HAVING max(i.registrada_en) IS NULL OR max(i.registrada_en) < now() - interval '7 days';

-- 9. Tiempo medio de primera respuesta a requerimientos, en minutos.
SELECT round(avg(extract(epoch FROM (respondido_en - creado_en)) / 60)::numeric, 1) AS minutos_primera_respuesta
FROM requerimiento WHERE respondido_en IS NOT NULL;
