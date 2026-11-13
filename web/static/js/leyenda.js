/* Cofrial SpA · leyendas de los mapas con los mismos íconos que se dibujan en el mapa (CofrialMapa.camion/destino/base). */
window.CofrialLeyenda = (function () {
  /* Muestra de un tramo: mismo color, mismo trazo y misma flecha que en el mapa, sobre el azul noche para que se lea igual con tema claro u oscuro. */
  function muestra(color, trazos) {
    return '<svg viewBox="0 0 44 14" width="44" height="14" aria-hidden="true"><rect width="44" height="14" rx="7" fill="#0B1A33"/><path d="M5 7h26" stroke="' + color + '" stroke-width="3"' + (trazos ? ' stroke-dasharray="6 4"' : ' stroke-linecap="round"') + '/><path d="M31 2.5 39 7l-8 4.5z" fill="' + color + '"/></svg>';
  }
  function circulo(color, letra) {
    return '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="' + color + '" stroke="#fff" stroke-width="2"/><text x="12" y="16.5" text-anchor="middle" font-size="12" font-weight="700" fill="#0B1A33">' + letra + "</text></svg>";
  }
  function leyenda(id, items) {
    var ul = document.getElementById(id); if (!ul || !window.CofrialMapa) return;
    var sinEtiqueta = function (html) { return html.replace(/<b class="pin-etq">.*?<\/b>/, ""); }, M = CofrialMapa;
    var defs = {
      camion: [sinEtiqueta(M.camion(false, "").html), "Camión"],
      alerta: [sinEtiqueta(M.camion(true, "").html), "Camión con ruptura de frío"],
      destino: [M.destino().html, "Dirección de entrega"],
      base: [M.base().html, "Frigorífico central"],
      salida: [circulo(M.COLOR_IDA, "S"), "Salida"],
      parada: [circulo(M.COLOR_IDA, "1"), "Parada, en orden"],
      ultima: ['<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="' + M.COLOR_IDA + '" stroke="' + M.COLOR_VUELTA + '" stroke-width="3"/></svg>', "Última parada: desde aquí vuelve"],
      regreso: [circulo(M.COLOR_VUELTA, "R"), "Regreso"],
      ruta: [muestra(M.COLOR_IDA, false), "Camino a tu dirección"]
    };
    Object.keys(M.ESTADOS).forEach(function (e) { defs["estado_" + e] = [M.estadoSVG(e), M.ESTADOS[e].texto]; });     // los puntos por estado de la flota
    ul.innerHTML = items.map(function (k) { return '<li><span class="ley-ico" aria-hidden="true">' + defs[k][0] + "</span>" + defs[k][1] + "</li>"; }).join("");
  }
  /* Botones que son a la vez leyenda y filtro de cada tramo, y selector de camión si hay más de un viaje. op: {camiones: [{id, texto}], alElegir: fn(id)}.
     Devuelve {elegir(id)} para que tocar un camión en el mapa actualice el selector. */
  leyenda.filtros = function (id, rec, op) {
    var caja = document.getElementById(id), M = window.CofrialMapa; op = op || {};
    if (!caja || !M) return {elegir: function () {}};
    [["ida", "Ida", M.COLOR_IDA, false], ["vuelta", "Vuelta", M.COLOR_VUELTA, true]].forEach(function (t) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "chip-tramo"; b.setAttribute("aria-pressed", "true");
      b.title = "Mostrar u ocultar la " + t[1].toLowerCase();
      b.innerHTML = muestra(t[2], t[3]) + "<span>" + t[1] + "</span>";
      b.addEventListener("click", function () {
        var activo = b.getAttribute("aria-pressed") !== "true";
        b.setAttribute("aria-pressed", activo ? "true" : "false");
        rec.ver(t[0], activo);
      });
      caja.appendChild(b);
    });
    var sel = null;
    if (op.camiones && op.camiones.length > 1) {
      var etiqueta = document.createElement("label"), texto = document.createElement("span");
      etiqueta.className = "filtro-camion"; texto.textContent = "Camión";
      sel = document.createElement("select");
      sel.appendChild(new Option("Todos", ""));
      op.camiones.forEach(function (c) { sel.appendChild(new Option(c.texto, c.id)); });
      sel.addEventListener("change", function () { if (op.alElegir) op.alElegir(sel.value || null); });
      etiqueta.appendChild(texto); etiqueta.appendChild(sel);
      caja.appendChild(etiqueta);
    }
    return {elegir: function (valor) { if (sel) sel.value = valor || ""; }};
  };
  return leyenda;
})();
