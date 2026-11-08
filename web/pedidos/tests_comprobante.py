"""COF-04: el cliente elige boleta o factura, y el documento emitido se consulta y se descarga."""
from django.core.management import call_command
from django.test import TestCase

from catalogo.models import Producto
from pedidos import documentos, servicios as s
from pedidos.models import Documento, Orden

CLAVE = "demo-cofrial-2026"


class EleccionDeComprobante(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.login(username="ana@correo.test", password=CLAVE)
        self.ana = s.cliente_de(get_user_model().objects.get(username="ana@correo.test"))
        self.direccion = self.ana.direccion_set.first().pk
        s.agregar(self.ana, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)

    def test_el_carrito_pide_boleta_o_factura_con_el_rut_de_la_cuenta(self):
        pagina = self.client.get("/carrito/")
        self.assertContains(pagina, 'name="comprobante"')
        self.assertContains(pagina, 'value="boleta"')
        self.assertContains(pagina, 'value="factura"')
        self.assertContains(pagina, self.ana.rut)
        self.assertContains(pagina, "No pedimos otro RUT")

    def test_la_boleta_queda_en_el_pedido_y_se_descarga(self):
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "boleta"})
        orden = Orden.objects.filter(direccion__cliente=self.ana).order_by("-orden_id").first()
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        self.assertEqual(orden.comprobante, "boleta")
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, f"Boleta N.º {boleta.folio}")
        self.assertContains(pagina, "Descargar")
        visto = self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/")
        self.assertContains(visto, self.ana.rut)
        self.assertContains(visto, "No es un documento tributario")
        pdf = self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/?descarga=1")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn(self.ana.rut.encode("latin-1"), pdf.content)
        self.client.logout()
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/").status_code, 404)

    def test_la_factura_exige_giro_y_queda_pagada_en_el_pedido(self):
        antes = Orden.objects.filter(direccion__cliente=self.ana).count()
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "factura", "giro": ""})
        self.assertEqual(Orden.objects.filter(direccion__cliente=self.ana).count(), antes)
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "factura", "giro": "Venta de alimentos"})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.giro, "Venta de alimentos")
        orden = Orden.objects.filter(direccion__cliente=self.ana).order_by("-orden_id").first()
        factura = Documento.objects.get(orden=orden, tipo="factura")
        self.assertEqual(orden.comprobante, "factura")
        self.assertEqual(documentos.saldo(factura), 0)
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/documentos/{factura.pk}/"), "Venta de alimentos")
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="boleta").exists())

    def test_la_institucion_sigue_recibiendo_la_factura_despues_de_la_entrega(self):
        from django.contrib.auth import get_user_model
        hospital = s.cliente_de(get_user_model().objects.get(username="abastecimiento@hospital.test"))
        s.agregar(hospital, Producto.objects.get(sku="POL-PEC-10K").pk, 1)
        orden = s.generar_ordenes(hospital, hospital.direccion_set.first().pk, "OC-COF04")[0]
        self.assertEqual(orden.comprobante, "factura")
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="factura").exists())
        self.client.logout()
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), "La factura de este pedido se emite después de la entrega.")
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), "Descargar")
