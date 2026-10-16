# Casos de uso del ecosistema

> Aporta a H1-D4 (arquitectura de canales y CRM). Sirve también como guion de la demo del Hito 2.
> **Estado: borrador de redacción**, pendiente de validación del equipo. Los criterios de aceptación de cada especificación son las pruebas que se ejecutan antes del Hito 2.

## Formato

| Formato | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| Diagrama de casos de uso UML + especificación breve | Muestra actores, límites del sistema y relaciones de un vistazo | La especificación completa es costosa | Adoptada. Diagrama general y especificación solo de los casos críticos |
| Historias de usuario | Rápidas, orientadas al valor | Sin vista global de actores | Complementaria. Se usan como tarjetas en Trello |

Nota. Elaboración propia.

## Actores

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

| ID | Caso de uso | Actor | Módulo | Prioridad | Rúbrica |
|---|---|---|---|---|---|
| CU-01 | Seleccionar perfil e iniciar sesión (B2B/B2C) | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-02 | Consultar el catálogo de refrigerados con precio según perfil | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-03 | Gestionar el carrito de compras | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-04 | Generar una orden | Cliente B2B, B2C | E-commerce | Obligatorio | H2-D2 |
| CU-05 | Seguir el estado del pedido | Cliente B2B, B2C | E-commerce | Extra | H2-D5 |
| CU-06 | Gestionar clientes | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-07 | Gestionar prospectos y avanzar etapas del pipeline | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-08 | Hacer seguimiento de pedidos web | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-09 | Registrar un requerimiento y clasificarlo con IA | Cliente, Servicio de IA | CRM / E-commerce | Obligatorio | H2-D5 |
| CU-10 | Enviar telemetría del camión | Simulador IoT | IoT | Obligatorio | H2-D3 |
| CU-11 | Detectar la ruptura de cadena de frío | Simulador IoT | IoT | Obligatorio | H2-D3 |
| CU-12 | Monitorear la flota y sus alertas | Despachador | Torre de control | Extra | H2-D4 |
| CU-13 | Consultar el dashboard de ventas y cadena de frío | Gerencia | BI | Obligatorio | H2-D4 |

Nota. Elaboración propia. "Obligatorio" se refiere a lo que exige la pauta del Hito 2.

## Diagrama de casos de uso

**Figura 1**
*Diagrama de casos de uso del ecosistema Cofrial*

![Diagrama de casos de uso](img/casos-de-uso.png)

*Nota.* Elaboración propia, con notación simplificada. Verde: casos críticos con especificación. Las flechas punteadas indican que un caso incluye a otro (por ejemplo, generar una orden incluye gestionar el carrito). Los actores en amarillo son sistemas.

## Especificaciones de los casos críticos

Se especifican cuatro casos: los tres que la pauta hace más sensibles (orden, IA y ruptura de frío) y el pipeline comercial, que concentra la lógica del CRM. Las reglas citadas (RN-xx) están en `04c-canales-b2b-b2c.md` y `04d-crm.md`.

### CU-04 Generar una orden

**Tabla 1**
*Especificación del caso de uso CU-04*

| Elemento | Descripción |
|---|---|
| Actor principal | Cliente B2B o B2C. Durante la transición, el vendedor a nombre del cliente (RN-15) |
| Precondiciones | Sesión iniciada; carrito abierto con al menos una línea; el cliente tiene una dirección |
| Disparador | El cliente pulsa «Confirmar pedido» |
| Flujo normal | 1. El sistema valida que la dirección sea del cliente (RN-04) y, si es B2B, que traiga número de orden de compra (RN-05). 2. Abre una transacción y bloquea los productos del carrito. 3. Verifica el stock de cada línea (RN-02). 4. Toma el precio vigente de la lista del cliente (RN-01, RN-06). 5. Crea la orden en estado «Recibida» con sus líneas. 6. Descuenta el stock. 7. Marca el carrito como convertido (RN-03). 8. Confirma la transacción. 9. Muestra la confirmación con el número de orden. 10. La orden aparece en «Pedidos web» del vendedor asignado |
| Flujos alternativos | A1. Stock insuficiente en alguna línea: no se crea la orden, se informa el producto y la cantidad disponible y se vuelve al carrito. A2. Dirección ajena o inexistente: se pide elegir o crear una. A3. B2B sin orden de compra: se pide completarla. A4. Falla técnica durante la transacción: se revierte todo (ni orden ni descuento), se informa y el carrito sigue abierto. A5. Dos compras simultáneas de las últimas unidades: la segunda ve «stock insuficiente» |
| Postcondiciones | Orden «Recibida» con sus líneas y precios congelados; stock descontado; carrito convertido; orden visible en el CRM |
| Tablas | `carrito`, `carrito_item`, `producto`, `precio_producto`, `tipo_cliente`, `orden`, `orden_item`, `direccion` |
| Criterios de aceptación | 1. Con stock 10 y una compra de 10, el stock queda en 0. 2. Con stock 5 y una compra de 6, no se crea la orden y el stock sigue en 5. 3. El precio de cada línea coincide con la lista del perfil, y no cambia si la lista se modifica después. 4. Dos compras simultáneas de las últimas 5 unidades generan una sola orden. 5. Una dirección de otro cliente es rechazada. 6. Si falla una línea, no se descuenta ninguna |

*Nota.* Elaboración propia.

### CU-07 Gestionar prospectos y avanzar etapas del pipeline

**Tabla 2**
*Especificación del caso de uso CU-07*

| Elemento | Descripción |
|---|---|
| Actor principal | Vendedor |
| Precondiciones | Sesión iniciada con rol vendedor |
| Disparador | El vendedor crea un prospecto o mueve su tarjeta a otra etapa |
| Flujo normal | 1. El vendedor ingresa el prospecto (contacto, correo o teléfono, origen); queda en «Prospecto», asignado a él (RN-09). 2. Registra la primera interacción y la tarjeta pasa a «Contactado» (RN-12). 3. Registra la propuesta y pasa a «Propuesta enviada». 4. Si el cliente responde con condiciones, pasa a «Negociación». 5. Al aceptar, pasa a «Cliente ganado»: el sistema crea el cliente (tipo B2B, lista institucional, mismo vendedor), vincula el prospecto y registra la fecha de cierre (RN-11) |
| Flujos alternativos | A1. Pasar a «Perdido» sin motivo: se rechaza y se pide el motivo (RN-11). A2. Movimiento no permitido (por ejemplo, de Prospecto a Negociación): se rechaza (RN-10). A3. Prospecto duplicado (mismo correo o empresa): se advierte antes de crear. A4. Un vendedor intenta ver o mover el prospecto de otro: el sistema no se lo muestra (RN-09). A5. El cliente pide aclaraciones tras la propuesta: vuelve a «Contactado» |
| Postcondiciones | Etapa actualizada; interacción registrada; si se ganó, cliente creado y prospecto cerrado con fecha |
| Tablas | `prospecto`, `etapa_pipeline`, `interaccion`, `cliente`, `tipo_cliente` |
| Criterios de aceptación | 1. No se puede pasar de Prospecto a Negociación. 2. Perder sin motivo falla. 3. Al ganar existe un cliente con la lista institucional y el vendedor del prospecto. 4. Un vendedor no ve los prospectos de otro. 5. La conversión del mes (consulta 6) coincide con un conteo manual |

*Nota.* Elaboración propia.

### CU-09 Registrar un requerimiento y clasificarlo con IA

**Tabla 3**
*Especificación del caso de uso CU-09*

| Elemento | Descripción |
|---|---|
| Actores | Cliente o visitante (principal); servicio de IA (secundario, externo) |
| Precondiciones | Ninguna: un visitante anónimo puede escribir; un cliente con sesión puede asociar una orden suya |
| Disparador | El usuario envía el formulario de consulta o «Reportar un problema» |
| Flujo normal | 1. El usuario completa asunto y descripción (y, si es cliente, la orden). 2. El sistema crea el requerimiento en estado «sin clasificar». 3. Envía asunto y descripción a la API de IA junto con las categorías vigentes. 4. La IA responde categoría y confianza. 5. El sistema guarda ambas y pasa el estado a «clasificado». 6. Si la categoría es «Calidad o frío» y hay orden asociada, el requerimiento queda destacado en la ficha del cliente y en la bandeja del vendedor. 7. El requerimiento aparece en la bandeja (RN-14) |
| Flujos alternativos | A1. La API no responde o se agota el tiempo de espera (supuesto: 10 segundos): el requerimiento queda «sin clasificar», aparece marcado en la bandeja y se reintenta en segundo plano. A2. Confianza menor que 0,60: queda clasificado con la marca «revisar» y exige confirmación manual. A3. La IA devuelve una categoría que no existe: se trata como «sin clasificar». A4. Se alcanzó el límite del plan gratuito: igual que A1; si hay una API de respaldo configurada, se usa. A5. Descripción vacía: se rechaza el envío |
| Postcondiciones | El requerimiento queda guardado siempre, haya o no clasificación |
| Tablas | `requerimiento`, `categoria_requerimiento`, `cliente`, `orden` |
| Criterios de aceptación | 1. Con la API de IA apagada, el requerimiento se guarda como «sin clasificar» y el portal responde normalmente. 2. Con una respuesta simulada de confianza 0,4, queda marcado «revisar». 3. Una categoría «Calidad o frío» con orden asociada aparece en la ficha del cliente. 4. La clave de la API no está en el repositorio (se lee de `.env`) |

*Nota.* Elaboración propia.

### CU-11 Detectar la ruptura de la cadena de frío

**Tabla 4**
*Especificación del caso de uso CU-11*

| Elemento | Descripción |
|---|---|
| Actor principal | Simulador IoT (sistema). Beneficiarios: despachador, vendedor y cliente |
| Precondiciones | El camión está registrado con su rango de temperatura; el contenedor del simulador está en ejecución |
| Disparador | Llega una lectura (cada pocos segundos por camión) |
| Flujo normal | 1. El simulador genera la lectura (`camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`). 2. Calcula `alerta_ruptura_frio` comparando `temp_camara` con el mínimo y el máximo del rango del camión: hay alerta si es menor que el mínimo o mayor que el máximo. 3. Inserta la lectura en `telemetria` con su fecha y hora. 4. El dashboard y la torre de control muestran las lecturas con alerta. 5. Las órdenes del despacho en curso del camión (con salida y sin llegada) quedan como afectadas (RN-13) y se destacan en la ficha del cliente y en el seguimiento del pedido |
| Flujos alternativos | A1. Lectura inválida (por ejemplo, latitud imposible): la base de datos la rechaza; el simulador registra el error y sigue con la siguiente. A2. Falla la conexión a la base: el simulador reintenta con espera creciente y no se detiene. A3. Varias lecturas seguidas con alerta: el dashboard las agrupa como un solo incidente. A4. Camión sin despacho en curso: la alerta se registra, pero no afecta a ninguna orden |
| Reglas | El umbral lo define el rango del camión, no el de cada producto; la compatibilidad entre el camión y las categorías que transporta se valida al asignar el despacho (ver `04b-modelo-datos.md`) |
| Postcondiciones | Lectura persistida con la bandera correcta |
| Tablas | `telemetria`, `camion`, `rango_temperatura`, `despacho`, `orden` |
| Criterios de aceptación | 1. Una lectura de 3,1 °C en un camión refrigerado (0 a 4 °C) queda sin alerta. 2. Una de 5,2 °C queda con alerta. 3. Una de -17 °C en un camión congelado (-25 a -18 °C) queda con alerta. 4. La consulta de consistencia (consulta 5) devuelve cero filas. 5. La lectura se ve en el dashboard en pocos segundos (umbral supuesto: 10 s). 6. Todas las lecturas las genera el simulador: no hay inserciones manuales |

*Nota.* Elaboración propia.

## Notas del equipo
