/** Card Payment Brick de Mercado Pago: modal centrado en el carrito B2C. */
(function () {
  var SALIDA_MS = 280;
  var ESTADO_MS = 850;
  var ESTADO_OK_MS = 650;

  function temaCofrial() {
    var t = document.documentElement.getAttribute("data-tema");
    if (t === "oscuro" || t === "claro") return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro";
  }

  function estiloVisualBrick() {
    var oscuro = temaCofrial() === "oscuro";
    if (oscuro) {
      return {
        theme: "dark",
        customVariables: {
          baseColor: "#009ee3",
          buttonTextColor: "#ffffff",
          formBackgroundColor: "transparent",
          inputBackgroundColor: "#232a3b",
          outlineColor: "#31425f",
          textPrimaryColor: "#edf1f7",
          textSecondaryColor: "#93a1b8",
        },
      };
    }
    return {
      theme: "default",
      customVariables: {
        baseColor: "#009ee3",
        buttonTextColor: "#ffffff",
        formBackgroundColor: "#ffffff",
        inputBackgroundColor: "#ffffff",
        outlineColor: "#bccbdd",
      },
    };
  }

  function sincronizarTemaBrick() {
    var t = temaCofrial();
    document.querySelectorAll(".mp-modal .mp-brick-shell[data-mp-tema]").forEach(function (n) {
      n.setAttribute("data-mp-tema", t);
    });
  }

  function datosFormulario(payload) {
    if (!payload) return null;
    if (payload.formData && typeof payload.formData === "object") return payload.formData;
    if (payload.token) return payload;
    return null;
  }

  function init(cfg) {
    if (!cfg.publicKey || !cfg.amount || cfg.sinStock) return;
    var modal = document.getElementById("mp-pago-modal");
    var mostrar = document.getElementById("mp-mostrar-pago");
    var contenedor = document.getElementById("mp-brick-container");
    var skeleton = document.getElementById("mp-brick-skeleton");
    var shell = document.querySelector(".mp-brick-shell");
    var direccion = document.getElementById("direccion");
    var errEl = document.getElementById("mp-brick-error");
    var estadoBox = document.getElementById("mp-modal-estado");
    var estadoTit = document.getElementById("mp-modal-estado-t");
    var estadoSub = document.getElementById("mp-modal-estado-sub");
    var estadoAcc = document.getElementById("mp-modal-estado-acc");
    var btnReintentar = document.getElementById("mp-estado-reintentar");
    var btnCarrito = document.getElementById("mp-estado-carrito");
    var panel = modal && modal.querySelector(".mp-modal__panel");
    var escalaEl = document.getElementById("mp-brick-escala");
    if (!modal || !mostrar || !contenedor || typeof MercadoPago === "undefined") return;

    if (modal.parentNode !== document.body) document.body.appendChild(modal);

    var mp = new MercadoPago(cfg.publicKey, { locale: "es-CL" });
    var brickController = null;
    var montando = false;
    var brickMontado = false;
    var cerrando = false;
    var escalaObs = null;
    var mensajeCarritoPendiente = "";
    var accionReintentar = null;

    function limpiarEscalaBrick() {
      contenedor.style.transform = "";
      contenedor.style.width = "";
      contenedor.style.marginBottom = "";
    }

    function ajustarEscalaBrick() {
      if (!escalaEl || modal.hidden) return;
      limpiarEscalaBrick();
      if (!brickMontado) return;
      var disponible = escalaEl.clientHeight;
      var necesario = contenedor.scrollHeight;
      if (disponible < 8 || necesario < 8) return;
      if (necesario <= disponible + 1) return;
      var s = Math.max(0.76, Math.min(1, disponible / necesario));
      contenedor.style.transform = "scale(" + s + ")";
      contenedor.style.width = 100 / s + "%";
      contenedor.style.marginBottom = -(necesario * (1 - s)) + "px";
    }

    function observarEscalaBrick() {
      if (!escalaEl || typeof ResizeObserver === "undefined") return;
      if (escalaObs) escalaObs.disconnect();
      escalaObs = new ResizeObserver(function () {
        window.requestAnimationFrame(ajustarEscalaBrick);
      });
      escalaObs.observe(escalaEl);
      escalaObs.observe(contenedor);
    }

    function mostrarError(msg) {
      if (!errEl) return;
      errEl.textContent = msg || "";
      errEl.hidden = !msg;
    }

    function skeletonVisible(visible) {
      if (skeleton) {
        skeleton.hidden = !visible;
        skeleton.setAttribute("aria-hidden", visible ? "false" : "true");
      }
      contenedor.classList.toggle("mp-brick--loading", visible);
      if (shell) shell.classList.toggle("mp-brick-shell--listo", !visible);
    }

    function destruirBrick() {
      if (brickController && typeof brickController.unmount === "function") {
        try {
          brickController.unmount();
        } catch (e) {
          /* ignore */
        }
      }
      brickController = null;
      montando = false;
      brickMontado = false;
      contenedor.innerHTML = "";
      limpiarEscalaBrick();
      skeletonVisible(true);
    }

    function ocultarEstado() {
      if (!estadoBox) return;
      estadoBox.hidden = true;
      estadoBox.className = "mp-modal__estado";
      estadoBox.querySelectorAll("[data-marca]").forEach(function (m) {
        m.hidden = true;
        m.setAttribute("hidden", "");
      });
      if (estadoAcc) estadoAcc.hidden = true;
      accionReintentar = null;
      mensajeCarritoPendiente = "";
    }

    function ocultarAccionesSolo() {
      if (estadoAcc) estadoAcc.hidden = true;
      if (estadoBox) estadoBox.classList.remove("mp-modal__estado--accion");
      accionReintentar = null;
    }

    function mostrarMarca(clave) {
      estadoBox.querySelectorAll("[data-marca]").forEach(function (m) {
        var on = m.getAttribute("data-marca") === clave;
        m.hidden = !on;
        if (on) m.removeAttribute("hidden");
        else m.setAttribute("hidden", "");
      });
    }

    function mostrarEstado(tipo, titulo, subt, ms, onFin) {
      if (!estadoBox || !estadoTit) {
        if (onFin) onFin();
        return;
      }
      ocultarEstado();
      estadoBox.hidden = false;
      estadoBox.removeAttribute("hidden");
      estadoBox.className = "mp-modal__estado mp-modal__estado--" + tipo;
      var clave = tipo === "ok" ? "ok" : tipo === "off" ? "off" : tipo === "carga" ? "carga" : "err";
      mostrarMarca(clave);
      estadoTit.textContent = titulo;
      if (estadoSub) estadoSub.textContent = subt || "";
      ocultarAccionesSolo();
      if (typeof ms !== "number") return;
      window.setTimeout(function () {
        if (onFin) onFin();
      }, ms);
    }

    function mostrarDecision(tipo, titulo, subt, opts) {
      opts = opts || {};
      if (cerrando) return;
      contenedor.setAttribute("aria-busy", "false");
      mostrarEstado(tipo, titulo, subt, null, null);
      if (!estadoAcc || !btnReintentar || !btnCarrito) return;
      estadoBox.classList.add("mp-modal__estado--accion");
      mensajeCarritoPendiente = opts.mensajeCarrito || "";
      accionReintentar = typeof opts.onRetry === "function" ? opts.onRetry : reintentarEnModal;
      btnReintentar.textContent = opts.retryLabel || "Reintentar pago";
      btnReintentar.hidden = !!opts.ocultarReintentar;
      btnCarrito.textContent = opts.carritoLabel || "Volver al carrito";
      estadoAcc.hidden = false;
      estadoAcc.removeAttribute("hidden");
      window.setTimeout(function () {
        if (!btnReintentar.hidden) btnReintentar.focus();
        else btnCarrito.focus();
      }, 80);
    }

    function reintentarEnModal() {
      ocultarEstado();
      cerrando = false;
      mostrarError("");
      destruirBrick();
      montarBrick();
    }

    function volverAlCarritoDesdeModal() {
      if (cerrando) return;
      cerrando = true;
      var msg = mensajeCarritoPendiente;
      ocultarEstado();
      if (msg) avisarCarrito(msg);
      finalizarCierre();
    }

    function irAPedido(url) {
      mostrarEstado("carga", "Recargando…", "Estamos abriendo el detalle de tu pedido.", null, null);
      fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
        .then(function (r) {
          if (!r.ok) throw new Error("pedido");
          mostrarEstado("ok", "¡Pago recibido!", "Tu pedido quedó registrado.", ESTADO_OK_MS, function () {
            window.location.assign(url);
          });
        })
        .catch(function () {
          window.location.assign(url);
        });
    }

    function animarEntrada() {
      modal.hidden = false;
      modal.classList.remove("mp-modal--saliendo");
      modal.classList.remove("mp-modal--visible");
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          modal.classList.add("mp-modal--visible");
        });
      });
    }

    function animarSalida(onListo) {
      document.body.classList.add("mp-modal-saliendo");
      modal.classList.remove("mp-modal--visible");
      modal.classList.add("mp-modal--saliendo");
      window.setTimeout(function () {
        modal.hidden = true;
        modal.classList.remove("mp-modal--saliendo");
        document.body.classList.remove("mp-modal-saliendo");
        if (onListo) onListo();
      }, SALIDA_MS);
    }

    function rellenarEmailPayer(formData) {
      if (!formData || !cfg.email) return formData;
      formData.payer = formData.payer || {};
      var actual = (formData.payer.email || "").trim();
      if (!actual || actual.indexOf("@") < 1) {
        formData.payer.email = cfg.email;
      }
      return formData;
    }

    function avisarCarrito(msg) {
      var inline = document.getElementById("mp-inline-error");
      if (!inline) return;
      if (msg) {
        inline.textContent = msg;
        inline.hidden = false;
      } else {
        inline.textContent = "";
        inline.hidden = true;
      }
    }

    function avisarError(msg) {
      mostrarError(msg);
      if (panel && msg) panel.classList.add("mp-modal__panel--shake");
      window.setTimeout(function () { if (panel) panel.classList.remove("mp-modal__panel--shake"); }, 450);
    }

    /** Rechazo o error de pago: el usuario elige reintentar (remonta Brick) o volver al carrito. */
    function pagoFallido(titulo, msg) {
      mostrarDecision("err", titulo, msg, {
        mensajeCarrito: msg,
        onRetry: reintentarEnModal,
        retryLabel: "Reintentar pago",
      });
    }

    function leerJsonRespuesta(r) {
      return r.text().then(function (texto) {
        var cuerpo;
        try {
          cuerpo = texto ? JSON.parse(texto) : {};
        } catch (e) {
          cuerpo = {
            ok: false,
            mensaje:
              r.status === 403
                ? "Sesión o CSRF inválido. Cierra el modal, recarga el carrito (F5) e intenta de nuevo. Para Mercado Pago usa https://localhost:8443."
                : "Respuesta inesperada del servidor (" + r.status + ").",
          };
        }
        return { respuesta: r, cuerpo: cuerpo };
      });
    }

    function csrfActual() {
      var inp = document.querySelector(".checkout-mp input[name=csrfmiddlewaretoken]");
      if (inp && inp.value) return inp.value;
      var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      if (m) return decodeURIComponent(m[1]);
      return cfg.csrf || "";
    }

    function enviarPago(formData) {
      avisarError("");
      contenedor.setAttribute("aria-busy", "true");
      mostrarEstado("carga", "Procesando…", "Mercado Pago", null, null);
      return fetch(cfg.urlPago, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfActual(),
          "X-Requested-With": "fetch",
        },
        body: JSON.stringify({ direccion: direccion.value, formData: formData }),
      })
        .then(leerJsonRespuesta)
        .then(function (par) {
          var r = par.respuesta;
          var cuerpo = par.cuerpo;
          contenedor.setAttribute("aria-busy", "false");
          if (!r.ok || !cuerpo.ok) {
            var msg = cuerpo.mensaje || "No pudimos procesar el pago.";
            pagoFallido("Pago rechazado", msg);
            return Promise.reject(new Error("mp-rechazado"));
          }
          if (cuerpo.redirect) {
            irAPedido(cuerpo.redirect);
            return;
          }
        })
        .catch(function (e) {
          contenedor.setAttribute("aria-busy", "false");
          if (e && e.message === "incomplete") {
            ocultarEstado();
            return;
          }
          if (e && e.message === "mp-rechazado") return;
          var msg = e && e.message ? String(e.message) : "Revisa tu conexión e intenta de nuevo.";
          pagoFallido("No se pudo pagar", msg);
        });
    }

    function montarBrick() {
      if (montando || brickMontado) return;
      sincronizarTemaBrick();
      skeletonVisible(true);
      montando = true;
      contenedor.setAttribute("aria-busy", "true");
      mp.bricks()
        .create("cardPayment", "mp-brick-container", {
          initialization: {
            amount: cfg.amount,
            payer: { email: cfg.email || "" },
          },
          customization: {
            visual: { style: estiloVisualBrick(), hideFormButtons: false },
            paymentMethods: { maxInstallments: 1, minInstallments: 1 },
          },
          callbacks: {
            onReady: function () {
              montando = false;
              brickMontado = true;
              contenedor.setAttribute("aria-busy", "false");
              skeletonVisible(false);
              observarEscalaBrick();
              window.requestAnimationFrame(function () {
                window.requestAnimationFrame(ajustarEscalaBrick);
              });
            },
            onSubmit: function (payload) {
              var formData = rellenarEmailPayer(datosFormulario(payload));
              if (!formData) {
                mostrarError("Datos de tarjeta incompletos.");
                return Promise.reject(new Error("incomplete"));
              }
              return enviarPago(formData);
            },
            onError: function (err) {
              montando = false;
              skeletonVisible(false);
              contenedor.setAttribute("aria-busy", "false");
              console.error("Mercado Pago Brick:", err);
              var detalle = err && (err.message || err.type || err.cause);
              var msg = detalle ? String(detalle) : "Revisa los datos e intenta de nuevo.";
              if (brickMontado) {
                pagoFallido("Formulario interrumpido", msg);
              } else {
                avisarError(msg);
              }
            },
          },
        })
        .then(function (ctrl) {
          brickController = ctrl;
        })
        .catch(function () {
          montando = false;
          skeletonVisible(false);
          pagoFallido(
            "Checkout no disponible",
            "No pudimos cargar Mercado Pago. Intenta de nuevo en unos segundos."
          );
        });
    }

    function finalizarCierre() {
      animarSalida(function () {
        document.body.classList.remove("mp-modal-abierto");
        mostrar.disabled = false;
        destruirBrick();
        ocultarEstado();
        mostrarError("");
        cerrando = false;
      });
    }

    function cerrarModal() {
      if (cerrando) return;
      if (estadoBox && !estadoBox.hidden && estadoBox.classList.contains("mp-modal__estado--accion")) return;
      if (estadoBox && !estadoBox.hidden && estadoBox.classList.contains("mp-modal__estado--carga")) {
        mostrarDecision("off", "Pago en curso", "Si vuelves al carrito, revisa Mis pedidos por si el cargo se registró.", {
          onRetry: function () {
            ocultarAccionesSolo();
            if (estadoSub) estadoSub.textContent = "Mercado Pago";
            if (estadoTit) estadoTit.textContent = "Procesando…";
          },
          retryLabel: "Seguir esperando",
          mensajeCarrito: "",
        });
        return;
      }
      mostrarDecision("off", "¿Salir del pago?", "Puedes seguir con el formulario o volver al carrito.", {
        onRetry: function () {
          ocultarEstado();
        },
        retryLabel: "Seguir pagando",
        mensajeCarrito: "",
      });
    }

    function abrirPago() {
      if (!direccion || !direccion.value) {
        var msg = "Elige una dirección de entrega antes de pagar.";
        var inline = document.getElementById("mp-inline-error");
        if (inline) {
          inline.textContent = msg;
          inline.hidden = false;
        }
        direccion && direccion.focus();
        return;
      }
      var inline = document.getElementById("mp-inline-error");
      if (inline) {
        inline.hidden = true;
        inline.textContent = "";
      }
      mostrarError("");
      avisarCarrito("");
      ocultarEstado();
      sincronizarTemaBrick();
      document.body.classList.add("mp-modal-abierto");
      mostrar.disabled = true;
      animarEntrada();
      montarBrick();
      var cerrar = modal.querySelector(".mp-modal__cerrar");
      if (cerrar) window.setTimeout(function () { cerrar.focus(); }, SALIDA_MS);
    }

    mostrar.addEventListener("click", abrirPago);
    if (btnReintentar) {
      btnReintentar.addEventListener("click", function () {
        var fn = accionReintentar || reintentarEnModal;
        fn();
      });
    }
    if (btnCarrito) {
      btnCarrito.addEventListener("click", function () {
        volverAlCarritoDesdeModal();
      });
    }
    modal.querySelectorAll("[data-mp-cerrar]").forEach(function (btn) {
      btn.addEventListener("click", cerrarModal);
    });
    modal.addEventListener("click", function (ev) {
      if (ev.target.classList.contains("mp-modal__backdrop")) cerrarModal();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !modal.hidden) cerrarModal();
    });
    window.addEventListener("resize", function () {
      if (!modal.hidden) ajustarEscalaBrick();
    });

    sincronizarTemaBrick();
    skeletonVisible(true);
  }

  function arrancarDesdeDom() {
    var nodo = document.getElementById("mp-brick-cfg");
    var btn = document.getElementById("mp-mostrar-pago");
    if (!nodo || !btn) return;
    if (btn.dataset.mpBrickListo === "1") return;
    try {
      init(JSON.parse(nodo.textContent));
      btn.dataset.mpBrickListo = "1";
    } catch (e) {
      console.error("Mercado Pago Brick:", e);
    }
  }

  window.cofrialMpBrick = { init: init, arrancarDesdeDom: arrancarDesdeDom, sincronizarTema: sincronizarTemaBrick };
})();
