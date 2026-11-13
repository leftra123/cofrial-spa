/* Cofrial SpA · semáforo de avance en los formularios (tienda, CRM, flota y operación). Sin dependencias; mejora progresiva: si este
   script no carga, los formularios se validan en el servidor como siempre.

   Cada campo muestra, recién cuando se llega a él, una luz con un texto corto:
     gris     aún sin tocar (u opcional y vacío)
     rojo     falta o está malo
     naranja  va bien pero incompleto
     verde    listo
   y los formularios de 3 o más campos obligatorios llevan un contador junto al botón de enviar («3 de 8 listos»).

   Regla de oro: lo que el semáforo frena, el servidor también lo rechazaría. El RUT usa el mismo módulo 11 de clientes/rut.py (los casos
   de clientes/rut_casos.json se prueban contra ambos), la clave nueva el mínimo de 8 de Django, y lo demás sale de los atributos que ya
   tiene cada campo (required, min, max, minlength, type). No consulta al servidor mientras se escribe: no revela qué RUT o correos existen.

   - Un <form data-semaforo="no"> queda fuera. También los buscadores (method=get), el selector de cantidad (.cant), los radios y las
     casillas (conservan la validación del navegador) y el formulario de tarjeta de Mercado Pago.
   - Las reglas son funciones puras: se prueban sin navegador con  node --test web/herramientas/pruebas-js/*.test.mjs  */
(function (raiz) {
  "use strict";

  /* ==================== reglas (sin DOM) ==================== */
  function r(estado, texto) { return {estado: estado, texto: texto}; }
  function faltan(n) { return n === 1 ? "Falta 1 carácter" : "Faltan " + n + " caracteres"; }

  function limpiarRut(v) { return String(v || "").replace(/[^0-9kK]/g, "").toUpperCase(); }
  function verificador(cuerpo) {                           // módulo 11, igual que clientes/rut.py
    var suma = 0, factor = 2;
    for (var i = cuerpo.length - 1; i >= 0; i--) { suma += Number(cuerpo[i]) * factor; factor = factor === 7 ? 2 : factor + 1; }
    var resto = 11 - (suma % 11);
    return resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
  }
  function rutValido(v) {
    var l = limpiarRut(v);
    return l.length >= 8 && /^\d+$/.test(l.slice(0, -1)) && verificador(l.slice(0, -1)) === l.slice(-1);
  }
  function formatearRut(v) {
    var l = limpiarRut(v);
    return String(Number(l.slice(0, -1))).replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "-" + l.slice(-1);
  }
  function rut(valor, enfocado) {
    var v = String(valor || "").trim(), l = limpiarRut(v);
    if (/[^0-9kK.\-\s]/.test(v) || /[kK]/.test(l.slice(0, -1))) return r("rojo", "Solo números y la letra K al final");
    if (l.length < 8) return r("naranja", "Faltan dígitos");
    if (l.length > 9) return r("rojo", "Sobran dígitos");
    if (rutValido(l)) return r("verde", "Listo");
    if (l.length === 8 && enfocado) return r("naranja", "Falta el dígito verificador");     // con 8 puede faltar el último: aún está escribiendo
    return r("rojo", "El dígito verificador no coincide");
  }

  function correo(valor) {
    var v = String(valor || "").trim();
    if (/\s/.test(v)) return r("rojo", "No puede llevar espacios");
    var partes = v.split("@");
    if (partes.length === 1) return r("naranja", "Falta el @");
    if (partes.length > 2) return r("rojo", "Lleva más de un @");
    if (!partes[0]) return r("rojo", "Falta el nombre antes del @");
    var dominio = partes[1];
    if (dominio !== "localhost" && !/^[^.]+(\.[^.]+)*\.[^.]{2,}$/.test(dominio)) return r("naranja", "Falta el dominio (p. ej. correo.cl)");
    return r("verde", "Listo");
  }

  function claveNueva(valor, minimo) {
    var n = (minimo || 8) - String(valor || "").length;
    return n > 0 ? r("naranja", faltan(n)) : r("verde", "Largo correcto");
  }

  function repetir(valor, original) {
    valor = String(valor || ""); original = String(original || "");
    if (!original) return r("naranja", "Escribe primero la clave de arriba");
    if (valor === original) return r("verde", "Las claves coinciden");
    return original.indexOf(valor) === 0 ? r("naranja", "Sigue escribiendo") : r("rojo", "No coincide con la clave");
  }

  function esNumero(x) { return x !== null && x !== undefined && x !== "" && !isNaN(Number(x)); }
  function numero(valor, min, max) {
    if (!esNumero(String(valor).trim())) return r("rojo", "Escribe un número");
    var n = Number(valor);
    if (esNumero(min) && n < Number(min)) return r("rojo", "El mínimo es " + Number(min));
    if (esNumero(max) && n > Number(max)) return r("rojo", "El máximo es " + Number(max));
    return r("verde", "Listo");
  }

  function texto(valor, minlength) {
    var n = (Number(minlength) || 0) - String(valor || "").length;
    return n > 0 ? r("naranja", faltan(n)) : r("verde", "Listo");
  }

  var NO_SE_EVALUA = ["hidden", "submit", "button", "reset", "image", "radio", "checkbox", "file", "search", "range", "color"];
  function tipoDe(c) {
    var etiqueta = String(c.etiqueta || "").toUpperCase(), tipo = String(c.tipo || "text").toLowerCase(), nombre = String(c.nombre || "");
    if (etiqueta === "SELECT") return "lista";
    if (etiqueta === "TEXTAREA") return "texto";
    if (etiqueta !== "INPUT" || NO_SE_EVALUA.indexOf(tipo) >= 0) return null;
    if (/(^|_)rut$/.test(nombre)) return "rut";
    if (tipo === "email") return "correo";
    if (tipo === "password") return /^(clave|new_password1|password1)$/.test(nombre) ? "clave-nueva" : /^(clave2|new_password2|password2)$/.test(nombre) ? "repetir" : "texto";
    if (tipo === "number") return "numero";
    return "texto";
  }

  /* c: {regla, valor, requerido, enfocado, tocado, original, min, max, minlength} */
  function evaluar(c) {
    var valor = c.valor === null || c.valor === undefined ? "" : String(c.valor);
    var vacio = c.regla === "clave-nueva" || c.regla === "repetir" ? valor === "" : valor.trim() === "";       // una clave puede llevar espacios
    if (vacio) {
      if (!c.tocado) return r("gris", "");
      if (c.requerido) return r("rojo", c.regla === "lista" ? "Elige una opción" : "Falta");
      return r("gris", "Opcional");
    }
    switch (c.regla) {
      case "rut": return rut(valor, c.enfocado);
      case "correo": return correo(valor);
      case "clave-nueva": return claveNueva(valor, c.minlength);
      case "repetir": return repetir(valor, c.original);
      case "numero": return numero(valor, c.min, c.max);
      case "lista": return r("verde", "Listo");
      default: return texto(valor, c.minlength);
    }
  }

  var reglas = {rut: rut, correo: correo, claveNueva: claveNueva, repetir: repetir, numero: numero, texto: texto, tipoDe: tipoDe,
                evaluar: evaluar, formatearRut: formatearRut, rutValido: rutValido};
  if (typeof module === "object" && module.exports) { module.exports = reglas; return; }       // node: solo las reglas
  if (!raiz || !raiz.document) return;

  /* ==================== formularios (DOM) ==================== */
  var doc = raiz.document, serie = 0, MINIMO_PARA_CONTADOR = 3;
  var ICONOS = {verde: "M20 6L9 17l-5-5", rojo: "M12 6v7M12 18h.01", naranja: "M6 12h.01M12 12h.01M18 12h.01", gris: ""};
  var SVG = "http://www.w3.org/2000/svg";

  function anunciar(t) { if (raiz.CofrialEstados && raiz.CofrialEstados.anunciar) raiz.CofrialEstados.anunciar(t); }

  function evaluable(campo) {
    if (!campo.name || campo.disabled || campo.readOnly) return false;
    if (campo.closest(".cant, #mp-brick-container, [data-semaforo='no']")) return false;
    return tipoDe({etiqueta: campo.tagName, tipo: campo.type, nombre: campo.name}) !== null;
  }
  function camposDe(form) { return Array.prototype.filter.call(form.elements, evaluable); }
  function visible(campo) { return !campo.disabled && (campo.offsetParent !== null || campo === doc.activeElement); }     // un campo que otro script ocultó o apagó no cuenta

  function compacto(form) {                                 // una fila dentro de una tabla o ficha: la luz no puede deformarla
    return form.classList.contains("en-linea") || !!form.closest("td, th") || /inline/.test(raiz.getComputedStyle(form).display);
  }

  function luz() {
    var i = doc.createElement("i"), svg = doc.createElementNS(SVG, "svg"), p = doc.createElementNS(SVG, "path");
    i.className = "sem-luz"; i.setAttribute("aria-hidden", "true");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.appendChild(p); i.appendChild(svg);
    return i;
  }
  function linea(clase) {
    var s = doc.createElement("span"), t = doc.createElement("span");
    s.className = clase + " sem-apagada"; s.dataset.estado = "gris"; s.id = "sem-" + (++serie);
    t.className = "sem-txt"; s.appendChild(luz()); s.appendChild(t);
    return s;
  }
  function pintar(el, res) {
    if (!el) return;
    el.dataset.estado = res.estado;
    el.classList.toggle("sem-apagada", res.estado === "gris" && !res.texto);        // sin tocar: no se muestra nada (un círculo vacío parece una casilla)
    el.querySelector("path").setAttribute("d", ICONOS[res.estado]);
    el.querySelector(".sem-txt").textContent = res.texto;
  }

  function original(campo) {                                // la clave que este campo debe repetir: la «clave nueva» anterior del formulario
    var todos = Array.prototype.slice.call(campo.form.elements), antes = todos.slice(0, todos.indexOf(campo)).reverse();
    return antes.filter(function (x) {                       // por la regla guardada: con el ojo abierto el campo pasa a type=text
      return (x._sem ? x._sem.regla : tipoDe({etiqueta: x.tagName, tipo: x.type, nombre: x.name})) === "clave-nueva";
    })[0] || null;
  }

  function medir(campo, enfocado) {
    var s = campo._sem, regla = s.regla, orig = regla === "repetir" ? original(campo) : null;
    if (s.delServidor) return {estado: "rojo", texto: "Revisa este dato"};       // el mensaje del servidor ya está junto al campo
    return evaluar({regla: regla, valor: campo.value, requerido: campo.required, enfocado: enfocado, tocado: s.tocado, original: orig ? orig.value : "",
                    min: campo.getAttribute("min"), max: campo.getAttribute("max"), minlength: campo.getAttribute("minlength")});
  }

  function actualizar(campo, enfocado) {
    var s = campo._sem; if (!s) return;
    if (enfocado === undefined) enfocado = doc.activeElement === campo;
    var res = medir(campo, enfocado), form = campo.form, f = form._sem;
    s.estado = res.estado; campo.dataset.sem = res.estado;
    if (res.estado === "rojo") campo.setAttribute("aria-invalid", "true"); else campo.removeAttribute("aria-invalid");
    if (s.linea) pintar(s.linea, res);
    if (f.linea && (enfocado || f.campoEnLinea === campo)) {            // compacto: una sola línea, la del campo que se está llenando
      f.campoEnLinea = campo; pintar(f.linea, res); f.linea.hidden = res.estado === "gris" && !res.texto;
    }
    contar(form);
  }

  function contar(form, frenado) {
    var f = form._sem; if (!f || !f.resumen) return;
    if (frenado) f.frenado = true;                            // tras un envío frenado el contador sigue diciendo cuántos faltan, hasta que no falte ninguno
    var campos = camposDe(form).filter(function (c) { return c._sem && visible(c); });
    var obligatorios = campos.filter(function (c) { return c.required; });
    var listos = obligatorios.filter(function (c) { return c._sem.estado === "verde"; }).length;
    var malos = campos.filter(function (c) { return !c.required && (c._sem.estado === "rojo" || c._sem.estado === "naranja"); }).length;
    var enCurso = obligatorios.filter(function (c) { return c._sem.estado === "rojo" || c._sem.estado === "naranja"; }).length;
    var total = obligatorios.length, faltan = total - listos + malos, res;
    if (f.frenado && faltan) res = r("rojo", (faltan === 1 ? "Falta 1 campo" : "Faltan " + faltan + " campos") + ": revisa los que están en rojo");
    else if (!faltan) res = r("verde", "Todo listo para enviar");
    else if (!listos && !malos && !enCurso) res = r("gris", total + " campos por completar");
    else res = r("naranja", listos + " de " + total + " listos" + (malos ? " · " + malos + " por corregir" : ""));
    if (f.resumen.dataset.estado !== res.estado || f.resumen.querySelector(".sem-txt").textContent !== res.texto) pintar(f.resumen, res);
  }

  function preparar(campo, form) {
    if (campo._sem) return;
    var f = form._sem, s = campo._sem = {regla: tipoDe({etiqueta: campo.tagName, tipo: campo.type, nombre: campo.name}), tocado: false, estado: "gris",
                                         delServidor: campo.getAttribute("aria-invalid") === "true"};
    if (!f.compacto) {
      s.linea = linea("sem");
      (campo.closest(".clave-caja") || campo).insertAdjacentElement("afterend", s.linea);       // bajo la caja del ojo, no dentro
      campo.setAttribute("aria-describedby", ((campo.getAttribute("aria-describedby") || "") + " " + s.linea.id).trim());
    }
    if (campo.value !== "" && campo.type !== "password") s.tocado = true;       // ya trae valor (servidor, navegador o lista con opción elegida): se puede juzgar
    if (s.delServidor) s.tocado = true;
    actualizar(campo, false);
  }

  function boton(form) {
    var b = form.querySelectorAll("button:not([type=button]):not([formnovalidate]), input[type=submit]");
    return b.length ? b[b.length - 1] : null;
  }

  function mejorar(form) {
    if (form._sem || form.method !== "post" || form.dataset.semaforo === "no" || form.closest("#mp-brick-container, [data-semaforo='no']")) return;
    var campos = camposDe(form);
    if (!campos.length) return;
    var f = form._sem = {compacto: compacto(form)};
    form.noValidate = true;                                   // los avisos los da el semáforo; al enviar se llama igual a la validación del navegador
    form.classList.add("con-semaforo");
    if (f.compacto) { f.linea = linea("sem sem-fila"); f.linea.hidden = true; f.linea.setAttribute("role", "status"); form.appendChild(f.linea); }
    else if (campos.filter(function (c) { return c.required; }).length >= MINIMO_PARA_CONTADOR) {
      var b = boton(form), ancla = b && b.parentElement !== form && b.parentElement.tagName === "P" ? b.parentElement : b;
      if (ancla) {
        f.resumen = linea("sem sem-resumen"); f.resumen.setAttribute("role", "status");
        ancla.insertAdjacentElement("beforebegin", f.resumen);
      }
    }
    campos.forEach(function (c) { preparar(c, form); });
    contar(form);
  }
  function mejorarTodo(base) { Array.prototype.forEach.call((base || doc).querySelectorAll("form"), mejorar); }

  function campoDe(e) {
    var c = e.target;
    if (!c || !c.form || !c.tagName || !/^(INPUT|SELECT|TEXTAREA)$/.test(c.tagName)) return null;
    if (!c.form._sem) mejorar(c.form);
    if (!c.form._sem) return null;
    if (!c._sem && evaluable(c)) preparar(c, c.form);         // campo agregado después (p. ej. al cambiar el rol en «Crear cuenta»)
    return c._sem ? c : null;
  }

  doc.addEventListener("focusin", function (e) {
    var c = campoDe(e); if (!c) return;
    c._sem.tocado = true; actualizar(c, true);
  });
  function alEscribir(e) {
    var c = campoDe(e); if (!c) return;
    c._sem.tocado = true; c._sem.delServidor = false;         // lo corrigió: desde aquí mandan las reglas
    actualizar(c);
    if (c._sem.regla === "clave-nueva") camposDe(c.form).forEach(function (x) { if (x._sem && x._sem.regla === "repetir" && x._sem.tocado) actualizar(x); });
  }
  doc.addEventListener("input", alEscribir);
  doc.addEventListener("change", alEscribir);
  doc.addEventListener("focusout", function (e) {
    var c = campoDe(e); if (!c) return;
    if (c._sem.regla === "rut" && rutValido(c.value)) c.value = formatearRut(c.value);        // mismo formato que guarda el servidor
    actualizar(c, false);
  });

  /* Envío: en captura, antes que el estado «cargando» de estados.js, para que el botón no quede ocupado si el semáforo frena. */
  doc.addEventListener("submit", function (e) {
    var form = e.target, f = form && form._sem;
    if (!f || (e.submitter && e.submitter.formNoValidate)) return;
    var campos = camposDe(form).filter(function (c) { return c._sem && visible(c); });
    campos.forEach(function (c) { c._sem.tocado = true; actualizar(c, false); });
    var pendientes = campos.filter(function (c) { return c._sem.estado === "rojo" || c._sem.estado === "naranja"; });
    if (pendientes.length) {
      e.preventDefault(); e.stopPropagation();
      contar(form, true);
      pendientes[0].focus();
      anunciar((pendientes.length === 1 ? "Falta 1 campo" : "Faltan " + pendientes.length + " campos") + " por completar o corregir. Te llevamos al primero.");
    } else if (!form.checkValidity()) {                       // radios, casillas y demás campos que el semáforo no evalúa
      e.preventDefault(); e.stopPropagation(); form.reportValidity();
    }
  }, true);

  function iniciar() {
    mejorarTodo(doc);
    if (raiz.MutationObserver) {                              // la tienda cambia de pantalla sin recargar: los formularios nuevos también llevan semáforo
      var espera = null;
      new raiz.MutationObserver(function (cambios) {
        if (!cambios.some(function (m) { return m.addedNodes.length; })) return;
        clearTimeout(espera); espera = setTimeout(function () { mejorarTodo(doc); }, 80);
      }).observe(doc.body, {childList: true, subtree: true});
    }
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", iniciar); else iniciar();

  raiz.CofrialSemaforo = {reglas: reglas, mejorar: mejorar};
})(typeof window !== "undefined" ? window : null);
