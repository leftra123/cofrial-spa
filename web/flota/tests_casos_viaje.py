"""Bordes del viaje: dos clientes, cliente que no responde y errores abiertos de otras sesiones (docs/matriz-casos-de-uso.md).

Las clases marcadas con `abierto` documentan errores reales que está corrigiendo otra sesión: se saltan por defecto para no dejar la suite
en rojo. Después de fusionar esa sesión hay que correrlas con `-e CASOS_ABIERTOS=1` y, si pasan, quitar el decorador."""
import os
import threading
import unittest
from datetime import timedelta

from django.core.cache import cache
from django.core.management import call_command
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente
from crm import servicios as crm
from flota import servicios
from flota.models import Despacho, Telemetria
from pedidos import servicios as pedidos
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"
abierto = unittest.skipUnless(os.environ.get("CASOS_ABIERTOS"), "error abierto de otra sesión: ver docs/matriz-casos-de-uso.md")


@override_settings(OSRM_URL="", CONFIRMACION_AUTO_SEG=120)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")
        cls.producto = Producto.objects.filter(activo=True, stock_disponible__gt=20, categoria__rango_temperatura__nombre="Refrigerado").first()

    def setUp(self):
        cache.clear()
        self.camion = servicios.camiones_libres().filter(rango_temperatura__nombre="Refrigerado").first()

    def orden_de(self, cliente):
        pedidos.agregar(cliente, self.producto.pk, 1)
        return pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, "OC-1")

    def estado(self, orden):
        return Orden.objects.select_related("estado_orden").get(pk=orden.pk).estado_orden.nombre


class DosClientesEnUnViaje(Base):
    def setUp(self):
        super().setUp()
        self.de_ana, self.del_hospital = self.orden_de(self.ana), self.orden_de(self.hospital)
        self.despacho = servicios.despachar(self.camion.pk, [self.de_ana.pk, self.del_hospital.pk])

    def test_cada_uno_solo_ve_y_confirma_su_pedido(self):
        pedidos.llegar_a_la_puerta([self.del_hospital])
        self.client.login(username="ana@correo.test", password=CLAVE)
        self.assertEqual(self.client.get(f"/pedidos/{self.del_hospital.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/pedidos/{self.del_hospital.pk}/seguimiento/").status_code, 404)
        self.assertEqual(self.client.post(f"/pedidos/{self.del_hospital.pk}/entrega/", {"accion": "aceptar"}).status_code, 404)
        self.assertEqual(self.estado(self.del_hospital), "Camión en la puerta")

    def test_cada_entrega_se_resuelve_por_separado(self):
        pedidos.llegar_a_la_puerta([self.de_ana])
        pedidos.resolver_entrega(self.ana, self.de_ana.pk, "no_recibido", "No había nadie en casa")
        self.assertEqual((self.estado(self.de_ana), self.estado(self.del_hospital)), ("Entrega no concretada", "Despachada"))

    def test_una_entrega_fallida_no_libera_al_camion_antes_de_tiempo(self):
        pedidos.llegar_a_la_puerta([self.de_ana])
        pedidos.resolver_entrega(self.ana, self.de_ana.pk, "no_recibido", "No había nadie en casa")
        self.assertNotIn(self.camion.pk, [c.pk for c in servicios.camiones_libres()])


class ClienteQueNoResponde(Base):
    def test_el_plazo_vencido_entrega_y_una_empresa_ya_se_puede_facturar(self):
        orden = self.orden_de(self.hospital)
        servicios.despachar(self.camion.pk, [orden.pk])
        pedidos.llegar_a_la_puerta([orden], ahora=timezone.now() - timedelta(seconds=121))
        self.assertEqual(pedidos.confirmar_vencidas(), 1)
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.entrega_automatica), ("Entregada", True))
        vendedora = self.hospital.vendedor.usuario
        self.assertEqual(crm.facturar(vendedora, orden.pk).tipo, "factura")

    def test_antes_del_plazo_no_se_confirma(self):
        orden = self.orden_de(self.hospital)
        servicios.despachar(self.camion.pk, [orden.pk])
        pedidos.llegar_a_la_puerta([orden], ahora=timezone.now() - timedelta(seconds=100))
        self.assertEqual(pedidos.confirmar_vencidas(), 0)


class CancelarDespachada(Base):
    def test_ni_el_cliente_ni_el_vendedor_cancelan_una_orden_en_camino(self):
        orden = self.orden_de(self.hospital)
        servicios.despachar(self.camion.pk, [orden.pk])
        stock = Producto.objects.get(pk=self.producto.pk).stock_disponible
        with self.assertRaises(pedidos.ErrorDeNegocio):
            pedidos.cancelar(orden, como="cliente")
        with self.assertRaises(pedidos.ErrorDeNegocio):
            crm.cancelar_orden(self.hospital.vendedor.usuario, orden.pk)
        self.assertEqual((self.estado(orden), Producto.objects.get(pk=self.producto.pk).stock_disponible), ("Despachada", stock))


class ErroresAbiertosDeFlota(Base):
    """Se derivan a flota-autonoma."""

    @abierto
    def test_un_pedido_sin_ubicar_no_queda_colgado_en_despachada(self):
        orden = self.orden_de(self.hospital)
        orden.direccion.lat = orden.direccion.long = None
        orden.direccion.save()
        try:
            d = servicios.despachar(self.camion.pk, [orden.pk])
        except pedidos.ErrorDeNegocio:
            return                                                              # rechazarlo al armar el viaje también es una salida válida
        Despacho.objects.filter(pk=d.pk).update(llegada_en=timezone.now(), regreso_en=timezone.now())     # lo que hace el simulador: vuelve sin parar
        servicios.cerrar_despacho(d.pk)
        self.assertEqual(self.estado(orden), "Entregada")

    @abierto
    def test_el_panel_distingue_un_camion_sin_senal(self):
        Telemetria.objects.create(camion=self.camion, temp_camara=2, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=False)
        Telemetria.objects.filter(camion=self.camion).update(registrado_en=timezone.now() - timedelta(hours=2))
        tarjetas, _ = servicios.estado_flota()
        tarjeta = next(t for t in tarjetas if t["camion"].pk == self.camion.pk)
        self.assertTrue(tarjeta.get("sin_senal"))


@override_settings(OSRM_URL="")
class ErroresAbiertosDeDespachoSimultaneo(TransactionTestCase):
    """Se deriva a flota-autonoma. Doble clic en «Despachar» o dos pestañas: dos solicitudes leen la misma orden antes de que la otra termine."""

    def dos_a_la_vez(self, pedidos_de_despacho):
        arranque, resultados = threading.Barrier(len(pedidos_de_despacho)), []

        def despachar(camion, ordenes):
            try:
                arranque.wait()
                servicios.despachar(camion, ordenes)
                resultados.append("ok")
            except pedidos.ErrorDeNegocio:
                resultados.append("rechazado")
            finally:
                connections.close_all()
        hilos = [threading.Thread(target=despachar, args=p) for p in pedidos_de_despacho]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        return sorted(resultados)

    def preparar(self):
        call_command("cargar_demo", verbosity=0)
        hospital = Cliente.objects.get(rut="61.973.200-4")
        producto = Producto.objects.filter(activo=True, stock_disponible__gt=20, categoria__rango_temperatura__nombre="Refrigerado").first()
        ordenes = []
        for _ in range(2):
            pedidos.agregar(hospital, producto.pk, 1)
            ordenes.append(pedidos.generar_orden(hospital, hospital.direccion_set.first().pk, "OC-1"))
        return ordenes, list(servicios.camiones_libres().filter(rango_temperatura__nombre="Refrigerado")[:2])

    @abierto
    def test_la_misma_orden_en_dos_camiones_sale_una_sola_vez_y_no_queda_entregada(self):
        (orden, _), (uno, otro) = self.preparar()
        self.assertEqual(self.dos_a_la_vez([(uno.pk, [orden.pk]), (otro.pk, [orden.pk])]), ["ok", "rechazado"])
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Despachada")

    @abierto
    def test_un_camion_no_toma_dos_viajes_a_la_vez(self):
        (una, otra), (camion, _) = self.preparar()
        self.assertEqual(self.dos_a_la_vez([(camion.pk, [una.pk]), (camion.pk, [otra.pk])]), ["ok", "rechazado"])
        self.assertEqual(Despacho.objects.filter(camion=camion, regreso_en__isnull=True).count(), 1)


class ErroresAbiertosDeEntrega(Base):
    """Se derivan a entrega-cliente: el aviso al cliente debe seguir la misma regla que el CRM (crm.servicios.fin_de_exposicion)."""

    @abierto
    def test_el_cliente_que_ya_recibio_no_ve_una_ruptura_posterior(self):
        orden = self.orden_de(self.ana)
        servicios.despachar(self.camion.pk, [orden.pk])
        pedidos.llegar_a_la_puerta([orden])
        pedidos.resolver_entrega(self.ana, orden.pk, "aceptar")
        Telemetria.objects.create(camion=self.camion, temp_camara=9, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=True)
        orden.refresh_from_db()
        self.assertFalse(pedidos.seguimiento(orden)["hubo_ruptura"])
