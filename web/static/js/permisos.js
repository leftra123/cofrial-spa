/* Cofrial SpA · permisos del navegador y notificaciones nativas. El navegador exige un gesto de la persona y un contexto seguro (HTTPS o localhost):
   por eso primero explicamos para qué es cada permiso en un diálogo propio, una vez por cuenta y navegador, y el aviso nativo sale al tocar el botón.
   Por http no se puede pedir nada: el diálogo lo dice y los avisos siguen dentro de la página. Aquí no se manda nada al servidor. */
(function () {
  var dialogo = document.getElementById("permisos");
  var seguro = window.isSecureContext === true;
  var CLAVE_ENVIADOS = "cofrial-notificados", ICONO = dialogo ? dialogo.getAttribute("data-icono") : "";

  function hayNotificaciones() { return seguro && "Notification" in window; }
  function hayUbicacion() { return seguro && "geolocation" in navigator; }
  function activas() { return hayNotificaciones() && Notification.permission === "granted"; }
  function leer(clave, defecto) { try { return JSON.parse(localStorage.getItem(clave)) || defecto; } catch (e) { return defecto; } }
  function guardar(clave, valor) { try { localStorage.setItem(clave, JSON.stringify(valor)); return true; } catch (e) { return false; } }

  /* Notificación nativa, una sola vez por id aunque haya varias pestañas abiertas. Devuelve false si no se pudo: Android y iOS la exigen
     desde un service worker o una app instalada, y ahí queda el aviso dentro de la página. */
  function notificar(a) {
    if (!activas()) return false;
    var enviados = leer(CLAVE_ENVIADOS, []);
    if (enviados.indexOf(a.id) >= 0) return true;
    enviados.push(a.id); guardar(CLAVE_ENVIADOS, enviados.slice(-200));
    try {
      var n = new Notification(a.titulo || "Cofrial", {body: a.texto, tag: a.id, icon: ICONO});
      n.onclick = function () { window.focus(); if (a.url) location.href = a.url; n.close(); };
      return true;
    } catch (e) { return false; }
  }
  window.CofrialPermisos = {notificar: notificar, activas: activas};

  /* ---- «Usar mi ubicación» al agregar una dirección de entrega ---- */
  var PRECISION_MAXIMA_M = 300;        // con peor precisión el camión iría a otra cuadra: mejor buscar la dirección escrita
  document.querySelectorAll("[data-usar-ubicacion]").forEach(function (caja) {
    if (!hayUbicacion()) return;
    var form = caja.closest("form"), estado = caja.querySelector("[data-usar-ubicacion-estado]"), boton = caja.querySelector("[data-usar-ubicacion-btn]");
    caja.hidden = false;
    boton.addEventListener("click", function () {
      estado.textContent = "Buscando tu ubicación…";
      navigator.geolocation.getCurrentPosition(function (p) {
        if (p.coords.accuracy > PRECISION_MAXIMA_M) {
          form.elements.lat.value = form.elements.long.value = "";
          estado.textContent = "Tu ubicación es poco precisa (unos " + Math.round(p.coords.accuracy) + " m). Buscaremos la dirección que escribiste.";
          return;
        }
        form.elements.lat.value = p.coords.latitude; form.elements.long.value = p.coords.longitude;
        estado.textContent = "Listo: al guardar, usaremos tu ubicación actual como punto de entrega.";
      }, function (e) {
        estado.textContent = e.code === 1 ? "El navegador no tiene permiso para usar tu ubicación. Buscaremos la dirección que escribiste." : "No pudimos obtener tu ubicación. Buscaremos la dirección que escribiste.";
      }, {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000});
    });
  });

  if (!dialogo || !dialogo.showModal) return;

  /* ---- diálogo ---- */
  var CLAVE_VISTO = "cofrial-permisos-" + dialogo.getAttribute("data-u"), filas = {};
  dialogo.querySelectorAll("[data-permiso]").forEach(function (f) { filas[f.getAttribute("data-permiso")] = f; });
  var cerrar = dialogo.querySelector("[data-permisos-cerrar]");

  function pintarFila(nombre, estado) {
    var f = filas[nombre]; if (!f) return;
    var b = f.querySelector("[data-permiso-pedir]"), s = f.querySelector("[data-permiso-estado]");
    var textos = {granted: "Activado.", denied: "Bloqueado en este navegador. Se cambia en el ícono junto a la dirección del sitio, en Permisos.",
                  inseguro: "No disponible sin conexión segura.", nosoporta: "Este navegador no lo permite aquí; los avisos siguen dentro de la página.", prompt: ""};
    s.textContent = textos[estado] || "";
    b.hidden = estado !== "prompt";
    pintarPie();
  }
  function pintarPie() {
    var pendiente = Object.keys(filas).some(function (n) { return !filas[n].querySelector("[data-permiso-pedir]").hidden; });
    cerrar.textContent = pendiente ? "Ahora no" : "Listo";
  }
  function estadoDe(nombre, listo) {
    if (!seguro) return listo("inseguro");
    if (nombre === "notificaciones") {
      if (!hayNotificaciones()) return listo("nosoporta");
      return listo(Notification.permission === "default" ? "prompt" : Notification.permission);
    }
    if (!hayUbicacion()) return listo("nosoporta");
    if (!navigator.permissions) return listo("prompt");       // Safari antiguo: no se puede saber sin preguntar
    navigator.permissions.query({name: "geolocation"}).then(function (r) { listo(r.state); }, function () { listo("prompt"); });
  }
  function refrescar(listo) {
    var nombres = Object.keys(filas), faltan = nombres.length, estados = {};
    nombres.forEach(function (n) {
      estadoDe(n, function (e) { estados[n] = e; pintarFila(n, e); if (--faltan === 0 && listo) listo(estados); });
    });
  }
  function pedir(nombre) {
    if (nombre === "notificaciones") {
      Notification.requestPermission().then(function (r) {
        var estado = r === "default" ? "prompt" : r;
        pintarFila(nombre, estado);
        if (estado === "granted" && !notificar({id: "permisos-activados", texto: "Listo: te avisaremos por aquí."})) pintarFila(nombre, "nosoporta");
      });
    } else {
      navigator.geolocation.getCurrentPosition(function () { pintarFila(nombre, "granted"); }, function (e) { pintarFila(nombre, e.code === 1 ? "denied" : "prompt"); },
        {timeout: 10000, maximumAge: 600000});      // solo abre la pregunta del navegador: la posición se descarta aquí
    }
  }
  function abrir() { if (dialogo.open) return; refrescar(); dialogo.querySelector("[data-permisos-inseguro]").hidden = seguro; dialogo.querySelector("[data-permisos-intro]").hidden = !seguro; dialogo.showModal(); }

  Object.keys(filas).forEach(function (n) { filas[n].querySelector("[data-permiso-pedir]").addEventListener("click", function () { pedir(n); }); });
  cerrar.addEventListener("click", function () { dialogo.close(); });
  document.querySelectorAll("[data-permisos-abrir]").forEach(function (b) { b.addEventListener("click", abrir); });

  /* Se abre solo una vez por cuenta y navegador. Sin almacenamiento no se abre: reaparecería en cada página. Si ya está todo resuelto, no molesta. */
  if (leer(CLAVE_VISTO, null) !== null) return;
  refrescar(function (estados) {
    var algo = !seguro || Object.keys(estados).some(function (n) { return estados[n] === "prompt"; });
    if (!algo) return;
    setTimeout(function () {
      if (document.querySelector("dialog[open]")) return;       // no tapar otro diálogo, como la revisión de una entrega
      if (guardar(CLAVE_VISTO, Date.now())) abrir();
    }, 700);
  });
})();
