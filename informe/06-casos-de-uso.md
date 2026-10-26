# Casos de uso del ecosistema


## Formato

**Tabla 1**
*Formatos de casos de uso considerados*

| Formato | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| Diagrama de casos de uso UML + especificación breve | Muestra actores, límites del sistema y relaciones de un vistazo | La especificación completa es costosa | Adoptada. Diagrama general y especificación solo de los casos críticos |
| Historias de usuario | Rápidas, orientadas al valor | Sin vista global de actores | Complementaria. Se usan como tarjetas en Trello |

Nota. Elaboración propia.

## Actores

**Tabla 2**
*Actores del ecosistema*

| Actor | Tipo | Descripción |
|---|---|---|
| Cliente B2B | Primario | Hospital, supermercado, feria o institución con lista de precios institucional |
| Cliente B2C | Primario | Persona que compra a precio público |
| Vendedor | Primario | Gestiona su cartera y sus prospectos en el CRM |
| Despachador | Primario | Supervisa la flota y las alertas de frío |
| Gerencia | Primario | Consulta el dashboard BI |
| Simulador IoT | Sistema | Contenedores Docker que envían telemetría |
| Servicio de IA | Sistema externo | Clasifica requerimientos y responde consultas |

## Catálogo de casos de uso

**Tabla 3**
*Catálogo de casos de uso*

| ID | Caso de uso | Actor | Módulo | Prioridad | Rúbrica |
|---|---|---|---|---|---|
| CU-01 | Seleccionar perfil e iniciar sesión (B2B/B2C) | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-02 | Consultar el catálogo de refrigerados con precio según perfil | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-03 | Gestionar el carrito de compras | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-04 | Generar órdenes por rango de temperatura | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-05 | Seguir el estado del pedido | Cliente B2B, B2C | E-commerce | Extra | H2-D5 |
| CU-06 | Gestionar clientes | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-07 | Gestionar prospectos y avanzar etapas del pipeline | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-08 | Hacer seguimiento de pedidos web | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-09 | Registrar un requerimiento y clasificarlo con IA | Cliente, Servicio de IA | CRM / E-commerce | Obligatorio | H2-D5 |
| CU-10 | Enviar telemetría del camión | Simulador IoT | IoT | Obligatorio | H2-D3 |
| CU-11 | Detectar la ruptura de cadena de frío | Simulador IoT | IoT | Obligatorio | H2-D3 |
| CU-12 | Monitorear la flota y sus alertas | Despachador | Torre de control | Extra | H2-D4 |
| CU-13 | Consultar el dashboard de ventas y cadena de frío | Gerencia | BI | Obligatorio | H2-D4 |
| CU-14 | Consultar al asistente de tienda | Visitante o cliente autenticado | E-commerce e IA | Complementario | H2-D5 |

Nota. Elaboración propia. "Obligatorio" se refiere a lo que exige la pauta del Hito 2.

## Diagrama de casos de uso

El diagrama sigue la idea del modelo de casos de uso del Lenguaje Unificado de Modelado (UML) 2.5.1 (Object Management Group [OMG], 2017): actores, casos de uso y relaciones de inclusión. Se simplifica la notación gráfica para que los límites del sistema se lean por módulo.

**Figura 1**
*Diagrama de casos de uso del ecosistema Cofrial*

![Diagrama de casos de uso](img/casos-de-uso.png)

*Nota.* Elaboración propia, con notación simplificada. Verde: casos críticos con especificación. Las flechas punteadas indican que un caso incluye a otro (por ejemplo, generar una orden incluye gestionar el carrito). Los actores en amarillo son sistemas.

## Especificaciones de los casos críticos

Se especifican cuatro casos: los tres que la pauta hace más sensibles (orden, IA y ruptura de frío) y el pipeline comercial, que concentra la lógica del CRM. Las reglas citadas (RN-xx) están en `04c-canales-b2b-b2c.md` y `04d-crm.md`.

### CU-04 Generar una orden

**Tabla 4**
*Especificación del caso de uso CU-04*

| Elemento | Descripción |
|---|---|
| Actor principal | Cliente B2B o B2C. Durante la transición, el vendedor a nombre del cliente (RN-15) |
| Precondiciones | Sesión iniciada; carrito abierto con al menos una línea; el cliente tiene una dirección |
| Disparador | El cliente pulsa «Confirmar pedido» |
| Flujo normal | 1. El sistema valida que la dirección sea del cliente (RN-04) y, si es B2B y no trae número de orden de compra, la marca como «OC pendiente» con una referencia propia (RN-05). 2. Abre una transacción y bloquea los productos del carrito. 3. Verifica el stock de cada línea (RN-02). 4. Toma el precio vigente de la lista del cliente (RN-01, RN-06). 5. Agrupa las líneas por rango de conservación y crea una orden «Recibida» por cada rango (RN-16). 6. Descuenta el stock. 7. Marca el carrito como convertido (RN-03). 8. Confirma la transacción. 9. Informa los números de orden y la división térmica cuando corresponde. 10. La orden aparece en «Pedidos web» del vendedor asignado |
| Flujos alternativos | A1. Stock insuficiente en alguna línea: no se crea la orden, se informa el producto y la cantidad disponible y se vuelve al carrito. A2. Dirección ajena o inexistente: se pide elegir o crear una. A3. B2B sin orden de compra: la orden se crea igual con la referencia WEB-año-número y el aviso «OC pendiente»; el cliente puede agregar la real después, y el CRM muestra las órdenes pendientes. A4. Falla técnica durante la transacción: se revierte todo (ni orden ni descuento), se informa y el carrito sigue abierto. A5. Dos compras simultáneas de las últimas unidades: la segunda ve «stock insuficiente» |
| Postcondiciones | Una o varias órdenes «Recibida» según el rango, con sus líneas y precios congelados; stock descontado; carrito convertido; orden visible en el CRM |
| Tablas | `carrito`, `carrito_item`, `producto`, `precio_producto`, `tipo_cliente`, `orden`, `orden_item`, `direccion` |
| Criterios de aceptación | 1. Con stock 10 y una compra de 10, el stock queda en 0. 2. Con stock 5 y una compra de 6, no se crea la orden y el stock sigue en 5. 3. El precio de cada línea coincide con la lista del perfil, y no cambia si la lista se modifica después. 4. Dos compras simultáneas de las últimas 5 unidades generan una sola orden. 5. Una dirección de otro cliente es rechazada. 6. Si falla una línea, no se descuenta ninguna |

*Nota.* Elaboración propia.

### CU-07 Gestionar prospectos y avanzar etapas del pipeline

**Tabla 5**
*Especificación del caso de uso CU-07*

| Elemento | Descripción |
|---|---|
| Actor principal | Vendedor |
| Precondiciones | Sesión iniciada con rol vendedor |
| Disparador | El vendedor crea un prospecto o mueve su tarjeta a otra etapa |
| Flujo normal | 1. El vendedor ingresa el prospecto (contacto, correo o teléfono, origen); queda en «Prospecto», asignado a él (RN-09). 2. Registra la primera interacción y mueve explícitamente la tarjeta a «Contactado» (RN-12). 3. Mueve la tarjeta a «Propuesta enviada» y conserva la actividad comercial en la ficha. 4. Si el cliente responde con condiciones, pasa a «Negociación». 5. Desde Negociación, con correo y RUT informado no duplicado, pasa a «Cliente ganado»: el sistema crea el cliente (tipo B2B, lista institucional, mismo vendedor), vincula el prospecto y registra la fecha de cierre (RN-11) |
| Flujos alternativos | A1. Pasar a «Perdido» sin motivo: se rechaza y se pide el motivo (RN-11). A2. Movimiento no permitido (por ejemplo, de Prospecto a Negociación): se rechaza (RN-10). A3. Al ganar, RUT de cliente ya existente o correo ausente: se rechaza el cierre. No existe advertencia automática por duplicidad de empresa al crear el prospecto. A4. Un vendedor intenta ver o mover el prospecto de otro: el sistema no se lo muestra (RN-09). A5. El cliente pide aclaraciones tras la propuesta: vuelve a «Contactado» |
| Postcondiciones | Etapa actualizada; interacción registrada; si se ganó, cliente creado y prospecto cerrado con fecha |
| Tablas | `prospecto`, `etapa_pipeline`, `interaccion`, `cliente`, `tipo_cliente` |
| Criterios de aceptación | 1. No se puede pasar de Prospecto a Negociación. 2. Perder sin motivo falla. 3. Al ganar existe un cliente con la lista institucional y el vendedor del prospecto. 4. Un vendedor no ve los prospectos de otro. 5. La conversión del mes (consulta 6) coincide con un conteo manual |

*Nota.* Elaboración propia.

### CU-09 Registrar un requerimiento y clasificarlo con IA

**Tabla 6**
*Especificación vigente del caso de uso CU-09*

| Elemento | Descripción |
|---|---|
| Actores | Cliente autenticado; proveedores externos de IA; personal comercial autorizado |
| Precondiciones | Cuenta de cliente; si se referencia una orden, debe pertenecer a esa cuenta |
| Disparador | Enviar Soporte o Reportar un problema desde el detalle de una orden |
| Flujo normal | Validar asunto y descripción; persistir el requerimiento con cliente y orden opcional; consultar al clasificador; guardar confianza y categoría válida si alcanza 0,60; mostrar el registro en soporte y en la bandeja CRM |
| Alternativas | Falla de proveedor, categoría inválida o confianza baja: el nuevo requerimiento queda sin clasificar. Respaldo por otro proveedor cuando está configurado y hay presupuesto. Reintento manual o clasificación humana; no existe cola automática. Descripción vacía: envío rechazado |
| Tiempo | Presupuesto nominal de doce segundos para proveedores; no garantiza el plazo total HTTP |
| Postcondiciones | Una falla de IA no elimina el requerimiento previamente guardado; el reintento fallido no borra una clasificación anterior |
| Datos | requerimiento, categoria_requerimiento, cliente y orden |
| Aceptación | Orden ajena no se vincula; con IA apagada el requerimiento persiste; confianza 0,40 no clasifica un nuevo registro; una categoría válida con confianza suficiente se guarda; credenciales por entorno |

Nota. Elaboración propia. El registro histórico de veinte aciertos sobre veinte ejemplos corresponde al clasificador del 22-oct-2026 y no al asistente de tienda.

### CU-14 Consultar al asistente de tienda

El visitante puede consultar productos y precios públicos; el cliente autenticado consulta su perfil y sus propios pedidos. El servidor construye el contexto, utiliza Groq y Gemini por defecto y revisa la respuesta antes de mostrarla. El asistente no crea órdenes, no modifica stock ni consulta pedidos ajenos. Si falta una clave o falla un proveedor, devuelve un aviso de indisponibilidad y el portal sigue operativo. La evaluación real del chat se realiza mediante `evaluar_asistente` y no se sustituye por el resultado histórico del clasificador.

### CU-11 Detectar la ruptura de la cadena de frío

**Tabla 7**
*Especificación del caso de uso CU-11*

| Elemento | Descripción |
|---|---|
| Actor principal | Simulador IoT (sistema). Beneficiarios: despachador, vendedor y cliente |
| Precondiciones | El camión está registrado con su rango de temperatura; el contenedor del simulador está en ejecución |
| Disparador | Llega una lectura (cada pocos segundos por camión) |
| Flujo normal | 1. El simulador genera la lectura (`camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`). 2. Calcula `alerta_ruptura_frio` comparando `temp_camara` con el mínimo y el máximo del rango del camión: hay alerta si es menor que el mínimo o mayor que el máximo. 3. Inserta la lectura en `telemetria` con su fecha y hora. 4. El dashboard y la torre de control muestran las lecturas con alerta. 5. Las órdenes cuyo intervalo de viaje coincide con la lectura quedan como afectadas (RN-13) y se destacan en la ficha del cliente y en el seguimiento del pedido |
| Flujos alternativos | A1. Lectura inválida (por ejemplo, latitud imposible): la base de datos la rechaza; el simulador registra el error y sigue con la siguiente. A2. Falla la conexión a la base: el simulador vuelve a conectar con espera fija de cinco segundos. A3. Varias lecturas seguidas con alerta: se conservan como lecturas; las consultas pueden agruparlas por tiempo, pero no existe un identificador de incidente único. A4. Camión sin despacho en curso: la alerta se registra, pero no afecta a ninguna orden |
| Reglas | El umbral lo define el rango del camión, no el de cada producto; la compatibilidad entre el camión y las categorías que transporta se valida al asignar el despacho (ver `04b-modelo-datos.md`) |
| Postcondiciones | Lectura persistida con la bandera correcta |
| Tablas | `telemetria`, `camion`, `rango_temperatura`, `despacho`, `orden` |
| Criterios de aceptación | 1. Una lectura de 3,1 °C en un camión refrigerado (0 a 4 °C) queda sin alerta. 2. Una de 5,2 °C queda con alerta. 3. Una de -17 °C en un camión congelado (-25 a -18 °C) queda con alerta. 4. La consulta de consistencia (consulta 5) devuelve cero filas. 5. La lectura se ve en el dashboard en pocos segundos (umbral supuesto: 10 s). 6. Las lecturas ordinarias las genera el simulador; las lecturas forzadas del modo administrativo se identifican aparte |

*Nota.* Elaboración propia.
