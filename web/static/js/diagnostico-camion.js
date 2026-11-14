/* Cofrial SpA · diagnóstico y acciones sobre un camión con alerta (panel de flota).
   Cada tarjeta con [data-diagnostico] pide /flota/camion/<id>/diagnostico/ y muestra qué le pasa al camión y qué se puede hacer:
   enviarlo a revisión (equipo de frío o sensor) y devolverlo a servicio. El texto lo escribe el código; si una IA gratuita responde, solo lo redacta.
   Una alerta no siempre es una ruptura de frío: un sensor que salta o se pega también la produce (o la oculta).
   Todo texto del servidor entra con textContent. Enviar a revisión exige confirmar y la hace una persona: nada se envía solo. */
(function () {
  "use strict";
  var CADA_MS = 15000, bloques = [], pedidoIA = {}, ocupado = false;
  function cookie(n) { var m = document.cookie.match(new RegExp("(?:^|; )" + n + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  function csrf() { var i = document.querySelector("[name=csrfmiddlewaretoken]"); return i ? i.value : cookie("csrftoken"); }
  function el(tag, clase, texto) { var e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; }

  function post(id, datos) {
    return fetch("/flota/camion/" + encodeURIComponent(id) + "/revision/", {method: "POST", credentials: "same-origin", headers: {"X-CSRFToken": csrf()}, body: new URLSearchParams(datos)})
      .then(function (r) { return r.json().then(function (j) { j._ok = r.ok; return j; }); });
  }

  function pintar(caja, d) {
    var espejo = caja.hasAttribute("data-atencion"), tarjeta = caja.closest("[data-camion], [data-foco]"), chip = tarjeta && tarjeta.querySelector('[data-campo="revision"]');
    if (chip) chip.hidden = !d.revision;
    var visible = d.estado !== "normal" || !!d.revision;
    caja.hidden = !visible;
    caja.textContent = "";
    if (!visible) return;
    caja.className = "diagnostico diag-" + (d.revision ? "revision" : d.estado);
    if (espejo) caja.hidden = false;
    var cab = el("div", "diag-cab"); cab.appendChild(el("b", null, (espejo ? d.camion + " · " : "") + (d.revision ? "En revisión técnica" : d.titulo)));
    if (!d.revision) cab.appendChild(el("span", "diag-origen", d.por_ia ? "Sugerencia de la IA" : "Sugerencia del sistema"));
    caja.appendChild(cab);
    if (d.revision) {
      caja.appendChild(el("p", null, "Enviado a revisión (" + d.revision.motivo + ") a las " + d.revision.desde + (d.revision.por ? " por " + d.revision.por : "") +
                          ". No se despachará hasta que vuelva a servicio."));
    } else {
      caja.appendChild(el("p", null, d.texto));
    }
    var acc = el("div", "acciones");
    if (d.accion) {
      var b = el("button", "btn", d.accion.texto); b.type = "button";
      b.addEventListener("click", function () {
        if (!confirm("¿" + d.accion.texto + " para " + d.camion + "? No se despachará hasta que vuelva a servicio. El viaje en curso sigue su camino.")) return;
        b.disabled = true;
        post(d.camion, {accion: "abrir", motivo: d.accion.motivo, confirmar: "1"}).then(function (r) { mensaje(caja, r._ok ? r.mensaje : (r.detail || "No se pudo enviar.")); refrescar(true); })
          .catch(function () { mensaje(caja, "Sin conexión con el servidor."); b.disabled = false; });
      });
      acc.appendChild(b);
    }
    if (d.revision && d.puede_actuar) {
      var v = el("button", "btn btn-sec", "Volver a servicio"); v.type = "button";
      v.addEventListener("click", function () {
        if (!confirm("¿Devolver " + d.camion + " a servicio? Podrá despacharse de nuevo.")) return;
        v.disabled = true;
        post(d.camion, {accion: "volver", confirmar: "1"}).then(function (r) { mensaje(caja, r._ok ? r.mensaje : (r.detail || "No se pudo.")); refrescar(true); })
          .catch(function () { mensaje(caja, "Sin conexión con el servidor."); v.disabled = false; });
      });
      acc.appendChild(v);
    }
    if (acc.childNodes.length) caja.appendChild(acc);
    var aviso = el("p", "diag-aviso"); aviso.setAttribute("role", "status"); aviso.hidden = true; caja.appendChild(aviso);
  }
  function mensaje(caja, texto) { var a = caja.querySelector(".diag-aviso"); if (a) { a.textContent = texto; a.hidden = false; } }

  /* «Requiere atención»: lo mismo que se ve en la tarjeta del camión, arriba junto al mapa, para no tener que bajar a buscarlo. */
  function copiarArriba(id, d) {
    var panel = document.getElementById("atencion"), lista = document.getElementById("atencion-lista");
    if (!panel || !lista) return;
    var copia = lista.querySelector('[data-atencion="' + id + '"]'), visible = d.estado !== "normal" || !!d.revision;
    if (!visible) { if (copia) copia.remove(); }
    else {
      if (!copia) { copia = el("div"); copia.setAttribute("data-atencion", id); lista.appendChild(copia); }
      pintar(copia, d);
    }
    panel.hidden = !lista.children.length;
    plegar(panel, lista);
  }
  /* Con más de 3 avisos (p. ej. varios camiones en revisión) se muestran 3 y un botón abre el resto: así la columna no se alarga. */
  function plegar(panel, lista) {
    var n = lista.children.length, extra = n - 3, b = panel.querySelector(".atencion-mas");
    if (extra <= 0) { lista.classList.remove("recortada"); if (b) b.remove(); return; }
    if (!b) {
      b = el("button", "enlace atencion-mas"); b.type = "button";
      b.addEventListener("click", function () { var r = lista.classList.toggle("recortada"); b.setAttribute("aria-expanded", r ? "false" : "true"); b.textContent = r ? b.dataset.abrir : "Ver menos"; });
      panel.appendChild(b); lista.classList.add("recortada");
    }
    b.dataset.abrir = "Ver los " + extra + " restantes";
    if (lista.classList.contains("recortada")) { b.textContent = b.dataset.abrir; b.setAttribute("aria-expanded", "false"); }
  }
  function idDe(caja) { var t = caja.closest("[data-camion], [data-camion-diag]"); return t && (t.dataset.camion || t.dataset.camionDiag); }
  function consultar(caja, ia) {
    var id = idDe(caja);
    if (!id) return Promise.resolve();
    return fetch("/flota/camion/" + encodeURIComponent(id) + "/diagnostico/?ia=" + (ia ? "1" : "0"), {credentials: "same-origin"}).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return;
      pintar(caja, d);
      copiarArriba(id, d);
      var clave = id + ":" + d.estado;
      if (!ia && d.estado !== "normal" && !d.por_ia && !pedidoIA[clave]) {            // el aviso aparece al instante con el texto del sistema; la IA lo mejora una vez por episodio
        pedidoIA[clave] = true;
        consultar(caja, true);
      }
      if (d.estado === "normal") Object.keys(pedidoIA).forEach(function (k) { if (k.indexOf(id + ":") === 0) delete pedidoIA[k]; });
    }).catch(function () {});
  }

  function refrescar(ya) {
    if (ocupado && !ya) return;
    ocupado = true;
    var activos = bloques.filter(function (c) { return !c.closest("[data-guardado]"); });          // los camiones guardados en la base no se consultan cada 15 s
    var cadena = Promise.resolve();
    activos.forEach(function (c) { cadena = cadena.then(function () { return consultar(c, false); }); });
    cadena.then(function () { ocupado = false; }, function () { ocupado = false; });
  }

  /* El pin del mapa y el aviso del mapa llevan hasta aquí: se muestra la tarjeta del camión (aunque estuviera guardada) y se destaca. */
  window.CofrialDiagnostico = {
    abrir: function (id) {
      var t = document.querySelector('#vehiculos [data-camion="' + id + '"]');
      if (!t) return;
      var det = document.getElementById("vehiculos-det"); if (det) det.open = true;      // las tarjetas viven en un bloque plegado: se abre para mostrarla
      t.removeAttribute("data-guardado");
      t.scrollIntoView({behavior: "smooth", block: "center"});
      t.classList.add("destacada"); window.setTimeout(function () { t.classList.remove("destacada"); }, 2400);
      var caja = t.querySelector("[data-diagnostico]"); if (caja) consultar(caja, false);
    }
  };

  function iniciar() {
    bloques = Array.prototype.slice.call(document.querySelectorAll("[data-diagnostico]"));
    if (!bloques.length) return;
    refrescar(true);
    window.setInterval(refrescar, CADA_MS);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
})();
