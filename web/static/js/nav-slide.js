/** Navegación slide Catálogo / Mis pedidos / Carrito: caché, doble panel y precarga. */
(function () {
  var CACHE_MS = 120000;
  /** «Mis pedidos» cambia con cada entrega: se guarda poco para no mostrar estados viejos. */
  var CACHE_PEDIDOS_MS = 10000;
  /** Tiempo máximo esperando imágenes antes del slide (alineado a animación calmada). */
  var MEDIA_MS = 1200;
  /** Pausa breve con skeleton montado, antes del crossfade. */
  var PRE_SLIDE_MS = 120;
  var RUTAS = [
    { pref: "/catalogo/", idx: 0 },
    { pref: "/pedidos/", idx: 1 },
    { pref: "/carrito/", idx: 2 },
  ];
  var SCRIPTS_FIJOS = /estados\.js|tienda\.js|nav-slide\.js|entrega\.js|campana\.js|tema_js|mercadopago\.com\/js\/v2|mp-brick\.js/;
  var cache = Object.create(null);
  var ocupado = false;
  /** Último destino pedido durante una transición: se abre al terminar, en vez de perder el clic. */
  var pendiente = null;
  /** Dirección de la página en pantalla. Puede diferir de location mientras dura una transición. */
  var mostrada = location.pathname + location.search;

  function reducido() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function duracionSlideMs() {
    var raw = getComputedStyle(document.documentElement).getPropertyValue("--nav-slide-dur").trim();
    if (!raw) return 380;
    if (raw.indexOf("ms") !== -1) return parseFloat(raw) || 720;
    if (raw.indexOf("s") !== -1) return (parseFloat(raw) || 0.38) * 1000;
    return parseFloat(raw) || 380;
  }

  function pausa(ms) {
    return new Promise(function (res) {
      window.setTimeout(res, ms);
    });
  }

  function claveUrl(url) {
    return (url || "").split("?")[0];
  }

  function indiceRuta(path) {
    for (var i = 0; i < RUTAS.length; i++) {
      if (path.indexOf(RUTAS[i].pref) === 0) return RUTAS[i].idx;
    }
    return -1;
  }

  function enlaceSlide(a) {
    return a && a.hasAttribute("data-nav-slide") && a.href;
  }

  function parseHtml(html) {
    return new DOMParser().parseFromString(html, "text/html");
  }

  function vigenciaMs(url) {
    return claveUrl(url).indexOf("/pedidos/") === 0 ? CACHE_PEDIDOS_MS : CACHE_MS;
  }

  function guardarCache(url, html) {
    cache[url] = { html: html, doc: parseHtml(html), t: Date.now() };
    return cache[url];
  }

  function obtenerPagina(url) {
    var hit = cache[url];
    if (hit && Date.now() - hit.t < vigenciaMs(url)) return Promise.resolve(hit);
    return fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch", Accept: "text/html" },
    })
      .then(function (r) {
        if (!r.ok) throw new Error("nav");
        return r.text();
      })
      .then(function (html) {
        return guardarCache(url, html);
      });
  }

  function invalidar(pref) {
    Object.keys(cache).forEach(function (url) {
      if (claveUrl(url) === claveUrl(pref)) delete cache[url];
    });
  }

  function precargarVecinas() {
    var actual = claveUrl(location.pathname);
    RUTAS.forEach(function (r) {
      if (r.pref === actual) return;
      obtenerPagina(r.pref).catch(function () {});
    });
  }

  function colocarIndicador(enlace) {
    var nav = document.querySelector(".tb-nav");
    var ind = document.getElementById("tb-nav-ind");
    if (!nav || !ind) return;
    if (!enlace || !enlace.hasAttribute("data-nav-slide")) {
      ind.hidden = true;
      return;
    }
    var nr = nav.getBoundingClientRect();
    var r = enlace.getBoundingClientRect();
    /* En móvil el menú se desliza de lado y «Carrito» queda cortado al borde: la pestaña elegida se trae a la vista.
       La raya se mide después, porque mover el menú cambia dónde cae el enlace. */
    if (nav.scrollWidth > nav.clientWidth) {
      if (r.right > nr.right - 8) nav.scrollLeft += r.right - nr.right + 8;
      else if (r.left < nr.left + 8) nav.scrollLeft -= nr.left + 8 - r.left;
      r = enlace.getBoundingClientRect();
    }
    ind.hidden = false;
    ind.removeAttribute("hidden");
    ind.style.left = r.left - nr.left + nav.scrollLeft + "px";
    ind.style.width = r.width + "px";
  }

  function marcarNav(path) {
    document.querySelectorAll(".tb-nav a[data-nav-slide]").forEach(function (a) {
      var href = a.getAttribute("href") || "";
      var on =
        (href === "/catalogo/" && path.indexOf("/catalogo/") === 0) ||
        (href === "/pedidos/" && path.indexOf("/pedidos/") === 0) ||
        (href === "/carrito/" && path.indexOf("/carrito/") === 0);
      a.classList.toggle("activo", on);
      if (on && href === "/catalogo/") a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    colocarIndicador(document.querySelector(".tb-nav a[data-nav-slide].activo"));
  }

  function sincronizarCarrito(doc) {
    if (!window.CofrialTienda || !doc) return;
    var n = doc.querySelector("[data-carrito-n]");
    var val = n && !n.hidden ? parseInt(n.textContent, 10) || 0 : 0;
    window.CofrialTienda.contador(val);
  }

  function reemplazarExtras(doc) {
    document.body.classList.remove("mp-modal-abierto", "mp-modal-saliendo");
    var modalViejo = document.getElementById("mp-pago-modal");
    if (modalViejo) modalViejo.remove();
    var modalNuevo = doc.getElementById("mp-pago-modal");
    if (modalNuevo) document.body.appendChild(modalNuevo.cloneNode(true));

    var cfgViejo = document.getElementById("mp-brick-cfg");
    if (cfgViejo) cfgViejo.remove();
    var cfgNuevo = doc.getElementById("mp-brick-cfg");
    if (cfgNuevo) document.body.appendChild(cfgNuevo.cloneNode(true));

    var dock = document.getElementById("dock-asistente");
    var dockN = doc.getElementById("dock-asistente");
    if (dock && dockN) dock.innerHTML = dockN.innerHTML;
  }

  function scriptOmitido(src) {
    if (!src) return false;
    if (/mercadopago\.com\/js\/v2/.test(src)) return typeof MercadoPago !== "undefined";
    if (/mp-brick\.js/.test(src)) return !!window.cofrialMpBrick;
    return SCRIPTS_FIJOS.test(src);
  }

  function scriptInlineOmitido(text, id) {
    if (id === "cofrial-tema-js") return !!(window.CofrialTema && window.CofrialTema.iniciado);
    if (window.CofrialTema && window.CofrialTema.iniciado && text && /data-tema-btn/.test(text)) return true;
    return false;
  }

  function reemplazarScriptsPagina(doc) {
    document.querySelectorAll("script[data-pagina-dinamica]").forEach(function (s) {
      s.remove();
    });
    doc.body.querySelectorAll("script").forEach(function (s) {
      var src = s.getAttribute("src") || "";
      var id = s.getAttribute("id") || "";
      var tipo = (s.getAttribute("type") || "").toLowerCase();
      if (tipo && tipo !== "text/javascript" && tipo !== "application/javascript" && tipo !== "module") return;
      if (src && scriptOmitido(src)) return;
      if (!src && scriptInlineOmitido(s.textContent, id)) return;
      if (!src && !s.textContent.trim()) return;
      if (id && document.getElementById(id)) return;
      var nu = document.createElement("script");
      if (id) nu.id = id;
      if (s.type) nu.type = s.type;
      if (src) {
        nu.src = src;
        nu.async = false;
      } else {
        nu.textContent = s.textContent;
      }
      nu.setAttribute("data-pagina-dinamica", "1");
      document.body.appendChild(nu);
    });
  }

  function cargarScript(url) {
    return new Promise(function (resolve) {
      if (!url) {
        resolve();
        return;
      }
      var s = document.createElement("script");
      s.src = url;
      s.async = false;
      s.onload = function () {
        resolve();
      };
      s.onerror = function () {
        resolve();
      };
      document.body.appendChild(s);
    });
  }

  function ensureMercadoPago(doc) {
    var sdk = doc && doc.querySelector('script[src*="mercadopago.com/js/v2"]');
    var brick = doc && doc.querySelector('script[src*="mp-brick.js"]');
    var sdkUrl = sdk ? sdk.getAttribute("src") : "https://sdk.mercadopago.com/js/v2";
    var brickUrl = brick ? brick.getAttribute("src") : null;
    var pasos = Promise.resolve();
    if (typeof MercadoPago === "undefined") {
      pasos = pasos.then(function () {
        return cargarScript(sdkUrl);
      });
    }
    if (!window.cofrialMpBrick && brickUrl) {
      pasos = pasos.then(function () {
        return cargarScript(brickUrl);
      });
    }
    return pasos;
  }

  function arrancarCarrito(doc, pathDestino) {
    var path = pathDestino || location.pathname;
    if (claveUrl(path).indexOf("/carrito/") !== 0) return Promise.resolve();
    if (!doc.getElementById("mp-brick-cfg")) return Promise.resolve();      // B2B y cobro simulado no usan Mercado Pago
    return ensureMercadoPago(doc).then(function () {
      if (window.cofrialMpBrick && window.cofrialMpBrick.arrancarDesdeDom) {
        window.cofrialMpBrick.arrancarDesdeDom();
      }
    });
  }

  function prepararMedios(root) {
    var imgs = root.querySelectorAll("img[src]");
    if (!imgs.length) return Promise.resolve();
    var tareas = Array.prototype.map.call(imgs, function (img) {
      if (img.complete && img.naturalWidth > 0) {
        return img.decode ? img.decode().catch(function () {}) : Promise.resolve();
      }
      return new Promise(function (res) {
        img.addEventListener("load", res, { once: true });
        img.addEventListener("error", res, { once: true });
      });
    });
    return Promise.race([
      Promise.all(tareas),
      new Promise(function (res) {
        window.setTimeout(res, MEDIA_MS);
      }),
    ]);
  }

  function crearPanelEntrante(doc) {
    var fuente = doc.getElementById("t-pagina");
    if (!fuente) return null;
    var panel = document.createElement("div");
    panel.className = "t-pagina t-pagina-siguiente t-pagina-entrante";
    panel.innerHTML = fuente.innerHTML;
    panel.setAttribute("aria-hidden", "true");
    return panel;
  }

  var SKELETON_RUTAS = {
    "/catalogo/": { id: "nav-skeleton-catalogo", etiqueta: "Cargando catálogo" },
    "/pedidos/": { id: "nav-skeleton-pedidos", etiqueta: "Cargando mis pedidos" },
    "/carrito/": { id: "nav-skeleton-carrito", etiqueta: "Cargando carrito" },
  };

  function rutaConSkeleton(path) {
    return Object.prototype.hasOwnProperty.call(SKELETON_RUTAS, path);
  }

  function crearPanelSkeleton(path) {
    var cfg = SKELETON_RUTAS[path];
    if (!cfg) return null;
    var tpl = document.getElementById(cfg.id);
    if (!tpl || !tpl.content) return null;
    var panel = document.createElement("div");
    panel.className = "t-pagina t-pagina-siguiente t-pagina-entrante t-pagina-skeleton";
    panel.appendChild(tpl.content.cloneNode(true));
    panel.setAttribute("aria-hidden", "true");
    panel.setAttribute("aria-busy", "true");
    panel.setAttribute("aria-label", cfg.etiqueta);
    return panel;
  }

  function navegarConSkeleton(escena, actual, path, url, fetchPromise, finalizar) {
    var entranteSk = crearPanelSkeleton(path);
    if (!entranteSk) return null;
    escena.appendChild(entranteSk);
    entranteSk.style.visibility = "hidden";
    void entranteSk.offsetHeight;
    var docRef = null;
    var fundido = pausa(PRE_SLIDE_MS).then(function () {
      return lanzarFundido(escena, actual, entranteSk);
    });
    var contenido = fetchPromise.then(function (paquete) {
      docRef = paquete.doc;
      if (!poblarPanelDesdeDoc(entranteSk, docRef)) throw new Error("nav");
      return prepararMedios(entranteSk);
    });
    return Promise.all([fundido, contenido])
      .then(function () {
        return commitPanel(escena, entranteSk, docRef, path);
      })
      .then(function () {
        return finalizar(true, docRef, path);
      })
      .catch(function () {
        window.location.assign(url);
        return finalizar(false, null, path);
      });
  }

  function poblarPanelDesdeDoc(panel, doc) {
    var fuente = doc.getElementById("t-pagina");
    if (!fuente || !panel) return false;
    panel.innerHTML = fuente.innerHTML;
    panel.classList.remove("t-pagina-skeleton");
    panel.removeAttribute("aria-busy");
    panel.removeAttribute("aria-label");
    return true;
  }

  function lanzarFundido(escena, actual, entrante) {
    entrante.style.visibility = "";
    var alto = Math.max(actual.offsetHeight, entrante.offsetHeight, escena.offsetHeight);
    escena.style.minHeight = alto + "px";
    actual.classList.add("t-pagina-saliente");
    escena.classList.add("t-fundir", "t-pre");
    void escena.offsetWidth;
    escena.classList.remove("t-pre");
    return esperarTransicion(entrante);
  }

  function esperarTransicion(panel) {
    return new Promise(function (res) {
      if (!panel || reducido()) {
        res();
        return;
      }
      var fin = false;
      function listo(ev) {
        if (ev && ev.target !== panel) return;
        if (ev && ev.propertyName && ev.propertyName !== "opacity") return;
        if (fin) return;
        fin = true;
        panel.removeEventListener("transitionend", listo);
        res();
      }
      panel.addEventListener("transitionend", listo);
      window.setTimeout(function () {
        if (!fin) listo();
      }, duracionSlideMs() + 120);
    });
  }

  function limpiarEscena(escena) {
    escena.classList.remove("t-fundir", "t-pre");
    escena.style.minHeight = "";
  }

  function commitPanel(escena, entrante, doc, path) {
    var saliente = escena.querySelector(".t-pagina-saliente");
    if (saliente) saliente.remove();
    entrante.classList.remove("t-pagina-siguiente", "t-pagina-entrante", "t-pagina-saliente");
    entrante.removeAttribute("aria-hidden");
    entrante.id = "t-pagina";
    entrante.style.transform = "";
    entrante.style.filter = "";
    entrante.style.opacity = "";
    limpiarEscena(escena);
    reemplazarExtras(doc);
    reemplazarScriptsPagina(doc);
    var tit = doc.querySelector("title");
    if (tit) document.title = tit.textContent;
    marcarNav(path);
    sincronizarCarrito(doc);
    if (window.CofrialTienda && window.CofrialTienda.iniciarCant) {
      window.CofrialTienda.iniciarCant(entrante);
    }
    window.scrollTo(0, 0);
    // Sin esperar: la pantalla ya cambió y un SDK externo lento no debe bloquear las pestañas.
    arrancarCarrito(doc, path).then(function () {
      precargarVecinas();
    });
  }

  function aplicarInstantaneo(doc, path) {
    var actual = document.getElementById("t-pagina");
    var fuente = doc.getElementById("t-pagina");
    if (!actual || !fuente) return false;
    actual.innerHTML = fuente.innerHTML;
    reemplazarExtras(doc);
    reemplazarScriptsPagina(doc);
    var tit = doc.querySelector("title");
    if (tit) document.title = tit.textContent;
    marcarNav(path);
    sincronizarCarrito(doc);
    if (window.CofrialTienda && window.CofrialTienda.iniciarCant) {
      window.CofrialTienda.iniciarCant(actual);
    }
    window.scrollTo(0, 0);
    arrancarCarrito(doc, path);
    return true;
  }

  function irPagina(url, dir, opciones) {
    opciones = opciones || {};
    if (ocupado) {
      pendiente = { url: url, dir: dir, opciones: opciones };
      return Promise.resolve(false);
    }
    var escena = document.getElementById("t-pagina-escena");
    var actual = document.getElementById("t-pagina");
    if (!escena || !actual || !window.fetch) return Promise.resolve(false);

    ocupado = true;
    document.body.classList.add("t-nav-animando");
    var path = claveUrl(url);
    var fetchPromise = obtenerPagina(url);

    function finalizar(ok, doc, pathCommit) {
      // Con «atrás» pendiente el navegador ya cambió la dirección: agregar esta entrada la desordenaría.
      var volviendo = pendiente && pendiente.opciones.push === false;
      if (ok && opciones.push !== false && !volviendo) {
        history.pushState({ navSlide: true, idx: indiceRuta(pathCommit) }, "", url);
      }
      if (ok) mostrada = url;
      ocupado = false;
      document.body.classList.remove("t-nav-animando");
      if (ok) abrirPendiente();
      else pendiente = null;
      return ok;
    }

    if (!reducido() && rutaConSkeleton(path)) {
      var navSk = navegarConSkeleton(escena, actual, path, url, fetchPromise, finalizar);
      if (navSk) return navSk;
    }

    return fetchPromise
      .then(function (paquete) {
        var doc = paquete.doc;
        if (reducido()) {
          if (!aplicarInstantaneo(doc, path)) throw new Error("nav");
          return true;
        }

        var entrante = crearPanelEntrante(doc);
        if (!entrante) throw new Error("nav");

        escena.appendChild(entrante);
        entrante.style.visibility = "hidden";

        return Promise.all([prepararMedios(entrante), pausa(PRE_SLIDE_MS)]).then(function () {
          return lanzarFundido(escena, actual, entrante);
        }).then(function () {
          return commitPanel(escena, entrante, doc, path);
        }).then(function () {
          return true;
        });
      })
      .catch(function () {
        window.location.assign(url);
        return false;
      })
      .then(function (ok) {
        return finalizar(ok, null, path);
      });
  }

  function abrirPendiente() {
    var p = pendiente;
    pendiente = null;
    if (!p || p.url === mostrada) return;
    var enlace = document.querySelector('.tb-nav a[data-nav-slide][href="' + claveUrl(p.url) + '"]');
    if (enlace) colocarIndicador(enlace);
    irPagina(p.url, p.dir, p.opciones);
  }

  function initIndicador() {
    marcarNav(location.pathname);
    window.addEventListener("resize", function () {
      colocarIndicador(document.querySelector(".tb-nav a[data-nav-slide].activo"));
    });
  }

  var nav = document.querySelector(".tb-nav");
  if (nav) {
    nav.addEventListener("click", function (ev) {
      var a = ev.target.closest("a");
      if (!enlaceSlide(a)) return;
      if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      var destino = new URL(a.href, location.origin);
      if (destino.origin !== location.origin) return;
      var desde = indiceRuta(location.pathname);
      var hacia = indiceRuta(destino.pathname);
      if (desde < 0 || hacia < 0 || (desde === hacia && !ocupado)) return;
      ev.preventDefault();
      colocarIndicador(a);
      var dir = hacia > desde ? 1 : -1;
      irPagina(destino.pathname + destino.search, dir, { push: true });
    });

    nav.querySelectorAll("a[data-nav-slide]").forEach(function (a) {
      a.addEventListener("mouseenter", function () {
        obtenerPagina(a.getAttribute("href")).catch(function () {});
      });
      a.addEventListener("focus", function () {
        obtenerPagina(a.getAttribute("href")).catch(function () {});
      });
    });
  }

  window.addEventListener("popstate", function () {
    var idx = indiceRuta(location.pathname);
    if (idx < 0) {
      window.location.reload();
      return;
    }
    var prev = history.state && typeof history.state.idx === "number" ? history.state.idx : idx;
    var dir = idx > prev ? 1 : idx < prev ? -1 : 0;
    irPagina(location.pathname + location.search, dir, { push: false });
  });

  if (indiceRuta(location.pathname) >= 0) {
    history.replaceState({ navSlide: true, idx: indiceRuta(location.pathname) }, "", location.href);
    window.setTimeout(precargarVecinas, 600);
  }

  initIndicador();
  window.CofrialNavSlide = {
    irPagina: irPagina,
    marcarNav: marcarNav,
    colocarIndicador: colocarIndicador,
    invalidar: invalidar,
    precargar: precargarVecinas,
  };
})();
