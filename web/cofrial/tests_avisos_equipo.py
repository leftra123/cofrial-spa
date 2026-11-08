"""Avisos en tiempo real de cada tipo de usuario y flujo de permisos del navegador."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from catalogo.models import AvisoStock, Producto
from clientes.models import Cliente, Comuna, Vendedor
from cofrial import avisos_equipo
from crm.models import Requerimiento
from crm.tests import CLAVE
from flota import servicios
from flota.models import Telemetria
from flota.tests_autodespacho import pedido
from pedidos import documentos
from pedidos import servicios as pedidos
from pedidos.models import EstadoOrden, Orden

URL = "/api/avisos-equipo/"
DESPACHO, VENDEDORA, GERENCIA, ADMIN = "despacho@cofrial.cl", "vendedora@cofrial.cl", "gerencia@cofrial.cl", "admin@cofrial.cl"
B2B, B2C = "abastecimiento@hospital.test", "ana@correo.test"
HOSPITAL = "61.973.200-4"
VENDEDOR_EXTRA = {}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c

    def avisos(self, usuario):
        return {a["id"]: a for a in self.entrar(usuario).get(URL).json()["avisos"]}

    def viaje_con_ruptura(self):
        orden = pedido()
        camion = next(x for x in servicios.camiones_libres() if x.rango_temperatura.nombre == "Refrigerado")
        despacho = servicios.despachar(camion.camion_id, [orden.pk])
        Telemetria.objects.create(camion=camion, temp_camara=9.0, lat=-38.7, long=-72.6, combustible_pct=70, alerta_ruptura_frio=True)
        return orden, despacho


class QuienVeQueTests(Base):
    def test_cada_rol_recibe_solo_lo_suyo(self):
        self.viaje_con_ruptura()
        pedido()
        Requerimiento.objects.create(cliente=Cliente.objects.get(rut=HOSPITAL), asunto="Reclamo", descripcion="Llegó abierto")
        vistos = {u: set(self.avisos(u)) for u in (DESPACHO, VENDEDORA, GERENCIA, ADMIN)}
        self.assertEqual(vistos[DESPACHO], {"por_despachar", "frio"})
        self.assertNotIn("por_despachar", vistos[VENDEDORA])
        self.assertIn("reclamos", vistos[VENDEDORA])
        self.assertIn("frio", vistos[VENDEDORA])
        for u in (GERENCIA, ADMIN):
            self.assertLessEqual({"por_despachar", "frio", "reclamos"}, vistos[u])

    def test_el_cliente_y_el_anonimo_no_entran(self):
        for u in (B2B, B2C):
            with self.subTest(u=u):
                self.assertEqual(self.entrar(u).get(URL).status_code, 403)
        self.assertEqual(Client().get(URL).status_code, 403)

    def test_solo_acepta_lecturas(self):
        self.assertEqual(self.entrar(ADMIN).post(URL).status_code, 405)

    def test_sin_novedades_no_aparece_el_aviso(self):
        Orden.objects.filter(pk__in=[o.pk for o in servicios.pedidos_por_despachar()]).update(estado_orden=EstadoOrden.objects.filter(es_final=True).first())
        self.assertNotIn("por_despachar", self.avisos(DESPACHO))

    def test_todos_los_enlaces_abren_para_ese_rol(self):
        self.viaje_con_ruptura()
        pedido()
        Requerimiento.objects.create(cliente=Cliente.objects.get(rut=HOSPITAL), asunto="Reclamo", descripcion="Llegó abierto")
        for u in (DESPACHO, VENDEDORA, GERENCIA, ADMIN):
            c = self.entrar(u)
            for a in c.get(URL).json()["avisos"]:
                with self.subTest(u=u, aviso=a["id"]):
                    self.assertEqual(c.get(a["url"]).status_code, 200, a["url"])

    def test_gerencia_no_recibe_enlaces_para_armar_viajes(self):
        pedido()
        self.assertEqual(self.avisos(GERENCIA)["por_despachar"]["url"], "/flota/")
        self.assertEqual(self.avisos(DESPACHO)["por_despachar"]["url"], "/flota/despachar/")


class ContenidoTests(Base):
    def test_el_conteo_sigue_a_los_datos_sin_recargar(self):
        c = self.entrar(DESPACHO)
        antes = {a["id"]: a["n"] for a in c.get(URL).json()["avisos"]}.get("por_despachar", 0)
        pedido()
        self.assertEqual({a["id"]: a["n"] for a in c.get(URL).json()["avisos"]}["por_despachar"], antes + 1)

    def test_el_frio_cuenta_viajes_en_curso_y_es_urgente(self):
        _, despacho = self.viaje_con_ruptura()
        frio = self.avisos(DESPACHO)["frio"]
        self.assertEqual(frio["n"], 1)
        self.assertTrue(frio["urgente"])
        despacho.llegada_en = timezone.now()
        despacho.save(update_fields=["llegada_en"])
        self.assertNotIn("frio", self.avisos(DESPACHO))

    def test_una_alerta_de_un_viaje_anterior_no_cuenta(self):
        orden = pedido()
        camion = next(x for x in servicios.camiones_libres() if x.rango_temperatura.nombre == "Refrigerado")
        t = Telemetria.objects.create(camion=camion, temp_camara=9.0, lat=-38.7, long=-72.6, combustible_pct=70, alerta_ruptura_frio=True)
        Telemetria.objects.filter(pk=t.pk).update(registrado_en=timezone.now() - timedelta(hours=2))
        servicios.despachar(camion.camion_id, [orden.pk])
        self.assertNotIn("frio", self.avisos(DESPACHO))

    def test_el_vendedor_solo_ve_el_frio_y_los_reclamos_de_su_cartera(self):
        hospital = Cliente.objects.get(rut=HOSPITAL)
        self.assertEqual(hospital.vendedor.usuario.username, VENDEDORA)
        self.viaje_con_ruptura()
        self.assertEqual(self.avisos(VENDEDORA)["frio"]["n"], 1)
        antes = self.avisos(VENDEDORA).get("reclamos", {"n": 0})["n"]
        otra = get_user_model().objects.create_user("otra@cofrial.cl", password=CLAVE)
        Cliente.objects.filter(pk=hospital.pk).update(vendedor=Vendedor.objects.create(usuario=otra, **VENDEDOR_EXTRA))
        self.assertNotIn("frio", self.avisos(VENDEDORA))
        Requerimiento.objects.create(cliente=hospital, asunto="Ajeno", descripcion="De otra cartera")
        self.assertLessEqual(self.avisos(VENDEDORA).get("reclamos", {"n": 0})["n"], antes)

    def test_un_reclamo_resuelto_deja_de_contar(self):
        r = Requerimiento.objects.create(cliente=Cliente.objects.get(rut=HOSPITAL), asunto="Reclamo", descripcion="Llegó abierto")
        antes = self.avisos(ADMIN)["reclamos"]["n"]
        Requerimiento.objects.filter(pk=r.pk).update(estado="resuelto")
        self.assertEqual(self.avisos(ADMIN).get("reclamos", {"n": 0})["n"], antes - 1)

    def test_entregas_sin_factura_y_facturas_vencidas(self):
        orden = pedido()
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        antes = self.avisos(ADMIN)["por_facturar"]["n"]
        factura = documentos.emitir_factura(Orden.objects.get(pk=orden.pk))
        self.assertEqual(self.avisos(ADMIN).get("por_facturar", {"n": 0})["n"], antes - 1)
        type(factura).objects.filter(pk=factura.pk).update(vence_en=timezone.localdate() - timedelta(days=3))
        self.assertGreaterEqual(self.avisos(ADMIN)["vencidas"]["n"], 1)


class CostoTests(Base):
    def test_la_consulta_periodica_es_barata_y_no_llama_a_la_ia(self):
        for _ in range(3):
            pedido()
        self.viaje_con_ruptura()
        c = self.entrar(ADMIN)
        c.get(URL)
        with patch("crm.ia.redactar") as redactar, CaptureQueriesContext(connection) as consultas:
            self.assertEqual(c.get(URL).status_code, 200)
        redactar.assert_not_called()
        self.assertLessEqual(len(consultas), 15, [q["sql"][:120] for q in consultas])     # medido: unos 5 ms en total

    def test_el_costo_no_crece_con_los_pedidos(self):
        self.viaje_con_ruptura()
        c = self.entrar(ADMIN)
        c.get(URL)
        with CaptureQueriesContext(connection) as uno:
            c.get(URL)
        for _ in range(4):
            self.viaje_con_ruptura()
        with CaptureQueriesContext(connection) as varios:
            c.get(URL)
        self.assertEqual(len(uno), len(varios))


class ClienteStockTests(Base):
    def test_el_cliente_recibe_el_stock_disponible_en_sus_avisos(self):
        cliente = Cliente.objects.get(rut=HOSPITAL)
        c = self.entrar(B2B)
        self.assertEqual(c.get("/api/avisos/").json()["stock_n"], 0)
        AvisoStock.objects.create(cliente=cliente, producto=Producto.objects.get(sku="VAC-LOM-5K"), cantidad_minima=1)
        self.assertEqual(c.get("/api/avisos/").json()["stock_n"], 1)


class MenuYPermisosTests(Base):
    def test_el_equipo_tiene_campana_y_el_cliente_conserva_la_suya(self):
        for u, pagina in ((DESPACHO, "/flota/"), (VENDEDORA, "/crm/"), (GERENCIA, "/crm/"), (ADMIN, "/crm/")):
            with self.subTest(u=u):
                html = self.entrar(u).get(pagina).content.decode()
                self.assertIn('id="avisos-equipo-btn"', html)
                self.assertIn("js/avisos-equipo", html)
                self.assertIn('id="toasts"', html)
        for u in (B2B, B2C):
            with self.subTest(u=u):
                html = self.entrar(u).get("/pedidos/").content.decode()
                self.assertIn('id="campana-btn"', html)
                self.assertNotIn("avisos-equipo", html)

    def test_todas_las_cuentas_con_sesion_tienen_el_dialogo_de_permisos(self):
        for u, pagina in ((DESPACHO, "/flota/"), (VENDEDORA, "/crm/"), (GERENCIA, "/crm/"), (ADMIN, "/crm/"), (B2B, "/pedidos/"), (B2C, "/pedidos/")):
            with self.subTest(u=u):
                html = self.entrar(u).get(pagina).content.decode()
                self.assertIn('id="permisos"', html)
                self.assertIn("js/permisos", html)
                self.assertIn("data-permisos-abrir", html)

    def test_el_anonimo_no_recibe_el_dialogo(self):
        html = Client().get("/catalogo/").content.decode()
        self.assertNotIn('id="permisos"', html)
        self.assertNotIn("js/permisos", html)

    def test_la_ubicacion_solo_se_pide_a_los_clientes(self):
        for u, pagina, esperado in ((B2C, "/pedidos/", True), (B2B, "/pedidos/", True), (DESPACHO, "/flota/", False), (VENDEDORA, "/crm/", False), (ADMIN, "/crm/", False)):
            with self.subTest(u=u):
                html = self.entrar(u).get(pagina).content.decode()
                self.assertEqual('data-permiso="ubicacion"' in html, esperado)

    def test_el_dialogo_explica_para_que_es_cada_permiso(self):
        self.assertIn("pedidos que esperan camión", self.entrar(DESPACHO).get("/flota/").content.decode())
        self.assertIn("tu pedido salga", self.entrar(B2C).get("/pedidos/").content.decode())


class UbicacionDireccionTests(Base):
    def setUp(self):
        self.cliente = Cliente.objects.get(rut=HOSPITAL)
        self.comuna = Comuna.objects.first()

    def test_con_coordenadas_no_consulta_el_geocodificador(self):
        with patch("clientes.geo.geocodificar") as geocodificar:
            d = pedidos.agregar_direccion(self.cliente, "Prat 123", self.comuna.pk, lat="-38.7359", long="-72.5904")
        geocodificar.assert_not_called()
        self.assertAlmostEqual(d.lat, -38.7359)
        self.assertAlmostEqual(d.long, -72.5904)

    def test_sin_coordenadas_sigue_geocodificando(self):
        with patch("clientes.geo.geocodificar", return_value=(-38.0, -72.0)) as geocodificar:
            d = pedidos.agregar_direccion(self.cliente, "Prat 124", self.comuna.pk)
        geocodificar.assert_called_once()
        self.assertEqual(d.lat, -38.0)

    def test_coordenadas_invalidas_se_ignoran_y_no_rompen(self):
        for lat, long in (("abc", "-72"), ("nan", "-72"), ("inf", "-72"), ("95", "-72"), ("-38", "200"), ("-38", ""), ("", "-72"), ("0", "0"), ("40.7", "-74.0")):
            with self.subTest(lat=lat, long=long), patch("clientes.geo.geocodificar", return_value=None):
                d = pedidos.agregar_direccion(self.cliente, f"Calle {lat}{long}"[:40], self.comuna.pk, lat=lat, long=long)
                self.assertIsNone(d.lat)
                self.assertIsNone(d.long)
                d.delete()

    def test_el_formulario_del_carrito_envia_las_coordenadas(self):
        c = self.entrar(B2B)
        pedidos.agregar(self.cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        html = c.get("/carrito/").content.decode()
        self.assertIn('name="lat"', html)
        self.assertIn("data-usar-ubicacion", html)
        c.post("/carrito/direccion/", {"calle_numero": "Bulnes 55", "comuna": self.comuna.pk, "lat": "-38.74", "long": "-72.59"})
        d = self.cliente.direccion_set.get(calle_numero="Bulnes 55")
        self.assertAlmostEqual(d.lat, -38.74)

    def test_el_crm_no_ofrece_usar_la_ubicacion_del_vendedor(self):
        c = self.entrar(ADMIN)
        html = c.get(f"/crm/clientes/{self.cliente.pk}/").content.decode()
        self.assertNotIn("data-usar-ubicacion", html)


class RecepcionParcialTests(Base):
    """RN-23: lo que el cliente rechaza al recibir cambia lo que el equipo debe atender."""

    def en_la_puerta(self, cantidad=2):
        orden = pedido()
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Camión en la puerta"), puerta_en=timezone.now())
        item = orden.ordenitem_set.get()
        type(item).objects.filter(pk=item.pk).update(cantidad=cantidad)
        return Orden.objects.get(pk=orden.pk), orden.direccion.cliente, item.producto_id

    def test_el_rechazo_parcial_sigue_por_facturar_y_avisa_a_ventas(self):
        orden, cliente, producto = self.en_la_puerta()
        antes = self.avisos(VENDEDORA)
        pedidos.resolver_entrega(cliente, orden.pk, "aceptar", motivo="La bolsa venía abierta", con_problema=True, tipo_problema="danado", rechazos={producto: (1, "danado")})
        ahora = self.avisos(VENDEDORA)
        self.assertEqual(ahora["por_facturar"]["n"], antes.get("por_facturar", {"n": 0})["n"] + 1)
        self.assertEqual(ahora["reclamos"]["n"], antes.get("reclamos", {"n": 0})["n"] + 1)

    def test_el_rechazo_total_no_queda_por_facturar_ni_por_despachar(self):
        orden, cliente, producto = self.en_la_puerta()
        antes = self.avisos(ADMIN)
        pedidos.resolver_entrega(cliente, orden.pk, "aceptar", motivo="Toda la carga venía abierta", con_problema=True, tipo_problema="danado", rechazos={producto: (2, "danado")})
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, pedidos.RECHAZADA)
        ahora = self.avisos(ADMIN)
        self.assertEqual(ahora.get("por_facturar", {"n": 0})["n"], antes.get("por_facturar", {"n": 0})["n"])
        self.assertEqual(ahora.get("por_despachar", {"n": 0})["n"], antes.get("por_despachar", {"n": 0})["n"])
        self.assertEqual(ahora["reclamos"]["n"], antes.get("reclamos", {"n": 0})["n"] + 1)

    def test_una_factura_rebajada_por_completo_no_figura_vencida(self):
        orden, cliente, producto = self.en_la_puerta()
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        factura = documentos.emitir_factura(Orden.objects.get(pk=orden.pk))
        type(factura).objects.filter(pk=factura.pk).update(vence_en=timezone.localdate() - timedelta(days=3))
        antes = self.avisos(ADMIN)["vencidas"]["n"]
        documentos.emitir_nota_credito(factura.pk, factura.monto_clp, "Rechazada en recepción")
        self.assertEqual(self.avisos(ADMIN).get("vencidas", {"n": 0})["n"], antes - 1)
