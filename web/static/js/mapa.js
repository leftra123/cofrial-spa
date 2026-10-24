/* Mapa minimalista con OpenStreetMap (teselas estándar, atenuadas con CSS para que resalten las rutas) y rutas con OSRM. Ninguno pide cuenta ni clave.
   Si OSRM no responde, el mapa sigue mostrando los puntos y se dibuja una línea recta entre ellos. */
window.CofrialMapa = (function () {
  var OSRM = "https://router.project-osrm.org";

  function crear(id, centro, zoom) {
    var m = L.map(id, {zoomControl: true, attributionControl: true}).setView(centro, zoom || 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>"}).addTo(m);
    return m;
  }

  /* Pin redondo con texto (número de parada, "C" de camión, "B" de base). */
  function pin(texto, color) {
    return L.divIcon({className: "pin-mapa", iconSize: [28, 28], iconAnchor: [14, 14],
      html: '<span style="background:' + color + '">' + texto + "</span>"});
  }

  /* Camión frigorífico (vista lateral, mirando a la derecha): caja blanca con copo, franja y cabina del color pedido.
     Con alerta (ruptura de frío) pasa a rojo y late. `etiqueta` es el código que se muestra bajo el camión. */
  function camion(alerta, etiqueta) {
    var c = alerta ? "#DC2626" : "#143A7B";
    var svg = '<svg viewBox="0 0 60 38" width="76" height="48" aria-hidden="true">' +
      '<ellipse cx="30" cy="35.5" rx="25" ry="2.4" fill="#0F172A" opacity=".2"/>' +
      '<rect x="2" y="5" width="37" height="23" rx="3" fill="#fff" stroke="#CBD5E1"/>' +
      '<path d="M2 23h37v2a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3z" fill="' + c + '"/>' +
      '<g stroke="' + c + '" stroke-width="1.7" stroke-linecap="round"><path d="M20.5 8v12M15.3 11l10.4 6M15.3 17l10.4-6"/></g>' +
      '<path d="M41 11.5h8.2c1.3 0 2.5.7 3.2 1.7l4.2 6.2c.6.9.9 1.9.9 3V28a2 2 0 0 1-2 2H41z" fill="' + c + '"/>' +
      '<path d="M44 14.6h4.9c.7 0 1.3.3 1.7.9l2.5 3.8H44z" fill="#DBEAFE"/>' +
      '<rect x="55.4" y="22.5" width="2.6" height="3" rx="1" fill="#FDE68A"/>' +
      '<g fill="#0F172A"><circle cx="12" cy="30" r="4.3"/><circle cx="23" cy="30" r="4.3"/><circle cx="48" cy="30" r="4.3"/></g>' +
      '<g fill="#CBD5E1"><circle cx="12" cy="30" r="1.8"/><circle cx="23" cy="30" r="1.8"/><circle cx="48" cy="30" r="1.8"/></g></svg>';
    return L.divIcon({className: "pin-camion" + (alerta ? " alerta" : ""), iconSize: [76, 64], iconAnchor: [38, 42], popupAnchor: [0, -38],
      html: svg + (etiqueta ? '<b class="pin-etq">' + etiqueta + "</b>" : "")});
  }

  /* Destino de entrega: gota verde con una casa. */
  function destino() {
    return L.divIcon({className: "pin-destino", iconSize: [30, 40], iconAnchor: [15, 38], popupAnchor: [0, -34],
      html: '<svg viewBox="0 0 30 40" width="30" height="40" aria-hidden="true"><path d="M15 38C15 38 3 23 3 14a12 12 0 0 1 24 0c0 9-12 24-12 24z" fill="#16A34A" stroke="#fff" stroke-width="2"/>' +
        '<path d="M9 15l6-5.5 6 5.5v6.5h-4.2v-4.3h-3.6v4.3H9z" fill="#fff"/></svg>'});
  }

  /* Frigorífico central (punto de salida): cuadrado oscuro con una bodega. */
  function base() {
    return L.divIcon({className: "pin-base", iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -18],
      html: '<svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true"><rect x="1.5" y="1.5" width="31" height="31" rx="8" fill="#0F172A" stroke="#fff" stroke-width="2"/>' +
        '<path d="M7 14l10-5.5L27 14v11H7z" fill="#fff"/><rect x="12" y="18" width="10" height="7" rx="1" fill="#0F172A"/><path d="M12 21.5h10" stroke="#fff" stroke-width="1"/></svg>'});
  }

  function coords(puntos) { return puntos.map(function (p) { return p[1] + "," + p[0]; }).join(";"); }   // OSRM usa lon,lat

  /* puntos: [[lat, lon], ...]. Con optimizar, la primera es el origen fijo y el resto se reordena (viajante). */
  function ruta(puntos, optimizar) {
    var url = optimizar
      ? OSRM + "/trip/v1/driving/" + coords(puntos) + "?source=first&roundtrip=false&overview=full&geometries=geojson"
      : OSRM + "/route/v1/driving/" + coords(puntos) + "?overview=full&geometries=geojson";
    return fetch(url).then(function (r) { return r.json(); }).then(function (d) {
      var t = optimizar ? (d.trips || [])[0] : (d.routes || [])[0];
      if (d.code !== "Ok" || !t) throw new Error("sin ruta");
      return {
        linea: t.geometry.coordinates.map(function (c) { return [c[1], c[0]]; }),
        metros: t.distance, segundos: t.duration,
        orden: optimizar ? d.waypoints.map(function (w) { return w.waypoint_index; }) : null};
    }).catch(function () {
      return {linea: puntos, metros: null, segundos: null, orden: null, aproximada: true};
    });
  }

  function texto(r) {
    if (r.metros == null) return "ruta aproximada (sin servicio de rutas)";
    return (r.metros / 1000).toFixed(1).replace(".", ",") + " km · unos " + Math.max(1, Math.round(r.segundos / 60)) + " min";
  }

  return {crear: crear, pin: pin, camion: camion, destino: destino, base: base, ruta: ruta, texto: texto};
})();
