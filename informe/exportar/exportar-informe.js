/**
 * Genera el informe del Hito 1 en Word (APA 7) a partir de los archivos .md de informe/.
 *
 *   cd informe/exportar && npm install && node exportar-informe.js
 *
 * Salida: informe/entrega/Informe_Hito1_Cofrial_SpA.docx
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  BorderStyle, ImageRun, Header, PageNumber, PageOrientation, SectionType, TableOfContents, SimpleField, LevelFormat,
  VerticalAlign, LineRuleType,
} = require("docx");

const RAIZ = path.resolve(__dirname, "..");
const FUENTE = "Calibri";
const ROJO = "000000";
const ANCHO_VERT = 9404;         // ancho útil en DXA (carta, márgenes laterales de 851 como la plantilla)
const PX_VERT = { w: 625, h: 710 };   // máximo de una figura en página vertical (px a 96 dpi)
const PX_HORIZ = { w: 865, h: 425 };  // máximo en página horizontal

// ------------------------------------------------------------------------------------------
// Estructura del informe
// ------------------------------------------------------------------------------------------
const SECCIONES = [
  { id: "intro", file: "entrega/introduccion.md", titulo: "Introducción", sinSalto: true },
  { id: "01", file: "01-diagnostico.md", titulo: "Diagnóstico y análisis del dolor" },
  { id: "05", file: "05-procesos-bpmn.md", titulo: "Procesos actuales y propuestos" },
  { id: "02", file: "02-propuesta-valor.md", titulo: "Propuesta de valor y resolución de conflictos" },
  { id: "07", file: "07-metodologia-cronograma.md", titulo: "Metodología y cronograma" },
  { id: "08", file: "08-herramientas.md", titulo: "Evaluación de herramientas" },
  { id: "03", file: "03-arquitectura-cloud.md", titulo: "Memoria de decisiones de arquitectura cloud" },
  { id: "04a", file: "04a-diagrama-arquitectura.md", titulo: "Diagrama de arquitectura cloud" },
  { id: "04b", file: "04b-modelo-datos.md", titulo: "Modelo de datos: MER en tercera forma normal" },
  { id: "04c", file: "04c-canales-b2b-b2c.md", titulo: "Arquitectura de canales: wireframes y recorridos de usuario" },
  { id: "04d", file: "04d-crm.md", titulo: "Arquitectura funcional del CRM y pipeline comercial" },
  { id: "04e", file: "04e-plan-despliegue.md", titulo: "Plan de despliegue y verificación" },
  { id: "concl", file: "entrega/conclusiones.md", titulo: "Conclusiones", sinSalto: true },
];
const NUM_SECCION = {};
SECCIONES.forEach((s, i) => { NUM_SECCION[path.basename(s.file)] = i + 1; });
NUM_SECCION["06-casos-de-uso.md"] = "del Anexo D";

const COMPACTO = process.argv.includes("--compacto");
// En la versión compacta se omiten subsecciones y figuras de apoyo que la pauta no exige
const OMITIR_H = !COMPACTO ? {} : {
  "04b-modelo-datos.md": [/^Cómo responde el modelo/],
  "06-casos-de-uso.md": [/^Formato/, /^Especificaciones de los casos/],
  "05-procesos-bpmn.md": [/^Proceso 3/],
  "08-herramientas.md": [/^Simulación IoT/, /^Dashboard de BI/, /^Servicio de IA/, /^Diagramas de arquitectura/],
  "04a-diagrama-arquitectura.md": [/^Vista simplificada/],
  "04b-modelo-datos.md": [/^Cómo responde el modelo/],
  "07-metodologia-cronograma.md": [/^Metodología$/, /^Gestión en Trello/, /^Herramientas de gestión/],
};
const OMITIR_CAPTION = !COMPACTO ? [] : [/^Cronograma de actividades/, /^W3\./, /^W5\./, /^W9\./];
const omitida = b => b.tipo === "caption" && OMITIR_CAPTION.some(re => re.test(b.titulo));
const corpus = [];
const captionsImpresos = [];
const SALTAR = /^(Notas del equipo|Pendiente|Por verificar|Estado\b|Código del diagrama)/i;

// ------------------------------------------------------------------------------------------
// Lectura de Markdown
// ------------------------------------------------------------------------------------------
function leerBloques(texto, omitir = []) {
  const lineas = texto.replace(/\r/g, "").split("\n");
  const bloques = [];
  let i = 0;
  let saltarNivel = null;
  let anexoA = null;
  while (i < lineas.length) {
    const l = lineas[i];
    if (/^<details>/.test(l.trim())) { while (i < lineas.length && !/<\/details>/.test(lineas[i])) i++; i++; continue; }
    if (/^<!--/.test(l.trim())) { i++; continue; }
    if (/^```/.test(l)) { i++; while (i < lineas.length && !/^```/.test(lineas[i])) i++; i++; continue; }
    const h = l.match(/^(#{1,3}) (.*)$/);
    if (h && anexoA && anexoA.activo && h[1].length === 3) { anexoA.lineas.push(l); i++; continue; }
    if (h) {
      const nivel = h[1].length, titulo = h[2].trim();
      if (saltarNivel !== null && nivel > saltarNivel) { i++; continue; }
      saltarNivel = null;
      if (anexoA && nivel <= 2) anexoA.activo = false;
      if (nivel === 1) { i++; continue; }
      if (SALTAR.test(titulo) || omitir.some(re => re.test(titulo))) { saltarNivel = nivel; i++; continue; }
      if (/^Diccionario de datos/.test(titulo)) {
        // El diccionario se imprime íntegro en el Anexo A; no crear una página de remisión aislada.
        anexoA = { activo: true, lineas: [] };
        i++; continue;
      }
      bloques.push({ tipo: "h", nivel, texto: titulo });
      i++; continue;
    }
    if (saltarNivel !== null) { i++; continue; }
    if (anexoA && anexoA.activo) { anexoA.lineas.push(l); i++; continue; }
    if (/^>/.test(l)) { while (i < lineas.length && /^>/.test(lineas[i])) i++; continue; }
    if (l.trim() === "") { i++; continue; }
    if (/^\|/.test(l)) {
      const filas = [];
      while (i < lineas.length && /^\|/.test(lineas[i])) { filas.push(lineas[i]); i++; }
      const celdas = f => f.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const cuerpo = filas.filter((f, k) => k !== 1).map(celdas);
      bloques.push({ tipo: "tabla", filas: cuerpo });
      continue;
    }
    const img = l.match(/^!\[(.*?)\]\((.*?)\)\s*$/);
    if (img) { bloques.push({ tipo: "img", alt: img[1], ruta: img[2] }); i++; continue; }
    if (/^(- |\d+\. )/.test(l)) {
      const ordenada = /^\d+\. /.test(l);
      const items = [];
      while (i < lineas.length && /^( {0,3}- |\d+\. | {2,}- )/.test(lineas[i])) {
        const nivel = /^ {2,}- /.test(lineas[i]) ? 1 : 0;
        let it = lineas[i].replace(/^( {2,}- |- |\d+\. )/, "");
        i++;
        while (i < lineas.length && /^ {2,}[^\s-]/.test(lineas[i])) { it += " " + lineas[i].trim(); i++; }
        if (/^\[ \] /.test(it)) continue;
        items.push({ t: it.replace(/^\[x\] /, ""), nivel });
      }
      if (items.length) bloques.push({ tipo: "lista", ordenada, items });
      continue;
    }
    // párrafo
    const par = [];
    while (i < lineas.length && lineas[i].trim() !== "" && !/^(#|\||>|- |\d+\. |!\[|```|<)/.test(lineas[i])) { par.push(lineas[i].replace(/\s+$/, "")); i++; }
    if (!par.length) { i++; continue; }
    const cap = par[0].match(/^\*\*(Tabla|Figura) ([A-Z]?\d+)\*\*$/);
    if (cap && par.length >= 2) {
      bloques.push({ tipo: "caption", etiqueta: cap[1], local: cap[2], titulo: par.slice(1).join(" ").replace(/^\*|\*$/g, "") });
    } else if (/^\*?Nota\.\*?/.test(par[0])) {
      bloques.push({ tipo: "nota", texto: par.join(" ") });
    } else {
      bloques.push({ tipo: "p", texto: par.join(" ") });
    }
  }
  // Completar captions y notas de tablas que no traían rótulo en la fuente.
  let localAuto = 1000;
  for (let j = 0; j < bloques.length; j++) {
    if (bloques[j].tipo !== "tabla") continue;
    if (!bloques[j - 1] || bloques[j - 1].tipo !== "caption") {
      const h = bloques.slice(0, j).reverse().find(x => x.tipo === "h");
      bloques.splice(j, 0, { tipo: "caption", etiqueta: "Tabla", local: String(++localAuto), titulo: h ? h.texto : "Datos del sistema" });
      j++;
    }
    if (!bloques[j + 1] || bloques[j + 1].tipo !== "nota") bloques.splice(j + 1, 0, { tipo: "nota", texto: "Nota. Elaboración propia." });
  }
  return { bloques, anexoA: anexoA ? anexoA.lineas : null };
}

// ------------------------------------------------------------------------------------------
// Numeración global y referencias cruzadas
// ------------------------------------------------------------------------------------------
const numeros = {};         // "archivo|Tabla|local" -> número global
let nTabla = 0, nFigura = 0;
function asignar(archivo, etiqueta, local) {
  const n = etiqueta === "Tabla" ? ++nTabla : ++nFigura;
  numeros[`${archivo}|${etiqueta}|${local}`] = n;
  return n;
}
function num(archivo, etiqueta, local) {
  const v = numeros[`${archivo}|${etiqueta}|${local}`];
  if (v === undefined) throw new Error(`Referencia sin destino: ${archivo} ${etiqueta} ${local}`);
  return v;
}
function limpiar(texto, archivo) {
  let t = texto;
  // Una sola pasada: así un número ya traducido no se vuelve a traducir
  t = t.replace(/(Tabla|Figura) (\d+) de `(?:informe\/)?([\w-]+\.md)`|Tablas (\d+) y (\d+)|\b(Tabla|Figura) (\d+)\b/g,
    (m, e1, n1, f1, a2, b2, e3, n3) => {
      if (e1) return `${e1} ${num(f1, e1, n1)}`;
      if (a2) return `Tablas ${num(archivo, "Tabla", a2)} y ${num(archivo, "Tabla", b2)}`;
      return `${e3} ${num(archivo, e3, n3)}`;
    });
  t = t.replace(/`(?:informe\/)?([\d]{2}[a-e]?-[\w-]+\.md)`/g, (m, f) => {
    const s = NUM_SECCION[f];
    if (!s) throw new Error("Archivo sin sección: " + f);
    return typeof s === "string" ? s : `la sección ${s}`;
  });
  t = t.replace(/la la sección/g, "la sección").replace(/(?:la sección |sección )del Anexo D/g, "el Anexo D");
  t = t.replace(/\b(?:borrador|borradores)\b/gi, "diseño");
  t = t.replace(/(\d) %/g, "$1\u00A0%");
  t = t.replace(/Borrador pendiente de validación del equipo\.\s*/g, "");
  corpus.push(t);
  return t;
}

// ------------------------------------------------------------------------------------------
// Texto en línea
// ------------------------------------------------------------------------------------------
function runs(texto, estilo = {}) {
  const salida = [];
  const partes = texto.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g).filter(p => p !== "");
  for (const p of partes) {
    if (/^\*\*[^*]+\*\*$/.test(p)) salida.push(...runs(p.slice(2, -2), { ...estilo, bold: true }));
    else if (/^\*[^*]+\*$/.test(p)) salida.push(...runs(p.slice(1, -1), { ...estilo, italics: true }));
    else if (/^`[^`]+`$/.test(p)) salida.push(new TextRun({ ...estilo, text: p.slice(1, -1), font: "Consolas", size: Math.max(16, (estilo.size || 24) - 2) }));
    else salida.push(new TextRun({ ...estilo, text: p }));
  }
  return salida;
}

// ------------------------------------------------------------------------------------------
// Imágenes
// ------------------------------------------------------------------------------------------
function dimsPng(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function escalaPx(nombre) {
  if (/^wf-/.test(nombre)) return 1.5;
  if (/^journey-/.test(nombre)) return 1.2;
  if (/\.drawio\.png$/.test(nombre)) return /^bpmn-/.test(nombre) ? 2 : 1;
  if (/visual-check/.test(nombre)) return 1;
  return 2; // Mermaid, MER y Gantt
}
function cargarImagen(rutaRel) {
  const ruta = path.resolve(RAIZ, rutaRel);
  const buf = fs.readFileSync(ruta);
  const d = dimsPng(buf);
  const nombre = path.basename(ruta);
  const css = { w: d.w / escalaPx(nombre), h: d.h / escalaPx(nombre) };
  return { buf, px: d, css, nombre };
}
function esApaisada(img) { return img.css.w > 1000; }
function ajustar(img, max) {
  const k = Math.min(max.w / img.css.w, max.h / img.css.h, 1.6);
  return { width: Math.round(img.css.w * k), height: Math.round(img.css.h * k) };
}

// ------------------------------------------------------------------------------------------
// Componentes de documento
// ------------------------------------------------------------------------------------------
const SANGRIA = 720;
const parrafoBase = { indent: { firstLine: 567 }, alignment: AlignmentType.JUSTIFIED, spacing: { line: 276, lineRule: LineRuleType.AUTO, after: 80 } };
let nListaNum = 0;
const configsNum = [];

function parrafo(texto) { return new Paragraph({ ...parrafoBase, children: runs(texto, { font: FUENTE, size: 22 }) }); }
function lista(b) {
  let ref = "vinetas";
  if (b.ordenada) { ref = `num-${++nListaNum}`; configsNum.push({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }, { level: 1, format: LevelFormat.LOWER_LETTER, text: "%2)", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }] }); }
  return b.items.map(it => new Paragraph({
    numbering: { reference: ref, level: it.nivel || 0 },
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 276, after: 80 },
    children: runs(it.t, { font: FUENTE, size: 22 }),
  }));
}
function encabezado(b, numeracion) {
  const nivel = b.nivel;
  const niv = nivel === 1 ? HeadingLevel.HEADING_1 : nivel === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
  const tam = nivel === 2 ? 28 : 24;
  return new Paragraph({ heading: niv, spacing: { before: 240, after: 100 }, alignment: AlignmentType.LEFT, keepNext: true,
    children: [new TextRun({ text: (numeracion ? numeracion + " " : "") + b.texto, font: FUENTE, size: tam, color: ROJO, bold: nivel === 3 })] });
}
function tituloH1(texto, numero, salto = true) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: salto, alignment: AlignmentType.CENTER, spacing: { before: 240, after: 200 },
    children: [new TextRun({ text: numero ? `${numero}. ${texto}` : texto, font: FUENTE, size: 32, color: ROJO })] });
}
function caption(etiqueta, numero, tituloBruto) {
  captionsImpresos.push({etiqueta, numero, titulo: tituloBruto.replace(/[`*]/g, "")});
  const titulo = tituloBruto.replace(/`/g, "");
  return new Paragraph({
    style: "Caption", keepNext: true, keepLines: true,
    spacing: { before: 240, after: 80 },
    children: [
      new TextRun({ text: `${etiqueta} `, bold: true, font: FUENTE, size: 22 }),
      new SimpleField(`SEQ ${etiqueta} \\* ARABIC`, String(numero)),
      new TextRun({ text: titulo, bold: false, italics: true, break: 1, font: FUENTE, size: 22 }),
    ],
  });
}
function nota(texto) {
  return new Paragraph({ keepLines: true, spacing: { before: 60, after: 240, line: 240 }, children: runs(texto.replace(/^\*Nota\.\*/, "Nota.").replace(/^\*|\*$/g, ""), { font: FUENTE, size: 18, italics: true }) });
}
const SIN = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const ICONOS_AWS = [
  [/^VPC$/, "vpc"], [/^Subred pública web/, "ec2"], [/^Subred pública IoT/, "ec2"], [/^Subred privada de datos/, "rds"],
  [/^Internet Gateway/, "igw"], [/^API de IA externa/, "servidor"], [/^Actores/, "usuarios"],
];
function iconoDe(texto) {
  const par = ICONOS_AWS.find(([re]) => re.test(texto));
  if (!par) return null;
  return fs.readFileSync(path.join(RAIZ, "img/iconos", par[1] + ".png"));
}
function tabla(filas, archivo) {
  const ncol = filas[0].length;
  const conIconos = archivo === "04a-diagrama-arquitectura.md" && filas[0][0] === "Elemento";
  const pesos = Array.from({ length: ncol }, (_, c) => {
    const largo = Math.max(...filas.map(f => (f[c] || "").replace(/[`*]/g, "").length));
    const media = filas.reduce((a, f) => a + (f[c] || "").replace(/[`*]/g, "").length, 0) / filas.length;
    return Math.max(largo <= 12 ? 17 : 8, Math.min(70, 0.6 * media + 0.4 * Math.min(largo, 70)));
  });
  const total = pesos.reduce((a, b) => a + b, 0);
  let anchos = pesos.map(p => Math.round(ANCHO_VERT * p / total));
  if (filas[0][0] === "ID" && filas[0][1] === "Caso de uso") anchos = [650, 3000, 1800, 1400, 1450, 1104];
  if (filas[0][0] === "Campo exigido") anchos = [2100, 1300, 2100, 1500, 2404];
  anchos[anchos.length - 1] += ANCHO_VERT - anchos.reduce((a, b) => a + b, 0);
  const tam = (archivo === "04d-crm.md" && filas[0].includes("Vendedor")) ? 18 : ncol >= 6 ? 18 : ncol >= 5 ? 18 : 20;
  const filasT = filas.map((f, r) => new TableRow({
    tableHeader: r === 0, cantSplit: true,
    children: f.map((celda, c) => new TableCell({
      width: { size: anchos[c], type: WidthType.DXA },
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      borders: { top: SIN, left: SIN, right: SIN, bottom: r === 0 ? { style: BorderStyle.SINGLE, size: 4, color: "000000" } : SIN },
      children: [new Paragraph({ keepNext: r === 0, keepLines: true, spacing: { line: 240 }, children: [
        ...((conIconos && c === 0 && r > 0 && iconoDe(celda)) ? [new ImageRun({ type: "png", data: iconoDe(celda), transformation: { width: 26, height: 26 }, altText: { title: "Ícono de AWS", description: "Ícono oficial de AWS", name: "icono-aws" } }), new TextRun({ text: "  ", size: tam })] : []),
        ...runs(limpiar(celda || "", archivo), { font: FUENTE, size: tam, bold: r === 0 })] })],
    })),
  }));
  return new Table({
    width: { size: ANCHO_VERT, type: WidthType.DXA }, columnWidths: anchos,
    borders: { top: { style: BorderStyle.SINGLE, size: 12, color: "000000" }, bottom: { style: BorderStyle.SINGLE, size: 12, color: "000000" }, left: SIN, right: SIN, insideHorizontal: SIN, insideVertical: SIN },
    rows: filasT,
  });
}
function figura(img, max, alt) {
  const t = ajustar(img, max);
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: img.buf, transformation: t, altText: { title: alt || img.nombre, description: alt || img.nombre, name: img.nombre } })],
  });
}

// ------------------------------------------------------------------------------------------
// Construcción
// ------------------------------------------------------------------------------------------
const encabezadoPagina = () => new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 22 })] })] });
const encabezadoVacio = () => new Header({ children: [new Paragraph({ children: [] })] });
const propVertical = { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } };
const propApaisada = { page: { size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1200, right: 1440, bottom: 1000, left: 1440 } } };

const encabezados = new Set();   // párrafos de encabezado, para no dejarlos solos antes de una página horizontal
const secciones = [];       // secciones de Word
let actual = null;
function abrirVertical(extra = {}) { actual = { properties: { ...propVertical, ...extra }, children: [] }; secciones.push(actual); }
function agregar(...c) { actual.children.push(...c.flat()); }

function portada() {
  const c = (texto, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, before: o.before ?? 0, line: 300 }, children: [new TextRun({ text: texto, font: FUENTE, size: o.size ?? 24, bold: o.bold, italics: o.italics })] });
  return [
    c("INACAP Sede Temuco", { bold: true, size: 28, before: 600 }),
    c("Transformación Digital (TIEL15)", { size: 22, after: 1800 }),
    c("Cofrial SpA: del caos operativo a la cadena de frío inteligente", { bold: true, size: 36, after: 240 }),
    c("Informe de ingeniería, Hito 1", { size: 28, after: 120 }),
    c("Diagnóstico del dolor, decisiones de arquitectura cloud, modelado de datos y canales digitales", { italics: true, size: 22, after: 1800 }),
    c("Eric Aguayo Quintriqueo", { size: 26, after: 60 }),
    c("Sergio Vásquez Marimán", { size: 26, after: 600 }),
    c("Evaluación sumativa integral (Nota 2)", { size: 22, after: 60 }),
    c("Proyecto de arquitectura y prototipado de transformación digital operativa, Unidad 02", { size: 22, after: 60 }),
    c("Temuco, 4 de noviembre de 2026", { size: 22 }),
  ];
}
const tituloFrontal = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240 }, children: [new TextRun({ text: t, font: FUENTE, size: 32, color: ROJO })] });

function renderBloques(bloques, archivo, numSec, opciones = {}) {
  let n2 = 0, n3 = 0;
  let i = 0;
  while (i < bloques.length) {
    const b = bloques[i];
    if (b.tipo === "h") {
      let numer = "";
      if (numSec && b.nivel === 2) { n2++; n3 = 0; numer = `${numSec}.${n2}`; }
      else if (numSec && b.nivel === 3) { n3++; numer = `${numSec}.${n2}.${n3}`; }
      const ph = encabezado({ nivel: b.nivel, texto: limpiar(b.texto, archivo).replace(/^\d+\.\s+/, "") }, numer);
      encabezados.add(ph);
      agregar(ph);
    } else if (b.tipo === "p") {
      if (opciones.definiciones) agregar(parrafo(limpiar(b.texto, archivo)));
      else agregar(parrafo(limpiar(b.texto, archivo)));
    } else if (b.tipo === "lista") {
      if (opciones.definiciones) {
        b.items.forEach(it => agregar(new Paragraph({ spacing: { line: 300, after: 100 }, indent: { left: 540, hanging: 540 }, alignment: AlignmentType.LEFT, children: runs(it.t, { font: FUENTE, size: 22 }) })));
      } else if (opciones.referencias) {
        b.items.forEach(it => agregar(new Paragraph({ spacing: { line: 300, after: 140 }, indent: { left: 720, hanging: 720 }, alignment: AlignmentType.LEFT, children: runs(it.t, { font: FUENTE, size: 22 }) })));
      } else {
        agregar(lista({ ...b, items: b.items.map(it => ({ ...it, t: limpiar(it.t, archivo) })) }));
      }
    } else if (b.tipo === "caption" && omitida(b)) {
      i += 2;
      if (bloques[i] && bloques[i].tipo === "nota") i++;
      continue;
    } else if (b.tipo === "caption") {
      const n = num(archivo, b.etiqueta, b.local);
      const sig = bloques[i + 1];
      const dic = b.etiqueta === "Tabla" && opciones.diccionario ? b.titulo.match(/^`(\w+)`: (.*)$/) : null;
      if (dic) {
        agregar(new Paragraph({ keepNext: true, spacing: { before: 200, after: 40 }, children: runs(`**${dic[1]}.** ${limpiar(dic[2], archivo)}`, { font: FUENTE, size: 22 }) }));
        agregar(caption("Tabla", n, `Diccionario de datos: tabla ${dic[1]}`));
        i++; continue;
      }
      if (b.etiqueta === "Figura" && sig && sig.tipo === "img") {
        const img = cargarImagen(path.join("informe", sig.ruta).replace(/^informe\//, ""));
        const hayNota = bloques[i + 2] && bloques[i + 2].tipo === "nota";
        const notaB = hayNota ? bloques[i + 2] : null;
        if (esApaisada(img)) {
          const arrastrados = [];
          while (actual.children.length && encabezados.has(actual.children[actual.children.length - 1])) arrastrados.unshift(actual.children.pop());
          if (actual.children.length === 0 && secciones[secciones.length - 1] === actual && secciones.length > 1) secciones.pop();
          actual = { properties: propApaisada, children: [] };
          secciones.push(actual);
          agregar(arrastrados);
          agregar(caption("Figura", n, limpiar(b.titulo, archivo)), figura(img, PX_HORIZ, sig.alt));
          if (notaB) agregar(nota(limpiar(notaB.texto, archivo)));
          abrirVertical({ type: SectionType.NEXT_PAGE });
        } else {
          agregar(caption("Figura", n, limpiar(b.titulo, archivo)), figura(img, PX_VERT, sig.alt));
          if (notaB) agregar(nota(limpiar(notaB.texto, archivo)));
        }
        i += hayNota ? 3 : 2; continue;
      }
      agregar(caption(b.etiqueta, n, limpiar(b.titulo, archivo)));
    } else if (b.tipo === "tabla") {
      agregar(tabla(b.filas, archivo));
    } else if (b.tipo === "img") {
      const img = cargarImagen(b.ruta);
      agregar(figura(img, PX_VERT, b.alt));
    } else if (b.tipo === "nota") {
      agregar(nota(limpiar(b.texto, archivo)));
    }
    i++;
  }
}

function agregarIndice(tipo) {
  const cache = path.join(RAIZ, "exportar/indices.json");
  if (!fs.existsSync(cache)) return;
  const entradas = JSON.parse(fs.readFileSync(cache, "utf-8"))[tipo] || [];
  for (const e of entradas) agregar(new Paragraph({ spacing: { after: 35, line: 220 }, tabStops: [{ type: "right", position: 9300, leader: "dot" }], children: [new TextRun({text: e.titulo + "\t" + e.pagina, font: FUENTE, size: 20})] }));
}
function main() {
  const datos = {};
  // 1) leer y asignar numeración
  const archivos = SECCIONES.map(s => s.file);
  for (const f of archivos) {
    const txt = fs.readFileSync(path.join(RAIZ, f), "utf-8");
    datos[f] = leerBloques(txt, OMITIR_H[path.basename(f)] || []);
  }
  const casos = leerBloques(fs.readFileSync(path.join(RAIZ, "06-casos-de-uso.md"), "utf-8")).bloques;
  const integrados = SECCIONES.map((x,i) => `# ${i+1} ${x.titulo}\n\n` + fs.readFileSync(path.join(RAIZ,x.file), "utf-8").replace(/^# .*\n/, "")).join("\n\n");
  fs.writeFileSync(path.join(RAIZ, "entrega/Informe_integrado_fuentes.md"), integrados);
  const anexoA = datos["04b-modelo-datos.md"].anexoA;
  const anexoAB = leerBloques(anexoA.join("\n")).bloques;
  for (const f of archivos) for (const b of datos[f].bloques) if (b.tipo === "caption" && !omitida(b)) asignar(f, b.etiqueta, b.local);
  for (const b of anexoAB) if (b.tipo === "caption") asignar("04b-modelo-datos.md", b.etiqueta, b.local);



  const cuentasB = leerBloques(fs.readFileSync(path.join(RAIZ, "entrega/anexo-cuentas.md"), "utf-8")).bloques;
  const pautaC = leerBloques(fs.readFileSync(path.join(RAIZ, "entrega/anexo-pauta.md"), "utf-8")).bloques;
  for (const [f, bs] of [["entrega/anexo-cuentas.md", cuentasB], ["entrega/anexo-pauta.md", pautaC], ["06-casos-de-uso.md", casos]])
    for (const b of bs) if (b.tipo === "caption") asignar(f, b.etiqueta, b.local);

  // 2) portada y preliminares
  abrirVertical();
  agregar(tituloFrontal("Índice"));
  agregarIndice("contenido");
  agregar(tituloH1("Índice de tablas"));
  agregarIndice("tablas");
  agregar(tituloH1("Índice de figuras"));
  agregarIndice("figuras");
  agregar(tituloH1("Resumen ejecutivo"));
  const resumen = leerBloques(fs.readFileSync(path.join(RAIZ, "entrega/resumen-ejecutivo.md"), "utf-8")).bloques;
  renderBloques(resumen, "entrega/resumen-ejecutivo.md", 0);

  // 3) cuerpo
  SECCIONES.forEach((s, k) => {
    agregar(tituloH1(s.titulo, k + 1, !s.sinSalto));
    renderBloques(datos[s.file].bloques, s.file, k + 1);
  });

  // 4) referencias y anexos
  agregar(tituloH1("Referencias"));
  const CITAS = [[/^Docker,/, /Docker, Inc\., s\.f\./], [/^Grafana Labs/, /Grafana Labs, s\.f\./], [/^Groq\./, /Groq, s\.f\./], [/^Leaflet\./, /Leaflet, s\.f\./], [/^PostgreSQL Global/, /PostgreSQL Global Development Group, s\.f\./], [/^Aguayo/, /Aguayo Quintriqueo y Vásquez Marimán, 2026/], [/^Amazon Web Services\. \(s\.f\.\)/, /Amazon Web Services, s\.f\./], [/^Amazon Web Services\. \(2021\)/, /Amazon Web Services, 2021/],
    [/^Anderson/, /Anderson, 2010/], [/^Codd/, /Codd \(1970\)/], [/^Django/, /Django Software Foundation, 2025/], [/^Google/, /Google, s\.f\./], [/^INACAP/, /INACAP Sede Temuco, 2026/], [/^Ministerio de Salud/, /Ministerio de Salud, 1997/],
    [/^Object Management Group\. \(2013\)/, /\[OMG\], 2013/], [/^Object Management Group\. \(2017\)/, /\[OMG\], 2017/], [/^Ohno/, /Ohno, 1988/], [/^Ortegón/, /Ortegón et al\., 2005/]];
  const todoTexto = corpus.join("\n") + fs.readFileSync(path.join(RAIZ, "06-casos-de-uso.md"), "utf-8");
  const refs = fs.readFileSync(path.join(RAIZ, "entrega/referencias.md"), "utf-8").split("\n").filter(Boolean).filter(r => {
    const par = CITAS.find(([re]) => re.test(r));
    if (!par) throw new Error("Referencia sin regla de cita: " + r.slice(0, 40));
    return par[1].test(todoTexto);
  });
  CITAS.forEach(([re, cita]) => { if (!cita.test(todoTexto) && !refs.some(r => re.test(r))) console.log("Referencia omitida (sin cita en esta versión):", cita.source); });
  renderBloques([{ tipo: "lista", ordenada: false, items: refs.map(t => ({ t, nivel: 0 })) }], "entrega/referencias.md", 0, { referencias: true });
  agregar(tituloH1("Anexo A. Diccionario de datos"));
  agregar(parrafo("Cada tabla del modelo de datos se describe con sus campos, tipo, nulidad, clave, descripción y un ejemplo ficticio. Las tablas se agrupan por módulo."));
  renderBloques(anexoAB.filter(b => !(b.tipo === "h" && b.nivel === 2)), "04b-modelo-datos.md", 0, { diccionario: true });
  const anexoCuentas = leerBloques(fs.readFileSync(path.join(RAIZ, "entrega/anexo-cuentas.md"), "utf-8")).bloques;

  agregar(tituloH1("Anexo B. Cuentas de prueba"));
  renderBloques(anexoCuentas, "entrega/anexo-cuentas.md", 0);
  agregar(tituloH1("Anexo C Correspondencia con la pauta"));
  renderBloques(pautaC, "entrega/anexo-pauta.md", 0);
  agregar(tituloH1("Anexo D Casos de uso"));
  renderBloques(casos, "06-casos-de-uso.md", 0);
  agregar(tituloH1("Anexo E Glosario"));
  renderBloques(leerBloques(fs.readFileSync(path.join(RAIZ, "entrega/glosario.md"), "utf-8")).bloques, "entrega/glosario.md", 0, { definiciones: true });
  const doc = new Document({
    creator: "Eric Aguayo Quintriqueo y Sergio Vásquez Marimán",
    title: "Cofrial SpA: del caos operativo a la cadena de frío inteligente. Informe de ingeniería, Hito 1",
    description: "Informe técnico ejecutivo del Hito 1, Transformación Digital (TIEL15), INACAP Sede Temuco",
    features: { updateFields: true },
    styles: {
      default: { document: { run: { font: FUENTE, size: 22 } } },
      paragraphStyles: [
        { id: "Caption", name: "caption", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 22, bold: true }, paragraph: { alignment: AlignmentType.LEFT, keepNext: true } },
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 22, bold: true }, paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 22, bold: true }, paragraph: { alignment: AlignmentType.LEFT, spacing: { before: 280, after: 140 }, keepNext: true, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 22, bold: true, italics: true }, paragraph: { alignment: AlignmentType.LEFT, spacing: { before: 220, after: 120 }, keepNext: true, outlineLevel: 2 } },
      ],
    },
    numbering: { config: [{ reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }, { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1160, hanging: 360 } } } }] }, ...configsNum] },
    sections: secciones.map(s => ({ properties: s.properties, children: s.children })),
  });
  fs.writeFileSync(path.join(RAIZ, "exportar/captions.json"), JSON.stringify(captionsImpresos, null, 2));
  return Packer.toBuffer(doc).then(buf => {
    const os = require("os");
    const cp = require("child_process");
    const carpetaPrincipal = path.resolve(RAIZ, "..");   // carpeta visible de Cofrial SPA
    const argSalida = process.argv.find(a => a.startsWith("--salida="));
    const carpetaSalida = argSalida ? argSalida.slice(9) : path.join(RAIZ, "entrega");
    fs.mkdirSync(carpetaSalida, { recursive: true });
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "cofrial-informe-"));
    const gen = path.join(tempDir, "contenido.docx");
    fs.writeFileSync(gen, buf);
    const dest = path.join(carpetaSalida, "Informe_Hito1_Cofrial_SpA" + (COMPACTO ? "_compacto" : "") + ".docx");
    const argPlantilla = process.argv.find(a => a.startsWith("--plantilla="));
    const carta = path.join(carpetaPrincipal, "Carta-1-vert.docx");
    const alternativa = path.join(carpetaPrincipal, "TIHI84_U1_Plantilla_informe_Guía_ABPro.docx");
    const plantilla = argPlantilla ? path.resolve(argPlantilla.slice(12)) : (fs.existsSync(carta) ? carta : alternativa);
    if (!fs.existsSync(plantilla)) throw new Error("Falta plantilla: use --plantilla=/ruta/a/plantilla.docx");
    const aplicador = path.basename(plantilla) === "Carta-1-vert.docx" ? "armar-con-plantilla.py" : "aplicar-plantilla-adjunta.py";
    const r = cp.spawnSync(process.env.COFRIAL_PYTHON || "python3", [path.join(__dirname, aplicador), gen, plantilla, dest,
      "INFORME DE INGENIERÍA DE TRANSFORMACIÓN DIGITAL", "Cofrial SpA",
      "Sergio Vásquez Marimán y Eric Aguayo Quintriqueo", "Transformación Digital (TIEL15) — Evaluación Sumativa Integral, Hito 1 (Nota 2)",
      "Felipe Andrés Henríquez Vilugrón", "5 de noviembre de 2026", "Ingeniería en Informática"], { encoding: "utf-8" });
    if (r.status !== 0) throw new Error("Falló la aplicación de la plantilla: " + r.stderr);
    console.log(r.stdout.trim());
    console.log(`Tablas: ${nTabla}, figuras: ${nFigura}, secciones de Word: ${secciones.length}`);
  });
}
main().catch(e => { console.error(e); process.exit(1); });
