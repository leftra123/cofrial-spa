# 1. Diagnóstico y análisis del dolor

Rúbrica H1-D1 (Logrado): analizar **en profundidad** (no repetir el caso) y argumentar con solidez técnica y de negocio.

## Síntesis de los tres focos críticos

| Foco | Hechos observables | Causa raíz | Impacto de negocio |
|---|---|---|---|
| On-premises vulnerable y silos | Un servidor físico en bodega, sin redundancia; contabilidad cerrada; inventario en Excel locales | Acumulación de deuda tecnológica sin inversión en integración | Riesgo de pérdida total de datos; inventario descuadrado permanente → compras incorrectas |
| Última milla a ciegas | 50 camiones sin GPS ni registros automáticos de temperatura; coordinación por llamadas y WhatsApp | Falta de trazabilidad digital y automatización de monitoreo | Entregas fallidas; mermas millonarias semanales por ruptura de frío no detectada |
| Sin canales digitales ni CRM | Pedidos por teléfono/correo; cartera en celulares de vendedores | Ausencia de un sistema único de gestión comercial | Pedidos perdidos; sin embudo de ventas; la cartera se va con el vendedor; sin métricas |

**Figura 1**
*Árbol de problemas: causas y efectos de los tres focos críticos*

![Árbol de problemas de Cofrial SpA](img/d1-arbol-problemas.png)

Nota. Elaboración propia.

## Análisis profundo por foco

### 1. Infraestructura on-premises: punto único de fallo y silos de información

**El problema no es "falta de nube" sino la falta de un único punto de verdad.**

Cofrial depende de un servidor físico ubicado en una bodega central. Aunque parezca una decisión puramente técnica de "dónde alojar", el verdadero problema es que esta arquitectura **impide la integración de datos**. 

- Contabilidad opera en un sistema cerrado con su propia BD, desconectada de bodega.
- Bodega maneja existencias en planillas Excel locales, que no se sincronizan con contabilidad.
- El resultado: cuando se recibe un pedido, nadie sabe en tiempo real si hay stock. Se consulta la planilla, pero esa planilla puede estar desactualizada respecto a lo que contabilidad acaba de registrar como vendido.

**Consecuencia financiera:** compras duplicadas, faltantes inesperados, stock comprometido por mermas que nadie detecta. Cada vez que el servidor falla (y algún día falla), todo se detiene y los datos de los últimos días se pierden.

**Riesgo de cumplimiento:** los clientes hospitalarios exigen trazabilidad documentada de la cadena de frío. Hoy no existe. Si un hospital sufre un evento de salud pública porque un producto llegó fuera de temperatura sin que Cofrial lo detectara, la responsabilidad legal y la reputación están en riesgo.

### 2. Última milla sin trazabilidad: mermas silenciosas por ruptura de frío

**El problema no es "los camiones necesitan GPS" sino que la información de la operación nunca llega a quien decide.**

Los 50 camiones frigoríficos salen sin registro automático de temperatura ni coordenadas. El despachador coordina rutas por teléfono y WhatsApp personales. El conductor es el único que "sabe" si la temperatura sube, pero no hay protocolo de alarma.

**Flujo actual (rotura de lógica de negocio):**
1. Temperatura sube durante el viaje.
2. Si el conductor lo nota, llamará al despachador (que está en otra tarea).
3. El despachador intenta contactar al cliente o redirige el camión.
4. **O nada de esto sucede**, porque el conductor no verificó, o estaba en zona sin cobertura, o la llamada no pasó.
5. El cliente recibe una carga fuera de especificación y rechaza la entrega.
6. La merma ya ocurrió y nadie la registró; solo aparece como una devolución sin causa documentada.

**Impacto cuantificable (del enunciado):** mermas millonarias **semanales**. Esto no es un número menor. En una región donde la cadena de frío es crítica, esa cifra sugiere que entre el 5 % y el 15 % de la carga transportada se pierde sin documentación de causa.

**Shadow IT extrema:** la coordinación real de la flota vive en WhatsApp, no en ningún sistema oficial. Los despachadores no son reemplazables; la información de "dónde está cada camión" muere con ellos.

### 3. Ausencia de canales digitales y CRM: pérdida de oportunidades comerciales

**El problema no es "no tenemos un website" sino que el conocimiento de cliente está fragmentado.**

Hoy, un cliente institucional (hospital, supermercado) hace un pedido por teléfono al vendedor. El vendedor anota en un papel o en un correo, o **lo guarda en su celular personal**. Cuando ese vendedor se va (por cambio de puesto, rotación, renuncia), toda la relación comercial y el historial se pierden. La empresa no tiene registro centralizado de:

- Quién es cada cliente, su historial de compras, su crédito.
- En qué etapa de conversación está cada oportunidad (prospecto inicial, propuesta enviada, negociando precio).
- Quién contactó a quién y cuándo.

**Consecuencia comercial:** no hay métricas de conversión, tasa de cierre ni pipeline visible. La gerencia no puede ver que una oportunidad lleva 3 meses sin avance. El equipo de ventas no puede coordinarse para no duplicar visitas. Los prospectos se pierden.

**Riesgo operativo:** los pedidos desordenados llegan a contabilidad y bodega sin estructura. ¿Es un pedido recurrente o puntual? ¿Cuál es el cliente? ¿Hay una PO (orden de compra) o es verbal? Sin canales digitales, la información siempre es incompleta.

## Cómo estos tres dolores se refuerzan entre sí

1. El servidor on-premises impide que bodega vea órdenes en tiempo real → responde tardíamente → mermas en tránsito porque el cliente pierde la confianza.
2. La última milla sin trazabilidad no produce datos → no hay histórico de qué camiones/ rutas / horarios generan mermas → se repite el error.
3. El CRM inexistente permite que un vendedor pierda un cliente sin que la empresa lo sepa → se pierde la oportunidad de optimizar esa ruta o renegociar términos.

**Figura 2**
*Ciclo de refuerzo entre los tres dolores*

![Ciclo de refuerzo entre infraestructura, última milla y ausencia de CRM](img/d1-ciclo-refuerzo.png)

Nota. Elaboración propia.

## Conclusión del diagnóstico

Los tres problemas no son independientes. Juntos forman un ciclo de degradación: datos fragmentados → decisiones pobres → operación ineficiente → clientes insatisfechos → pérdida de ingresos.

La solución no es "poner AWS", sino **integrar la información en un único flujo de negocio**, donde:
- Un pedido genera automáticamente una orden en el CRM.
- Un camión en ruta reporta temperatura → alerta si sale del rango → se documenta.
- Un vendedor cierra una oportunidad → aparece en BI para medir la tasa de conversión.

Nota. Elaboración propia.
