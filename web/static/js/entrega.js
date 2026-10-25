/* Cofrial SpA · «Estamos afuera»: el cliente confirma la entrega o cuenta por qué no pudo recibirla.
   Mejora progresiva: sin este script los formularios de la pantalla del pedido envían igual (POST /pedidos/<id>/entrega/).
   - iniciar(raiz): pantalla del pedido (contador de caracteres, validación, envío sin recarga, cuenta regresiva suave).
   - modal(ordenId): el mismo formulario en un diálogo, para la campanita en cualquier página.
   - aceptar(ordenId): «Recibí mi pedido» directo, para la campanita. */
(function () {
  var MIN = 5, MAX = 500, TIEMPO_MAX = 10000;
  var anunciar = window.CofrialEstados ? CofrialEstados.anunciar : function () {}, ocupar = window.CofrialEstados ? CofrialEstados.ocupar : function () { return function () {}; };

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/), i = document.querySelector("input[name=csrfmiddlewaretoken]");
    return m ? decodeURIComponent(m[1]) : (i ? i.value : "");
  }
  function toast(texto, tipo) {
    var c = document.getElementById("toasts"); if (!c) return;
    var t = document.createElement("div"); t.className = "toast t-" + (tipo || "info"); t.setAttribute("role", tipo === "error" ? "alert" : "status"); t.textContent = texto;
    c.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 300); }, tipo === "error" ? 7000 : 5000);
  }
  function enviar(ordenId, accion, motivo) {
    var cuerpo = new FormData(); cuerpo.append("accion", accion); if (motivo != null) cuerpo.append("motivo", motivo);
    var ctl = window.AbortController ? new AbortController() : null, corte = setTimeout(function () { if (ctl) ctl.abort(); }, TIEMPO_MAX);
    return fetch("/pedidos/" + ordenId + "/entrega/", {method: "POST", body: cuerpo, credentials: "same-origin", signal: ctl ? ctl.signal : undefined,
                 headers: {"X-Requested-With": "fetch", "Accept": "application/json", "X-CSRFToken": csrf()}})
      .then(function (r) { clearTimeout(corte); return r.json().catch(function () { return {ok: false, mensaje: "No pudimos completar la acción. Inténtalo de nuevo."}; }); },
            function () { clearTimeout(corte); return {ok: false, mensaje: "No pudimos completar la acción. Revisa tu conexión e inténtalo de nuevo."}; });
  }
  /* Validación en el navegador: el servidor vuelve a validar. Devuelve el mensaje de error o "". */
  function validar(texto) {
    var t = texto.trim();
    if (t.length < MIN) return "Cuéntanos qué pasó, con al menos " + MIN + " caracteres.";
    if (t.length > MAX) return "El mensaje es demasiado largo: máximo " + MAX + " caracteres.";
    return "";
  }
  function termino(ordenId, d) {
    document.dispatchEvent(new CustomEvent("cofrial:entrega", {detail: {orden: ordenId, ok: d.ok}}));
    if (!d.ok) return;
    toast(d.mensaje, "info"); anunciar(d.mensaje);
    if (new RegExp("^/pedidos/" + ordenId + "/?$").test(location.pathname)) setTimeout(function () { location.reload(); }, 1100);   // la pantalla se vuelve a dibujar con el estado nuevo
  }

  function contadorDe(area, cuenta) {
    function pintar() { var n = area.value.length; cuenta.textContent = n + " / " + MAX; cuenta.classList.toggle("limite", n >= MAX - 40); }
    area.addEventListener("input", pintar); pintar();
  }
  function ligarFormularioNo(form, ordenId, alTerminar) {
    var area = form.querySelector("textarea"), err = form.querySelector(".entrega-error"), cuenta = form.querySelector(".entrega-cuenta-car"), boton = form.querySelector("button:not([type=button])");
    contadorDe(area, cuenta);
    area.addEventListener("input", function () { if (!err.hidden && !validar(area.value)) { err.hidden = true; area.removeAttribute("aria-invalid"); } });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var m = validar(area.value);
      if (m) { err.textContent = m; err.hidden = false; area.setAttribute("aria-invalid", "true"); area.focus(); return; }
      err.hidden = true; var fin = ocupar(boton, "Enviando…");
      enviar(ordenId, "no_recibido", area.value.trim()).then(function (d) {
        if (d.ok) { fin("Enviado", 3000); } else { fin(); err.textContent = d.mensaje; err.hidden = false; area.focus(); }
        if (alTerminar) alTerminar(d);
      });
    });
  }

  /* ---------- pantalla del pedido ---------- */
  function iniciar(raiz) {
    if (!raiz || !window.fetch) return;
    var ordenId = (raiz.dataset.url.match(/pedidos\/(\d+)/) || [])[1];
    var aceptar = raiz.querySelector('form[data-accion="aceptar"]'), no = raiz.querySelector('form[data-accion="no_recibido"]'), det = raiz.querySelector("details"),
        resta = document.getElementById("entrega-resta"), barra = document.getElementById("entrega-barra"), seccion = raiz.closest(".estado-pedido");
    var total = null, fin = null, anuncio = document.getElementById("entrega-anuncio");
    function ocupado(si) { if (seccion) seccion.classList.toggle("cargando", si); }
    aceptar.addEventListener("submit", function (e) {
      e.preventDefault(); var b = aceptar.querySelector("button"), listo = ocupar(b, "Confirmando…"); ocupado(true);
      enviar(ordenId, "aceptar").then(function (d) { ocupado(false); if (d.ok) listo("Confirmado", 3000); else { listo(); toast(d.mensaje, "error"); anunciar(d.mensaje); } termino(ordenId, d); });
    });
    ligarFormularioNo(no, ordenId, function (d) { ocupado(false); termino(ordenId, d); });
    det.addEventListener("toggle", function () { if (det.open) no.querySelector("textarea").focus(); });
    /* cuenta regresiva suave: no hay números que cambien cada segundo; la barra se vacía despacio y el texto se redondea */
    function texto(s) { return s <= 15 ? "en unos segundos" : s < 60 ? "en menos de un minuto" : "en unos " + Math.ceil(s / 60) + " minutos"; }
    function pintarResta(s) {
      if (total == null) total = Math.max(s, 1);
      resta.textContent = texto(s); if (barra) barra.style.width = Math.max(0, Math.min(100, s / total * 100)) + "%";
    }
    var restante = null, ultimo = Date.now();
    function consulta() {
      fetch(raiz.dataset.url, {credentials: "same-origin", headers: {"Accept": "application/json"}}).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
        if (!d) return;
        if (!d.puede_responder) { location.reload(); return; }          // se confirmó sola o se respondió desde otra pantalla
        restante = d.se_confirma_sola_en_seg; ultimo = Date.now(); if (restante != null) pintarResta(restante);
      }).catch(function () {});
    }
    consulta(); setInterval(consulta, 8000);
    setInterval(function () { if (restante != null) pintarResta(Math.max(0, restante - Math.round((Date.now() - ultimo) / 1000))); }, 5000);
    if (anuncio) anuncio.textContent = "El camión llegó con tu pedido. Confirma si lo recibiste.";
  }

  /* ---------- diálogo para la campanita ---------- */
  function modal(ordenId) {
    if (!window.HTMLDialogElement) { location.href = "/pedidos/" + ordenId + "/#entrega"; return; }
    var d = document.createElement("dialog"); d.className = "dialogo entrega-dialogo"; d.setAttribute("aria-labelledby", "ed-t");
    d.innerHTML = '<form method="dialog" novalidate><h2 id="ed-t">No pudiste recibir tu pedido N.º ' + ordenId + '</h2>' +
      '<label for="ed-motivo">Cuéntanos qué pasó</label><textarea id="ed-motivo" rows="4" maxlength="' + MAX + '" required aria-describedby="ed-ayuda ed-error"></textarea>' +
      '<div class="entrega-pie"><span id="ed-ayuda" class="frio">Mínimo ' + MIN + ' y máximo ' + MAX + ' caracteres. Ventas lo revisa y te contacta.</span><span class="entrega-cuenta-car" aria-hidden="true">0 / ' + MAX + '</span></div>' +
      '<p class="entrega-error" id="ed-error" role="alert" hidden></p>' +
      '<div class="acciones"><button class="btn btn-sec" value="enviar">Informar el problema</button><button type="button" class="btn-sec" data-cerrar>Cancelar</button></div></form>';
    document.body.appendChild(d);
    var form = d.querySelector("form"); form.querySelector("textarea").name = "motivo";
    ligarFormularioNo(form, ordenId, function (r) { if (r.ok) { d.close(); termino(ordenId, r); } else termino(ordenId, r); });
    d.querySelector("[data-cerrar]").addEventListener("click", function () { d.close(); });
    d.addEventListener("close", function () { d.remove(); if (modal.origen && document.contains(modal.origen)) modal.origen.focus(); });
    modal.origen = document.activeElement; d.showModal(); d.querySelector("textarea").focus();
  }
  function aceptarDirecto(ordenId, boton) {
    var fin = ocupar(boton, "Confirmando…");
    enviar(ordenId, "aceptar").then(function (d) { if (d.ok) fin("Confirmado", 2500); else { fin(); toast(d.mensaje, "error"); anunciar(d.mensaje); } termino(ordenId, d); });
  }
  /* Lo que cuenta la campanita: lo que espera una respuesta, las entregas sin concretar aún abiertas (el aviso desaparece al cerrarse) y lo nuevo de las últimas 2 horas.
     Los avisos viejos y lo ya entregado no suman, aunque sigan en la lista. */
  var RECIENTE_MS = 2 * 3600 * 1000;
  function pide(a) { return a.tipo === "puerta" && /^Estamos afuera/.test(a.texto); }
  function contarAvisos(avisos, vistos, ahora) {
    return avisos.filter(function (a) {
      if (pide(a) || a.tipo === "no_concretada") return true;
      return vistos.indexOf(a.id) < 0 && ahora - new Date(a.cuando).getTime() <= RECIENTE_MS;
    }).length;
  }
  window.CofrialEntrega = {iniciar: iniciar, modal: modal, aceptar: aceptarDirecto, validar: validar, pide: pide, contarAvisos: contarAvisos};
})();
