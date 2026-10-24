# Prompts para crear las imágenes de producto con IA

Cómo usarlos: genera cada imagen (formato horizontal 4:3, mínimo 1200 px), guárdala como `web/static/productos/propias/<SKU>.jpg` (también sirve `.png` o `.webp`) y súbela al repositorio. La tienda la usa sola, antes que la foto de Commons y que la ilustración, y en el detalle indica «Imagen referencial generada con IA». No hace falta tocar código.

**Estilo común (pégalo al final de cada prompt):**
`Fotografía de producto de estudio, fondo blanco liso, luz suave y difusa, vista de tres cuartos desde arriba, sombra suave bajo el producto, alta nitidez, colores naturales, sin texto, sin marcas, sin manos, sin personas.`

**Regla:** siempre carne o alimento ya cortado y presentado como producto de supermercado o frigorífico; nunca animales vivos ni enteros en pie.

## Productos que hoy no tienen foto (usan una ilustración de IA)

| SKU | Archivo | Prompt |
|---|---|---|
| VAC-MOL-5K | `VAC-MOL-5K.jpg` | Bandeja blanca con carne molida de vacuno fresca, roja y con textura fina, envuelta en film transparente. |
| PES-MER-5K | `PES-MER-5K.jpg` | Tres filetes de merluza cruda sin piel, de carne blanca y brillante, sobre una bandeja con hielo picado. |
| MAR-CON-2K | `MAR-CON-2K.jpg` | Bolsa transparente de mariscos congelados mixtos (choritos, camarones, calamar en anillos y almejas) con escarcha. |
| LAC-MAN-10K | `LAC-MAN-10K.jpg` | Bloque rectangular de mantequilla amarilla envuelto a medias en papel blanco, con una esquina cortada. |

## Productos cuya foto actual es regular (conviene reemplazarla)

| SKU | Archivo | Prompt |
|---|---|---|
| VAC-POS-5K | `VAC-POS-5K.jpg` | Pieza entera de posta rosada de vacuno cruda, magra y de color rojo intenso, envasada al vacío. |
| PES-FIL-3K | `PES-FIL-3K.jpg` | Tres filetes de salmón crudo de color naranja con vetas blancas, sobre hielo, sin piel quemada ni cocción. |
| PAV-PEC-5K | `PAV-PEC-5K.jpg` | Pechuga de pavo cruda, deshuesada y rosada, en una bandeja blanca cubierta con film. |
| EMB-LON-4K | `EMB-LON-4K.jpg` | Tres longanizas ahumadas atadas, de color café rojizo, sobre fondo blanco. |
| CER-LOM-4K | `CER-LOM-4K.jpg` | Lomo de cerdo crudo entero, de color rosado claro con una fina capa de grasa, envasado al vacío. |
| COR-PIE-6K | `COR-PIE-6K.jpg` | Pierna de cordero cruda con hueso, de carne rojo oscuro y grasa blanca, lista para hornear. |

## Portada y categorías (opcionales)

| Uso | Archivo | Prompt |
|---|---|---|
| Fondo de portada | `web/static/img/portada.jpg` | Mesón de acero inoxidable de una cámara frigorífica limpia con cajas de carne y pollo ordenadas, luz fría azulada, vista amplia, sin personas. |
| Categoría Aves | `web/static/productos/propias/cat-aves.jpg` | Pollo entero crudo, trutros y pechugas dispuestos sobre una bandeja blanca. |
| Categoría Cárnicos | `web/static/productos/propias/cat-carnicos.jpg` | Cortes de vacuno y cerdo crudos (lomo, costillar, posta) dispuestos sobre fondo blanco. |
| Categoría Congelados | `web/static/productos/propias/cat-congelados.jpg` | Bolsas de pescado, verduras y papas congeladas con escarcha, sobre fondo blanco. |
| Categoría Lácteos y embutidos | `web/static/productos/propias/cat-lacteos.jpg` | Queso laminado, bloque de mantequilla y jamón cocido sobre fondo blanco. |

Las de portada y categorías son opcionales: hoy la portada y las categorías usan ilustraciones y no leen esos archivos todavía; pídele a la sesión de mejora visual que las incorpore si las generas.


## Estado de las imágenes propias (24-oct-2026)

Ya cargadas en `web/static/productos/propias/` (10): `VAC-LOM-5K`, `POL-PEC-10K`, `CER-COS-5K`, `PES-FIL-3K`, `VAC-POS-5K`, `CER-LOM-4K`, `COR-PIE-6K`, `POL-TRU-8K`, `POL-ENT-10K` y `PAV-PEC-5K`.

Faltan 10. Prompts en el mismo estilo que las ya hechas (vista desde arriba, fondo blanco, etiqueta en blanco sin texto, sin marcas):

| SKU | Archivo | Prompt |
|---|---|---|
| VAC-MOL-5K | `VAC-MOL-5K.jpg` | Fotografía de producto de estudio, vista cenital, fondo blanco, luz suave. Bandeja blanca de espuma con carne molida de vacuno cruda, roja y de textura fina, cubierta con film transparente y una etiqueta blanca en blanco, sin texto. |
| PES-MER-5K | `PES-MER-5K.jpg` | Mismo estilo. Bolsa al vacío transparente con tres filetes de merluza cruda sin piel, de carne blanca y brillante, con una etiqueta blanca en blanco. |
| MAR-CON-2K | `MAR-CON-2K.jpg` | Mismo estilo. Bolsa transparente de mariscos congelados mixtos (choritos, camarones, anillos de calamar y almejas) con escarcha, y una etiqueta blanca en blanco. |
| MAR-CAM-1K | `MAR-CAM-1K.jpg` | Mismo estilo. Bolsa transparente con camarones crudos pelados y congelados, con escarcha, y una etiqueta blanca en blanco. |
| VER-MIX-10K | `VER-MIX-10K.jpg` | Mismo estilo. Bolsa transparente grande de verduras mixtas congeladas (zanahoria en cubos, arvejas y choclo) con escarcha, y una etiqueta blanca en blanco. |
| PAP-FRI-10K | `PAP-FRI-10K.jpg` | Mismo estilo. Bolsa transparente de papas prefritas en bastón, congeladas y con escarcha, y una etiqueta blanca en blanco. |
| LAC-QUE-5K | `LAC-QUE-5K.jpg` | Mismo estilo. Paquete al vacío de láminas de queso gauda amarillo apiladas con papel separador, y una etiqueta blanca en blanco. |
| LAC-MAN-10K | `LAC-MAN-10K.jpg` | Mismo estilo. Bloque rectangular de mantequilla amarilla envuelto en papel blanco, con una esquina cortada a la vista y una etiqueta blanca en blanco. |
| EMB-JAM-3K | `EMB-JAM-3K.jpg` | Mismo estilo. Pieza entera de jamón cocido rosado envasada al vacío, con una etiqueta blanca en blanco. |
| EMB-LON-4K | `EMB-LON-4K.jpg` | Mismo estilo. Cuatro longanizas ahumadas de color café rojizo en una bandeja blanca cubierta con film transparente, con una etiqueta blanca en blanco. |
