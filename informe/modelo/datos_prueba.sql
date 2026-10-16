-- Datos de ejemplo para probar el esquema, el dashboard y la demostración. Todos son ficticios.
INSERT INTO region (nombre) VALUES ('La Araucanía');
INSERT INTO comuna (region_id, nombre) VALUES (1, 'Temuco'), (1, 'Villarrica');
INSERT INTO rango_temperatura (nombre, temp_min_c, temp_max_c) VALUES ('Refrigerado', 0.0, 4.0), ('Congelado', -25.0, -18.0);
INSERT INTO categoria (nombre, rango_temperatura_id) VALUES ('Cárnicos refrigerados', 1), ('Congelados', 2);
INSERT INTO producto (sku, nombre, categoria_id, unidad_medida, stock_disponible) VALUES
  ('VAC-LOM-5K', 'Lomo vetado de vacuno 5 kg', 1, 'caja', 120),
  ('POL-PEC-10K', 'Pechuga de pollo 10 kg', 1, 'caja', 80),
  ('MAR-CON-2K', 'Mariscos congelados 2 kg', 2, 'caja', 60);
INSERT INTO lista_precio (nombre) VALUES ('Institucional B2B'), ('Público B2C');
INSERT INTO precio_producto (lista_precio_id, producto_id, precio_clp) VALUES
  (1, 1, 38990), (1, 2, 29990), (1, 3, 21990),
  (2, 1, 45990), (2, 2, 34990), (2, 3, 25990);
INSERT INTO tipo_cliente (codigo, nombre, lista_precio_id) VALUES ('B2B', 'Institucional', 1), ('B2C', 'Público general', 2);
INSERT INTO usuario (email, password_hash, rol) VALUES
  ('vendedora@cofrial.test', 'hash-de-prueba', 'vendedor'),
  ('abastecimiento@hospital.test', 'hash-de-prueba', 'cliente'),
  ('ana@correo.test', 'hash-de-prueba', 'cliente');
INSERT INTO vendedor (usuario_id, nombre, telefono) VALUES (1, 'María Paz Soto', '+56912345678');
INSERT INTO cliente (usuario_id, tipo_cliente_id, vendedor_id, rut, nombre, email) VALUES
  (2, 1, 1, '61.973.200-4', 'Hospital Regional de Temuco', 'abastecimiento@hospital.test'),
  (3, 2, NULL, '12.345.678-5', 'Ana Pérez', 'ana@correo.test');
INSERT INTO direccion (cliente_id, calle_numero, comuna_id, es_principal) VALUES
  (1, 'Manuel Montt 115', 1, true), (2, 'Av. Alemania 0671', 1, true);
INSERT INTO estado_orden (nombre, orden_flujo, es_final) VALUES
  ('Recibida', 1, false), ('Confirmada', 2, false), ('En preparación', 3, false),
  ('Despachada', 4, false), ('Entregada', 5, true), ('Cancelada', 6, true);
INSERT INTO camion (camion_id, patente, capacidad_kg, rango_temperatura_id) VALUES
  ('CAM-01', 'HJKL-42', 8000, 1), ('CAM-02', 'PQRS-17', 6000, 2);
INSERT INTO despacho (camion_id, programado_para, salida_en, llegada_en) VALUES
  ('CAM-01', now() - interval '3 hours', now() - interval '3 hours', now() - interval '1 hour');
INSERT INTO orden (direccion_id, estado_orden_id, despacho_id, numero_oc) VALUES
  (1, 5, 1, 'OC-2026-0457'), (2, 2, NULL, NULL);
INSERT INTO orden_item (orden_id, producto_id, cantidad, precio_unitario_clp) VALUES
  (1, 1, 10, 38990), (1, 2, 5, 29990), (2, 1, 1, 45990);
INSERT INTO telemetria (camion_id, temp_camara, lat, "long", combustible_pct, alerta_ruptura_frio, registrado_en) VALUES
  ('CAM-01', 3.1, -38.7359, -72.5904, 80, false, now() - interval '170 minutes'),
  ('CAM-01', 5.2, -38.7401, -72.5950, 79, true,  now() - interval '120 minutes'),
  ('CAM-01', 3.4, -38.7455, -72.6001, 77, false, now() - interval '70 minutes'),
  ('CAM-02', -20.0, -39.2800, -72.2300, 60, false, now() - interval '60 minutes');
INSERT INTO etapa_pipeline (nombre, orden_etapa, es_final, es_ganada) VALUES
  ('Prospecto', 1, false, false), ('Contactado', 2, false, false), ('Propuesta enviada', 3, false, false),
  ('Negociación', 4, false, false), ('Cliente ganado', 5, true, true), ('Perdido', 6, true, false);
INSERT INTO prospecto (vendedor_id, etapa_id, nombre_contacto, empresa, email, origen, monto_estimado_clp) VALUES
  (1, 3, 'Carlos Muñoz', 'Supermercado El Sur', 'cmunoz@elsur.test', 'web', 2500000);
INSERT INTO interaccion (vendedor_id, prospecto_id, tipo, detalle) VALUES (1, 1, 'llamada', 'Se envía propuesta de precios');
INSERT INTO categoria_requerimiento (nombre) VALUES ('Reclamo'), ('Cotización'), ('Despacho'), ('Calidad o frío'), ('Otro');
INSERT INTO requerimiento (cliente_id, orden_id, asunto, descripcion, categoria_requerimiento_id, confianza_ia, estado, creado_en, respondido_en) VALUES
  (1, 1, 'Llegó tibia la carga', 'El pedido llegó con la cadena de frío cortada.', 4, 0.91, 'clasificado', now() - interval '50 minutes', now() - interval '20 minutes');
INSERT INTO prospecto (vendedor_id, etapa_id, nombre_contacto, empresa, telefono, origen, monto_estimado_clp, cerrado_en, motivo_perdida) VALUES
  (1, 6, 'Rosa Díaz', 'Almacén La Esquina', '+56911112222', 'llamada', 300000, now() - interval '2 days', 'Eligió otro proveedor por precio'),
  (1, 5, 'Hugo Salas', 'Hostal Villarrica', '+56933334444', 'feria', 700000, now() - interval '1 day', NULL);
