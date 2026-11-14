"""Demanda en espera: quién espera cada producto, con RN-09 (el vendedor solo ve los clientes de su cartera)."""
from django.core.management import call_command
from django.test import TestCase

from catalogo import avisos
from catalogo.models import Producto
from clientes.models import Cliente

CLAVE = "demo-cofrial-2026"


class QuienEspera(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.producto = Producto.objects.filter(activo=True).first()
        Producto.objects.filter(pk=cls.producto.pk).update(stock_disponible=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")                 # particular, sin vendedor
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")            # institucional, cartera de la vendedora
        avisos.pedir(cls.ana, cls.producto.pk, 2)
        avisos.pedir(cls.hospital, cls.producto.pk, 5)

    def ver(self, usuario):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))
        return self.client.get("/crm/demanda/")

    def test_el_administrador_ve_a_todos_con_enlace_a_su_ficha(self):
        r = self.ver("admin@cofrial.cl")
        self.assertContains(r, "Quién espera")
        self.assertContains(r, f'href="/crm/clientes/{self.ana.pk}/"')
        self.assertContains(r, f'href="/crm/clientes/{self.hospital.pk}/"')
        self.assertContains(r, "(2 u.)")
        self.assertContains(r, "(5 u.)")

    def test_la_vendedora_solo_ve_su_cartera_y_cuenta_el_resto_sin_nombrarlo(self):
        r = self.ver("vendedora@cofrial.cl")
        self.assertContains(r, f'href="/crm/clientes/{self.hospital.pk}/"')
        self.assertNotContains(r, f'href="/crm/clientes/{self.ana.pk}/"')
        self.assertNotContains(r, self.ana.nombre)
        self.assertContains(r, "1 cliente de otras carteras")
        r = self.ver("vendedor2@cofrial.cl")                                # otra cartera: no ve al hospital
        self.assertNotContains(r, self.hospital.nombre)
        self.assertContains(r, "2 clientes de otras carteras")

    def test_los_avisos_ya_atendidos_no_aparecen(self):
        avisos.marcar_atendidos(self.ana, self.producto.pk)
        r = self.ver("admin@cofrial.cl")
        self.assertNotContains(r, f'href="/crm/clientes/{self.ana.pk}/"')
