# Torre de control: diseño

Fecha: 8-nov-2026. Defensa: jueves 12-nov-2026. Estado: por aprobar por Eric. Sin código todavía.
Marcas: **[Eric]** lo pidió o lo decidió Eric; **[propuesta]** lo decidió quien redacta y Eric puede cambiarlo.

## 1. Intención

La plataforma ya cumple la pauta, pero hay que saltar entre menús para notarlo y nada muestra el problema de negocio de Cofrial. Se quiere una pantalla donde Eric y el profesor vean, con datos en vivo, de qué trata el negocio, qué dolor resuelve y que cada punto de la rúbrica se cumple. **[Eric]**

Público: Eric, Sergio y el profesor, durante la defensa y mientras el laboratorio esté encendido.

## 2. Objetivos

Una pantalla «Torre de control» que muestre **[Eric]**:

1. La macrozona sur, con La Araucanía marcada con claridad.
2. Clientes frecuentes reales de muestra: hospitales, cadenas de supermercados, ferias e institucionales.
3. El «antes»: un registro sin trazabilidad, con tiempo perdido en llamadas y WhatsApp personales, entregas fallidas y mermas millonarias, frente al dato de hoy.
4. El embudo, con el nivel en que está cada cliente.
5. El equilibrio verificable entre Front-Office (e-commerce + CRM) y Back-Office (AWS + IoT + BI).
6. Un análisis en tiempo real.
7. Los cinco puntos de la rúbrica del Hito 2, cada uno con evidencia.

## 3. Lo que no se hará

- Ninguna escritura desde la Torre: es solo lectura.
- No se reemplaza Grafana: sigue siendo el panel de BI de la rúbrica (D4), enlazado desde la Torre.
- Sin página pública, sin cuenta nueva para el profesor y sin roles nuevos.
- Sin integración real con WhatsApp.
- Sin IA en el ciclo de actualización: gastaría la cuota gratuita y podría fallar en plena defensa.
- Sin cambios en el simulador IoT ni en las reglas de negocio existentes.

## 4. Sería un fracaso aunque funcione si...

- Presenta un ahorro como medido, o un supuesto como dato de Cofrial.
- Marca algo como cumplido sin evidencia, o sigue en verde con el simulador caído.
- Presenta a una empresa real como cliente confirmado de Cofrial.
- Los datos sembrados ensucian cobranza, stock, despacho, carteras de vendedores o la suite de pruebas.
- Pone en riesgo la demostración que ya funciona, a cuatro días de la defensa.

## 5. Restricciones

- Stack actual: Django con plantillas, DRF, Leaflet local, PostgreSQL en RDS, WSGI sin websockets. No se agrega React, HTMX ni Tailwind.
- Modelo en 3FN: lo calculable no se guarda.
- Todo en español y en la voz de la plataforma; tema claro y oscuro; sin desborde a 375 px, aunque la prioridad es el proyector de escritorio.
- `cargar_demo` corre en cada arranque y debe seguir siendo idempotente: nunca pisa ni duplica.
- En AWS, `cargar_demo --solo-primera-vez` no carga nada si ya hay productos. Para que lleguen los datos hay que usar `FORZAR_CARGA_DEMO=1` en `secretos.env`, `recrear-web`, quitarla y recrear otra vez. El estado vigente de AWS vive en otro worktree (ver memoria de despliegue; confirmarlo antes).
- Antes de cerrar, actualizar según CLAUDE.md: `informe/04b-modelo-datos.md`, `informe/04d-crm.md`, `informe/99-bitacora.md`, `docs/decisiones.md`, `docs/guion-defensa.md`, `docs/guia-pruebas-aws.md`.

## 6. Enfoques considerados

| Enfoque | A favor | En contra |
|---|---|---|
| **Pantalla interna con cuenta de gerencia (elegido por Eric)** | Datos en vivo de RDS; la cuenta lee todo y no modifica nada | Hay que entregar la clave |
| Página pública sin clave | Se abre con el enlace | Expone clientes y ventas; mostraría pérdidas a los compradores |
| Presentación aparte | Funciona con AWS apagado | Sin conexión a la base; la rúbrica penaliza los gráficos estáticos |
| Repartir en pantallas existentes | Menos código nuevo | Sigue obligando a saltar entre menús |

## 7. Acceso **[Eric, con detalle propuesto]**

- Ruta `/torre/` y datos en `/torre/pulso/`, con `con_rol("admin", "gerencia")`. Los vendedores no entran, porque verían clientes fuera de su cartera (RN-09).
- Primera opción del menú para esos dos roles. **[propuesta]**
- `gerencia` inicia en `/torre/` (cambia `INICIOS` en `web/cofrial/acceso.py` y su prueba). `admin` sigue en `/crm/`. **[propuesta]**
- App Django nueva `torre`, sin modelos, con la forma de `operacion` (`vistas.py`, `servicios.py`, `urls.py`, `tests.py`). **[propuesta]**

## 8. Secciones de la pantalla, en este orden **[propuesta]**

### 8.1 Lectura del momento (análisis en tiempo real)

Banda superior con el indicador «En vivo» y dos o tres frases redactadas por reglas en código a partir de los datos. Ejemplo: «3 camiones con ruptura de frío y $4,2 M en pedidos en riesgo. El más expuesto es Hospital de Angol. Las ventas de 24 h van 70 % institucional». Con enlace a Grafana. Si no hay novedades, lo dice.

**Cifras de riesgo [propuesta].** La Lectura usa solo el estado actual: camiones cuya última lectura trae alerta y pedidos a bordo sin entregar. Por eso puede decir «sin novedades». La sección «Ahora» muestra además «Ventas en riesgo (histórico)», con la misma definición que Grafana, para que ambas cifras coincidan si el profesor las compara. Las lecturas forzadas desde `/demo/` cuentan como alerta, igual que en Grafana, pero la Lectura agrega «simulación en curso» mientras existan.

Actualización: sondeo cada 5 s a `/torre/pulso/` (JSON), igual que `/flota/`, con caché de 5 s en el servidor y pausa con la pestaña oculta. Si el sondeo falla, se muestra «Sin conexión desde hh:mm:ss» y las evidencias dejan de verse en verde.

### 8.2 Mapa de la macrozona sur

Leaflet con `web/static/js/mapa.js`.
- Polígono de La Araucanía con relleno y borde fuertes, y etiqueta.
- Biobío, Los Ríos y Los Lagos solo con contorno tenue y etiqueta. Esta definición de macrozona es un supuesto del equipo, porque el caso no la define: se declara en el informe. **[propuesta]**
- Contornos en un GeoJSON simplificado local en `web/static/geo/`, derivado de OpenStreetMap (licencia ODbL, con atribución). Menos de 200 KB. Se ven aunque no carguen los mosaicos.
- Marcadores por segmento (color y forma, no solo color), solo para clientes con segmento, y la base en Temuco. Así no se muestran los domicilios de las cuentas particulares de prueba. Camiones en ruta o con alerta, con los datos de `estado_flota`.
- Al tocar un cliente: nombre, segmento, comuna, nivel del embudo, enlace a su ficha.

### 8.3 Clientes frecuentes

Tabla con los 8 clientes con segmento de más pedidos en 90 días (se excluyen los cancelados): nombre, segmento, comuna, pedidos, último pedido, nivel. Filtro por segmento.

**Rótulo [propuesta].** Fijo y visible en toda la Torre: «Clientes ilustrativos: nombres públicos usados como ejemplo; ninguno es cliente confirmado de Cofrial». También una línea breve en la ficha del cliente, solo para los RUT de muestra y regionales. No se tocan `/crm/clientes/` ni Grafana.

### 8.4 Antes y ahora

Dos columnas.

**Antes (rótulo: «Reconstrucción ilustrativa, no son datos de Cofrial»).** Un registro estático de unas 6 líneas de un día de coordinación, con voces genéricas («Chofer CAM-12», «Bodega»), sin nombres de personas, donde se pierde un pedido y una ruptura de frío pasa inadvertida. Debajo:
- Mermas: 13,5 a 36 millones de pesos a la semana (Tablas 5 y 6 del informe).
- Tiempo: 300 viajes semanales × 15 min de coordinación = 75 horas a la semana. **Los 15 min son un supuesto nuevo**: se agrega a la Tabla 5.
- Entregas fallidas: «alta tasa según el caso; nadie la registra». No se inventa un porcentaje.

**Ahora (datos reales de la base).** Última lectura, alertas de 24 h, monto de pedidos en riesgo, entregas no concretadas con motivo registrado, interacciones registradas en el CRM. La frase de cierre no afirma ahorro: «La merma evitada se medirá con datos de Cofrial».

### 8.5 Embudo por niveles

Cinco fases con el vocabulario que trajo Eric. Dentro, las etapas reales de Cofrial. Cada una muestra cantidad y monto o pedidos, y cada cliente enlaza a su ficha o prospecto. **[propuesta]**

| Fase | Etapa de Cofrial | De dónde sale |
|---|---|---|
| Atracción | Prospecto | `etapa_pipeline` |
| Interés | Contactado | `etapa_pipeline` |
| Consideración | Propuesta enviada, Negociación | `etapa_pipeline` |
| Acción | Ganado sin pedido, Primer pedido | Cliente B2B con 0 o 1 pedido |
| Fidelización | Recompra, Fidelizado | Recompra: 2 o más pedidos. Fidelizado: 4 o más en 90 días |
| Aparte | En riesgo, Perdido | En riesgo: con pedidos, pero ninguno en 30 días. Perdido: `etapa_pipeline` |

- «En riesgo» tiene prioridad sobre Recompra, Fidelizado y Primer pedido.
- El nivel se **calcula, no se guarda**. Función única en `crm/servicios.py`, con los umbrales como constantes.
- Solo clientes B2B: los B2C compran solos, sin vendedor. Se muestra su cantidad en una línea aparte.
- Entran los B2B con segmento, con prospecto ganado o con pedidos. Quedan fuera las solicitudes por aprobar (`solicitudes_empresa`) y las cuentas de prueba sin actividad, como `felipe@cofrial.cl`. Un prospecto ganado en vivo aparece al instante. **[propuesta]**
- También se ve como chip en la ficha del cliente (`crm/cliente.html`).
- El embudo actual de `/crm/embudo/` y sus reglas RN-10 y RN-11 no cambian.

### 8.6 Front-Office y Back-Office

Dos columnas iguales, unidas por «Una sola base de datos»:
- Front-Office: E-commerce, CRM, IA.
- Back-Office: AWS, IoT, BI.

Cada componente muestra un dato vivo y un enlace a su pantalla. Debajo, **un pedido trazado de punta a punta**: el último no cancelado cuyo viaje ya salió (nunca `HIS-`; sí un `OC-REG-…`, porque su despacho y su telemetría son reales), con orden web → cliente en CRM → camión → hora de salida → última lectura del camión → alerta sí o no. Una compra aparece aquí cuando se despacha, no antes. Es la prueba concreta de que ambos lados comparten datos. Sin un pedido así, lo dice.

### 8.7 Cumplimiento de la rúbrica

Una fila por cada dimensión de `informe/00-pauta-y-rubrica.md`: exigencia, evidencia viva, estado y enlace.

| Dimensión | Evidencia en vivo | En verde solo si |
|---|---|---|
| D1 AWS | Motor y versión de la base, host terminado en `.rds.amazonaws.com` (sin mostrarlo completo), tiempo encendida, instancia EC2 | Consulta correcta y host de RDS |
| D2 E-commerce y CRM | Productos activos, último pedido por canal, prospectos abiertos | Hay productos y un pedido real de cada canal: ni cancelado, ni `HIS-`, ni sembrado por la carga (`REFERENCIAS_SEMBRADAS`) |
| D3 IoT | Última fila con los nombres exactos (`camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`, `alerta_ruptura_frio`), su antigüedad, camiones reportando en 2 min | Lectura de menos de 2 min, no forzada desde `/demo/` |
| D4 BI | Ventas por canal cruzadas con alertas de 7 días, con la ventana a la vista; Grafana responde desde el servidor | Grafana responde y hay al menos una venta real (ni `HIS-` ni sembrada por la carga) en la ventana; sin exigir alertas: que no haya rupturas también es un resultado válido |
| D5 IA | Última clasificación de IA (categoría, confianza, hora), proveedores configurados sin mostrar claves, `ANTHROPIC_API_KEY` vacía | Hay clasificación, hay un proveedor gratuito configurado y no hay IA de pago activa |

**Qué es una venta real.** `REFERENCIAS_SEMBRADAS` (`web/clientes/muestra.py`) es la lista exacta de `numero_oc` que crea la carga de demostración (`cargar_demo` y `regionales`); son valores exactos y no un prefijo, salvo `HIS-`, porque un cliente podría escribir una OC parecida. Quedan fuera de D2, D4 y `ventas_24h`.

Tres estados: **Verificado**, **Sin evidencia ahora** y **No se pudo comprobar**. Se distinguen con texto e ícono. Nada genera pedidos por sí solo, así que la Lectura dirá «sin ventas en 24 h» hasta que alguien compre; el guion mantiene la compra en vivo para ver el cambio. La defensa en vivo de D5 se anota como responsabilidad del equipo: la pantalla no la puede comprobar.

Instancia EC2: se intenta leer con IMDSv2 (timeout de 200 ms, resultado en caché). Si el contenedor no lo alcanza, usar una variable que escriba `provision.sh`; si tampoco existe, queda en «No se pudo comprobar», nunca en verde.

## 9. Datos nuevos

### Segmento **[propuesta]**

Tabla `segmento_cliente` (`segmento_id`, `nombre` único) con Hospital, Supermercado, Feria e Institucional, y FK anulable `cliente.segmento`. No se usa `giro`, que es texto libre para la factura. B2C y clientes sin asignar quedan nulos y se muestran como «Sin segmento». Sin cambios en formularios: se edita en `/admin/`. Migración y entrada en el diccionario (`04b-modelo-datos.md`).

### Clientes de muestra

Módulo `web/clientes/muestra.py`, igual que `regionales.py`: nombres públicos, direcciones y coordenadas fijas de OpenStreetMap, RUT y correos ficticios (`.test`), sin cuentas de acceso y sin vendedor, para no cambiar las carteras.

- Hospitales: los 10 ya sembrados; se les asigna segmento solo si está nulo.
- Supermercados: Jumbo, Unimarc, Lider y Santa Isabel en Temuco; Supermercados Eltit; Supermercados del Sur (ya existe, es ficticio).
- Ferias: Feria Pinto (Temuco).
- Institucionales: internados municipales de Temuco, Universidad de La Frontera.
- Fuera de La Araucanía, para justificar la macrozona: Hospital Base Valdivia y Complejo Asistencial Víctor Ríos Ruiz (Los Ángeles). Solo con historial, sin despachos.

Si un nombre no se confirma en OpenStreetMap al implementar, se reemplaza por otro del mismo segmento y se deja nota.

Cuatro prospectos nuevos de estos segmentos, dos para cada vendedor actual (`vendedor` es obligatorio y una cuenta extra complicaría más la demo). Uno queda en «Perdido» con motivo, para que esa fila tenga un caso. Sus carteras de **clientes** no cambian; sus indicadores del embudo sí suben, y se comprueba que las pruebas lo toleren. **[propuesta]**

### Historial de pedidos

**Quiénes lo reciben [propuesta].** Solo los clientes nuevos de muestra y los hospitales sin cuenta ni vendedor. Quedan fuera Hospital Regional de Temuco, Supermercados del Sur, Angol, Villarrica y Pucón: tienen vendedor o cuenta de acceso, y el historial cambiaría los «Mis pedidos» y las fichas que se usan en el guion. Su nivel sale de sus pedidos reales.

Unos 120 pedidos como máximo, repartidos en los últimos 90 días y hasta hace al menos 24 h, con referencia `HIS-…` para identificarlos y no duplicarlos. Deben producir clientes en cada nivel, incluido «En riesgo».

- Estado final «Entregada», sin despacho, por eso no cruzan con alertas.
- Se insertan directo con líneas al precio de la lista, **sin descontar stock**. No pasan por `pedidos.agregar`.
- Con factura pagada, para no aparecer en «sin facturar» ni en «por cobrar». No se agregan filtros al código de cobranza.
- `creada_en` en el pasado se fija con `update`, porque es `auto_now_add`.
- Grafana los ve fuera de su ventana por defecto (6 h), así que no alteran lo que se muestra de entrada.

## 10. Rendimiento

`crm.servicios.indicadores` recorre las órdenes en Python, una consulta por total. **No se usa en el pulso.** El pulso agrega con SQL sobre `v_orden_total`, igual que Grafana. Medir que `/crm/` no se degrade con el historial; si lo hace, reducir la cantidad de pedidos antes de tocar esa función.

## 11. Comprobación

- Pruebas: permisos por rol (`tests_rutas`, `tests_403_por_rol`, `tests_navegacion`), reglas de nivel en cada límite, estados de rúbrica incluyendo simulador caído y lectura forzada, idempotencia de la siembra, cobranza y stock sin cambios tras sembrar. Ver [[cofrial-correr-tests]] en la memoria.
- Navegador con la cuenta de gerencia: 1440 px y 375 px, tema claro y oscuro, mosaicos bloqueados, y detener el simulador para ver el cambio de estado.
- Agregar la Torre a `aws/verificar.py`.
- En AWS, solo con el visto bueno de Eric: despliegue, carga forzada y `verificar.py`. Debe quedar listo antes del miércoles 11-nov, para ensayar.

## 12. Alcance por prioridad y vuelta atrás **[propuesta]**

Si falta tiempo, se recorta desde abajo:

1. **Imprescindible:** acceso, rúbrica (8.7), Lectura (8.1), mapa (8.2).
2. **Importante:** embudo (8.5), Antes y ahora (8.4), clientes (8.3), con segmento e historial.
3. **Prescindible:** pedido trazado (8.6, se conservan las dos columnas) y línea o chip en la ficha.

Vuelta atrás:
- La migración solo agrega una tabla y una columna anulable, así que el código anterior sigue funcionando sobre la base migrada.
- Comando `limpiar_muestra`, probado en local, que borra solo pedidos `HIS-…`, sus facturas y líneas, clientes de muestra y prospectos nuevos.
- Antes de la carga en AWS, intentar un snapshot de RDS; si el laboratorio no lo permite, queda solo el comando.
- `provision.sh` clona `main` por defecto: fusionar a `main` afecta a cualquier otra sesión que despliegue, así que se coordina o se usa `RAMA` para esta rama.
- Punto de decisión: si el miércoles 11-nov a las 18:00 `verificar.py` no pasa completo en AWS, se revierte a la versión anterior y la defensa sigue el guion actual.

## 13. Queda a criterio de quien implemente

Disposición visual y componentes reutilizados de `kpi-card`, `chip` y `tarjeta-ui`; redacción final del registro «Antes» y de las reglas de la Lectura; simplificación del GeoJSON; reparto exacto del historial.
