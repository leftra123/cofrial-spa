"""Ficha y tarjetas del catálogo: stock con número, compra mínima junto a la cantidad, relacionados compactos y el aviso de que una
compra con congelados y refrigerados se separa en pedidos que pueden llegar en camiones distintos."""
from django.core.management import call_command
from django.test import TestCase

from catalogo import views
from catalogo.models import Producto
from clientes.models import Cliente
from pedidos import servicios
from pedidos.models import EstadoOrden, Orden, OrdenItem

CLAVE = "demo-cofrial-2026"


class FichaDeCompra(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")              # refrigerado
        cls.verduras = Producto.objects.get(sku="VER-MIX-10K")          # congelado

    def test_la_ficha_dice_minimo_y_disponible_junto_a_la_compra(self):
        r = self.client.get(f"/catalogo/{self.verduras.pk}/")
        disponibles = views.en_unidades(self.verduras, self.verduras.stock_disponible)
        self.assertContains(r, f"Compra mínima: 1 caja · Disponibles: {disponibles}")
        self.assertContains(r, f'data-tope="Es todo el stock disponible: {disponibles}."')

    def test_la_tarjeta_muestra_cuanto_stock_hay(self):
        Producto.objects.filter(pk=self.lomo.pk).update(stock_disponible=91)
        Producto.objects.filter(pk=self.verduras.pk).update(stock_disponible=7)
        r = self.client.get("/catalogo/")
        self.assertContains(r, "91 cajas en stock")
        self.assertContains(r, "Quedan 7 cajas")
        self.assertContains(r, "Compra mínima: 1 caja")

    def test_unidades_en_singular_y_plural(self):
        self.assertEqual(views.en_unidades(self.lomo, 1), "1 caja")
        self.assertEqual(views.en_unidades(Producto(unidad_medida="un"), 3), "3 unidades")
        self.assertEqual(views.en_unidades(Producto(unidad_medida="kg"), 12), "12 kg")

    def test_sin_stock_no_ofrece_compra_minima(self):
        Producto.objects.filter(pk=self.verduras.pk).update(stock_disponible=0)
        r = self.client.get(f"/catalogo/{self.verduras.pk}/")
        self.assertNotContains(r, "Compra mínima: 1 caja · Disponibles")        # la nota de la ficha; las tarjetas de otros productos sí la llevan
        self.assertContains(r, "Sin stock por ahora")

    def test_los_relacionados_van_en_tira_compacta(self):
        html = self.client.get(f"/catalogo/{self.verduras.pk}/").content.decode()
        self.assertIn('<div class="tira">', html)
        self.assertNotIn('class="productos"', html)        # en el catálogo agrupado `.productos` es un bloque: dejaba la foto a todo el ancho


class SuelenPedirseJuntos(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")
        cls.molida = Producto.objects.get(sku="VAC-MOL-5K")
        cls.posta = Producto.objects.get(sku="VAC-POS-5K")
        cls.direccion = Cliente.objects.get(rut="12.345.678-5").direccion_set.first()
        OrdenItem.objects.all().delete()                   # solo cuentan los pedidos de esta prueba

    def _pedido(self, *productos, estado="Entregada"):
        orden = Orden.objects.create(direccion=self.direccion, estado_orden=EstadoOrden.objects.get(nombre=estado))
        OrdenItem.objects.bulk_create([OrdenItem(orden=orden, producto=p, cantidad=1, precio_unitario_clp=1000) for p in productos])

    def test_cuenta_desde_dos_pedidos_en_comun(self):
        self._pedido(self.lomo, self.molida)
        self._pedido(self.lomo, self.molida)
        self._pedido(self.lomo, self.posta)                # una sola coincidencia no es costumbre
        self.assertEqual(views.suelen_pedirse_con(self.lomo), [self.molida])

    def test_no_cuenta_los_cancelados_ni_los_inactivos(self):
        self._pedido(self.lomo, self.molida)
        self._pedido(self.lomo, self.molida, estado="Cancelada")
        self._pedido(self.lomo, self.posta)
        self._pedido(self.lomo, self.posta)
        Producto.objects.filter(pk=self.posta.pk).update(activo=False)
        self.assertEqual(views.suelen_pedirse_con(self.lomo), [])

    def test_la_ficha_los_muestra_y_no_los_repite_en_la_categoria(self):
        self._pedido(self.lomo, self.molida)
        self._pedido(self.lomo, self.molida)
        r = self.client.get(f"/catalogo/{self.lomo.pk}/")
        self.assertContains(r, "Suelen pedirse junto con este producto")
        self.assertEqual(r.content.decode().count(f'data-sku="{self.molida.sku}"'), 1)

    def test_sin_historial_no_aparece_la_seccion(self):
        self.assertNotContains(self.client.get(f"/catalogo/{self.lomo.pk}/"), "Suelen pedirse junto")


class AvisoDeTemperaturasDistintas(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")
        cls.molida = Producto.objects.get(sku="VAC-MOL-5K")
        cls.verduras = Producto.objects.get(sku="VER-MIX-10K")

    def setUp(self):
        self.client.login(username="ana@correo.test", password=CLAVE)

    def _agregar(self, producto):
        return self.client.post("/carrito/agregar/", {"producto": producto.pk, "cantidad": 1}, headers={"X-Requested-With": "fetch"}).json()

    def test_avisa_una_vez_al_mezclar_congelados_y_refrigerados(self):
        self.assertEqual([m["tipo"] for m in self._agregar(self.lomo)["mensajes"]], ["success"])
        mezcla = self._agregar(self.verduras)["mensajes"]
        self.assertEqual([m["tipo"] for m in mezcla], ["success", "info"])
        self.assertIn("congelados y refrigerados", mezcla[1]["texto"])
        self.assertIn("pueden llegar en camiones distintos", mezcla[1]["texto"])
        self.assertEqual([m["tipo"] for m in self._agregar(self.molida)["mensajes"]], ["success"])      # ya se avisó: no se repite

    def test_el_carrito_lo_explica_con_el_mismo_texto(self):
        self._agregar(self.lomo)
        self.assertNotContains(self.client.get("/carrito/"), "camiones distintos")
        self._agregar(self.verduras)
        r = self.client.get("/carrito/")
        self.assertContains(r, "Tu compra lleva congelados y refrigerados. Como viajan a temperaturas distintas, la separamos en 2 pedidos")
        self.assertContains(r, "Sigues cada pedido por separado en «Mis pedidos»")

    def test_un_solo_rango_no_lleva_aviso(self):
        self.assertEqual(servicios.aviso_de_rangos(["Refrigerado"]), "")
        self.assertEqual(servicios.aviso_de_rangos([]), "")
