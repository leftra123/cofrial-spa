# Torre de control: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una pantalla `/torre/` de solo lectura, para gerencia y administración, que muestre en vivo el negocio de Cofrial, su dolor y la evidencia de cada punto de la rúbrica.

**Architecture:** App Django `torre` sin modelos. `torre/servicios.py` arma un único diccionario («pulso») que la vista entrega como JSON cada 5 s y, al cargar, dentro de la página con `json_script`. Un solo renderizador en `static/js/torre.js` dibuja todo: no hay HTML duplicado entre servidor y navegador.

**Tech Stack:** Django con plantillas, PostgreSQL, Leaflet local (`CofrialMapa`), JavaScript sin dependencias.

**Spec:** `docs/superpowers/specs/2026-11-08-torre-de-control-design.md` (léelo antes de cada tarea; contiene copys y umbrales).

## Global Constraints

- Todo en español. Sin React, HTMX ni Tailwind. Sin dependencias nuevas.
- La Torre no escribe en la base. **No usar `flota.servicios.estado_flota`** (llama a `confirmar_vencidas`, que escribe): usar `flota.vigente.ultimas_vigentes()` y consultar `Despacho` directo. **No usar `crm.servicios.indicadores`** (N+1).
- Lo calculable no se guarda (3FN). Colores con los tokens de `cofrial.css`; sin desborde a 375 px; tema claro y oscuro.
- Rótulo exacto, fijo en toda la Torre: «Clientes ilustrativos: nombres públicos usados como ejemplo; ninguno es cliente confirmado de Cofrial».
- Pedidos de historial: `numero_oc` empieza con `HIS-`.
- **`cargar_demo` no siembra la muestra durante las pruebas** (`sys.argv[1:2] == ["test"]`, patrón ya usado en ese comando): evita alargar 800 pruebas y alterar sus conteos. Las pruebas de esta función llaman a `muestra.sembrar` a mano.
- Archivos nuevos: crearlos con Bash y ruta relativa, porque la herramienta Write rechaza la ruta del worktree (carpeta en NFD).
- Commits al cierre de cada tarea en la rama actual, con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Sin push ni despliegue.

**Cómo correr pruebas.** Una sola vez, crear `.env` (ignorado) desde `.env.example` con `COMPOSE_PROJECT_NAME=cofrial-torre`, `WEB_PUERTO=8091`, `DB_PUERTO=54391` y valores cualesquiera en `DEMO_PASSWORD`, `GRAFANA_DB_PASSWORD`, `GRAFANA_PASSWORD`; luego `docker build -t cofrial-torre-web ./web`. En adelante, `PRUEBA` significa:

```bash
docker compose run --rm -e DEMO_PASSWORD= -e ADMIN_PASSWORD= -v "$PWD/web:/app" web python manage.py test <etiqueta> --noinput --keepdb
```

## Review Focus

1. Simulador detenido (última lectura de más de 2 min): D3 no queda en verde y la Lectura lo dice. Prueba en Tarea 6.
2. Solo hay lecturas forzadas desde `/demo/`: D3 no queda en verde y la Lectura agrega «simulación en curso». Pruebas en Tareas 5 y 6.
3. Base recién creada, sin pedidos ni telemetría: `/torre/pulso/` responde 200 y la pantalla explica qué falta. Prueba en Tarea 5.
4. Sesión vencida con la pantalla abierta: el sondeo recibe un redirect al login y la Torre muestra «Tu sesión terminó» con enlace, sin pintar el login dentro ni seguir en verde. Comprobación en Tarea 8.
5. Nombre de cliente con HTML (`<img src=x onerror=...>`, posible por el registro de empresas): se ve como texto en mapa, tabla y embudo. Comprobación en Tarea 8.

---

### Task 1: Segmento de cliente

**Files:**
- Modify: `web/clientes/models.py`, `web/clientes/admin.py`
- Create: `web/clientes/migrations/0004_segmento_cliente.py`
- Test: `web/clientes/tests_segmento.py`

**Interfaces:**
- Produces: `clientes.models.SegmentoCliente` (`segmento_id`, `nombre` único; tabla `segmento_cliente`); `Cliente.segmento` (FK anulable, `SET_NULL`). Nombres de fila: `Hospital`, `Supermercado`, `Feria`, `Institucional`, creados por la migración con `RunPython` para que existan también en pruebas.

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_los_cuatro_segmentos_existen`: `set(values_list("nombre"))` igual a los cuatro. `test_cliente_sin_segmento_es_valido`: un `Cliente` con `segmento=None` hace `full_clean(exclude=["usuario"])` sin error. `test_borrar_segmento_no_borra_cliente`: tras `segmento.delete()`, el cliente sigue con `segmento_id is None`.

- [ ] **Step 2:** `PRUEBA clientes.tests_segmento`. Esperado: error de importación de `SegmentoCliente`.
- [ ] **Step 3: Implementar el modelo, la migración y el registro en admin (con `segmento` editable en `Cliente`).**
- [ ] **Step 4:** `PRUEBA clientes.tests_segmento`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Segmento de cliente: hospital, supermercado, feria e institucional».

### Task 2: Nivel del cliente en el embudo

**Files:**
- Modify: `web/crm/servicios.py`
- Test: `web/crm/tests_niveles.py`

**Interfaces:**
- Produces, en `crm/servicios.py`:
  - constantes `DIAS_EN_RIESGO = 30`, `PEDIDOS_FIDELIZADO = 4`, `VENTANA_FIDELIZADO_DIAS = 90`.
  - `nivel_de(total: int, en_ventana: int, ultimo: datetime | None, ahora: datetime) -> str`, función pura que devuelve `"Ganado sin pedido" | "Primer pedido" | "Recompra" | "Fidelizado" | "En riesgo"`.
  - `nivel_de_cliente(cliente) -> str`.
  - `embudo_por_niveles(usuario) -> dict` con `{"fases": [{"nombre", "etapas": [{"nombre", "n", "monto_clp", "items": [{"nombre", "url", "detalle"}]}]}], "aparte": [mismas etapas], "n_b2c": int}`.

Fases: Atracción (Prospecto), Interés (Contactado), Consideración (Propuesta enviada, Negociación), Acción (Ganado sin pedido, Primer pedido), Fidelización (Recompra, Fidelizado). Aparte: En riesgo, Perdido.

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_limites_de_nivel` con `ahora` fijo:

```python
self.assertEqual(s.nivel_de(0, 0, None, A), "Ganado sin pedido")
self.assertEqual(s.nivel_de(1, 1, A - timedelta(days=30), A), "Primer pedido")
self.assertEqual(s.nivel_de(1, 0, A - timedelta(days=31), A), "En riesgo")
self.assertEqual(s.nivel_de(2, 2, A - timedelta(days=1), A), "Recompra")
self.assertEqual(s.nivel_de(3, 3, A - timedelta(days=1), A), "Recompra")
self.assertEqual(s.nivel_de(4, 4, A - timedelta(days=1), A), "Fidelizado")
self.assertEqual(s.nivel_de(9, 4, A - timedelta(days=31), A), "En riesgo")
```

`test_cancelados_no_cuentan`: un cliente con una orden «Cancelada» queda en «Ganado sin pedido». `test_quien_entra`: aparece un B2B con segmento, un B2B con prospecto ganado y un B2B con pedidos; no aparecen un B2B sin segmento, prospecto ni pedidos, una solicitud por aprobar (`solicitudes_empresa`) ni un B2C. `test_b2c_se_cuenta_aparte`: `n_b2c` coincide. `test_vendedor_ve_solo_su_cartera`: con `vendedora@cofrial.cl` no aparece un cliente de Pedro. `test_consultas_acotadas`: con 30 clientes, `assertNumQueries` constante al duplicarlos (agregar con `Count` y `Max`, no por cliente).

- [ ] **Step 2:** `PRUEBA crm.tests_niveles`. Esperado: `AttributeError` por `nivel_de`.
- [ ] **Step 3: Implementar.** `embudo_por_niveles` usa `prospectos_visibles` y `clientes_visibles`; `url` apunta a `/crm/prospectos/<id>/` o `/crm/clientes/<id>/`; `detalle` es el monto o «N pedidos, último dd/mm». «Perdido» muestra solo los últimos 90 días.
- [ ] **Step 4:** `PRUEBA crm.tests_niveles`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Nivel del cliente: del prospecto a la fidelización, calculado desde los pedidos».

### Task 3: Clientes de muestra e historial

**Files:**
- Create: `web/clientes/muestra.py`, `web/clientes/management/commands/limpiar_muestra.py`
- Modify: `web/catalogo/management/commands/cargar_demo.py` (después de `regionales.sembrar`, línea 260)
- Test: `web/clientes/tests_muestra.py`

**Interfaces:**
- Consumes: `SegmentoCliente`, `crm.servicios.nivel_de_cliente`.
- Produces: `muestra.sembrar(tipo_b2b) -> list[str]` (avisos), `muestra.limpiar() -> dict[str, int]`, `muestra.RUT_ILUSTRATIVOS: frozenset[str]` (muestra y `regionales.HOSPITALES`, más Hospital Regional de Temuco y Supermercados del Sur).

Contenido: la lista del spec §9 con coordenadas de OpenStreetMap consultadas una vez y fijadas en el módulo (User-Agent genérico, sin correo). Usar RUT ficticios de la serie `70.400.1xx-d` con dígito verificador válido y correos `.test`. Regiones `Biobío` y `Los Ríos`, y sus comunas, con `get_or_create`. Segmento a los ya existentes solo si es nulo. Historial con `random.Random(2026)`, referencia `HIS-<dv del rut sin puntos>-<n>` (máximo 30 caracteres).

Reciben historial solo los clientes nuevos y estos seis RUT: `70.300.101-7`, `70.300.102-5`, `70.300.103-3`, `70.300.105-K`, `70.300.106-8`, `70.300.109-2`. Reparto de modo que haya al menos un cliente en cada nivel.

Cada pedido: `Orden` en «Entregada» con `OrdenItem` a `pedidos.precio_de`, sin tocar stock. Luego `documentos.emitir_factura` y `documentos.registrar_pago(doc.pk, doc.monto_clp, "transferencia")` dentro de `transaction.atomic`, y `update` de `creada_en`, `entrega_resuelta_en`, `emitido_en` y `vence_en`.

Prospectos: 2 de `vendedora@cofrial.cl` y 2 de `vendedor2@cofrial.cl`, contactos ficticios, uno en «Perdido» con motivo y `cerrado_en`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Con `call_command("cargar_demo")` en `setUpTestData` y `muestra.sembrar(...)` en cada prueba:

`test_cargar_demo_no_siembra_en_pruebas`: 0 órdenes `HIS-`. `test_idempotente`: dos `sembrar` dejan iguales los conteos de `Cliente`, `Orden`, `Documento`, `Prospecto`. `test_limites_del_historial`: entre 60 y 120 órdenes `HIS-`, todas con `creada_en` entre 90 días y 24 h atrás, `despacho_id` nulo. `test_stock_no_cambia`: `stock_disponible` de todos los productos igual antes y después. `test_cobranza_no_cambia`: `resumen_cobranza(Cliente.objects.all())` conserva `por_cobrar`, `vencido` y la cantidad de `sin_facturar`. `test_excluidos_sin_historial`: Hospital Regional, Supermercados del Sur, Angol, Villarrica y Pucón sin órdenes `HIS-`. `test_carteras_de_clientes_iguales`: `Cliente.objects.filter(vendedor=...)` igual para ambos. `test_hay_cliente_en_cada_nivel`: los cinco niveles aparecen. `test_no_pisa_segmento`: un segmento cambiado a mano sobrevive a `sembrar`. `test_coordenadas_presentes`: toda dirección de muestra con `lat` y `long`. `test_limpiar_revierte`: tras `limpiar()`, conteos y stock iguales a los anteriores a `sembrar`, y los pedidos que no son `HIS-` siguen ahí.

- [ ] **Step 2:** `PRUEBA clientes.tests_muestra`. Esperado: error de importación de `clientes.muestra`.
- [ ] **Step 3: Implementar módulo, comando `limpiar_muestra` (imprime los conteos de `limpiar()`) y llamada desde `cargar_demo`, envuelta en el mismo `try` que `regionales`, sin correr en pruebas.**
- [ ] **Step 4:** `PRUEBA clientes.tests_muestra`. Esperado: `OK`.
- [ ] **Step 5:** Con el stack aislado arriba, medir `/crm/` con gerencia antes y después de sembrar. Esperado: menos de 2 s; si no, reducir historial hacia 60.
- [ ] **Step 6:** Commit «Clientes de muestra e historial, reversibles con limpiar_muestra».

### Task 4: Contornos de la macrozona

**Files:**
- Create: `web/static/geo/macrozona_sur.geojson`
- Test: `web/torre/tests_geo.py` (crear también `web/torre/__init__.py`)

Datos de OpenStreetMap (Nominatim, `polygon_geojson=1`, `polygon_threshold` ajustado), una descarga por región y simplificado. Propiedades: `nombre` y `principal` (`true` solo en La Araucanía).

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_cuatro_regiones`: nombres `{"Biobío", "La Araucanía", "Los Ríos", "Los Lagos"}`. `test_solo_araucania_es_principal`. `test_peso`: menos de 200 KB. `test_temuco_dentro_de_araucania` y `test_valdivia_fuera_de_araucania`, con punto en polígono escrito en la prueba (Temuco `-38.7359, -72.5904`; Valdivia `-39.8142, -73.2459`).

- [ ] **Step 2:** `PRUEBA torre.tests_geo`. Esperado: `FileNotFoundError`.
- [ ] **Step 3: Generar el archivo.**
- [ ] **Step 4:** `PRUEBA torre.tests_geo`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Contornos de la macrozona sur (OpenStreetMap, ODbL)».

### Task 5: Pulso de negocio y Lectura del momento

**Files:**
- Create: `web/torre/servicios.py`, `web/torre/lectura.py`
- Test: `web/torre/tests_pulso.py`

**Interfaces:**
- Consumes: `crm.servicios.embudo_por_niveles`, `flota.vigente.ultimas_vigentes`.
- Produces:
  - `servicios.datos_negocio(usuario) -> dict` con `camiones` (`[{"id","lat","long","alerta"}]`, solo con viaje activo o alerta), `clientes_mapa` (`[{"nombre","segmento","comuna","lat","long","nivel","url"}]`, solo con segmento), `frecuentes` (8, con `pedidos`, `ultimo`, `nivel`), `embudo`, `ahora`.
  - `ahora` tiene `ultima_lectura_seg | None`, `alertas_24h`, `riesgo_actual_clp`, `camiones_en_alerta`, `riesgo_historico_clp`, `no_concretadas`, `interacciones`, `ventas_24h` (`{"B2B": clp, "B2C": clp}`), `simulacion: bool`, `mas_expuesto | None`.
  - `lectura.redactar(ahora: dict) -> list[str]`, de dos o tres frases.

Riesgo actual: órdenes no «Entregada» ni «Cancelada», en un despacho con `salida_en` y sin `regreso_en`, cuyo camión tiene alerta en `ultimas_vigentes()`. Riesgo histórico: misma consulta que `AFECTADAS` en `grafana/generar_dashboard.py` (copiarla con un comentario que apunte al original). Ventas con `v_orden_total`, sin canceladas. `simulacion`: existe una lectura `forzada=True` de menos de `VIGENCIA_FORZADA_S`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_base_vacia`: sin órdenes ni telemetría, `datos_negocio` no lanza error; `ultima_lectura_seg` es `None` y `lectura.redactar` incluye «Sin lecturas de los camiones todavía». `test_riesgo_actual_excluye_entregadas`: un viaje con alerta y dos órdenes, una entregada, cuenta solo la otra. `test_riesgo_actual_vuelve_a_cero_e_historico_no`: al cerrar el viaje, `riesgo_actual_clp == 0` y `riesgo_historico_clp > 0`. `test_clientes_mapa_solo_con_segmento`: `ana@correo.test` y `felipe@cofrial.cl` no aparecen. `test_frecuentes_excluye_canceladas_y_limita_a_8`. `test_lectura_sin_novedades`: sin alertas incluye «Sin novedades en la cadena de frío». `test_lectura_con_alerta`: nombra la cantidad de camiones, el monto y `mas_expuesto`. `test_lectura_sin_ventas`: con ventas en cero incluye «Sin ventas en 24 h». `test_lectura_simulacion`: `simulacion=True` incluye «simulación en curso». `test_no_escribe`: `CaptureQueriesContext` no registra `INSERT`, `UPDATE` ni `DELETE`.

- [ ] **Step 2:** `PRUEBA torre.tests_pulso`. Esperado: error de importación.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4:** `PRUEBA torre.tests_pulso`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Torre: datos de negocio y lectura del momento por reglas».

### Task 6: Evidencia de la rúbrica

**Files:**
- Create: `web/torre/rubrica.py`
- Test: `web/torre/tests_rubrica.py`

**Interfaces:**
- Produces: `rubrica.evaluar() -> list[dict]` con 5 filas `{"dim","titulo","exigencia","evidencia": list[str],"estado","url"}`. Estados: `VERIFICADO = "verificado"`, `SIN_EVIDENCIA = "sin_evidencia"`, `NO_COMPROBADO = "no_comprobado"`. Cualquier excepción de base en una fila la deja en `NO_COMPROBADO` y no tumba las demás.
- Consumes: `connection.settings_dict["HOST"]`, `settings.GRAFANA_INTERNA_URL`.

Reglas según spec §8.7, con estas precisiones: D2 no cuenta pedidos `HIS-`; D3 usa `Telemetria` con `forzada=False`; D4 usa ventana de 7 días, muestra cuántas ventas son `HIS-` y consulta `/api/health` de Grafana (timeout 1 s, caché 30 s); D5 muestra nombres de proveedores configurados (`GEMINI_API_KEY`, `GROQ_API_KEY`), nunca valores, y añade «La defensa en vivo la hace el equipo». Instancia EC2 en D1: `torre.rubrica.instancia_ec2() -> str | None` (IMDSv2, timeout 200 ms, caché de proceso; si falla, variable `INSTANCIA_EC2`). Si es `None`, D1 queda en `NO_COMPROBADO`. El host de RDS se muestra enmascarado: `…<fin>.rds.amazonaws.com`.

- [ ] **Step 1: Escribir las pruebas que fallan**

D1: `test_d1_host_local_no_es_verde` (host `db`, `SIN_EVIDENCIA`); `test_d1_rds_sin_instancia` (`NO_COMPROBADO`); `test_d1_rds_con_instancia` (`VERIFICADO`, y el host completo no aparece). D2: `test_d2_solo_historial_no_es_verde`; `test_d2_ambos_canales`. D3: `test_d3_lectura_reciente`; `test_d3_simulador_detenido` (3 min, `SIN_EVIDENCIA`); `test_d3_solo_forzadas` (`SIN_EVIDENCIA`); y la evidencia contiene los seis nombres de campo exactos. D4: `test_d4_grafana_caido` (`NO_COMPROBADO`); `test_d4_sin_ventas` (`SIN_EVIDENCIA`); `test_d4_sin_alertas_es_verde`; `test_d4_cuenta_ilustrativas`. D5: `test_d5_ia_de_pago_no_es_verde` (con `ANTHROPIC_API_KEY`); `test_d5_sin_clasificacion`; `test_d5_no_muestra_claves` (el valor de la clave no aparece en el JSON). `test_error_de_base_aisla_la_fila`.

- [ ] **Step 2:** `PRUEBA torre.tests_rubrica`. Esperado: error de importación.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4:** `PRUEBA torre.tests_rubrica`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Torre: evidencia viva por cada punto de la rúbrica».

### Task 7: Rutas, permisos, menú e inicio

**Files:**
- Create: `web/torre/urls.py`, `web/torre/vistas.py`, `web/templates/torre/panel.html` (mínima, se completa en Tarea 8)
- Modify: `web/cofrial/urls.py`, `web/cofrial/acceso.py:7`, `web/cofrial/contexto.py:28`, `web/templates/base.html` (etiqueta «Operación»), `web/cofrial/tests_rutas.py`, `docs/cuentas-y-permisos.md`
- Test: `web/torre/tests_vistas.py`

**Interfaces:**
- Consumes: `servicios.datos_negocio`, `rubrica.evaluar`, `lectura.redactar`, `crm.views.con_rol`.
- Produces: `servicios.pulso(usuario) -> dict` (claves de `datos_negocio` más `generado_en`, `lectura`, `rubrica`, `front_back: None`, `pedido_trazado: None`); caché de 4 s con clave por rol; `GET /torre/` y `GET /torre/pulso/` con `con_rol("admin", "gerencia")` y `require_GET`; `menu["torre"]`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_permisos`: gerencia y admin 200 en ambas rutas; vendedor, despachador, B2B y B2C 403; anónimo al login. `test_post_405`. `test_gerencia_inicia_en_torre`: el login redirige a `/torre/`. `test_admin_sigue_en_crm`. `test_menu`: gerencia ve `/torre/`; vendedora no. `test_pulso_json`: tiene `lectura`, `rubrica` de 5 filas, `embudo`, `ahora`. `test_panel_lleva_rotulo`: la página contiene el rótulo exacto. `test_pulso_cacheado`: dos llamadas seguidas con `cache` activa hacen `assertNumQueries(0)` en la segunda (limpiar caché en `setUp`).

Actualizar `tests_rutas.py`: `INICIO["gerencia"] = "/torre/"`, filas `'/torre/': ('L 403 403 403 200 403 200', '405 405 405 405 405 405 405')` y lo mismo para `/torre/pulso/`, y las filas donde gerencia caía en `/crm/` por inicio. Esas filas fallan al correr y la tabla indica cuáles.

- [ ] **Step 2:** `PRUEBA torre.tests_vistas cofrial.tests_rutas`. Esperado: fallan por 404 y por inicio.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4:** `PRUEBA torre.tests_vistas cofrial.tests_rutas cofrial.tests_navegacion cofrial.tests_403_por_rol cofrial.tests_casos_sesion`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Torre de control: rutas, permisos y primera opción de gerencia».

### Task 8: La pantalla

**Files:**
- Modify: `web/templates/torre/panel.html`
- Create: `web/static/js/torre.js`, `web/static/css/torre.css`, `web/torre/antes.py`
- Test: `web/torre/tests_vistas.py`

**Interfaces:**
- Consumes: claves de `servicios.pulso`; `CofrialMapa.crear(id, centro, zoom)`, `.camion(alerta, id, zoom)`, `.base()`; `/static/geo/macrozona_sur.geojson`.
- Produces: `antes.REGISTRO` (lista de `(hora, canal, texto)`, 6 líneas según spec §8.4), `antes.SUPUESTOS` (13,5, 22,5 y 36 millones; 300 viajes; 15 min; 75 h), que la vista pasa al `pulso` inicial. `torre.js` expone `render(pulso)` y sondea cada 5 s.

Orden en página: spec §8.1 a §8.5, §8.6 (Tarea 9) y §8.7. Todo el contenido variable se inserta con `textContent` o `createElement`, nunca con `innerHTML`; en Leaflet, `bindPopup` recibe un nodo DOM. Marcadores de cliente con `L.divIcon`: letra H, S, F o I sobre el color del segmento. Polígono de La Araucanía con relleno y borde fuertes usando el token de acento; regiones vecinas con contorno tenue; etiquetas con `bindTooltip({permanent: true})`. Pausa con `document.hidden`. El sondeo usa `redirect: "manual"`: `opaqueredirect` o 401/403 muestran «Tu sesión terminó» con enlace a ingresar y detienen el sondeo; un fallo de red muestra «Sin conexión desde hh:mm:ss» y atenúa la rúbrica, de modo que ninguna fila se vea verificada. Estados con ícono y texto, no solo color.

- [ ] **Step 1: Escribir la prueba que falla**

`test_panel_incluye_supuestos_y_datos`: la página contiene «Reconstrucción ilustrativa, no son datos de Cofrial», «La merma evitada se medirá con datos de Cofrial», `id="pulso-inicial"` y `js/torre.js`. `test_antes_no_inventa_tasa`: «alta tasa según el caso; nadie la registra» está presente.

- [ ] **Step 2:** `PRUEBA torre.tests_vistas`. Esperado: fallan esas dos.
- [ ] **Step 3: Implementar plantilla, CSS y JS.**
- [ ] **Step 4:** `PRUEBA torre.tests_vistas`. Esperado: `OK`.
- [ ] **Step 5: Comprobar en navegador con Playwright y Chromium** contra `http://torre.localhost:8091/` con gerencia, con el simulador corriendo y la muestra sembrada. Con capturas a 1440 y 375 px, en tema claro y oscuro:
  - La Araucanía se distingue de un vistazo y `document.documentElement.scrollWidth <= innerWidth`.
  - Bloquear `tile.openstreetmap.org`: los contornos siguen visibles.
  - Comprar como `ana@correo.test`: en menos de 10 s cambia «Ventas».
  - `docker compose stop` del simulador: en menos de 3 min D3 pasa a «Sin evidencia ahora».
  - Detener `web`: aparece «Sin conexión» y ninguna fila se ve verificada.
  - Borrar la cookie de sesión: aparece «Tu sesión terminó», sin login dentro de la página.
  - Crear un cliente con segmento y nombre `<img src=x onerror=window.__x=1>`: se ve como texto y `window.__x` es `undefined`.
  - La consola no muestra errores.
- [ ] **Step 6:** Commit «Torre de control: mapa, embudo, antes y ahora, y rúbrica en vivo».

### Task 9: Front-Office, Back-Office y pedido trazado

La tabla de componentes es importante. El pedido trazado es lo primero que se recorta (spec §12).

**Files:**
- Modify: `web/torre/servicios.py`, `web/static/js/torre.js`
- Test: `web/torre/tests_pulso.py`

**Interfaces:**
- Produces: `servicios.front_back() -> dict` con `{"front": [...], "back": [...]}`, filas `{"nombre","dato","url"}` de E-commerce, CRM e IA, y AWS, IoT y BI. `servicios.pedido_trazado() -> dict | None` con `{"orden_id","cliente","camion_id","temp_camara","alerta","orden_url","cliente_url"}`, tomado de la última orden con despacho con `salida_en` y lectura de su camión, excluyendo `HIS-`. Ambas se conectan en `pulso` en lugar de los `None` de la Tarea 7.

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_front_back_simetrico`: 3 filas por lado, todas con `dato` y `url`. `test_pedido_trazado_sin_viajes`: `None`. `test_pedido_trazado_con_viaje`: trae el camión y la temperatura de su última lectura. `test_pedido_trazado_alerta`: `alerta` verdadera con lectura en alerta.

- [ ] **Step 2:** `PRUEBA torre.tests_pulso`. Esperado: fallan las cuatro.
- [ ] **Step 3: Implementar y dibujar.** Sin pedido trazado, la sección dice «Aún no hay un pedido en viaje para trazar».
- [ ] **Step 4:** `PRUEBA torre.tests_pulso`. Esperado: `OK`. Luego comprobar en navegador a 1440 y 375 px.
- [ ] **Step 5:** Commit «Torre: equilibrio Front-Office y Back-Office, con un pedido trazado».

### Task 10: Nivel y rótulo en la ficha del cliente

Recortable (spec §12).

**Files:**
- Modify: `web/crm/views.py` (vista de ficha), `web/templates/crm/cliente.html`
- Test: `web/crm/tests_niveles.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_ficha_muestra_nivel`: la ficha de un B2B contiene su nivel. `test_ficha_rotula_ilustrativo`: un RUT de `RUT_ILUSTRATIVOS` muestra «Cliente ilustrativo»; uno ajeno no. `test_ficha_b2c_sin_nivel`: `ana@correo.test` no muestra nivel.

- [ ] **Step 2:** `PRUEBA crm.tests_niveles`. Esperado: fallan las tres.
- [ ] **Step 3: Implementar**, pasando `nivel` e `ilustrativo` al contexto y mostrándolos en `.sub` de la cabecera.
- [ ] **Step 4:** `PRUEBA crm`. Esperado: `OK`.
- [ ] **Step 5:** Commit «Ficha del cliente: nivel del embudo y aviso de cliente ilustrativo».

### Task 11: Verificador, documentos y suite completa

**Files:**
- Modify: `aws/verificar.py`, `informe/01-diagnostico.md` (Tabla 5, supuesto de 15 min y macrozona), `informe/04b-modelo-datos.md` (`segmento_cliente` y `cliente.segmento`; regenerar el MER solo si el exportador lo exige), `informe/04d-crm.md` (niveles), `informe/99-bitacora.md`, `docs/decisiones.md`, `docs/guion-defensa.md`, `docs/guia-pruebas-aws.md`

- [ ] **Step 1: Agregar a `verificar.py`** con la cuenta de gerencia: `/torre/` responde 200, `/torre/pulso/` trae 5 filas de rúbrica y se imprime el estado de cada una, sin fallar si un estado es «sin evidencia» antes de la demo. Una cuenta de vendedor recibe 403.
- [ ] **Step 2: Actualizar los documentos.** En el guion, abrir la Torre al inicio del bloque 1 y recordar comprar en vivo; en la guía de AWS, los pasos de `FORZAR_CARGA_DEMO=1`, `limpiar_muestra` y el snapshot; en el informe, los supuestos marcados como supuestos.
- [ ] **Step 3: Correr la suite completa en segundo plano** (unos 13 min), sin `| tail`: `PRUEBA` sin etiqueta. Esperado: línea final `OK`.
- [ ] **Step 4:** Commit «Torre de control: verificador, guion, informe y bitácora».

## Después del plan (requiere el visto bueno de Eric)

Fusión y despliegue según spec §12: coordinar con otras sesiones por `RAMA`, intentar snapshot de RDS, `recrear-web`, carga forzada, `recrear-iot` si corresponde y `verificar.py`. Fecha límite de decisión: miércoles 11-nov a las 18:00.
