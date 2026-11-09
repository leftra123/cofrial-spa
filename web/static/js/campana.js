/* Cofrial SpA · campanita de avisos del cliente: salió, ventana de llegada, cerca y llegó.
   Consulta /api/avisos/ (solo trae lo de las órdenes de quien inició sesión). Lo ya visto se recuerda en este navegador.
   Los avisos que importan ahora (el camión está cerca; el camión llegó y espera tu respuesta) NO dependen de abrir la campanita: además de
   estar en la lista, salen como un banner fijo arriba de cualquier página, cambian el título de la pestaña y se consultan más seguido. */
(function () {
  var btn = document.getElementById("campana-btn"), panel = document.getElementById("campana-panel"), lista = document.getElementById("campana-lista"),
      n = document.getElementById("campana-n"), toasts = document.getElementById("toasts");
  if (!btn || !window.fetch) return;
  var CLAVE = "cofrial-avisos-vistos", vistos = [], primera = true, actuales = [];
  try { vistos = JSON.parse(localStorage.getItem(CLAVE) || "[]"); } catch (e) {}
  function guardar() { try { localStorage.setItem(CLAVE, JSON.stringify(vistos.slice(-200))); } catch (e) {} }
  function hora(iso) { return new Date(iso).toLocaleTimeString("es-CL", {hour: "2-digit", minute: "2-digit", hour12: false}); }
  var pide = CofrialEntrega.pide, contar = CofrialEntrega.contarAvisos;      // reglas del contador en entrega.js (una función pura, con prueba)
  var ICONOS = {salio: "Salió", ventana: "Llegada", cerca: "Cerca", puerta: "En la puerta", llego: "Entregado", no_concretada: "No concretada", rechazada: "Rechazado", frio: "Temperatura"};
  var MARCA = {
    mapa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
    doc: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h4"/></svg>',
    ok: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16 9.5"/></svg>',
    no: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>',
    chat: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a8 8 0 01-11.6 7.1L3 21l1.9-6.4A8 8 0 1121 12z"/></svg>',
    temp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14.5V5a2 2 0 014 0v9.5a4 4 0 11-4 0z"/></svg>',
    caja: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/></svg>'
  };
  function marcaDe(tipo) {
    if (tipo === "salio" || tipo === "ventana" || tipo === "cerca") return MARCA.mapa;
    if (tipo === "llego") return MARCA.doc;
    if (tipo === "no_concretada") return MARCA.chat;
    if (tipo === "frio") return MARCA.temp;
    if (tipo === "rechazada") return MARCA.no;
    return MARCA.caja;
  }
  function conMarca(el, svg) { el.insertAdjacentHTML("afterbegin", svg); }

  function datosDelPedido(a) {
    var p = a.pedido; if (!p) return "";
    var partes = [];
    if (p.documento) partes.push(p.documento.etiqueta);
    if (p.total_clp != null) partes.push("$" + Number(p.total_clp).toLocaleString("es-CL") + (p.con_iva ? " con IVA" : ""));
    return partes.join(" · ");
  }
  var VACIO = "Sin avisos por ahora. Te avisamos cuando tu pedido salga, esté cerca y llegue.", cargado = false, nota = document.getElementById("campana-nota");
  function mensaje(clase, texto) { lista.innerHTML = ""; var li = document.createElement("li"); li.className = clase; li.textContent = texto; lista.appendChild(li); return li; }
  function pintar() {
    if (!cargado) return;
    lista.setAttribute("aria-busy", "false");
    var cuenta = contar(actuales, vistos, Date.now());
    n.hidden = cuenta === 0; n.textContent = cuenta;
    btn.setAttribute("aria-label", cuenta ? "Avisos de tus pedidos: " + cuenta + " por atender" : "Avisos de tus pedidos");
    if (!actuales.length) { mensaje("campana-vacio", VACIO); return; }
    lista.innerHTML = "";
    actuales.slice().sort(function (x, y) { return pide(y) - pide(x); }).forEach(function (a) {          // lo que espera una respuesta va primero
      var li = document.createElement("li"); li.className = "campana-item" + (vistos.indexOf(a.id) < 0 ? " nuevo" : "");
      var enlace = document.createElement("a"); enlace.href = "/pedidos/" + a.orden_id + "/";
      var tipo = document.createElement("span"); tipo.className = "campana-tipo t-" + a.tipo; tipo.textContent = ICONOS[a.tipo] || "Aviso";
      var txt = document.createElement("span"); txt.className = "campana-txt"; txt.textContent = a.texto;
      var meta = datosDelPedido(a);          // lo que el pedido lleva de verdad: documento y monto, para no hacerlo abrir para saberlo
      if (meta) { var m = document.createElement("small"); m.className = "campana-meta"; m.textContent = meta; txt.appendChild(document.createElement("br")); txt.appendChild(m); }
      var h = document.createElement("time"); h.dateTime = a.cuando; h.textContent = hora(a.cuando);
      enlace.appendChild(tipo); enlace.appendChild(txt); enlace.appendChild(h); li.appendChild(enlace); lista.appendChild(li);
      /* Todo aviso trae su botón con una acción real (el servidor dice a qué pantalla lleva); el de «estamos afuera» trae las dos respuestas. */
      if (a.accion && !(a.tipo === "puerta" && pide(a))) {
        var ab = document.createElement("div"); ab.className = "campana-acciones";
        var ir = document.createElement("a"); ir.className = "btn"; ir.href = a.accion.url; ir.textContent = a.accion.texto; if (a.accion.texto === "Ver dónde va") ir.classList.add("campana-ir"); conMarca(ir, marcaDe(a.tipo)); ab.appendChild(ir); li.appendChild(ab);
      }
      /* «Estamos afuera»: mientras el camión sigue en la puerta (el servidor cambia el texto cuando ya no), el aviso trae las dos respuestas */
      if (a.tipo === "puerta" && /^Estamos afuera/.test(a.texto) && window.CofrialEntrega) {
        var ac = document.createElement("div"); ac.className = "campana-acciones campana-par";
        var si = document.createElement("button"); si.type = "button"; si.className = "btn"; si.textContent = "Revisar y recibir"; conMarca(si, MARCA.ok);
        si.addEventListener("click", function (e) { e.stopPropagation(); panel.hidden = true; btn.setAttribute("aria-expanded", "false"); CofrialEntrega.revisar(a.orden_id); });
        var no = document.createElement("button"); no.type = "button"; no.className = "btn-sec"; no.textContent = "No pude recibirlo"; conMarca(no, MARCA.no);
        no.addEventListener("click", function (e) { e.stopPropagation(); panel.hidden = true; btn.setAttribute("aria-expanded", "false"); CofrialEntrega.modal(a.orden_id); });
        ac.appendChild(si); ac.appendChild(no); li.appendChild(ac);
      }
    });
  }
  /* ---- Aviso destacado: banner fijo, título de la pestaña y vibración (una vez por aviso). ---- */
  var CERRADOS = "cofrial-aviso-cerrado", cerrados = [], anunciados = [], banner = null, tituloBase = document.title, timer = null;
  try { cerrados = JSON.parse(sessionStorage.getItem(CERRADOS) || "[]"); } catch (e) {}
  function cerrar(id) { cerrados.push(id); try { sessionStorage.setItem(CERRADOS, JSON.stringify(cerrados.slice(-50))); } catch (e) {} pintarBanner(); }
  function enSuPantalla(a) { return location.pathname.replace(/\/$/, "") === "/pedidos/" + a.orden_id; }      // la pantalla del pedido ya lo dice con todas sus letras
  function nodo(tag, clase, texto) { var n = document.createElement(tag); if (clase) n.className = clase; if (texto != null) n.textContent = texto; return n; }
  function pintarBanner() {
    var lista = actuales.filter(function (a) { return a.destacado && !enSuPantalla(a) && (pide(a) || cerrados.indexOf(a.id) < 0); })
      .sort(function (x, y) { return pide(y) - pide(x); }).slice(0, 2);
    if (!lista.length) { if (banner) { banner.remove(); banner = null; } document.title = tituloBase; return; }
    var contenedor = document.getElementById("contenido"); if (!contenedor) return;
    if (!banner) {
      banner = nodo("div", "aviso-llegada"); banner.id = "aviso-llegada"; banner.setAttribute("role", "status"); banner.setAttribute("aria-live", "polite");
      var cab = document.querySelector(".tb"); banner.style.setProperty("--al-top", (Math.min(cab ? cab.offsetHeight : 64, 120) + 8) + "px");
      contenedor.insertBefore(banner, contenedor.firstChild);
    }
    banner.innerHTML = "";
    lista.forEach(function (a) {
      var llego = pide(a), it = nodo("div", "aviso-llegada-item " + (llego ? "llego" : "cerca")), cuerpo = nodo("div", "al-texto");
      cuerpo.appendChild(nodo("b", "", llego ? "El camión llegó con tu pedido N.º " + a.orden_id : "Tu pedido N.º " + a.orden_id + " está por llegar"));
      cuerpo.appendChild(nodo("span", "", llego ? "Revisa lo que recibes y confírmanos si todo llegó bien. Si no respondes, lo damos por entregado en unos minutos."
        : "El camión está a menos de 2 km" + (a.minutos ? " (llega " + (a.minutos <= 1 ? "en cerca de un minuto" : "en unos " + a.minutos + " min") + ")" : "") + ". Deja a alguien listo para recibirlo."));
      var ac = nodo("div", "al-acciones");
      if (llego) { var r = nodo("button", "btn", "Revisar y recibir"); r.type = "button"; r.addEventListener("click", function () { CofrialEntrega.revisar(a.orden_id); }); ac.appendChild(r); }
      var ver = nodo("a", llego ? "btn-sec" : "btn", llego ? "Ver mi pedido" : "Ver dónde va"); ver.href = a.accion ? a.accion.url : "/pedidos/" + a.orden_id + "/"; ac.appendChild(ver);
      if (!llego) { var x = nodo("button", "al-cerrar", "×"); x.type = "button"; x.setAttribute("aria-label", "Cerrar este aviso"); x.addEventListener("click", function () { cerrar(a.id); }); ac.appendChild(x); }
      it.appendChild(cuerpo); it.appendChild(ac);
      banner.appendChild(it);
    });
    var primero = lista[0];
    document.title = (pide(primero) ? "¡Tu pedido llegó! · " : "Tu pedido está por llegar · ") + tituloBase;
    lista.forEach(function (a) { if (anunciados.indexOf(a.id) < 0) { anunciados.push(a.id); try { if (navigator.vibrate) navigator.vibrate([200, 100, 200]); } catch (e) {} } });
  }
  function programar() { clearTimeout(timer); timer = setTimeout(cargar, actuales.some(function (a) { return a.destacado; }) ? 5000 : 15000); }      // con el camión cerca, cada 5 s

  function aviso(a) {
    var t = document.createElement("div"); t.className = "toast t-" + a.tipo;
    var b = document.createElement("a"); b.href = "/pedidos/" + a.orden_id + "/"; b.textContent = a.texto; t.appendChild(b);
    toasts.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 400); }, a.destacado ? 15000 : 8000);
    if (window.CofrialPermisos) CofrialPermisos.notificar({id: a.id, texto: a.texto, url: a.accion ? a.accion.url : "/pedidos/" + a.orden_id + "/"});
  }
  /* Stock que el cliente esperaba: el número del pie de la campanita y un aviso cuando sube. La primera vez en este navegador solo se toma nota. */
  var CLAVE_STOCK = "cofrial-stock-n", pie = document.querySelector(".campana-pie");
  function stock(n) {
    if (n == null || !pie) return;
    var chip = pie.querySelector(".tb-n");
    if (n && !chip) { chip = document.createElement("span"); chip.className = "tb-n"; chip.title = "Productos que esperabas y ya tienen stock"; pie.appendChild(document.createTextNode(" ")); pie.appendChild(chip); }
    if (chip) { chip.textContent = n; chip.hidden = !n; }
    var antes = null;
    try { antes = JSON.parse(localStorage.getItem(CLAVE_STOCK)); localStorage.setItem(CLAVE_STOCK, JSON.stringify(n)); } catch (e) {}
    if (antes === null || n <= antes) return;
    var texto = n === 1 ? "Ya hay stock de un producto que esperabas." : "Ya hay stock de " + n + " productos que esperabas.";
    var t = document.createElement("div"); t.className = "toast";
    var b = document.createElement("a"); b.href = "/avisos/"; b.textContent = texto; t.appendChild(b);
    toasts.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 400); }, 8000);
    if (window.CofrialPermisos) CofrialPermisos.notificar({id: "stock:" + n, texto: texto, url: "/avisos/"});
  }
  /* Un fallo no se disfraza de «sin avisos»: si nunca se cargó, el panel lo dice y ofrece reintentar; si ya había avisos, se quedan con una nota de que no están al día. */
  function fallo() {
    if (nota) nota.hidden = false;
    if (cargado) return;
    lista.setAttribute("aria-busy", "false");
    var li = mensaje("campana-error", "No pudimos cargar tus avisos."), b = document.createElement("button");
    b.type = "button"; b.className = "btn-sec"; b.textContent = "Reintentar";
    b.addEventListener("click", function (e) { e.stopPropagation(); mensaje("campana-vacio cargando", "Cargando avisos…"); lista.setAttribute("aria-busy", "true"); cargar(); });
    li.appendChild(b);
  }
  function cargar() {
    fetch("/api/avisos/", {credentials: "same-origin", headers: {"Accept": "application/json"}})
      .then(function (r) { if (!r.ok) throw r; return r.json(); })
      .then(function (d) {
        cargado = true; if (nota) nota.hidden = true;
        var nuevos = d.avisos.filter(function (a) { return vistos.indexOf(a.id) < 0 && !actuales.some(function (x) { return x.id === a.id; }); });
        actuales = d.avisos;
        if (!primera) nuevos.forEach(aviso);          // avisa emergente solo lo que aparece mientras navegas
        primera = false; pintar(); pintarBanner(); stock(d.stock_n); programar();
      }).catch(function (e) { fallo(e); programar(); });
  }
  btn.addEventListener("click", function () {
    var abre = panel.hidden; panel.hidden = !abre; btn.setAttribute("aria-expanded", abre);
    if (abre) { actuales.forEach(function (a) { if (vistos.indexOf(a.id) < 0) vistos.push(a.id); }); guardar(); setTimeout(function () { n.textContent = contar(actuales, vistos, Date.now()); n.hidden = n.textContent === "0"; }, 600); }
    else pintar();
  });
  document.addEventListener("click", function (e) { if (!panel.hidden && !e.target.closest("#campana")) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); pintar(); } });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
  document.addEventListener("cofrial:entrega", function () { cargar(); });         // respondió «Estamos afuera»: el aviso se actualiza al tiro
  cargar();
})();
