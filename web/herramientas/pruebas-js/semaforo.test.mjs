// Reglas del semáforo de formularios (web/static/js/semaforo.js), sin navegador:  node --test web/herramientas/pruebas-js/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const R = require("../../static/js/semaforo.js");
const casos = JSON.parse(readFileSync(new URL("../../clientes/rut_casos.json", import.meta.url)));
const es = (r, estado, texto) => { assert.equal(r.estado, estado, JSON.stringify(r)); if (texto !== undefined) assert.equal(r.texto, texto); };

test("RUT: mismos casos que clientes/rut.py", () => {
  for (const v of casos.validos) es(R.rut(v, false), "verde");
  for (const v of casos.invalidos.filter(Boolean)) assert.notEqual(R.rut(v, false).estado, "verde", v);
});

test("RUT: naranja mientras se escribe, rojo cuando ya no calza", () => {
  es(R.rut("35.5", true), "naranja", "Faltan dígitos");
  es(R.rut("35.500.00", true), "naranja", "Faltan dígitos");
  es(R.rut("35.500.001", true), "naranja", "Falta el dígito verificador");      // 8 caracteres: puede faltar el último
  es(R.rut("35.500.001", false), "rojo", "El dígito verificador no coincide");   // salió del campo: ya no está escribiendo
  es(R.rut("35.500.001-0", true), "rojo", "El dígito verificador no coincide");
  es(R.rut("35.500.001-12", true), "rojo", "Sobran dígitos");
  es(R.rut("35.500.001-K1", true), "rojo", "Solo números y la letra K al final");
  es(R.rut("35.5oo.001", true), "rojo", "Solo números y la letra K al final");
  es(R.rut("1234", false), "naranja", "Faltan dígitos");
  es(R.rut("35500001k", false), "verde", "Listo");
});

test("RUT: formato con puntos y guion", () => {
  assert.equal(R.formatearRut("35500001k"), "35.500.001-K");
  assert.equal(R.formatearRut("1.234.567-4"), "1.234.567-4");
});

test("correo: dice qué falta", () => {
  es(R.correo("camila"), "naranja", "Falta el @");
  es(R.correo("camila@"), "naranja", "Falta el dominio (p. ej. correo.cl)");
  es(R.correo("camila@correo"), "naranja", "Falta el dominio (p. ej. correo.cl)");
  es(R.correo("camila@correo."), "naranja", "Falta el dominio (p. ej. correo.cl)");
  es(R.correo("camila@correo.cl"), "verde", "Listo");
  es(R.correo("camila rojas@correo.cl"), "rojo", "No puede llevar espacios");
  es(R.correo("a@b@correo.cl"), "rojo", "Lleva más de un @");
  es(R.correo("@correo.cl"), "rojo", "Falta el nombre antes del @");
});

test("clave nueva: cuenta lo que falta hasta el mínimo", () => {
  es(R.claveNueva("abcde"), "naranja", "Faltan 3 caracteres");
  es(R.claveNueva("abcdefg"), "naranja", "Falta 1 carácter");
  es(R.claveNueva("abcdefgh"), "verde", "Largo correcto");
  es(R.claveNueva("abc", 4), "naranja", "Falta 1 carácter");
});

test("repetir clave: naranja mientras calza, rojo si se desvía", () => {
  es(R.repetir("Cofr", "Cofrial-demo"), "naranja", "Sigue escribiendo");
  es(R.repetir("Cofx", "Cofrial-demo"), "rojo", "No coincide con la clave");
  es(R.repetir("Cofrial-demo", "Cofrial-demo"), "verde", "Las claves coinciden");
  es(R.repetir("abc", ""), "naranja", "Escribe primero la clave de arriba");
});

test("número y texto: según los límites del campo", () => {
  es(R.numero("0", 1, 50), "rojo", "El mínimo es 1");
  es(R.numero("51", 1, 50), "rojo", "El máximo es 50");
  es(R.numero("7", 1, 50), "verde", "Listo");
  es(R.numero("abc", 1, 50), "rojo", "Escribe un número");
  es(R.numero("7", null, null), "verde");
  es(R.texto("hola", 10), "naranja", "Faltan 6 caracteres");
  es(R.texto("hola", null), "verde", "Listo");
});

test("tipoDe: qué regla le toca a cada campo", () => {
  const t = (etiqueta, tipo, nombre) => R.tipoDe({ etiqueta, tipo, nombre });
  assert.equal(t("INPUT", "text", "rut"), "rut");
  assert.equal(t("INPUT", "email", "email"), "correo");
  assert.equal(t("INPUT", "password", "clave"), "clave-nueva");
  assert.equal(t("INPUT", "password", "new_password1"), "clave-nueva");
  assert.equal(t("INPUT", "password", "clave2"), "repetir");
  assert.equal(t("INPUT", "password", "new_password2"), "repetir");
  assert.equal(t("INPUT", "password", "password"), "texto");          // ingresar: solo que no esté vacía
  assert.equal(t("INPUT", "password", "old_password"), "texto");
  assert.equal(t("INPUT", "number", "monto"), "numero");
  assert.equal(t("SELECT", "select-one", "comuna"), "lista");
  assert.equal(t("TEXTAREA", "textarea", "descripcion"), "texto");
  assert.equal(t("INPUT", "tel", "telefono"), "texto");
  assert.equal(R.tipoDe({ etiqueta: "INPUT", tipo: "checkbox", nombre: "acepta", requerido: true }), "casilla");
  for (const tipo of ["hidden", "submit", "button", "radio", "checkbox", "file", "search", "image", "reset"]) assert.equal(t("INPUT", tipo, "x"), null, tipo);
});

test("evaluar: vacío, sin tocar y obligatorio", () => {
  const base = { regla: "texto", valor: "", requerido: true, enfocado: false, tocado: false };
  es(R.evaluar(base), "gris", "");
  es(R.evaluar({ ...base, tocado: true }), "rojo", "Falta");
  es(R.evaluar({ ...base, tocado: true, requerido: false }), "gris", "Opcional");
  es(R.evaluar({ ...base, regla: "lista", tocado: true }), "rojo", "Elige una opción");
  es(R.evaluar({ ...base, regla: "lista", valor: "3" }), "verde", "Listo");
  es(R.evaluar({ ...base, regla: "rut", valor: "35.500.001-K", tocado: true }), "verde");
  es(R.evaluar({ ...base, regla: "repetir", valor: "abc", original: "abcdefgh", tocado: true }), "naranja");
  es(R.evaluar({ ...base, regla: "clave-nueva", valor: "abc", tocado: true }), "naranja", "Faltan 5 caracteres");
  es(R.evaluar({ ...base, regla: "casilla", tocado: true }), "rojo", "Marca la casilla para continuar");
  es(R.evaluar({ ...base, regla: "casilla" }), "gris", "");                 // sin tocar no acusa: el consentimiento es un acto de la persona
  es(R.evaluar({ ...base, regla: "casilla", valor: "1", tocado: true }), "verde", "Listo");
  es(R.evaluar({ ...base, regla: "texto", valor: "   ", tocado: true }), "rojo", "Falta");          // solo espacios no es un dato
});
