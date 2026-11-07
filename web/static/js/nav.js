/* Cofrial SpA · navegación que se mantiene. Complementa el menú de cada plantilla base sin cambiar su HTML:
   1. Menú del panel en móvil (#lateral): se cierra con Esc, tocando fuera, al elegir un enlace o al volver a pantalla ancha,
      y la página de atrás no se desplaza mientras está abierto.
   2. Submenú del CRM (.subnav): en móvil se desliza de lado; muestra una sombra en el borde con más opciones y deja visible la sección actual.
   3. Barra de la tienda (.tb) en móvil: la fila del buscador se pliega al bajar y vuelve al subir; logo, menú y carrito siguen a la vista.
   Sin JavaScript todo sigue funcionando: las barras quedan pegadas arriba (sticky) con el buscador a la vista. */
(function () {
  "use strict";
  var raiz = document.documentElement;

  /* ---------- 1. menú lateral en móvil ---------- */
  var lateral = document.getElementById("lateral"), boton = document.getElementById("menu-btn");
  if (lateral && boton) {
    function abierto() { return lateral.classList.contains("abierto"); }
    function cerrar(devolverFoco) {
      if (!abierto()) return;
      lateral.classList.remove("abierto"); boton.setAttribute("aria-expanded", "false");
      if (devolverFoco) boton.focus();
    }
    function sincronizar() { raiz.classList.toggle("menu-abierto", abierto()); }
    new MutationObserver(sincronizar).observe(lateral, {attributes: true, attributeFilter: ["class"]});
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") cerrar(true); });
    document.addEventListener("click", function (e) {
      if (!abierto()) return;
      if (e.target.closest("#menu-btn")) return;
      if (e.target.closest("#lateral a, #lateral button[type=submit]") || !e.target.closest("#lateral")) cerrar(false);
    });
    matchMedia("(min-width: 861px)").addEventListener("change", function (m) { if (m.matches) cerrar(false); });
    sincronizar();
  }

  /* ---------- 2. submenú del CRM ---------- */
  var sub = document.querySelector(".subnav");
  if (sub) {
    function bordes() {
      var max = sub.scrollWidth - sub.clientWidth;
      sub.classList.toggle("mas-izq", sub.scrollLeft > 4);
      sub.classList.toggle("mas-der", max > 4 && sub.scrollLeft < max - 4);
    }
    var activo = sub.querySelector("a.activo");
    if (activo && sub.scrollWidth > sub.clientWidth) sub.scrollLeft = Math.max(0, activo.offsetLeft - (sub.clientWidth - activo.offsetWidth) / 2);
    sub.addEventListener("scroll", bordes, {passive: true}); window.addEventListener("resize", bordes); bordes();
  }

  /* ---------- 3. barra de la tienda en móvil ---------- */
  var barra = document.querySelector(".tb"), buscador = barra && barra.querySelector(".tb-buscar"), marca = barra && barra.querySelector(".tb-marca");
  if (barra && buscador && marca) {
    var y0 = window.pageYOffset, plegada = false, esperando = false, subido = 0, quieto = 0;       // subido: lo que se lleva subiendo seguido
    function enOtraFila() { return !plegada && buscador.offsetTop - marca.offsetTop > 20; }     // solo si el buscador ocupa su propia fila
    function actualizar() {
      esperando = false;
      var y = window.pageYOffset, d = y - y0; y0 = y;
      if (Date.now() < quieto) { subido = 0; return; }                                   // el propio cambio de alto mueve el desplazamiento (anclaje del navegador): no cuenta como gesto
      subido = d < 0 ? subido - d : 0;                                                  // un gesto lento suma varios pasos chicos
      if (!plegada && d > 0 && y > 160 && enOtraFila()) { plegada = true; subido = 0; quieto = Date.now() + 300; barra.classList.add("tb-compacta"); }
      else if (plegada && (subido > 24 || y < 60)) { plegada = false; quieto = Date.now() + 300; barra.classList.remove("tb-compacta"); }
    }
    window.addEventListener("scroll", function () { if (!esperando) { esperando = true; requestAnimationFrame(actualizar); } }, {passive: true});
    barra.addEventListener("focusin", function () { if (plegada) { plegada = false; barra.classList.remove("tb-compacta"); } });
    if (window.ResizeObserver) new ResizeObserver(function () { raiz.style.setProperty("--tb-alto", barra.offsetHeight + "px"); }).observe(barra);   // los filtros del catálogo se pegan justo debajo
  }
})();
