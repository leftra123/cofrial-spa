"""Nivel del cliente en el embudo de la Torre de control: se calcula desde los pedidos, no se guarda."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente, Comuna, Direccion, SegmentoCliente, TipoCliente, Vendedor
from clientes import muestra
from crm import servicios as s
from crm.models import EtapaPipeline, Prospecto
from pedidos.models import EstadoOrden, Orden, OrdenItem

A = timezone.now()


class FuncionNivel(TestCase):
    def test_limites_de_nivel(self):
        self.assertEqual(s.nivel_de(0, 0, None, A), "Ganado sin pedido")
        self.assertEqual(s.nivel_de(1, 1, A - timedelta(days=30), A), "Primer pedido")
        self.assertEqual(s.nivel_de(1, 0, A - timedelta(days=31), A), "En riesgo")
        self.assertEqual(s.nivel_de(2, 2, A - timedelta(days=1), A), "Recompra")
        self.assertEqual(s.nivel_de(3, 3, A - timedelta(days=1), A), "Recompra")
        self.assertEqual(s.nivel_de(4, 4, A - timedelta(days=1), A), "Fidelizado")
        self.assertEqual(s.nivel_de(9, 4, A - timedelta(days=31), A), "En riesgo")


class Embudo(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        U = get_user_model()
        cls.maria, cls.pedro = U.objects.get(username="vendedora@cofrial.cl"), U.objects.get(username="vendedor2@cofrial.cl")
        cls.gerencia = U.objects.get(username="gerencia@cofrial.cl")
        cls.v_maria, cls.v_pedro = Vendedor.objects.get(usuario=cls.maria), Vendedor.objects.get(usuario=cls.pedro)
        cls.b2b, cls.b2c = TipoCliente.objects.get(codigo="B2B"), TipoCliente.objects.get(codigo="B2C")
        cls.comuna = Comuna.objects.first()
        cls.producto = Producto.objects.first()
        cls.n = 0

    def cliente(self, nombre, tipo=None, vendedor=None, segmento=None, activo=True, sin_vendedor=False):
        type(self).n += 1
        cuenta = get_user_model().objects.create_user(username=f"niv{self.n}@test.cl", password="x", is_active=activo)
        c = Cliente.objects.create(usuario=cuenta, tipo_cliente=tipo or self.b2b, vendedor=None if sin_vendedor else vendedor or self.v_maria, rut=f"9{self.n:07d}-1",
                                   nombre=nombre, email=f"niv{self.n}@test.cl", segmento=segmento)
        Direccion.objects.create(cliente=c, calle_numero="Calle 1", comuna=self.comuna, es_principal=True)
        return c

    def pedido(self, cliente, hace_dias=1, estado="Entregada", cantidad=2, precio=1000):
        o = Orden.objects.create(direccion=cliente.direccion_set.first(), estado_orden=EstadoOrden.objects.get(nombre=estado))
        OrdenItem.objects.create(orden=o, producto=self.producto, cantidad=cantidad, precio_unitario_clp=precio)
        Orden.objects.filter(pk=o.pk).update(creada_en=timezone.now() - timedelta(days=hace_dias))
        return o

    def prospecto(self, etapa, contacto="Contacto", vendedor=None, cliente=None, monto=500000):
        e = EtapaPipeline.objects.get(nombre=etapa)
        return Prospecto.objects.create(vendedor=vendedor or self.v_maria, etapa=e, nombre_contacto=contacto, empresa=contacto, email="p@test.cl",
                                        origen="web", monto_estimado_clp=monto, cliente=cliente,
                                        cerrado_en=timezone.now() if e.es_final else None,
                                        motivo_perdida="No compró" if e.nombre == "Perdido" else "")

    def nombres(self, fase_o_aparte, etapa):
        for e in fase_o_aparte:
            if e["nombre"] == etapa:
                return [i["nombre"] for i in e["items"]]
        raise AssertionError(etapa)

    def etapas(self, datos):
        return {e["nombre"]: e for f in datos["fases"] for e in f["etapas"]} | {e["nombre"]: e for e in datos["aparte"]}

    def test_cancelados_no_cuentan(self):
        c = self.cliente("Solo Cancelada", segmento=SegmentoCliente.objects.first())
        self.pedido(c, estado="Cancelada")
        self.assertEqual(s.nivel_de_cliente(c), "Ganado sin pedido")
        self.assertIn("Solo Cancelada", [i["nombre"] for i in self.etapas(s.embudo_por_niveles(self.gerencia))["Ganado sin pedido"]["items"]])

    def test_niveles_de_cliente_y_agrupacion(self):
        base = self.etapas(s.embudo_por_niveles(self.gerencia))
        primero = self.cliente("Uno", segmento=SegmentoCliente.objects.first())
        self.pedido(primero, 5)
        recompra = self.cliente("Dos")
        self.pedido(recompra, 5)
        self.pedido(recompra, 100)
        fiel = self.cliente("Cuatro")
        for d in (1, 10, 20, 30):
            self.pedido(fiel, d)
        riesgo = self.cliente("Riesgo")
        self.pedido(riesgo, 45)
        e = self.etapas(s.embudo_por_niveles(self.gerencia))
        for nombre, etapa in (("Uno", "Primer pedido"), ("Dos", "Recompra"), ("Cuatro", "Fidelizado"), ("Riesgo", "En riesgo")):
            self.assertIn(nombre, [i["nombre"] for i in e[etapa]["items"]])
        item = next(i for i in e["Primer pedido"]["items"] if i["nombre"] == "Uno")
        self.assertEqual(item["url"], f"/crm/clientes/{primero.pk}/")
        self.assertEqual(item["detalle"], f"1 pedido, último {timezone.localtime(timezone.now() - timedelta(days=5)):%d/%m}")
        self.assertEqual(e["Primer pedido"]["monto_clp"] - base["Primer pedido"]["monto_clp"], 2000)
        self.assertEqual(e["Primer pedido"]["n"] - base["Primer pedido"]["n"], 1)

    def test_pipeline_en_las_fases(self):
        self.prospecto("Prospecto", "Pros Uno")
        self.prospecto("Contactado", "Cont Uno")
        self.prospecto("Negociación", "Nego Uno")
        self.prospecto("Perdido", "Perd Reciente")
        p = self.prospecto("Perdido", "Perd Antiguo")
        Prospecto.objects.filter(pk=p.pk).update(cerrado_en=timezone.now() - timedelta(days=100))
        datos = s.embudo_por_niveles(self.gerencia)
        self.assertEqual([f["nombre"] for f in datos["fases"]], ["Atracción", "Interés", "Consideración", "Acción", "Fidelización"])
        e = self.etapas(datos)
        self.assertIn("Pros Uno", [i["nombre"] for i in e["Prospecto"]["items"]])
        self.assertIn("Nego Uno", [i["nombre"] for i in e["Negociación"]["items"]])
        perdidos = [i["nombre"] for i in e["Perdido"]["items"]]
        self.assertIn("Perd Reciente", perdidos)
        self.assertNotIn("Perd Antiguo", perdidos)
        pros = next(i for i in e["Prospecto"]["items"] if i["nombre"] == "Pros Uno")
        self.assertTrue(pros["url"].startswith("/crm/prospectos/"))
        self.assertEqual(pros["detalle"], "$500.000")

    def test_quien_entra(self):
        self.cliente("Con Segmento", segmento=SegmentoCliente.objects.first())
        ganado = self.cliente("Con Ganado")
        self.prospecto("Cliente ganado", "Ganador", cliente=ganado)
        self.pedido(self.cliente("Con Pedidos"))
        self.cliente("Sin Nada")
        por_aprobar = self.cliente("Por Aprobar", sin_vendedor=True, activo=False, segmento=SegmentoCliente.objects.first())
        self.pedido(por_aprobar)
        self.pedido(self.cliente("Persona B2C", tipo=self.b2c))
        datos = s.embudo_por_niveles(self.gerencia)
        todos = [i["nombre"] for e in self.etapas(datos).values() for i in e["items"]]
        for esperado in ("Con Segmento", "Con Ganado", "Con Pedidos"):
            self.assertIn(esperado, todos)
        for ausente in ("Sin Nada", "Por Aprobar", "Persona B2C"):
            self.assertNotIn(ausente, todos)

    def test_b2c_se_cuenta_aparte(self):
        antes = s.embudo_por_niveles(self.gerencia)["n_b2c"]
        self.cliente("Comprador 1", tipo=self.b2c)
        self.cliente("Comprador 2", tipo=self.b2c)
        self.assertEqual(s.embudo_por_niveles(self.gerencia)["n_b2c"], antes + 2)
        self.assertEqual(s.embudo_por_niveles(self.gerencia)["n_b2c"], Cliente.objects.filter(tipo_cliente__codigo="B2C").count())

    def test_vendedor_ve_solo_su_cartera(self):
        self.pedido(self.cliente("De Pedro", vendedor=self.v_pedro))
        self.pedido(self.cliente("De Maria", vendedor=self.v_maria))
        self.prospecto("Contactado", "Prospecto de Pedro", vendedor=self.v_pedro)
        todos = [i["nombre"] for e in self.etapas(s.embudo_por_niveles(self.maria)).values() for i in e["items"]]
        self.assertIn("De Maria", todos)
        self.assertNotIn("De Pedro", todos)
        self.assertNotIn("Prospecto de Pedro", todos)

    def test_consultas_acotadas(self):
        def crear(desde, hasta):
            for i in range(desde, hasta):
                c = self.cliente(f"Masivo {i}")
                self.pedido(c, 3)
                self.pedido(c, 40)
        crear(0, 15)
        with self.captureQueries() as pocos:
            s.embudo_por_niveles(self.gerencia)
        crear(15, 30)
        with self.captureQueries() as muchos:
            s.embudo_por_niveles(self.gerencia)
        self.assertEqual(len(pocos), len(muchos))

    def captureQueries(self):
        return CaptureQueriesContext(connection)


class FichaDelCliente(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut=muestra.HOSPITAL_REGIONAL)
        cls.ana = Cliente.objects.get(email="ana@correo.test")

    def ficha(self, cliente):
        self.client.login(username="gerencia@cofrial.cl", password="demo-cofrial-2026")
        return self.client.get(f"/crm/clientes/{cliente.pk}/")

    def test_ficha_muestra_nivel(self):
        r = self.ficha(self.hospital)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f"Nivel: {s.nivel_de_cliente(self.hospital)}")

    def test_ficha_rotula_ilustrativo(self):
        self.assertIn(self.hospital.rut, muestra.RUT_ILUSTRATIVOS)
        self.assertContains(self.ficha(self.hospital), "Cliente ilustrativo: nombre público usado como ejemplo")
        self.assertNotContains(self.ficha(self.ana), "Cliente ilustrativo")

    def test_ficha_b2c_sin_nivel(self):
        self.assertNotContains(self.ficha(self.ana), "Nivel:")
