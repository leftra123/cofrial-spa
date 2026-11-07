/* Cofrial SpA · leyendas de los mapas con los mismos íconos que se dibujan en el mapa (CofrialMapa.camion/destino/base). */
window.CofrialLeyenda = function (id, items) {
  var ul = document.getElementById(id); if (!ul || !window.CofrialMapa) return;
  var sinEtiqueta = function (html) { return html.replace(/<b class="pin-etq">.*?<\/b>/, ""); };
  var defs = {
    camion: [sinEtiqueta(CofrialMapa.camion(false, "").html), "Camión"],
    alerta: [sinEtiqueta(CofrialMapa.camion(true, "").html), "Camión con ruptura de frío"],
    destino: [CofrialMapa.destino().html, "Dirección de entrega"],
    base: [CofrialMapa.base().html, "Frigorífico central"],
    ruta: ['<svg viewBox="0 0 38 12" width="38" height="12" aria-hidden="true"><rect width="38" height="12" rx="6" fill="#0B1A33"/><path d="M6 6h26" stroke="' + CofrialMapa.COLOR_RUTA + '" stroke-width="3.5" stroke-linecap="round"/></svg>', "Ruta"]
  };
  ul.innerHTML = items.map(function (k) { return '<li><span class="ley-ico" aria-hidden="true">' + defs[k][0] + "</span>" + defs[k][1] + "</li>"; }).join("");
};
