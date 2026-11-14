/* Cofrial SpA · emulador del pago con tarjeta de Mercado Pago (solo cuando no hay credenciales reales).
   Abre un diálogo con una tarjeta de prueba y deja elegir cómo responde el pago (aprobado o rechazado). Envía el mismo carrito que el Brick real a
   /carrito/mp/emulador/; el servidor decide y solo un pago aprobado crea el pedido. Todo texto del servidor entra con textContent. */
(function () {
  "use strict";
  var dlg = document.getElementById("mp-emu");
  if (!dlg || !window.fetch) return;
  var abrir = document.getElementById("mp-emu-abrir"), barra = document.getElementById("mp-emu-barra"), pagar = document.getElementById("mp-emu-pagar"),
      cancelar = document.getElementById("mp-emu-cancelar"), error = document.getElementById("mp-emu-error"), titular = document.getElementById("mp-emu-titular");
  function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function valor(id) { var e = document.getElementById(id); return e ? e.value : ""; }
  function comprobante() {
    var c = document.querySelector('.checkout-mp input[name="comprobante"]:checked') || document.querySelector('.checkout-mp input[type="hidden"][name="comprobante"]');
    return c ? c.value : "boleta";
  }
  function falla(texto) { error.textContent = texto; error.hidden = false; }
  function abrirDialogo() {
    var dir = document.getElementById("direccion");
    if (!dir || !dir.value) { if (dir) { dir.focus(); dir.scrollIntoView({block: "center"}); } return; }          // falta la dirección: el carrito ya la pide
    error.hidden = true; pagar.disabled = false; pagar.dataset.texto = pagar.dataset.texto || pagar.textContent;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    titular.focus();
  }
  [abrir, barra].forEach(function (b) { if (b) b.addEventListener("click", abrirDialogo); });
  cancelar.addEventListener("click", function () { dlg.close ? dlg.close() : dlg.removeAttribute("open"); });
  pagar.addEventListener("click", function () {
    error.hidden = true; pagar.disabled = true; pagar.textContent = "Procesando…";
    var recibeNuevo = (valor("recibe_nuevo") || "").trim(), cuerpo = {
      direccion: valor("direccion"), recibe: recibeNuevo || valor("recibe"), comprobante: comprobante(),
      giro: (document.querySelector('.checkout-mp input[name="giro"]') || {}).value || "", titular: titular.value};
    fetch(dlg.dataset.url, {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf()}, body: JSON.stringify(cuerpo)})
      .then(function (r) { return r.json().catch(function () { return {ok: false, mensaje: "No pudimos procesar el pago. Inténtalo de nuevo."}; }); })
      .then(function (d) {
        if (d.ok && d.redirect) { pagar.textContent = "Pago aprobado"; location.href = d.redirect; return; }
        falla(d.mensaje || "El pago no fue aprobado."); pagar.disabled = false; pagar.textContent = pagar.dataset.texto;
      })
      .catch(function () { falla("No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo."); pagar.disabled = false; pagar.textContent = pagar.dataset.texto; });
  });
})();
