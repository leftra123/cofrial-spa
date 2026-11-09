"""Lo que ve quien compra mientras espera: cuánto falta como dato principal, también sin mapa, y un mapa tranquilo que no carga de más."""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from catalogo.models import Producto
from flota.models import Telemetria
from pedidos import servicios as s
from pedidos.models import EstadoOrden

from .tests_entrega import EntregaBase

WEB = Path(__file__).resolve().parent.parent
PLANTILLA = (WEB / "templates" / "pedidos" / "detalle.html").read_text()
CSS = (WEB / "static" / "css" / "cofrial.css").read_text()


def lectura(despacho):
    return Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=60, alerta_ruptura_frio=False)


class PantallaDelCompradorTests(EntregaBase):
    def pagina(self, orden):
        self.entrar()
        return self.client.get(f"/pedidos/{orden.pk}/").content.decode()

    def test_en_ruta_trae_mapa_distintivo_y_texto_fuera_del_mapa(self):
        _, orden, despacho = self.orden_despachada()
        lectura(despacho)
        pagina = self.pagina(orden)
        self.assertIn('id="mapa"', pagina)
        self.assertIn('id="llegada-insignia"', pagina)
        self.assertIn("vendor/maplibre/maplibre-gl.js", pagina)
        fuera, _, _ = pagina.partition('id="mapa"')
        self.assertIn('id="ep-sub"', fuera)                                # el tiempo también se dice antes del mapa, por si no se puede dibujar
        self.assertIn('id="seg-eta"', pagina.partition('id="mapa"')[2])    # y debajo, en la fila de datos

    def test_la_api_entrega_lo_que_la_pantalla_necesita(self):
        _, orden, despacho = self.orden_despachada()
        lectura(despacho)
        self.entrar()
        seg = self.client.get(f"/api/pedidos/{orden.pk}/seguimiento/").json()["seguimiento"]
        for campo in ("minutos", "eta", "cerca", "km_restantes", "salida_en", "llegada_en", "destino", "ruta_url"):
            self.assertIn(campo, seg)
        self.assertGreaterEqual(seg["minutos"], 1)
        self.assertEqual(set(seg["eta"]), {"desde", "hasta"})
        salida = datetime.fromisoformat(seg["salida_en"]).replace(second=0, microsecond=0)
        self.assertGreaterEqual(datetime.fromisoformat(seg["eta"]["desde"]), salida)       # el rango no empieza antes de la salida

    def test_entregado_no_carga_el_mapa_ni_deja_una_caja_vacia(self):
        cliente, orden, despacho = self.orden_despachada()
        lectura(despacho)
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        pagina = self.pagina(orden)
        self.assertIn('id="seg"', pagina)                                  # el registro de temperatura sigue
        self.assertIn('id="seg-eta"', pagina)
        for pieza in ('id="mapa"', 'id="mapa-vacio"', 'id="llegada-insignia"', "vendor/maplibre/", "js/mapa.js", "js/leyenda.js"):
            self.assertNotIn(pieza, pagina)
        self.assertNotIn("Dónde va su pedido", pagina)

    def test_en_la_puerta_sigue_el_mapa(self):
        _, orden, despacho = self.orden_despachada()
        lectura(despacho)
        s.llegar_a_la_puerta([orden])
        pagina = self.pagina(orden)
        self.assertIn('id="mapa"', pagina)
        self.assertIn('id="llegada-insignia"', pagina)

    def test_sin_despacho_no_hay_seguimiento_y_se_dice_que_aun_no_sale(self):
        cliente = s.cliente_de(get_user_model().objects.get(username="ana@correo.test"))
        s.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        orden = s.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]
        orden.estado_orden = EstadoOrden.objects.get(nombre="Confirmada")
        orden.save(update_fields=["estado_orden"])
        pagina = self.pagina(orden)
        self.assertIn("Tu pedido aún no sale", pagina)
        self.assertNotIn('id="seg"', pagina)
        self.assertNotIn("vendor/maplibre/", pagina)

    def test_el_mapa_del_comprador_no_muestra_datos_operativos(self):
        _, orden, despacho = self.orden_despachada()
        lectura(despacho)
        pagina = self.pagina(orden)
        self.assertNotIn("combustible", pagina.lower())
        self.assertNotIn("etiqueta: s.camion_id", PLANTILLA)               # el código del camión no va sobre el mapa


class VentanaDeLlegadaTests(SimpleTestCase):
    """La ventana nunca parte antes de ahora: con el camión recién salido decía «Salió 16:57» y «entre 16:50 y 17:10»."""

    def test_cerca_de_llegar_no_parte_en_el_pasado(self):
        ahora = datetime(2026, 11, 8, 16, 57, 30, tzinfo=dt_timezone.utc)
        v = s._ventana(ahora + timedelta(minutes=2), 1, ahora)
        self.assertEqual(datetime.fromisoformat(v["desde"]), ahora.replace(second=0))
        self.assertEqual(datetime.fromisoformat(v["hasta"]).minute, 15)

    def test_lejos_sigue_la_ventana_de_siempre(self):
        ahora = datetime(2026, 11, 8, 14, 0, tzinfo=dt_timezone.utc)
        v = s._ventana(ahora + timedelta(minutes=30), 1, ahora)
        self.assertEqual((datetime.fromisoformat(v["desde"]).minute, datetime.fromisoformat(v["hasta"]).minute), (25, 45))

    def test_con_tiempo_acelerado_tampoco(self):
        ahora = datetime(2026, 11, 8, 14, 0, 40, tzinfo=dt_timezone.utc)
        v = s._ventana(ahora + timedelta(seconds=5), 20, ahora)
        self.assertGreaterEqual(datetime.fromisoformat(v["desde"]), ahora.replace(second=0))


class ReglasDelMapaDelCompradorTests(SimpleTestCase):
    """Sin navegador se revisa lo que no se debe colar: lo que se ve de verdad se comprobó con Chromium (docs/decisiones.md)."""

    def test_usa_gradiente_y_deslizamiento_sin_animar_el_lienzo(self):
        self.assertIn("gradiente:", PLANTILLA)
        self.assertIn(".animarA(", PLANTILLA)
        self.assertNotIn("flujo:", PLANTILLA)                             # la línea que avanza obliga a redibujar el lienzo
        self.assertNotIn("requestAnimationFrame", PLANTILLA)
        self.assertNotIn("setPaintProperty", PLANTILLA)

    def test_no_hay_cuenta_regresiva_ni_reloj_por_segundo(self):
        self.assertNotIn("setInterval(mostrarSenal", PLANTILLA)
        self.assertNotIn(', 1000)', PLANTILLA)

    def test_solo_se_anuncia_el_cambio_de_franja_o_de_estado(self):
        """La región en vivo es una sola; escribir en ella en cada lectura de 5 s saturaría a quien usa un lector de pantalla."""
        self.assertEqual(PLANTILLA.count('aria-live="polite"'), 2)         # el anuncio del seguimiento y el de la entrega en la puerta, que ya existía
        self.assertIn('id="llegada-anuncio"', PLANTILLA)
        self.assertNotIn('id="ruta-info" aria-live', PLANTILLA)

    def test_el_halo_vive_en_css_y_respeta_el_movimiento_reducido(self):
        inicio = CSS.index("seguimiento del comprador")
        bloque = CSS[inicio:]
        self.assertIn("@keyframes destino-halo", bloque)
        self.assertIn("prefers-reduced-motion", bloque)
        fotogramas = bloque[bloque.index("@keyframes destino-halo"):].split("}\n")[0]
        for prohibido in ("width", "height", "box-shadow", "filter"):
            self.assertNotIn(prohibido, fotogramas)                        # solo transform y opacity: no repintan
