/* Cofrial SpA · avisos del equipo interno: la campana del menú con lo que cada rol debe atender (lo decide el servidor en cofrial/avisos_equipo.py).
   Pregunta cada 15 s, con un conteo por aviso. Cuando un número sube: mensaje dentro de la página y, si la persona dio permiso, notificación del navegador.
   Con la pestaña oculta sigue preguntando solo si hay permiso de notificaciones: es justo cuando sirven. Si no, se detiene hasta que vuelva. */
(function () {
  var btn = document.getElementById("avisos-equipo-btn"), panel = document.getElementById("avisos-equipo-panel"), n = document.getElementById("avisos-equipo-n"),
      enMenu = document.getElementById("avisos-equipo-n-menu"), toasts = document.getElementById("toasts");
  if (!btn || !panel || !window.fetch) return;
  var RUTA = "/api/avisos-equipo/", CADA_MS = 15000, CLAVE = "cofrial-avisos-equipo-" + (document.body.getAttribute("data-u") || ""),
      tituloBase = document.title, temporizador = null, sigue = true, cargado = false, actuales = [];

  function nodo(tag, clase, texto) { var e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; }
  function conocidos() { try { return JSON.parse(localStorage.getItem(CLAVE)); } catch (e) { return null; } }
  function recordar(v) { try { localStorage.setItem(CLAVE, JSON.stringify(v)); } catch (e) {} }
  function permisos() { return window.CofrialPermisos; }

  function mostrarMensaje(a) {
    if (!toasts) return;
    var t = nodo("div", "toast" + (a.urgente ? " t-frio" : "")), e = nodo("a", "", a.texto);
    e.href = a.url; t.appendChild(e); toasts.appendChild(t);
    setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 400); }, a.urgente ? 15000 : 8000);
  }
  /* La primera vez en este navegador solo se toma nota: avisar de todo lo que ya estaba pendiente sería ruido. */
  function avisarNovedades(avisos) {
    var antes = conocidos(), ahora = {};
    avisos.forEach(function (a) {
      ahora[a.id] = a.n;
      if (antes && a.n > (antes[a.id] || 0)) {
        mostrarMensaje(a);
        if (permisos()) permisos().notificar({id: a.id + ":" + a.n, texto: a.texto, url: a.url});
      }
    });
    recordar(ahora);
  }
  function pintar(avisos) {
    actuales = avisos;
    var total = avisos.reduce(function (s, a) { return s + a.n; }, 0), urgente = avisos.some(function (a) { return a.urgente; });
    n.hidden = total === 0; n.textContent = total; n.classList.toggle("urgente", urgente);
    if (enMenu) { enMenu.hidden = total === 0; enMenu.textContent = total; }
    btn.classList.remove("sin-actualizar");
    btn.setAttribute("aria-label", total ? "Avisos: " + total + " por atender" : "Avisos: nada por atender");
    document.title = (total ? "(" + total + ") " : "") + tituloBase;
    pintarPanel();
  }
  function pintarPanel(nota) {
    panel.innerHTML = "";
    if (!actuales.length && cargado) panel.appendChild(nodo("p", "", "Nada por atender por ahora."));
    if (actuales.length) {
      var ul = nodo("ul");
      actuales.forEach(function (a) { var li = nodo("li"), e = nodo("a", a.urgente ? "urgente" : "", a.texto); e.href = a.url; li.appendChild(e); ul.appendChild(li); });
      panel.appendChild(ul);
    }
    if (nota) panel.appendChild(nodo("small", "", nota));
  }
  function programar() {
    clearTimeout(temporizador);
    if (!sigue) return;
    if (document.hidden && !(permisos() && permisos().activas())) return;
    temporizador = setTimeout(cargar, CADA_MS);
  }
  function fallo() {
    btn.classList.add("sin-actualizar");
    if (!cargado) { panel.innerHTML = ""; panel.appendChild(nodo("p", "", "No pudimos cargar los avisos. Volveremos a intentarlo.")); }
    else pintarPanel("Sin actualizar: mostramos lo último que supimos.");
    document.dispatchEvent(new CustomEvent("cofrial:avisos-equipo-fallo"));
  }
  function cargar() {
    fetch(RUTA, {credentials: "same-origin", headers: {"Accept": "application/json"}}).then(function (r) {
      if (r.status === 403) { sigue = false; throw new Error("sin acceso"); }        // la sesión terminó: dejar de preguntar
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      cargado = true;
      avisarNovedades(d.avisos); pintar(d.avisos);
      document.dispatchEvent(new CustomEvent("cofrial:avisos-equipo", {detail: d}));
    }).catch(fallo).then(programar);
  }
  btn.addEventListener("click", function () {
    var abre = panel.hidden; panel.hidden = !abre; btn.setAttribute("aria-expanded", abre);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden && !document.querySelector("dialog[open]")) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) programar(); else if (sigue) { clearTimeout(temporizador); cargar(); }
  });
  cargar();
})();
