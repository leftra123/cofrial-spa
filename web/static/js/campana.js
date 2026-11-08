/* Cofrial SpA · campanita de avisos del cliente: salió, ventana de llegada, cerca y llegó.
   Consulta /api/avisos/ (solo trae lo de las órdenes de quien inició sesión). Lo ya visto se recuerda en este navegador. */
(function () {
  var btn = document.getElementById("campana-btn"), panel = document.getElementById("campana-panel"), lista = document.getElementById("campana-lista"),
      n = document.getElementById("campana-n"), toasts = document.getElementById("toasts");
  if (!btn || !window.fetch) return;
  var CLAVE = "cofrial-avisos-vistos", vistos = [], primera = true, actuales = [];
  try { vistos = JSON.parse(localStorage.getItem(CLAVE) || "[]"); } catch (e) {}
  function guardar() { try { localStorage.setItem(CLAVE, JSON.stringify(vistos.slice(-200))); } catch (e) {} }
  function hora(iso) { return new Date(iso).toLocaleTimeString("es-CL", {hour: "2-digit", minute: "2-digit", hour12: false}); }
  var pide = CofrialEntrega.pide, contar = CofrialEntrega.contarAvisos;      // reglas del contador en entrega.js (una función pura, con prueba)
  var ICONOS = {salio: "Salió", ventana: "Llegada", cerca: "Cerca", puerta: "En la puerta", llego: "Entregado", no_concretada: "No concretada", frio: "Temperatura"};

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
      var h = document.createElement("time"); h.dateTime = a.cuando; h.textContent = hora(a.cuando);
      enlace.appendChild(tipo); enlace.appendChild(txt); enlace.appendChild(h); li.appendChild(enlace);
      if (a.documento && a.documento.orden_id === a.orden_id) {
        var doc = document.createElement("a"); doc.className = "campana-doc"; doc.href = "/pedidos/" + a.orden_id + "/#documentos";
        doc.textContent = a.documento.etiqueta + " N.º " + a.documento.folio + " de este pedido";
        li.appendChild(doc);
      }
      var acciones = a.acciones || (pide(a) ? [{id: "aceptar", etiqueta: "Recibí mi pedido"}, {id: "no_recibido", etiqueta: "No pude recibirlo", href: "/pedidos/" + a.orden_id + "/#entrega"}] : []);
      if (acciones.length) {
        var ac = document.createElement("div"); ac.className = "campana-acciones"; ac.setAttribute("aria-label", "Acciones del pedido N.º " + a.orden_id);
        acciones.forEach(function (accion) { ac.appendChild(botonDe(a.orden_id, accion)); });
        li.appendChild(ac);
      }
      lista.appendChild(li);
    });
  }
  function botonDe(ordenId, accion) {
    if (accion.id === "aceptar") {
      var f = document.createElement("form"); f.method = "post"; f.action = "/pedidos/" + ordenId + "/entrega/";
      var tok = document.querySelector("input[name=csrfmiddlewaretoken]");
      if (tok) f.appendChild(tok.cloneNode(true));
      var oculto = document.createElement("input"); oculto.type = "hidden"; oculto.name = "accion"; oculto.value = "aceptar"; f.appendChild(oculto);
      var b = document.createElement("button"); b.className = "btn"; b.textContent = accion.etiqueta;
      b.addEventListener("click", function (e) {
        if (!window.CofrialEntrega) return;
        e.preventDefault(); CofrialEntrega.aceptar(ordenId, b);
      });
      f.appendChild(b); return f;
    }
    var enlace = document.createElement("a"); enlace.className = accion.id === "aceptar" ? "btn" : "btn-sec"; enlace.href = accion.href || ("/pedidos/" + ordenId + "/");
    enlace.textContent = accion.etiqueta;
    if (accion.id === "no_recibido") enlace.addEventListener("click", function (e) {
      if (!window.CofrialEntrega) return;
      e.preventDefault(); panel.hidden = true; btn.setAttribute("aria-expanded", "false"); CofrialEntrega.modal(ordenId);
    });
    return enlace;
  }
  function aviso(a) {
    var t = document.createElement("div"); t.className = "toast t-" + a.tipo;
    var b = document.createElement("a"); b.href = "/pedidos/" + a.orden_id + "/"; b.textContent = a.texto; t.appendChild(b);
    toasts.appendChild(t); setTimeout(function () { t.classList.add("sale"); setTimeout(function () { t.remove(); }, 400); }, 8000);
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
        primera = false; pintar();
      }).catch(fallo);
  }
  btn.addEventListener("click", function () {
    var abre = panel.hidden; panel.hidden = !abre; btn.setAttribute("aria-expanded", abre);
    if (abre) { actuales.forEach(function (a) { if (vistos.indexOf(a.id) < 0) vistos.push(a.id); }); guardar(); setTimeout(function () { n.textContent = contar(actuales, vistos, Date.now()); n.hidden = n.textContent === "0"; }, 600); }
    else pintar();
  });
  document.addEventListener("click", function (e) { if (!panel.hidden && !e.target.closest("#campana")) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); pintar(); } });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); btn.focus(); } });
  document.addEventListener("cofrial:entrega", function () { cargar(); });         // respondió «Estamos afuera»: el aviso se actualiza al tiro
  cargar(); setInterval(cargar, 15000);
})();
