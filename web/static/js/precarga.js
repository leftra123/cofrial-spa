/* Botón «Precargar datos de ejemplo» del registro: rellena el formulario con una persona ficticia (RUT válido y correo propios de
   cada clic) para mostrar la pantalla sin escribir todos los campos. Todo es inventado; el correo usa el dominio reservado .test. */
(function () {
  var boton = document.getElementById("precargar-registro");
  if (!boton) return;
  var form = boton.closest(".auth").querySelector("form");
  var nota = document.getElementById("precarga-nota");
  var CLAVE = "Cofrial-demo-2026";
  var PERSONAS = [["Camila Rojas Fuentes", "camila.rojas"], ["Matías Soto Parra", "matias.soto"], ["Valentina Muñoz Leal", "valentina.munoz"],
                  ["Ignacio Vera Campos", "ignacio.vera"], ["Francisca Núñez Bravo", "francisca.nunez"], ["Tomás Araya Pinto", "tomas.araya"]];
  var DIRECCIONES = ["Av. Alemania 671", "Manuel Montt 1090", "Av. Caupolicán 520", "Calle Bulnes 450", "Av. Pedro de Valdivia 1250"];

  function azar(lista) { return lista[Math.floor(Math.random() * lista.length)]; }
  function entre(a, b) { return a + Math.floor(Math.random() * (b - a + 1)); }

  function rutValido() {                                   // módulo 11, igual que clientes/rut.py
    var cuerpo = String(entre(10000000, 24999999)), suma = 0, factor = 2;
    for (var i = cuerpo.length - 1; i >= 0; i--) { suma += Number(cuerpo[i]) * factor; factor = factor === 7 ? 2 : factor + 1; }
    var resto = 11 - (suma % 11), dv = resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
    return cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "-" + dv;
  }

  function poner(nombre, valor) {
    var campo = form.elements[nombre];
    if (!campo) return;
    campo.value = valor;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
    campo.dispatchEvent(new Event("change", { bubbles: true }));
  }

  boton.addEventListener("click", function () {
    var persona = azar(PERSONAS), comuna = form.elements.comuna;
    poner("nombre", persona[0]);
    poner("rut", rutValido());
    poner("email", persona[1] + entre(100, 999) + "@correo.test");
    poner("telefono", "+56 9 " + entre(5000, 9999) + " " + entre(1000, 9999));
    poner("direccion", azar(DIRECCIONES));
    if (comuna) {
      var opciones = Array.prototype.slice.call(comuna.options);
      var temuco = opciones.filter(function (o) { return /temuco/i.test(o.text); })[0];
      poner("comuna", (temuco || azar(opciones)).value);
    }
    poner("clave", CLAVE);
    poner("clave2", CLAVE);
    if (nota) nota.textContent = "Datos ficticios cargados. Clave de ejemplo: " + CLAVE + ". Vuelve a pulsar para otra persona.";
    var enviar = form.querySelector("button:not([type=button])");
    if (enviar) enviar.focus();
  });
})();
