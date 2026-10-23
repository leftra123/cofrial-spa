# Referencia: 21st.dev (inspiración de interfaz)

Revisado el 12-oct-2026. Es material de terceros; solo se usa como referencia.

**Qué es:** catálogo comunitario de componentes React + Tailwind + shadcn/ui (https://21st.dev). El código se copia al repo. Navegar es gratis; incluye 2 copias gratuitas al día y el resto es de pago.

**Para qué sirve en el prototipo**
- E-commerce y CRM: tablas, tarjetas de producto, formularios, filtros y paneles de estado del pipeline.
- Torre de control: solo el marco visual (barra lateral, tarjetas de alertas). El mapa y los camiones van con Leaflet (D-08).

**Límites**
- No tiene mapas, telemetría ni componentes de IoT.
- Los componentes son React y la web irá en Django con plantillas (HTMX y Tailwind), así que no se pueden usar tal cual. Sirven como inspiración visual: se rehace el diseño con las clases de Tailwind en las plantillas.
- La licencia la define cada autor: revisarla antes de copiar. magic-mcp es ISC; el SDK y agent-elements son MIT.
- No instalar Magic MCP: genera componentes React que no encajan con el stack y que luego habría que explicar.

**Descartado:** jev-demo.com (directorio de demos de IA con publicidad; sin e-commerce, CRM, telemetría, código ni API).
