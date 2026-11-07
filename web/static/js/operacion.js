// Crear cuenta: muestra solo los campos que el rol elegido necesita. Sin JavaScript se ven todos y el servidor valida igual.
(function () {
  var rol = document.getElementById("id_rol");
  if (!rol) return;
  function actualizar() {
    document.querySelectorAll("#form-cuenta [data-roles]").forEach(function (bloque) {
      bloque.hidden = bloque.getAttribute("data-roles").split(" ").indexOf(rol.value) === -1;
    });
  }
  rol.addEventListener("change", actualizar);
  actualizar();
})();
