# 4c. Arquitectura de canales: wireframes y user journeys B2B/B2C

Rúbrica H1-D4 (Logrado): user journeys **avanzados** del portal con diferenciación B2B/B2C.

## Perfiles y diferenciales

| Aspecto | B2B (Institucional) | B2C (Público general) |
|---|---|---|
| Usuarios típicos | Hospitales, supermercados, ferias, instituciones | Personas, restaurantes, pequeños negocios |
| Precio | Lista de precios institucional (negociado, con volumen mínimo) | Precio público sin descuentos |
| Crédito | Línea de crédito (pagar en 15-30 días) | Pago inmediato (tarjeta, transferencia) |
| Volumen | Pedidos grandes, recurrentes | Pedidos puntuales, menores |
| Contacto | Vendedor asignado, soporte dedicado | Atención automática + chat |
| Documentación | Factura con referencias PO, DNI empresa | Boleta simple |

Nota. Elaboración propia.

## User journeys principales

### Journey 1: Cliente B2B compra un pedido institucional

```
ETAPA 1: DESCUBRIMIENTO
├─ Cliente institucional accede al e-commerce (o recibe link de vendedor)
├─ Página de login: "¿Eres cliente B2B?"
└─ Inicia sesión con correo/contraseña (datos preexistentes de la BD)

ETAPA 2: CONSULTA Y SELECCIÓN
├─ Ve su lista de precios (ej. Hospital Temuco: -15 % respecto precio público)
├─ Busca por categoría: Carnes | Embutidos | Productos del mar
├─ Filtra por temperatura: -20°C | -10°C | 0-4°C (interés en especificaciones)
├─ Selecciona productos: Lomo Vetado 1kg × 20 unidades
└─ Ve **rango de temperatura del producto** (etiqueta verde: "0-4°C")

ETAPA 3: CARRITO Y VALIDACIÓN
├─ Carrito muestra: producto, cantidad, precio institucional, subtotal
├─ Sistema valida **stock en tiempo real** (descuento automático)
├─ Si falta stock: "Disponible en 3 días. ¿Deseas reservar?"
├─ Cliente ingresa:
│  ├─ Dirección de entrega (autocompletado de direcciones previas, o nueva)
│  ├─ Fecha de entrega deseada
│  └─ Contacto en el sitio (ej. "Entrega en Pañol, Tel: 2231-4567")
└─ Revisa resumen

ETAPA 4: PAGO Y CONFIRMACIÓN
├─ Elige forma de pago:
│  ├─ Crédito a 15 días (si tiene saldo disponible)
│  └─ Transferencia bancaria (opción alternativa)
├─ Sistema **genera la orden automáticamente** en RDS
├─ Estado inicial: "Confirmada - Pendiente preparación"
└─ Recibe confirmación por correo + SMS

ETAPA 5: SEGUIMIENTO
├─ Cliente accede a "Mis pedidos" en el e-commerce
├─ Ve estado en tiempo real:
│  ├─ "Confirmada" → "Preparando en bodega" → "En ruta" → "Entregada"
│  └─ Nota: cada etapa incluye fecha/hora y contacto del responsable
├─ Si el estado es "En ruta":
│  ├─ Aparece información del camión:
│  │  ├─ Temperatura actual de la cámara (verde si ≤ 4°C, rojo si > 4°C)
│  │  ├─ Ubicación del camión (mapa, aunque sea simplificada)
│  │  └─ ETA estimada de entrega
│  └─ Si hay **alerta de ruptura de frío**: notificación inmediata
└─ Entrega: cliente confirma recepción en la plataforma (opcionalmente)
```

**Puntos de dolor que se erradican:**
- ❌ Antes: pedido por teléfono → vendedor anota → bodega no lo recibe a tiempo
- ✅ Ahora: orden inmediata en RDS, bodega la ve de inmediato

---

### Journey 2: Cliente B2C compra sin contrato previo

```
ETAPA 1: LLEGADA Y AUTENTICACIÓN
├─ Cliente entra sin cuenta (invitado)
├─ Página de inicio: "¿Eres cliente nuevo?" → "Crear cuenta rápida"
├─ Ingresa: correo, contraseña, nombre, teléfono
└─ Sistema lo registra como B2C automáticamente (no requiere RUT empresa)

ETAPA 2: COMPRA PUNTUAL
├─ Busca productos a precio público (sin filtro de contrato)
├─ Selecciona: Pollo entero 2kg × 2 unidades
├─ Carrito muestra precio público + IVA
├─ Descuenta stock (si quedan < 5 unidades, muestra "Últimos disponibles")
└─ Revisa subtotal

ETAPA 3: PAGO INMEDIATO
├─ Elige forma de pago:
│  ├─ Tarjeta de crédito / débito
│  └─ Transferencia (si es en horario bancario)
├─ Sistema procesa pago de inmediato
├─ Si pago rechazado: permite reintentar
└─ Si aprobado: genera la orden

ETAPA 4: CONFIRMACIÓN Y ENTREGA
├─ Correo de confirmación con número de orden
├─ Dirección de entrega: ingresa nueva (sin historial)
├─ Fecha de entrega: próximo día hábil (opciones predeterminadas)
└─ Sin vendedor asignado (atención automática si hay dudas)

ETAPA 5: SEGUIMIENTO SIMPLIFICADO
├─ Link en correo: "Seguir mi pedido"
├─ Vista simplificada: Estado (Preparando → En ruta → Entregado)
├─ Contacto: chat automático (o número de WhatsApp del despacho)
└─ Si hay alerta de frío: notificación (pero menor énfasis que B2B)
```

**Diferencial clave:** B2C es **sin fricción**, pago inmediato, sin soporte dedicado. B2B es **con servicio**, crédito, vendedor.

---

## Wireframes de pantallas críticas

### Pantalla 1: Home - Selector de perfil

```
┌─────────────────────────────────────┐
│ COFRIAL · Cadena de Frío Inteligente│
├─────────────────────────────────────┤
│                                     │
│  ¿Quién eres?                       │
│                                     │
│  ┌─────────────┐   ┌─────────────┐ │
│  │ Institución │   │  Persona /  │ │
│  │  Hospital   │   │ Restaurante │ │
│  │ Supermercad│   │             │ │
│  │    o       │   │             │ │
│  │  [Login B2B]│   │ [Login B2C] │ │
│  └─────────────┘   └─────────────┘ │
│                                     │
└─────────────────────────────────────┘
```

### Pantalla 2: Catálogo B2B (con precio institucional)

```
┌──────────────────────────────────────┐
│ COFRIAL · Mi Catálogo Institucional  │
├──────────────────────────────────────┤
│ Bienvenido, Hospital Temuco          │
│ Tu descuento: 15%                    │
├──────────────────────────────────────┤
│ Filtrar por: ▼ Categoría             │
│             ▼ Temperatura            │
│             ▼ Disponibilidad         │
├──────────────────────────────────────┤
│                                      │
│ ┌────────────────────────────┐      │
│ │ Lomo Vetado 1kg            │      │
│ │ Temp: 0-4°C                │      │
│ │ Precio público: $12.000    │      │
│ │ Tu precio (B2B): $10.200   │ (-15%)
│ │ Stock: 45 unidades         │      │
│ │ [Agregar al carrito]       │      │
│ └────────────────────────────┘      │
│                                      │
│ ┌────────────────────────────┐      │
│ │ Pollo Entero 2kg           │      │
│ │ Temp: -18°C                │      │
│ │ Precio público: $8.500     │      │
│ │ Tu precio (B2B): $7.225    │ (-15%)
│ │ Stock: 120 unidades        │      │
│ │ [Agregar al carrito]       │      │
│ └────────────────────────────┘      │
│                                      │
│ [Carrito: 2 items] [$18.925]  [→]   │
└──────────────────────────────────────┘
```

### Pantalla 3: Seguimiento de pedido (con temperatura en vivo)

```
┌──────────────────────────────────────┐
│ Pedido #ORD-2026-1045                │
├──────────────────────────────────────┤
│ Cliente: Hospital Temuco             │
│ Fecha: 15-oct-2026 · 14:32           │
│                                      │
│ Estado:           EN RUTA            │
│ ├─ Confirmada     ✓ (15:05)          │
│ ├─ Preparando     ✓ (15:30)          │
│ ├─ Despachada     ✓ (16:20)          │
│ └─ En ruta →      ⏳ ETA: 16:50     │
│                                      │
│ Camión: TR-2205                      │
│ Temperatura: 3.8°C                   │ ✓ Verde (en rango)
│ Ubicación: Ruta 5 Sur, Km 12         │ 📍 Mapa
│ Combustible: 68%                     │
│                                      │
│ [Contactar al despachador]           │
│                                      │
└──────────────────────────────────────┘
```

**Nota:** si `temp_camara` > 4°C, el fondo pasa a rojo y aparece una alerta.

---

## Flujo de validaciones en el carrito

```
Cliente selecciona producto
        ↓
Sistema verifica stock en RDS en tiempo real
        ↓
¿Stock disponible?
  ├─ SÍ: Descuenta del stock virtual
  │      Precio se calcula según perfil (B2B/B2C)
  │      Item se agrega al carrito
  │
  └─ NO: Muestra mensaje "Stock disponible en 3 días"
         Opción: "¿Reservar?" (pone en espera)
```

---

## Próximas pantallas a diseñar (Hito 2)

- Detalle de producto (con especificaciones de temperatura)
- Checkout (dirección, pago)
- Confirmación de orden
- Perfil del cliente (historial, direcciones, facturas)
- Panel del vendedor en el CRM (ver órdenes de sus clientes)
- Torre de control (vista del despachador con flota en tiempo real)

Nota. Wireframes: borrador en texto. En el Hito 2 se harán en Figma o draw.io como figuras. Elaboración propia.
