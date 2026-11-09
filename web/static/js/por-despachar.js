/* Cofrial SpA · contador de pedidos por despachar del menú interno (admin, gerencia y despachador; la plantilla solo lo carga a ellos).
   El número llega con la consulta común de avisos-equipo.js; la sugerencia se pide a /flota/por-despachar/?detalle=1 recién al abrir el contador.
   Un fallo no se disfraza: el número queda atenuado y dice «sin actualizar». */
(function () {
  var btn = document.getElementById("despacho-n"), panel = document.getElementById("despacho-panel"), vivo = document.getElementById("despacho-vivo");
  if (!btn || !panel || !window.fetch) return;
  var RUTA = "/flota/por-despachar/", ultimo = null, vez = 0;

  function frase(n) { return n === 1 ? "1 pedido por despachar" : n + " pedidos por despachar"; }
  function nodo(tag, texto) { var n = document.createElement(tag); n.textContent = texto; return n; }
  function pedir(url) {
    return fetch(url, {credentials: "same-origin", headers: {"Accept": "application/json"}}).then(function (r) {
      if (r.redirected || r.status === 403) throw new Error("sin acceso");
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function cerrar() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); }
  function pintar(total, refrescar) {
    btn.hidden = total === 0; btn.textContent = total; btn.classList.remove("sin-actualizar");
    btn.setAttribute("aria-label", frase(total) + ": ver la sugerencia"); btn.title = frase(total);
    if (total === 0) cerrar();
    var cambio = ultimo !== null && total !== ultimo;
    ultimo = total;
    if (cambio) {
      if (vivo) vivo.textContent = frase(total);            // lo anuncia el lector de pantalla solo si cambió, no en cada página
      if (refrescar && !panel.hidden) detalle();
    }
  }
  function sinActualizar() {
    if (ultimo === null) return;
    btn.classList.add("sin-actualizar"); btn.title = frase(ultimo) + " (sin actualizar)"; btn.setAttribute("aria-label", btn.title + ": ver la sugerencia");
  }
  /* El número llega con la consulta común de avisos-equipo.js, para no sumar otra consulta periódica por pestaña. */
  document.addEventListener("cofrial:avisos-equipo", function (e) {
    var a = e.detail.avisos.filter(function (x) { return x.id === "por_despachar"; })[0];
    pintar(a ? a.n : 0, true);
  });
  document.addEventListener("cofrial:avisos-equipo-fallo", sinActualizar);
  function mostrar(texto, acciones) {
    panel.innerHTML = ""; panel.setAttribute("aria-busy", "false");
    panel.appendChild(nodo("p", texto));
    acciones.forEach(function (a) { var e = nodo("a", a.texto); e.href = a.url; panel.appendChild(e); });
  }
  function detalle() {
    var esta = ++vez;
    if (!panel.firstChild) panel.appendChild(nodo("p", "Revisando los pedidos…"));
    panel.setAttribute("aria-busy", "true");
    pedir(RUTA + "?detalle=1").then(function (d) {
      if (esta !== vez) return;                              // llegó otra respuesta más nueva mientras tanto
      mostrar(d.texto, d.acciones); pintar(d.total, false);
    }).catch(function () {
      if (esta === vez) mostrar("No pudimos calcular la sugerencia. Flota la muestra al abrirla.", [{texto: "Ir a Flota", url: "/flota/"}]);
    });
  }
  btn.addEventListener("click", function () {
    var abre = panel.hidden; panel.hidden = !abre; btn.setAttribute("aria-expanded", abre);
    if (abre) detalle();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { cerrar(); btn.focus(); } });
})();
