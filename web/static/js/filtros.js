/* Cofrial SpA · filtros que se mantienen. Un solo script para toda la web: recuerda, por pantalla, lo que la persona filtró
   y lo devuelve al volver de un detalle, al recargar o al regresar otro día (hasta 7 días).

   Qué recuerda (no hay que editar cada plantilla):
     1. Formularios GET de la propia pantalla (el catálogo): sus parámetros; al volver sin parámetros se recargan con los últimos.
     2. Pestañas de filtro con botones [data-filtro] (Mis pedidos): la pestaña elegida.
     3. Listas del CRM (clientes, solicitudes, cobranza, requerimientos, embudo, demanda, alertas): una barra de búsqueda y
        selectores por columna (Estado, Tipo, Categoría…) que se arma sola sobre la tabla o el embudo.

   Qué NO guarda: nada que parezca un dato personal (correos, RUT, teléfonos, textos largos), ni campos de clave o
   token. Se guarda solo en este navegador (localStorage), separado por cuenta, y se borra al cerrar sesión.
   Todo acceso a localStorage va en try/catch: si el navegador lo bloquea, los filtros funcionan igual, sin recordarse. */
(function () {
  "use strict";
  var VIDA = 7 * 24 * 3600 * 1000, usuario = (document.body && document.body.getAttribute("data-u")) || "anon";
  var PREFIJO = "cofrial-filtros:" + usuario + ":", ruta = location.pathname;
  var NO_GUARDAR = /^\/(cuenta|seguimiento|carrito|soporte|api|bi|pago|checkout)\b/;
  if (NO_GUARDAR.test(ruta)) return;

  /* ---------- almacenamiento (siempre protegido) ---------- */
  function leer(sub) {
    try {
      var c = JSON.parse(localStorage.getItem(PREFIJO + ruta + sub) || "null");
      if (!c || typeof c.t !== "number" || Date.now() - c.t > VIDA) { if (c) localStorage.removeItem(PREFIJO + ruta + sub); return null; }
      return c.v;
    } catch (e) { return null; }
  }
  var olvidado = false;                                                     // tras cerrar sesión no se vuelve a guardar nada
  function guardar(sub, v) { if (olvidado) return; try { localStorage.setItem(PREFIJO + ruta + sub, JSON.stringify({t: Date.now(), v: v})); } catch (e) {} }
  function borrar(sub) { try { localStorage.removeItem(PREFIJO + ruta + sub); } catch (e) {} }
  function borrarTodoDeEstaCuenta() {
    olvidado = true;
    try {
      var claves = [], i;
      for (i = 0; i < localStorage.length; i++) { var k = localStorage.key(i); if (k && k.indexOf("cofrial-filtros:") === 0) claves.push(k); }
      claves.forEach(function (k) { localStorage.removeItem(k); });
    } catch (e) {}
  }
  /* marca de «se restauró»: vive solo en esta pestaña (sessionStorage) */
  function marcar(clave) { try { sessionStorage.setItem(clave, "1"); } catch (e) {} }
  function marcaLeida(clave) { try { var x = sessionStorage.getItem(clave); sessionStorage.removeItem(clave); return x === "1"; } catch (e) { return false; } }

  /* un valor que parezca dato personal no se guarda */
  function limpio(v) {
    v = String(v == null ? "" : v).trim();
    if (!v || v.length > 60 || v.indexOf("@") >= 0) return "";
    if (/\d{7,}/.test(v.replace(/[\s.\-]/g, ""))) return "";                 // RUT, teléfono, folios largos
    return v;
  }
  var TIPOS_FUERA = /^(hidden|password|email|tel|file|submit|button|reset|image|url)$/i, NOMBRES_FUERA = /pass|clave|token|csrf|rut|mail|fono|tel|tarjeta|card|next/i;

  function botonLimpiar(clase) {
    var b = document.createElement("button"); b.type = "button"; b.className = clase || "filtros-limpiar-btn"; b.textContent = "Limpiar filtros"; return b;
  }

  /* ---------- 1. formulario GET de esta pantalla (catálogo) ---------- */
  function formularioGet() {
    var f = null;
    document.querySelectorAll("form").forEach(function (x) {
      if (f || (x.getAttribute("method") || "").toLowerCase() !== "get" || x.closest(".tb-buscar, .buscar-grande")) return;
      var a = x.getAttribute("action"); if (a && a.split("?")[0] !== ruta) return;
      f = x;
    });
    return f;
  }
  function controles(form) {
    return Array.prototype.filter.call(form.elements, function (el) { return el.name && !TIPOS_FUERA.test(el.type) && !NOMBRES_FUERA.test(el.name); });
  }
  function parametrosDe(form) {
    var p = new URLSearchParams(), ok = {};
    controles(form).forEach(function (el) { ok[el.name] = 1; });
    new FormData(form).forEach(function (v, k) { v = limpio(v); if (ok[k] && v) p.append(k, v); });
    return p.toString();
  }
  function iniciarFormulario(form) {
    var nombres = {}; controles(form).forEach(function (el) { nombres[el.name] = 1; });
    var hayQuery = Array.from(new URLSearchParams(location.search).keys()).some(function (k) { return nombres[k]; });
    if (!location.search) {
      var guardado = leer("");
      if (typeof guardado === "string" && guardado) { marcar("cofrial-filtros-restaurado:" + ruta); location.replace(ruta + "?" + guardado); return; }
    }
    var timer = null;
    function sincronizar() { var s = parametrosDe(form); if (s) guardar("", s); else borrar(""); }
    function programar() { clearTimeout(timer); timer = setTimeout(sincronizar, 450); }
    form.addEventListener("change", programar); form.addEventListener("input", programar); form.addEventListener("submit", programar);
    document.addEventListener("click", function (e) { if (e.target.closest("[data-limpiar], [data-quitar]")) programar(); });
    window.addEventListener("pagehide", sincronizar);
    if (hayQuery) sincronizar();
    if (hayQuery && marcaLeida("cofrial-filtros-restaurado:" + ruta)) {
      var cab = document.getElementById("cat-inicio") || form, av = document.createElement("div");
      av.className = "filtros-aviso"; av.setAttribute("role", "status");
      var s = document.createElement("span"); s.textContent = "Se restauraron tus últimos filtros."; av.appendChild(s);
      var b = botonLimpiar(); b.addEventListener("click", function () {
        borrar(""); var l = document.querySelector("[data-limpiar]"); if (l) l.click(); else location.href = ruta; av.remove();
      });
      av.appendChild(b); cab.parentNode.insertBefore(av, cab.nextSibling);
    }
  }

  /* ---------- 2. pestañas de filtro: [data-filtro] ---------- */
  function iniciarPestanas() {
    document.querySelectorAll("[role=group]").forEach(function (grupo, n) {
      var botones = grupo.querySelectorAll("button[data-filtro]"); if (!botones.length) return;
      var sub = "#pestanas" + n, primero = botones[0].getAttribute("data-filtro"), limpiar = botonLimpiar();
      limpiar.hidden = true; grupo.appendChild(limpiar);
      function actual() { var a = grupo.querySelector("button[data-filtro].activo, button[data-filtro][aria-pressed=true]"); return a ? a.getAttribute("data-filtro") : primero; }
      function estado() { var v = actual(); limpiar.hidden = v === primero; if (v === primero) borrar(sub); else guardar(sub, v); }
      grupo.addEventListener("click", function (e) {
        if (e.target === limpiar) { botones[0].click(); return; }
        if (e.target.closest("button[data-filtro]")) setTimeout(estado, 0);
      });
      var g = leer(sub);
      if (typeof g === "string" && g !== primero) {
        var b = Array.prototype.find.call(botones, function (x) { return x.getAttribute("data-filtro") === g; });
        if (b) b.click();
      }
      estado();
    });
  }

  /* ---------- 3. listas del CRM: búsqueda y selectores sobre lo que ya está en pantalla ---------- */
  var LISTAS_CRM = /^\/crm\/(clientes|solicitudes|cobranza|requerimientos|embudo|demanda|alertas)\/?$/;
  var COLUMNAS_SELECTOR = ["Estado", "Tipo", "Categoría", "Plazo"];
  function normal(el) { return (el.textContent || "").replace(/\s+/g, " ").trim(); }
  /* valor de una celda para los selectores: su texto propio («Atraso en entrega»), sin la etiqueta que lo acompañe («Manual»); si solo tiene una etiqueta (un estado), esa */
  function valorCelda(c) {
    var t = Array.prototype.filter.call(c.childNodes, function (n) { return n.nodeType === 3; }).map(function (n) { return n.textContent; }).join(" ").replace(/\s+/g, " ").trim();
    return t || normal(c);
  }
  function iniciarListas() {
    if (!LISTAS_CRM.test(ruta)) return;
    var tablas = Array.prototype.slice.call(document.querySelectorAll(".contenido .tabla-caja table"));
    var tarjetas = Array.prototype.slice.call(document.querySelectorAll(".contenido .embudo .tarjeta"));
    var filasPorTabla = tablas.map(function (t) { return Array.prototype.filter.call(t.tBodies[0] ? t.tBodies[0].rows : [], function (r) { return !r.querySelector("td.vacio, td.vacio-caja"); }); });
    var total = filasPorTabla.reduce(function (s, f) { return s + f.length; }, 0) + tarjetas.length;
    if (!total) return;
    var primera = tablas.length ? tablas[0].closest(".tabla-caja") : document.querySelector(".contenido .embudo"); if (!primera) return;

    /* selectores: columnas de la primera tabla con pocas opciones distintas */
    var selectores = [];
    if (tablas.length && tablas[0].tHead) {
      Array.prototype.forEach.call(tablas[0].tHead.rows[0].cells, function (th, i) {
        var nombre = normal(th); if (COLUMNAS_SELECTOR.indexOf(nombre) < 0) return;
        var vals = {}; filasPorTabla[0].forEach(function (r) { var c = r.cells[i]; if (c) { var t = valorCelda(c); if (t && t.length <= 40) vals[t] = 1; } });
        var lista = Object.keys(vals).sort(); if (lista.length >= 2 && lista.length <= 10) selectores.push({nombre: nombre, col: i, opciones: lista});
      });
    }

    var barra = document.createElement("div"); barra.className = "filtro-barra"; barra.setAttribute("role", "search"); barra.setAttribute("aria-label", "Filtrar esta lista");
    var q = document.createElement("input"); q.type = "search"; q.placeholder = "Buscar en esta lista"; q.setAttribute("aria-label", "Buscar en esta lista"); q.autocomplete = "off"; q.className = "filtro-q";
    barra.appendChild(q);
    selectores.forEach(function (s) {
      var sel = document.createElement("select"); sel.setAttribute("aria-label", "Filtrar por " + s.nombre.toLowerCase());
      var o0 = document.createElement("option"); o0.value = ""; o0.textContent = s.nombre + ": todos"; sel.appendChild(o0);
      s.opciones.forEach(function (v) { var o = document.createElement("option"); o.value = v; o.textContent = v; sel.appendChild(o); });
      barra.appendChild(sel); s.el = sel;
    });
    var cuenta = document.createElement("span"); cuenta.className = "filtro-cuenta"; cuenta.setAttribute("aria-live", "polite"); barra.appendChild(cuenta);
    var limpiar = botonLimpiar(); limpiar.hidden = true; barra.appendChild(limpiar);
    primera.parentNode.insertBefore(barra, primera);
    var vacio = document.createElement("div"); vacio.className = "filtro-vacio"; vacio.hidden = true; vacio.setAttribute("role", "status");
    vacio.innerHTML = "<b>Ningún resultado con esos filtros</b><span>Prueba con otra palabra o quita algún filtro.</span>";
    var vb = botonLimpiar("btn-sec"); vacio.appendChild(vb);
    barra.parentNode.insertBefore(vacio, barra.nextSibling);
    var nCols = Array.prototype.slice.call(document.querySelectorAll(".contenido .embudo .col-cab .n"));
    nCols.forEach(function (n) { n.dataset.total = n.textContent; });

    function aplicar(guarda) {
      var texto = q.value.trim().toLowerCase(), visibles = 0;
      function pasa(fila) {
        if (texto && normal(fila).toLowerCase().indexOf(texto) < 0) return false;
        return selectores.every(function (s) { if (!s.el.value) return true; var c = fila.cells[s.col]; return !!c && valorCelda(c) === s.el.value; });
      }
      filasPorTabla.forEach(function (filas) { filas.forEach(function (f) { var ok = pasa(f); f.hidden = !ok; if (ok) visibles++; }); });
      tarjetas.forEach(function (t) { var ok = !texto || normal(t).toLowerCase().indexOf(texto) >= 0; t.hidden = !ok; if (ok) visibles++; });
      nCols.forEach(function (n) { var col = n.closest(".col"); n.textContent = texto ? col.querySelectorAll(".tarjeta:not([hidden])").length : n.dataset.total; });
      var filtrando = !!texto || selectores.some(function (s) { return s.el.value; });
      limpiar.hidden = !filtrando;
      cuenta.textContent = filtrando ? "Mostrando " + visibles + " de " + total : total + (total === 1 ? " resultado" : " resultados");
      vacio.hidden = visibles > 0;
      tablas.forEach(function (t) { t.closest(".tabla-caja").hidden = visibles === 0; });
      if (guarda) {
        var e = {q: limpio(q.value)}; selectores.forEach(function (s) { e[s.nombre] = s.el.value; });
        if (e.q || selectores.some(function (s) { return e[s.nombre]; })) guardar("#lista", e); else borrar("#lista");
      }
    }
    function restablecer() { q.value = ""; selectores.forEach(function (s) { s.el.value = ""; }); aplicar(true); }
    var timer = null;
    q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { aplicar(true); }, 200); });
    selectores.forEach(function (s) { s.el.addEventListener("change", function () { aplicar(true); }); });
    limpiar.addEventListener("click", restablecer); vb.addEventListener("click", restablecer);
    var g = leer("#lista");
    if (g && typeof g === "object") {
      q.value = limpio(g.q || "");
      selectores.forEach(function (s) { var v = g[s.nombre]; if (typeof v === "string" && s.opciones.indexOf(v) >= 0) s.el.value = v; });
    }
    aplicar(false);
  }

  /* al cerrar sesión se olvidan los filtros de esta cuenta (el botón de salir de la tienda envía el formulario con form.submit(), que no dispara «submit»: por eso también se escucha el clic) */
  var SALIR = 'form[action$="/cuenta/salir/"]';
  document.addEventListener("submit", function (e) { if (e.target && e.target.matches && e.target.matches(SALIR)) borrarTodoDeEstaCuenta(); }, true);
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest(SALIR + " button")) borrarTodoDeEstaCuenta(); }, true);

  var form = formularioGet();
  if (form) iniciarFormulario(form);
  iniciarPestanas();
  iniciarListas();
})();
