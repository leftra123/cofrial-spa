/* Cofrial SpA · microinteracciones de la tienda (sin dependencias). Mejora progresiva: si algo falla, los formularios siguen funcionando como siempre. */
(function () {
  var RETARDO_SPINNER = 300, TIEMPO_MAX = 8000, MUESTRA_OK = 1200;

  /* ---------- cantidades +/− ---------- */
  function iniciarCant(raiz) {
    (raiz || document).querySelectorAll(".cant").forEach(function (c) {
      if (c.dataset.listo) return; c.dataset.listo = "1";
      var i = c.querySelector("input"), menos = c.querySelector("[data-menos]"), mas = c.querySelector("[data-mas]");
      if (!i || !menos || !mas) return;
      var max = parseInt(i.max, 10) || 9999, min = parseInt(i.min, 10), espera = null, form = c.closest(".linea-form");
      if (isNaN(min)) min = 1;
      function poner(v, enviar) {
        i.value = Math.max(min, Math.min(max, v)); menos.disabled = +i.value <= min; mas.disabled = +i.value >= max;
        if (enviar && form) { clearTimeout(espera); espera = setTimeout(function () { if (form.requestSubmit) form.requestSubmit(); }, 700); }   // en el carrito se guarda solo tras una pausa
      }
      menos.addEventListener("click", function () { poner((parseInt(i.value, 10) || min) - 1, true); });
      mas.addEventListener("click", function () { poner((parseInt(i.value, 10) || min) + 1, true); });
      i.addEventListener("change", function () { poner(parseInt(i.value, 10) || min, true); });
      poner(parseInt(i.value, 10) || min, false);
    });
  }
  iniciarCant(document);

  /* ---------- aviso al usuario ---------- */
  /* los contenedores van al final de la página, después de este script: se buscan en el momento de usarlos */
  function anunciar(texto) { var vivo = document.getElementById("vivo"); if (vivo) { vivo.textContent = ""; setTimeout(function () { vivo.textContent = texto; }, 50); } }
  function aviso(texto, tipo) {
    var toasts = document.getElementById("toasts"); if (!toasts) return;
    var t = document.createElement("div"); t.className = "toast t-" + (tipo || "info"); t.setAttribute("role", tipo === "error" ? "alert" : "status"); t.textContent = texto;
    toasts.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 300); }, tipo === "error" ? 7000 : 4000);
  }
  function contador(n) {
    document.querySelectorAll("[data-carrito-n]").forEach(function (e) {
      var antes = e.textContent; e.textContent = n; e.hidden = !n;
      if (n && antes !== String(n)) { e.classList.remove("pop"); void e.offsetWidth; e.classList.add("pop"); }
    });
  }

  /* ---------- estado de carga de un botón ---------- */
  /* Se deshabilita al tiro (sin doble envío) pero el spinner y el texto aparecen solo si tarda más de 300 ms: una respuesta rápida no parpadea. */
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
      if (final) { b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" style="stroke:currentColor;fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round"><path d="M20 6L9 17l-5-5"/></svg> ' + final; b.classList.add("hecho"); setTimeout(restaurar, ms || MUESTRA_OK); }
      else restaurar();
    };
  }
  function pedir(form, extra) {
    var ctl = window.AbortController ? new AbortController() : null, corte = setTimeout(function () { if (ctl) ctl.abort(); }, TIEMPO_MAX);
    var cab = {"X-Requested-With": "fetch"}; for (var k in extra) cab[k] = extra[k];
    return fetch(form.action, {method: "POST", body: new FormData(form), credentials: "same-origin", headers: cab, signal: ctl ? ctl.signal : undefined})
      .then(function (r) { clearTimeout(corte); return r; }, function (e) { clearTimeout(corte); throw e; });
  }
  var ERROR_RED = "No pudimos completar la acción. Revisa tu conexión e inténtalo de nuevo.";

  /* ---------- agregar al carrito sin recargar ---------- */
  function agregar(form, boton) {
    var fin = ocupar(boton, "Agregando…");
    pedir(form, {"Accept": "application/json"}).then(function (r) {
      if (r.redirected && /\/cuenta\/entrar/.test(r.url)) { location.href = r.url; return null; }
      return r.json();
    }).then(function (d) {
      if (!d) return;
      var errores = d.mensajes.filter(function (m) { return m.tipo === "error"; });
      if (d.ok) { fin("Agregado", MUESTRA_OK); contador(d.carrito_n); anunciar("Producto agregado al carrito. Hay " + d.carrito_n + " en total."); }
      else { fin(); var t = errores.map(function (m) { return m.texto; }).join(" ") || ERROR_RED; aviso(t, "error"); anunciar(t); }
    }).catch(function () { fin(); aviso(ERROR_RED, "error"); anunciar(ERROR_RED); });
  }

  /* ---------- actualizar el carrito sin recargar: se trae la página y se cambia solo el contenido ---------- */
  function actualizarCarrito(form, boton) {
    var linea = form.closest(".linea"), fin = ocupar(boton, "Actualizando…");
    if (linea) linea.classList.add("cargando");
    pedir(form, {"Accept": "text/html"}).then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, "text/html"), nuevo = doc.getElementById("contenido"), actual = document.getElementById("contenido");
      if (!nuevo || !actual) throw new Error("sin contenido");
      actual.innerHTML = nuevo.innerHTML; iniciarCant(actual);
      var n = doc.querySelector("[data-carrito-n]"); if (n) contador(parseInt(n.textContent, 10) || 0);
      anunciar("Carrito actualizado.");
    }).catch(function () { fin(); if (linea) linea.classList.remove("cargando"); aviso(ERROR_RED, "error"); anunciar(ERROR_RED); });
  }

  document.addEventListener("submit", function (e) {
    var f = e.target, b = e.submitter || f.querySelector("button:not([type=button])");
    if (!window.fetch || !window.FormData || e.defaultPrevented) return;
    if (f.matches('form[action="/carrito/agregar/"]')) { e.preventDefault(); if (!b || !b.disabled) agregar(f, f.querySelector(".agregar") || b); }
    else if (f.matches('.linea-form[action="/carrito/actualizar/"]')) { e.preventDefault(); if (!b || !b.disabled) actualizarCarrito(f, f.querySelector(".btn-sec")); }
    else if (f.hasAttribute("data-carga") && b && !b.disabled) {              // «Generar orden», soporte: envío normal, con el mismo estado de carga del botón
      var fin = ocupar(b, b.dataset.cargando || "Procesando…");
      window.addEventListener("pageshow", function () { fin(); }, {once: true});  // si el navegador vuelve atrás desde su caché, el botón queda usable
    }
  });
  window.CofrialTienda = {iniciarCant: iniciarCant};
})();
