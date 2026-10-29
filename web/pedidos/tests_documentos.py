from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente, Vendedor
from crm import servicios as crm
from flota.models import Camion, Despacho
from pedidos import documentos as d, servicios as s
from pedidos.models import Documento, Orden, Pago

CLAVE = "demo-cofrial-2026"


class DocumentosYPagos(TestCase):
    """RN-17 a RN-22: guía, boleta, factura, pagos, notas de crédito y cobranza."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")      # B2B, vendedora María Paz
        cls.sur = Cliente.objects.get(rut="76.543.210-K")           # B2B, vendedor Pedro
        cls.ana = Cliente.objects.get(rut="12.345.678-5")           # B2C
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")

    def comprar(self, cliente, cantidad=2, oc="OC-T-1"):
        s.agregar(cliente, self.lomo.pk, cantidad)
        return s.generar_orden(cliente, cliente.direccion_set.first().pk, oc)

    def entregar(self, orden):
        despacho = Despacho.objects.create(camion=Camion.objects.get(camion_id="CAM-03"), programado_para=timezone.now(), salida_en=timezone.now())
        Orden.objects.filter(pk=orden.pk).update(despacho=despacho)
        orden.refresh_from_db()
        for _ in range(4):
            s.avanzar(orden)
        return Orden.objects.get(pk=orden.pk)

    def test_rn17_b2c_paga_al_comprar_y_recibe_boleta_pagada_con_iva_incluido(self):
        orden = self.comprar(self.ana, 2)
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        self.assertEqual(boleta.monto_clp, 2 * 45990)               # el precio B2C ya incluye IVA
        self.assertEqual(d.saldo(boleta), 0)
        self.assertEqual(Pago.objects.get(documento=boleta).medio, "webpay")
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="factura").exists())

    def test_b2b_al_comprar_no_se_cobra_ni_se_emite_nada(self):
        orden = self.comprar(self.hospital)
        self.assertFalse(Documento.objects.filter(orden=orden).exists())

    def test_rn16_al_despachar_sale_la_guia_una_sola_vez_y_sin_monto(self):
        orden = self.entregar(self.comprar(self.hospital))
        guias = Documento.objects.filter(orden=orden, tipo="guia_despacho")
        self.assertEqual(guias.count(), 1)
        self.assertIsNone(guias.first().monto_clp)
        self.assertEqual(d.emitir_guia(orden).pk, guias.first().pk)  # emitirla otra vez no duplica

    def test_rn18_factura_solo_tras_la_entrega_una_vez_con_iva_y_vencimiento(self):
        orden = self.comprar(self.hospital, 2)
        with self.assertRaises(s.ErrorDeNegocio):
            d.emitir_factura(orden)                                  # aún «Recibida»
        orden = self.entregar(orden)
        f = d.emitir_factura(orden)
        self.assertEqual(f.monto_clp, round(2 * 38990 * 1.19))       # el precio B2B es neto: se suma el IVA
        self.assertEqual(f.vence_en, timezone.localdate() + timedelta(days=30))
        with self.assertRaises(s.ErrorDeNegocio):
            d.emitir_factura(orden)
        with self.assertRaises(s.ErrorDeNegocio):
            d.emitir_factura(self.entregar(self.comprar(self.ana)))  # el público no recibe factura

    def test_los_folios_avanzan_por_tipo(self):
        f1 = d.emitir_factura(self.entregar(self.comprar(self.hospital, 1, "A")))
        f2 = d.emitir_factura(self.entregar(self.comprar(self.hospital, 1, "B")))
        self.assertEqual(f2.folio, f1.folio + 1)
        self.assertEqual(Documento.objects.filter(tipo="factura", folio=f1.folio).count(), 1)

    def test_rn19_pago_parcial_total_y_nunca_mas_que_el_saldo(self):
        f = d.emitir_factura(self.entregar(self.comprar(self.hospital, 1)))
        total = f.monto_clp
        d.registrar_pago(f.pk, 10000, "transferencia", "TRF-1")
        self.assertEqual(d.saldo(f), total - 10000)
        with self.assertRaises(s.ErrorDeNegocio):
            d.registrar_pago(f.pk, total, "transferencia")           # supera el saldo
        with self.assertRaises(s.ErrorDeNegocio):
            d.registrar_pago(f.pk, 0, "transferencia")
        with self.assertRaises(s.ErrorDeNegocio):
            d.registrar_pago(f.pk, 100, "devolucion")                # ese medio lo usa el sistema, no el vendedor
        d.registrar_pago(f.pk, total - 10000, "cheque")
        self.assertEqual(d.saldo(f), 0)
        self.assertEqual(d.documentos_de_orden(f.orden)[-1].estado_pago, "pagado")

    def test_rn20_nota_de_credito_rebaja_la_deuda_y_exige_motivo(self):
        f = d.emitir_factura(self.entregar(self.comprar(self.hospital, 2)))
        with self.assertRaises(s.ErrorDeNegocio):
            d.emitir_nota_credito(f.pk, 1000, " ")
        with self.assertRaises(s.ErrorDeNegocio):
            d.emitir_nota_credito(f.pk, f.monto_clp + 1, "Cadena de frío rota")
        n = d.emitir_nota_credito(f.pk, 20000, "Cadena de frío rota: 2 cajas rechazadas")
        self.assertEqual(n.referencia_id, f.pk)
        self.assertEqual(d.saldo(f), f.monto_clp - 20000)
        self.assertFalse(Pago.objects.filter(documento=f).exists())  # nada pagado: no hay nada que devolver

    def test_nota_de_credito_sobre_lo_ya_pagado_devuelve_el_excedente(self):
        f = d.emitir_factura(self.entregar(self.comprar(self.hospital, 1)))
        d.registrar_pago(f.pk, f.monto_clp, "transferencia")
        d.emitir_nota_credito(f.pk, 5000, "Producto en mal estado")
        self.assertEqual(d.saldo(f), 0)
        self.assertEqual(Pago.objects.get(documento=f, medio="devolucion").monto_clp, -5000)

    def test_cancelar_una_orden_b2c_anula_la_boleta_y_devuelve_el_pago(self):
        orden = self.comprar(self.ana, 1)
        s.cancelar(orden, como="cliente")
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        self.assertEqual(Documento.objects.get(orden=orden, tipo="nota_credito").monto_clp, boleta.monto_clp)
        self.assertEqual(d.saldo(boleta), 0)
        self.assertEqual(d.documentos_de_orden(orden)[0].estado_pago, "anulado")
        self.assertEqual(sum(Pago.objects.filter(documento=boleta).values_list("monto_clp", flat=True)), 0)

    def test_cancelar_una_orden_b2b_sin_documentos_no_emite_nada(self):
        orden = self.comprar(self.hospital)
        s.cancelar(orden, como="cliente")
        self.assertFalse(Documento.objects.filter(orden=orden).exists())

    def test_rn21_cobranza_separa_sin_facturar_por_cobrar_y_vencido(self):
        # la demo trae: una factura pagada, una vencida, una por cobrar y una entrega sin facturar
        c = d.resumen_cobranza(Cliente.objects.filter(pk__in=[self.hospital.pk, self.sur.pk]))
        self.assertEqual(len(c["sin_facturar"]), 1)
        self.assertEqual(c["n_vencidas"], 1)
        self.assertEqual(len(c["facturas"]), 2)                      # la pagada no aparece
        self.assertGreater(c["vencido"], 0)
        self.assertEqual(c["por_cobrar"], sum(f.saldo for f in c["facturas"]))
        vencida = next(f for f in c["facturas"] if f.estado_pago == "vencido")
        self.assertGreaterEqual(vencida.dias_atraso, 1)

    def test_la_orden_pagada_de_la_demo_figura_pagada(self):
        pagada = next(f for f in d.documentos_de_cliente(self.hospital) if f.tipo == "factura" and f.estado_pago == "pagado")
        self.assertEqual(d.saldo(pagada), 0)


class DocumentosEnElCrm(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.sur = Cliente.objects.get(rut="76.543.210-K")           # cartera de Pedro
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")      # cartera de María Paz

    def entrar(self, usuario):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def sin_facturar_de_sur(self):
        return d.entregadas_sin_factura([self.sur])[0]

    def test_el_vendedor_factura_y_cobra_solo_dentro_de_su_cartera(self):
        orden = self.sin_facturar_de_sur()
        with self.assertRaises(s.ErrorDeNegocio):
            crm.facturar(Vendedor.objects.get(nombre="María Paz Soto").usuario, orden.pk)      # no es su cliente
        pedro = Vendedor.objects.get(nombre="Pedro Núñez").usuario
        f = crm.facturar(pedro, orden.pk)
        crm.registrar_pago(pedro, f.pk, f.monto_clp, "transferencia", "TRF-9")
        self.assertEqual(d.saldo(f), 0)

    def test_gerencia_ve_la_cobranza_pero_no_puede_emitir_ni_cobrar(self):
        gerencia = get_user_model().objects.get(username="gerencia@cofrial.cl")
        self.assertEqual(len(crm.cobranza(gerencia)["sin_facturar"]), 1)
        with self.assertRaises(s.ErrorDeNegocio):
            crm.facturar(gerencia, self.sin_facturar_de_sur().pk)

    def test_pantalla_de_cobranza_y_ficha_del_cliente(self):
        self.entrar("vendedor2@cofrial.cl")
        r = self.client.get("/crm/cobranza/")
        self.assertContains(r, "Entregado, sin facturar")
        self.assertContains(r, "Emitir factura")
        self.assertContains(r, "Supermercados del Sur")
        self.assertNotContains(r, "Hospital Regional")               # la cartera de la otra vendedora no se ve
        self.assertContains(self.client.get(f"/crm/clientes/{self.sur.pk}/"), "Documentos y pagos")
        self.assertEqual(self.client.get(f"/crm/clientes/{self.hospital.pk}/").status_code, 404)

    def test_emitir_factura_desde_la_pantalla(self):
        self.entrar("vendedor2@cofrial.cl")
        orden = self.sin_facturar_de_sur()
        r = self.client.post(f"/crm/ordenes/{orden.pk}/factura/", follow=True)
        self.assertContains(r, "Factura N.º")
        self.assertTrue(Documento.objects.filter(orden=orden, tipo="factura").exists())

    def test_el_destino_de_regreso_solo_acepta_rutas_del_crm(self):
        self.entrar("vendedor2@cofrial.cl")
        r = self.client.post(f"/crm/ordenes/{self.sin_facturar_de_sur().pk}/factura/", {"volver": "//evil.test/"})
        self.assertEqual(r["Location"], "/crm/cobranza/")

    def test_el_cliente_ve_sus_documentos_en_el_detalle_del_pedido(self):
        self.assertTrue(self.client.login(username="abastecimiento@hospital.test", password=CLAVE))
        orden = Orden.objects.filter(direccion__cliente=self.hospital, documento__tipo="factura").first()
        r = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(r, "Documentos y pago")
        self.assertContains(r, "Factura N.º")
        self.assertContains(r, "Guía de despacho N.º")
