"""El «Total» de un pedido B2B se rotula y se calcula igual en Mis pedidos, la ficha del CRM y Cobranza (revisión de usuarios del 8-nov-2026)."""
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase

from catalogo.templatetags.formato import clp, con_iva
from catalogo.models import Producto
from clientes.models import Cliente
from pedidos import servicios as s
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class TotalConIvaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.ana = Cliente.objects.get(rut="12.345.678-5")

    def setUp(self):
        cache.clear()

    def entrar(self, usuario):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c

    def orden_del(self, cliente):
        orden = Orden.objects.filter(direccion__cliente=cliente).order_by("orden_id").first()
        self.assertIsNotNone(orden)
        return orden

    def test_mis_pedidos_b2b_muestra_el_total_con_iva_y_lo_dice(self):
        orden = self.orden_del(self.hospital)
        html = self.entrar("abastecimiento@hospital.test").get("/pedidos/").content.decode()
        self.assertIn("Total con IVA</th>", html)
        self.assertIn(con_iva(s.total_orden(orden)), html)
        self.assertNotIn(f">{clp(s.total_orden(orden))}<", html)             # el neto ya no se muestra como «Total»

    def test_la_ficha_del_crm_muestra_el_mismo_total_con_iva(self):
        orden = self.orden_del(self.hospital)
        html = self.entrar("vendedora@cofrial.cl").get(f"/crm/clientes/{self.hospital.cliente_id}/").content.decode()
        self.assertIn("Total con IVA</th>", html)
        self.assertIn(con_iva(s.total_orden(orden)), html)
        self.assertNotIn(f'class="num">{clp(s.total_orden(orden))}</td>', html)

    def test_mis_pedidos_b2c_ya_trae_el_iva_y_no_se_le_suma(self):
        producto = Producto.objects.filter(activo=True, stock_disponible__gt=20).first()
        s.agregar(self.ana, producto.pk, 1)
        orden = s.generar_ordenes(self.ana, self.ana.direccion_set.first().direccion_id)[0]
        html = self.entrar("ana@correo.test").get("/pedidos/").content.decode()
        self.assertIn("Total con IVA</th>", html)
        self.assertIn(clp(s.total_orden(orden)), html)
        self.assertNotIn(con_iva(s.total_orden(orden)), html)
