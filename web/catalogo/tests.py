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


class FormatoChilenoTests(TestCase):
    def test_precios_con_punto_y_sin_clp(self):
        from catalogo.templatetags.formato import clp, con_iva, iva, miles
        self.assertEqual(clp(34990), "$34.990")
        self.assertEqual(clp(1234567), "$1.234.567")
        self.assertEqual(clp(0), "$0")
        self.assertEqual(miles(5000), "5.000")
        self.assertEqual(iva(100000), "$19.000")
        self.assertEqual(con_iva(100000), "$119.000")

    def test_el_catalogo_muestra_el_precio_sin_clp(self):
        call_command("cargar_demo", verbosity=0)
        r = self.client.get("/catalogo/")
        self.assertContains(r, "$45.990")
        self.assertNotContains(r, "CLP")


class SvgSeguroTests(TestCase):
    def test_conserva_formas_y_descarta_scripts_y_enlaces(self):
        from catalogo.svg_seguro import limpiar
        sucio = ('<svg viewBox="0 0 160 120" onload="alert(1)"><script>alert(1)</script><image href="http://x/y.png"/>'
                 '<circle cx="10" cy="10" r="5" fill="#fff" onclick="x()"/><rect x="1" y="1" width="5" height="5" fill="url(http://x)"/>'
                 '<path d="M0 0L5 5" stroke="#000"/><ellipse cx="3" cy="3" rx="2" ry="1"/></svg>')
        limpio = limpiar("Aquí va: " + sucio)
        for malo in ("script", "image", "onload", "onclick", "http://x", "url(", "href"):
            self.assertNotIn(malo, limpio)
        self.assertIn("<circle", limpio)
        self.assertIn("<path", limpio)

    def test_rechaza_entidades_xml_mal_formado_y_vacios(self):
        from catalogo.svg_seguro import SvgInvalido, limpiar
        for malo in ('<!DOCTYPE svg [<!ENTITY a "b">]><svg><g/></svg>', "<svg><g></svg>", "hola", "", "<svg><circle/></svg>"):
            with self.assertRaises(SvgInvalido):
                limpiar(malo)


class IlustracionIATests(TestCase):
    def test_comando_guarda_el_svg_validado_con_el_modelo(self):
        import json, tempfile
        from pathlib import Path
        from unittest.mock import patch

        from django.test import override_settings
        call_command("cargar_demo", verbosity=0)
        svg = '{"svg": "<svg viewBox=\\"0 0 160 120\\"><circle cx=\\"1\\" cy=\\"1\\" r=\\"1\\"/><rect x=\\"1\\" y=\\"1\\" width=\\"2\\" height=\\"2\\"/><path d=\\"M0 0L1 1\\"/></svg>"}'
        with tempfile.TemporaryDirectory() as d, override_settings(BASE_DIR=Path(d)), \
                patch("crm.ia._llamar", return_value=svg), patch("crm.ia.ultimo_modelo", "Gemini prueba"), patch("time.sleep"):
            call_command("generar_ilustraciones", sku="MAR-CAM-1K", verbosity=0)
            self.assertTrue((Path(d) / "static/productos/ia/MAR-CAM-1K.svg").exists())
            self.assertEqual(json.loads((Path(d) / "static/productos/ia/creditos.json").read_text())["MAR-CAM-1K"]["modelo"], "Gemini prueba")
