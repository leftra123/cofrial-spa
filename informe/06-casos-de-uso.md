# Casos de uso del ecosistema

> Aporta a H1-D4 (arquitectura de canales y CRM). Sirve también como guion de la demo del Hito 2.

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

## Especificaciones a desarrollar (casos críticos)
- [ ] CU-04 Generar una orden (flujo normal, alternativo: sin stock; postcondición: orden visible en el CRM)
- [ ] CU-09 Clasificar un requerimiento con IA (flujo alternativo: la API no responde → queda "sin clasificar")
- [ ] CU-11 Detectar la ruptura de cadena de frío (regla: rango crítico según la categoría del producto)

## Notas del equipo
