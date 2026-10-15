# 5. Procesos AS-IS y TO-BE (BPMN 2.0)

Aporta a H1-D1 (diagnóstico visible en AS-IS) y a H1-D4 (TO-BE muestra cómo desaparece el Shadow IT).

## Decisión de notación

| Notación | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| BPMN 2.0 | Estándar abierto, carriles por responsable, eventos y compuertas | Requiere aprender la simbología | Adoptada. Los traspasos entre responsables son donde hoy se pierde la información |
| Diagrama de actividades UML | Conocido en desarrollo de software | Menos legible para gerencia no técnica | Descartada |
| Flujograma simple | Muy fácil de leer | Sin carriles: oculta responsabilidades | Complementaria. Solo para presentaciones |

Nota. Elaboración propia. Herramienta: bpmn.io / Camunda Modeler (gratis).

## Proceso 1: Pedido de cliente institucional (B2B)

### AS-IS (problema: registro manual, doble digitación, stock descuadrado)

**Carriles:** Cliente institucional | Vendedor | Bodega | Contabilidad

1. Cliente llama o envía correo al vendedor.
2. Vendedor **anota en papel o celular** el pedido (marca, cantidad, fecha requerida).
3. Vendedor avisa a bodega **por WhatsApp o llamada** (traspaso informal).
4. Bodega revisa **su planilla Excel local** (que puede no coincidir con contabilidad).
5. **Compuerta:** ¿hay stock según la planilla?
   - Si NO: bodega llama al cliente o al vendedor para avisar faltante.
   - Si SÍ: bodega separa la carga (registro manual en el Excel).
6. Contabilidad recibe un **correo o una factura manual** del vendedor.
7. Contabilidad factura en su **sistema cerrado** (sin enlace a bodega).
8. **Punto de dolor:** si contabilidad acaba de vender otras unidades del mismo producto, bodega no lo sabe. Stock sale negativo.

**Puntos marcados en el diagrama BPMN:**
- Rectángulo rojo: "Anota en celular/papel" (Shadow IT).
- Rectángulo rojo: "Revisa Excel local" (no es origen único).
- Compuerta de decisión: "Stock según planilla" (información desactualizada).

### TO-BE (solución: orden digital, RDS único, sin papeles)

**Carriles:** Cliente B2B | E-commerce | CRM | Bodega | RDS (base de datos)

1. Cliente inicia sesión en el e-commerce con perfil B2B.
2. Ve su **lista de precios institucional** (descuento, volumen mínimo, crédito límite).
3. Busca productos, agrega al carrito.
4. **La orden se genera automáticamente** en RDS y aparece en CRM con estado "Nueva".
5. Sistema revisa **stock en RDS en tiempo real** (única fuente de verdad).
6. **Compuerta:** ¿stock disponible?
   - Si NO: orden entra en estado "Pendiente stock" y se notifica al cliente.
   - Si SÍ: bodega ve la orden, la prepara, actualiza stock en RDS.
7. Contabilidad **ve la orden en RDS automáticamente**, factura desde el sistema.
8. El vendedor asignado recibe una **notificación en el CRM** (no por WhatsApp).

**Mejora:** cero papeles, cero diferencias de inventario, trazabilidad completa.

---

## Proceso 2: Despacho con cadena de frío

### AS-IS (problema: temperatura desconocida, ruptura silenciosa)

**Carriles:** Despachador | Conductor | Cliente | Plataforma (inexistente)

1. Despachador asigna ruta **por teléfono o WhatsApp**.
2. Conductor sale con la carga sin registros iniciales.
3. **Durante el viaje:**
   - Si el conductor **nota que la temperatura sube**, podría llamar al despachador.
   - O **no se da cuenta** (conducción, distracciones).
   - O **la cobertura está mala** y no puede comunicar.
4. Cliente recibe la carga.
5. **Evento crítico:** temperatura fuera de rango → cliente rechaza la entrega (merma).
6. **No hay registro de por qué pasó.** El despachador registra "devolución" sin causa.

**Puntos de pérdida:** paso 3 completo es un agujero negro. Nadie sabe si la temperatura subió o no.

### TO-BE (solución: IoT, alertas en tiempo real)

**Carriles:** Camión (IoT) | Plataforma | Despachador | Cliente | Torre de control

1. Camión se prepara con los equipos IoT calibrados.
2. Conductor confirma salida; la plataforma registra `camion_id`, `tiempo_salida`, `temp_inicial`.
3. **Cada N segundos (ej. 30 seg):**
   - IoT envia: `camion_id`, `temp_camara`, `lat`, `long`, `combustible_pct`.
   - Sistema inserta en RDS.
   - Dashboard actualiza en vivo.
4. **Compuerta:** ¿`temp_camara` fuera del rango crítico?
   - Si SÍ: `alerta_ruptura_frio = true` → torre de control y despachador reciben alerta.
   - Despachador actúa: desvía a una parada refrigerada, busca alternativa, o reprograma entrega.
5. Cliente recibe la carga **dentro del rango, con documentación** de temperatura histórica.

**Mejora:** detección inmediata, actuación antes del daño, registro completo.

---

## Proceso 3: Gestión comercial de prospectos

### AS-IS (problema: cartera dispersa)

**Carriles:** Vendedor | Prospecto/Cliente | Vendedor (celular personal)

1. Vendedor contacta a un prospecto (hospital, supermercado).
2. Negocia verbalmente; mantiene notas **en su celular** (WhatsApp, correos, notas de voz).
3. Prospecto está en alguna etapa (le interesa / pidió precio / está negociando), pero **solo el vendedor lo sabe**.
4. Si el vendedor se va, **toda la información desaparece**.
5. No hay métricas: ¿cuántos prospectos hay? ¿cuántos se cierran? ¿en cuánto tiempo?

### TO-BE (solución: CRM centralizado)

**Carriles:** Vendedor | CRM | Prospecto/Cliente | IA (clasificación)

1. Vendedor abre el CRM y crea un prospecto con datos básicos (nombre, rubro, contacto).
2. **Estados del pipeline (carril de decisión):**
   - Prospecto (nuevo contacto) → Contactado (tuvo conversación) → Propuesta enviada → Negociación → Ganado / Perdido.
3. Cada transición se registra con **fecha, motivo y notas** (en CRM, no en celular).
4. Si un requerimiento llega por el e-commerce, **IA lo clasifica** automáticamente (reclamo, cotización, despacho, calidad).
5. El sistema **enruta a la persona correcta** basado en la clasificación.
6. Gerencia **ve el pipeline en tiempo real:** cuántos prospectos, en qué etapa, cuál va lento.

**Mejora:** información centralizada, métricas reales, formación del equipo sin pérdida de conocimiento.

---

## Herramientas y siguientes pasos

- **Diagramas:** generados en bpmn.io, exportados a PNG y almacenados en `informe/img/`.
- **Base para el Hito 2:** estos procesos definen los **casos de uso** del e-commerce, CRM e IoT.

Nota. Elaboración propia.
