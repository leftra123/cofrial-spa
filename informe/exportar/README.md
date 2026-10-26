# Generación del informe Hito 1

El exportador integra todas las secciones del informe, los casos de uso en el Anexo D y el diccionario con sus extensiones físicas. Numeración continua de tablas/figuras y referencias cruzadas validadas al generar.

Requiere Node con docx y Python con lxml (pypdf para los índices y Pillow para las figuras). Se ejecuta `node informe/exportar/exportar-informe.js --plantilla=/ruta/plantilla.docx`. La salida por defecto es `informe/entrega/Informe_Hito1_Cofrial_SpA.docx`; `--salida=/ruta` permite otra carpeta y `COFRIAL_PYTHON` selecciona el intérprete Python.

Se busca Carta-1-vert.docx en la raíz. Si no existe, puede indicarse la plantilla INACAP adjunta; su formato no sustituye la pauta EVA2_3. Las instrucciones académicas de ejemplo de la plantilla se retiran del documento final.

Las figuras de topología, Gantt, pipeline y normalización se regeneran con `informe/img/generar-figuras-vigentes.py` (Pillow). El Gantt lee la tabla del cronograma. El diseño SQL académico no se aplica a una base Django: la instalación utiliza sus migraciones.

Los índices estáticos se obtienen del PDF de comprobación con `actualizar-indices.py /ruta/render.pdf` y se regenera el Word hasta estabilizar páginas. El DOCX definitivo no se guarda mediante LibreOffice; el render es solo una comprobación visual.
