# Panel del administrador sin Django e íconos en el CRM

Fecha: 7-nov-2026. Rama: `claude/admin-app-react-icons-crm-557ff9`. Defensa: 12-nov-2026.

## Intención
Cofrial es una aplicación de negocio: el administrador debe poder operarla entera desde sus propias pantallas, sin abrir el admin de Django ni correr comandos. En AWS no hay SSH, así que lo que hoy exige `manage.py` no se puede hacer. Además, el CRM se siente recargado: 9 pestañas de puro texto.

## Objetivos
1. Todo lo que hoy solo se hace en `/admin/` o por comando, y que una persona necesita hacer, queda en `/operacion/`.
2. Ningún enlace de la app lleva a `/admin/`.
3. El CRM pasa de 9 pestañas a 5 entradas con ícono y nombre.
4. Los íconos de la navegación y del panel vienen de `react-icons`.

## Fuera de alcance
- El informe: ya se envió, no se toca. Tampoco `informe/*.md`.
- Apagar `/admin/`: decisión del usuario. Queda sin enlaces y la ruta sigue activa como respaldo hasta después de la defensa.
- Editar a mano datos transaccionales o de auditoría: `Telemetria`, `Despacho`, `Carrito`, `Documento`, `Pago`. Se generan por el flujo (simulador, flota, tienda, Cobranza). Editarlos a mano rompe la trazabilidad, así que el panel no lo ofrece.
- Cambiar el rol de una cuenta o renombrar su usuario.
- Rediseñar la tienda pública o las ilustraciones.
- Desplegar en AWS: se hace aparte, cuando el usuario lo pida.

## Lo que sería un fracaso aunque funcione
- Que una edición desde el panel rompa pedidos, el embudo o el simulador.
- Que una cuenta que no sea administradora entre al panel.
- Que el panel deje sin administradores activos o permita pisar el stock vendido.
- Que aparezca React o un paso de compilación en la EC2.

## Restricciones
- Django 6.1 con plantillas, sin React en la app ni `package.json` en la imagen de Docker. Sin migraciones nuevas.
- Solo el rol admin: todas las vistas nuevas usan `solo_admin`.
- Reglas de negocio en servicios, sin HTTP (patrón de `operacion/servicios.py`). Las órdenes pasan por `pedidos.servicios.avanzar` y `cancelar`; nada cambia su estado directamente.
- Las URL actuales del CRM no cambian.
- Todo en español, sin emojis.

## Enfoques considerados
| Enfoque | A favor | En contra |
|---|---|---|
| **Panel común (elegido por el usuario)** | Una lista y un formulario para todas las tablas, poco código, aspecto uniforme, menos riesgo antes del 12-nov | Las tablas simples quedan sencillas |
| Una pantalla a medida por tabla | Cada una ajustada a su uso | Unas 12 pantallas, más pruebas, sin funciones nuevas |
| Solo lo diario | Lo más rápido | El resto seguiría exigiendo `/admin/`: no cumple «todo desde el admin» |

Íconos (decisión de Claude, informada al usuario): tomar los SVG del paquete `react-icons`, sin React en la app. Instalar React y un empaquetador solo para íconos agregaría un paso de compilación a una app de plantillas.

## Diseño

### 1. Panel común: `/operacion/datos/`
Un registro en `operacion/tablas.py` describe cada tabla: modelo, título, ícono, columnas, búsqueda, campos editables y permisos (crear, borrar). Las vistas genéricas son índice, lista, nuevo, editar y borrar (solo POST).

| Grupo | Tabla | Crear | Editar | Borrar | Límite |
|---|---|---|---|---|---|
| Catálogo | Categorías, Rangos de temperatura, Listas de precio | Sí | Sí | Sí | Rangos: el nombre no se edita (flota lo compara) |
| Flota | Camiones | Sí | Sí | Sí | Aviso en el formulario: el simulador solo mueve `CAM-01` a `CAM-50` |
| Clientes | Clientes | No | Sí | No | Se crean en Usuarios o al ganar un prospecto. RUT validado con `clientes/rut.py`. Una solicitud de empresa pendiente no se edita aquí; a un B2B con cuenta no se le quita el vendedor si eso lo convierte en solicitud |
| Clientes | Direcciones | No | Sí | Sí | Se crean en la ficha del CRM. Una sola principal por cliente. Bloqueada si tiene órdenes en curso. Al cambiar calle o comuna se borran lat/long para volver a ubicarla |
| Clientes | Vendedores | No | Nombre y teléfono | No | Se crean en Usuarios; se activan y desactivan solo desde Usuarios |
| Clientes | Tipos de cliente | No | Lista de precios y días de crédito | No | El código B2B/B2C no se edita |
| Territorio | Regiones, Comunas | Sí | Sí | Sí | |
| CRM | Prospectos | No | Datos de contacto, monto, vendedor, origen | No | La etapa no se edita: se mueve en el embudo, que aplica RN-11 |
| CRM | Etapas del embudo | Sí | Sí | Sí | Siempre debe quedar una etapa ganada y una final perdida. «Contactado» y «Propuesta enviada» no se renombran ni se borran |
| CRM | Categorías de requerimiento | Sí | Sí | Sí | «Reclamo por temperatura» y «Problema en la entrega» no se renombran ni se borran |
| Pedidos | Estados de orden | No | No | No | Solo lectura: el código y el simulador los buscan por nombre |

Si un borrado choca con datos relacionados (`ProtectedError`), se muestra un mensaje claro y no pasa nada.

### 2. Productos: `/operacion/productos/`
Pantalla propia: lista con búsqueda, nuevo y editar, con SKU, nombre, descripción, categoría, unidad y activo, más un precio por cada lista. Dejar un precio vacío quita el producto de esa lista. El stock inicial solo se pide al crear; después se usa Reponer stock, que suma sin pisar ventas. Los productos no se borran: se desactivan.

### 3. Órdenes: `/operacion/ordenes/`
Lista con filtro por estado y búsqueda, con botones Avanzar y Cancelar que llaman a `pedidos.servicios`. Los errores de negocio se muestran como mensaje. Avanzar aparece solo en «Recibida» y «Confirmada», y en «En preparación» si la orden ya tiene despacho. No aparece con la orden en viaje: saltaría la confirmación del cliente y el simulador perdería la parada.

### 4. Usuarios
En `/operacion/cuentas/`, botón Activar o Desactivar. No se puede desactivar la propia cuenta ni al último administrador activo.

Una solicitud de empresa se reconoce por ser cliente B2B, sin vendedor y con cuenta inactiva, así que el botón debe respetar esa cola:
- No se activa una solicitud pendiente: se aprueba en CRM, Solicitudes, que asigna vendedor.
- No se desactiva un B2B sin vendedor: aparecería como solicitud y «Rechazar» borraría al cliente. Primero se le asigna vendedor.

Vendedores: el botón cambia `User.is_active` y `Vendedor.activo` juntos. No se desactiva a quien tenga clientes o prospectos abiertos; el mensaje pide reasignarlos en Datos.

### 5. Sistema: `/operacion/sistema/`
- **Probar IA:** clasifica un texto de ejemplo y muestra categoría, confianza y modelo, o la causa del error.
- **Podar telemetría:** primero cuenta lo que se borraría y pide confirmar. Comparte la lógica con `podar_telemetria`. Debe terminar dentro del límite de 60 s de gunicorn; si no alcanza, borra hasta un tope por clic y dice cuánto falta.

Quedan como comando, a propósito: `evaluar_ia`, `evaluar_asistente` y `evaluar_desglose` (mediciones de decenas de llamadas que superan el límite de 60 s), `cambiar_clave_demo` (reemplazado en la práctica por «Asignar clave»), `cargar_demo` y `preparar_bi` (corren solos al arrancar), y las herramientas de imágenes.

### 6. Quitar Django de la vista
Eliminar el enlace del menú lateral (`templates/base.html`) y la tarjeta de `templates/operacion/indice.html`. Las pruebas que exigían `href="/admin/"` pasan a exigir que no esté. Las pruebas de seguridad de la ruta `/admin/` se mantienen. La navegación de Operación queda: Resumen, Usuarios, Productos, Reponer stock, Órdenes, Datos, Sistema.

### 7. CRM: 5 entradas
Panel, Ventas (Embudo, Demanda en espera), Clientes (Clientes, Solicitudes, Cobranza), Atención (Requerimientos, IA) y Alertas de frío. Cada entrada lleva ícono y nombre. Una segunda fila, más chica, muestra las subpestañas solo dentro de un grupo. El contador de Solicitudes se ve también en Clientes.

El despachador sigue viendo solo Demanda en espera y Alertas de frío, sin grupos. Panel BI queda como enlace con ícono. El chip «Rol: ...» se quita porque el rol ya aparece en la tarjeta de usuario del menú lateral.

### 8. Íconos
`web/herramientas/iconos/` tiene un `package.json` con `react-icons` en versión fija y un script que escribe `web/cofrial/iconos.json`. Ese archivo se versiona; Docker y la EC2 no usan Node. La etiqueta `{% icono "nombre" %}` pinta el SVG en línea con `aria-hidden`. Se usa el juego Lucide (`react-icons/lu`), de trazo, que calza con el CSS actual. Se aplica al menú lateral, a las pestañas del CRM y de Operación, y a las acciones del panel. No se aplica a la tienda pública.

### 9. Datos de demostración y arranque (decidido por el usuario: los cambios quedan)
`cargar_demo` corre en cada arranque y busca por nombre, RUT o SKU. Sin cambios, lo editado en el panel choca con él: renombrar una etapa cargada impide que el sitio parta (`IntegrityError` antes de gunicorn), y lo borrado o renombrado vuelve o se duplica. El Learner Lab apaga las EC2 cada 4 horas, así que los reinicios son normales.

Decisión: los datos de demostración se cargan solo la primera vez y después manda lo que haga el administrador.
- `cargar_demo` recibe la opción `--solo-primera-vez`: si ya hay productos en la base, avisa en el registro y termina sin tocar nada. Los productos sirven de señal porque el panel no los borra y ninguna migración los crea.
- `docker-compose.yml` y `aws/docker-compose.web.yml` arrancan con esa opción. `preparar_bi` sigue corriendo siempre.
- El comando sin opción sigue igual, así las pruebas y la carga manual no cambian.
- `FORZAR_CARGA_DEMO=1` ignora la opción para un arranque. Sirve si RDS aún no tiene datos nuevos del repositorio, como el reparto regional. Se usa antes de editar datos en el panel, porque forzarla después puede chocar con lo editado.
- Se verifica con un reinicio real: editar datos, reiniciar la web, comprobar que el sitio parte y que lo editado sigue ahí.

## Pruebas
- Por cada ruta nueva: anónimo va a ingresar, los demás roles reciben 403, admin 200.
- Cada límite de la tabla, productos y precios, órdenes, activar cuentas y Sistema con la IA simulada.
- Suite completa en un stack aislado, y revisión en navegador con host propio, en escritorio y móvil, claro y oscuro.

## Lo que queda a criterio de quien construye
Nombres internos, paginación (seguir `FILAS_MAXIMAS`), ícono exacto de cada entrada y separar o no las vistas en más archivos.
