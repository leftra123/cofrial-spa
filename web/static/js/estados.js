/* Cofrial SpA · estados de la interfaz compartidos por toda la web (tienda, CRM y flota). Sin dependencias; mejora progresiva:
   si este script no carga, los formularios se envían y las páginas se leen igual que siempre.
   - ocupar(boton, texto): estado «cargando» de un botón (se deshabilita al tiro; el spinner aparece solo si tarda más de 300 ms).
   - [data-carga] en un <form>: aplica ese estado al enviar, con el texto de data-cargando en el botón.
   - [data-confirmar="texto"] en un botón: acción destructiva en dos pasos (el primer toque pide confirmar, el segundo envía).
   - [data-enter-avanza] en un <form>: Enter (o «Siguiente» del teclado del celular) pasa al campo que falta; con el campo vacío, o sin nada más que llenar, envía y el navegador avisa.
   - vivo(elemento, opciones): indicador de conexión de los paneles que se refrescan solos (conectando, en vivo, reintentando, sin conexión).
   - anunciar(texto): lo dice a los lectores de pantalla.
   - tiempo(x): prende o apaga el aviso de tiempo acelerado sin recargar (lo llaman los paneles que se refrescan solos). */
(function () {
  var RETARDO_SPINNER = 300, VENCE_CONFIRMAR = 5000;

  function anunciar(texto) {
    var vivo = document.getElementById("vivo");
    if (!vivo) {                                       // el CRM y la flota no traen la región «en vivo» de la tienda: se crea una
      vivo = document.createElement("div"); vivo.id = "vivo"; vivo.className = "solo-lector"; vivo.setAttribute("role", "status"); vivo.setAttribute("aria-live", "polite");
      document.body.appendChild(vivo);
    }
    vivo.textContent = ""; setTimeout(function () { vivo.textContent = texto; }, 50);
  }

  /* ---------- botón ocupado ---------- */
  function ocupar(b, texto) {
    if (!b) return function () {};
    var original = b.innerHTML, ancho = b.offsetWidth, t = setTimeout(function () {
      b.style.minWidth = ancho + "px";
      b.innerHTML = '<span class="spinner" aria-hidden="true"></span> ' + texto;
    }, RETARDO_SPINNER);
    b.setAttribute("aria-busy", "true"); b.disabled = true;
    return function (final, ms) {                       // final: texto opcional de confirmación (con ✓) que se muestra ms milisegundos
      clearTimeout(t); b.removeAttribute("aria-busy");
      function restaurar() { b.innerHTML = original; b.style.minWidth = ""; b.classList.remove("hecho"); b.disabled = false; }
      if (final) {
        b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" style="stroke:currentColor;fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round"><path d="M20 6L9 17l-5-5"/></svg> ' + final;
        b.classList.add("hecho"); setTimeout(restaurar, ms || 1200);
      } else restaurar();
    };
  }

  /* ---------- envío con estado de carga ---------- */
  document.addEventListener("submit", function (e) {
    var f = e.target, b = e.submitter || (f.querySelector && f.querySelector("button:not([type=button])"));
    if (e.defaultPrevented || !f.hasAttribute || !f.hasAttribute("data-carga") || !b || b.disabled) return;
    var fin = ocupar(b, b.dataset.cargando || "Procesando…");
    window.addEventListener("pageshow", function () { fin(); }, {once: true});     // si el navegador vuelve atrás desde su caché, el botón queda usable
  });

  /* ---------- Enter avanza de campo ----------
     Sin esto, Enter en el usuario envía el formulario con la clave vacía. Avanza solo si el campo tiene texto y aún falta otro por llenar. Solo cuenta el Enter de un <input> de texto: un botón, una
     lista o un <textarea> conservan su comportamiento, y mientras una tilde o un teclado de otro idioma componen texto (isComposing) no se toca. */
  document.addEventListener("keydown", function (e) {
    var c = e.target, f = c && c.form;
    if (e.key !== "Enter" || e.isComposing || e.defaultPrevented || !f || c.tagName !== "INPUT" || !f.hasAttribute("data-enter-avanza")) return;
    var campos = Array.prototype.filter.call(f.elements, function (x) {
      return x.tagName === "INPUT" && !x.disabled && !x.readOnly && x.offsetParent !== null && ["hidden", "submit", "button", "checkbox", "radio"].indexOf(x.type) < 0;
    });
    var i = campos.indexOf(c);
    if (i < 0 || !c.value) return;                      // campo vacío: Enter envía y el navegador marca el que falta, en vez de pasar al siguiente sin avisar
    var falta = campos.slice(i + 1).filter(function (x) { return !x.value; })[0];
    if (!falta) return;                                 // el último campo, o el gestor de claves ya llenó los demás: Enter envía como siempre
    e.preventDefault(); falta.focus();
  });

  /* ---------- confirmación en dos pasos ---------- */
  var pendiente = null;
  function cancelarConfirmacion() {
    if (!pendiente) return;
    var b = pendiente.boton; clearTimeout(pendiente.t);
    b.innerHTML = pendiente.html; b.classList.remove("confirmando"); delete b.dataset.confirmando; pendiente = null;
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-confirmar]");
    if (!b) { cancelarConfirmacion(); return; }
    if (b.dataset.confirmando) return;                  // segundo toque: el envío sigue su curso
    cancelarConfirmacion();
    e.preventDefault();
    pendiente = {boton: b, html: b.innerHTML, t: setTimeout(cancelarConfirmacion, VENCE_CONFIRMAR)};
    b.dataset.confirmando = "1"; b.classList.add("confirmando"); b.textContent = b.dataset.confirmar;
    anunciar(b.dataset.confirmar + " Vuelve a presionar para confirmar.");
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") cancelarConfirmacion(); });

  /* ---------- indicador de conexión de un panel en vivo ----------
     Estados: conectando (aún sin datos) → vivo → retraso (1 fallo) → caido (2 o más, o sin red). Al caer muestra hace cuánto es el último dato bueno.
     Los datos viejos siguen en pantalla, pero rotulados: un valor sin fecha parece actual y no lo es. */
  var TEXTOS = {conectando: "Conectando…", vivo: "En vivo", retraso: "Reintentando…"};
  function vivo(el, opciones) {
    opciones = opciones || {};
    if (!el) return {ok: function () {}, falla: function () {}, estado: function () { return "conectando"; }};
    var estado = "", fallos = 0, ultimo = null, reloj = null, avisar = opciones.alCambiar || function () {};
    function hace() {
      var s = Math.max(0, Math.round((Date.now() - ultimo) / 1000));
      return s < 60 ? s + " s" : s < 3600 ? Math.floor(s / 60) + " min" : Math.floor(s / 3600) + " h";
    }
    function pintar() {
      var texto = estado === "caido" ? (ultimo ? "Sin conexión · último dato hace " + hace() : "Sin conexión") : (estado === "vivo" && opciones.etiqueta) || TEXTOS[estado];
      el.textContent = texto; el.hidden = false;
    }
    function poner(nuevo) {
      var cambio = nuevo !== estado; estado = nuevo; el.dataset.estado = nuevo;
      pintar();
      if (nuevo === "caido" && !reloj) reloj = setInterval(pintar, 1000);
      if (nuevo !== "caido" && reloj) { clearInterval(reloj); reloj = null; }
      if (cambio) {
        if (nuevo === "caido") anunciar("Se perdió la conexión. Mostramos el último dato recibido.");
        else if (nuevo === "vivo" && fallos) anunciar("Conexión recuperada.");
        avisar(nuevo);
      }
    }
    el.setAttribute("role", "status"); el.classList.add("vivo");
    poner("conectando");
    window.addEventListener("offline", function () { fallos = Math.max(fallos, 2); poner("caido"); });
    window.addEventListener("online", function () { if (estado === "caido") poner("retraso"); });
    return {
      ok: function () { ultimo = Date.now(); poner("vivo"); fallos = 0; },
      falla: function () { fallos++; poner(fallos >= 2 || !navigator.onLine ? "caido" : "retraso"); },
      estado: function () { return estado; }
    };
  }

  /* ---------- errores de un formulario ---------- */
  var resumen = document.getElementById("resumen-errores");
  if (resumen) resumen.focus();

  function tiempo(x) {
    var aviso = document.getElementById("tiempo-acelerado");
    if (!aviso) return;
    aviso.hidden = !(x > 1);
    if (x > 1) aviso.querySelector("[data-tiempo-x]").textContent = x + "×";
  }

  window.CofrialEstados = {ocupar: ocupar, anunciar: anunciar, vivo: vivo, tiempo: tiempo};
})();
