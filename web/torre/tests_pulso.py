"""Pulso de negocio y Lectura del momento de la Torre de control."""
from datetime import timedelta
from unittest import mock

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
from torre.rubrica import LECTURA_VIGENTE_S


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

    def test_ventas_24h_excluye_sembrados_e_historial(self):
        c = self.cliente("Institución")
        for oc, precio in (("OC-REG-001", 9000), ("OC-2026-0457", 9000), ("HIS-1", 9000), ("OC-REAL-1", 1000)):
            o = self.pedido(c, "Recibida", hace_dias=0.5, precio=precio)
            Orden.objects.filter(pk=o.pk).update(numero_oc=oc)
        self.assertEqual(servicios.datos_negocio(self.gerencia)["ahora"]["ventas_24h"], {"B2B": 2000, "B2C": 0})

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

    def test_alerta_sin_pedidos_a_bordo_no_dice_cero_pesos(self):
        t = self.texto(camiones_en_alerta=1, riesgo_actual_clp=0)
        self.assertIn("1 camión con ruptura de frío, sin pedidos a bordo.", t)
        self.assertNotIn("$0", t)
        self.assertIn("3 camiones con ruptura de frío, sin pedidos a bordo.", self.texto(camiones_en_alerta=3, riesgo_actual_clp=0))

    def test_vigencia_igual_a_la_de_la_rubrica(self):
        self.assertIn("Sin novedades", self.texto(ultima_lectura_seg=LECTURA_VIGENTE_S - 1))
        t = self.texto(ultima_lectura_seg=LECTURA_VIGENTE_S)         # exactamente 120 s: ya no es vigente (D3 usa `<`)
        self.assertNotIn("Sin novedades", t)
        self.assertIn("simulador parece detenido", t)

    def test_nunca_mas_de_tres_frases(self):
        peor = _ahora(ultima_lectura_seg=300, camiones_en_alerta=2, riesgo_actual_clp=1000, mas_expuesto="X", simulacion=True)
        frases = lectura.redactar(peor)
        self.assertEqual(len(frases), 3)
        self.assertNotIn("ventas", " ".join(frases))
        self.assertIn("simulación en curso", " ".join(frases))

    def test_lecturas_vencidas_avisan_que_la_alerta_es_de_la_ultima_lectura(self):
        vencida = lectura.redactar(_ahora(ultima_lectura_seg=600, camiones_en_alerta=1, riesgo_actual_clp=50000))
        self.assertIn("según su última lectura", " ".join(vencida))
        self.assertLessEqual(len(vencida), 3)
        self.assertIn("según su última lectura", " ".join(lectura.redactar(_ahora(ultima_lectura_seg=600, camiones_en_alerta=2))))
        al_dia = lectura.redactar(_ahora(ultima_lectura_seg=5, camiones_en_alerta=1, riesgo_actual_clp=50000))
        self.assertNotIn("según su última lectura", " ".join(al_dia))

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


class FrontBack(Base):
    def test_front_back_simetrico(self):
        fb = servicios.front_back()
        self.assertEqual([f["nombre"] for f in fb["front"]], ["E-commerce", "CRM", "IA"])
        self.assertEqual([f["nombre"] for f in fb["back"]], ["AWS", "IoT", "BI"])
        for fila in fb["front"] + fb["back"]:
            self.assertTrue(fila["dato"], fila)
            self.assertTrue(fila["url"].startswith("/"), fila)

    def test_datos_vivos(self):
        fb = servicios.front_back()
        self.assertIn(f"{Producto.objects.filter(activo=True).count()} productos activos", fb["front"][0]["dato"])
        self.assertIn("Sin lecturas", fb["back"][1]["dato"])
        v = self.viaje()
        self.lectura(v.camion, False)
        self.assertIn("1 camión reportando", servicios.front_back()["back"][1]["dato"])

    def test_json_serializable(self):
        import json
        json.dumps(servicios.front_back())

    def test_consultas_constantes_y_sin_escritura(self):
        with CaptureQueriesContext(connection) as q:
            servicios.front_back()
        for consulta in q.captured_queries:
            self.assertNotRegex(consulta["sql"].lstrip().upper(), r"^(INSERT|UPDATE|DELETE)")


class PedidoTrazado(Base):
    def test_pedido_trazado_sin_viajes(self):
        self.pedido(self.cliente("Hospital A"), "Entregada")           # un pedido sin despacho no se traza
        self.assertIsNone(servicios.pedido_trazado())

    def test_pedido_trazado_con_viaje(self):
        v = self.viaje()
        c = self.cliente("Hospital B")
        o = self.pedido(c, "Despachada", despacho=v)
        self.lectura(v.camion, False)
        p = servicios.pedido_trazado()
        self.assertEqual(p["orden_id"], o.pk)
        self.assertEqual(p["cliente"], "Hospital B")
        self.assertEqual(p["camion_id"], v.camion_id)
        self.assertEqual(p["temp_camara"], 3.0)
        self.assertFalse(p["alerta"])
        self.assertEqual(p["cliente_url"], f"/crm/clientes/{c.pk}/")
        self.assertEqual(p["orden_url"], f"/crm/clientes/{c.pk}/#orden-{o.pk}")

    def test_pedido_trazado_alerta(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital C"), "Despachada", despacho=v)
        self.lectura(v.camion, True)
        self.assertTrue(servicios.pedido_trazado()["alerta"])

    def test_excluye_historial(self):
        v = self.viaje()
        o = self.pedido(self.cliente("Hospital D"), "Entregada", despacho=v)
        Orden.objects.filter(pk=o.pk).update(numero_oc="HIS-0001")
        self.assertIsNone(servicios.pedido_trazado())

    def test_sin_lectura_del_camion(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital E"), "Despachada", despacho=v)
        p = servicios.pedido_trazado()
        self.assertIsNone(p["temp_camara"])
        self.assertIsNone(p["alerta"])      # sin lectura no se afirma «no hay alerta»

    def test_toma_el_ultimo_viaje(self):
        c = self.cliente("Hospital F")
        viejo = self.viaje()
        Despacho.objects.filter(pk=viejo.pk).update(salida_en=timezone.now() - timedelta(days=2))
        self.pedido(c, "Entregada", despacho=viejo)
        nuevo = self.viaje(activo=True)
        o2 = self.pedido(c, "Despachada", despacho=nuevo)
        self.assertEqual(servicios.pedido_trazado()["orden_id"], o2.pk)

    def test_excluye_canceladas(self):
        c = self.cliente("Hospital I")
        v1, v2 = self.viaje(), self.viaje()
        Despacho.objects.filter(pk=v1.pk).update(salida_en=timezone.now() - timedelta(days=1))
        vivo = self.pedido(c, "Despachada", despacho=v1)
        self.pedido(c, "Cancelada", despacho=v2)
        self.assertEqual(servicios.pedido_trazado()["orden_id"], vivo.pk)

    def test_trae_la_hora_de_salida(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital J"), "Despachada", despacho=v)
        self.assertEqual(servicios.pedido_trazado()["salida_en"], v.salida_en.isoformat())

    def test_puede_usar_pedido_regional(self):
        v = self.viaje()
        o = self.pedido(self.cliente("Hospital K"), "Despachada", despacho=v)
        Orden.objects.filter(pk=o.pk).update(numero_oc="OC-REG-001")
        self.assertEqual(servicios.pedido_trazado()["orden_id"], o.pk)

    def test_usa_las_vigentes_que_recibe(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital L"), "Despachada", despacho=v)
        lectura_real = self.lectura(v.camion, False)
        with mock.patch.object(servicios.vigente, "ultimas_vigentes") as calcular:
            p = servicios.pedido_trazado({v.camion_id: lectura_real})
        calcular.assert_not_called()
        self.assertEqual(p["temp_camara"], 3.0)

    def test_pulso_calcula_las_vigentes_una_sola_vez(self):
        from django.core.cache import cache
        cache.clear()
        v = self.viaje()
        self.pedido(self.cliente("Hospital M"), "Despachada", despacho=v)
        self.lectura(v.camion, False)
        with mock.patch.object(servicios.vigente, "ultimas_vigentes", wraps=servicios.vigente.ultimas_vigentes) as calcular:
            servicios.pulso(self.gerencia, "gerencia")
        self.assertEqual(calcular.call_count, 1)
        self.assertEqual(servicios.CACHE_S, 5)

    def test_consultas_constantes(self):
        def consultas():
            with CaptureQueriesContext(connection) as q:
                servicios.pedido_trazado()
            return len(q)
        v = self.viaje()
        self.pedido(self.cliente("Hospital G"), "Despachada", despacho=v)
        self.lectura(v.camion, False)
        antes = consultas()
        for i in range(10):
            self.pedido(self.cliente(f"Otro {i}"), "Entregada", despacho=self.viaje())
        self.assertEqual(consultas(), antes)

    def test_pulso_los_incluye(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital H"), "Despachada", despacho=v)
        from django.core.cache import cache
        cache.clear()
        d = servicios.pulso(self.gerencia, "gerencia")
        self.assertEqual(len(d["front_back"]["front"]), 3)
        self.assertEqual(d["pedido_trazado"]["cliente"], "Hospital H")

    def test_enlaces_los_abre_gerencia(self):
        v = self.viaje()
        self.pedido(self.cliente("Hospital I"), "Despachada", despacho=v)
        p = servicios.pedido_trazado()
        self.client.force_login(self.gerencia)
        r = self.client.get(p["cliente_url"])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'id="orden-{p["orden_id"]}"')
