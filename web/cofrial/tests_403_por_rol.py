"""403 claros por rol: gerencia mira los despachos pero no los arma, y el equipo no compra ni reclama como cliente."""
from django.core.management import call_command
from django.test import Client, TestCase

from catalogo.models import Producto
from clientes.models import Cliente, Direccion
from crm.models import Requerimiento
from flota import servicios as flota
from flota.models import Despacho
from pedidos import servicios as s

CLAVE = "demo-cofrial-2026"
EQUIPO = ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "admin@cofrial.cl")


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c


class GerenciaNoArmaDespachos(Base):
    def _viaje(self):
        """Una orden nueva de la clienta y un camión libre de su mismo rango de temperatura."""
        ana = Cliente.objects.get(rut="12.345.678-5")
        s.agregar(ana, Producto.objects.filter(stock_disponible__gt=0).first().pk, 1)
        orden = s.generar_orden(ana, ana.direccion_set.first().pk)
        rango = flota.rangos_de(orden)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        return {"camion": camion.camion_id, "ordenes": [orden.orden_id]}

    def test_gerencia_recibe_403_al_despachar_y_no_sale_ningun_camion(self):
        antes = Despacho.objects.count()
        r = self.entrar("gerencia@cofrial.cl").post("/flota/despachar/", self._viaje())
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "los arman el despachador y el administrador", status_code=403)
        self.assertEqual(Despacho.objects.count(), antes)

    def test_gerencia_recibe_403_al_ubicar_una_direccion(self):
        direccion = Direccion.objects.first()
        r = self.entrar("gerencia@cofrial.cl").post(f"/flota/despachar/ubicar/{direccion.pk}/")
        self.assertEqual(r.status_code, 403)

    def test_despachador_y_administrador_si_despachan_y_ubican(self):
        for usuario in ("despacho@cofrial.cl", "admin@cofrial.cl"):
            c = self.entrar(usuario)
            antes = Despacho.objects.count()
            self.assertRedirects(c.post("/flota/despachar/", self._viaje()), "/flota/", fetch_redirect_response=False, msg_prefix=usuario)
            self.assertEqual(Despacho.objects.count(), antes + 1, usuario)
            r = c.post(f"/flota/despachar/ubicar/{Direccion.objects.first().pk}/")
            self.assertRedirects(r, "/flota/despachar/", fetch_redirect_response=False, msg_prefix=usuario)

    def test_gerencia_ve_la_pantalla_de_despacho_sin_el_boton_de_despachar(self):
        r = self.entrar("gerencia@cofrial.cl").get("/flota/despachar/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'id="btn-despachar"')
        self.assertNotContains(r, 'formaction="/flota/despachar/ubicar/')
        self.assertContains(self.entrar("despacho@cofrial.cl").get("/flota/despachar/"), 'id="btn-despachar"')


class ElEquipoNoCompraComoCliente(Base):
    def setUp(self):
        ana = Cliente.objects.get(rut="12.345.678-5")
        self.producto = Producto.objects.filter(stock_disponible__gt=0).first()
        s.agregar(ana, self.producto.pk, 1)
        self.orden = s.generar_orden(ana, ana.direccion_set.first().pk)

    def test_post_al_carrito_cancelar_y_soporte_da_403_claro(self):
        acciones = [("/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 1}),
                    ("/carrito/actualizar/", {"producto": self.producto.pk, "cantidad": 2}),
                    ("/carrito/repetir/", {"orden": self.orden.pk}),
                    ("/carrito/confirmar/", {"direccion": 1}),
                    (f"/pedidos/{self.orden.pk}/cancelar/", {}),
                    ("/soporte/", {"asunto": "Prueba", "descripcion": "Reclamo escrito desde una cuenta del equipo"})]
        requerimientos = Requerimiento.objects.count()
        for usuario in EQUIPO:
            c = self.entrar(usuario)
            for url, datos in acciones:
                with self.subTest(usuario=usuario, url=url):
                    r = c.post(url, datos)
                    self.assertEqual(r.status_code, 403)
                    self.assertContains(r, "Las cuentas del equipo no compran", status_code=403)
        self.assertEqual(Requerimiento.objects.count(), requerimientos)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado_orden.orden_flujo, 1)                 # la orden de la clienta sigue como estaba

    def test_las_pantallas_de_cliente_por_get_siguen_llevando_al_catalogo(self):
        c = self.entrar("vendedora@cofrial.cl")
        for url in ("/carrito/", "/soporte/", "/pedidos/"):
            self.assertRedirects(c.get(url), "/catalogo/", fetch_redirect_response=False, msg_prefix=url)

    def test_el_cliente_sigue_comprando_y_cancelando(self):
        c = self.entrar("ana@correo.test")
        self.assertRedirects(c.post("/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 1}), "/catalogo/", fetch_redirect_response=False)
        self.assertEqual(c.post(f"/pedidos/{self.orden.pk}/cancelar/").status_code, 302)
