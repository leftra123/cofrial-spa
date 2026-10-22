# Conclusiones

## Hallazgos principales

El análisis muestra que los tres focos críticos de Cofrial comparten una causa raíz: la operación no genera ni conserva un dato único, en línea y confiable. Por eso la solución se organiza en torno a una base de datos central a la que escriben el portal de ventas y los camiones, y de la que leen el CRM y el tablero de BI.

Del diseño se desprenden cinco resultados:

- **La arquitectura responde al caso y no solo a la pauta.** Cada decisión de red, seguridad, cómputo y base de datos se amarra a un dolor concreto: la base de datos queda en una subred privada porque sus datos son el activo de la empresa, y los respaldos automáticos reemplazan al respaldo manual que hoy depende de una persona.
- **Las restricciones del laboratorio se convirtieron en decisiones explícitas.** La imposibilidad de usar Multi-AZ en RDS, el rol único `LabRole` y la falta de un dominio para HTTPS se declaran como límites del prototipo, con su mitigación y su contraparte en producción.
- **El modelo de datos soporta los dos mundos que exige la pauta.** Las 25 tablas en tercera forma normal cubren transacciones comerciales, CRM y telemetría, y la base las valida: el esquema carga sin errores, las consultas del tablero devuelven los montos esperados y quince inserciones inválidas son rechazadas.
- **Los canales y el CRM tienen lógica de negocio, no solo pantallas.** Quince reglas numeradas, un pipeline con transiciones permitidas, permisos por rol y eventos entre componentes explican cómo la cartera pasa a ser de la empresa y cómo se vuelve innecesario el canal informal.
- **El impacto se dimensiona con transparencia.** El modelo de pérdidas por ruptura de frío indica el orden de magnitud y el valor de detectar a tiempo, con parámetros que se reemplazan por datos reales.

## Desafíos y riesgos

El principal desafío es el calendario: solo hay ocho días entre los dos hitos, y el prototipo debe estar desplegado y estable en un entorno donde las instancias pueden detenerse al cerrar la sesión. El equipo lo mitiga adelantando el esqueleto de la aplicación y el simulador durante las semanas de redacción, y diseñando servicios que arrancan solos. El segundo desafío es que las cifras de impacto, los umbrales del CRM y las emociones de los recorridos son estimaciones del equipo; su validez depende de contrastarlas con Cofrial.

## Lecciones del diseño

Revisar el diseño con pruebas reales rindió más que revisarlo solo leyéndolo. Al verificar la tercera forma normal apareció una dependencia transitiva en la tabla de órdenes, donde el cliente se deducía de la dirección de entrega; se corrigió antes de entregar. Al detallar el pipeline faltaban tres campos (fecha de cierre y motivo de pérdida de un prospecto, y fecha de respuesta de un requerimiento) sin los cuales no se podían exigir las reglas ni medir los indicadores. Ambos hallazgos confirman el valor de mantener el modelo, los diagramas y los criterios de aceptación en un solo lugar, regenerable.

Otra lección es que conviene decidir la herramienta por lo que el equipo debe escribir y defender, y no solo por su popularidad. La evaluación ponderada llevó a cambiar la propuesta inicial de framework web: Django, con su administración, autenticación y migraciones incluidas, reduce lo que hay que construir a mano en cinco semanas.

## Avance hacia el Hito 2

El diseño ya se construyó y se desplegó en AWS Academy, y se verificó de punta a punta sobre esa instalación: compras de clientes institucionales y del público generan órdenes en la base, el CRM las muestra, los contenedores de la instancia dedicada insertan la telemetría con los seis campos exigidos, el tablero cruza ventas por canal con las alertas de frío y la clasificación de requerimientos con IA alcanzó un acierto de 100 % sobre veinte mensajes de prueba (90 % usando solo Gemini; el respaldo con Groq resolvió las consultas que el primero no alcanzó a responder). La sección 4 detalla en qué se apartó el despliegue del diseño (entre otros, una subred pública compartida, el tablero abierto al público y respaldos mínimos), y todas esas diferencias son limitaciones declaradas.

Construir también dejó lecciones que el diseño solo no mostraba. Los permisos del terminal integrado del laboratorio no alcanzan para crear recursos y hay que usar el rol del usuario; la capa gratuita de la IA cambia con rapidez (el modelo elegido primero ya no estaba disponible), de modo que el nombre del modelo se configura y se prueba en cascada; y los servicios gratuitos tienen una disponibilidad que justificó incorporar un proveedor de respaldo. Antes de la defensa quedan por hacer el ensayo del apagado y encendido del laboratorio, el guion de la demostración y la validación con Cofrial de los supuestos de impacto y de adopción.

## Cierre

La transformación digital de Cofrial no consiste en reemplazar planillas por un sitio web, sino en que cada pedido, cada lectura de temperatura y cada contacto comercial queden registrados en un lugar que pertenece a la empresa. El diseño presentado define cómo lograrlo con herramientas gratuitas, decisiones justificadas y límites declarados, y deja a la consultora en condiciones de demostrarlo en funcionamiento.
