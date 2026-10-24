/* Cofrial SpA · microinteracciones de la tienda (sin dependencias). Si falla, los formularios siguen funcionando. */
(function () {
  function iniciarCant(raiz) {
  (raiz || document).querySelectorAll(".cant").forEach(function (c) {
    if (c.dataset.listo) return; c.dataset.listo = "1";
    var i = c.querySelector("input"), menos = c.querySelector("[data-menos]"), mas = c.querySelector("[data-mas]");
    if (!i || !menos || !mas) return;
    var max = parseInt(i.max, 10) || 9999, min = parseInt(i.min, 10);
    if (isNaN(min)) min = 1;
    function poner(v) { i.value = Math.max(min, Math.min(max, v)); menos.disabled = +i.value <= min; mas.disabled = +i.value >= max; }
    menos.addEventListener("click", function () { poner((parseInt(i.value, 10) || min) - 1); });
    mas.addEventListener("click", function () { poner((parseInt(i.value, 10) || min) + 1); });
    i.addEventListener("change", function () { poner(parseInt(i.value, 10) || min); });
    poner(parseInt(i.value, 10) || min);
  });
  }
  iniciarCant(document);
  window.CofrialTienda = {iniciarCant: iniciarCant};
  /* al enviar un formulario con botón principal: estado de carga y sin doble clic */
  document.querySelectorAll("form[data-carga]").forEach(function (f) {
    f.addEventListener("submit", function () {
      var b = f.querySelector("button:not([type=button])");
      if (!b || b.disabled) return;
      b.setAttribute("aria-busy", "true");
      b.innerHTML = '<span class="spinner" aria-hidden="true"></span> ' + (b.dataset.cargando || "Procesando…");
      setTimeout(function () { b.disabled = true; }, 0);
    });
  });
})();
