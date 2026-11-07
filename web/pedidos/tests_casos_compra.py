"""Bordes de la compra que el informe no detalla y un profesor probaría (docs/matriz-casos-de-uso.md)."""
import threading
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente, Comuna, Direccion
from pedidos import documentos, servicios as s
from pedidos.models import Carrito, CarritoItem, Orden

CLAVE = "demo-cofrial-2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.refrigerado = Producto.objects.filter(activo=True, stock_disponible__gt=20, categoria__rango_temperatura__nombre="Refrigerado").first()
        cls.congelado = Producto.objects.filter(activo=True, stock_disponible__gt=20, categoria__rango_temperatura__nombre="Congelado").first()

    def setUp(self):
        cache.clear()

    def stock(self, producto):
        return Producto.objects.get(pk=producto.pk).stock_disponible

    def direccion(self, cliente):
        return cliente.direccion_set.first().pk


class ProductoRetirado(Base):
    def test_un_producto_desactivado_en_el_carrito_no_se_compra(self):
        s.agregar(self.ana, self.refrigerado.pk, 2)
        Producto.objects.filter(pk=self.refrigerado.pk).update(activo=False)
        antes, ordenes = self.stock(self.refrigerado), Orden.objects.count()
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Ya no vendemos"):
            s.generar_ordenes(self.ana, self.direccion(self.ana))
        self.assertEqual((self.stock(self.refrigerado), Orden.objects.count()), (antes, ordenes))
        self.assertTrue(Carrito.objects.filter(cliente=self.ana, estado="abierto").exists())

    def test_la_pantalla_del_carrito_bloquea_el_boton(self):
        s.agregar(self.ana, self.refrigerado.pk, 1)
        Producto.objects.filter(pk=self.refrigerado.pk).update(activo=False)
        self.assertFalse(s.lineas(self.ana)[0]["hay_stock"])
        self.client.login(username="ana@correo.test", password=CLAVE)
        self.assertTrue(self.client.get("/carrito/").context["sin_stock"])


class DobleEnvio(Base):
    def test_confirmar_dos_veces_crea_una_sola_orden_y_descuenta_una_vez(self):
        self.client.login(username="ana@correo.test", password=CLAVE)
        s.agregar(self.ana, self.refrigerado.pk, 3)
        antes, ordenes = self.stock(self.refrigerado), Orden.objects.count()
        datos = {"direccion": self.direccion(self.ana)}
        self.assertIn("/pedidos/", self.client.post("/carrito/confirmar/", datos).url)
        segundo = self.client.post("/carrito/confirmar/", datos, follow=True)
        self.assertContains(segundo, "Tu carrito está vacío")
        self.assertEqual((self.stock(self.refrigerado), Orden.objects.count()), (antes - 3, ordenes + 1))

    def test_cancelar_dos_veces_repone_el_stock_una_sola_vez(self):
        s.agregar(self.ana, self.refrigerado.pk, 3)
        antes = self.stock(self.refrigerado)
        orden = s.generar_orden(self.ana, self.direccion(self.ana))
        s.cancelar(orden)
        with self.assertRaises(s.ErrorDeNegocio):
            s.cancelar(orden)
        self.assertEqual(self.stock(self.refrigerado), antes)

    def test_agregar_dos_veces_suma_y_respeta_el_tope(self):
        s.agregar(self.ana, self.refrigerado.pk, 2)
        self.assertEqual(s.agregar(self.ana, self.refrigerado.pk, 3).cantidad, 5)
        with self.assertRaisesMessage(s.ErrorDeNegocio, "cantidad máxima"):
            s.agregar(self.ana, self.refrigerado.pk, 10000)


class FallaTecnica(Base):
    def test_si_falla_el_cobro_se_revierte_todo_y_el_carrito_sigue_abierto(self):
        """CU-04, A4: ni orden ni descuento."""
        s.agregar(self.ana, self.refrigerado.pk, 2)
        s.agregar(self.ana, self.congelado.pk, 1)
        stock, ordenes = (self.stock(self.refrigerado), self.stock(self.congelado)), Orden.objects.count()
        with patch("pedidos.servicios.documentos.cobrar_b2c", side_effect=[documentos.Documento(), RuntimeError("falló el cobro")]):
            with self.assertRaises(RuntimeError):
                s.generar_ordenes(self.ana, self.direccion(self.ana))
        self.assertEqual(((self.stock(self.refrigerado), self.stock(self.congelado)), Orden.objects.count()), (stock, ordenes))
        self.assertEqual(CarritoItem.objects.filter(carrito__cliente=self.ana, carrito__estado="abierto").count(), 2)


class RepetirCompraDividida(Base):
    def setUp(self):
        super().setUp()
        CarritoItem.objects.filter(carrito__cliente=self.hospital).delete()     # la demo deja un carrito armado
        Orden.objects.filter(direccion__cliente=self.hospital).update(creada_en=timezone.now() - timedelta(days=1))     # y órdenes recién creadas

    def test_repetir_trae_las_dos_ordenes_de_una_compra_mixta(self):
        s.agregar(self.hospital, self.refrigerado.pk, 2)
        s.agregar(self.hospital, self.congelado.pk, 1)
        self.assertEqual(len(s.generar_ordenes(self.hospital, self.direccion(self.hospital), "OC-1")), 2)
        s.repetir_ultimo_pedido(self.hospital)
        self.assertEqual({f["producto"].pk: f["cantidad"] for f in s.lineas(self.hospital)}, {self.refrigerado.pk: 2, self.congelado.pk: 1})

    def test_no_arrastra_una_compra_anterior(self):
        s.agregar(self.hospital, self.refrigerado.pk, 1)
        anterior = s.generar_orden(self.hospital, self.direccion(self.hospital), "OC-1")
        Orden.objects.filter(pk=anterior.pk).update(creada_en=anterior.creada_en.replace(year=anterior.creada_en.year - 1))
        s.agregar(self.hospital, self.congelado.pk, 1)
        s.generar_orden(self.hospital, self.direccion(self.hospital), "OC-2")
        s.repetir_ultimo_pedido(self.hospital)
        self.assertEqual([f["producto"].pk for f in s.lineas(self.hospital)], [self.congelado.pk])


class DireccionNueva(Base):
    def setUp(self):
        super().setUp()
        self.comuna = Comuna.objects.first()
        self.client.login(username="ana@correo.test", password=CLAVE)

    def test_el_cliente_agrega_una_direccion_y_compra_con_ella(self):
        with patch("clientes.geo.geocodificar", return_value=(-38.7, -72.6)):
            r = self.client.post("/carrito/direccion/", {"calle_numero": "Calle Nueva 123", "comuna": self.comuna.pk}, follow=True)
        self.assertContains(r, "Agregamos")
        nueva = Direccion.objects.get(cliente=self.ana, calle_numero="Calle Nueva 123")
        self.assertFalse(nueva.es_principal)                                    # ya tenía una principal
        s.agregar(self.ana, self.refrigerado.pk, 1)
        self.assertEqual(s.generar_orden(self.ana, nueva.pk).direccion, nueva)

    def test_sin_ubicar_se_guarda_y_avisa(self):
        with patch("clientes.geo.geocodificar", return_value=None):
            r = self.client.post("/carrito/direccion/", {"calle_numero": "No Existe 1", "comuna": self.comuna.pk}, follow=True)
        self.assertContains(r, "No pudimos ubicar")
        self.assertIsNone(Direccion.objects.get(calle_numero="No Existe 1").lat)

    def test_datos_invalidos_se_rechazan_sin_500(self):
        for datos in ({"calle_numero": "", "comuna": self.comuna.pk}, {"calle_numero": "x" * 151, "comuna": self.comuna.pk},
                      {"calle_numero": "Calle 1", "comuna": "abc"}, {"calle_numero": "Calle 1", "comuna": 999999}, {}):
            n = Direccion.objects.count()
            self.assertEqual(self.client.post("/carrito/direccion/", datos).status_code, 302)
            self.assertEqual(Direccion.objects.count(), n)

    def test_la_primera_direccion_queda_como_principal_y_hay_un_tope(self):
        sin = Cliente.objects.create(tipo_cliente=self.ana.tipo_cliente, rut="11.111.111-1", nombre="Sin dirección", email="s@x.test")
        with patch("clientes.geo.geocodificar", return_value=None):
            self.assertTrue(s.agregar_direccion(sin, "Calle 1", self.comuna.pk).es_principal)
            for i in range(s.MAX_DIRECCIONES - 1):
                s.agregar_direccion(sin, f"Calle {i + 2}", self.comuna.pk)
            with self.assertRaisesMessage(s.ErrorDeNegocio, "hasta"):
                s.agregar_direccion(sin, "Una más", self.comuna.pk)

    def test_una_cuenta_del_equipo_no_agrega_direcciones_de_cliente(self):
        self.client.logout()
        self.client.login(username="vendedora@cofrial.cl", password=CLAVE)
        self.assertEqual(self.client.post("/carrito/direccion/", {"calle_numero": "x", "comuna": self.comuna.pk}).status_code, 403)


class AgregarConcurrente(TransactionTestCase):
    def test_cuatro_agregar_a_la_vez_suman_todos(self):
        call_command("cargar_demo", verbosity=0)
        ana = Cliente.objects.get(rut="12.345.678-5")
        producto = Producto.objects.filter(activo=True, stock_disponible__gt=20).first()
        s.agregar(ana, producto.pk, 1)

        def una_vez():
            try:
                s.agregar(ana, producto.pk, 1)
            finally:
                connection.close()
        hilos = [threading.Thread(target=una_vez) for _ in range(4)]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertEqual(CarritoItem.objects.get(carrito__cliente=ana, producto=producto).cantidad, 5)
