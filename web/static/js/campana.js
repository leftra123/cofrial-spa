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
        var ir = document.createElement("a"); ir.className = "btn-sec"; ir.href = a.accion.url; ir.textContent = a.accion.texto; ab.appendChild(ir); li.appendChild(ab);
      }
      /* «Estamos afuera»: mientras el camión sigue en la puerta (el servidor cambia el texto cuando ya no), el aviso trae las dos respuestas */
      if (a.tipo === "puerta" && /^Estamos afuera/.test(a.texto) && window.CofrialEntrega) {
        var ac = document.createElement("div"); ac.className = "campana-acciones";
        var si = document.createElement("button"); si.type = "button"; si.className = "btn"; si.textContent = "Revisar y recibir";
        si.addEventListener("click", function (e) { e.stopPropagation(); panel.hidden = true; btn.setAttribute("aria-expanded", "false"); CofrialEntrega.revisar(a.orden_id); });
        var no = document.createElement("button"); no.type = "button"; no.className = "btn-sec"; no.textContent = "No pude recibirlo";
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
      it.appendChild(cuerpo); it.appendChild(ac);
      if (!llego) { var x = nodo("button", "al-cerrar", "×"); x.type = "button"; x.setAttribute("aria-label", "Cerrar este aviso"); x.addEventListener("click", function () { cerrar(a.id); }); it.appendChild(x); }
      banner.appendChild(it);
    });
    var primero = lista[0];
    document.title = (pide(primero) ? "¡Tu pedido llegó! · " : "Tu pedido está por llegar · ") + tituloBase;
    lista.forEach(function (a) { if (anunciados.indexOf(a.id) < 0) { anunciados.push(a.id); try { if (navigator.vibrate && (!navigator.userActivation || navigator.userActivation.hasBeenActive)) navigator.vibrate([200, 100, 200]); } catch (e) {} } });
  }
  function programar() { clearTimeout(timer); timer = setTimeout(cargar, actuales.some(function (a) { return a.destacado; }) ? 5000 : 15000); }      // con el camión cerca, cada 5 s

  function aviso(a) {
    var t = document.createElement("div"); t.className = "toast t-" + a.tipo;
    var b = document.createElement("a"); b.href = "/pedidos/" + a.orden_id + "/"; b.textContent = a.texto; t.appendChild(b);
    toasts.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 400); }, a.destacado ? 15000 : 8000);
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
        primera = false; pintar(); pintarBanner(); programar();
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
