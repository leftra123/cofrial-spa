from django.core.management import call_command
from django.test import TestCase


class CatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _precio_lomo(self, contenido):
        import re
        return re.search(r'data-sku="VAC-LOM-5K"\s+data-precio="(\d+)"', contenido).group(1)

    def test_visitante_ve_lista_publica(self):
        r = self.client.get("/catalogo/")
        self.assertContains(r, "Público B2C")
        self.assertIn("45", self._precio_lomo(r.content.decode()))      # 45.990

    def test_cliente_institucional_ve_su_lista(self):
        self.client.login(username="abastecimiento@hospital.test", password="demo-cofrial-2026")
        r = self.client.get("/catalogo/")
        self.assertContains(r, "Institucional B2B")
        self.assertIn("38", self._precio_lomo(r.content.decode()))      # 38.990

    def test_carga_demo_es_idempotente(self):
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(self.client.get("/salud/").status_code, 200)


class TiendaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_hay_entre_15_y_20_productos_en_4_categorias(self):
        from catalogo.models import Categoria, Producto
        self.assertTrue(15 <= Producto.objects.filter(activo=True).count() <= 20)
        self.assertEqual(Categoria.objects.count(), 4)

    def test_cargar_demo_dos_veces_no_duplica(self):
        from catalogo.models import Producto
        n = Producto.objects.count()
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(Producto.objects.count(), n)

    def test_filtra_por_categoria_y_temperatura(self):
        from catalogo.models import Categoria
        aves = Categoria.objects.get(nombre="Aves")
        r = self.client.get(f"/catalogo/?categoria={aves.pk}")
        self.assertContains(r, "Pollo entero")
        self.assertNotContains(r, "Lomo vetado")
        r = self.client.get("/catalogo/?temperatura=" + str(aves.rango_temperatura_id))
        self.assertNotContains(r, "Filete de salmón")

    def test_busca_por_nombre_y_sku(self):
        self.assertContains(self.client.get("/catalogo/?q=salmón"), "Filete de salmón")
        self.assertContains(self.client.get("/catalogo/?q=POL-ENT"), "Pollo entero")
        self.assertContains(self.client.get("/catalogo/?q=zzzz"), "No encontramos productos")

    def test_solo_con_stock_oculta_sin_stock(self):
        self.assertContains(self.client.get("/catalogo/"), "Camarones")
        self.assertNotContains(self.client.get("/catalogo/?stock=1"), "Camarones")

    def test_detalle_muestra_rango_de_conservacion(self):
        from catalogo.models import Producto
        p = Producto.objects.get(sku="VAC-LOM-5K")
        r = self.client.get(f"/catalogo/{p.pk}/")
        self.assertContains(r, "Conservación")
        self.assertContains(r, "0 a 4")
        self.assertEqual(self.client.get("/catalogo/99999/").status_code, 404)

    def test_visitante_no_ve_boton_agregar(self):
        r = self.client.get("/catalogo/")
        self.assertNotContains(r, 'action="/carrito/agregar/"')
        self.assertContains(r, "Ingresar para comprar")

    def test_fotos_con_credito_y_respaldo_de_ilustracion(self):
        r = self.client.get("/catalogo/")
        self.assertContains(r, 'src="/static/productos/POL-PEC-10K.jpg"')      # tiene foto descargada
        self.assertContains(r, "<svg")                                         # los sin foto usan ilustración
        from catalogo.models import Producto
        p = Producto.objects.get(sku="POL-PEC-10K")
        self.assertContains(self.client.get(f"/catalogo/{p.pk}/"), "Wikimedia Commons")
