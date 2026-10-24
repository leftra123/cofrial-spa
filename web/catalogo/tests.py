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
        self.assertContains(r, 'src="/static/productos/propias/POL-PEC-10K.jpg"')      # imagen propia: tiene prioridad
        from catalogo.models import Producto
        self.assertContains(self.client.get(f"/catalogo/{Producto.objects.get(sku='POL-PEC-10K').pk}/"), "Imagen referencial del producto")


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


class ImagenPropiaTests(TestCase):
    def test_imagen_propia_tiene_prioridad_y_se_acredita_como_ia(self):
        import tempfile
        from pathlib import Path

        from django.test import override_settings
        call_command("cargar_demo", verbosity=0)
        from catalogo.models import Producto
        p = Producto.objects.get(sku="POL-PEC-10K")
        with tempfile.TemporaryDirectory() as d, override_settings(BASE_DIR=Path(d)):
            (Path(d) / "static/productos/propias").mkdir(parents=True)
            (Path(d) / "static/productos/propias/POL-PEC-10K.png").write_bytes(b"x")
            r = self.client.get(f"/catalogo/{p.pk}/")
            self.assertContains(r, "productos/propias/POL-PEC-10K.png")
            self.assertContains(r, "Imagen referencial del producto")


class ApiProductos(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_ficha_por_sku_sin_precios(self):
        r = self.client.get("/api/productos/vac-lom-5k/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["sku"], "VAC-LOM-5K")
        self.assertEqual(d["categoria"], "Cárnicos refrigerados")
        self.assertEqual(d["conservacion"]["temp_max_c"], 4.0)
        self.assertNotIn("precio", r.content.decode().lower())

    def test_sku_inexistente_da_404_y_el_listado_trae_todos(self):
        self.assertEqual(self.client.get("/api/productos/NO-EXISTE/").status_code, 404)
        self.assertEqual(len(self.client.get("/api/productos/").json()["productos"]), 20)


class AvisoStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _entrar(self, usuario="ana@correo.test"):
        self.client.login(username=usuario, password="demo-cofrial-2026")

    def _camarones(self):
        from catalogo.models import Producto
        return Producto.objects.get(sku="MAR-CAM-1K")          # sin stock en la demostración

    def test_cliente_pide_aviso_y_se_ve_en_mis_avisos(self):
        p = self._camarones()
        self._entrar()
        r = self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 5, "volver": "/catalogo/"}, follow=True)
        self.assertContains(r, "te avisaremos cuando haya al menos 5")
        pagina = self.client.get("/avisos/")
        self.assertContains(pagina, "Esperando stock")
        self.assertContains(pagina, p.nombre)

    def test_pedir_dos_veces_actualiza_la_cantidad_sin_duplicar(self):
        from catalogo.models import AvisoStock
        p = self._camarones()
        self._entrar()
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 5})
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 8})
        self.assertEqual(AvisoStock.objects.filter(producto=p).count(), 1)
        self.assertEqual(AvisoStock.objects.get(producto=p).cantidad_minima, 8)

    def test_no_se_pide_aviso_si_ya_hay_stock_suficiente(self):
        from catalogo.models import AvisoStock, Producto
        p = Producto.objects.get(sku="POL-PEC-10K")
        self._entrar()
        r = self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 1}, follow=True)
        self.assertContains(r, "Ya hay")
        self.assertFalse(AvisoStock.objects.exists())

    def test_cuando_llega_stock_aparece_como_disponible_y_avisa_en_la_barra(self):
        p = self._camarones()
        self._entrar()
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 5})
        self.assertNotContains(self.client.get("/catalogo/"), "Ya hay stock de")
        p.stock_disponible = 7
        p.save(update_fields=["stock_disponible"])
        self.assertContains(self.client.get("/catalogo/"), "Ya hay stock de 1 producto")
        self.assertContains(self.client.get("/avisos/"), "Ya disponible")

    def test_agregar_al_carrito_da_el_aviso_por_atendido(self):
        from catalogo.models import AvisoStock
        p = self._camarones()
        self._entrar()
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 3})
        p.stock_disponible = 10
        p.save(update_fields=["stock_disponible"])
        self.client.post("/carrito/agregar/", {"producto": p.pk, "cantidad": 3})
        self.assertIsNotNone(AvisoStock.objects.get(producto=p).atendido_en)
        self.assertNotContains(self.client.get("/avisos/"), "Esperando stock")

    def test_un_cliente_no_ve_ni_quita_avisos_ajenos(self):
        from catalogo.models import AvisoStock
        p = self._camarones()
        self._entrar("ana@correo.test")
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 5})
        aviso = AvisoStock.objects.get()
        self.client.logout()
        self._entrar("abastecimiento@hospital.test")
        self.assertNotContains(self.client.get("/avisos/"), p.nombre)
        self.client.post(f"/avisos/{aviso.pk}/quitar/")
        self.assertTrue(AvisoStock.objects.filter(pk=aviso.pk).exists())

    def test_visitante_es_enviado_a_ingresar_y_el_crm_ve_la_demanda(self):
        p = self._camarones()
        self.assertEqual(self.client.get("/avisos/").status_code, 302)
        self.assertContains(self.client.get("/catalogo/"), "Ingresa para pedir aviso")
        self._entrar()
        self.client.post("/avisos/pedir/", {"producto": p.pk, "cantidad": 6})
        self.client.logout()
        self._entrar("vendedora@cofrial.cl")
        r = self.client.get("/crm/demanda/")
        self.assertContains(r, "Camarones")
        self.assertContains(r, "Sin stock: reponer")
        self.client.logout()
        self._entrar("ana@correo.test")
        self.assertEqual(self.client.get("/crm/demanda/").status_code, 403)


class PortadaYCategoriasTests(TestCase):
    def test_portada_y_fotos_de_categoria(self):
        call_command("cargar_demo", verbosity=0)
        r = self.client.get("/")
        self.assertContains(r, "con-foto")
        self.assertContains(r, "static/img/portada.jpg")
        for slug in ("carnicos-refrigerados", "aves", "congelados", "lacteos-y-embutidos"):
            self.assertContains(r, f"/static/productos/categorias/{slug}.jpg")


class GuiaYMapaTests(TestCase):
    def test_guia_publica_con_los_cuatro_flujos_y_el_estado(self):
        call_command("cargar_demo", verbosity=0)
        r = self.client.get("/guia/")
        self.assertEqual(r.status_code, 200)
        for texto in ("Un cliente compra y sigue su pedido", "Despacho arma un viaje", "Ventas atiende un reclamo", "Un producto sin stock",
                      "esperando camión", "/flota/despachar/", "/crm/demanda/"):
            self.assertContains(r, texto)
        self.assertNotContains(r, "123456")                     # la guía no publica claves

    def test_el_mapa_dibuja_camion_destino_y_bodega(self):
        import re
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent / "static" / "js" / "mapa.js").read_text()
        for funcion in ("camion", "destino", "base"):
            self.assertIn(f"function {funcion}(", js)
        self.assertRegex(js, r"return \{[^}]*camion: camion[^}]*destino: destino[^}]*base: base")


class EtiquetaTemperaturaTests(TestCase):
    def test_la_etiqueta_muestra_el_rango_con_ícono_y_sin_pastilla_de_punto(self):
        call_command("cargar_demo", verbosity=0)
        r = self.client.get("/catalogo/")
        self.assertContains(r, 'class="etq-temp refrigerado"')
        self.assertContains(r, 'class="etq-temp congelado"')
        self.assertContains(r, "0 a 4 °C")
        self.assertContains(r, "-25 a -18 °C")
        self.assertNotContains(r, "generada con IA")
