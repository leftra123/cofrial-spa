from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from catalogo.models import Producto
from clientes.models import Cliente
from pedidos import mercadopago as mp, servicios as s
from pedidos.models import Carrito, CheckoutPago, Orden, Pago

MP_SETTINGS = {
    "MERCADOPAGO_ACCESS_TOKEN": "TEST-TOKEN",
    "MERCADOPAGO_PUBLIC_KEY": "TEST-PUBLIC",
    "MERCADOPAGO_PUBLIC_URL": "http://testserver",
    "MERCADOPAGO_PAYER_EMAIL": "test_user_1@testuser.com",
}


class MercadoPagoCheckout(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")

    @override_settings(**MP_SETTINGS)
    @patch("pedidos.mercadopago._api")
    def test_brick_aprobado_crea_orden(self, api_mock):
        s.agregar(self.ana, self.lomo.pk, 1)
        ctx = s._contexto_desde_carrito(self.ana, self.ana.direccion_set.first().pk)
        monto = sum(ctx["precios"][i.producto_id] * i.cantidad for i in ctx["items"])
        api_mock.return_value = {"id": 555, "status": "approved", "transaction_amount": float(monto),
                                 "external_reference": "COF-00000001"}
        c = self.client
        c.force_login(get_user_model().objects.get(username="ana@correo.test"))
        r = c.post("/carrito/mp/pagar/", data='{"direccion": %d, "formData": {"token": "tok", "payment_method_id": "visa", "installments": 1, "transaction_amount": %d}}'
                   % (self.ana.direccion_set.first().pk, monto), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertTrue(datos["ok"])
        self.assertIn("/pedidos/", datos["redirect"])
        self.assertEqual(CheckoutPago.objects.filter(estado="completado").count(), 1)

    @override_settings(**MP_SETTINGS)
    def test_pago_aprobado_crea_orden_idempotente(self):
        s.agregar(self.ana, self.lomo.pk, 2)
        ctx = s._contexto_desde_carrito(self.ana, self.ana.direccion_set.first().pk)
        monto = sum(ctx["precios"][i.producto_id] * i.cantidad for i in ctx["items"])
        checkout = CheckoutPago.objects.create(cliente=self.ana, direccion=ctx["direccion"], monto_clp=monto,
                                                 external_reference="COF-00000099")
        pago = {"id": 999, "status": "approved", "external_reference": "COF-00000099", "transaction_amount": float(monto)}
        with patch("pedidos.mercadopago.obtener_pago", return_value=pago):
            mp.procesar_pago_mp("999")
            mp.procesar_pago_mp("999")
        checkout.refresh_from_db()
        self.assertEqual(checkout.estado, "completado")
        ordenes = list(checkout.ordenes.order_by("orden_id"))
        self.assertEqual(len(ordenes), 1)
        self.assertEqual(Pago.objects.filter(documento__orden=ordenes[0]).first().medio, "mercadopago")
        self.assertEqual(Carrito.objects.filter(cliente=self.ana, estado="convertido").count(), 1)

    @override_settings(**MP_SETTINGS)
    def test_pago_rechazado_no_crea_orden(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        ctx = s._contexto_desde_carrito(self.ana, self.ana.direccion_set.first().pk)
        monto = sum(ctx["precios"][i.producto_id] * i.cantidad for i in ctx["items"])
        checkout = CheckoutPago.objects.create(cliente=self.ana, direccion=ctx["direccion"], monto_clp=monto,
                                                 external_reference="COF-00000100")
        pago = {"id": 1000, "status": "rejected", "external_reference": "COF-00000100", "transaction_amount": float(monto)}
        with patch("pedidos.mercadopago.obtener_pago", return_value=pago):
            mp.procesar_pago_mp("1000")
        checkout.refresh_from_db()
        self.assertEqual(checkout.estado, "fallido")
        self.assertFalse(Orden.objects.filter(checkout_pago=checkout).exists())
        self.assertTrue(Carrito.objects.filter(cliente=self.ana, estado="abierto").exists())

    def test_b2b_sin_mercado_pago(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        ordenes = s.generar_ordenes(self.hospital, self.hospital.direccion_set.first().pk, "OC-MP-1")
        self.assertEqual(len(ordenes), 1)
        self.assertFalse(CheckoutPago.objects.exists())

    @override_settings(**MP_SETTINGS)
    def test_email_demo_se_normaliza_para_mp(self):
        self.assertEqual(mp.email_cliente_mp(self.ana), "test_user_1@testuser.com")

    @override_settings(**MP_SETTINGS)
    def test_payer_otro_se_normaliza_a_rut(self):
        ana = self.ana
        payer = mp._normalizar_payer(ana, {"email": "", "identification": {"type": "Otro", "number": "12.345.678-5"}})
        self.assertEqual(payer["email"], "test_user_1@testuser.com")
        self.assertEqual(payer["identification"], {"type": "Otro", "number": "123456785"})

    @override_settings(**MP_SETTINGS)
    @patch("pedidos.mercadopago._api")
    def test_brick_inyecta_email_en_payer(self, api_mock):
        s.agregar(self.ana, self.lomo.pk, 1)
        ctx = s._contexto_desde_carrito(self.ana, self.ana.direccion_set.first().pk)
        monto = sum(ctx["precios"][i.producto_id] * i.cantidad for i in ctx["items"])
        api_mock.return_value = {"id": 556, "status": "approved", "transaction_amount": float(monto),
                                 "external_reference": "COF-00000002"}
        c = self.client
        c.force_login(get_user_model().objects.get(username="ana@correo.test"))
        r = c.post("/carrito/mp/pagar/", data='{"direccion": %d, "formData": {"token": "tok", "payment_method_id": "visa", "installments": 1, "payer": {"email": ""}}}'
                   % self.ana.direccion_set.first().pk, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        cuerpo = api_mock.call_args[0][2]
        self.assertEqual(cuerpo["payer"]["email"], "test_user_1@testuser.com")
        self.assertEqual(cuerpo["transaction_amount"], int(monto))
