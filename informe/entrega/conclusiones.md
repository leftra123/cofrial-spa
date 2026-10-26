# Conclusiones

## Respuesta al problema

El equipo consultor concluye que el sistema implementado responde a los tres focos del caso mediante una persistencia común y flujos verificables. La aplicación y RDS separan los datos del servidor físico original; el stock y las órdenes dejan de depender de planillas independientes; la telemetría y su cruce con despachos hacen visible la cadena de frío; el portal y el CRM registran clientes, oportunidades y atención en un entorno empresarial.

El beneficio no se limita a reunir pantallas. La compra bloquea stock durante la transacción, conserva el precio contratado, valida la dirección y separa órdenes por conservación. El CRM restringe carteras y transiciones, exige motivo de pérdida y permite pedidos asistidos. El despacho comprueba compatibilidad y registra el cierre del viaje. La clasificación persiste el requerimiento antes de invocar a la IA y el asistente consulta información del perfil sin ejecutar compras.

## Decisiones y límites

Django, PostgreSQL, Python, Grafana, Gemini, Groq y Leaflet son decisiones ya implementadas. La documentación actualiza las alternativas abandonadas y explica sus trade-offs. La red compartida por web e IoT mantiene aislamiento mediante Security Groups; RDS privada mejora la protección de datos, aunque Single-AZ no ofrece alta disponibilidad. HTTP, Grafana público de solo lectura, respaldos mínimos y servicios externos sin garantía de disponibilidad delimitan el alcance académico.

El modelo conserva el vínculo entre requerimiento y orden. Su análisis distingue el núcleo normalizado, la dependencia condicional de la representación física y la descomposición lógica que evita repetir el cliente de una compra. La incorporación de autenticación Django, avisos de stock, coordenadas, OC pendiente y telemetría forzada se documenta para que el MER de referencia no se confunda con un inventario literal de la instalación.

## Evidencia y proyección

La prueba histórica de AWS del 22-oct-2026 respalda la instalación existente entonces. Las ampliaciones incorporadas hasta el 25 de octubre requieren comprobar en conjunto la misma revisión instalada antes de la defensa. La muestra histórica de veinte aciertos del clasificador no garantiza precisión universal ni certifica el chat. Las pruebas locales y las de simulación se informan con su alcance propio.

El Gantt actualizado concentra el trabajo restante en revalidación, correcciones, cierre del informe y ensayo de defensa; no presenta como construcción futura los componentes ya implementados. Los beneficios económicos, la puntualidad real y el abandono de canales informales deben medirse con Cofrial. La integración contable, sensores físicos, alta disponibilidad y automatizaciones de atención permanecen como evolución propuesta y no como capacidades actuales.
