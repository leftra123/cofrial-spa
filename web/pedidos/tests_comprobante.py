"""COF-04: el cliente elige boleta o factura, y el documento emitido se consulta y se descarga."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from catalogo.models import Producto
from pedidos import documentos, servicios as s
from pedidos.models import Documento, EstadoOrden, Orden

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
        self.assertGreater(documentos.saldo(boleta), 0)
        self.assertIsNotNone(boleta.vence_en)
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, f"Boleta N.º {boleta.folio}")
        self.assertContains(pagina, "Ver boleta")
        self.assertContains(pagina, "Descargar PDF")
        self.assertNotContains(pagina, f"Boleta N.º {boleta.folio} <a")
        visto = self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/")
        self.assertContains(visto, self.ana.rut)
        self.assertContains(visto, f"Boleta N.º {boleta.folio}")
        self.assertContains(visto, "logo-horizontal-900.png")
        self.assertContains(visto, "comprobante-hoja")
        self.assertContains(visto, orden.ordenitem_set.select_related("producto").first().producto.nombre)
        self.assertContains(visto, "Total (IVA incluido)")
        self.assertContains(visto, "No es un documento tributario")
        pdf = self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/?descarga=1")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn(self.ana.rut.encode("latin-1"), pdf.content)
        self.assertIn("Documento simulado para la demostración.".encode("latin-1"), pdf.content)
        self.assertIn(b"No es un documento tributario", pdf.content)
        self.assertIn(b"SII.", pdf.content)
        self.client.logout()
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/").status_code, 404)

    def test_la_factura_exige_giro_y_queda_por_pagar_a_30_dias(self):
        antes = Orden.objects.filter(direccion__cliente=self.ana).count()
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "factura", "giro": ""})
        self.assertEqual(Orden.objects.filter(direccion__cliente=self.ana).count(), antes)
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "factura", "giro": "Venta de alimentos"})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.giro, "Venta de alimentos")
        orden = Orden.objects.filter(direccion__cliente=self.ana).order_by("-orden_id").first()
        factura = Documento.objects.get(orden=orden, tipo="factura")
        self.assertEqual(orden.comprobante, "factura")
        self.assertGreater(documentos.saldo(factura), 0)
        self.assertEqual(factura.vence_en, timezone.localdate() + timedelta(days=30))
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
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), "Descargar PDF")
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), "Ver boleta")

    def _hospital(self):
        from django.contrib.auth import get_user_model
        self.client.logout()
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        hospital = s.cliente_de(get_user_model().objects.get(username="abastecimiento@hospital.test"))
        s.agregar(hospital, Producto.objects.get(sku="POL-PEC-10K").pk, 1)
        return hospital

    def test_la_institucion_no_elige_boleta(self):
        hospital = self._hospital()
        pagina = self.client.get("/carrito/")
        self.assertContains(pagina, 'type="hidden" name="comprobante" value="factura"')
        self.assertNotContains(pagina, 'value="boleta"')
        antes = Orden.objects.filter(direccion__cliente=hospital).count()
        self.client.post("/carrito/confirmar/", {"direccion": hospital.direccion_set.first().pk, "comprobante": "boleta", "numero_oc": "OC-1"})
        self.assertEqual(Orden.objects.filter(direccion__cliente=hospital).count(), antes)
        self.assertFalse(Documento.objects.filter(orden__direccion__cliente=hospital, tipo="boleta").exists())

    def test_la_factura_institucional_no_queda_pagada_y_sigue_en_cobranza(self):
        hospital = self._hospital()
        self.client.post("/carrito/confirmar/", {"direccion": hospital.direccion_set.first().pk, "comprobante": "factura", "giro": "Salud", "numero_oc": "OC-2"})
        orden = Orden.objects.filter(direccion__cliente=hospital).order_by("-orden_id").first()
        self.assertEqual(orden.comprobante, "factura")
        self.assertFalse(orden.documento_set.exists())
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        self.assertIn(orden.pk, [o.pk for o in documentos.entregadas_sin_factura([hospital])])

    def test_un_comprobante_o_giro_que_no_es_texto_no_rompe(self):
        self.assertEqual(s.elegir_comprobante(self.ana, "factura", 123), "factura")
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.giro, "123")
        with self.assertRaises(s.ErrorDeNegocio):
            s.elegir_comprobante(self.ana, ["factura"], "")

    def test_la_guia_acompaña_la_entrega_y_no_se_abre_como_boleta(self):
        self.client.post("/carrito/confirmar/", {"direccion": self.direccion, "comprobante": "boleta"})
        orden = Orden.objects.filter(direccion__cliente=self.ana).order_by("-orden_id").first()
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        guia = documentos.emitir_guia(orden)
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn("Ver boleta", html)
        self.assertIn("Descargar PDF", html)
        self.assertIn(f"Guía de despacho N.º {guia.folio}", html)
        self.assertIn("Acompaña la entrega", html)
        self.assertNotIn(f"/documentos/{guia.pk}/", html)
        self.assertIn(f"/documentos/{boleta.pk}/", html)

    def test_el_pdf_institucional_desglosa_el_iva(self):
        hospital = self._hospital()
        orden = s.generar_ordenes(hospital, hospital.direccion_set.first().pk, "OC-3")[0]
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        factura = documentos.emitir_factura(orden)
        pdf = documentos.comprobante_pdf(factura)
        self.assertIn(b"Neto ", pdf)
        self.assertIn(b"IVA 19 %", pdf)
        self.assertIn(b"Total con IVA", pdf)
        pagina = self.client.get(f"/pedidos/{orden.pk}/documentos/{factura.pk}/")
        self.assertContains(pagina, "IVA 19 %")

    def test_un_pedido_largo_sigue_en_otra_pagina_y_conserva_el_total(self):
        pdf = documentos._pdf([f"Linea {i}" for i in range(120)] + ["Total final"])
        self.assertEqual(pdf.count(b"/Type /Page "), 3)
        self.assertIn(b"/Count 3", pdf)
        self.assertIn(b"(Total final) Tj", pdf)
        inicio_xref = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
        self.assertTrue(pdf[inicio_xref:].startswith(b"xref"))
