"""Contador de pedidos por despachar en el menú interno, y el límite conocido de la capacidad en kg."""
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.db.models import Q
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from catalogo.models import Categoria, Producto
from crm.tests import CLAVE
from flota import servicios, sugerencias
from flota.models import Camion
from flota.tests_autodespacho import CONGELADO, REFRIGERADO, pedido
from pedidos.models import EstadoOrden, Orden

URL = "/flota/por-despachar/"
DETALLE = URL + "?detalle=1"
EQUIPO_FLOTA = ("despacho@cofrial.cl", "admin@cofrial.cl", "gerencia@cofrial.cl")
SIN_FLOTA = ("vendedora@cofrial.cl", "abastecimiento@hospital.test", "ana@correo.test")


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario="despacho@cofrial.cl"):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c


class ContadorTests(Base):
    def test_el_contador_sigue_a_los_pedidos(self):
        c = self.entrar()
        antes = c.get(URL).json()["total"]
        orden = pedido()
        self.assertEqual(c.get(URL).json()["total"], antes + 1)
        camion = next(x for x in servicios.camiones_libres() if x.rango_temperatura.nombre == "Refrigerado")
        servicios.despachar(camion.camion_id, [orden.pk])
        self.assertEqual(c.get(URL).json()["total"], antes)

    def test_cuenta_lo_mismo_que_armar_despacho(self):
        pedido()
        self.assertEqual(self.entrar().get(URL).json()["total"], len(servicios.pedidos_por_despachar()))

    def test_una_entrega_no_concretada_vuelve_a_contar(self):
        c = self.entrar()
        orden = pedido()
        camion = next(x for x in servicios.camiones_libres() if x.rango_temperatura.nombre == "Refrigerado")
        servicios.despachar(camion.camion_id, [orden.pk])
        antes = c.get(URL).json()["total"]
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entrega no concretada"))
        self.assertEqual(c.get(URL).json()["total"], antes + 1)

    def test_la_consulta_periodica_es_un_solo_conteo_y_no_llama_a_la_ia(self):
        pedido()
        c = self.entrar()
        with patch("flota.views.sugerencias.calcular") as calcular, patch("crm.ia.redactar") as redactar, CaptureQueriesContext(connection) as consultas:
            datos = c.get(URL).json()
        calcular.assert_not_called()
        redactar.assert_not_called()
        self.assertEqual(set(datos), {"total"})
        textos = [q["sql"] for q in consultas]
        self.assertEqual(sum('FROM "orden"' in s for s in textos), 1, textos)
        self.assertIn("COUNT(", next(s for s in textos if 'FROM "orden"' in s))
        for tabla in ("telemetria", "orden_item", "producto", "camion"):
            self.assertFalse(any(f'"{tabla}"' in s for s in textos), f"la consulta periódica no debe tocar {tabla}")

    def test_solo_acepta_lecturas(self):
        self.assertEqual(self.entrar().post(URL).status_code, 405)


class AccesoTests(Base):
    def test_el_rol_con_flota_entra(self):
        for usuario in EQUIPO_FLOTA:
            with self.subTest(usuario=usuario):
                self.assertEqual(self.entrar(usuario).get(URL).status_code, 200)

    def test_el_rol_sin_flota_queda_fuera(self):
        pedido()
        for usuario in SIN_FLOTA:
            for url in (URL, DETALLE):
                with self.subTest(usuario=usuario, url=url):
                    r = self.entrar(usuario).get(url)
                    self.assertEqual(r.status_code, 403)
                    self.assertTrue(r["Content-Type"].startswith("text/html"), "un 403 no debe traer el dato en JSON")
                    self.assertNotIn('"total"', r.content.decode())

    def test_sin_sesion_manda_a_ingresar(self):
        r = Client().get(URL)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/cuenta/entrar/"))

    def test_el_menu_trae_el_contador_solo_a_quien_ve_flota(self):
        for usuario, pagina in (("despacho@cofrial.cl", "/flota/"), ("admin@cofrial.cl", "/crm/"), ("gerencia@cofrial.cl", "/crm/")):
            with self.subTest(usuario=usuario):
                html = self.entrar(usuario).get(pagina).content.decode()
                self.assertIn('id="despacho-n"', html)
                self.assertIn("js/por-despachar", html)
        for usuario, pagina in (("vendedora@cofrial.cl", "/crm/"), ("abastecimiento@hospital.test", "/pedidos/"), ("ana@correo.test", "/pedidos/")):
            with self.subTest(usuario=usuario):
                html = self.entrar(usuario).get(pagina).content.decode()
                self.assertNotIn("despacho-n", html)
                self.assertNotIn("js/por-despachar", html)


class DetalleTests(Base):
    def test_dice_que_camion_conviene_y_lleva_a_armar_despacho(self):
        pedido()
        c = self.entrar()
        d = c.get(DETALLE).json()
        viajes, _ = sugerencias.calcular()
        self.assertEqual(d["total"], len(servicios.pedidos_por_despachar()))
        self.assertIn(viajes[0]["camion"], d["texto"])
        urls = [a["url"] for a in d["acciones"]]
        self.assertTrue(any(u.startswith(f"/flota/despachar/?camion={viajes[0]['camion']}&ordenes=") for u in urls), urls)
        self.assertIn("/flota/despachar/", urls)
        self.assertIn("/flota/", urls)
        for u in urls:
            self.assertEqual(c.get(u).status_code, 200, u)

    def test_avisa_si_no_hay_camion_libre_de_ese_rango(self):
        pedido(CONGELADO)
        congelados = Camion.objects.filter(Q(rango_temperatura__nombre="Congelado") | Q(rango_secundario__nombre="Congelado"))
        ids = list(congelados.values_list("camion_id", flat=True))
        congelados.update(activo=False)
        d = self.entrar().get(DETALLE).json()
        self.assertIn("congelado(s) sin camión libre de ese rango", d["texto"])
        self.assertFalse([a for a in d["acciones"] if any(f"camion={i}&" in a["url"] for i in ids)], "propuso un camión inactivo")

    def test_no_gasta_la_cuota_de_la_ia(self):
        pedido()
        with patch("crm.ia.redactar") as redactar:
            self.assertTrue(self.entrar().get(DETALLE).json()["texto"])
        redactar.assert_not_called()

    def test_gerencia_ve_la_sugerencia_pero_no_recibe_enlaces_para_armar(self):
        pedido()
        d = self.entrar("gerencia@cofrial.cl").get(DETALLE).json()
        self.assertTrue(d["texto"])
        self.assertEqual([a["url"] for a in d["acciones"]], ["/flota/"])

    def test_limita_los_viajes_ofrecidos_para_no_llenar_el_menu(self):
        for _ in range(3):
            pedido(REFRIGERADO)
        d = self.entrar().get(DETALLE).json()
        self.assertLessEqual(sum("camion=" in a["url"] for a in d["acciones"]), 3)

    def test_no_despacha_nada(self):
        orden = pedido()
        self.entrar().get(DETALLE)
        orden.refresh_from_db()
        self.assertIsNone(orden.despacho_id)


class CapacidadSinPesoTests(Base):
    """Límite conocido (docs/decisiones.md): sin peso por producto no se puede sumar un viaje. Si esta clase falla porque alguien agregó el peso,
    toca implementar la regla en `despachar`, `sugerencias.calcular` y `autodespacho`, y reemplazar estas pruebas por las de la regla."""

    def test_producto_no_tiene_un_campo_de_peso(self):
        campos = {f.name for f in Producto._meta.get_fields()}
        self.assertFalse({c for c in campos if "peso" in c or c.endswith("_kg")}, campos)

    def test_el_sku_no_sirve_de_peso_porque_es_texto_libre(self):
        Producto(sku="QUE-GOUDA", nombre="Queso gauda", categoria=Categoria.objects.first(), unidad_medida="caja").full_clean()

    def test_ninguna_unidad_del_catalogo_dice_cuanto_pesa_la_venta(self):
        self.assertEqual(set(Producto.objects.values_list("unidad_medida", flat=True)), {"caja"})

    def test_despachar_y_sugerir_todavia_no_miran_la_capacidad(self):
        orden = pedido()
        camion = next(x for x in servicios.camiones_libres() if x.rango_temperatura.nombre == "Refrigerado")
        Camion.objects.filter(rango_temperatura__nombre="Refrigerado").update(capacidad_kg=1)
        self.assertTrue(sugerencias.calcular()[0])
        self.assertEqual(servicios.despachar(camion.camion_id, [orden.pk]).camion_id, camion.camion_id)
