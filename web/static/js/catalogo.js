/* Cofrial SpA · filtros del catálogo en vivo. Al cambiar un filtro (o tras una breve pausa al escribir) se pide el catálogo
   con los mismos parámetros que usaría el formulario y se reemplazan solo los resultados y el contador: sin recargar la página.
   Sin JavaScript el formulario sigue funcionando con su botón "Aplicar filtros". */
(function () {
  var form = document.getElementById("form-filtros"), cont = document.getElementById("productos");
  if (!form || !cont || !window.fetch || !window.URLSearchParams) return;
  var contador = document.getElementById("cat-contador"), chips = document.getElementById("cat-chips"),
      resumen = document.getElementById("filtros-resumen"), limpiar = document.getElementById("filtros-limpiar"),
      detalle = document.getElementById("filtros-det"), q = form.elements.q, vivo = document.getElementById("cat-vivo");
  var temporizador = null, control = null, pausa = 350;
  document.documentElement.classList.add("filtros-vivos");   // oculta "Aplicar filtros" (con JS no hace falta)

  function etiqueta(el) { var l = el.closest("label"); return l ? l.textContent.replace(/\s+/g, " ").trim() : ""; }
  function activos() {
    var a = [], txt = q.value.trim();
    if (txt) a.push({tipo: "q", texto: "\"" + txt + "\""});
    form.querySelectorAll('input[name="categoria"]:checked').forEach(function (c) { a.push({tipo: "categoria", valor: c.value, texto: etiqueta(c)}); });
    form.querySelectorAll('input[name="temperatura"]:checked').forEach(function (t) { a.push({tipo: "temperatura", valor: t.value, texto: etiqueta(t).replace(/\s*\(.*\)$/, "")}); });
    var s = form.elements.stock; if (s && s.checked) a.push({tipo: "stock", texto: "Solo con stock"});
    return a;
  }
  function params() {
    var p = new URLSearchParams();
    if (q.value.trim()) p.set("q", q.value.trim());
    form.querySelectorAll('input[name="categoria"]:checked').forEach(function (c) { p.append("categoria", c.value); });
    form.querySelectorAll('input[name="temperatura"]:checked').forEach(function (t) { p.append("temperatura", t.value); });
    if (form.elements.stock && form.elements.stock.checked) p.set("stock", "1");
    return p;
  }
  function pintarEstado() {
    var a = activos(), n = a.length;
    if (limpiar) limpiar.hidden = n === 0;
    if (resumen) { resumen.textContent = n ? n + (n === 1 ? " activo" : " activos") : ""; resumen.hidden = n === 0; }
    if (chips) {
      chips.hidden = n === 0; chips.innerHTML = "";
      a.forEach(function (f) {
        var b = document.createElement("button"); b.type = "button"; b.className = "chip-filtro"; b.dataset.quitar = f.tipo; if (f.valor) b.dataset.valor = f.valor;
        b.setAttribute("aria-label", "Quitar filtro " + f.texto); b.innerHTML = "";
        b.appendChild(document.createTextNode(f.texto + " ")); var x = document.createElement("span"); x.setAttribute("aria-hidden", "true"); x.textContent = "×"; b.appendChild(x);
        chips.appendChild(b);
      });
    }
  }
  function aplicar() {
    clearTimeout(temporizador);
    var p = params(), url = "/catalogo/" + (p.toString() ? "?" + p.toString() : "");
    if (control) control.abort();
    control = window.AbortController ? new AbortController() : null;
    cont.setAttribute("aria-busy", "true"); cont.classList.add("cargando");
    fetch(url, {headers: {"Accept": "text/html"}, credentials: "same-origin", signal: control ? control.signal : undefined})
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var nuevo = doc.getElementById("productos"), cnt = doc.getElementById("cat-contador");
        if (!nuevo) throw new Error("sin resultados");
        cont.innerHTML = nuevo.innerHTML;
        if (cnt && contador) contador.innerHTML = cnt.innerHTML;
        if (window.CofrialTienda) window.CofrialTienda.iniciarCant(cont);
        history.replaceState(null, "", url);
        if (vivo) vivo.textContent = (cnt ? cnt.textContent.split("·")[0].trim() : "Resultados actualizados");
        var vb = document.getElementById("filtros-ver"); if (vb && cnt) vb.textContent = "Ver " + cnt.textContent.split("·")[0].trim();
      })
      .catch(function (e) { if (e && e.name === "AbortError") return; location.href = url; })   // si algo falla, carga normal
      .then(function () { cont.removeAttribute("aria-busy"); cont.classList.remove("cargando"); });
  }
  function programar() { pintarEstado(); clearTimeout(temporizador); temporizador = setTimeout(aplicar, pausa); }
  function restablecer() {
    form.reset();                                   // vuelve a los valores iniciales del HTML… que pueden traer filtros, así que se fuerzan:
    q.value = "";
    form.querySelectorAll('input[name="categoria"], input[name="temperatura"]').forEach(function (r) { r.checked = false; });
    if (form.elements.stock) form.elements.stock.checked = false;
    pintarEstado(); aplicar();
  }

  form.addEventListener("change", function (e) { if (e.target !== q) { pintarEstado(); aplicar(); } });   // radios y casilla: al instante
  q.addEventListener("input", programar);                                                                  // buscador: con pausa
  form.addEventListener("submit", function (e) { e.preventDefault(); pintarEstado(); aplicar(); });         // Enter en el buscador
  document.addEventListener("click", function (e) {
    if (!form.isConnected) return;       // al volver a esta pestaña el script corre de nuevo: este oyente quedó de la visita anterior
    var l = e.target.closest("[data-limpiar]"); if (l) { e.preventDefault(); restablecer(); return; }
    var x = e.target.closest("[data-quitar]");
    if (x) {
      var t = x.dataset.quitar;
      if (t === "q") q.value = ""; else if (t === "stock") form.elements.stock.checked = false;
      else { var r = form.querySelector('input[name="' + t + '"][value="' + x.dataset.valor + '"]'); if (r) r.checked = false; }
      pintarEstado(); aplicar();
    }
    if (e.target.closest("[data-cerrar-filtros]") && detalle) { detalle.removeAttribute("open"); var m = document.getElementById("cat-inicio"); if (m) m.scrollIntoView({behavior: "smooth", block: "start"}); }
  });
  /* en móvil los filtros parten cerrados; la barra de filtros queda pegada bajo el encabezado, que puede cambiar de alto */
  if (detalle && matchMedia("(max-width: 860px)").matches && !activos().length) detalle.removeAttribute("open");
  pintarEstado();
})();
