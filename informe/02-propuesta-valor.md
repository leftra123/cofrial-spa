# 2. Propuesta de valor y resolución de conflictos

> Rúbrica H1-D1 (Logrado): demostrar cómo la arquitectura **neutraliza cada dolor**, erradicando los pedidos por WhatsApp y el papel.

## Matriz dolor → solución → evidencia en el prototipo (borrador)
| Dolor | Componente que lo resuelve | Cómo se demuestra en el Hito 2 | Indicador sugerido |
|---|---|---|---|
| Servidor único sin respaldo | EC2 + RDS (respaldos automáticos, snapshots) | App y BD corriendo en AWS | Disponibilidad, RPO/RTO |
| Excel incomunicados | Una sola BD central para ventas, inventario y logística | Orden web descuenta stock visible en CRM | Diferencias de inventario |
| Camiones sin trazabilidad | IoT: `lat`/`long` cada N segundos | Mapa/dashboard con posición en vivo | % entregas a tiempo |
| Ruptura de frío no detectada | IoT: `temp_camara` + `alerta_ruptura_frio` | Alerta visible en BI apenas ocurre | Mermas por ruptura |
| WhatsApp/llamadas para coordinar | Dashboard y CRM como canal oficial | Pedido y su estado en el CRM | Pedidos fuera del sistema |
| Pedidos por teléfono/correo | E-commerce B2B/B2C | Flujo catálogo → carrito → orden | Pedidos digitales / total |
| Cartera en celulares | CRM con pipeline | Prospecto avanza de etapa en el CRM | Tasa de conversión |
| Atención lenta | IA gratuita (clasificación / asistente) | Requerimiento clasificado automáticamente | Tiempo de primera respuesta |

## Pendiente
- [ ] Propuesta de valor en una frase para la gerencia.
- [ ] Beneficios de negocio cuantificados con supuestos.
- [ ] Hoja de ruta de adopción (qué pasa con los vendedores, despachadores, contabilidad).

## Notas del equipo
