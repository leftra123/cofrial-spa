# 2. Propuesta de valor y resolución de conflictos

Rúbrica H1-D1 (Logrado): demostrar cómo la arquitectura **neutraliza cada dolor**, erradicando los pedidos por WhatsApp y el papel.

## Matriz dolor → solución → indicador

| Dolor | Componente que lo resuelve | Cómo se demuestra en Hito 2 | Indicador de mejora |
|---|---|---|---|
| Servidor único sin respaldo | EC2 persistente + RDS con respaldos automáticos | App y BD corriendo en AWS sin interrupción | RPO (Recovery Point Objective) < 1 hora |
| Excel incomunicados | Una sola base de datos RDS para ventas, inventario y logística | Orden web descuenta stock instantáneamente; bodega ve lo mismo que CRM | Diferencias de inventario → 0 |
| Camiones sin trazabilidad | IoT: telemetría cada N segundos (lat, long, temp, combustible) | Dashboard muestra la flota en tiempo real; alerta si temp sale del rango | % entregas a tiempo, mermas documentadas |
| Ruptura de frío no detectada | `alerta_ruptura_frio` en la BD, visible en BI | Evento de ruptura genera alerta antes de la entrega; se documenta el motivo | Mermas por frío detectadas / totales |
| WhatsApp/llamadas para coordinar | Dashboard y CRM como canal oficial de gestión | Despachador ve órdenes en el CRM; rutas asignadas en plataforma | 100 % de rutas en sistema |
| Pedidos por teléfono/correo | E-commerce B2B/B2C autoservicio | Cliente entra, ve su precio según perfil (B2B/B2C), genera la orden | % de pedidos digitales / total |
| Cartera en celulares | CRM con pipeline visible | Prospecto registrado; estados (contactado, propuesta, ganado/perdido) en tiempo real | Tasa de conversión medible |
| Atención lenta/manual | IA clasificando requerimientos automáticamente | Reclamo/cotización/despacho clasificado por NLP; enruta al área | Tiempo promedio de clasificación < 1 min |

Nota. Elaboración propia.

## Propuesta de valor en una frase

**De la coordinación manual y fragmentada a un ecosistema integrado donde cada operación genera datos para mejorar la cadena de frío y la relación comercial.**

## Beneficios de negocio cuantificados

Supuestos:
- Mermas semanales actuales: ~5 % de la carga (de "millonarias semanales").
- Pedidos exitosos actuales: ~85 % (15 % fallan por coordinación, falta de stock o rechazo por frío).
- Costo promedio por envío: $50.000 CLP (costo operativo + producto).

| Escenario | Baseline (actual) | Con solución | Mejora anual |
|---|---|---|---|
| Mermas evitadas | 5 % semanal (4 camiones × 50 productos × 5 %) | 1 % semanal (detección temprana) | 4 % × 52 sem × costo promedio = ~$10.4 millones |
| Entregas exitosas | 85 % | 95 % (menos coordinación manual) | 10 % × pedidos/año × margen unitario = variable según volumen |
| Tiempo de gestión comercial | ~2 horas/vendedor/día en tareas manuales | ~30 min/vendedor/día | 1,5 horas × 4 vendedores × 250 días = 1.500 horas/año reasignables a venta |

Nota. Supuestos propios, a validar con la contraparte. Elaboración propia.

## Cómo erradica el Shadow IT

| Antes | Ahora | Control |
|---|---|---|
| Cartera en WhatsApp de vendedor | CRM centralizado con asignación de clientes | Gerencia ve pipeline en tiempo real |
| Ruta coordinada por llamadas | Dashboard de despacho; rutas asignadas en plataforma | Trazabilidad de cada camión |
| Temperatura "sabida por el conductor" | Telemetría automática con alerta | Datos históricos para análisis |
| Pedido anotado en papel o celular | Orden digital en e-commerce, visible en CRM | Trazabilidad total desde compra hasta entrega |

Nota. Elaboración propia.

## Impacto organizacional

**Para el vendedor:** una cartera digital que crece con él, no desaparece cuando se va. Herramientas para saber en qué están sus oportunidades. Menos tiempo en papeleo, más en venta.

**Para el despachador:** visibilidad en tiempo real. Actúa antes de que pase lo malo.

**Para contabilidad:** un único origen de la verdad. No reconciliaciones manuales.

**Para la gerencia:** métricas que antes no existían. Sabe dónde están las pérdidas.

Nota. Elaboración propia.
