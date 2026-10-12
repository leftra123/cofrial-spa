# Referencia: WareTrack (proyecto visto en Threads)

> Material de terceros. Los videos y capturas están en `app/`, que **no se sube** al repositorio. Solo la usamos como inspiración.

## Qué es
Un "gemelo digital" logístico: vista isométrica 3D de bodegas, camiones y montacargas con datos en vivo.
- KPIs arriba: stock disponible, camiones en sitio, % de entregas a tiempo.
- Panel lateral al seleccionar un camión: estado, envío, cliente, destino, ETA, velocidad y carga.
- Seguimiento del envío: Orden confirmada → Preparado → Cargado → En tránsito → Entregado.
- Lista de andenes, montacargas y camiones con su estado.
- Selector de sitios (incluye uno de "Cold Chain").

## ¿Tiene conexión con Cofrial? Sí
| WareTrack | Cofrial (nuestro prototipo) |
|---|---|
| Camión con estado y ETA | Camión con `temp_camara`, `combustible_pct`, `lat`/`long` y `alerta_ruptura_frio` |
| Seguimiento del envío | Estado de la orden del e-commerce, visible para el cliente B2B y en el CRM |
| KPIs de stock y entregas | Dashboard BI: ventas por canal × alertas de frío |
| Sitios / bodegas | Frigorífico central de Temuco y puntos de entrega de la macrozona sur |

## ¿Es funcional para nosotros?
- WareTrack es un **diseño de interfaz** con datos de demo; no es un sistema que podamos reutilizar.
- **Lo que sí sirve:** su patrón de pantalla (KPIs + mapa + panel de detalle + línea de tiempo del envío), aplicado a nuestra "torre de control".
- **Versión recomendada:** mapa 2D (Leaflet) con los 50 camiones moviéndose según la telemetría real de la BD y alertas en rojo. Es alcanzable en el plazo.
- **Versión ambiciosa:** isométrica 3D con Three.js. Solo si lo obligatorio ya está listo antes del 10-nov.
- **Valor en la nota:** refuerza H2-D4 (BI en vivo) y H2-D5 (defensa). Es "más de lo que piden" sin desviar el foco.
