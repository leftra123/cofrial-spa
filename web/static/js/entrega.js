/* Cofrial SpA · «Estamos afuera»: el cliente confirma la entrega o cuenta por qué no pudo recibirla.
   Mejora progresiva: sin este script los formularios de la pantalla del pedido envían igual (POST /pedidos/<id>/entrega/).
   - iniciar(raiz): pantalla del pedido (revisión al recibir, contador de caracteres, validación, envío sin recarga, cuenta regresiva suave).
   - modal(ordenId): «No pude recibirlo» en un diálogo, para la campanita y el aviso destacado en cualquier página.
   - revisar(ordenId): el paso de revisión al recibir (productos, temperatura del viaje y si todo llegó bien) en un diálogo, para la campanita y el aviso.
   - aceptar(ordenId): «Recibí mi pedido» directo, sin revisión (queda por si algún flujo antiguo lo usa). */
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
  function enviar(ordenId, accion, extra) {          // extra: el motivo (texto) o un objeto con más campos (resultado, tipo_problema, problema…)
    var cuerpo = new FormData(); cuerpo.append("accion", accion);
    if (typeof extra === "string") cuerpo.append("motivo", extra);
    else if (extra) Object.keys(extra).forEach(function (k) { cuerpo.append(k, extra[k]); });
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

  /* Paso de revisión al recibir: el cliente ve productos y temperatura, dice si todo llegó bien o qué falló y recién entonces confirma.
     Con «algo falló» el pedido queda entregado y el aviso llega a ventas como reclamo (lo crea el servidor). Misma lógica para la página y el diálogo. */
  function ligarRevision(form, ordenId, alEmpezar, alTerminar) {
    var radios = form.querySelectorAll("input[name=resultado]"), falla = form.querySelector(".revision-falla"), area = form.querySelector("textarea"),
        tipo = form.querySelector("select"), err = form.querySelector(".entrega-error"), boton = form.querySelector("button:not([type=button])");
    function eligio() { var r = form.querySelector("input[name=resultado]:checked"); return r ? r.value : ""; }
    function mostrar() { var f = eligio() === "falla"; falla.hidden = !f; if (f) area.focus(); }
    function error(m, campo) { err.textContent = m; err.hidden = false; if (campo) { campo.setAttribute("aria-invalid", "true"); campo.focus(); } }
    function limpiar() { err.hidden = true; area.removeAttribute("aria-invalid"); }
    for (var i = 0; i < radios.length; i++) radios[i].addEventListener("change", function () { limpiar(); mostrar(); });
    area.addEventListener("input", function () { if (!err.hidden && !validar(area.value)) limpiar(); });
    falla.hidden = eligio() !== "falla";                  // sin JavaScript el bloque queda a la vista y el servidor decide; con JavaScript aparece solo si algo falló
    form.addEventListener("submit", function (e) {
      e.preventDefault(); var r = eligio();
      if (!r) { error("Elige si todo llegó bien o si algo falló.", radios[0]); return; }
      var datos = {resultado: r};
      if (r === "falla") {
        var m = validar(area.value); if (m) { error(m.replace("qué pasó", "qué falló"), area); return; }
        datos.tipo_problema = tipo.value; datos.problema = area.value.trim();
      }
      limpiar(); if (alEmpezar) alEmpezar(); var fin = ocupar(boton, "Confirmando…");
      enviar(ordenId, "aceptar", datos).then(function (d) {
        if (d.ok) fin("Confirmado", 3000); else { fin(); error(d.mensaje); }
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
    ligarRevision(aceptar, ordenId, function () { ocupado(true); }, function (d) { ocupado(false); if (!d.ok) anunciar(d.mensaje); termino(ordenId, d); });
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
  /* Diálogo con el paso de revisión (campanita y aviso destacado). Los datos vienen del servidor; todo se escribe con textContent. */
  function revisar(ordenId) {
    var url = "/pedidos/" + ordenId + "/entrega/?revision=1";
    if (!window.HTMLDialogElement || !window.fetch) { location.href = "/pedidos/" + ordenId + "/#entrega"; return; }
    function el(tag, props, texto) { var n = document.createElement(tag); Object.keys(props || {}).forEach(function (k) { n.setAttribute(k, props[k]); }); if (texto != null) n.textContent = texto; return n; }
    fetch(url, {credentials: "same-origin", headers: {"Accept": "application/json"}}).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d || !d.puede_responder || !d.revision) { document.dispatchEvent(new CustomEvent("cofrial:entrega", {detail: {orden: ordenId, ok: false}})); location.href = "/pedidos/" + ordenId + "/"; return; }
      var rev = d.revision, dlg = el("dialog", {"class": "dialogo entrega-dialogo", "aria-labelledby": "rv-t"}), form = el("form", {novalidate: ""});
      form.appendChild(el("h2", {id: "rv-t"}, "Revisa tu pedido N.º " + ordenId));
      var ul = el("ul", {"class": "revision-productos", "aria-label": "Productos de tu pedido"});
      rev.productos.forEach(function (p) { var li = el("li"); li.appendChild(el("b", {}, String(p.cantidad))); li.appendChild(document.createTextNode(" × " + p.producto)); ul.appendChild(li); });
      form.appendChild(ul);
      if (rev.temperatura) {
        var t = rev.temperatura, f1 = function (v) { return v.toFixed(1).replace(".", ","); }, fb = function (v) { return String(v).replace(".", ","); };
        var pt = el("p", {"class": "revision-temp" + (t.en_rango ? "" : " fuera")});
        pt.appendChild(el("b", {}, "Temperatura del viaje: "));
        pt.appendChild(document.createTextNode(f1(t.ultima) + " °C ahora (entre " + f1(t.minima) + " y " + f1(t.maxima) + " °C en la última hora; lo permitido es " + fb(t.banda.min) + " a " + fb(t.banda.max) + " °C). "));
        pt.appendChild(el("span", {"class": "chip " + (t.en_rango ? "entregado" : "alerta")}, t.en_rango ? "Dentro de rango" : "Fuera de rango"));
        form.appendChild(pt);
      }
      var fs = el("fieldset", {"class": "revision-resultado"}); fs.appendChild(el("legend", {}, "¿Llegó todo bien?"));
      [["bien", "Sí, todo llegó bien"], ["falla", "No, algo falló"]].forEach(function (o) {
        var lb = el("label"), rd = el("input", {type: "radio", name: "resultado", value: o[0]}); lb.appendChild(rd); lb.appendChild(document.createTextNode(" " + o[1])); fs.appendChild(lb);
      });
      form.appendChild(fs);
      var fl = el("div", {"class": "revision-falla"});
      fl.appendChild(el("label", {"for": "rv-tipo"}, "¿Qué falló?"));
      var sel = el("select", {id: "rv-tipo", name: "tipo_problema"}); rev.problemas.forEach(function (k) { sel.appendChild(el("option", {value: k.codigo}, k.etiqueta)); }); fl.appendChild(sel);
      fl.appendChild(el("label", {"for": "rv-problema"}, "Cuéntanos qué pasó (obligatorio si algo falló)"));
      fl.appendChild(el("textarea", {id: "rv-problema", name: "problema", rows: "3", maxlength: String(MAX), "aria-describedby": "rv-error"}));
      fl.appendChild(el("p", {"class": "frio"}, "Ventas recibe tu aviso como reclamo y te contacta. El pedido igual queda como entregado."));
      form.appendChild(fl);
      form.appendChild(el("p", {"class": "entrega-error", id: "rv-error", role: "alert", hidden: ""}));
      var ac = el("div", {"class": "acciones"}); ac.appendChild(el("button", {"class": "btn"}, "Recibí mi pedido"));
      var cerrar = el("button", {type: "button", "class": "btn-sec"}, "Cancelar"); cerrar.addEventListener("click", function () { dlg.close(); }); ac.appendChild(cerrar);
      form.appendChild(ac); dlg.appendChild(form); document.body.appendChild(dlg);
      ligarRevision(form, ordenId, null, function (r) { if (r.ok) { dlg.close(); termino(ordenId, r); } else termino(ordenId, r); });
      dlg.addEventListener("close", function () { dlg.remove(); if (revisar.origen && document.contains(revisar.origen)) revisar.origen.focus(); });
      revisar.origen = document.activeElement; dlg.showModal(); fs.querySelector("input").focus();
    }).catch(function () { location.href = "/pedidos/" + ordenId + "/#entrega"; });
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
  window.CofrialEntrega = {iniciar: iniciar, modal: modal, revisar: revisar, aceptar: aceptarDirecto, validar: validar, pide: pide, contarAvisos: contarAvisos};
})();
