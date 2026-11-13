/* Cofrial SpA · paginación de tablas. Un solo script para toda la web: cualquier tabla dentro de .tabla-caja con más de 10 filas
   se muestra de a 10 y trae debajo «Viendo 1–10 de 47», «Anterior» y «Siguiente».
   - No hay que editar cada plantilla. Para dejar una tabla entera a la vista: data-sin-paginar en su <table>.
   - Convive con los filtros (filtros.js oculta filas con [hidden]): se cuentan y se reparten solo las filas que el filtro deja visibles.
   - Si las filas cambian solas (una tabla que se vuelve a dibujar), se recalcula la página sin volver al inicio. */
(function () {
  "use strict";
  var POR_PAGINA = 10, OPCIONES = [10, 25, 50];

  function filasDe(tabla) {
    var cuerpo = tabla.tBodies[0];
    return cuerpo ? Array.prototype.filter.call(cuerpo.rows, function (f) { return !f.hidden && !f.querySelector("td[colspan]"); }) : [];
  }

  function armar(tabla) {
    var caja = tabla.closest(".tabla-caja");
    if (!caja || tabla.hasAttribute("data-sin-paginar") || tabla.tBodies.length !== 1) return;
    if (filasDe(tabla).length <= POR_PAGINA) return;
    var pagina = 0, tamano = POR_PAGINA, trabajando = false;

    var nav = document.createElement("nav");
    nav.className = "paginacion"; nav.setAttribute("aria-label", "Paginación de la tabla");
    nav.innerHTML =
      '<p class="paginacion-texto" role="status" aria-live="polite"></p>' +
      '<div class="paginacion-ctl">' +
      '<label class="paginacion-tam">Filas <select aria-label="Filas por página"></select></label>' +
      '<button type="button" class="btn btn-sec" data-pag="ant">Anterior</button>' +
      '<span class="paginacion-nro"></span>' +
      '<button type="button" class="btn btn-sec" data-pag="sig">Siguiente</button>' +
      '</div>';
    caja.insertAdjacentElement("afterend", nav);
    var texto = nav.querySelector(".paginacion-texto"), nro = nav.querySelector(".paginacion-nro"),
        ant = nav.querySelector('[data-pag="ant"]'), sig = nav.querySelector('[data-pag="sig"]'), sel = nav.querySelector("select");
    OPCIONES.forEach(function (n) { var o = document.createElement("option"); o.value = n; o.textContent = n; sel.appendChild(o); });

    function pintar() {
      trabajando = true;
      var filas = filasDe(tabla), total = filas.length, paginas = Math.max(1, Math.ceil(total / tamano));
      if (pagina > paginas - 1) pagina = paginas - 1;
      var desde = pagina * tamano, hasta = Math.min(total, desde + tamano);
      Array.prototype.forEach.call(tabla.tBodies[0].rows, function (f) { f.removeAttribute("data-pag-oculta"); });
      filas.forEach(function (f, i) { if (i < desde || i >= hasta) f.setAttribute("data-pag-oculta", ""); });
      nav.hidden = total <= Math.min.apply(null, OPCIONES);
      texto.textContent = total ? "Viendo " + (desde + 1) + "–" + hasta + " de " + total : "Sin filas";
      nro.textContent = "Página " + (pagina + 1) + " de " + paginas;
      ant.disabled = pagina === 0; sig.disabled = pagina >= paginas - 1;
      window.setTimeout(function () { trabajando = false; }, 0);
    }
    function ir(p, enfocar) { pagina = p; pintar(); if (enfocar) caja.scrollIntoView({block: "nearest"}); }
    ant.addEventListener("click", function () { ir(pagina - 1, true); });
    sig.addEventListener("click", function () { ir(pagina + 1, true); });
    sel.addEventListener("change", function () { tamano = Number(sel.value) || POR_PAGINA; ir(0, false); });

    var pendiente = null;
    function cambio() { if (trabajando || pendiente) return; pendiente = window.setTimeout(function () { pendiente = null; pintar(); }, 30); }
    var cuerpo = tabla.tBodies[0];
    if (window.MutationObserver) {
      new MutationObserver(function (cambios) {
        for (var i = 0; i < cambios.length; i++) { if (cambios[i].type === "childList" || cambios[i].attributeName === "hidden") { cambio(); return; } }
      }).observe(cuerpo, {childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"]});
    }
    pintar();
  }

  function iniciar() { Array.prototype.forEach.call(document.querySelectorAll(".tabla-caja table"), armar); }
  /* filtros.js arma sus barras al cargar: se espera un instante para contar ya con el filtro recordado */
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { window.setTimeout(iniciar, 0); });
  else window.setTimeout(iniciar, 0);
})();
