/* Cofrial SpA · Torre de control. Pinta el pulso que entrega el servidor y lo vuelve a pedir cada 5 s.
   Todo lo que viene de la base entra con textContent o createElement, nunca como HTML: un cliente puede llamarse «<img src=x onerror=...>». */
window.CofrialTorre = (function () {
  var SONDEO_MS = 5000, ESPERA_MS = 8000, SIN_LECTURAS_S = 120;
  var ENTRAR = "/cuenta/entrar/?next=/torre/";
  var ITEMS_VISIBLES = 4;      // clientes por etapa antes de plegar el resto

  var ESTADOS = {
    verificado: {texto: "Verificado", chip: "entregado", ico: "M20 6L9 17l-5-5"},
    sin_evidencia: {texto: "Sin evidencia ahora", chip: "pendiente", ico: "M12 8v5M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"},
    no_comprobado: {texto: "No se pudo comprobar", chip: "cancelado", ico: "M9.1 9a3 3 0 015.8 1c0 2-3 2.6-3 4.5M12 18h.01"}
  };
  var SEGMENTOS = {
    Hospital: {letra: "H", clase: "seg-hospital"},
    Supermercado: {letra: "S", clase: "seg-supermercado"},
    Feria: {letra: "F", clase: "seg-feria"},
    Institucional: {letra: "I", clase: "seg-institucional"}
  };
  var SIN_SEGMENTO = {letra: "?", clase: "seg-otro"};
  var CHIP_NIVEL = {"Fidelizado": "entregado", "Recompra": "transito", "Primer pedido": "asignado", "En riesgo": "alerta"};

  /* ---------- utilidades ---------- */
  function $(id) { return document.getElementById(id); }
  function el(etiqueta, clase, texto) {
    var n = document.createElement(etiqueta);
    if (clase) n.className = clase;
    if (texto !== undefined && texto !== null) n.textContent = texto;
    return n;
  }
  function enlace(url, texto, clase) { var a = el("a", clase, texto); a.href = url; return a; }
  function poner(campo, texto) { var n = document.querySelector('[data-ahora="' + campo + '"]'); if (n) n.textContent = texto; }
  function icono(d) {
    var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg"), p = document.createElementNS(ns, "path");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("width", "14"); svg.setAttribute("height", "14"); svg.setAttribute("aria-hidden", "true");
    p.setAttribute("d", d); svg.appendChild(p);
    return svg;
  }
  function chipEstado(estado, texto) {
    var e = ESTADOS[estado], c = el("span", "chip sin-punto torre-estado " + e.chip);
    c.appendChild(icono(e.ico)); c.appendChild(document.createTextNode(texto === undefined ? e.texto : texto));
    return c;
  }
  function chipNivel(nivel) { return el("span", "chip " + (CHIP_NIVEL[nivel] || "cancelado"), nivel); }
  function segmento(nombre) { return SEGMENTOS[nombre] || SIN_SEGMENTO; }
  function insignia(nombre) { var s = segmento(nombre), n = el("span", "seg-marca " + s.clase, s.letra); n.setAttribute("aria-hidden", "true"); return n; }
  function miles(n) { return Number(n).toLocaleString("es-CL"); }
  function pesos(n) { return "$" + miles(n); }
  function coma(n) { return String(n).replace(".", ","); }
  function pesosCortos(n) { return n >= 1000000 ? "$" + coma((n / 1000000).toFixed(1)) + " M" : pesos(n); }
  function hora(fecha) { return fecha.toLocaleTimeString("es-CL", {hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false}); }
  function fechaCorta(iso) { return new Date(iso).toLocaleDateString("es-CL", {day: "2-digit", month: "2-digit", year: "numeric"}); }
  function antiguedad(seg) {
    if (seg === null || seg === undefined) return "Sin lecturas";
    if (seg < 90) return "hace " + seg + " s";
    if (seg < 5400) return "hace " + Math.round(seg / 60) + " min";
    return "hace " + Math.round(seg / 3600) + " h";
  }
  /* Evita rehacer una sección si sus datos no cambiaron: conserva el foco, los paneles abiertos y lo que se esté leyendo. */
  var vistos = {};
  function siCambio(clave, datos, pintar) {
    var json = JSON.stringify(datos);
    if (vistos[clave] === json) return;
    delete vistos[clave];        // si pintar falla, aunque sea a medias, la sección se vuelve a pintar en el próximo sondeo
    pintar(datos);
    vistos[clave] = json;
  }
  /* Una sección que falla no detiene a las demás ni se confunde con una caída de la red: se registra y las otras siguen. */
  function seccion(nombre, pintar, siFalla) {
    try { pintar(); } catch (e) {
      console.error("Torre: no se pudo pintar «" + nombre + "»", e);
      if (siFalla) siFalla();
    }
  }

  /* ---------- 8.1 Lectura ---------- */
  function tonoLectura(ahora) {
    if (ahora.camiones_en_alerta) return "alerta";
    if (ahora.ultima_lectura_seg === null || ahora.ultima_lectura_seg > SIN_LECTURAS_S) return "aviso";
    return "ok";
  }
  function pintarLectura(p) {
    var generado = hora(new Date(p.generado_en)), frases = p.lectura;
    $("torre-lectura").dataset.tono = conexion === "vivo" ? tonoLectura(p.ahora) : "sin-datos";
    $("torre-hora").textContent = "Datos de las " + generado;
    if (conexion !== "vivo") frases = ["Último dato recibido a las " + generado + "."].concat(frases);       // «Sin novedades» ya no se afirma como presente
    var cuerpo = frases.map(function (f, i) { return el("p", i === 0 ? "principal" : "", f); });
    $("torre-frases").replaceChildren.apply($("torre-frases"), cuerpo);
  }

  /* ---------- 8.2 Mapa ---------- */
  /* Mapa nocturno de CofrialMapa (MapLibre + OpenFreeMap). Las coordenadas van como [lat, lon], igual que en el resto de la app. */
  var mapa = null, marcasCliente = {}, marcasCamion = {}, marcaBase = null, contornos = null;
  var ENCUADRE = [[-36.85, -74.1], [-40.95, -70.4]];        // del sur de Biobío a la entrada de Los Lagos: La Araucanía queda al centro y grande
  /* Dónde va el nombre de cada región: La Araucanía, justo sobre su borde, porque sus clientes llenan el polígono; Los Lagos, en la parte que entra en el encuadre. */
  var ETIQUETAS = {"Biobío": [-37.0, -72.15], "La Araucanía": [-37.4, -71.35], "Los Ríos": [-40.05, -71.95], "Los Lagos": [-40.72, -72.6]};
  var ANCLA = 12, PASO = 25;                                // marcador de 24 px; separación mínima entre dos en pantalla
  var COLOR_PRINCIPAL = "#BDE63A", COLOR_VECINA = "#8BA3C4"; // sobre el azul noche del mapa: lima de la marca y gris azulado
  var Z_CLIENTE = 1, Z_CAMION = 3, Z_BASE = 5;               // clientes al fondo, camiones encima, el frigorífico sobre todo

  function iniciarMapa(base) {
    if (!window.maplibregl || !window.CofrialMapa) return;
    var caja = $("mapa-torre");
    mapa = CofrialMapa.crear("mapa-torre", [base.lat, base.long], 6);
    if (!mapa.disponible) { mapa = null; return; }          // sin WebGL el div ya muestra el aviso; el resto de la Torre sigue
    var n = mapa.nativo;
    n.scrollZoom.disable();                                 // la página es larga: la rueda debe seguir bajando por ella
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) n.dragPan.disable();    // en el teléfono, un dedo desplaza la página; dos mueven el mapa
    mapa.encuadrar(ENCUADRE, {padding: 8, maxZoom: 9, animar: false});
    marcaBase = mapa.base([base.lat, base.long], {titulo: base.nombre, popup: el("b", "", base.nombre)});
    marcaBase.el.style.zIndex = Z_BASE;
    mapa.al("estilo", ponerContornos);                      // cambiar de estilo (local a OpenFreeMap) borra las capas: se vuelven a poner
    mapa.al("zoomend", separarClientes);
    fetch(caja.dataset.geo).then(function (r) { if (!r.ok) throw r; return r.json(); }).then(pintarContornos).catch(function () {
      caja.appendChild(el("p", "torre-mapa-nota", "No se pudieron cargar los contornos de las regiones."));
    });
  }
  function pintarContornos(geo) {
    contornos = geo;
    ponerContornos();
    geo.features.forEach(function (f) {                     // el nombre de cada región, como marcador de texto (no depende de las tipografías del estilo)
      var punto = ETIQUETAS[f.properties.nombre];
      if (!punto) return;
      var marca = mapa.marcador(punto, {clase: "geo-etiqueta" + (f.properties.principal ? " principal" : ""), ancho: 150, alto: 26, ancla: "center", html: ""});
      marca.el.appendChild(el("span", "", f.properties.nombre));
      marca.el.style.zIndex = 0;
    });
  }
  function ponerContornos() {
    var n = mapa && mapa.nativo;
    if (!n || !contornos || !mapa.estiloListo || n.getSource("torre-geo")) return;       // sin estilo cargado no hay dónde poner capas: el aviso de estilo lo vuelve a llamar
    n.addSource("torre-geo", {type: "geojson", data: contornos});
    var principal = ["==", ["get", "principal"], true], vecina = ["!=", ["get", "principal"], true];
    n.addLayer({id: "torre-geo-relleno", type: "fill", source: "torre-geo", paint: {"fill-color": ["case", principal, COLOR_PRINCIPAL, COLOR_VECINA], "fill-opacity": ["case", principal, 0.2, 0.05]}});
    n.addLayer({id: "torre-geo-vecina", type: "line", source: "torre-geo", filter: vecina, layout: {"line-join": "round"}, paint: {"line-color": COLOR_VECINA, "line-width": 1.2, "line-opacity": 0.65, "line-dasharray": [4, 3]}});
    n.addLayer({id: "torre-geo-principal", type: "line", source: "torre-geo", filter: principal, layout: {"line-join": "round"}, paint: {"line-color": COLOR_PRINCIPAL, "line-width": 3, "line-opacity": 1}});
  }
  function popupCliente(c) {
    var n = el("div", "torre-popup");
    n.appendChild(el("b", "", c.nombre));
    n.appendChild(el("div", "frio", c.segmento + ", " + c.comuna));
    var pie = el("div", "torre-popup-pie");
    pie.appendChild(chipNivel(c.nivel));
    pie.appendChild(enlace(c.url, "Abrir ficha"));
    n.appendChild(pie);
    return n;
  }
  function htmlCliente(nombre) { var s = segmento(nombre); return '<span class="seg-marca ' + s.clase + '">' + s.letra + "</span>"; }       // clase y letra salen de una tabla fija, no de la base
  function pintarClientes(lista) {
    if (!mapa) return;
    var vivos = {};
    lista.forEach(function (c) {
      vivos[c.url] = true;
      var m = marcasCliente[c.url];
      if (!m) {
        m = mapa.marcador([c.lat, c.long], {clase: "torre-pin", ancho: ANCLA * 2, alto: ANCLA * 2, ancla: "center", altoPopup: ANCLA, html: htmlCliente(c.segmento), titulo: c.nombre, popup: popupCliente(c)});
        m.el.style.zIndex = Z_CLIENTE;
        marcasCliente[c.url] = m;
      } else {
        m.mover([c.lat, c.long]);
        m.popup(popupCliente(c));
      }
    });
    Object.keys(marcasCliente).forEach(function (url) { if (!vivos[url]) { marcasCliente[url].quitar(); delete marcasCliente[url]; } });
    separarClientes();
  }
  /* Varios clientes comparten ciudad (ocho en Temuco): en pantalla se reparten alrededor de su punto para que cada uno se vea y se pueda tocar.
     Solo se mueve el dibujo; la coordenada sigue siendo la real. */
  function separarClientes() {
    if (!mapa || !mapa.nativo) return;
    var n = mapa.nativo;
    function px(pos) { return n.project([pos[1], pos[0]]); }
    var puestos = marcaBase ? [px(marcaBase.latlon())] : [];
    Object.keys(marcasCliente).sort().forEach(function (url) {
      var m = marcasCliente[url], p = px(m.latlon()), dx = 0, dy = 0;
      for (var anillo = 0, libre = false; anillo < 6 && !libre; anillo++) {
        var cuantos = anillo === 0 ? 1 : anillo * 6;
        for (var i = 0; i < cuantos && !libre; i++) {
          var ang = (i / cuantos) * 2 * Math.PI - Math.PI / 2, x = anillo * PASO * Math.cos(ang), y = anillo * PASO * Math.sin(ang);
          libre = !puestos.some(function (o) { return Math.hypot(o.x - p.x - x, o.y - p.y - y) < PASO; });
          if (libre) { dx = Math.round(x); dy = Math.round(y); }
        }
      }
      puestos.push({x: p.x + dx, y: p.y + dy});
      if (m.despl[0] !== dx || m.despl[1] !== dy) m.desplazar([dx, dy]);
    });
  }
  function pintarCamiones(lista) {
    if (!mapa) return;
    var vivos = {};
    lista.forEach(function (c) {
      var id = String(c.id).replace(/[^\w-]/g, "");         // CofrialMapa.camion arma HTML con la etiqueta
      vivos[id] = true;
      var m = marcasCamion[id];
      if (!m) {
        m = mapa.camion([c.lat, c.long], {alerta: c.alerta, etiqueta: id, titulo: id, popup: el("div")});
        m.el.style.zIndex = Z_CAMION;
        marcasCamion[id] = m;
      } else {
        m.animarA([c.lat, c.long]);
        m.alerta(c.alerta);
      }
      var texto = el("div", "torre-popup");
      texto.appendChild(el("b", "", id));
      texto.appendChild(el("div", c.alerta ? "torre-popup-alerta" : "frio", c.alerta ? "Con ruptura de frío" : "En ruta"));
      m.popup(texto);
    });
    Object.keys(marcasCamion).forEach(function (id) { if (!vivos[id]) { marcasCamion[id].quitar(); delete marcasCamion[id]; } });
  }
  function pintarLeyenda(p) {
    var cuenta = {};
    p.clientes_mapa.forEach(function (c) { cuenta[c.segmento] = (cuenta[c.segmento] || 0) + 1; });
    var nombres = Object.keys(SEGMENTOS).concat(Object.keys(cuenta).filter(function (n) { return !SEGMENTOS[n]; }).sort());
    siCambio("leyenda", cuenta, function () {
      var ul = $("torre-segmentos");
      if (!p.clientes_mapa.length) { ul.replaceChildren(el("li", "frio", "Sin clientes con segmento y dirección todavía.")); return; }
      ul.replaceChildren.apply(ul, nombres.map(function (n) {
        var li = el("li");
        li.appendChild(insignia(n)); li.appendChild(el("span", "", n)); li.appendChild(el("b", "", cuenta[n] || 0));
        return li;
      }));
    });
    var alerta = p.camiones.filter(function (c) { return c.alerta; }).length, ruta = p.camiones.length - alerta;
    $("torre-camiones").textContent = !p.camiones.length ? "Ninguno en ruta ni con alerta." :
      ruta + " en ruta" + (alerta ? ", " + alerta + " con ruptura de frío" : ", ninguno con ruptura de frío") + ".";
  }

  /* ---------- 8.3 Clientes frecuentes ---------- */
  var frecuentes = [];
  function pintarFrecuentes() {
    var filtro = $("filtro-segmento").value, cuerpo = $("torre-frecuentes");
    var filas = frecuentes.filter(function (c) { return !filtro || c.segmento === filtro; }).map(function (c) {
      var tr = el("tr"), nombre = el("th"), seg = el("td", "torre-seg"), nivel = el("td");
      nombre.scope = "row"; nombre.appendChild(enlace(c.url, c.nombre));
      seg.appendChild(insignia(c.segmento)); seg.appendChild(document.createTextNode(c.segmento));
      nivel.appendChild(chipNivel(c.nivel));
      tr.append(nombre, seg, el("td", "", c.comuna), el("td", "num", c.pedidos), el("td", "", fechaCorta(c.ultimo)), nivel);
      return tr;
    });
    if (!filas.length) {
      var vacio = el("td", "vacio", frecuentes.length ? "Ningún cliente de este segmento entre los 8 más frecuentes." :
        "Sin pedidos de clientes con segmento en los últimos 90 días. Aparecerán aquí cuando compren.");
      vacio.colSpan = 6;
      var tr = el("tr"); tr.appendChild(vacio); filas = [tr];
    }
    cuerpo.replaceChildren.apply(cuerpo, filas);
  }
  function opcionesFiltro() {
    var sel = $("filtro-segmento"), actual = sel.value, nombres = [];
    frecuentes.forEach(function (c) { if (nombres.indexOf(c.segmento) < 0) nombres.push(c.segmento); });
    if (actual && nombres.indexOf(actual) < 0) nombres.push(actual);        // el filtro elegido no desaparece aunque hoy quede vacío
    var opciones = [el("option", "", "Todos")].concat(nombres.sort().map(function (n) { var o = el("option", "", n); o.value = n; return o; }));
    opciones[0].value = "";
    sel.replaceChildren.apply(sel, opciones);
    sel.value = actual;
  }

  /* ---------- 8.4 Antes y ahora ---------- */
  function pintarAntes(a) {
    var ol = $("torre-registro"), s = a.supuestos;
    ol.replaceChildren.apply(ol, a.registro.map(function (l) {
      var li = el("li");
      li.append(el("time", "", l[0]), el("span", "canal", l[1]), el("span", "texto", l[2]));
      return li;
    }));
    $("antes-mermas").textContent = "$" + coma(s.merma_bajo_mm) + " a $" + s.merma_alto_mm + " millones a la semana; $" + coma(s.merma_base_mm) + " millones en el escenario base (supuestos, Tablas 5 y 6 del informe)";
    $("antes-tiempo").textContent = s.viajes_semana + " viajes × " + s.min_coordinacion + " min de coordinación = " + s.horas_semana + " horas a la semana (los " + s.min_coordinacion + " min son un supuesto)";
  }
  function pintarAhora(a) {
    var total = a.ventas_24h.B2B + a.ventas_24h.B2C, sinLectura = a.ultima_lectura_seg === null || a.ultima_lectura_seg > SIN_LECTURAS_S;
    poner("ventas", pesos(total));
    poner("ventas-canal", total ? "B2B " + pesos(a.ventas_24h.B2B) + " y B2C " + pesos(a.ventas_24h.B2C) : "Sin ventas en 24 h: compra en la tienda para verla aquí");
    poner("lectura", antiguedad(a.ultima_lectura_seg));
    poner("alertas", miles(a.alertas_24h));
    poner("riesgo", pesosCortos(a.riesgo_actual_clp));
    poner("riesgo-det", a.camiones_en_alerta ? "a bordo de " + a.camiones_en_alerta + (a.camiones_en_alerta === 1 ? " camión" : " camiones") + " con ruptura" : "ningún camión con ruptura ahora");
    poner("historico", pesosCortos(a.riesgo_historico_clp));
    poner("no-concretadas", miles(a.no_concretadas));
    poner("interacciones", miles(a.interacciones));
    document.querySelector('[data-tarjeta="lectura"]').classList.toggle("critico", sinLectura);
    document.querySelector('[data-tarjeta="riesgo"]').classList.toggle("critico", a.camiones_en_alerta > 0);
  }

  /* ---------- 8.5 Embudo ---------- */
  function listaItems(etapa) {
    var ul = el("ul", "torre-items");
    function fila(i) {
      var li = el("li");
      li.append(enlace(i.url, i.nombre), el("span", "frio", i.detalle));
      return li;
    }
    etapa.items.slice(0, ITEMS_VISIBLES).forEach(function (i) { ul.appendChild(fila(i)); });
    var frag = document.createDocumentFragment();
    frag.appendChild(ul);
    var resto = etapa.items.slice(ITEMS_VISIBLES);
    if (resto.length) {
      var d = el("details", "torre-mas");
      d.dataset.etapa = etapa.nombre;
      d.appendChild(el("summary", "", "Ver " + resto.length + " más"));
      var ul2 = el("ul", "torre-items");
      resto.forEach(function (i) { ul2.appendChild(fila(i)); });
      d.appendChild(ul2);
      frag.appendChild(d);
    }
    return frag;
  }
  function bloqueEtapa(etapa) {
    var b = el("div", "torre-etapa"), cab = el("div", "torre-etapa-cab");
    cab.append(el("h4", "", etapa.nombre), el("b", "torre-etapa-n", etapa.n));
    b.appendChild(cab);
    b.appendChild(el("div", "frio", etapa.monto_clp ? pesos(etapa.monto_clp) : "Sin monto"));
    if (etapa.items.length) b.appendChild(listaItems(etapa));
    return b;
  }
  function pintarEmbudo(e) {
    var caja = $("torre-embudo"), aparte = $("torre-aparte"), abiertos = {};
    document.querySelectorAll(".torre-mas[open]").forEach(function (d) { abiertos[d.dataset.etapa] = true; });
    var vacio = e.fases.concat([{etapas: e.aparte}]).every(function (f) { return f.etapas.every(function (x) { return !x.n; }); });
    caja.replaceChildren.apply(caja, e.fases.map(function (f) {
      var col = el("article", "torre-fase"), cab = el("header", "torre-fase-cab");
      var n = f.etapas.reduce(function (t, x) { return t + x.n; }, 0);
      cab.append(el("h3", "", f.nombre), el("b", "", n));
      col.appendChild(cab);
      f.etapas.forEach(function (x) { col.appendChild(bloqueEtapa(x)); });
      return col;
    }));
    aparte.replaceChildren.apply(aparte, e.aparte.map(function (x) { var b = bloqueEtapa(x); b.classList.add("fuera"); return b; }));
    document.querySelectorAll(".torre-mas").forEach(function (d) { if (abiertos[d.dataset.etapa]) d.open = true; });
    $("torre-b2c").textContent = (vacio ? "Aún no hay prospectos ni empresas en el embudo: aparecen al registrar un prospecto en el CRM o una empresa con pedidos. " : "") +
      "Además, " + miles(e.n_b2c) + (e.n_b2c === 1 ? " cliente particular (B2C) compra" : " clientes particulares (B2C) compran") + " solo en la tienda, sin vendedor.";
  }

  /* ---------- 8.6 Front-Office y Back-Office ---------- */
  function pintarLado(id, filas) {
    var ul = $(id);
    ul.replaceChildren.apply(ul, filas.map(function (f) {
      var li = el("li");
      li.append(el("h4", "", f.nombre), el("p", "torre-dato", f.dato), enlace(f.url, "Ver pantalla"));
      return li;
    }));
  }
  function pasoTraza(titulo, valor, url, tono) {
    var li = el("li", tono ? "tpaso " + tono : "tpaso");
    li.append(el("span", "frio", titulo), url ? enlace(url, valor) : el("b", "", valor));
    return li;
  }
  function pintarTraza(t) {
    var caja = $("torre-traza");
    if (!t) { caja.replaceChildren(el("p", "frio", "Aún no hay un pedido en viaje para trazar")); return; }
    var temp = t.temp_camara === null ? "sin lectura" : coma(t.temp_camara) + " °C";
    var ol = el("ol", "torre-pasos");
    ol.append(pasoTraza("Orden web", "N.º " + t.orden_id, t.orden_url),
              pasoTraza("Cliente en el CRM", t.cliente, t.cliente_url),
              pasoTraza("Camión", t.camion_id),
              pasoTraza("Salida del viaje", fechaCorta(t.salida_en) + ", " + hora(new Date(t.salida_en))),
              pasoTraza("Última lectura del camión", temp),
              t.alerta === null ? pasoTraza("Alerta de frío", "Sin lectura") : pasoTraza("Alerta de frío", t.alerta ? "Sí" : "No", null, t.alerta ? "alerta" : "ok"));
    caja.replaceChildren(ol);
  }
  function pintarFrontBack(p) {
    if (!p.front_back) { $("torre-front-back").hidden = true; return; }
    siCambio("front-back", p.front_back, function (fb) { pintarLado("fb-front-lista", fb.front); pintarLado("fb-back-lista", fb.back); });
    siCambio("traza", p.pedido_trazado, pintarTraza);
    $("torre-front-back").hidden = false;
  }

  /* ---------- 8.7 Rúbrica ---------- */
  var filasRubrica = {};
  function crearFilaRubrica(r) {
    var fila = el("article", "torre-fila"), dim = el("div", "torre-dim", r.dim), que = el("div", "torre-que"), lado = el("div", "torre-fila-lado");
    que.append(el("h3", "", r.titulo), el("p", "frio", r.exigencia));
    var estado = el("div"), ev = el("ul", "torre-evidencia");
    lado.append(estado, enlace(r.url, "Ver pantalla"));
    fila.append(dim, que, ev, lado);
    $("torre-rubrica").appendChild(fila);
    return filasRubrica[r.dim] = {fila: fila, estado: estado, ev: ev};
  }
  /* Sin conexión o sin sesión nada se da por verificado: la evidencia queda a la vista, atenuada, y el estado pasa a «No se pudo comprobar». */
  function estadoVisible(r) { return conexion === "vivo" ? r.estado : "no_comprobado"; }
  function pintarRubrica(filas) {
    filas.forEach(function (r) {
      var f = filasRubrica[r.dim] || crearFilaRubrica(r), estado = estadoVisible(r);
      if (f.fila.dataset.estado !== estado) { f.fila.dataset.estado = estado; f.estado.replaceChildren(chipEstado(estado)); }
      f.ev.replaceChildren.apply(f.ev, r.evidencia.map(function (t) { return el("li", "", t); }));
    });
    var resumen = $("torre-resumen"), ok = filas.filter(function (r) { return estadoVisible(r) === "verificado"; }).length;
    var piezas = [el("span", "torre-resumen-txt", "Rúbrica: " + ok + " de " + filas.length + " verificadas")];
    filas.forEach(function (r) {
      var estado = estadoVisible(r), c = chipEstado(estado, r.dim);
      c.title = r.dim + ": " + ESTADOS[estado].texto;
      c.appendChild(el("span", "solo-lector", ": " + ESTADOS[estado].texto));
      piezas.push(c);
    });
    resumen.replaceChildren.apply(resumen, piezas);
  }

  /* Una rúbrica que no se pudo pintar no puede quedar en verde con los datos anteriores. */
  function rubricaSinConfirmar() {
    Object.keys(filasRubrica).forEach(function (dim) {
      var f = filasRubrica[dim];
      f.fila.dataset.estado = "no_comprobado";
      f.estado.replaceChildren(chipEstado("no_comprobado"));
    });
    $("torre-resumen").replaceChildren(el("span", "torre-resumen-txt", "Rúbrica: no se pudo mostrar; nada se da por verificado"));
  }

  /* ---------- conexión ---------- */
  var conexion = "vivo", ultimo = null, sinConexionDesde = null, detenido = false, temporizador = null;
  function pintarConexion() {
    var vivo = $("en-vivo"), aviso = $("torre-aviso");
    vivo.classList.add("vivo");
    $("contenido").classList.toggle("desactualizado", conexion !== "vivo");
    if (conexion === "vivo") {
      vivo.dataset.estado = "vivo"; vivo.textContent = "En vivo, cada 5 s"; aviso.hidden = true;
    } else if (conexion === "caido") {
      var desde = "Sin conexión desde " + hora(sinConexionDesde);
      vivo.dataset.estado = "caido"; vivo.textContent = desde;
      aviso.textContent = desde + ". Lo que ves es el último dato recibido y nada se da por verificado.";
      aviso.hidden = false;
    } else {
      vivo.dataset.estado = "caido"; vivo.textContent = "Sesión terminada";
      aviso.replaceChildren(el("span", "", "Tu sesión terminó. Lo que ves es el último dato recibido y nada se da por verificado. "), enlace(ENTRAR, "Ingresar de nuevo"));
      aviso.hidden = false;
    }
    if (!ultimo) return;
    var p = ultimo;
    seccion("lectura", function () { pintarLectura(p); }, function () { $("torre-lectura").dataset.tono = "sin-datos"; });
    seccion("rúbrica", function () { pintarRubrica(p.rubrica); }, rubricaSinConfirmar);
  }
  function cambiarConexion(nueva) {
    if (nueva === conexion) return;
    conexion = nueva;
    sinConexionDesde = nueva === "caido" ? new Date() : null;
    if (nueva === "vivo" && window.CofrialEstados) CofrialEstados.anunciar("Conexión recuperada.");      // la pérdida la anuncia el aviso, con role="alert"
    pintarConexion();
  }
  function sesionTerminada() { detenido = true; clearTimeout(temporizador); cambiarConexion("sesion"); }
  function agendar() { clearTimeout(temporizador); if (!detenido && !document.hidden) temporizador = setTimeout(sondear, SONDEO_MS); }
  function sondear() {
    if (detenido || document.hidden) return;
    var control = new AbortController(), plazo = setTimeout(function () { control.abort(); }, ESPERA_MS);
    /* redirect "manual": si la sesión venció, el servidor redirige al login y este no debe pintarse dentro de la Torre. */
    fetch("/torre/pulso/", {redirect: "manual", credentials: "same-origin", headers: {"Accept": "application/json"}, signal: control.signal}).then(function (r) {
      if (r.type === "opaqueredirect" || r.status === 401 || r.status === 403) { sesionTerminada(); return null; }
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (p) {                   // con dos funciones: un error al pintar no llega a la de red
      if (!p) return;
      cambiarConexion("vivo");
      render(p);
    }, function () {
      cambiarConexion("caido");
    }).catch(function (e) {
      console.error("Torre: no se pudo pintar el pulso", e);
    }).then(function () { clearTimeout(plazo); agendar(); });
  }

  /* ---------- pintado ---------- */
  function render(p) {
    ultimo = p;
    if (p.antes) seccion("antes", function () { pintarAntes(p.antes); });
    seccion("clientes del mapa", function () { siCambio("clientes", p.clientes_mapa, pintarClientes); });
    seccion("camiones", function () { pintarCamiones(p.camiones); });
    seccion("leyenda", function () { pintarLeyenda(p); });
    seccion("clientes frecuentes", function () { siCambio("frecuentes", p.frecuentes, function (f) { frecuentes = f; opcionesFiltro(); pintarFrecuentes(); }); });
    seccion("ahora", function () { pintarAhora(p.ahora); });
    seccion("embudo", function () { siCambio("embudo", p.embudo, pintarEmbudo); });
    seccion("front-office y back-office", function () { pintarFrontBack(p); });
    pintarConexion();
  }

  function iniciar() {
    var inicial = JSON.parse($("pulso-inicial").textContent);
    $("filtro-segmento").addEventListener("change", pintarFrecuentes);
    seccion("mapa", function () { iniciarMapa(inicial.base); });
    render(inicial);
    document.addEventListener("visibilitychange", function () {
      if (detenido) return;
      clearTimeout(temporizador);
      if (!document.hidden) sondear();
    });
    agendar();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();

  return {render: render};
})();
