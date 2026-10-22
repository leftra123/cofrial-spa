# Generador del informe en Word

Arma `informe/entrega/Informe_Hito1_Cofrial_SpA.docx` a partir de los `.md` de `informe/` (secciones 01 a 04d, más `informe/entrega/` para resumen, introducción, conclusiones, glosario y referencias) y los inyecta en la plantilla institucional de INACAP.

```bash
cd informe/exportar
npm install                              # una sola vez (instala la librería docx; node_modules no se sube)
node exportar-informe.js                 # escribe en "Entrega Hito 1/" (carpeta principal del proyecto)
node exportar-informe.js --salida=/ruta  # o en otra carpeta
node exportar-informe.js --compacto      # versión más corta
```

Requisitos:
- **Plantilla `Carta-1-vert.docx`** en la carpeta principal del proyecto (la que contiene `.claude/` y `Entrega Hito 1/`). No está en el repositorio.
- Node.js y Python 3.
- Cada referencia de `entrega/referencias.md` necesita una regla de cita en `exportar-informe.js` (constante `CITAS`) y solo se imprime si el texto la cita.
- Cada «Tabla N» o «Figura N» mencionada en un `.md` debe tener su título en ese mismo archivo, o el generador se detiene con «Referencia sin destino».
