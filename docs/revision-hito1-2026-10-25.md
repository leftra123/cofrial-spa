# Revisión del informe Hito 1 contra la implementación

Fecha: 25-oct-2026. Base revisada: main a5130bd, posterior al pull. Pauta: EVA2_3 Unidad 02, dimensiones D1–D4. Las decisiones versionadas se consideran adoptadas; no se solicita volver a elegir arquitectura.

## Cambios documentales

- Stack vigente: Django, plantillas, CSS propio, fetch, DRF, autenticación y migraciones; se retiran scaffold backend, HTMX y Tailwind como componentes actuales.
- Topología de tres subredes, Gunicorn/WhiteNoise, SSH, visor Grafana y respaldo de un día; diagrama PNG y draw.io consistentes.
- Cincuenta camiones en cinco contenedores; rutas hacia paradas, velocidad compartida, cierre manual y demostración forzada diferenciada.
- Asistente de tienda separado del clasificador; proveedores, presupuestos nominales, privacidad y límites por proceso.
- OC B2B diferida y carrito mixto dividido por conservación; RN-16 evita duplicar el identificador RN-09 del CRM.
- Pipeline sin saltos ni retrocesos y cambio explícito después de la interacción; bandeja de requerimientos compartida y orden propia opcional.
- Se conserva la relación reclamo–pedido. Se retira la afirmación universal de BCNF y se documenta la descomposición lógica normalizada junto con la excepción física; no se ejecuta una migración ni se cambia la aplicación.
- Diccionario ampliado con aviso_stock, campos de geolocalización, oc_pendiente, forzada y claves físicas Django.
- Gantt actualizado con avance al corte y planificación restante; Hito 1 jueves 05-nov-2026, Hito 2 12-nov-2026. Las ventanas históricas no se presentan como fechas certificadas.
- Integración completa del Word, índices, numeración continua y trazabilidad de la pauta; se retiran instrucciones de trabajo del cuerpo.

## Verificación local realizada

Se montó el código de web/ del checkout actual en modo de solo lectura sobre un contenedor de pruebas, con base de pruebas separada. La ejecución definitiva retiró DEMO_PASSWORD y ADMIN_PASSWORD del entorno de ese contenedor para utilizar las credenciales de fixtures previstas por cargar_demo. No se modificaron las cuentas de la aplicación en ejecución.

- Django: **191 pruebas, OK**, 87,156 s; incluye el chequeo de sistema sin incidencias.
- Simulador: **9 pruebas, OK**, 0,122 s, sin escrituras de telemetría.
- Script AWS: prueba con CLI ficticia y sintaxis Bash aprobadas; no se llamó a AWS real.
- Consulta local de solo lectura: **50 camiones, 50 con telemetría ordinaria de menos de 30 s** al comprobar.
- El primer intento heredó credenciales de demo ajenas a los fixtures y falló por autenticación; no se contabiliza como validación del sistema. Se repitió con el entorno de pruebas correcto.

Los dobles de IA de las pruebas no verifican las cuotas ni la disponibilidad actual de Gemini/Groq. El 20/20 del clasificador es un registro histórico del 22-oct-2026; no se ejecutaron llamadas nuevas de evaluación real. No se volvió a desplegar ni verificar esta revisión en AWS.

## Formato y fuentes

No se encontró Carta-1-vert.docx en la raíz. Se utiliza como referencia visual la plantilla INACAP adjunta TIHI84_U1_Plantilla_informe_Guía_ABPro.docx, con encabezado, pie y portada institucionales; se elimina su contenido de ejemplo sin adoptar su pauta de Proyecto de Título. La plantilla de referencia no se modifica.

Se contrastó el artículo 68 con la compilación de febrero de 2026 publicada por MINSAL; se evita inferir de él una obligación adicional de telemetría continua. Se comprobó la documentación oficial de Groq; las funciones descritas se sostienen principalmente en el código local y no se afirman modelos o cuotas permanentes.

El informe fuente 00 conserva la fecha del PDF original; la entrega y el Gantt adoptan la fecha del foro autorizada por el usuario. La calificación final corresponde al docente.

## Comprobación documental final

El Word renderizado contiene 117 páginas, 90 tablas y 27 figuras. Se comprobó la numeración continua, la coincidencia de las 137 entradas de índices con la paginación y la existencia de los destinos internos del paquete. No se detectaron caracteres fuera de los límites de página ni textos de instrucción de la plantilla en la entrega. Se revisaron las láminas de todas las páginas y las páginas críticas de Gantt, topología, normalización y pipeline en su render. Los 18 medios y partes customXml de la plantilla se conservaron sin cambios. El registro técnico de verificación se guarda en informe/exportar/verificacion-final.json.

La plantilla adjunta se conserva también en la raíz para que la generación sea reproducible sin depender de la carpeta Descargas. Los scripts locales nuevos y las instrucciones que aparecieron durante la revisión se preservaron; no se modificó la lógica de web/, iot/ ni los scripts de infraestructura.

La consulta local de consistencia entre requerimiento, orden y cliente devolvió cero filas inconsistentes. Se ajustaron los anchos de las tablas de telemetría y casos de uso para conservar los nombres completos y evitar letras aisladas.
