"""Casos de uso que un profesor probaría en vivo: la sesión vence con la pantalla abierta (docs/matriz-casos-de-uso.md)."""
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from catalogo.models import Producto
from clientes.models import Cliente
from cofrial import entradas
from crm.models import Prospecto
from pedidos import servicios as pedidos
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class SesionVencida(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.producto = Producto.objects.filter(activo=True, stock_disponible__gt=5).first()

    def setUp(self):
        cache.clear()

    def ingresar_siguiendo(self, respuesta, usuario="ana@correo.test"):
        """Hace lo que hace la persona: sigue el enlace al login y entra con su clave."""
        return self.client.post(respuesta["Location"], {"username": usuario, "password": CLAVE}, follow=True)

    def test_confirmar_con_la_sesion_vencida_vuelve_al_carrito_y_no_a_un_405(self):
        pedidos.agregar(self.ana, self.producto.pk, 2)
        ordenes = Orden.objects.count()
        r = self.client.post("/carrito/confirmar/", {"direccion": 1}, HTTP_REFERER="http://testserver/carrito/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("next=%2Fcarrito%2F", r["Location"])
        final = self.ingresar_siguiendo(r)
        self.assertEqual((final.status_code, final.request["PATH_INFO"]), (200, "/carrito/"))
        self.assertContains(final, self.producto.nombre)                        # el carrito está en la base: sobrevivió a la sesión
        self.assertEqual(Orden.objects.count(), ordenes)                        # no se compró nada a ciegas

    def test_agregar_con_la_sesion_vencida_vuelve_a_la_ficha_del_producto(self):
        ficha = f"/catalogo/{self.producto.pk}/"
        r = self.client.post("/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 1}, HTTP_REFERER=f"http://testserver{ficha}")
        final = self.ingresar_siguiendo(r)
        self.assertEqual((final.status_code, final.request["PATH_INFO"]), (200, ficha))

    def test_el_aviso_explica_que_la_sesion_termino(self):
        r = self.client.post("/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 1}, follow=True)
        self.assertContains(r, "Tu sesión terminó")

    def test_sin_referer_o_con_uno_externo_vuelve_a_un_lugar_propio(self):
        for cabecera in ({}, {"HTTP_REFERER": "https://malo.example/robo/"}):
            r = self.client.post("/carrito/confirmar/", {"direccion": 1}, **cabecera)
            self.assertTrue(r["Location"].endswith("next=%2Fcarrito%2F"), r["Location"])

    def test_el_crm_tampoco_termina_en_un_405(self):
        ficha = f"/crm/prospectos/{Prospecto.objects.get(nombre_contacto='Jorge Rivas').pk}/"
        r = self.client.post(f"{ficha}mover/", {"etapa": 2}, HTTP_REFERER=f"http://testserver{ficha}")
        final = self.ingresar_siguiendo(r, "vendedora@cofrial.cl")
        self.assertEqual((final.status_code, final.request["PATH_INFO"]), (200, ficha))

    def test_un_get_sigue_volviendo_a_la_misma_pagina(self):
        self.assertEqual(self.client.get("/pedidos/").url, "/cuenta/entrar/?next=%2Fpedidos%2F")

    def test_conserva_los_filtros_de_la_pagina_de_origen(self):
        pedido = RequestFactory().post("/carrito/agregar/", HTTP_REFERER="http://testserver/catalogo/?categoria=2")
        self.assertEqual(entradas.url_de_ingreso(pedido), "/cuenta/entrar/?next=%2Fcatalogo%2F%3Fcategoria%3D2")
