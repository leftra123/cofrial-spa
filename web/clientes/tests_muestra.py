"""Clientes de muestra e historial de pedidos para la Torre de control: idempotentes, sin tocar stock ni cobranza y reversibles."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from catalogo.models import Producto
from crm import servicios as crm
from crm.models import Prospecto
from pedidos import documentos
from pedidos.models import Documento, Orden, OrdenItem, Pago

from . import muestra
from .models import Cliente, Direccion, SegmentoCliente, TipoCliente


def conteos():
    return {m.__name__: m.objects.count() for m in (Cliente, Direccion, Orden, OrdenItem, Documento, Pago, Prospecto)}


def stock():
    return dict(Producto.objects.values_list("pk", "stock_disponible"))


def cobranza():
    r = documentos.resumen_cobranza(Cliente.objects.all())
    return r["por_cobrar"], r["vencido"], len(r["sin_facturar"])


class ClientesDeMuestra(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.b2b = TipoCliente.objects.get(codigo="B2B")
        cls.antes = {"conteos": conteos(), "stock": stock(), "cobranza": cobranza()}
        U = get_user_model()
        cls.vendedores = [U.objects.get(username=u) for u in ("vendedora@cofrial.cl", "vendedor2@cofrial.cl")]

    def cartera(self):
        return [sorted(Cliente.objects.filter(vendedor__usuario=u).values_list("pk", flat=True)) for u in self.vendedores]

    def historial(self):
        return Orden.objects.filter(numero_oc__startswith="HIS-")

    def test_cargar_demo_no_siembra_en_pruebas(self):
        self.assertEqual(self.historial().count(), 0)

    def test_idempotente(self):
        muestra.sembrar(self.b2b)
        primero = conteos()
        muestra.sembrar(self.b2b)
        self.assertEqual(conteos(), primero)

    def test_limites_del_historial(self):
        muestra.sembrar(self.b2b)
        ahora = timezone.now()
        n = self.historial().count()
        self.assertTrue(60 <= n <= 120, n)
        for o in self.historial():
            self.assertLess(o.creada_en, ahora - timedelta(hours=24))
            self.assertGreater(o.creada_en, ahora - timedelta(days=90))
            self.assertIsNone(o.despacho_id)
            self.assertEqual(o.estado_orden.nombre, "Entregada")
            self.assertLessEqual(len(o.numero_oc), 30)
        refs = list(self.historial().values_list("numero_oc", flat=True))
        self.assertEqual(len(refs), len(set(refs)))

    def test_stock_no_cambia(self):
        muestra.sembrar(self.b2b)
        self.assertEqual(stock(), self.antes["stock"])

    def test_cobranza_no_cambia(self):
        muestra.sembrar(self.b2b)
        self.assertEqual(cobranza(), self.antes["cobranza"])

    def test_excluidos_sin_historial(self):
        muestra.sembrar(self.b2b)
        for rut in ("61.973.200-4", "76.543.210-K", "70.300.104-1", "70.300.107-6", "70.300.108-4"):
            self.assertFalse(Orden.objects.filter(direccion__cliente__rut=rut, numero_oc__startswith="HIS-").exists(), rut)

    def test_carteras_de_clientes_iguales(self):
        antes = self.cartera()
        muestra.sembrar(self.b2b)
        self.assertEqual(self.cartera(), antes)

    def test_hay_cliente_en_cada_nivel(self):
        muestra.sembrar(self.b2b)
        niveles = {crm.nivel_de_cliente(c) for c in Cliente.objects.filter(rut__in=muestra.RUT_ILUSTRATIVOS)}
        self.assertEqual(niveles, {"Ganado sin pedido", "Primer pedido", "Recompra", "Fidelizado", "En riesgo"})

    def test_no_pisa_segmento(self):
        feria = SegmentoCliente.objects.get(nombre="Feria")
        Cliente.objects.filter(rut="70.300.101-7").update(segmento=feria)
        muestra.sembrar(self.b2b)
        self.assertEqual(Cliente.objects.get(rut="70.300.101-7").segmento, feria)
        self.assertEqual(Cliente.objects.get(rut="70.300.102-5").segmento.nombre, "Hospital")

    def test_coordenadas_presentes(self):
        muestra.sembrar(self.b2b)
        direcciones = Direccion.objects.filter(cliente__rut__in=muestra.RUT_ILUSTRATIVOS)
        self.assertGreater(direcciones.count(), 15)
        for d in direcciones:
            self.assertIsNotNone(d.lat, d.cliente.nombre)
            self.assertIsNotNone(d.long, d.cliente.nombre)

    def test_rut_validos(self):
        from .rut import es_valido
        for rut in muestra.RUT_ILUSTRATIVOS - {muestra.HOSPITAL_REGIONAL, muestra.SUPERMERCADOS_DEL_SUR}:      # esos dos ya existían, con RUT de otra serie
            self.assertTrue(es_valido(rut), rut)

    def test_prospectos_nuevos(self):
        antes = set(Prospecto.objects.values_list("pk", flat=True))
        muestra.sembrar(self.b2b)
        nuevos = list(Prospecto.objects.exclude(pk__in=antes))
        self.assertEqual(len(nuevos), 4)
        self.assertEqual({p.vendedor.usuario.username for p in nuevos}, {u.username for u in self.vendedores})
        perdidos = [p for p in nuevos if p.etapa.nombre == "Perdido"]
        self.assertEqual(len(perdidos), 1)
        self.assertTrue(perdidos[0].motivo_perdida and perdidos[0].cerrado_en)

    def test_limpiar_revierte(self):
        muestra.sembrar(self.b2b)
        resultado = muestra.limpiar()
        self.assertGreater(resultado["pedidos"], 0)
        self.assertEqual(conteos(), self.antes["conteos"])
        self.assertEqual(stock(), self.antes["stock"])
        self.assertEqual(self.historial().count(), 0)
        self.assertTrue(Orden.objects.filter(numero_oc="OC-REG-001").exists())
        self.assertTrue(Orden.objects.filter(numero_oc="OC-SUR-102").exists())
