/* Mapa minimalista con OpenStreetMap (teselas estándar, atenuadas con CSS para que resalten las rutas) y rutas con OSRM. Ninguno pide cuenta ni clave.
   Si OSRM no responde, el mapa sigue mostrando los puntos y se dibuja una línea recta entre ellos. */
window.CofrialMapa = (function () {
  /* Escapa un texto para ponerlo como contenido de un elemento dentro de un trozo de HTML. Fuera de eso (atributos, popups, listas) usar nodos y textContent. */
  function esc(texto) {
    var d = document.createElement("div");
    d.textContent = texto;
    return d.innerHTML;
  }

  var OSRM = "https://router.project-osrm.org";
  /* Mosaicos: vienen de las variables de entorno MAP_TILE_* (settings.MAPA_TILES) a través de la plantilla; por defecto, OpenStreetMap.
     La atribución del proveedor se muestra siempre en el mapa (control de atribución de Leaflet). */
  var MOSAICOS = {url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", maxZoom: 19, subdomains: "abc",
                  attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>"};
  try { var cfg = document.getElementById("mapa-tiles"); if (cfg) MOSAICOS = Object.assign(MOSAICOS, JSON.parse(cfg.textContent)); } catch (e) {}

  function crear(id, centro, zoom) {
    var m = L.map(id, {zoomControl: true, attributionControl: true}).setView(centro, zoom || 13);
    L.tileLayer(MOSAICOS.url, {
      maxZoom: MOSAICOS.maxZoom, subdomains: MOSAICOS.subdomains, attribution: MOSAICOS.attribution,
      referrerPolicy: "strict-origin-when-cross-origin"}).addTo(m);          // OSM exige el Referer: sin él responde «403 Access blocked»
    m.on("zoomend", function () { redimensionarCamiones(m); });
    m.on("moveend zoomend layeradd", function () { agendarSeparacion(m); });
    return m;
  }

  /* Tamaño del camión según el zoom: en la calle cabe en una cuadra; al alejar se achica de verdad (el ícono de Leaflet, no un scale CSS). */
  function medidasCamion(zoom) {
    if (zoom == null) return {w: 32, imgH: 20, mostrarEtq: false};
    var w = Math.round(Math.max(24, Math.min(44, 10 + zoom * 1.85)));
    return {w: w, imgH: Math.max(14, Math.round(w * 5 / 8)), mostrarEtq: zoom >= 13};
  }
  function esCamion(l) {
    var o = l && l.options && l.options.icon && l.options.icon.options;
    return !!(l && l._icon && o && (o.className || "").indexOf("pin-camion") >= 0);
  }
  function redimensionarCamiones(m) {
    var z = m.getZoom();
    m.eachLayer(function (l) {
      if (!esCamion(l)) return;
      var o = l.options.icon.options;
      if (o.cofrialZoom === z) return;
      l.setIcon(camion(o.className.indexOf("alerta") >= 0, o.cofrialEtiqueta || "", z));
    });
  }
  /* Camiones cercanos: se reparten en pantalla (solo el dibujo) para no taparse, y quedan debajo de paradas y bodega. */
  var pendiente = new WeakSet();
  function separarCamiones(m) {
    var med = medidasCamion(m.getZoom()), pasoX = med.w + 10, pasoY = med.imgH + 14;
    var huecos = [[0, 0], [pasoX, 0], [-pasoX, 0], [0, -pasoY], [0, pasoY], [pasoX, -pasoY], [-pasoX, -pasoY], [pasoX, pasoY], [-pasoX, pasoY]];
    var camiones = [];
    m.eachLayer(function (l) { if (esCamion(l)) camiones.push(l); });
    if (!camiones.length) return;
    camiones.sort(function (a, b) { return String(a._icon.textContent).localeCompare(String(b._icon.textContent)); });
    if (camiones.length === 1) {
      var solo = camiones[0], o0 = solo.options.icon.options;
      solo._icon.style.marginLeft = (-o0.iconAnchor[0]) + "px";
      solo._icon.style.marginTop = (-o0.iconAnchor[1]) + "px";
      solo.setZIndexOffset(0);
      return;
    }
    var colocados = [];
    camiones.forEach(function (l) {
      var p = m.latLngToContainerPoint(l.getLatLng()), o = l.options.icon.options, elegido = huecos[0];
      for (var h = 0; h < huecos.length; h++) {
        var x = p.x + huecos[h][0], y = p.y + huecos[h][1];
        if (!colocados.some(function (c) { return Math.abs(c[0] - x) < med.w && Math.abs(c[1] - y) < med.imgH + 8; })) { elegido = huecos[h]; break; }
      }
      colocados.push([p.x + elegido[0], p.y + elegido[1]]);
      l._icon.style.marginLeft = (-o.iconAnchor[0] + elegido[0]) + "px";
      l._icon.style.marginTop = (-o.iconAnchor[1] + elegido[1]) + "px";
      l.setZIndexOffset((o.className.indexOf("alerta") >= 0 ? -500 : -1000));
    });
  }
  function agendarSeparacion(m) {
    if (pendiente.has(m)) return;
    pendiente.add(m);
    requestAnimationFrame(function () { pendiente.delete(m); separarCamiones(m); });
  }
  ["setIcon", "setLatLng"].forEach(function (nombre) {          // la flota refresca posición y color cada 5 s: se vuelve a separar
    var original = L.Marker.prototype[nombre];
    L.Marker.prototype[nombre] = function () { var r = original.apply(this, arguments); if (this._map) agendarSeparacion(this._map); return r; };
  });

  /* Pin redondo con texto (número de parada, "C" de camión, "B" de base). */
  function pin(texto, color) {
    return L.divIcon({className: "pin-mapa", iconSize: [28, 28], iconAnchor: [14, 14],
      html: '<span style="background:' + color + '">' + texto + "</span>"});
  }

  /* Camión frigorífico (imagen de marca, vista lateral mirando a la derecha). Con alerta (ruptura de frío) usa la versión roja y late.
     `etiqueta` es el código que se muestra bajo el camión. Las imágenes viven en static/img/marca/; la ruta se deduce de la de este mismo script. */
  var BASE_IMG = (function () {
    var t = document.querySelector('script[src*="js/mapa.js"]');
    return t ? t.getAttribute("src").replace(/js\/mapa\.js.*$/, "img/marca/") : "/static/img/marca/";
  })();
  function camion(alerta, etiqueta, zoom) {
    var med = medidasCamion(zoom), etq = etiqueta || "";
    var url = BASE_IMG + (alerta ? "camion-alerta.png" : "camion-mapa.png");
    var etqH = etq && med.mostrarEtq ? 16 : 0;
    var cajaH = med.imgH + etqH;
    /* PNG de 512×320: <img> + reglas globales lo pintaban casi a tamaño real; fondo en caja fija = escala de mapa */
    var html = '<span class="pin-camion-graf" role="presentation" aria-hidden="true" style="width:' + med.w + "px;height:" + med.imgH + "px;background-image:url('" + url + "')\"></span>";
    if (etq && med.mostrarEtq) html += '<b class="pin-etq">' + esc(etq) + "</b>";
    return L.divIcon({
      className: "pin-camion" + (alerta ? " alerta" : ""),
      iconSize: [med.w, cajaH],
      iconAnchor: [Math.round(med.w / 2), med.imgH],
      popupAnchor: [0, -med.imgH - 4],
      cofrialZoom: zoom == null ? null : zoom, cofrialEtiqueta: etq,
      html: html});
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

  /* Fila de una lista de paradas: «**cliente** · dirección (detalle)». El nombre y la dirección los escribe el cliente al registrarse, así que
     entran como texto y nunca como HTML. */
  function filaParada(cliente, direccion, detalle) {
    var li = document.createElement("li"), nombre = document.createElement("b"), nota = document.createElement("span");
    nombre.textContent = cliente;
    nota.className = "frio";
    nota.textContent = detalle;
    li.appendChild(nombre);
    li.appendChild(document.createTextNode(" · " + direccion + " "));
    li.appendChild(nota);
    return li;
  }

  /* Contenido de un popup con datos variables. Leaflet interpreta un texto como HTML; un nodo lo deja tal cual. Una línea por cada texto. */
  function popupTexto(lineas) {
    var caja = document.createElement("div");
    lineas.forEach(function (linea) {
      var d = document.createElement("div");
      d.textContent = linea;
      caja.appendChild(d);
    });
    return caja;
  }

  /* La ruta que calculó y guardó el servidor ({puntos, km, minutos, aproximada}): se dibuja tal cual, sin volver a pedirle nada a OSRM. */
  function rutaGuardada(r) {
    return {linea: r.puntos, metros: r.aproximada ? null : r.km * 1000, segundos: (r.minutos || 0) * 60, orden: null, aproximada: !!r.aproximada};
  }

  return {crear: crear, pin: pin, camion: camion, destino: destino, base: base, ruta: ruta, rutaGuardada: rutaGuardada, texto: texto, filaParada: filaParada, popupTexto: popupTexto};
})();
