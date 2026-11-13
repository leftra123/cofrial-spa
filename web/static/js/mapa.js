/* Cofrial SpA · mapas nocturnos con MapLibre GL JS sobre teselas vectoriales de OpenFreeMap, y rutas con OSRM. Ninguno pide cuenta ni clave.

   API (las coordenadas siempre son [lat, lon]; el zoom es el de MapLibre, uno menos que Leaflet para la misma escala):

   var m = CofrialMapa.crear("id-del-div", [lat, lon], zoom, {inclinable: false, inclinacion: 0, rumbo: 0, pixelRatioMax: 2, ruedaConPagina: false});
     ruedaConPagina: quien viene bajando por la página sigue bajando aunque el cursor pase sobre el mapa; la rueda hace zoom recién tras una pausa o si empezó sobre el mapa.
     m.nativo               el maplibregl.Map, para lo que esta API no cubra (null si no hay WebGL)
     m.disponible           false si el navegador no puede dibujar el mapa: todo sigue respondiendo sin efecto y el div muestra el aviso .mapa-vacio
     m.contenedor           el div del mapa
     m.baseActual           "openfreemap" o "local" (también en el atributo data-mapa-base del div)
                            el div guarda este objeto en .cofrialMapa, para revisarlo desde la consola
     m.zoom()
     m.encuadrar(puntos, {padding: 40, maxZoom: 15, animar: true})
     m.camara({centro, zoom, inclinacion, rumbo, animar: true})                 mueve la cámara; la inclinación necesita crear(..., {inclinable: true})
     m.al("camiones", fn)   después de repartir los camiones en pantalla (para medir etiquetas)
     m.al("estilo", fn)     ahora si ya hay estilo y cada vez que cambia: las capas propias se agregan aquí, porque cambiar de estilo las borra
     m.al(evento, fn)       cualquier otro evento de maplibregl.Map (moveend, zoomend…)
     m.ordenarCamiones()    pide volver a repartir los camiones
     m.enPantalla(pos, margen = 0)   true si el punto cae dentro del mapa visible, con un margen en píxeles

   Dibujo: m tiene estos métodos, y m.grupo({zoomMin, zoomMax}) entrega un conjunto con los mismos para borrarlo u ocultarlo de una vez (g.limpiar(), g.mostrar(bool)).
   Con zoomMin / zoomMax el grupo solo se ve en ese rango: así el detalle aparece al acercar con la rueda.
   Rendimiento: un marcador es un nodo del DOM que se recoloca en cada movimiento; una capa se dibuja en la GPU. Marcadores solo para pocos elementos con etiqueta
   o interacción (camiones activos); para listas largas, m.puntos. No hay terreno ni edificios 3D. Las lecturas de 5 s usan .actualizar (setData), nunca se recrea una fuente.
     m.camion(pos, {alerta, etiqueta, etiquetaDesde: 12, titulo, popup})        cambia de tamaño con el zoom y se separa de los camiones vecinos
     m.parada(pos, numero, color, {titulo, popup})
     m.destino(pos, {titulo, popup})
     m.base(pos, {titulo, popup, etiqueta})
     m.puntos([{pos, numero, forma, color, radio, offset: [x, y], popup}], {color, radio, zoomMin, zoomMax})   capa del mapa, no DOM; offset en píxeles, igual con cualquier zoom
     m.etiquetas([{pos, texto, offset, grupo}], {zoomMin, zoomMax})             texto en una capa (dibujado en un canvas, nunca como HTML); las que chocan se ocultan
     m.marcador(pos, {html, clase, ancho, alto, ancla, altoPopup, offset, titulo, popup})
     m.ruta(linea, {color, ancho, aproximada, flujo, gradiente: [desde, hasta], zoomMin, zoomMax})
     m.recorridos({base: [lat, lon], alElegir: fn(viaje, tramo), marcasDesde, flechasDesde})   ida y vuelta de uno o varios viajes, en capas compartidas;
                            marcasDesde y flechasDesde: zoom desde el que salen las marcas S y R de la base y las flechas (por defecto, siempre)
   popup acepta un texto, una lista de textos (una línea cada uno, siempre como texto plano) o un nodo del DOM.

   Cada marcador responde a: .mover(pos) .animarA(pos, ms = 4600) .latlon() .popup(contenido) .etiqueta(texto) .desplazar([x, y]) .quitar()
   y el camión además a .alerta(bool). animarA desliza entre lecturas de 5 s; con prefers-reduced-motion salta directo.
   Cada ruta responde a: .actualizar(linea, {aproximada}) .quitar() .mostrar(bool). Se dibuja con un halo difuso y una línea central,
   punteada si es aproximada. flujo agrega una línea que avanza; es opcional porque obliga a redibujar el mapa unas 8 veces por segundo mientras
   esté en pantalla, y se detiene con la pestaña oculta, con el mapa fuera de la vista y con prefers-reduced-motion.
   m.puntos responde a: .actualizar(lista) .enfocar(grupo) .quitar() .mostrar(bool). Cada punto puede llevar borde (color del aro), grupo (a quién pertenece) y forma (el dibujo interior de un estado).
   m.etiquetas responde a lo mismo.
   m.recorridos responde a: .poner([{id, ruta, fase} o {id, ida, vuelta, aproximada}]) .ver("ida" | "vuelta", bool) .enfocar(id) .fase(id, "ida" | "vuelta") .sacar(id) .quitar().
   Ida: línea continua azul. Vuelta: línea a trazos ámbar. Ambas con flechas y corridas a la derecha de su sentido, para que se lean aunque usen la misma calle.
   Es un par apto para daltonismo y no depende solo del color. Una ruta aproximada va a puntos. Con varios camiones, .enfocar atenúa los demás viajes.
   CofrialMapa.partirRuta(ruta) separa la ruta guardada del servidor en {ida, vuelta}, en la última parada; CofrialMapa.largoKm(linea) mide un tramo.

   Sueltas, sin mapa: CofrialMapa.pin / camion / destino / base entregan {html, clase, ancho, alto, …} (las leyendas usan .html); CofrialMapa.PALETA,
   CofrialMapa.COLOR_RUTA, COLOR_IDA y COLOR_VUELTA son los colores para fondo de noche; ruta, rutaGuardada y texto no dependen del mapa.
   CofrialMapa.NIVELES da el zoom de cada nivel de detalle {ciudad, calle}. CofrialMapa.ESTADOS son los estados de un camión {color, borde, forma, texto}; estadoDe(situacion, alerta, sinSenal) elige uno, puntoEstado(pos, estado, {radio, grupo, popup}) arma su punto
   para m.puntos y estadoSVG(estado) su muestra para leyendas. puntoParada(m, pos, numero, total, {grupo, offset, popup}) es la parada numerada, igual en todos los mapas.
   filaParada y popupTexto arman filas y popups con datos del cliente como texto, nunca como HTML.

   Respaldo: el mapa parte con un estilo local (fondo azul noche, sin pedir nada a la red) y cambia al de OpenFreeMap cuando llega. Si no llega, se queda
   en el local y siguen las rutas y los puntos. Si OSRM no responde, ruta() entrega una línea recta entre los puntos. */
window.CofrialMapa = (function () {
  /* Escapa un texto para ponerlo como contenido de un elemento dentro de un trozo de HTML. Fuera de eso (atributos, popups, listas) usar nodos y textContent. */
  function esc(texto) {
    var d = document.createElement("div");
    d.textContent = texto;
    return d.innerHTML;
  }

  var OSRM = "https://router.project-osrm.org";
  /* Estilo: viene de la variable MAP_STYLE_URL (settings.MAPA_TILES) a través de la plantilla. "local" no pide nada a la red. */
  var CONFIG = {estilo: "https://tiles.openfreemap.org/styles/dark", maxZoom: 19,
                attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'};
  try { var cfg = document.getElementById("mapa-tiles"); if (cfg) CONFIG = Object.assign(CONFIG, JSON.parse(cfg.textContent)); } catch (e) {}

  /* Azul y ámbar: se distinguen con los tres tipos de daltonismo y tienen contraste alto sobre el azul noche. El rojo queda para las alertas. */
  var COLOR_IDA = "#56B4E9", COLOR_VUELTA = "#FFB000", COLOR_RUTA = COLOR_IDA;
  var PALETA = [COLOR_IDA, "#BDE63A", "#C084FC", "#FB923C"];
  /* Estados de un camión: mismo azul y ámbar que la ida y la vuelta, lima de la marca, y rojo solo para la ruptura de frío. La forma interior dice lo mismo que el color. */
  var ESTADOS = {
    en_ruta: {color: COLOR_IDA, forma: "ida", texto: "En ruta"},
    en_la_puerta: {color: PALETA[1], forma: "puerta", texto: "En la puerta del cliente"},
    volviendo: {color: COLOR_VUELTA, forma: "vuelta", texto: "Volviendo a la base"},
    en_base: {color: "#94A3B8", forma: "base", texto: "En base"},
    alerta: {color: "#FF6B6B", forma: "alerta", texto: "Ruptura de frío"},
    sin_senal: {color: "#0B1A33", borde: "#CBD5E1", forma: "sin_senal", tinta: "#CBD5E1", texto: "Sin señal"}
  };
  /* Dibujo interior de cada estado, en un cuadro de 24 con el círculo de radio 10 al centro. Lo comparten el punto del mapa (canvas) y la leyenda (SVG). */
  var FORMAS = {
    ida: "M9 6.5 18 12 9 17.5z",
    vuelta: "M15 6.5 6 12 15 17.5z",
    puerta: "M7.5 7.5h9v9h-9z",
    base: "M12 5.5 19 12h-2.2v6.5H7.2V12H5z",
    alerta: "M10.4 4.5h3.2v9.5h-3.2zM10.4 16h3.2v3.4h-3.2z",
    sin_senal: "M16.8 5.4l1.8 1.8L7.2 18.6l-1.8-1.8z"
  };
  /* Desde qué zoom se ve cada nivel de detalle en los mapas de la operación: la ciudad de Temuco entera cabe desde 11, y una cuadra se distingue desde 14,5. */
  var NIVELES = {ciudad: 11, calle: 14.5};
  function estadoDe(situacion, alerta, sinSenal) { return alerta ? "alerta" : sinSenal ? "sin_senal" : ESTADOS[situacion] ? situacion : "en_ruta"; }
  function puntoEstado(pos, estado, op) {
    op = op || {};
    var e = ESTADOS[estado] || ESTADOS.en_ruta;
    return {pos: pos, color: e.color, borde: e.borde, forma: e.forma, radio: op.radio || (estado === "alerta" ? 11 : 8), grupo: op.grupo, popup: op.popup, offset: op.offset};
  }
  function estadoSVG(estado) {
    var e = ESTADOS[estado] || ESTADOS.en_ruta;
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="' + e.color + '" stroke="' + (e.borde || "#FFFFFF") + '" stroke-width="1.5"/><path d="' + FORMAS[e.forma] + '" fill="' + (e.tinta || NOCHE.tierra) + '"/></svg>';
  }

  var NOCHE = {tierra: "#0B1A33", residencial: "#0E2040", verde: "#0D2632", agua: "#123052", edificio: "#10223F", edificioBorde: "#152C4B",
               calle: "#172D4C", avenida: "#1E3A60", avenidaBorde: "#264873", autopista: "#284A78", autopistaBorde: "#335A8E", linea: "#1E3A60",
               etiqueta: "#B4C6DF", etiquetaCalle: "#8BA3C4", etiquetaAgua: "#6E9CCB", halo: "#0B1A33"};

  /* ---------- estilo ---------- */
  function estiloLocal() {
    return {version: 8, name: "Cofrial local", sources: {}, layers: [{id: "fondo", type: "background", paint: {"background-color": NOCHE.tierra}}]};
  }

  /* Sobre el estilo dark de OpenFreeMap: se recolorea cada capa a la marca (los id son los del esquema OpenMapTiles) y las etiquetas salen en español si existe el nombre. */
  var PINTURA = [
    [/^background$/, {"background-color": NOCHE.tierra}],
    [/^(water|waterway)$/, {"fill-color": NOCHE.agua, "line-color": NOCHE.agua}],
    [/^landcover_(ice_shelf|glacier)$/, {"fill-color": NOCHE.residencial}],
    [/^landuse_residential$/, {"fill-color": NOCHE.residencial}],
    [/^(landcover_wood|landuse_park)$/, {"fill-color": NOCHE.verde}],
    [/^building$/, {"fill-color": NOCHE.edificio, "fill-outline-color": NOCHE.edificioBorde}],
    [/^aeroway/, {"fill-color": NOCHE.calle, "line-color": NOCHE.calle}],
    [/^road_(area_)?pier$/, {"fill-color": NOCHE.tierra, "line-color": NOCHE.tierra}],
    [/^highway_(path|minor)$/, {"line-color": NOCHE.calle}],
    [/^highway_major_casing$/, {"line-color": NOCHE.avenidaBorde}],
    [/^highway_major_(inner|subtle)$/, {"line-color": NOCHE.avenida}],
    [/^highway_motorway_casing$/, {"line-color": NOCHE.autopistaBorde}],
    [/^highway_motorway_(inner|subtle)$/, {"line-color": NOCHE.autopista}],
    [/^railway.*dashline$/, {"line-color": NOCHE.tierra}],
    [/^railway/, {"line-color": NOCHE.linea}],
    [/^boundary/, {"line-color": NOCHE.avenidaBorde}],
    [/^road_oneway/, {"icon-opacity": .25}],
    [/^water_name$/, {"text-color": NOCHE.etiquetaAgua, "text-halo-color": NOCHE.halo, "text-halo-width": 1}],
    [/^highway_name/, {"text-color": NOCHE.etiquetaCalle, "text-halo-color": NOCHE.halo, "text-halo-width": 1.2}],
    [/^place_/, {"text-color": NOCHE.etiqueta, "text-halo-color": NOCHE.halo, "text-halo-width": 1.3, "text-halo-blur": .5}]
  ];
  var ES_LINEA = /^line-/, ES_RELLENO = /^fill-/;
  function estiloNocturno(estilo) {
    var nombre = ["coalesce", ["get", "name:es"], ["get", "name:latin"], ["get", "name"]];
    estilo.layers.forEach(function (capa) {
      var pintura = capa.paint || (capa.paint = {}), diseno = capa.layout;
      PINTURA.some(function (regla) {
        if (!regla[0].test(capa.id)) return false;
        Object.keys(regla[1]).forEach(function (k) {
          if ((ES_LINEA.test(k) && capa.type !== "line") || (ES_RELLENO.test(k) && capa.type !== "fill")) return;
          pintura[k] = regla[1][k];
        });
        return true;
      });
      delete pintura["fill-pattern"];                                     // el patrón de bosque taparía el color
      if (diseno && Array.isArray(diseno["text-field"]) && diseno["text-field"][0] === "case") diseno["text-field"] = nombre;
    });
    return estilo;
  }

  var pedidoEstilo = null;
  function cargarEstilo() {
    if (pedidoEstilo) return pedidoEstilo;
    if (!CONFIG.estilo || CONFIG.estilo === "local") return (pedidoEstilo = Promise.reject(new Error("estilo local")));
    var corte = new AbortController(), plazo = setTimeout(function () { corte.abort(); }, 6000);
    pedidoEstilo = fetch(CONFIG.estilo, {signal: corte.signal, credentials: "omit"}).then(function (r) {
      clearTimeout(plazo);
      if (!r.ok) throw new Error("estilo " + r.status);
      return r.json();
    }).then(estiloNocturno);
    return pedidoEstilo;
  }

  function hayWebGL() {
    if (!window.maplibregl) return false;
    try { var c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch (e) { return false; }
  }
  /* Sin GPU el navegador pinta por software: la mitad de la resolución cuadruplica los cuadros por segundo y es lo que separa un mapa usable de uno trabado. */
  function dibujoPorSoftware() {
    try {
      var gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl"), info = gl.getExtension("WEBGL_debug_renderer_info");
      return !!info && /swiftshader|llvmpipe|software/i.test(gl.getParameter(info.UNMASKED_RENDERER_WEBGL));
    } catch (e) { return false; }
  }
  function sinMovimiento() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function lngLat(p) { return [p[1], p[0]]; }

  /* ---------- íconos ---------- */
  /* Tamaño del camión según el zoom: en la calle cabe en una cuadra; al alejar se achica de verdad, no con un scale CSS. La fórmula viene de la escala de Leaflet (zoom + 1). */
  function medidasCamion(zoom, etiquetaDesde) {
    if (zoom == null) return {w: 32, imgH: 20, mostrarEtq: false};
    var w = Math.round(Math.max(24, Math.min(44, 10 + (zoom + 1) * 1.85)));
    return {w: w, imgH: Math.max(14, Math.round(w * 5 / 8)), mostrarEtq: zoom >= (etiquetaDesde == null ? 12 : etiquetaDesde)};
  }

  /* Pin redondo con texto (número de parada). */
  function pin(texto, color) {
    return {clase: "pin-mapa", ancho: 30, alto: 30, ancla: "center", altoPopup: 16,
            html: '<span style="background:' + color + '">' + esc(texto) + "</span>"};
  }

  /* Camión frigorífico (imagen de marca, vista lateral mirando a la derecha). Con alerta (ruptura de frío) usa la versión roja y late.
     `etiqueta` es el código que se muestra bajo el camión. Las imágenes viven en static/img/marca/; la ruta se deduce de la de este mismo script. */
  var BASE_IMG = (function () {
    var t = document.querySelector('script[src*="js/mapa"]');
    return t ? t.getAttribute("src").replace(/js\/mapa[^/]*$/, "img/marca/") : "/static/img/marca/";
  })();
  function camion(alerta, etiqueta, zoom, etiquetaDesde) {
    var med = medidasCamion(zoom, etiquetaDesde), etq = etiqueta || "";
    var url = BASE_IMG + (alerta ? "camion-alerta.png" : "camion-mapa.png");
    /* PNG de 512×320: <img> + reglas globales lo pintaban casi a tamaño real; fondo en caja fija = escala de mapa */
    var html = '<span class="pin-camion-graf" role="presentation" aria-hidden="true" style="width:' + med.w + "px;height:" + med.imgH + "px;background-image:url('" + url + "')\"></span>";
    if (etq && med.mostrarEtq) html += '<b class="pin-etq">' + esc(etq) + "</b>";
    return {clase: "pin-camion" + (alerta ? " alerta" : ""), ancho: med.w, alto: med.imgH, ancla: "bottom", altoPopup: med.imgH + 4, html: html};
  }

  /* Destino de entrega: gota verde con una casa. */
  function destino() {
    return {clase: "pin-destino", ancho: 30, alto: 40, ancla: "bottom", altoPopup: 36,
      html: '<svg viewBox="0 0 30 40" width="30" height="40" aria-hidden="true"><path d="M15 38C15 38 3 23 3 14a12 12 0 0 1 24 0c0 9-12 24-12 24z" fill="#16A34A" stroke="#fff" stroke-width="2"/>' +
        '<path d="M9 15l6-5.5 6 5.5v6.5h-4.2v-4.3h-3.6v4.3H9z" fill="#fff"/></svg>'};
  }

  /* Frigorífico central (punto de salida): cuadrado oscuro con una bodega. */
  function base(etiqueta) {
    return {clase: "pin-base", ancho: 34, alto: 34, ancla: "center", altoPopup: 18,
      html: '<svg viewBox="0 0 34 34" width="34" height="34" aria-hidden="true"><rect x="1.5" y="1.5" width="31" height="31" rx="8" fill="#0F172A" stroke="#fff" stroke-width="2"/>' +
        '<path d="M7 14l10-5.5L27 14v11H7z" fill="#fff"/><rect x="12" y="18" width="10" height="7" rx="1" fill="#0F172A"/><path d="M12 21.5h10" stroke="#fff" stroke-width="1"/></svg>' +
        (etiqueta == null ? "" : '<b class="pin-etq base-contador">' + esc(etiqueta) + "</b>")};
  }

  /* ---------- marcadores ---------- */
  function contenidoPopup(v) {
    if (v instanceof Node) return v;
    var caja = document.createElement("div");
    (Array.isArray(v) ? v : [v]).forEach(function (linea) {
      var d = document.createElement("div");
      d.textContent = linea;
      caja.appendChild(d);
    });
    return caja;
  }

  function Marcador(grupo, pos, icono, op) {
    op = op || {};
    this.grupo = grupo; this.mapa = grupo.mapa; this.pos = pos.slice(); this.dibujada = pos.slice();
    this.despl = op.offset || [0, 0]; this.altoPopup = icono.altoPopup || 0; this.pp = null; this.anim = null; this.enMapa = false;
    var el = this.el = document.createElement("div");
    el.className = icono.clase || "";
    el.style.width = icono.ancho + "px"; el.style.height = icono.alto + "px";
    el.innerHTML = icono.html;
    if (op.titulo) { el.title = op.titulo; el.setAttribute("aria-label", op.titulo); }
    if (this.mapa.nativo) this.mk = new maplibregl.Marker({element: el, anchor: icono.ancla || "center", offset: this.despl, subpixelPositioning: true}).setLngLat(lngLat(pos));
    if (op.popup != null) this.popup(op.popup);
    grupo.items.push(this);
    this.alternar(grupo.activo());
  }
  Marcador.prototype.alternar = function (ver) {
    if (!this.mk || ver === this.enMapa) return;
    if (ver) this.mk.addTo(this.mapa.nativo); else { this.mk.remove(); this.terminar(); }
    this.enMapa = ver;
  };
  Marcador.prototype.latlon = function () { return this.pos.slice(); };
  Marcador.prototype.terminar = function () {
    if (!this.anim) return;
    this.anim = null;
    this.dibujar(this.pos);
  };
  Marcador.prototype.dibujar = function (pos) {
    this.dibujada = pos;
    if (this.mk) this.mk.setLngLat(lngLat(pos));
    if (this.alDeslizar) this.alDeslizar(pos);
  };
  Marcador.prototype.mover = function (pos) {
    this.anim = null; this.pos = pos.slice();
    this.dibujar(this.pos);
    return this;
  };
  Marcador.prototype.animarA = function (pos, ms) {
    var dLat = Math.abs(pos[0] - this.dibujada[0]), dLon = Math.abs(pos[1] - this.dibujada[1]);
    if (!this.mk || !this.enMapa || !this.mapa.enVista || sinMovimiento() || document.hidden || dLat + dLon < 1e-7 || dLat + dLon > .2) return this.mover(pos);   // más de ~20 km en una lectura es un salto, no un viaje
    this.pos = pos.slice();
    this.anim = {desde: this.dibujada.slice(), hacia: this.pos, ms: ms || 4600, inicio: null};
    if (this.mapa.animados.indexOf(this) < 0) this.mapa.animados.push(this);
    this.mapa.pulsar();
    return this;
  };
  Marcador.prototype.popup = function (contenido) {
    if (!this.mk) return this;
    if (!this.pp) { this.pp = new maplibregl.Popup({offset: [this.despl[0], this.despl[1] - this.altoPopup], maxWidth: "280px"}); this.mk.setPopup(this.pp); }
    this.pp.setDOMContent(contenidoPopup(contenido));
    return this;
  };
  Marcador.prototype.desplazar = function (xy) {
    this.despl = xy;
    if (this.mk) this.mk.setOffset(xy);
    if (this.pp) this.pp.setOffset([xy[0], xy[1] - this.altoPopup]);
    return this;
  };
  Marcador.prototype.etiqueta = function (texto) {
    var e = this.el.querySelector(".pin-etq");
    if (e) e.textContent = texto;
    return this;
  };
  Marcador.prototype.quitar = function () {
    this.alternar(false);
    var i = this.grupo.items.indexOf(this);
    if (i >= 0) this.grupo.items.splice(i, 1);
    return this;
  };

  function Camion(grupo, pos, op) {
    op = op || {};
    this.enAlerta = !!op.alerta; this.codigo = op.etiqueta || ""; this.etiquetaDesde = op.etiquetaDesde; this.med = medidasCamion(grupo.mapa.zoom(), op.etiquetaDesde);
    Marcador.call(this, grupo, pos, camion(this.enAlerta, this.codigo, grupo.mapa.zoom(), op.etiquetaDesde), op);
    this.mapa.camiones.push(this);
    this.mapa.ordenarCamiones();
  }
  Camion.prototype = Object.create(Marcador.prototype);
  Camion.prototype.repintar = function () {
    var z = this.mapa.zoom(), ic = camion(this.enAlerta, this.codigo, z, this.etiquetaDesde);
    this.med = medidasCamion(z, this.etiquetaDesde);
    this.el.classList.toggle("alerta", this.enAlerta);
    this.el.style.width = ic.ancho + "px"; this.el.style.height = ic.alto + "px";
    this.el.innerHTML = ic.html;
    this.altoPopup = ic.altoPopup;
    this.desplazar(this.despl);
  };
  Camion.prototype.alerta = function (activa) {
    if (!!activa !== this.enAlerta) { this.enAlerta = !!activa; this.repintar(); this.mapa.ordenarCamiones(); }
    return this;
  };
  Camion.prototype.mover = function (pos) { Marcador.prototype.mover.call(this, pos); this.mapa.ordenarCamiones(); return this; };
  Camion.prototype.quitar = function () {
    Marcador.prototype.quitar.call(this);
    var i = this.mapa.camiones.indexOf(this);
    if (i >= 0) this.mapa.camiones.splice(i, 1);
    this.mapa.ordenarCamiones();
    return this;
  };

  /* ---------- rutas ---------- */
  var serieRutas = 0;
  /* Los pasos de la línea que avanza: un trazo de 3 con un hueco de 4 que se corre por la ruta. */
  var FLUJO = [[0, 4, 3], [.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, .5], [3, 4, 0], [0, .5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, .5]];
  var PUNTEADO = [1.2, 2];

  function rangoZoom(x) {
    var r = {};
    if (x.zoomMin != null) r.minzoom = x.zoomMin;
    if (x.zoomMax != null) r.maxzoom = x.zoomMax;
    return r;
  }
  function geojson(linea) {
    if (!linea || linea.length < 2) return {type: "FeatureCollection", features: []};
    return {type: "Feature", properties: {}, geometry: {type: "LineString", coordinates: linea.map(lngLat)}};
  }
  function Ruta(grupo, linea, op) {
    op = op || {};
    this.grupo = grupo; this.mapa = grupo.mapa; this.id = "cofrial-ruta-" + (++serieRutas); this.linea = linea; this.aproximada = !!op.aproximada;
    this.color = op.color || COLOR_RUTA; this.ancho = op.ancho || 3.5; this.gradiente = op.gradiente || null;
    this.flujo = !!op.flujo && !sinMovimiento(); this.zoomMin = op.zoomMin; this.zoomMax = op.zoomMax;
    this.visible = grupo.activo();
    grupo.items.push(this);
    this.mapa.rutas.push(this);
    this.pintar();
    if (this.flujo) this.mapa.pulsar();
  }
  Ruta.prototype.pintar = function () {
    var n = this.mapa.nativo;
    if (!n || !this.mapa.estiloListo || n.getSource(this.id)) return;
    var id = this.id, antes = this.mapa.capaEtiquetas(), ver = {visibility: this.visible ? "visible" : "none", "line-cap": "round", "line-join": "round"}, rango = rangoZoom(this);
    n.addSource(id, {type: "geojson", data: geojson(this.linea), lineMetrics: true});
    n.addLayer(Object.assign({id: id + "-halo", type: "line", source: id, layout: ver, paint: {"line-color": this.color, "line-width": this.ancho * 3.4, "line-blur": this.ancho * 2.4, "line-opacity": .5}}, rango), antes);
    var centro = {"line-color": this.color, "line-width": this.ancho};
    if (this.aproximada) centro["line-dasharray"] = PUNTEADO;
    else if (this.gradiente) centro["line-gradient"] = ["interpolate", ["linear"], ["line-progress"], 0, this.gradiente[0], 1, this.gradiente[1]];
    n.addLayer(Object.assign({id: id + "-centro", type: "line", source: id, layout: Object.assign({}, ver, this.aproximada ? {"line-cap": "butt"} : {}), paint: centro}, rango), antes);
    if (this.flujo) n.addLayer(Object.assign({id: id + "-flujo", type: "line", source: id, layout: Object.assign({}, ver, {"line-cap": "butt"}), paint: {"line-color": "#FFFFFF", "line-width": Math.max(1.5, this.ancho * .5), "line-opacity": .85, "line-dasharray": FLUJO[0]}}, rango), antes);
  };
  Ruta.prototype.actualizar = function (linea, op) {
    this.linea = linea;
    var n = this.mapa.nativo, fuente = n && this.mapa.estiloListo && n.getSource(this.id), aproximada = op && op.aproximada != null ? !!op.aproximada : this.aproximada;
    if (fuente) fuente.setData(geojson(linea));
    if (aproximada !== this.aproximada) {
      this.aproximada = aproximada;
      if (fuente) { this.despintar(); this.pintar(); }
    }
    return this;
  };
  Ruta.prototype.despintar = function () {
    var n = this.mapa.nativo, id = this.id;
    if (!n || !this.mapa.estiloListo || !n.getSource(id)) return;
    ["-flujo", "-centro", "-halo"].forEach(function (s) { if (n.getLayer(id + s)) n.removeLayer(id + s); });
    n.removeSource(id);
  };
  Ruta.prototype.alternar = function (ver) {
    this.visible = ver;
    var n = this.mapa.nativo, id = this.id;
    if (!n || !this.mapa.estiloListo) return;
    ["-halo", "-centro", "-flujo"].forEach(function (s) { if (n.getLayer(id + s)) n.setLayoutProperty(id + s, "visibility", ver ? "visible" : "none"); });
  };
  Ruta.prototype.mostrar = function (ver) { this.alternar(!!ver); return this; };
  Ruta.prototype.quitar = function () {
    this.despintar();
    this.flujo = false;
    [this.grupo.items, this.mapa.rutas].forEach(function (lista) { var i = lista.indexOf(this); if (i >= 0) lista.splice(i, 1); }, this);
    return this;
  };

  /* ---------- puntos en capa ---------- */
  /* El círculo se dibuja en un canvas y entra al mapa como imagen: el número no depende de las fuentes de OpenFreeMap, así que también sale en el respaldo local. */
  function iconoPunto(n, color, radio, numero, borde, forma) {
    var nombre = "cofrial-punto-" + color + "-" + radio + "-" + (numero == null ? "" : numero) + "-" + (borde || "") + "-" + (forma || "");
    if (n.hasImage(nombre)) return nombre;
    var escala = 2, lado = (radio * 2 + 4) * escala, lienzo = document.createElement("canvas"), c = lienzo.getContext("2d");
    lienzo.width = lienzo.height = lado;
    c.beginPath(); c.arc(lado / 2, lado / 2, radio * escala, 0, Math.PI * 2);
    c.fillStyle = color; c.fill();
    c.lineWidth = (forma ? 1.5 : borde ? 3 : numero == null ? 1 : 2) * escala; c.strokeStyle = borde || "#FFFFFF"; c.stroke();
    if (forma) {
      c.save();
      c.translate(lado / 2, lado / 2); c.scale(radio * escala / 10, radio * escala / 10); c.translate(-12, -12);
      c.fillStyle = forma === "sin_senal" ? ESTADOS.sin_senal.tinta : NOCHE.tierra;
      c.fill(new Path2D(FORMAS[forma]));
      c.restore();
    }
    if (numero != null) {
      c.fillStyle = NOCHE.tierra; c.font = "700 " + Math.round(radio * escala) + "px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
      c.fillText(String(numero), lado / 2, lado / 2 + escala / 2);
    }
    n.addImage(nombre, c.getImageData(0, 0, lado, lado), {pixelRatio: escala});
    return nombre;
  }
  function Puntos(grupo, lista, op) {
    op = op || {};
    this.grupo = grupo; this.mapa = grupo.mapa; this.id = "cofrial-puntos-" + (++serieRutas); this.lista = lista || [];
    this.color = op.color || "#94A3B8"; this.radio = op.radio || 5; this.zoomMin = op.zoomMin; this.zoomMax = op.zoomMax;
    this.visible = grupo.activo(); this.foco = null;
    grupo.items.push(this);
    this.mapa.rutas.push(this);
    this.pintar();
  }
  Puntos.prototype.datos = function () {
    var n = this.mapa.nativo, yo = this;
    return {type: "FeatureCollection", features: this.lista.map(function (p, i) {
      return {type: "Feature", properties: {i: i, img: iconoPunto(n, p.color || yo.color, yo.radioDe(p), p.numero, p.borde, p.forma), off: p.offset || [0, 0], grupo: p.grupo == null ? "" : String(p.grupo)},
              geometry: {type: "Point", coordinates: lngLat(p.pos)}};
    })};
  };
  Puntos.prototype.pintar = function () {
    var n = this.mapa.nativo;
    if (!n || !this.mapa.estiloListo || n.getSource(this.id)) return;
    n.addSource(this.id, {type: "geojson", data: this.datos()});
    n.addLayer(Object.assign({id: this.id, type: "symbol", source: this.id, layout: {
      visibility: this.visible ? "visible" : "none", "icon-image": ["get", "img"], "icon-offset": ["get", "off"], "icon-allow-overlap": true, "icon-ignore-placement": true,
      "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport"}, paint: {"icon-opacity": this.opacidad()}}, rangoZoom(this)));
  };
  Puntos.prototype.opacidad = function () { return this.foco == null ? 1 : ["case", ["==", ["get", "grupo"], this.foco], 1, .2]; };
  Puntos.prototype.enfocar = function (grupo) {
    this.foco = grupo == null ? null : String(grupo);
    var n = this.mapa.nativo;
    if (n && this.mapa.estiloListo && n.getLayer(this.id)) n.setPaintProperty(this.id, "icon-opacity", this.opacidad());
    return this;
  };
  Puntos.prototype.radioDe = function (p) { return p.radio || (p.numero != null ? 14 : this.radio); };
  /* Se compara en píxeles contra la lista en vez de consultar la capa: es más barato al mover el mouse, y la consulta entrega el offset convertido en texto, que MapLibre rechaza. */
  Puntos.prototype.enPixel = function (px) {
    var n = this.mapa.nativo, z = n.getZoom();
    if (!this.visible || (this.zoomMin != null && z < this.zoomMin) || (this.zoomMax != null && z >= this.zoomMax)) return null;
    for (var i = this.lista.length - 1; i >= 0; i--) {
      var p = this.lista[i], q = n.project(lngLat(p.pos)), o = p.offset || [0, 0], r = this.radioDe(p) + 3, dx = px.x - q.x - o[0], dy = px.y - q.y - o[1];
      if (dx * dx + dy * dy <= r * r) return {punto: p, capa: this};
    }
    return null;
  };
  Puntos.prototype.actualizar = function (lista) {
    this.lista = lista;
    var n = this.mapa.nativo, fuente = n && this.mapa.estiloListo && n.getSource(this.id);
    if (fuente) fuente.setData(this.datos());
    return this;
  };
  Puntos.prototype.alternar = function (ver) {
    this.visible = ver;
    var n = this.mapa.nativo;
    if (n && this.mapa.estiloListo && n.getLayer(this.id)) n.setLayoutProperty(this.id, "visibility", ver ? "visible" : "none");
  };
  Puntos.prototype.mostrar = function (ver) { this.alternar(!!ver); return this; };
  Puntos.prototype.quitar = function () {
    var n = this.mapa.nativo;
    if (n && this.mapa.estiloListo && n.getSource(this.id)) { n.removeLayer(this.id); n.removeSource(this.id); }
    [this.grupo.items, this.mapa.rutas].forEach(function (lista) { var i = lista.indexOf(this); if (i >= 0) lista.splice(i, 1); }, this);
    return this;
  };

  /* ---------- etiquetas en capa ---------- */
  /* Texto dibujado en un canvas: no depende de las fuentes de OpenFreeMap, así que también sale en el respaldo local, y un nombre escrito por un cliente nunca se interpreta como HTML. */
  var LARGO_ETIQUETA = 28;
  function iconoEtiqueta(n, texto) {
    var nombre = "cofrial-etq-" + texto;
    if (n.hasImage(nombre)) return nombre;
    var escala = 2, alto = 20 * escala, relleno = 7 * escala, lienzo = document.createElement("canvas"), c = lienzo.getContext("2d"), fuente = "600 " + 12 * escala + "px system-ui, sans-serif";
    c.font = fuente;
    lienzo.width = Math.ceil(c.measureText(texto).width) + relleno * 2; lienzo.height = alto;
    c = lienzo.getContext("2d");                                               // cambiar el tamaño del lienzo reinicia el contexto
    c.font = fuente; c.textBaseline = "middle";
    c.beginPath(); if (c.roundRect) c.roundRect(escala, escala, lienzo.width - 2 * escala, alto - 2 * escala, 6 * escala); else c.rect(escala, escala, lienzo.width - 2 * escala, alto - 2 * escala);
    c.fillStyle = "rgba(11, 26, 51, .92)"; c.fill();
    c.lineWidth = escala; c.strokeStyle = "rgba(255, 255, 255, .28)"; c.stroke();
    c.fillStyle = "#E7EFFA"; c.fillText(texto, relleno, alto / 2 + escala / 2);
    n.addImage(nombre, c.getImageData(0, 0, lienzo.width, alto), {pixelRatio: escala});
    return nombre;
  }
  function Etiquetas(grupo, lista, op) { Puntos.call(this, grupo, lista, op); }
  Etiquetas.prototype = Object.create(Puntos.prototype);
  Etiquetas.prototype.datos = function () {
    var n = this.mapa.nativo;
    return {type: "FeatureCollection", features: this.lista.map(function (p, i) {
      var t = String(p.texto == null ? "" : p.texto);
      if (t.length > LARGO_ETIQUETA) t = t.slice(0, LARGO_ETIQUETA - 1).trim() + "…";
      return {type: "Feature", properties: {i: i, img: iconoEtiqueta(n, t), off: p.offset || [0, 0], grupo: p.grupo == null ? "" : String(p.grupo)}, geometry: {type: "Point", coordinates: lngLat(p.pos)}};
    })};
  };
  Etiquetas.prototype.pintar = function () {
    var n = this.mapa.nativo;
    if (!n || !this.mapa.estiloListo || n.getSource(this.id)) return;
    n.addSource(this.id, {type: "geojson", data: this.datos()});
    n.addLayer(Object.assign({id: this.id, type: "symbol", source: this.id, layout: {
      visibility: this.visible ? "visible" : "none", "icon-image": ["get", "img"], "icon-anchor": "left", "icon-offset": ["get", "off"],
      "icon-pitch-alignment": "viewport", "icon-rotation-alignment": "viewport"}, paint: {"icon-opacity": this.opacidad()}}, rangoZoom(this)));
  };
  Etiquetas.prototype.enPixel = function () { return null; };                  // el toque es de la parada, no de su nombre

  /* ---------- ida y vuelta ---------- */
  /* La ruta guardada es una sola línea base -> paradas -> base. La ida termina en la última parada; desde ahí es la vuelta. */
  function partirRuta(r) {
    var p = r.puntos || [], marcas = r.paradas || [], corte = -1;
    marcas.forEach(function (m) { if (m.indice != null && m.indice > corte) corte = m.indice; });
    if (corte < 0 || corte >= p.length) return {ida: p, vuelta: []};
    return {ida: p.slice(0, corte + 1), vuelta: p.slice(corte)};
  }
  function largoKm(linea) {
    var total = 0, rad = Math.PI / 180;
    for (var i = 1; i < (linea || []).length; i++) {
      var a = linea[i - 1], b = linea[i], dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
      var h = Math.pow(Math.sin(dLat / 2), 2) + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.pow(Math.sin(dLon / 2), 2);
      total += 12742 * Math.asin(Math.sqrt(h));
    }
    return total;
  }
  function iconoFlecha(n, tramo, color) {
    var nombre = "cofrial-flecha-" + tramo;
    if (n.hasImage(nombre)) return nombre;
    var escala = 2, ancho = 16 * escala, alto = 14 * escala, lienzo = document.createElement("canvas"), c = lienzo.getContext("2d");
    lienzo.width = ancho; lienzo.height = alto;
    c.beginPath(); c.moveTo(3 * escala, 2 * escala); c.lineTo(13 * escala, 7 * escala); c.lineTo(3 * escala, 12 * escala); c.lineTo(6 * escala, 7 * escala); c.closePath();
    c.lineJoin = "round"; c.lineWidth = 2.5 * escala; c.strokeStyle = NOCHE.tierra; c.stroke();
    c.fillStyle = color; c.fill();
    n.addImage(nombre, c.getImageData(0, 0, ancho, alto), {pixelRatio: escala});
    return nombre;
  }
  var TRAMOS = {ida: {color: COLOR_IDA, nombre: "Ida", salida: "S"}, vuelta: {color: COLOR_VUELTA, nombre: "Vuelta", salida: "R"}};
  var DESPLAZA = ["interpolate", ["linear"], ["zoom"], 8, 1.5, 12, 2.5, 16, 4];                                                   // a la derecha del sentido de viaje
  var DESPLAZA_FLECHA = ["interpolate", ["linear"], ["zoom"], 8, ["literal", [0, 1.5]], 12, ["literal", [0, 2.5]], 16, ["literal", [0, 4]]];
  var ANCHO_LINEA = ["interpolate", ["linear"], ["zoom"], 8, 2.5, 13, 3.5, 16, 5];
  var ATENUADA = .12;

  function Recorridos(grupo, op) {
    op = op || {};
    this.grupo = grupo; this.mapa = grupo.mapa; this.id = "cofrial-recorridos-" + (++serieRutas); this.viajes = []; this.foco = null;
    this.ver_ = {ida: true, vuelta: true}; this.visible = grupo.activo(); this.alElegir = op.alElegir || null; this.base = op.base || null;
    grupo.items.push(this);
    this.mapa.rutas.push(this);
    this.flechasDesde = op.flechasDesde;
    var rangoMarcas = op.marcasDesde == null ? {} : {zoomMin: op.marcasDesde};
    this.marcas = this.base ? {ida: grupo.puntos([], rangoMarcas), vuelta: grupo.puntos([], rangoMarcas)} : null;      // después de las líneas, para quedar sobre ellas
    this.pintar();
    if (this.alElegir && this.mapa.nativo) this.escuchar();
  }
  Recorridos.prototype.datos = function (tramo) {
    var f = [];
    this.viajes.forEach(function (v) {
      var linea = v[tramo];
      if (!linea || linea.length < 2) return;
      f.push({type: "Feature", properties: {viaje: String(v.id), aprox: !!v.aproximada, hecho: tramo === "ida" && v.fase === "vuelta"}, geometry: {type: "LineString", coordinates: linea.map(lngLat)}});
    });
    return {type: "FeatureCollection", features: f};
  };
  Recorridos.prototype.opacidad = function (base, tenue) {
    var propia = ["case", ["==", ["get", "hecho"], true], tenue, base];        // la ida ya recorrida pierde fuerza cuando el camión viene de vuelta
    return this.foco == null ? propia : ["case", ["==", ["get", "viaje"], this.foco], propia, ATENUADA];
  };
  Recorridos.prototype.pintar = function () {
    var n = this.mapa.nativo, yo = this;
    if (!n || !this.mapa.estiloListo || n.getSource(this.id + "-ida")) return;
    var antes = this.mapa.capaEtiquetas();
    Object.keys(TRAMOS).forEach(function (t) {
      var id = yo.id + "-" + t, color = TRAMOS[t].color, ver = yo.visible && yo.ver_[t] ? "visible" : "none", esVuelta = t === "vuelta";
      n.addSource(id, {type: "geojson", data: yo.datos(t)});
      n.addLayer({id: id + "-halo", type: "line", source: id, layout: {visibility: ver, "line-cap": "round", "line-join": "round"},
                  paint: {"line-color": color, "line-width": 11, "line-blur": 7, "line-offset": DESPLAZA, "line-opacity": yo.opacidad(.42, .16)}}, antes);
      var centro = {"line-color": color, "line-width": ANCHO_LINEA, "line-offset": DESPLAZA, "line-opacity": yo.opacidad(1, .45)};
      if (esVuelta) centro["line-dasharray"] = [2, 1.6];
      n.addLayer({id: id + "-centro", type: "line", source: id, filter: ["==", ["get", "aprox"], false], layout: {visibility: ver, "line-cap": esVuelta ? "butt" : "round", "line-join": "round"}, paint: centro}, antes);
      n.addLayer({id: id + "-aprox", type: "line", source: id, filter: ["==", ["get", "aprox"], true], layout: {visibility: ver, "line-cap": "round", "line-join": "round"},
                  paint: {"line-color": color, "line-width": ANCHO_LINEA, "line-offset": DESPLAZA, "line-opacity": yo.opacidad(1, .45), "line-dasharray": [.1, 2]}}, antes);
      n.addLayer({id: id + "-flechas", type: "symbol", source: id, minzoom: yo.flechasDesde == null ? 0 : yo.flechasDesde, layout: {visibility: ver, "symbol-placement": "line", "symbol-spacing": 90, "icon-image": iconoFlecha(n, t, color), "icon-offset": DESPLAZA_FLECHA,
                  "icon-rotation-alignment": "map", "icon-pitch-alignment": "map", "icon-allow-overlap": true, "icon-ignore-placement": true}, paint: {"icon-opacity": yo.opacidad(1, .45)}}, antes);
    });
  };
  Recorridos.prototype.capas = function (t) { return [this.id + "-" + t + "-halo", this.id + "-" + t + "-centro", this.id + "-" + t + "-aprox", this.id + "-" + t + "-flechas"]; };
  Recorridos.prototype.refrescar = function () {
    var n = this.mapa.nativo, yo = this;
    if (n && this.mapa.estiloListo) Object.keys(TRAMOS).forEach(function (t) { var f = n.getSource(yo.id + "-" + t); if (f) f.setData(yo.datos(t)); });
    if (!this.marcas) return;
    Object.keys(TRAMOS).forEach(function (t) {
      var hay = yo.viajes.some(function (v) { return v[t] && v[t].length > 1; }), esIda = t === "ida";
      yo.marcas[t].actualizar(hay ? [{pos: yo.base, numero: TRAMOS[t].salida, color: TRAMOS[t].color, radio: 10, offset: [esIda ? -30 : 30, -8], popup: esIda ? "Salida del frigorífico" : "Regreso al frigorífico"}] : []);
    });
  };
  Recorridos.prototype.poner = function (lista) {
    this.viajes = (lista || []).map(function (v) {
      var partes = v.ruta ? partirRuta(v.ruta) : v;
      return {id: v.id, ida: partes.ida || [], vuelta: partes.vuelta || [], aproximada: v.ruta ? !!v.ruta.aproximada : !!v.aproximada, fase: v.fase || "ida"};
    });
    this.refrescar();
    return this;
  };
  Recorridos.prototype.sacar = function (id) {
    var antes = this.viajes.length;
    this.viajes = this.viajes.filter(function (v) { return String(v.id) !== String(id); });
    if (this.viajes.length !== antes) this.refrescar();
    return this;
  };
  Recorridos.prototype.fase = function (id, fase) {
    var v = this.viajes.filter(function (x) { return String(x.id) === String(id); })[0];
    if (v && v.fase !== fase) { v.fase = fase; this.refrescar(); }                  // solo al cambiar: una lectura de 5 s no toca las fuentes
    return this;
  };
  Recorridos.prototype.aplicarVisibilidad = function () {
    var n = this.mapa.nativo, yo = this;
    Object.keys(TRAMOS).forEach(function (t) {
      var ver = yo.visible && yo.ver_[t];
      if (n && yo.mapa.estiloListo) yo.capas(t).forEach(function (c) { if (n.getLayer(c)) n.setLayoutProperty(c, "visibility", ver ? "visible" : "none"); });
      if (yo.marcas) yo.marcas[t].alternar(ver);
    });
  };
  Recorridos.prototype.ver = function (tramo, activo) { this.ver_[tramo] = !!activo; this.aplicarVisibilidad(); return this; };
  Recorridos.prototype.alternar = function (ver) { this.visible = ver; this.aplicarVisibilidad(); };
  Recorridos.prototype.mostrar = function (ver) { this.alternar(!!ver); return this; };
  Recorridos.prototype.enfocar = function (id) {
    this.foco = id == null || id === "" ? null : String(id);
    var n = this.mapa.nativo, yo = this;
    if (!n || !this.mapa.estiloListo) return this;
    Object.keys(TRAMOS).forEach(function (t) {
      var pre = yo.id + "-" + t;
      if (!n.getLayer(pre + "-halo")) return;
      n.setPaintProperty(pre + "-halo", "line-opacity", yo.opacidad(.42, .16));
      n.setPaintProperty(pre + "-centro", "line-opacity", yo.opacidad(1, .45));
      n.setPaintProperty(pre + "-aprox", "line-opacity", yo.opacidad(1, .45));
      n.setPaintProperty(pre + "-flechas", "icon-opacity", yo.opacidad(1, .45));
    });
    return this;
  };
  /* Tocar una línea elige su viaje y tocar el fondo vuelve a todos. Los marcadores y los puntos tienen su propio popup: esos toques no cuentan. */
  Recorridos.prototype.escuchar = function () {
    var yo = this, n = this.mapa.nativo;
    n.on("click", function (e) {
      if (e.originalEvent.target !== n.getCanvas() || !yo.mapa.estiloListo || yo.mapa.puntoEn(e.point)) return;
      var capas = [], t = 8;
      Object.keys(TRAMOS).forEach(function (k) { if (yo.ver_[k]) [yo.id + "-" + k + "-centro", yo.id + "-" + k + "-aprox"].forEach(function (c) { if (n.getLayer(c)) capas.push(c); }); });
      var f = capas.length ? n.queryRenderedFeatures([[e.point.x - t, e.point.y - t], [e.point.x + t, e.point.y + t]], {layers: capas}) : [];
      yo.alElegir(f.length ? f[0].properties.viaje : null, f.length && f[0].layer.id.indexOf("-vuelta-") > 0 ? "vuelta" : "ida");
    });
  };
  Recorridos.prototype.quitar = function () {
    var n = this.mapa.nativo, yo = this;
    Object.keys(TRAMOS).forEach(function (t) {
      if (n && yo.mapa.estiloListo && n.getSource(yo.id + "-" + t)) {
        yo.capas(t).forEach(function (c) { if (n.getLayer(c)) n.removeLayer(c); });
        n.removeSource(yo.id + "-" + t);
      }
      if (yo.marcas) yo.marcas[t].quitar();
    });
    [this.grupo.items, this.mapa.rutas].forEach(function (lista) { var i = lista.indexOf(this); if (i >= 0) lista.splice(i, 1); }, this);
    return this;
  };

  /* ---------- grupos y mapa ---------- */
  function Grupo(mapa, op) {
    op = op || {};
    this.mapa = mapa; this.items = []; this.visible = true; this.zoomMin = op.zoomMin; this.zoomMax = op.zoomMax; this.enRango = this.dentro(mapa.zoom());
    if (op.zoomMin != null || op.zoomMax != null) mapa.porZoom.push(this);
  }
  Grupo.prototype.dentro = function (z) { return z == null || ((this.zoomMin == null || z >= this.zoomMin) && (this.zoomMax == null || z < this.zoomMax)); };
  Grupo.prototype.activo = function () { return this.visible && this.enRango; };
  Grupo.prototype.aplicar = function () {
    var ver = this.activo();
    this.items.forEach(function (x) { x.alternar(ver); });
    this.mapa.ordenarCamiones();
  };
  Grupo.prototype.marcador = function (pos, op) { return new Marcador(this, pos, op, op); };
  Grupo.prototype.camion = function (pos, op) { return new Camion(this, pos, op); };
  Grupo.prototype.parada = function (pos, numero, color, op) { return new Marcador(this, pos, pin(numero, color || COLOR_RUTA), op); };
  Grupo.prototype.destino = function (pos, op) { return new Marcador(this, pos, destino(), op); };
  Grupo.prototype.base = function (pos, op) { return new Marcador(this, pos, base(op && op.etiqueta), op); };
  Grupo.prototype.puntos = function (lista, op) { return new Puntos(this, lista, op); };
  Grupo.prototype.etiquetas = function (lista, op) { return new Etiquetas(this, lista, op); };
  Grupo.prototype.ruta = function (linea, op) { return new Ruta(this, linea, op); };
  Grupo.prototype.recorridos = function (op) { return new Recorridos(this, op); };
  Grupo.prototype.limpiar = function () {
    this.items.slice().forEach(function (x) { x.quitar(); });
    return this;
  };
  Grupo.prototype.mostrar = function (ver) {
    this.visible = !!ver;
    this.aplicar();
    return this;
  };

  var TEXTOS = {"NavigationControl.ZoomIn": "Acercar", "NavigationControl.ZoomOut": "Alejar", "NavigationControl.ResetBearing": "Volver al norte", "Popup.Close": "Cerrar",
                "AttributionControl.ToggleAttribution": "Mostrar u ocultar la atribución", "Marker.Title": "Marcador del mapa", "Map.Title": "Mapa"};

  function Mapa(id, centro, zoom, op) {
    op = op || {};
    this.contenedor = typeof id === "string" ? document.getElementById(id) : id;
    this.nativo = null; this.disponible = false; this.estiloListo = false; this.baseActual = "local"; this.fuentesBase = []; this.huboTesela = false;
    this.oyentes = {camiones: [], estilo: []}; this.porZoom = []; this.raiz = new Grupo(this); this.camiones = []; this.rutas = [];
    this.animados = []; this.latiendo = false; this.pasoFlujo = -1; this.separando = false; this.enVista = true;
    this.contenedor.cofrialMapa = this;
    if (hayWebGL()) {
      try {
        this.nativo = new maplibregl.Map({
          container: this.contenedor, style: estiloLocal(), center: lngLat(centro), zoom: zoom == null ? 12 : zoom, maxZoom: CONFIG.maxZoom,
          pitch: op.inclinacion || 0, bearing: op.rumbo || 0, attributionControl: false, locale: TEXTOS, renderWorldCopies: false,
          pixelRatio: dibujoPorSoftware() ? 1 : Math.min(window.devicePixelRatio || 1, op.pixelRatioMax || 2),       // una pantalla 3x cuesta más del doble de píxeles y no se nota en un mapa
          dragRotate: !!op.inclinable, pitchWithRotate: !!op.inclinable, touchPitch: !!op.inclinable});
      } catch (e) { this.nativo = null; }
    }
    if (!this.nativo) { this.avisoSinMapa(); return; }
    this.disponible = true;
    this.preparar(!!op.inclinable);
    if (op.ruedaConPagina) this.cuidarRueda();
  }
  Mapa.prototype.avisoSinMapa = function () {
    this.contenedor.setAttribute("data-mapa-base", "ninguno");
    var aviso = document.createElement("div");
    aviso.className = "mapa-vacio";
    aviso.innerHTML = "<div><b>Este navegador no puede dibujar el mapa</b>Necesita WebGL. Los datos del recorrido siguen disponibles en esta página.</div>";
    this.contenedor.appendChild(aviso);
  };
  Mapa.prototype.preparar = function (inclinable) {
    var yo = this, n = this.nativo;
    if (!inclinable) n.touchZoomRotate.disableRotation();
    n.addControl(new maplibregl.NavigationControl({showCompass: inclinable, visualizePitch: inclinable}), "top-left");
    n.addControl(new maplibregl.AttributionControl({compact: false, customAttribution: CONFIG.attribution}), "bottom-right");
    this.marcarBase("local");
    n.on("style.load", function () {
      yo.estiloListo = true;
      yo.rutas.forEach(function (r) { r.pintar(); });
      yo.oyentes.estilo.forEach(function (fn) { fn(yo); });
    });
    /* Sin este oyente MapLibre escribe cada tesela fallida en la consola. Si ninguna llega, el mapa queda como en el respaldo local y se avisa. */
    n.on("error", function (e) { if (yo.fuentesBase.indexOf(e.sourceId) >= 0 && !yo.huboTesela) yo.avisoBase(true); });
    n.on("sourcedata", function (e) { if (e.tile && yo.fuentesBase.indexOf(e.sourceId) >= 0 && !yo.huboTesela) { yo.huboTesela = true; yo.avisoBase(false); } });
    /* El estilo de OpenFreeMap pide «circle-11» al alejar y su sprite no lo trae: una imagen vacía evita el aviso en consola y deja solo el nombre del pueblo. */
    n.on("styleimagemissing", function (e) { if (!n.hasImage(e.id)) n.addImage(e.id, {width: 1, height: 1, data: new Uint8Array(4)}); });
    n.on("zoomend", function () { yo.redimensionarCamiones(); });
    n.on("zoom", function () { yo.revisarZoom(); });
    n.on("click", function (e) {
      var h = yo.puntoEn(e.point);
      if (!h || h.punto.popup == null) return;
      var o = h.punto.offset || [0, 0];
      new maplibregl.Popup({offset: [o[0], o[1] - h.capa.radioDe(h.punto) - 2], maxWidth: "280px"}).setLngLat(lngLat(h.punto.pos)).setDOMContent(contenidoPopup(h.punto.popup)).addTo(n);
    });
    n.on("mousemove", function (e) { if (!n.isMoving()) n.getCanvas().style.cursor = yo.puntoEn(e.point) ? "pointer" : ""; });
    if (window.IntersectionObserver) new IntersectionObserver(function (e) { yo.enVista = e[e.length - 1].isIntersecting; if (yo.enVista) yo.pulsar(); }).observe(this.contenedor);
    n.on("moveend", function () { yo.ordenarCamiones(); });
    cargarEstilo().then(function (estilo) {
      yo.estiloListo = false;
      yo.fuentesBase = Object.keys(estilo.sources);
      n.setStyle(estilo, {diff: false});
      yo.marcarBase("openfreemap");
    }, function () { yo.avisoBase(true); });
  };
  /* La rueda sobre el mapa hace zoom; fuera de él, baja la página. Sin esto, quien baja por la página queda atrapado al pasar el cursor sobre el mapa:
     mientras la página venga moviéndose, el mapa no recibe la rueda y la página sigue. Tras una pausa breve, la rueda vuelve a ser del mapa. */
  Mapa.prototype.cuidarRueda = function () {
    var c = this.contenedor, ultima = -1e9, PAUSA_MS = 350;
    this.nativo.scrollZoom.setWheelZoomRate(1 / 90);                           // MapLibre avanza muy poco por muesca: de la región a la calle serían más de 50
    window.addEventListener("wheel", function (e) { if (!c.contains(e.target)) ultima = e.timeStamp; }, {passive: true, capture: true});
    c.addEventListener("wheel", function (e) { if (e.timeStamp - ultima < PAUSA_MS) { ultima = e.timeStamp; e.stopPropagation(); } }, {passive: true, capture: true});
  };
  Mapa.prototype.marcarBase = function (nombre) {
    this.baseActual = nombre;
    this.contenedor.setAttribute("data-mapa-base", nombre);
  };
  Mapa.prototype.avisoBase = function (ver) {
    var aviso = this.contenedor.querySelector(".mapa-sin-base");
    if (ver && !aviso) {
      aviso = document.createElement("div");
      aviso.className = "mapa-sin-base";
      aviso.textContent = "Mapa base sin conexión: rutas y puntos siguen activos";
      this.contenedor.appendChild(aviso);
    } else if (!ver && aviso) aviso.remove();
  };
  /* Bajo los nombres de lugares, para que la ruta no los tape. El estilo local no tiene etiquetas. */
  Mapa.prototype.capaEtiquetas = function () {
    var capas = this.nativo.getStyle().layers, i;
    for (i = 0; i < capas.length; i++) if (capas[i].id.indexOf("place_") === 0) return capas[i].id;
    return undefined;
  };
  Mapa.prototype.puntoEn = function (px) {
    for (var i = this.rutas.length - 1; i >= 0; i--) {
      var h = this.rutas[i] instanceof Puntos && this.rutas[i].enPixel(px);
      if (h) return h;
    }
    return null;
  };
  Mapa.prototype.zoom = function () { return this.nativo ? this.nativo.getZoom() : null; };
  Mapa.prototype.enPantalla = function (pos, margen) {
    if (!this.nativo) return false;
    var p = this.nativo.project(lngLat(pos)), lienzo = this.nativo.getContainer(), g = margen || 0;
    return p.x >= -g && p.y >= -g && p.x <= lienzo.clientWidth + g && p.y <= lienzo.clientHeight + g;
  };
  Mapa.prototype.grupo = function (op) { return new Grupo(this, op); };
  /* Solo actúa al cruzar un límite: durante el zoom no se toca nada del DOM. */
  Mapa.prototype.revisarZoom = function () {
    var z = this.zoom();
    this.porZoom.forEach(function (g) { var d = g.dentro(z); if (d !== g.enRango) { g.enRango = d; g.aplicar(); } });
  };
  Mapa.prototype.al = function (evento, fn) {
    if (evento === "camiones") this.oyentes.camiones.push(fn);
    else if (evento === "estilo") { this.oyentes.estilo.push(fn); if (this.estiloListo) fn(this); }
    else if (this.nativo) this.nativo.on(evento, fn);
    return this;
  };
  Mapa.prototype.encuadrar = function (puntos, op) {
    op = op || {};
    if (!this.nativo || !puntos.length) return this;
    var caja = new maplibregl.LngLatBounds();
    puntos.forEach(function (p) { caja.extend(lngLat(p)); });
    this.nativo.fitBounds(caja, {padding: op.padding == null ? 40 : op.padding, maxZoom: op.maxZoom || 15, duration: op.animar === false ? 0 : 700});
    return this;
  };
  Mapa.prototype.camara = function (op) {
    if (!this.nativo) return this;
    var destinoCamara = {duration: op.animar === false ? 0 : 900};
    if (op.centro) destinoCamara.center = lngLat(op.centro);
    if (op.zoom != null) destinoCamara.zoom = op.zoom;
    if (op.inclinacion != null) destinoCamara.pitch = op.inclinacion;
    if (op.rumbo != null) destinoCamara.bearing = op.rumbo;
    this.nativo.easeTo(destinoCamara);
    return this;
  };

  /* Un solo bucle por mapa mueve los marcadores que se deslizan y la línea que avanza por las rutas; se detiene cuando no queda nada que animar.
     requestAnimationFrame no corre con la pestaña oculta, así que ahí tampoco se gasta nada. */
  Mapa.prototype.pulsar = function () {
    if (this.latiendo || !this.nativo) return;
    this.latiendo = true;
    var yo = this;
    function paso(ahora) {
      var sigue = yo.avanzarMarcadores(ahora);
      sigue = yo.avanzarFlujo(ahora) || sigue;
      if (sigue) requestAnimationFrame(paso); else yo.latiendo = false;
    }
    requestAnimationFrame(paso);
  };
  Mapa.prototype.avanzarMarcadores = function (ahora) {
    var llego = false;
    this.animados = this.animados.filter(function (m) {
      var a = m.anim;
      if (!a) return false;
      if (a.inicio == null) a.inicio = ahora;
      var t = Math.min(1, (ahora - a.inicio) / a.ms);
      m.dibujar([a.desde[0] + (a.hacia[0] - a.desde[0]) * t, a.desde[1] + (a.hacia[1] - a.desde[1]) * t]);
      if (t < 1) return true;
      m.anim = null; llego = true;
      return false;
    });
    if (llego) this.ordenarCamiones();
    return this.animados.length > 0;
  };
  Mapa.prototype.avanzarFlujo = function (ahora) {
    var con = this.rutas.filter(function (r) { return r.flujo; }), n = this.nativo;
    if (!con.length || !this.enVista) return false;                         // al volver a la vista, el observador reanuda el bucle
    var paso = Math.floor(ahora / 120) % FLUJO.length;
    if (paso !== this.pasoFlujo && this.estiloListo) {
      this.pasoFlujo = paso;
      con.forEach(function (r) { if (n.getLayer(r.id + "-flujo")) n.setPaintProperty(r.id + "-flujo", "line-dasharray", FLUJO[paso]); });
    }
    return true;
  };

  Mapa.prototype.redimensionarCamiones = function () {
    var z = this.zoom();
    this.camiones.forEach(function (c) { var med = medidasCamion(z, c.etiquetaDesde); if (c.med.w !== med.w || c.med.mostrarEtq !== med.mostrarEtq) c.repintar(); });
    this.ordenarCamiones();
  };
  Mapa.prototype.ordenarCamiones = function () {
    if (this.separando || !this.nativo) return;
    this.separando = true;
    var yo = this;
    requestAnimationFrame(function () { yo.separando = false; yo.separarCamiones(); });
  };
  /* Camiones cercanos: se reparten en pantalla (solo el dibujo, con el offset del marcador) para no taparse; el CSS los deja debajo de paradas y bodega. */
  Mapa.prototype.separarCamiones = function () {
    var med = medidasCamion(this.zoom()), pasoX = med.w + 10, pasoY = med.imgH + 14, n = this.nativo;
    var huecos = [[0, 0], [pasoX, 0], [-pasoX, 0], [0, -pasoY], [0, pasoY], [pasoX, -pasoY], [-pasoX, -pasoY], [pasoX, pasoY], [-pasoX, pasoY]];
    var lista = this.camiones.filter(function (c) { return c.enMapa; }), colocados = [];
    lista.sort(function (a, b) { return String(a.codigo).localeCompare(String(b.codigo)); });
    lista.forEach(function (c) {
      var p = n.project(lngLat(c.dibujada)), elegido = huecos[0];
      for (var h = 0; h < huecos.length; h++) {
        var x = p.x + huecos[h][0], y = p.y + huecos[h][1];
        if (!colocados.some(function (o) { return Math.abs(o[0] - x) < med.w && Math.abs(o[1] - y) < med.imgH + 8; })) { elegido = huecos[h]; break; }
      }
      colocados.push([p.x + elegido[0], p.y + elegido[1]]);
      if (elegido[0] !== c.despl[0] || elegido[1] !== c.despl[1]) c.desplazar(elegido);
    });
    this.oyentes.camiones.forEach(function (fn) { fn(); });
  };
  ["marcador", "camion", "parada", "destino", "base", "puntos", "etiquetas", "ruta", "recorridos"].forEach(function (nombre) {
    Mapa.prototype[nombre] = function () { return this.raiz[nombre].apply(this.raiz, arguments); };
  });

  /* Parada numerada de un recorrido: azul de la ida, y con aro ámbar la última, desde donde el camión vuelve. Más chica en una pantalla angosta. */
  function puntoParada(m, pos, numero, total, op) {
    op = op || {};
    return {pos: pos, numero: numero, color: COLOR_IDA, borde: numero === total ? COLOR_VUELTA : null, radio: m.contenedor.clientWidth < 500 ? 11 : 14, grupo: op.grupo, offset: op.offset, popup: op.popup};
  }

  function crear(id, centro, zoom, opciones) { return new Mapa(id, centro, zoom, opciones); }

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

  return {crear: crear, pin: pin, camion: camion, destino: destino, base: base, ruta: ruta, rutaGuardada: rutaGuardada, texto: texto, PALETA: PALETA, COLOR_RUTA: COLOR_RUTA, COLOR_IDA: COLOR_IDA, COLOR_VUELTA: COLOR_VUELTA,
          partirRuta: partirRuta, largoKm: largoKm, filaParada: filaParada, popupTexto: popupTexto,
          NIVELES: NIVELES, ESTADOS: ESTADOS, estadoDe: estadoDe, puntoEstado: puntoEstado, estadoSVG: estadoSVG, puntoParada: puntoParada};
})();
