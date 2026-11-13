/* Aviso informativo de cookies. El sitio solo usa cookies necesarias (sesión, CSRF, balanceo), así que no hay nada que
   aceptar ni bloquear: se muestra una vez y «Entendido» lo guarda en este navegador. Si el almacenamiento está bloqueado,
   el aviso aparece en cada página pero se puede cerrar igual. */
(function () {
  var CLAVE = "cofrial-aviso-cookies";
  var caja = document.getElementById("aviso-cookies"), ok = document.getElementById("aviso-cookies-ok");
  if (!caja || !ok) return;
  var visto = false;
  try { visto = localStorage.getItem(CLAVE) === "1"; } catch (e) {}
  if (visto) return;
  caja.hidden = false;
  ok.addEventListener("click", function () {
    try { localStorage.setItem(CLAVE, "1"); } catch (e) {}
    caja.hidden = true;
  });
})();
