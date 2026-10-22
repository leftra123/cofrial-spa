# 6. Casos de uso del ecosistema

Aporta a H1-D4 (arquitectura de canales y CRM). Sirve como guion para la demo del Hito 2.

## Formato y decisión

| Formato | Fortaleza | Limitación | Decisión |
|---|---|---|---|
| Diagrama UML + especificación textual | Muestra actores, límites y relaciones de un vistazo | Especificación completa es costosa (flows, alternativas) | Adoptada. Diagrama general + especificación de 3 casos críticos |
| Historias de usuario | Rápidas, orientadas al valor | Sin vista global de actores | Complementaria. Tarjetas en Trello |

Nota. Elaboración propia.

## Actores del sistema

| Actor | Tipo | Descripción | Interactúa con |
|---|---|---|---|
| Cliente B2B | Primario | Hospital, supermercado, institución con lista de precios institucional | E-commerce, CRM |
| Cliente B2C | Primario | Persona que compra a precio público | E-commerce |
| Vendedor | Primario | Gestiona cartera y prospectos | CRM, IA |
| Despachador | Primario | Supervisa flota y alertas de frío | Torre de control, BD |
| Gerencia | Primario | Consulta métricas | Dashboard BI |
| Simulador IoT | Sistema | Contenedores Docker que envían telemetría | BD (RDS) |
| Servicio de IA | Sistema externo | Clasifica requerimientos (NLP) | CRM, E-commerce |
| Base de datos (RDS) | Sistema | Único origen de verdad | Todos |

Nota. Elaboración propia.

## Catálogo de casos de uso (CU-01 a CU-13)

| ID | Caso de uso | Actor principal | Módulo | Prioridad | Rúbrica |
|---|---|---|---|---|---|
| CU-01 | Seleccionar perfil e iniciar sesión (B2B/B2C) | Cliente | E-commerce | Obligatorio | H2-D2 |
| CU-02 | Consultar catálogo de refrigerados con precio según perfil | Cliente | E-commerce | Obligatorio | H2-D2 |
| CU-03 | Gestionar carrito de compras | Cliente | E-commerce | Obligatorio | H2-D2 |
| CU-04 | Generar una orden | Cliente | E-commerce | Obligatorio | H2-D2 |
| CU-05 | Seguir estado del pedido en tiempo real | Cliente | E-commerce + BI | Extra | H2-D5 |
| CU-06 | Gestionar clientes (CRUD, historial) | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-07 | Gestionar prospectos y avanzar etapas del pipeline | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-08 | Hacer seguimiento de pedidos web | Vendedor | CRM | Obligatorio | H2-D2 |
| CU-09 | Registrar requerimiento y clasificarlo con IA | Cliente/Vendedor | CRM + IA | Obligatorio | H2-D5 |
| CU-10 | Enviar telemetría del camión automáticamente | Simulador IoT | IoT | Obligatorio | H2-D3 |
| CU-11 | Detectar ruptura de cadena de frío | Sistema | IoT + Alertas | Obligatorio | H2-D3 |
| CU-12 | Monitorear flota y alertas en tiempo real | Despachador | Torre de control | Extra | H2-D4 |
| CU-13 | Consultar dashboard de ventas y cadena de frío | Gerencia | BI | Obligatorio | H2-D4 |

Nota. Elaboración propia. "Obligatorio" refiere a lo exigido en la pauta del Hito 2.

## Especificaciones de casos críticos

### CU-04: Generar una orden

**Actor:** Cliente B2B o B2C.
**Precondición:** cliente autenticado, carrito no vacío.

**Flujo normal:**
1. Cliente revisa el carrito (producto, cantidad, precio).
2. Ingresa datos de despacho (dirección, fecha deseada, contacto).
3. Selecciona método de pago (crédito empresa / tarjeta / transferencia).
4. Sistema **valida el stock** de todas las líneas en RDS.
5. En una misma transacción, **genera la orden** con estado "Recibida" y **descuenta el stock**.
6. Sistema **crea un registro en CRM** vinculado al cliente.
7. Sistema **envía confirmación** por correo y dentro del e-commerce.
8. **Postcondición:** orden visible en CRM, inventario actualizado.

**Flujo alternativo 1 (sin stock):**
- Paso 4 falla: stock < cantidad solicitada en alguna línea.
- Sistema **no genera la orden** ni descuenta stock.
- Informa al cliente qué líneas no alcanzan y ofrece ajustar la cantidad o elegir otro producto.

**Reglas de negocio:**
- Precio B2B: según lista institucional del cliente.
- Precio B2C: precio público + IVA.
- Descuento por volumen: > 100 unidades = -10 %.

---

### CU-09: Clasificar un requerimiento con IA

**Actor:** Cliente registra una consulta; IA clasifica.
**Precondición:** requerimiento ingresado en e-commerce o CRM.

**Flujo normal:**
1. Cliente o vendedor ingresa texto: "El último pedido llegó con temperatura elevada".
2. Sistema envía al API de Gemini (o alternativa): `{texto, cliente_id}`.
3. IA **clasifica** en una de: RECLAMO | COTIZACIÓN | DESPACHO | CALIDAD O FRÍO | OTRO.
4. Sistema **enruta** al área responsable:
   - RECLAMO → Atención al cliente.
   - COTIZACIÓN → Vendedor asignado.
   - DESPACHO → Despachador.
   - CALIDAD O FRÍO → Gerencia operativa.
5. Área recibe **notificación en el CRM** con contexto.
6. **Postcondición:** requerimiento clasificado, responsable asignado, tiempo registrado.

**Flujo alternativo (API no responde):**
- IA no responde en 5 segundos.
- Sistema deja requerimiento en estado "Sin clasificar".
- Notifica al supervisor: "Revisar manualmente".

**Regla:** la clasificación automática debe lograr > 85 % de acierto en la demo.

**Implementación en el prototipo (22-oct-2026).** Lo construido cubre el núcleo del caso de uso y se aparta del diseño en tres puntos:

- **Qué se hace:** el cliente registra su consulta en la sección Soporte del portal; el sistema la guarda siempre y la envía a Gemini, que devuelve una categoría y una confianza. Si la confianza es de 0,60 o más, el requerimiento queda clasificado y aparece en el CRM con su categoría y la confianza de la IA; si es menor o la API falla, queda «sin clasificar» y el vendedor lo clasifica a mano o pulsa «Clasificar con IA» para reintentar.
- **Categorías:** el prototipo usa cinco (Consulta de producto, Reclamo por temperatura, Atraso en entrega, Facturación y Otro), más cercanas a las consultas reales que las del diseño original.
- **Lo que no se implementó:** el enrutamiento automático por área (paso 4) y la notificación al supervisor cuando la IA falla. Hoy existe una bandeja única de requerimientos en el CRM, que ve el vendedor, y el contador de «requerimientos por clasificar» del panel.
- **Tiempo máximo:** el diseño fijaba 5 segundos. La latencia medida de Gemini es de 4 a 7 segundos por consulta, por lo que con ese plazo casi todas las consultas habrían quedado sin clasificar. El prototipo concede **12 segundos en total**, repartidos entre los modelos de respaldo.
- **Proveedor:** Gemini con la clave gratuita y, de respaldo, Groq si se configura su clave. Si un modelo de Gemini está saturado se prueba el siguiente de una lista configurable.
- **Medición de la regla del 85 %:** con 20 mensajes etiquetados y la API real se obtuvo **90 % (18 de 20)**. Las 18 respuestas recibidas fueron correctas; las otras 2 no tuvieron respuesta de Google (una por demora y otra por saturación), por lo que el sistema las habría dejado sin clasificar. El margen sobre la meta es estrecho y depende de la disponibilidad del proveedor gratuito.
- **Cómo repetir la medición:** `python manage.py probar_ia` verifica la clave y `python manage.py evaluar_ia` calcula el acierto sobre el conjunto de ejemplos.

---

### CU-11: Detectar ruptura de cadena de frío

**Actor:** Sistema IoT y plataforma.
**Precondición:** camión en ruta, telemetría llegando cada 5 segundos.

**Flujo normal:**
1. IoT envía: `{camion_id: "TR-2205", temp_camara: 4.2, lat: -38.74, long: -72.59, ...}`.
2. Sistema inserta en RDS tabla `telemetria`.
3. Sistema **verifica el rango del camión** (`rango_temperatura`): para refrigerados, 0 °C a 4 °C.
4. **Compuerta:** ¿`temp_camara` sale de ese rango?
   - Si SÍ: `alerta_ruptura_frio = true` en la BD.
   - Si NO: continúa normal.
5. Si alerta: sistema **notifica inmediatamente:**
   - Despachador en la torre de control (resalta en rojo).
6. Despachador puede:
   - Desviar a parada refrigerada (actualiza ruta).
   - Contactar al cliente (cambiar hora entrega).
7. **Postcondición:** alerta documentada en `telemetria`, merma evitada o mitigada.

**Regla:** alerta debe llegar en < 2 minutos de ocurrir el evento.

---

## Diagrama de casos de uso

**Figura 1**
*Casos de uso del ecosistema Cofrial*

![Diagrama de casos de uso de Cofrial SpA](img/casos-de-uso.png)

Nota. Elaboración propia.
