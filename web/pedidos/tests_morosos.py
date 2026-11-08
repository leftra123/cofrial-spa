from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from clientes.models import Cliente
from crm import servicios as crm
from pedidos import documentos as d
from pedidos.models import Documento

CLAVE = "demo-cofrial-2026"


class TramoDeAtraso(SimpleTestCase):
    def test_los_bordes_de_cada_tramo(self):
        for dias, tramo in ((1, "1 a 30 días"), (30, "1 a 30 días"), (31, "31 a 60 días"), (60, "31 a 60 días"),
                            (61, "61 a 90 días"), (90, "61 a 90 días"), (91, "Más de 90 días"), (400, "Más de 90 días")):
            self.assertEqual(d.tramo_de_atraso(dias), tramo)


class ClientesMorosos(TestCase):
    """La demo trae al Hospital con una factura vencida y a Supermercados del Sur con una por vencer y una entrega sin facturar."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.sur = Cliente.objects.get(rut="76.543.210-K")
        cls.clientes = Cliente.objects.filter(pk__in=[cls.hospital.pk, cls.sur.pk])

    def morosos(self):
        return d.resumen_cobranza(self.clientes)["morosos"]

    def factura_abierta(self, cliente):
        return next(f for f in d.facturas_abiertas([cliente]))

    def atrasar(self, factura, dias):
        Documento.objects.filter(pk=factura.pk).update(vence_en=timezone.localdate() - timedelta(days=dias))

    def test_solo_es_moroso_quien_tiene_una_factura_vencida(self):
        self.assertEqual([m["cliente"].pk for m in self.morosos()], [self.hospital.pk])

    def test_una_factura_que_vence_hoy_todavia_no_es_mora(self):
        self.atrasar(self.factura_abierta(self.hospital), 0)
        self.assertEqual(self.morosos(), [])

    def test_la_deuda_total_incluye_lo_que_aun_no_vence(self):
        primera = self.factura_abierta(self.sur)
        self.atrasar(primera, 5)
        segunda = d.emitir_factura(d.entregadas_sin_factura([self.sur])[0])
        sur = next(m for m in self.morosos() if m["cliente"].pk == self.sur.pk)
        self.assertEqual(sur["vencido"], primera.monto_clp)
        self.assertEqual(sur["deuda"], primera.monto_clp + segunda.monto_clp)
        self.assertEqual(sur["n_vencidas"], 1)

    def test_el_tramo_lo_marca_la_factura_mas_atrasada(self):
        primera = self.factura_abierta(self.sur)
        segunda = d.emitir_factura(d.entregadas_sin_factura([self.sur])[0])
        self.atrasar(primera, 5)
        self.atrasar(segunda, 70)
        sur = next(m for m in self.morosos() if m["cliente"].pk == self.sur.pk)
        self.assertEqual(sur["dias_atraso"], 70)
        self.assertEqual(sur["folio"], segunda.folio)
        self.assertEqual(sur["tramo"], "61 a 90 días")
        self.assertEqual(sur["n_vencidas"], 2)

    def test_primero_quien_debe_mas_vencido(self):
        factura_sur = self.factura_abierta(self.sur)
        self.atrasar(factura_sur, 3)
        factura_hospital = self.factura_abierta(self.hospital)
        mayor, menor = (self.hospital, self.sur) if factura_hospital.saldo > factura_sur.saldo else (self.sur, self.hospital)
        self.assertEqual([m["cliente"].pk for m in self.morosos()], [mayor.pk, menor.pk])

    def test_un_abono_baja_la_mora_y_el_pago_completo_la_saca(self):
        factura = self.factura_abierta(self.hospital)
        d.registrar_pago(factura.pk, 1000, "transferencia")
        self.assertEqual(self.morosos()[0]["vencido"], factura.monto_clp - 1000)
        d.registrar_pago(factura.pk, factura.monto_clp - 1000, "transferencia")
        self.assertEqual(self.morosos(), [])

    def test_una_nota_de_credito_total_saca_al_cliente(self):
        factura = self.factura_abierta(self.hospital)
        d.emitir_nota_credito(factura.pk, factura.monto_clp, "Cadena de frío rota")
        self.assertEqual(self.morosos(), [])


class FiltroYPantalla(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.sur = Cliente.objects.get(rut="76.543.210-K")
        cls.vencida = d.facturas_abiertas([cls.hospital])[0]
        cls.por_vencer = d.facturas_abiertas([cls.sur])[0]

    def entrar(self, usuario="gerencia@cofrial.cl"):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def folios(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return [f.folio for f in r.context["cob"]["vistas"]]

    def test_sin_filtro_salen_todas_las_facturas_abiertas(self):
        self.entrar()
        self.assertEqual(self.folios("/crm/cobranza/"), [self.vencida.folio, self.por_vencer.folio])

    def test_el_filtro_deja_solo_las_vencidas_o_las_por_vencer(self):
        self.entrar()
        self.assertEqual(self.folios("/crm/cobranza/?estado=vencido"), [self.vencida.folio])
        self.assertEqual(self.folios("/crm/cobranza/?estado=por_cobrar"), [self.por_vencer.folio])

    def test_un_estado_desconocido_muestra_todas(self):
        self.entrar()
        self.assertEqual(self.folios("/crm/cobranza/?estado=pagado"), [self.vencida.folio, self.por_vencer.folio])

    def test_filtrar_no_cambia_los_totales_de_arriba(self):
        self.entrar()
        cob = self.client.get("/crm/cobranza/?estado=por_cobrar").context["cob"]
        self.assertEqual(cob["por_cobrar"], self.vencida.saldo + self.por_vencer.saldo)
        self.assertEqual(cob["n_vencidas"], 1)
        self.assertEqual(len(cob["morosos"]), 1)

    def test_las_opciones_traen_su_cantidad_y_marcan_la_activa(self):
        self.entrar()
        r = self.client.get("/crm/cobranza/?estado=vencido")
        self.assertEqual([(o["nombre"], o["n"], o["activo"]) for o in r.context["cob"]["filtros"]],
                         [("Todas", 2, False), ("Por vencer", 1, False), ("Vencidas", 1, True)])
        self.assertContains(r, 'href="/crm/cobranza/?estado=por_cobrar#facturas"')
        self.assertContains(r, 'aria-current="true"')

    def test_sin_resultados_lo_dice_sin_afirmar_que_no_hay_deuda(self):
        self.entrar()
        Documento.objects.filter(pk=self.vencida.pk).update(vence_en=timezone.localdate())
        r = self.client.get("/crm/cobranza/?estado=vencido")
        self.assertContains(r, "Ninguna factura con este estado.")
        self.assertNotContains(r, "No hay facturas con saldo pendiente.")

    def test_la_seccion_de_morosos_muestra_deuda_y_tramo(self):
        self.entrar()
        r = self.client.get("/crm/cobranza/")
        self.assertContains(r, "Clientes morosos")
        self.assertContains(r, f'<a href="/crm/clientes/{self.hospital.pk}/">{self.hospital.nombre}</a>', count=2)
        self.assertContains(r, d.tramo_de_atraso(self.vencida.dias_atraso))

    def test_sin_morosos_lo_dice(self):
        self.entrar()
        Documento.objects.filter(pk=self.vencida.pk).update(vence_en=timezone.localdate())
        self.assertContains(self.client.get("/crm/cobranza/"), "Ningún cliente tiene facturas vencidas.")

    def test_el_vendedor_no_ve_morosos_de_otra_cartera(self):
        self.entrar("vendedor2@cofrial.cl")
        r = self.client.get("/crm/cobranza/")
        self.assertEqual(r.context["cob"]["morosos"], [])
        self.assertNotContains(r, self.hospital.nombre)

    def test_al_registrar_un_pago_se_vuelve_al_mismo_filtro(self):
        self.entrar("vendedora@cofrial.cl")
        r = self.client.get("/crm/cobranza/?estado=vencido")
        self.assertContains(r, 'name="volver" value="/crm/cobranza/?estado=vencido"')
        r = self.client.post(f"/crm/documentos/{self.vencida.pk}/pago/",
                             {"monto": 1000, "medio": "transferencia", "volver": "/crm/cobranza/?estado=vencido"})
        self.assertEqual(r["Location"], "/crm/cobranza/?estado=vencido")

    def test_un_valor_inyectado_en_el_filtro_no_llega_al_html(self):
        self.entrar()
        self.assertNotContains(self.client.get('/crm/cobranza/?estado="><b>inyectado'), "inyectado")
