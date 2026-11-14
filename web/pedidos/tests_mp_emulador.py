"""Emulador de Mercado Pago: sin credenciales reales el carrito ofrece pagar con una tarjeta de prueba; solo un pago aprobado crea el pedido."""
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalogo.models import Producto
from clientes.models import Cliente
from pedidos import mercadopago as mp, servicios as s
from pedidos.models import CheckoutPago, Documento, Orden, Pago

URL = "/carrito/mp/emulador/"
REALES = {"MERCADOPAGO_ACCESS_TOKEN": "TEST-TOKEN", "MERCADOPAGO_PUBLIC_KEY": "TEST-PUBLIC"}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")

    def entrar(self, cliente=None):
        cliente = cliente or self.ana
        self.client.force_login(get_user_model().objects.get(pk=cliente.usuario_id))

    def pagar(self, titular, cliente=None, **extra):
        cliente = cliente or self.ana
        datos = {"direccion": cliente.direccion_set.first().pk, "titular": titular, "comprobante": "boleta", **extra}
        return self.client.post(URL, data=json.dumps(datos), content_type="application/json")


class EmuladorTests(Base):
    def test_aprobado_crea_el_pedido_la_boleta_y_el_pago_y_vacia_el_carrito(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        stock = Producto.objects.get(pk=self.lomo.pk).stock_disponible
        self.entrar()
        r = self.pagar("APRO")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("/pedidos/", r.json()["redirect"])
        checkout = CheckoutPago.objects.get()
        self.assertEqual(checkout.estado, "completado")
        self.assertTrue(checkout.payment_id.startswith("EMU-"))
        orden = Orden.objects.get(pk=checkout.primera_orden_id)
        self.assertTrue(Documento.objects.filter(orden=orden, tipo="boleta").exists())
        self.assertTrue(Pago.objects.filter(documento__orden=orden, medio="mercadopago", referencia__startswith="EMU-").exists())
        self.assertEqual(s.lineas_en_carrito(self.ana), 0)
        self.assertEqual(Producto.objects.get(pk=self.lomo.pk).stock_disponible, stock - 1)

    def test_rechazado_no_crea_nada_y_el_carrito_queda(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        ordenes = Orden.objects.count()
        self.entrar()
        for titular, texto in (("FUND", "no tiene fondos suficientes"), ("OTHE", "el banco rechazó la tarjeta")):
            r = self.pagar(titular)
            self.assertEqual(r.status_code, 400)
            self.assertFalse(r.json()["ok"])
            self.assertIn(texto, r.json()["mensaje"])
        self.assertEqual(Orden.objects.count(), ordenes)
        self.assertEqual(CheckoutPago.objects.filter(estado="completado").count(), 0)         # un rechazo no deja pedido, boleta ni cobro
        self.assertEqual(s.lineas_en_carrito(self.ana), 1)

    def test_titular_inventado_o_mal_formado(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        self.entrar()
        for malo in ("", "XXXX", "apro", "APRO; DROP TABLE orden"):
            self.assertEqual(self.pagar(malo).status_code, 400, malo)
        self.assertEqual(self.client.post(URL, data="no es json", content_type="application/json").status_code, 400)
        self.assertEqual(CheckoutPago.objects.filter(estado="completado").count(), 0)

    def test_la_institucion_paga_con_factura_al_contado(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        self.entrar(self.hospital)
        r = self.pagar("APRO", self.hospital, comprobante="factura")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(CheckoutPago.objects.get().comprobante, "factura")

    def test_el_carrito_ofrece_el_emulador_y_solo_sin_credenciales_reales(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        self.entrar()
        html = self.client.get("/carrito/").content.decode()
        self.assertIn('id="mp-emu-abrir"', html)
        self.assertIn("mp-emulador.js", html)
        self.assertIn("no se cobra nada", html)
        with override_settings(**REALES):
            html = self.client.get("/carrito/").content.decode()
            self.assertNotIn('id="mp-emu-abrir"', html)
            self.assertIn("mp-mostrar-pago", html)                     # el Brick real toma su lugar
            self.assertEqual(self.pagar("APRO").status_code, 403)       # y el emulador deja de responder
        with override_settings(MP_EMULADOR=False):
            self.assertNotIn('id="mp-emu-abrir"', self.client.get("/carrito/").content.decode())
            self.assertEqual(self.pagar("APRO").status_code, 403)

    def test_carrito_vacio_y_sin_sesion(self):
        self.entrar()
        self.assertNotIn('id="mp-emu-abrir"', self.client.get("/carrito/").content.decode())
        self.client.logout()
        self.assertIn(self.client.post(URL, data="{}", content_type="application/json").status_code, (302, 403))
        self.assertEqual(self.client.get(URL).status_code, 405)

    def test_emulador_no_se_confunde_con_el_real(self):
        self.assertTrue(mp.emulador())
        with override_settings(**REALES):
            self.assertFalse(mp.emulador())
            self.assertTrue(mp.activo())


class EmuladorForzadoTests(Base):
    def test_forzar_reemplaza_al_formulario_real_aunque_haya_credenciales(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        self.entrar()
        with override_settings(**REALES, MP_EMULADOR="forzar"):
            html = self.client.get("/carrito/").content.decode()
            self.assertIn('id="mp-emu-abrir"', html)
            self.assertNotIn("mp-mostrar-pago", html)
            self.assertEqual(self.pagar("APRO").status_code, 200)                         # el emulador responde y crea el pedido
        s.agregar(self.ana, self.lomo.pk, 1)
        with override_settings(**REALES, MP_EMULADOR="1"):
            self.assertIn("mp-mostrar-pago", self.client.get("/carrito/").content.decode())   # sin forzar, con credenciales manda el real
