/* Página de estado (/salud/): dice hace cuánto son los datos y permite pedirlos de nuevo sin esperar el refresco automático de cada minuto.
   Mejora progresiva: sin este script la página muestra la hora de los datos y «Actualizar» es un enlace a la misma dirección. */
(function () {
  var edad = document.getElementById("s-edad"), boton = document.getElementById("s-actualizar");
  if (edad && edad.dataset.momento) {
    var momento = new Date(edad.dataset.momento).getTime(), hora = edad.textContent;
    var pintar = function () {
      var s = Math.max(0, Math.round((Date.now() - momento) / 1000));
      if (isNaN(s)) return;
      edad.textContent = (s < 5 ? "Actualizado recién" : s < 90 ? "Actualizado hace " + s + " s" : "Actualizado hace " + Math.round(s / 60) + " min") + " · " + hora.toLowerCase();
    };
    pintar(); setInterval(pintar, 1000);
  }
  if (boton) boton.addEventListener("click", function (e) {      // recarga en el mismo lugar, sin sumar una entrada al historial del navegador
    e.preventDefault(); boton.textContent = "Actualizando…"; boton.setAttribute("aria-busy", "true"); location.reload();
  });
})();
