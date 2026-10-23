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
