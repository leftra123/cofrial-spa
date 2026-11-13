/* Aviso informativo de cookies. El sitio solo usa cookies necesarias (sesión, CSRF, balanceo), así que no hay nada que
   aceptar ni bloquear: se muestra una vez y se guarda en este navegador que ya se vio. Se puede cerrar de cuatro formas, todas
   sin mouse: «Entendido» (Tab y Enter), la tecla Escape, o simplemente seguir con lo que se estaba haciendo: enviar el formulario
   de ingreso o de registro lo da por visto. Si el almacenamiento está bloqueado, el aviso aparece en cada página pero se puede cerrar igual. */
(function () {
  var CLAVE = "cofrial-aviso-cookies";
  var caja = document.getElementById("aviso-cookies"), ok = document.getElementById("aviso-cookies-ok");
  if (!caja || !ok) return;
  var visto = false;
  try { visto = localStorage.getItem(CLAVE) === "1"; } catch (e) {}
  if (visto) return;
  caja.hidden = false;
  function cerrar() {
    try { localStorage.setItem(CLAVE, "1"); } catch (e) {}
    caja.hidden = true;
  }
  ok.addEventListener("click", cerrar);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !caja.hidden) cerrar(); });
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (f && f.hasAttribute && (f.hasAttribute("data-enter-avanza") || f.hasAttribute("data-carga"))) cerrar();
  }, true);
})();
