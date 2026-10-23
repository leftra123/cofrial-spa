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

  return {crear: crear, pin: pin, ruta: ruta, texto: texto};
})();
