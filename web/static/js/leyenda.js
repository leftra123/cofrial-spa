/* Cofrial SpA · leyendas de los mapas con los mismos íconos que se dibujan en el mapa (CofrialMapa.camion/destino/base). */
window.CofrialLeyenda = function (id, items) {
  var ul = document.getElementById(id); if (!ul || !window.CofrialMapa || !window.L) return;
  var sinEtiqueta = function (html) { return html.replace(/<b class="pin-etq">.*?<\/b>/, ""); };
  var defs = {
    camion: [sinEtiqueta(CofrialMapa.camion(false, "").options.html), "Camión"],
    alerta: [sinEtiqueta(CofrialMapa.camion(true, "").options.html), "Camión con ruptura de frío"],
    destino: [CofrialMapa.destino().options.html, "Dirección de entrega"],
    base: [CofrialMapa.base().options.html, "Frigorífico central"],
    ruta: ['<svg viewBox="0 0 38 8" width="38" height="8" aria-hidden="true"><path d="M2 4h34" stroke="#143A7B" stroke-width="4" stroke-linecap="round"/></svg>', "Ruta"]
  };
  ul.innerHTML = items.map(function (k) { return '<li><span class="ley-ico" aria-hidden="true">' + defs[k][0] + "</span>" + defs[k][1] + "</li>"; }).join("");
};
