"""Pedido de prueba cercano para la demostración: de Temuco o Padre Las Casas, «En preparación» y listo para despachar."""
from django.core.management import call_command
from django.test import TestCase

from flota import pedido_demo, servicios
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class PedidoCercano(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def post(self, usuario, rango="Congelado"):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))
        return self.client.post("/demo/pedido-cercano/", {"rango": rango})

    def test_crea_un_pedido_cercano_en_preparacion_que_aparece_para_despachar(self):
        for rango in ("Refrigerado", "Congelado"):
            r = self.post("admin@cofrial.cl", rango)
            self.assertEqual(r.status_code, 200, r.content)
            datos = r.json()
            orden = Orden.objects.select_related("direccion__comuna", "estado_orden").get(pk=datos["orden"])
            self.assertIn(orden.direccion.comuna.nombre, pedido_demo.COMUNAS_CERCANAS)
            self.assertEqual(orden.estado_orden.nombre, "En preparación")
            self.assertEqual(servicios.rangos_de(orden), [rango])
            self.assertIn(orden.pk, [o.pk for o in servicios.pedidos_por_despachar()])

    def test_solo_el_administrador_y_con_rango_valido(self):
        n = Orden.objects.count()
        for u in ("despacho@cofrial.cl", "gerencia@cofrial.cl", "vendedora@cofrial.cl", "ana@correo.test"):
            self.assertIn(self.post(u).status_code, (302, 403), u)
        self.assertEqual(self.post("admin@cofrial.cl", "Tibio").status_code, 400)
        self.assertEqual(self.client.get("/demo/pedido-cercano/").status_code, 405)
        self.assertEqual(Orden.objects.count(), n)

    def test_no_toca_el_carrito_de_quien_ya_tiene_cosas_en_el_y_repite_con_otros(self):
        from pedidos import servicios as s
        from clientes.models import Cliente
        from catalogo.models import Producto
        ids = {self.post("admin@cofrial.cl").json()["orden"] for _ in range(3)}
        self.assertEqual(len(ids), 3)                                         # cada vez otro cliente o dirección libre, sin chocar
        hospital = Cliente.objects.get(rut="61.973.200-4")
        s.agregar(hospital, Producto.objects.filter(activo=True).first().pk, 1)
        n = s.lineas_en_carrito(hospital)
        self.post("admin@cofrial.cl")
        self.assertEqual(s.lineas_en_carrito(hospital), n)


class Preparar(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_deja_viajes_en_curso_con_pedido_bueno_y_sin_rupturas(self):
        from flota.models import Camion, Despacho, EscenarioSimulador, Telemetria
        for c in Camion.objects.select_related('rango_temperatura'):                    # como en vivo: todos los camiones reportan, sanos y con combustible
            r = c.rango_temperatura
            Telemetria.objects.create(camion=c, temp_camara=(float(r.temp_min_c) + float(r.temp_max_c)) / 2, lat=-38.73, long=-72.6, combustible_pct=80, alerta_ruptura_frio=False)
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password=CLAVE))
        self.assertEqual(self.client.post("/demo/preparar/", {}).status_code, 400)               # sin confirmar no hace nada
        r = self.client.post("/demo/preparar/", {"confirmar": "1"})
        self.assertEqual(r.status_code, 200, r.content)
        datos = r.json()
        self.assertTrue(1 <= len(datos["viajes"]) <= 3)
        for v in datos["viajes"]:
            d = Despacho.objects.get(pk=v["despacho"])
            self.assertIsNone(d.regreso_en)
            e = EscenarioSimulador.objects.get(despacho=d)
            self.assertEqual((e.tipo, e.estado), ("entrega_perfecta", "pendiente"))
            self.assertEqual(Orden.objects.get(pk=v["orden"]).estado_orden.nombre, "Despachada")
        camiones = [v["camion"] for v in datos["viajes"]]
        self.assertEqual(len(camiones), len(set(camiones)))                                      # cada viaje, su camión
