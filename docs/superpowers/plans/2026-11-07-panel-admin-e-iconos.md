# Panel del administrador sin Django e íconos en el CRM: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el administrador opere toda la app desde `/operacion/`, sin enlaces a `/admin/`, con un CRM de 5 entradas e íconos de `react-icons`.

**Architecture:** Un registro declarativo (`operacion/tablas.py`) alimenta una lista y un formulario comunes para las tablas simples. Productos, Órdenes, Usuarios y Sistema tienen pantalla propia. Las reglas viven en servicios sin HTTP; las vistas solo piden y muestran. Los íconos se generan una vez desde `react-icons` a un JSON versionado que pinta una etiqueta de plantilla.

**Tech Stack:** Django 6.1 con plantillas, PostgreSQL 16, Docker; Node solo en desarrollo, para generar íconos.

**Spec:** `docs/superpowers/specs/2026-11-07-panel-admin-e-iconos-design.md`

## Global Constraints
- No tocar `informe/`.
- `/admin/` queda sin enlaces, con la ruta activa. Sus pruebas de seguridad no se eliminan.
- Sin migraciones nuevas: `makemigrations --check` debe seguir sin cambios.
- Todas las vistas nuevas usan `solo_admin`; las que modifican datos usan `@require_POST` salvo los formularios GET/POST.
- Las órdenes cambian de estado solo con `pedidos.servicios.avanzar` y `cancelar`.
- Sin React en la app y sin Node en la imagen de Docker.
- Las URL actuales del CRM no cambian. Textos en español, sin emojis.
- Toda ruta nueva se agrega a la tabla de `web/cofrial/tests_rutas.py` (anónimo `L`, roles 403, admin 200).
- Commits: solo si el usuario los autoriza. Sin autorización, cada tarea termina con pruebas en verde y sin commit.

## Cómo correr las pruebas
Una vez, crear `.env` (ignorado) con `COMPOSE_PROJECT_NAME=cofrial-panel`, `WEB_PUERTO=8071`, `DB_PUERTO=5501`, `DB_PASSWORD`, `DJANGO_SECRET_KEY` y `DEMO_PASSWORD` de prueba. Luego:

```bash
docker build -t cofrial-panel-web ./web
docker compose up -d db
docker compose run --rm -v "$PWD/web:/app" -e DEMO_PASSWORD= -e ADMIN_PASSWORD= web python manage.py test <módulo> --noinput
```

En adelante, `PRUEBA <módulo>` significa ese último comando.

## Review Focus
1. Editar un producto mientras se vende: el formulario nunca escribe `stock_disponible`, así que la venta no se pisa.
2. Borrar una fila usada por otras (`ProtectedError`): mensaje claro y la fila sigue, nunca un 500.
3. Valores repetidos (SKU, patente, nombre, RUT con otro formato): error en el campo, nunca un 500.
4. Precios inválidos (negativo, texto, mayor a `ENTERO_MAXIMO`): error en el campo y no se guarda ningún precio de ese envío.
5. URL manipuladas: tabla inexistente o `pk` inexistente dan 404; `CAM-01` funciona como `pk` de texto, y un POST a una acción bloqueada (crear, borrar, editar Estados de orden) responde 403 aunque el botón no se muestre.

---

### Task 1: Arranque que respeta lo editado

**Files:**
- Modify: `web/catalogo/management/commands/cargar_demo.py`, `docker-compose.yml`, `aws/docker-compose.web.yml`, `aws/README.md`, `.env.example`
- Test: `web/catalogo/tests.py`

**Interfaces:**
- Produces: `cargar_demo --solo-primera-vez` y la variable `FORZAR_CARGA_DEMO`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_solo_primera_vez_no_deshace_lo_editado`: tras `cargar_demo`, renombrar «Contactado» a otro nombre con `update()`, borrar un `PrecioProducto`, llamar `cargar_demo --solo-primera-vez`; no hay error, el nombre sigue cambiado y el precio sigue borrado.
  - `test_solo_primera_vez_carga_una_base_vacia`: con `Producto.objects.count() == 0`, la opción carga y `Producto.objects.count() == 20`.
  - `test_forzar_ignora_la_opcion`: con `FORZAR_CARGA_DEMO=1` en el entorno, un `PrecioProducto` borrado vuelve.
- [ ] **Step 2: `PRUEBA catalogo` debe fallar** por opción desconocida.
- [ ] **Step 3: Implementar.** Agregar `add_arguments` con `--solo-primera-vez`. Al inicio de `handle`: si la opción está, `FORZAR_CARGA_DEMO != "1"` y `Producto.objects.exists()`, escribir «Datos de demostración ya cargados: no se tocan.» y volver.
- [ ] **Step 4: Usar la opción** en el `command` de web de ambos compose, pasar `FORZAR_CARGA_DEMO: ${FORZAR_CARGA_DEMO:-0}` al servicio web, y documentar la variable en `.env.example` y `aws/README.md`, con la advertencia de usarla antes de editar datos.
- [ ] **Step 5: `PRUEBA catalogo` debe pasar.**

### Task 2: Íconos y fuera Django de la vista

**Files:**
- Create: `web/herramientas/iconos/package.json`, `web/herramientas/iconos/generar.mjs`, `web/catalogo/iconos.json`, `web/catalogo/templatetags/iconos.py` (van en `catalogo` porque `cofrial` no está en `INSTALLED_APPS`)
- Modify: `web/templates/base.html:27-43`, `web/templates/operacion/base.html`, `web/templates/operacion/indice.html`, `web/static/css/cofrial.css`, `web/.dockerignore`, `web/cofrial/contexto.py`
- Test: `web/cofrial/tests_navegacion.py`, `web/cofrial/tests_rutas.py:236-253,276`, `web/catalogo/tests_seguridad_avisos.py:45-49`

**Interfaces:**
- Produces: `{% load iconos %}{% icono "nombre" %}` y `{% icono "nombre" "clase" %}`. Pinta `<svg class="ico clase" viewBox="0 0 24 24" aria-hidden="true">…</svg>`. Un nombre desconocido lanza `KeyError` con `DEBUG` y en pruebas no pasa inadvertido.
- Nombres disponibles: `inicio catalogo carrito pedidos soporte camion crm alerta-frio bi demo operacion panel ventas clientes atencion embudo demanda solicitudes cobranza requerimientos ia usuarios productos stock ordenes datos sistema agregar editar borrar buscar activar desactivar avanzar cancelar volver`.

- [ ] **Step 1: Generar.** `package.json` fija `react-icons`, `react` y `react-dom` en versión exacta (`react-icons` 5.7.0). `generar.mjs` recorre un mapa nombre → ícono de `react-icons/lu`, renderiza con `renderToStaticMarkup` y guarda solo el interior del SVG en `iconos.json`. Excluir la carpeta `herramientas/iconos` de la imagen en `.dockerignore`.
- [ ] **Step 2: Escribir las pruebas que fallan**
  - `test_icono_pinta_svg_oculto_al_lector`: el resultado contiene `aria-hidden="true"` y `<svg`.
  - `test_todos_los_iconos_tienen_contenido`: cada valor de `iconos.json` no está vacío.
  - `test_ninguna_pantalla_enlaza_a_django`: como admin, `/crm/`, `/flota/`, `/operacion/` no contienen `href="/admin/`.
  - Invertir las pruebas existentes que exigían `href="/admin/"` para el admin. `/admin/` debe seguir respondiendo 200 al admin.
- [ ] **Step 3: `PRUEBA cofrial catalogo.tests_seguridad_avisos` debe fallar.**
- [ ] **Step 4: Implementar** la etiqueta con `mark_safe` sobre contenido del JSON, cargado una vez. Reemplazar los SVG del menú lateral. Quitar la línea de `menu.admin` en `base.html`, su clave en `cofrial/contexto.py` y la tarjeta de `indice.html`. La clase `.ico` usa el mismo trazo que `.nav svg`.
- [ ] **Step 5: `PRUEBA cofrial catalogo.tests_seguridad_avisos` debe pasar.**

### Task 3: CRM de 5 entradas

**Files:**
- Create: `web/templates/crm/_nav.html`
- Modify: `web/templates/crm/base.html`, `web/static/css/cofrial.css`, `web/static/js/nav-slide.js` solo si deja de funcionar con la segunda fila
- Test: `web/crm/tests.py`

**Interfaces:**
- Consumes: `{% icono %}` de la Task 2.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_comercial_ve_cinco_entradas`: en `/crm/` hay exactamente 5 enlaces en `nav.subnav[aria-label="Secciones del CRM"]`, sin contar Panel BI.
  - `test_subpestanas_solo_dentro_del_grupo`: `/crm/cobranza/` muestra `/crm/solicitudes/` en la segunda fila; `/crm/` no muestra `/crm/cobranza/` en ninguna fila de navegación.
  - `test_grupo_activo`: en `/crm/prospectos/<pk>/` queda activo Ventas y en `/crm/ia/` queda activo Atención.
  - `test_despachador_solo_ve_lo_suyo`: ve Demanda en espera y Alertas de frío, sin grupos.
  - `test_contador_de_solicitudes_en_clientes`: con una solicitud pendiente, la entrada Clientes muestra el contador.
  - `test_sin_chip_de_rol`: `Rol:` no aparece.
- [ ] **Step 2: `PRUEBA crm` debe fallar.**
- [ ] **Step 3: Implementar.** Destinos: Panel `/crm/`; Ventas `/crm/embudo/`; Clientes `/crm/clientes/`; Atención `/crm/requerimientos/`; Alertas de frío `/crm/alertas/`. Segunda fila con clase `subnav-2`, no fija al hacer scroll. Grupos por ruta: Ventas `/crm/embudo`, `/crm/prospectos`, `/crm/demanda`; Clientes `/crm/clientes`, `/crm/solicitudes`, `/crm/cobranza`; Atención `/crm/requerimientos`, `/crm/ia`. Mantener `aria-current="page"` y Panel BI.
- [ ] **Step 4: `PRUEBA crm cofrial` debe pasar.**

### Task 4: Panel común y tablas simples

**Files:**
- Create: `web/operacion/tablas.py`, `web/operacion/datos.py`, `web/templates/operacion/datos.html`, `web/templates/operacion/tabla.html`, `web/templates/operacion/fila.html`
- Modify: `web/operacion/urls.py`, `web/templates/operacion/base.html`, `web/templates/operacion/indice.html`
- Test: `web/operacion/tests_datos.py`

**Interfaces:**
- Produces, en `tablas.py`: `@dataclass Tabla(slug, titulo, grupo, icono, modelo, columnas, busqueda, campos, crear=True, editar=True, borrar=True, ayuda="", validar=None, protegida=None)`.
  - `validar(form, objeto) -> None` agrega errores al formulario.
  - `protegida(objeto) -> str` devuelve el motivo que impide borrar, o `""`.
  - `TABLAS: dict[str, Tabla]` y `formulario_de(tabla) -> type[ModelForm]`.
- Produces, rutas: `/operacion/datos/`, `/operacion/datos/<slug>/`, `.../nuevo/`, `.../<str:pk>/`, `.../<str:pk>/borrar/`.

- [ ] **Step 1: Escribir las pruebas que fallan**, con estas tablas: `categorias`, `rangos`, `listas`, `regiones`, `comunas`, `camiones`, `tipos-cliente`, `estados-orden`.
  - Permisos: anónimo a ingresar; vendedor, gerencia, despachador y cliente 403; admin 200.
  - `test_crear_editar_y_borrar_categoria`.
  - `test_borrar_categoria_con_productos_avisa`: 302, mensaje, la fila sigue.
  - `test_nombre_repetido_es_error_de_campo`.
  - `test_slug_y_pk_inexistentes_dan_404`.
  - `test_camion_se_edita_por_su_codigo`: `/operacion/datos/camiones/CAM-01/` da 200 y `camion_id` no se puede cambiar.
  - `test_camion_nuevo_avisa_del_simulador`: la ayuda menciona `CAM-01` y `CAM-50`.
  - `test_rango_no_cambia_de_nombre`: un POST con otro nombre deja el nombre intacto.
  - `test_tipo_cliente_no_cambia_de_codigo`: solo cambian lista y días de crédito.
  - `test_estados_de_orden_son_solo_lectura`: GET de la lista 200; POST a nuevo, editar y borrar 403.
- [ ] **Step 2: `PRUEBA operacion.tests_datos` debe fallar.**
- [ ] **Step 3: Implementar** las vistas en `datos.py` con `FILAS_MAXIMAS`, búsqueda por `busqueda`, `ProtectedError` y `RestrictedError` convertidos en `messages.error`, y 403 cuando la tabla no permite la acción. Reutilizar `_campo.html`. Agregar Datos a la navegación de Operación con su ícono y a `tests_rutas.py`.
- [ ] **Step 4: `PRUEBA operacion cofrial.tests_rutas` debe pasar.**

### Task 5: Tablas con reglas de negocio

**Files:**
- Modify: `web/operacion/tablas.py`
- Test: `web/operacion/tests_datos.py`

**Interfaces:**
- Consumes: `Tabla.validar`, `Tabla.protegida`.
- Produces: tablas `etapas`, `categorias-requerimiento`, `prospectos`, `clientes`, `direcciones`, `vendedores`; constantes `ETAPAS_FIJAS = {"Contactado", "Propuesta enviada"}` y `CATEGORIAS_FIJAS = {"Reclamo por temperatura", "Problema en la entrega"}`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_etapas_fijas_no_se_renombran_ni_borran` y `test_categorias_fijas_no_se_renombran_ni_borran`.
  - `test_no_se_quita_la_unica_etapa_ganada`: ni borrándola ni desmarcando `es_ganada`. Igual con la única final perdida.
  - `test_prospecto_no_cambia_de_etapa`: el formulario no tiene el campo `etapa`.
  - `test_prospecto_sin_correo_ni_telefono_es_error`: no da 500.
  - `test_cliente_rut_invalido_es_error` y `test_cliente_rut_repetido_con_otro_formato_es_error`.
  - `test_solicitud_pendiente_no_se_edita`: POST deja el cliente igual y avisa que va en Solicitudes.
  - `test_no_se_quita_vendedor_si_lo_vuelve_solicitud`: B2B con cuenta inactiva y vendedor, quitar el vendedor es error.
  - `test_direccion_con_orden_en_curso_no_se_edita`.
  - `test_cambiar_calle_borra_coordenadas`: `lat` y `long` quedan en `None`.
  - `test_una_sola_direccion_principal`: marcar otra como principal desmarca la anterior, sin error de base.
  - `test_vendedor_solo_edita_nombre_y_telefono`.
- [ ] **Step 2: `PRUEBA operacion.tests_datos` debe fallar.**
- [ ] **Step 3: Implementar** las seis tablas. El RUT se valida con `rut.es_valido` y se guarda con `rut.formatear`. Orden en curso significa `estado_orden__es_final=False`.
- [ ] **Step 4: `PRUEBA operacion.tests_datos` debe pasar.**

### Task 6: Productos y precios

**Files:**
- Create: `web/templates/operacion/productos.html`, `web/templates/operacion/producto.html`
- Modify: `web/operacion/forms.py`, `web/operacion/servicios.py`, `web/operacion/vistas.py`, `web/operacion/urls.py`, `web/templates/operacion/base.html`
- Test: `web/operacion/tests_productos.py`

**Interfaces:**
- Produces: `ProductoForm(ModelForm)` con un campo `precio_<lista_precio_id>` por lista, y `servicios.guardar_producto(form) -> Producto`. Rutas: `/operacion/productos/`, `.../nuevo/`, `.../<int:pk>/`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_crear_producto_con_precios_y_stock_inicial`.
  - `test_editar_no_toca_el_stock`: cambiar `stock_disponible` con `update()` después de abrir el formulario, enviar; el stock no cambia, aunque el POST traiga `stock_disponible=0`.
  - `test_precio_vacio_quita_de_la_lista`.
  - `test_precio_invalido_no_guarda_nada`: `-1`, `abc`, `2147483648` dan error de campo y ningún precio cambia.
  - `test_sku_repetido_es_error`.
  - `test_producto_nuevo_aparece_en_catalogo`: con precio B2C, `/catalogo/` lo muestra sin error, aunque no tenga foto.
  - `test_desactivar_lo_oculta_del_catalogo`.
  - `test_no_hay_ruta_de_borrar`.
- [ ] **Step 2: `PRUEBA operacion.tests_productos` debe fallar.**
- [ ] **Step 3: Implementar.** Stock inicial solo en el formulario de creación, entero entre 0 y `REPOSICION_MAXIMA`. `guardar_producto` usa `transaction.atomic`. Al editar, guardar con `update_fields` que excluya `stock_disponible`. El precio mínimo es 1.
- [ ] **Step 4: `PRUEBA operacion cofrial.tests_rutas` debe pasar**, con las rutas agregadas a `tests_rutas.py`.

### Task 7: Órdenes

**Files:**
- Create: `web/templates/operacion/ordenes.html`
- Modify: `web/operacion/servicios.py`, `web/operacion/vistas.py`, `web/operacion/urls.py`, `web/templates/operacion/base.html`
- Test: `web/operacion/tests_ordenes.py`

**Interfaces:**
- Produces: `servicios.ordenes(q="", estado="")` y `servicios.puede_avanzar(orden) -> bool`. Rutas: `/operacion/ordenes/`, `.../<int:pk>/avanzar/`, `.../<int:pk>/cancelar/`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_avanzar_de_recibida_a_confirmada`.
  - `test_boton_avanzar_por_estado`: `puede_avanzar` es verdadero en «Recibida» y «Confirmada», en «En preparación» solo con despacho, y falso en «Despachada», «Camión en la puerta» y estados finales.
  - `test_post_a_orden_en_viaje_no_avanza`: la orden no cambia y hay mensaje.
  - `test_cancelar_repone_stock`.
  - `test_cancelar_fuera_de_plazo_avisa`: `ErrorDeNegocio` se muestra como mensaje.
  - `test_filtro_y_busqueda`, incluido un `estado` inexistente, que se ignora.
- [ ] **Step 2: `PRUEBA operacion.tests_ordenes` debe fallar.**
- [ ] **Step 3: Implementar.** La vista de avanzar revisa `puede_avanzar` antes de llamar a `pedidos.servicios.avanzar`. Cancelar usa `como="vendedor"`.
- [ ] **Step 4: `PRUEBA operacion cofrial.tests_rutas` debe pasar.**

### Task 8: Activar y desactivar cuentas

**Files:**
- Modify: `web/operacion/servicios.py`, `web/operacion/vistas.py`, `web/operacion/urls.py`, `web/templates/operacion/cuentas.html`
- Test: `web/operacion/tests_cuentas_estado.py`

**Interfaces:**
- Produces: `servicios.cambiar_activa(objetivo, activa, quien) -> User`, que lanza `ErrorOperacion` con el motivo. Ruta POST: `/operacion/cuentas/<int:pk>/activa/`, campo `activa` con `1` o `0`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `test_no_se_desactiva_la_propia_cuenta` y `test_no_se_desactiva_el_ultimo_administrador`.
  - `test_cuenta_desactivada_no_ingresa` y `test_sesion_abierta_se_corta`.
  - `test_no_se_activa_una_solicitud_pendiente`.
  - `test_no_se_desactiva_b2b_sin_vendedor`: `solicitudes_empresa()` no cambia.
  - `test_vendedor_con_cartera_no_se_desactiva`: con clientes o prospectos abiertos, el mensaje pide reasignar.
  - `test_vendedor_sin_cartera_cambia_ambos_interruptores`: `is_active` y `Vendedor.activo` quedan iguales, al desactivar y al activar.
- [ ] **Step 2: `PRUEBA operacion.tests_cuentas_estado` debe fallar.**
- [ ] **Step 3: Implementar** con `transaction.atomic`. Prospecto abierto significa `etapa__es_final=False`.
- [ ] **Step 4: `PRUEBA operacion cofrial.tests_rutas` debe pasar.**

### Task 9: Sistema

**Files:**
- Create: `web/templates/operacion/sistema.html`
- Modify: `web/operacion/servicios.py`, `web/operacion/vistas.py`, `web/operacion/urls.py`, `web/templates/operacion/base.html`, `web/flota/management/commands/podar_telemetria.py`
- Test: `web/operacion/tests_sistema.py`

**Interfaces:**
- Consumes: `crm.ia.clasificar(asunto, texto, categorias)`, `lecturas_prescindibles(corte)`.
- Produces: `servicios.probar_ia() -> dict` con `ok`, `categoria`, `confianza`, `modelo`, `error`; `servicios.podar(dias, tope=PODA_TOPE) -> (borradas, faltan)`, con `PODA_TOPE = 50_000`. Rutas: `/operacion/sistema/`, `.../ia/`, `.../podar/`.

- [ ] **Step 1: Escribir las pruebas que fallan**, con la IA simulada.
  - `test_probar_ia_muestra_categoria_y_modelo` y `test_ia_caida_muestra_la_causa`: 200, sin 500.
  - `test_pantalla_cuenta_sin_borrar`: el GET muestra cuántas lecturas se borrarían y no borra.
  - `test_podar_respeta_alertas_y_forzadas`.
  - `test_podar_con_tope_dice_cuanto_falta`.
  - `test_comando_sigue_funcionando`: `podar_telemetria --simular` da el mismo conteo.
- [ ] **Step 2: `PRUEBA operacion.tests_sistema flota.tests_retencion` debe fallar.**
- [ ] **Step 3: Implementar.** Mover `lecturas_prescindibles` a `flota/servicios.py` e importarla desde el comando. `dias` usa `RETENCION_TELEMETRIA_DIAS` o 7. Podar borra por lotes de 5.000 hasta `tope`.
- [ ] **Step 4: `PRUEBA operacion flota cofrial.tests_rutas` debe pasar.**

### Task 10: Verificación final

**Files:**
- Modify: `docs/credenciales-y-cuentas.md`, `docs/cuentas-y-permisos.md`, `docs/decisiones.md` (no `informe/`)

- [ ] **Step 1: Suite completa.** `PRUEBA` sin módulo y `python manage.py makemigrations --check`. Esperado: todo en verde y sin cambios.
- [ ] **Step 2: Reinicio real.** Levantar el stack aislado, entrar en `http://panel.localhost:8071/`, renombrar una etapa, quitar un precio y borrar una comuna sin uso. Ejecutar `docker compose restart web`. Esperado: `/salud/` responde 200 y los tres cambios siguen.
- [ ] **Step 3: Revisión en navegador.** Como admin y como despachador: CRM y cada pantalla de Operación, en escritorio y móvil, claro y oscuro. Sin desborde horizontal ni errores de consola.
- [ ] **Step 4: Actualizar los documentos** para que indiquen `/operacion/` en vez de `/admin/`, y registrar las decisiones.
