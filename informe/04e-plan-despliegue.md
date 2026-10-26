# Despliegue y verificación del sistema

## Estado y alcance

El equipo consultor registra una prueba integral en AWS Academy del 22-oct-2026. El código incorporado hasta el 25-oct-2026 amplía esa base con cincuenta camiones, asistente de tienda, cierre de viajes, OC diferida y separación de compras por temperatura. La presencia de estas funciones en el repositorio no se confunde con una nueva prueba de esa revisión en la nube.

**Tabla 1**
*Componentes implementados y comprobación de aceptación*

| Componente | Implementación | Comprobación |
|---|---|---|
| Red y persistencia | VPC con tres subredes, dos EC2 y RDS privada Single-AZ | Portal accesible; SQL solo desde grupos autorizados; estado RDS |
| E-commerce | Precios por perfil, stock transaccional, carrito, órdenes por rango y OC diferida | Compra B2B/B2C, dirección propia, stock, división de órdenes y posterior OC |
| CRM | Cartera, prospectos, interacciones, pedidos asistidos y requerimientos | Aislamiento por cartera, avance sin saltos, motivo de pérdida, creación de cliente y gestión de OC |
| IoT | Cinco contenedores, diez camiones cada uno | Cincuenta camiones con lectura reciente y seis campos correctos |
| BI | Grafana cada cinco segundos; usuario SQL de solo lectura | Cruce ventas-frío, filtros de camión y lecturas recientes |
| IA | Clasificación y asistente separados, proveedores configurables | Respuesta válida, acceso solo a pedidos propios y continuidad ante proveedor caído |
| Despacho | Camión activo y libre, compatibilidad térmica y cierre manual | Viaje creado; órdenes despachadas; llegada libera camión y entrega órdenes |

Nota. Elaboración propia. Se derivan los criterios de la pauta EVA2_3 y de las reglas implementadas, sin agregar exigencias de otra evaluación (INACAP Sede Temuco, 2026).

## Procedimiento reproducible

El entorno local se inicia con `docker-compose.yml`; AWS utiliza los compose separados de `aws/`. La EC2 web aplica las migraciones Django, carga datos ficticios de forma idempotente, prepara el usuario BI y arranca Gunicorn. La EC2 IoT inicia los cinco grupos de camiones. La instalación física se obtiene mediante migraciones y no ejecutando encima el SQL académico de referencia.

`provision.sh encender` recupera las instancias del laboratorio. `recrear-web` y `recrear-iot` reemplazan solo el nodo correspondiente; el segundo conserva web, RDS e IP elástica y produce una interrupción breve de telemetría. El procedimiento `destruir` elimina datos sin snapshot final; no forma parte del ensayo ordinario de recuperación.

## Evidencias de comprobación

**Tabla 2**
*Evidencias y límites de las verificaciones*

| Evidencia | Fecha o alcance | Qué permite concluir |
|---|---|---|
| Registro de prueba integral AWS | 22-oct-2026 | Funcionamiento de la revisión instalada entonces; no certifica automáticamente cambios posteriores |
| Clasificador con APIs reales | Registro histórico: veinte mensajes, veinte categorías correctas con respaldo | Resultado de esa muestra; no garantiza exactitud universal ni mide el chat |
| Pruebas Django | Resultado de la ejecución local consignado en el registro técnico de esta revisión | Comportamiento de reglas y rutas bajo datos de prueba; IA externa simulada en las pruebas correspondientes |
| Pruebas del simulador | Movimiento, paradas y velocidad compartida | Consistencia del movimiento sintético; no prueba sensores físicos |
| Pruebas de recreación AWS | Doble de CLI sin recursos reales | Selección del nodo correcto y sintaxis del script; no prueba un despliegue en la cuenta |
| Verificador de AWS | Script disponible, no ejecutado contra AWS en esta revisión | Procedimiento para revalidar compras, cincuenta camiones y consultas de Grafana |

Nota. Elaboración propia. Los resultados completos se conservan en `docs/revision-hito1-2026-10-25.md`.

## Recorrido de defensa

La demostración comienza con una compra institucional sin OC y un carrito con productos de dos rangos. Se muestran las órdenes resultantes, el stock y la OC pendiente en el CRM; luego se completa la referencia institucional. El vendedor registra una interacción y avanza un prospecto con las restricciones reales del embudo. El despachador selecciona camiones compatibles, crea el viaje y muestra el seguimiento con telemetría. Una ruptura del simulador o del modo de demostración se cruza con los pedidos afectados en CRM y Grafana. Finalmente se registra un requerimiento vinculado a una orden propia y se consulta al asistente, mostrando la continuidad del portal cuando la IA no está disponible. El cierre manual del viaje entrega las órdenes despachadas y libera el camión.

El modo de demostración es una herramienta administrativa separada: inserta lecturas `forzada`, dura como máximo 180 s y permite retirar solo esas lecturas. Las mediciones ordinarias siguen siendo generadas por los contenedores. En la defensa se identifica qué origen produjo la alerta.
