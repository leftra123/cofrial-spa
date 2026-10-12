# Procesos AS-IS y TO-BE (BPMN 2.0)

> Aporta a H1-D1 (el diagnóstico se ve en el AS-IS) y a H1-D4 (el TO-BE muestra cómo se elimina el Shadow IT).

## Notación elegida

| Notación | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| BPMN 2.0 | Estándar abierto, con carriles por responsable, eventos y compuertas | Requiere conocer la simbología | Adoptada. Muestra los traspasos entre vendedor, bodega y despacho, que es donde hoy se pierde la información |
| Diagrama de actividades UML | Conocido en desarrollo de software | Menos legible para la gerencia | Descartada |
| Flujograma simple | Muy fácil de leer | Sin carriles: oculta quién hace cada paso | Complementaria. Solo para la presentación |

Nota. Elaboración propia, con el mismo criterio usado en TRAZO.

Herramienta de modelado: bpmn.io / Camunda Modeler (gratis, exporta a PNG y SVG). Alternativa: draw.io con la librería BPMN. Las imágenes se guardan en `informe/img/`.

## Proceso 1: Pedido de cliente institucional (B2B)

**Carriles AS-IS:** Cliente institucional · Vendedor · Bodega · Contabilidad
- [ ] El cliente llama o escribe un correo al vendedor.
- [ ] El vendedor anota el pedido en su celular o en papel.
- [ ] El vendedor avisa a bodega por WhatsApp.
- [ ] Bodega revisa el stock en su Excel local (puede no coincidir con contabilidad).
- [ ] Compuerta: ¿hay stock? → si no hay, se llama al cliente.
- [ ] Contabilidad factura en un sistema cerrado, sin enlace con bodega.
- Puntos de dolor que se marcan en el diagrama: registro informal, doble digitación, stock descuadrado.

**Carriles TO-BE:** Cliente institucional · E-commerce · CRM · Bodega · Base de datos (RDS)
- [ ] El cliente inicia sesión con perfil B2B y ve su lista de precios institucional.
- [ ] Arma el carrito y genera la orden.
- [ ] La orden queda registrada en RDS y aparece en el CRM del vendedor asignado.
- [ ] Bodega ve la orden y el stock desde la misma base de datos.

## Proceso 2: Despacho con cadena de frío

**Carriles AS-IS:** Despachador · Conductor · Cliente
- [ ] El despachador asigna la ruta por teléfono o WhatsApp.
- [ ] El conductor sale sin registro de temperatura ni GPS.
- [ ] Evento: la temperatura sube y nadie lo detecta.
- [ ] El cliente rechaza la carga al recibirla → merma.

**Carriles TO-BE:** Camión (IoT) · Plataforma · Despachador · Cliente
- [ ] El camión envía telemetría cada N segundos: `camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`.
- [ ] Compuerta: ¿`temp_camara` fuera de rango? → `alerta_ruptura_frio = true`.
- [ ] La alerta aparece en el dashboard y en la torre de control.
- [ ] El despachador actúa (desvía o reprograma) antes de la entrega.
- [ ] El cliente ve el estado de su pedido en el portal.

## Proceso 3: Gestión comercial de prospectos

**AS-IS:** cartera en el celular del vendedor, sin etapas ni métricas.
**TO-BE:** prospecto → contactado → propuesta → negociación → ganado o perdido, todo en el CRM, con requerimientos clasificados por IA.

## Notas del equipo
