"""Pulso de negocio y Lectura del momento de la Torre de control."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente, Comuna, Direccion, SegmentoCliente, TipoCliente
from flota.models import Camion, Despacho, EscenarioSimulador, Telemetria
from pedidos.models import Documento, EstadoOrden, Orden, OrdenItem, Pago
from torre import lectura, servicios


def _vaciar():
    """Deja la base sin pedidos, viajes ni lecturas, para que las cifras sean solo las de cada prueba."""
    Pago.objects.all().delete()
    Documento.objects.all().delete()
    Orden.objects.all().delete()
    EscenarioSimulador.objects.all().delete()
    Despacho.objects.all().delete()
    Telemetria.objects.all().delete()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.gerencia = get_user_model().objects.get(username="gerencia@cofrial.cl")
        cls.b2b, cls.b2c = TipoCliente.objects.get(codigo="B2B"), TipoCliente.objects.get(codigo="B2C")
        cls.comuna = Comuna.objects.first()
        cls.producto = Producto.objects.first()
        cls.segmento = SegmentoCliente.objects.first()
        cls.n = 0

    def setUp(self):
        _vaciar()

    def cliente(self, nombre, segmento=True, tipo=None, lat=-38.7, long=-72.6):
        type(self).n += 1
        c = Cliente.objects.create(tipo_cliente=tipo or self.b2b, rut=f"8{self.n:07d}-1", nombre=nombre, email=f"p{self.n}@test.cl",
                                   segmento=self.segmento if segmento else None)
        Direccion.objects.create(cliente=c, calle_numero="Calle 1", comuna=self.comuna, es_principal=True, lat=lat, long=long)
        return c

    def pedido(self, cliente, estado="Entregada", hace_dias=1, despacho=None, cantidad=2, precio=1000):
        o = Orden.objects.create(direccion=cliente.direccion_set.first(), estado_orden=EstadoOrden.objects.get(nombre=estado), despacho=despacho)
        OrdenItem.objects.create(orden=o, producto=self.producto, cantidad=cantidad, precio_unitario_clp=precio)
        Orden.objects.filter(pk=o.pk).update(creada_en=timezone.now() - timedelta(days=hace_dias))
        return o

    def viaje(self, camion_id="CAM-01", activo=True):
        camion = Camion.objects.get(pk=camion_id) if Camion.objects.filter(pk=camion_id).exists() else Camion.objects.first()
        ahora = timezone.now()
        return Despacho.objects.create(camion=camion, programado_para=ahora, salida_en=ahora - timedelta(hours=1),
                                       llegada_en=None if activo else ahora - timedelta(minutes=10),
                                       regreso_en=None if activo else ahora - timedelta(minutes=5))

    def lectura(self, camion, alerta, forzada=False):
        return Telemetria.objects.create(camion=camion, temp_camara=9.0 if alerta else 3.0, lat=-38.7, long=-72.6, combustible_pct=70,
                                         alerta_ruptura_frio=alerta, forzada=forzada)


class Datos(Base):
    def test_base_vacia(self):
        d = servicios.datos_negocio(self.gerencia)
        self.assertIsNone(d["ahora"]["ultima_lectura_seg"])
        self.assertEqual(d["ahora"]["riesgo_actual_clp"], 0)
        self.assertEqual(d["ahora"]["ventas_24h"], {"B2B": 0, "B2C": 0})
        self.assertEqual(d["camiones"], [])
        self.assertIn("Sin lecturas de los camiones todavía", " ".join(lectura.redactar(d["ahora"])))

    def test_riesgo_actual_excluye_entregadas(self):
        v = self.viaje()
        c = self.cliente("Hospital A")
        self.pedido(c, "Entregada", despacho=v, precio=1000)
        self.pedido(c, "Despachada", despacho=v, precio=5000)
        self.lectura(v.camion, True)
        a = servicios.datos_negocio(self.gerencia)["ahora"]
        self.assertEqual(a["riesgo_actual_clp"], 10000)
        self.assertEqual(a["camiones_en_alerta"], 1)
        self.assertEqual(a["mas_expuesto"], "Hospital A")

    def test_riesgo_actual_vuelve_a_cero_e_historico_no(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital B"), "Despachada", despacho=v, precio=5000)
        self.lectura(v.camion, True)
        antes = servicios.datos_negocio(self.gerencia)["ahora"]
        self.assertEqual(antes["riesgo_actual_clp"], 10000)
        Despacho.objects.filter(pk=v.pk).update(llegada_en=timezone.now(), regreso_en=timezone.now())
        self.lectura(v.camion, False)
        despues = servicios.datos_negocio(self.gerencia)["ahora"]
        self.assertEqual(despues["riesgo_actual_clp"], 0)
        self.assertEqual(despues["camiones_en_alerta"], 0)
        self.assertGreater(despues["riesgo_historico_clp"], 0)

    def test_clientes_mapa_solo_con_segmento(self):
        self.cliente("Con segmento")
        self.cliente("Sin segmento", segmento=False)
        nombres = [c["nombre"] for c in servicios.datos_negocio(self.gerencia)["clientes_mapa"]]
        self.assertIn("Con segmento", nombres)
        self.assertNotIn("Sin segmento", nombres)
        cuentas = ["ana@correo.test", "felipe@cofrial.cl"]
        de_prueba = list(Cliente.objects.filter(usuario__username__in=cuentas))
        self.assertEqual(len(de_prueba), 2)                     # existen y no tienen segmento
        for c in de_prueba:
            self.assertIsNone(c.segmento_id)
            self.assertNotIn(c.nombre, nombres)
        fila = next(c for c in servicios.datos_negocio(self.gerencia)["clientes_mapa"] if c["nombre"] == "Con segmento")
        self.assertEqual(set(fila), {"nombre", "segmento", "comuna", "lat", "long", "nivel", "url"})
        self.assertEqual(fila["nivel"], "Ganado sin pedido")

    def test_frecuentes_excluye_canceladas_y_limita_a_8(self):
        for i in range(10):
            c = self.cliente(f"Cliente {i}")
            for _ in range(i + 1):
                self.pedido(c, hace_dias=2)
        solo_canceladas = self.cliente("Solo canceladas")
        for _ in range(20):
            self.pedido(solo_canceladas, "Cancelada")
        f = servicios.datos_negocio(self.gerencia)["frecuentes"]
        self.assertEqual(len(f), 8)
        self.assertNotIn("Solo canceladas", [x["nombre"] for x in f])
        self.assertEqual([x["pedidos"] for x in f], [10, 9, 8, 7, 6, 5, 4, 3])
        self.assertEqual(f[0]["nivel"], "Fidelizado")
        self.assertIsInstance(f[0]["ultimo"], str)

    def test_ventas_24h_excluye_canceladas(self):
        c = self.cliente("Institución")
        p = self.cliente("Particular", tipo=self.b2c)
        self.pedido(c, "Recibida", hace_dias=0.5, precio=1000)
        self.pedido(c, "Cancelada", hace_dias=0.5, precio=9000)
        self.pedido(c, "Entregada", hace_dias=3, precio=9000)
        self.pedido(p, "Recibida", hace_dias=0.5, precio=500)
        self.assertEqual(servicios.datos_negocio(self.gerencia)["ahora"]["ventas_24h"], {"B2B": 2000, "B2C": 1000})

    def test_camiones_solo_con_viaje_o_alerta(self):
        v = self.viaje()
        libre = Camion.objects.exclude(pk=v.camion_id).first()
        self.lectura(v.camion, False)
        self.lectura(libre, False)
        d = servicios.datos_negocio(self.gerencia)
        self.assertEqual([c["id"] for c in d["camiones"]], [v.camion_id])
        self.lectura(libre, True)
        d = servicios.datos_negocio(self.gerencia)
        self.assertEqual({c["id"]: c["alerta"] for c in d["camiones"]}, {v.camion_id: False, libre.pk: True})

    def test_simulacion_solo_con_forzada_reciente_y_no_cuenta_como_lectura(self):
        camion = Camion.objects.first()
        self.lectura(camion, True, forzada=True)
        a = servicios.datos_negocio(self.gerencia)["ahora"]
        self.assertTrue(a["simulacion"])
        self.assertIsNone(a["ultima_lectura_seg"])
        self.assertEqual(a["camiones_en_alerta"], 1)

    def test_json_serializable(self):
        import json
        v = self.viaje()
        c = self.cliente("Hospital C")
        self.pedido(c, "Despachada", despacho=v)
        self.lectura(v.camion, True)
        json.dumps(servicios.datos_negocio(self.gerencia))

    def test_no_escribe(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital D"), "Despachada", despacho=v)
        self.lectura(v.camion, True)
        with CaptureQueriesContext(connection) as q:
            servicios.datos_negocio(self.gerencia)
        for consulta in q.captured_queries:
            self.assertNotRegex(consulta["sql"].lstrip().upper(), r"^(INSERT|UPDATE|DELETE)")

    def test_consultas_no_crecen_con_los_clientes(self):
        def consultas():
            with CaptureQueriesContext(connection) as q:
                servicios.datos_negocio(self.gerencia)
            return len(q)
        for i in range(3):
            self.pedido(self.cliente(f"Pocos {i}"))
        pocas = consultas()
        for i in range(15):
            self.pedido(self.cliente(f"Muchos {i}"), hace_dias=3)
        self.assertEqual(consultas(), pocas)


def _ahora(**cambios):
    base = {"ultima_lectura_seg": 5, "alertas_24h": 0, "riesgo_actual_clp": 0, "camiones_en_alerta": 0, "riesgo_historico_clp": 0,
            "no_concretadas": 0, "interacciones": 0, "ventas_24h": {"B2B": 700, "B2C": 300}, "simulacion": False, "mas_expuesto": None}
    return {**base, **cambios}


class Lectura(TestCase):
    def texto(self, **cambios):
        return " ".join(lectura.redactar(_ahora(**cambios)))

    def test_lectura_sin_novedades(self):
        self.assertIn("Sin novedades en la cadena de frío", self.texto())

    def test_lectura_con_alerta(self):
        t = self.texto(camiones_en_alerta=3, riesgo_actual_clp=4_200_000, mas_expuesto="Hospital de Angol")
        self.assertIn("3 camiones con ruptura de frío", t)
        self.assertIn("$4,2 M", t)
        self.assertIn("Hospital de Angol", t)
        self.assertNotIn("Sin novedades", t)
        self.assertIn("1 camión con ruptura de frío", self.texto(camiones_en_alerta=1, riesgo_actual_clp=450_000))
        self.assertIn("$450.000", self.texto(camiones_en_alerta=1, riesgo_actual_clp=450_000))

    def test_lectura_sin_ventas(self):
        self.assertIn("Sin ventas en 24 h", self.texto(ventas_24h={"B2B": 0, "B2C": 0}))
        self.assertIn("70 % institucional", self.texto())

    def test_lectura_simulacion(self):
        self.assertIn("simulación en curso", self.texto(simulacion=True))
        self.assertNotIn("simulación en curso", self.texto())

    def test_simulador_detenido_no_afirma_novedades(self):
        t = self.texto(ultima_lectura_seg=300)
        self.assertIn("5 min", t)
        self.assertNotIn("Sin novedades", t)

    def test_dos_o_tres_frases(self):
        self.assertEqual(len(lectura.redactar(_ahora())), 2)
        self.assertEqual(len(lectura.redactar(_ahora(simulacion=True))), 3)
