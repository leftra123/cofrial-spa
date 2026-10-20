# 4d. Arquitectura funcional del CRM y pipeline comercial

Rúbrica H1-D4 (Logrado): arquitectura funcional del CRM que **erradica el Shadow IT** (cartera en celulares, WhatsApp).

## Eliminación del Shadow IT: antes vs. después

| Aspecto | Antes (Shadow IT) | Ahora (CRM centralizado) | Impacto |
|---|---|---|---|
| Cartera de clientes | En celular del vendedor (notas, correos) | BD centralizada (CLIENTE + OPORTUNIDAD) | Información persiste si vendedor se va |
| Prospecto a cliente | Conversaciones por WhatsApp | Estados en CRM (Prospecto → Contactado → Propuesta → Negociación → Ganado/Perdido) | Métricas visibles: tasa de cierre, tiempo promedio |
| Registro de contactos | Notas de voz, correos fragmentados | Tabla INTERACCION (fecha, tipo, notas, responsable) | Auditoría completa |
| Pedidos de clientes | Anotaciones informales | Órdenes vinculadas a CLIENTE, visibles en CRM | Historial de compra centralizado |
| Requerimientos (reclamos, cotizaciones) | Llamadas, correos sueltos | CRM con tabla REQUERIMIENTO, clasificados por IA | Trazabilidad, escalamiento automático |
| Métricas de venta | Ninguna; "sensación" | Dashboard con pipeline por etapa, tasa de cierre, valor promedio | Toma de decisiones basada en datos |

Nota. Elaboración propia.

---

## Módulos del CRM

### 1. Gestión de clientes (CRUD)

**Funcionalidades:**
- Crear cliente: nombre, RUT, tipo (B2B/B2C), email, teléfono, dirección.
- Editar: datos de contacto, crédito límite, vendedor asignado.
- Ver historial: todas las órdenes que ha hecho, fechas, montos, estados.
- Filtrar: por vendedor, por tipo (B2B/B2C), por estado (activo/inactivo).

**Quién usa:** vendedores, gerencia, contabilidad.

**Dato de origen:** parte viene del e-commerce (cliente auto-registrado), parte se crea manual en el CRM.

---

### 2. Pipeline de oportunidades

**Estados del pipeline (orden secuencial):**

```
1. PROSPECTO
   ├─ Cliente nuevo identificado
   ├─ No ha habido contacto formal
   └─ Acciones: investigar, preparar contacto

2. CONTACTADO
   ├─ Se hizo el primer contacto (llamada, correo, reunión)
   ├─ Se estableció interés inicial
   └─ Acciones: enviar información, agendar próxima conversación

3. PROPUESTA
   ├─ Se envió una propuesta formal (precio, términos, etc.)
   ├─ Cliente está evaluando
   └─ Acciones: seguimiento, responder preguntas

4. NEGOCIACIÓN
   ├─ Cliente negocia términos (precio, volumen, plazo)
   ├─ Es inminente el cierre
   └─ Acciones: concesiones, aceleradores

5. GANADA
   ├─ Cliente confirma la orden
   ├─ Se registra la venta (ORDEN en el e-commerce o manual)
   └─ Transición: cliente entra al historial

6. PERDIDA
   ├─ Cliente rechazó o eligió competencia
   ├─ Se registra el motivo (precio, producto, servicio)
   └─ Acción: análisis post-mortem
```

**Tabla ETAPA_PIPELINE:** almacena estos estados, con secuencia numérica para ordenarlos.

---

### 3. Tablero visual del pipeline

```
PROSPECTO         CONTACTADO        PROPUESTA         NEGOCIACIÓN       GANADA           PERDIDA
(7 opcs)          (5 opcs)           (4 opcs)          (2 opcs)          (10 opcs)        (3 opcs)
├─ Hosp. Norte    ├─ Superm. Sur    ├─ Clínica X     ├─ Feria Rural    ├─ [Nuevos]      ├─ [Análisis]
├─ Rest. Central  ├─ Institución Y  ├─ Rest. Centro  └─ Panadería Z    └─ [Este mes]    ├─ Decidió otra
├─ [+3]           └─ [+2]           └─ [+1]                                             └─ Precio alto
│
Valor total:      Valor total:      Valor total:      Valor total:      Valor total:    Valor perdido:
$2.100.000       $1.400.000        $800.000          $350.000          $4.250.000      $750.000
Tasa: 14 %       Tasa: 36 %        Tasa: 50 %        Tasa: 85 %
```

**Datos que se muestran:** nombre de prospecto, valor estimado, vendedor, días en esa etapa.

**Acciones desde el tablero:** arrastrar para cambiar de etapa, doble click para editar.

---

**Figura 4**
*Etapas del pipeline comercial y sus transiciones*

![Pipeline comercial del CRM: de prospecto a cliente ganado o perdido](img/crm-pipeline.png)

Nota. Elaboración propia.

---

### 4. Historial de interacciones

**Tabla INTERACCION:**
- `tipo`: LLAMADA | CORREO | REUNIÓN | NOTA | PROPUESTA_ENVIADA
- `fecha`: cuándo ocurrió
- `descripción`: qué se habló / acordó
- `responsable`: quién lo hizo (vendedor_id)
- `próxima_acción`: fecha en que debe hacerse el seguimiento

**Vista:** timeline cronológico por prospecto/cliente.

**Ejemplo:**
```
15-oct-2026 14:30 | REUNIÓN
Participantes: José Vendedor, Gerente de Compras Hospital Temuco
Tema: Propuesta de carnés frescos, descuento volumen 20%
Resultado: "Cliente interesado, espera presupuesto aprobado"
Próxima acción: 18-oct (seguimiento)

12-oct-2026 09:15 | CORREO
De: José Vendedor
Asunto: Catálogo de productos Cofrial
Respuesta: Abierto, sin respuesta aún
```

---

### 5. Clasificación automática de requerimientos (IA)

Cuando un cliente ingresa una consulta en el e-commerce o CRM:

```
INPUT: "El pedido llegó con temperatura de 5.2°C, ¿qué hago?"
  ↓
API Gemini (o alternativa gratuita):
  ├─ Analiza el texto
  ├─ Clasifica en: RECLAMO | COTIZACIÓN | DESPACHO | CALIDAD | OTRO
  └─ Respuesta: CALIDAD + RECLAMO (prioridad alta)
  ↓
Sistema enruta automáticamente:
  ├─ Gerencia de Operaciones (copia de la ruptura de frío)
  ├─ Atención al Cliente (responder al cliente)
  └─ CRM: crea un REQUERIMIENTO con estado "Asignado"
```

**Beneficio:** sin intervención manual, el problema llega al responsable en < 2 minutos.

---

### 6. Dashboard para gerencia

**Métricas visibles:**

| Métrica | Cálculo | Frecuencia |
|---|---|---|
| Tasa de conversión (Prospecto → Ganada) | (Ganadas / Prospectos totales) × 100 | Mensual |
| Tiempo promedio en pipeline | Suma de días en cada etapa / N oportunidades | Mensual |
| Valor promedio de oportunidad | Suma de valores / N oportunidades | Mensual |
| Oportunidades vencidas (sin movimiento) | Oportunidades sin cambio de etapa en > 30 días | En tiempo real (alertas) |
| Pedidos por vendedor | N órdenes confirmadas por vendedor | Semanal |
| Tasa de retención de clientes | Clientes que compran > 1 vez / Clientes totales | Mensual |

---

## Cómo el CRM erradica el Shadow IT

| Shadow IT | Problema | Solución CRM |
|---|---|---|
| Cartera en celular del vendedor | Se pierde si renuncia | Datos en BD, otros vendedores ven la oportunidad |
| "Debe volver a contactar a este cliente" en nota de voz | No hay prioridad, se olvida | Campo "próxima_acción" con fecha + recordatorio automático |
| "Hablé con el cliente hace 2 meses" (sin evidencia) | No se sabe qué se prometió | Tabla INTERACCION con registro completo |
| Comprador privado: vendedor negocia precio sin reportar | Márgenes desconocidos | Todas las órdenes van por el sistema, con precio registrado |
| "No sé si cerré ese deal" | Métricas falsas | Tasa de conversión calculada automáticamente desde DB |

---

## Integración CRM ← → E-commerce

```
Cliente compra en e-commerce
       ↓
Orden se crea en RDS (ORDEN + ORDEN_ITEM)
       ↓
Trigger: se actualiza CLIENTE (fecha_última_compra, total_gastado)
       ↓
Se crea un evento en CRM:
  ├─ Si es cliente nuevo → se registra automáticamente
  ├─ Si es cliente existente → se actualiza historial
  └─ Si es un prospecto en negociación → etapa pasa a GANADA
       ↓
Vendedor asignado recibe notificación: "Tu cliente X acaba de generar una orden"
       ↓
Historial del cliente muestra: "Compró $XX el 15-oct-2026"
```

**Resultado:** no hay duplicación de información. Todo fluye desde RDS.

---

## Pantalla del CRM: vista del vendedor

```
┌──────────────────────────────────────────────┐
│ CRM COFRIAL · Mi Cartera                     │
├──────────────────────────────────────────────┤
│ Bienvenido, José Vendedor                    │
│                                              │
│ Mi Pipeline (Oportunidades)                  │
│                                              │
│ Prospecto (4)          Valor: $1.2M          │
│ ├─ Hospital A (Est: $300k)  [+30 días]      │
│ └─ [+3 más]                                 │
│                                              │
│ Contactado (5)         Valor: $900k          │
│ ├─ Superm. B (Est: $200k)   [+5 días]      │
│ └─ [+4 más]                                 │
│                                              │
│ Propuesta (3)          Valor: $500k          │
│ ├─ Clínica C (Est: $250k)   [+2 días]      │
│ └─ [+2 más]                                 │
│                                              │
│ Mis Próximas Acciones                        │
│ ├─ ⏰ Hoy a las 16:00: Llamar a Hosp. A    │
│ ├─ 🎯 Enviar propuesta a Superm. B         │
│ └─ ✉️ Responder consulta de Clínica C      │
│                                              │
│ [Mi Historial] [Clientes] [Requerimientos] │
└──────────────────────────────────────────────┘
```

Nota. Elaboración propia.

---

## Siguiente fase: integraciones avanzadas

- **Outlook/Gmail:** sincronizar correos de oportunidades
- **WhatsApp Business:** recibir mensajes de clientes en el CRM (sin celular personal)
- **Zoom/Teams:** agendar videollamadas desde el CRM
- **BI:** conectar el pipeline al dashboard para análisis de tendencias

Nota. Elaboración propia. Ahora no, pero el diseño lo permite.
