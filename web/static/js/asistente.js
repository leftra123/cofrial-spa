/* Cofrial SpA · asistente de IA de la tienda. Solo lectura: pregunta al servidor (/api/asistente/), que arma el contexto con los datos de
   la sesión y deja que el modelo redacte. Todo el texto se inserta como texto (textContent), nunca como HTML. */
(function () {
  var raiz = document.getElementById("asistente");
  if (!raiz || !window.fetch) { if (raiz) raiz.hidden = true; return; }
  var btn = document.getElementById("asistente-btn"), panel = document.getElementById("asistente-panel"), log = document.getElementById("asistente-log"),
      form = document.getElementById("asistente-form"), entrada = document.getElementById("asistente-in"), enviar = document.getElementById("asistente-enviar"),
      sug = document.getElementById("asistente-sug"), cerrar = document.getElementById("asistente-cerrar");
  var token = raiz.querySelector("[name=csrfmiddlewaretoken]").value, ocupado = false, saludado = false;
  var SUGERENCIAS = {
    producto: ["¿Cuánto cuesta este producto?", "¿Hay stock?", "¿A qué temperatura se conserva?"],
    pedido: ["¿En qué estado está este pedido?", "¿Cuándo llega?", "¿La temperatura va bien?"],
    carrito: ["¿Cuál es el estado de mi último pedido?", "¿Qué hago si algo no tiene stock?"],
    catalogo: ["¿Cuánto cuesta el lomo vetado?", "¿Qué productos están sin stock?", "¿Cuál es el estado de mi último pedido?"]
  };

  function burbuja(texto, quien) {
    var d = document.createElement("div"); d.className = "as-msg as-" + quien; d.textContent = texto;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  function abrir() {
    panel.hidden = false; btn.setAttribute("aria-expanded", "true"); raiz.classList.add("abierto");
    if (!saludado) {
      saludado = true; burbuja("Hola, soy el asistente de IA de Cofrial. Te ayudo con precios, stock, conservación de productos y el estado de tus pedidos.", "bot");
      (SUGERENCIAS[raiz.dataset.pagina] || SUGERENCIAS.catalogo).forEach(function (t) {
        var b = document.createElement("button"); b.type = "button"; b.className = "as-chip"; b.textContent = t;
        b.addEventListener("click", function () { preguntar(t); }); sug.appendChild(b);
      });
    }
    setTimeout(function () { entrada.focus(); }, 30);
  }
  function cerrarPanel() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); raiz.classList.remove("abierto"); btn.focus(); }
  btn.addEventListener("click", function () { if (panel.hidden) abrir(); else cerrarPanel(); });
  cerrar.addEventListener("click", cerrarPanel);
  raiz.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { e.stopPropagation(); cerrarPanel(); } });

  function acciones(lista) {
    if (!lista || !lista.length) return;
    var caja = document.createElement("div"); caja.className = "as-acciones";
    lista.forEach(function (a) {
      if (a.tipo !== "avisar") return;
      var b = document.createElement("button"); b.type = "button"; b.className = "as-accion"; b.textContent = a.etiqueta;
      b.addEventListener("click", function () {
        b.disabled = true; b.textContent = "Guardando…";
        var f = new FormData(); f.append("producto", a.producto_id); f.append("cantidad", "1"); f.append("volver", "/avisos/"); f.append("csrfmiddlewaretoken", token);
        fetch("/avisos/pedir/", {method: "POST", body: f, credentials: "same-origin"}).then(function (r) {
          if (!r.ok) throw new Error(r.status);
          b.remove(); burbuja("Listo: te avisaremos cuando haya stock. Lo verás en «Avisos» de la barra.", "bot");
        }).catch(function () { b.disabled = false; b.textContent = a.etiqueta; burbuja("No pude guardar el aviso. Inténtalo otra vez en un momento.", "bot"); });
      });
      caja.appendChild(b);
    });
    if (caja.children.length) { log.appendChild(caja); log.scrollTop = log.scrollHeight; }
  }

  function preguntar(texto) {
    texto = (texto || "").trim(); if (!texto || ocupado) return;
    ocupado = true; entrada.value = ""; entrada.disabled = true; enviar.disabled = true; sug.hidden = true;
    burbuja(texto, "yo"); log.setAttribute("aria-busy", "true");
    var pensando = null, aparece = setTimeout(function () {                      // el indicador aparece solo si tarda más de 300 ms
      pensando = burbuja("", "bot"); pensando.classList.add("as-pensando"); pensando.setAttribute("aria-label", "El asistente está pensando");
      pensando.innerHTML = '<span class="as-punto"></span><span class="as-punto"></span><span class="as-punto"></span>';
    }, 300);
    var ctl = window.AbortController ? new AbortController() : null, corte = setTimeout(function () { if (ctl) ctl.abort(); }, 14000);
    fetch(raiz.dataset.url, {method: "POST", credentials: "same-origin", signal: ctl ? ctl.signal : undefined,
      headers: {"Content-Type": "application/json", "X-CSRFToken": token},
      body: JSON.stringify({mensaje: texto, producto_id: raiz.dataset.producto || null, orden_id: raiz.dataset.orden || null})})
      .then(function (r) { return r.json().catch(function () { return {respuesta: "No pude leer la respuesta del asistente."}; }); })
      .then(function (d) { fin(); burbuja(d.respuesta || "No tengo una respuesta ahora.", "bot"); acciones(d.acciones); })
      .catch(function () { fin(); burbuja("No pude conectar con el asistente. Revisa tu conexión e inténtalo de nuevo.", "bot"); });
    function fin() {
      clearTimeout(aparece); clearTimeout(corte); if (pensando) pensando.remove();
      ocupado = false; entrada.disabled = false; enviar.disabled = false; log.removeAttribute("aria-busy"); entrada.focus();
    }
  }
  form.addEventListener("submit", function (e) { e.preventDefault(); preguntar(entrada.value); });
})();
