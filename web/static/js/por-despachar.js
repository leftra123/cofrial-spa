/* Cofrial SpA · contador de pedidos por despachar del menú interno (admin, gerencia y despachador; la plantilla solo lo carga a ellos).
   Cada 30 s pregunta /flota/por-despachar/, que es un solo COUNT; la sugerencia se calcula recién al abrir el contador.
   Con la pestaña oculta no pregunta. Un fallo no se disfraza: el número queda atenuado y dice «sin actualizar». */
(function () {
  var btn = document.getElementById("despacho-n"), panel = document.getElementById("despacho-panel"), vivo = document.getElementById("despacho-vivo"),
      enMenu = document.getElementById("despacho-n-menu");
  if (!btn || !panel || !window.fetch) return;
  var RUTA = "/flota/por-despachar/", CADA_MS = 30000, ultimo = null, temporizador = null, sigue = true, vez = 0;

  function frase(n) { return n === 1 ? "1 pedido por despachar" : n + " pedidos por despachar"; }
  function nodo(tag, texto) { var n = document.createElement(tag); n.textContent = texto; return n; }
  function pedir(url) {
    return fetch(url, {credentials: "same-origin", headers: {"Accept": "application/json"}}).then(function (r) {
      if (r.redirected || r.status === 403) { sigue = false; throw new Error("sin acceso"); }      // la sesión terminó o cambió el rol: dejar de preguntar
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function cerrar() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); }
  function pintar(total, refrescar) {
    btn.hidden = total === 0; btn.textContent = total; btn.classList.remove("sin-actualizar");
    btn.setAttribute("aria-label", frase(total) + ": ver la sugerencia"); btn.title = frase(total);
    if (enMenu) { enMenu.hidden = total === 0; enMenu.textContent = total; }
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
  function programar() { clearTimeout(temporizador); if (sigue && !document.hidden) temporizador = setTimeout(cargar, CADA_MS); }
  function cargar() {
    pedir(RUTA).then(function (d) { pintar(d.total, true); }).catch(sinActualizar).then(programar);
  }
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
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) clearTimeout(temporizador); else if (sigue) cargar();
  });
  cargar();
})();
