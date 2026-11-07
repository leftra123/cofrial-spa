"""RN-09 y flujos del vendedor que un profesor probaría con dos cuentas abiertas (docs/matriz-casos-de-uso.md)."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from clientes.models import Cliente, Comuna
from crm import servicios as s
from crm.models import CategoriaRequerimiento, EtapaPipeline, Prospecto, Requerimiento
from flota import servicios as flota
from flota.models import Telemetria
from pedidos import servicios as pedidos
from pedidos.models import CarritoItem, EstadoOrden, Orden

CLAVE = "demo-cofrial-2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        U = get_user_model()
        cls.maria, cls.pedro = U.objects.get(username="vendedora@cofrial.cl"), U.objects.get(username="vendedor2@cofrial.cl")
        cls.gerencia = U.objects.get(username="gerencia@cofrial.cl")
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")        # cartera de María
        cls.sur = Cliente.objects.get(rut="76.543.210-K")             # cartera de Pedro
        cls.ana = Cliente.objects.get(rut="12.345.678-5")             # B2C, sin vendedor
        cls.producto = Producto.objects.filter(activo=True, stock_disponible__gt=20, categoria__rango_temperatura__nombre="Refrigerado").first()

    def setUp(self):
        cache.clear()

    def entrar(self, usuario):
        self.client.logout()
        self.client.login(username=usuario, password=CLAVE)

    def etapa(self, nombre):
        return EtapaPipeline.objects.get(nombre=nombre).pk

    def orden_de(self, cliente, cantidad=1, oc="OC-1"):
        pedidos.agregar(cliente, self.producto.pk, cantidad)
        return pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, oc)


class ReclamosPorCartera(Base):
    def setUp(self):
        super().setUp()
        Requerimiento.objects.all().delete()
        self.del_hospital = Requerimiento.objects.create(cliente=self.hospital, asunto="Reclamo del hospital", descripcion="Llegó tarde")
        self.de_ana = Requerimiento.objects.create(cliente=self.ana, asunto="Consulta de Ana", descripcion="Sin vendedor")

    def test_la_bandeja_de_otro_vendedor_no_muestra_el_reclamo_ajeno(self):
        self.entrar("vendedor2@cofrial.cl")
        bandeja = self.client.get("/crm/requerimientos/")
        self.assertNotContains(bandeja, "Reclamo del hospital")
        self.assertContains(bandeja, "Consulta de Ana")                         # sin vendedor: bandeja común
        self.assertEqual(self.client.get(f"/crm/requerimientos/{self.del_hospital.pk}/").status_code, 404)

    def test_el_dueno_de_la_cartera_y_gerencia_si_lo_ven(self):
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "admin@cofrial.cl"):
            self.entrar(usuario)
            self.assertContains(self.client.get("/crm/requerimientos/"), "Reclamo del hospital")
            self.assertEqual(self.client.get(f"/crm/requerimientos/{self.del_hospital.pk}/").status_code, 200)

    def test_otro_vendedor_no_clasifica_ni_reintenta_el_reclamo_ajeno(self):
        self.entrar("vendedor2@cofrial.cl")
        categoria = CategoriaRequerimiento.objects.first()
        self.client.post(f"/crm/requerimientos/{self.del_hospital.pk}/clasificar/", {"categoria": categoria.pk})
        with patch("crm.ia.clasificar") as ia:
            self.client.post(f"/crm/requerimientos/{self.del_hospital.pk}/ia/")
        ia.assert_not_called()
        self.del_hospital.refresh_from_db()
        self.assertEqual((self.del_hospital.estado, self.del_hospital.categoria_requerimiento), ("sin_clasificar", None))

    def test_el_panel_de_ia_y_los_indicadores_tambien_respetan_la_cartera(self):
        self.entrar("vendedor2@cofrial.cl")
        panel = self.client.get("/crm/ia/")
        self.assertNotContains(panel, "Reclamo del hospital")
        self.assertEqual(panel.context["resumen"]["total"], 1)
        self.assertEqual(s.indicadores(self.pedro)["requerimientos_pendientes"], 1)
        self.assertEqual(s.indicadores(self.maria)["requerimientos_pendientes"], 2)


class CierreDelReclamo(Base):
    def setUp(self):
        super().setUp()
        self.categoria = CategoriaRequerimiento.objects.first()
        self.r = Requerimiento.objects.create(cliente=self.hospital, asunto="Faltó una caja", descripcion="Llegó incompleto",
                                              categoria_requerimiento=self.categoria, estado="clasificado")

    def test_el_vendedor_lo_resuelve_y_el_cliente_lo_ve_en_soporte(self):
        self.entrar("vendedora@cofrial.cl")
        self.assertContains(self.client.get(f"/crm/requerimientos/{self.r.pk}/"), "Marcar como resuelto")
        self.client.post(f"/crm/requerimientos/{self.r.pk}/resolver/")
        self.r.refresh_from_db()
        self.assertEqual(self.r.estado, "resuelto")
        self.assertIsNotNone(self.r.respondido_en)                              # alimenta el indicador de primera respuesta
        self.entrar("abastecimiento@hospital.test")
        self.assertContains(self.client.get("/soporte/"), "resuelto")

    def test_sin_clasificar_no_se_resuelve_y_resuelto_no_se_reabre(self):
        sin = Requerimiento.objects.create(cliente=self.hospital, asunto="x", descripcion="y")
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Clasifícalo antes"):
            s.resolver_requerimiento(self.maria, sin.pk)
        s.resolver_requerimiento(self.maria, self.r.pk)
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Ya está resuelto"):
            s.resolver_requerimiento(self.maria, self.r.pk)
        with self.assertRaises(s.ErrorDeNegocio):
            s.clasificar_manual(self.maria, self.r.pk, self.categoria.pk)
        with self.assertRaises(s.ErrorDeNegocio):
            s.reintentar_ia(self.maria, self.r.pk)

    def test_otro_vendedor_y_gerencia_no_lo_resuelven(self):
        self.entrar("vendedor2@cofrial.cl")
        self.client.post(f"/crm/requerimientos/{self.r.pk}/resolver/")
        self.entrar("gerencia@cofrial.cl")
        self.client.post(f"/crm/requerimientos/{self.r.pk}/resolver/")
        self.r.refresh_from_db()
        self.assertEqual(self.r.estado, "clasificado")


class Embudo(Base):
    def test_a5_de_propuesta_enviada_vuelve_a_contactado(self):
        p = Prospecto.objects.get(nombre_contacto="Luis Soto")                  # Propuesta enviada, de Pedro
        self.assertEqual(s.mover_prospecto(self.pedro, p.pk, self.etapa("Contactado")).etapa.nombre, "Contactado")
        self.assertEqual(s.mover_prospecto(self.pedro, p.pk, self.etapa("Propuesta enviada")).etapa.nombre, "Propuesta enviada")

    def test_solo_propuesta_enviada_retrocede(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")                  # Negociación
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.pedro, p.pk, self.etapa("Propuesta enviada"))

    def test_la_ficha_ofrece_volver_a_contactado(self):
        self.entrar("vendedor2@cofrial.cl")
        p = Prospecto.objects.get(nombre_contacto="Luis Soto")
        self.assertIn("Contactado", [e.nombre for e in self.client.get(f"/crm/prospectos/{p.pk}/").context["destinos"]])

    def test_ganar_exige_un_rut_valido(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")
        for malo in ("11111111-2", "123", "abc", "111111111111-1"):
            with self.assertRaisesMessage(s.ErrorDeNegocio, "RUT no es válido"):
                s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut=malo)
        self.assertEqual(Prospecto.objects.get(pk=p.pk).etapa.nombre, "Negociación")

    def test_el_mismo_rut_con_otro_formato_es_el_mismo_cliente(self):
        Cliente.objects.create(tipo_cliente=self.hospital.tipo_cliente, rut="11.111.111-1", nombre="Ya existe", email="y@x.test")
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Ya existe un cliente"):
            s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut="11111111-1")

    def test_el_rut_se_guarda_con_el_formato_del_registro(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")
        self.assertEqual(s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut="111111111").cliente.rut, "11.111.111-1")

    def test_un_dato_malo_no_muestra_texto_de_python(self):
        self.entrar("vendedora@cofrial.cl")
        for r in (self.client.post(f"/crm/clientes/{self.hospital.pk}/pedido/", {"q_abc": "1"}, follow=True),
                  self.client.post(f"/crm/prospectos/{Prospecto.objects.get(nombre_contacto='Jorge Rivas').pk}/mover/", {"etapa": "²"}, follow=True)):
            self.assertNotContains(r, "invalid literal")
            self.assertNotContains(r, "número no válido")
            self.assertContains(r, "Dato no válido")


class ClienteGanadoCompra(Base):
    def test_el_vendedor_le_agrega_direccion_y_le_crea_el_pedido(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")
        nuevo = s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut="11.111.111-1").cliente
        self.entrar("vendedor2@cofrial.cl")
        with patch("clientes.geo.geocodificar", return_value=None):
            r = self.client.post(f"/crm/clientes/{nuevo.pk}/direccion/", {"calle_numero": "Feria 1", "comuna": Comuna.objects.first().pk}, follow=True)
        self.assertContains(r, "Sin ubicar en el mapa")
        d = nuevo.direccion_set.get()
        self.assertTrue(d.es_principal)
        orden = s.crear_pedido_para_cliente(self.pedro, nuevo.pk, {self.producto.pk: 1}, d.pk, "", "llamada", "Primer pedido")
        self.assertEqual(orden.direccion.cliente, nuevo)

    def test_otro_vendedor_y_gerencia_no_agregan_direcciones(self):
        n = self.hospital.direccion_set.count()
        self.entrar("vendedor2@cofrial.cl")
        self.assertEqual(self.client.post(f"/crm/clientes/{self.hospital.pk}/direccion/", {"calle_numero": "x", "comuna": 1}).status_code, 404)
        self.entrar("gerencia@cofrial.cl")
        self.client.post(f"/crm/clientes/{self.hospital.pk}/direccion/", {"calle_numero": "x", "comuna": Comuna.objects.first().pk})
        self.assertEqual(self.hospital.direccion_set.count(), n)


class PedidoANombreDelCliente(Base):
    def test_no_borra_lo_que_el_cliente_tenia_en_su_carrito(self):
        otro = Producto.objects.filter(activo=True, stock_disponible__gt=20).exclude(pk=self.producto.pk).first()
        pedidos.agregar(self.hospital, otro.pk, 3)
        orden = s.crear_pedido_para_cliente(self.maria, self.hospital.pk, {self.producto.pk: 1}, self.hospital.direccion_set.first().pk, "OC-9", "llamada", "Llamó")
        self.assertEqual([i.producto_id for i in orden.ordenitem_set.all()], [self.producto.pk])     # el pedido lleva solo lo que dictó
        self.assertEqual(list(CarritoItem.objects.filter(carrito__cliente=self.hospital, carrito__estado="abierto").values_list("producto_id", "cantidad")), [(otro.pk, 3)])

    def test_si_falla_tampoco_se_pierde_el_carrito(self):
        otro = Producto.objects.filter(activo=True, stock_disponible__gt=20).exclude(pk=self.producto.pk).first()
        pedidos.agregar(self.hospital, otro.pk, 3)
        with self.assertRaises(pedidos.ErrorDeNegocio):
            s.crear_pedido_para_cliente(self.maria, self.hospital.pk, {self.producto.pk: 1}, 999999, "OC-9", "llamada", "Llamó")
        self.assertEqual(CarritoItem.objects.filter(carrito__cliente=self.hospital, carrito__estado="abierto").count(), 1)


class CancelacionDelVendedor(Base):
    def stock(self):
        return Producto.objects.get(pk=self.producto.pk).stock_disponible

    def test_el_vendedor_cancela_desde_la_ficha_y_repone_el_stock(self):
        antes = self.stock()
        orden = self.orden_de(self.hospital, 2)
        self.entrar("vendedora@cofrial.cl")
        ficha = self.client.get(f"/crm/clientes/{self.hospital.pk}/")
        self.assertContains(ficha, f"/crm/ordenes/{orden.pk}/cancelar/")
        r = self.client.post(f"/crm/ordenes/{orden.pk}/cancelar/", {"volver": f"/crm/clientes/{self.hospital.pk}/"}, follow=True)
        self.assertContains(r, "cancelado")
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, self.stock()), ("Cancelada", antes))

    def test_llega_hasta_en_preparacion_y_no_despues(self):
        orden = pedidos.avanzar(pedidos.avanzar(self.orden_de(self.hospital)))
        self.assertEqual(orden.estado_orden.nombre, "En preparación")
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Despachada"))
        with self.assertRaisesMessage(pedidos.ErrorDeNegocio, "ya no puede cancelarla"):
            s.cancelar_orden(self.maria, orden.pk)
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="En preparación"))
        self.assertEqual(s.cancelar_orden(self.maria, orden.pk).estado_orden.nombre, "Cancelada")

    def test_una_entrega_no_concretada_se_puede_dar_de_baja(self):
        orden = self.orden_de(self.hospital)
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entrega no concretada"))
        self.assertEqual(s.cancelar_orden(self.maria, orden.pk).estado_orden.nombre, "Cancelada")

    def test_ni_otro_vendedor_ni_gerencia_ni_el_cliente_usan_esta_ruta(self):
        orden = self.orden_de(self.hospital)
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Orden no encontrada en tu cartera"):
            s.cancelar_orden(self.pedro, orden.pk)
        with self.assertRaisesMessage(s.ErrorDeNegocio, "Tu rol no puede"):
            s.cancelar_orden(self.gerencia, orden.pk)
        self.entrar("abastecimiento@hospital.test")
        self.assertEqual(self.client.post(f"/crm/ordenes/{orden.pk}/cancelar/").status_code, 403)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Recibida")

    def test_una_orden_entregada_no_ofrece_el_boton(self):
        orden = self.orden_de(self.hospital)
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        self.entrar("vendedora@cofrial.cl")
        self.assertNotContains(self.client.get(f"/crm/clientes/{self.hospital.pk}/"), f"/crm/ordenes/{orden.pk}/cancelar/")


@override_settings(OSRM_URL="")
class ViajeCompartido(Base):
    """Dos clientes en el mismo camión: una ruptura de frío solo afecta a la carga que todavía iba a bordo."""

    def setUp(self):
        super().setUp()
        self.primera, self.segunda = self.orden_de(self.ana), self.orden_de(self.hospital)
        camion = flota.camiones_libres().filter(rango_temperatura__nombre="Refrigerado").first()
        self.despacho = flota.despachar(camion.pk, [self.primera.pk, self.segunda.pk])
        self.camion = camion

    def lectura(self, alerta=True, temp=9.0, hace_min=0):
        t = Telemetria.objects.create(camion=self.camion, temp_camara=temp, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=alerta)
        if hace_min:
            Telemetria.objects.filter(pk=t.pk).update(registrado_en=timezone.now() - timedelta(minutes=hace_min))
        return t

    def alertas(self, cliente):
        return next(o.alertas_frio for o in s.ordenes_de_cliente(cliente) if o.despacho_id == self.despacho.pk)

    def test_la_alerta_durante_el_viaje_afecta_a_los_dos(self):
        self.lectura()
        self.assertEqual((self.alertas(self.ana), self.alertas(self.hospital)), (1, 1))

    def test_una_alerta_anterior_a_la_salida_no_cuenta(self):
        self.lectura(hace_min=30)
        self.assertEqual((self.alertas(self.ana), self.alertas(self.hospital)), (0, 0))

    def test_la_alerta_despues_de_entregar_al_primero_solo_afecta_al_segundo(self):
        pedidos.llegar_a_la_puerta([self.primera])
        pedidos.resolver_entrega(self.ana, self.primera.pk, "aceptar")
        self.lectura()
        self.assertEqual((self.alertas(self.ana), self.alertas(self.hospital)), (0, 1))
        self.assertNotIn(self.primera.pk, [o.pk for o in s.ordenes_afectadas(get_user_model().objects.get(username="admin@cofrial.cl"))])

    def test_ruptura_con_el_camion_en_la_ultima_puerta_cuenta(self):
        """El simulador fija llegada_en al llegar a la última parada, pero el cliente aún no recibe: la carga sigue en el camión."""
        pedidos.llegar_a_la_puerta([self.segunda])
        type(self.despacho).objects.filter(pk=self.despacho.pk).update(salida_en=timezone.now() - timedelta(minutes=10), llegada_en=timezone.now() - timedelta(seconds=30))
        self.lectura()
        self.assertEqual(self.alertas(self.hospital), 1)

    def test_el_reclamo_muestra_la_telemetria_aunque_la_ia_este_caida(self):
        self.lectura()
        with override_settings(GEMINI_API_KEY="", GROQ_API_KEY="", ANTHROPIC_API_KEY=""), patch("crm.ia.clasificar", side_effect=s.ia.ErrorIA("caída")):
            r = s.crear_requerimiento(self.hospital, "Carga caliente", "La carne llegó tibia", orden=self.segunda)
        self.assertEqual((r.estado, r.desglose), ("sin_clasificar", None))
        self.entrar("vendedora@cofrial.cl")
        pantalla = self.client.get(f"/crm/requerimientos/{r.pk}/")
        self.assertContains(pantalla, "Dato real de la base")
        self.assertContains(pantalla, "9,0 °C")

    def test_un_reclamo_que_no_habla_de_frio_no_muestra_la_telemetria(self):
        with patch("crm.ia.clasificar", side_effect=s.ia.ErrorIA("caída")):
            r = s.crear_requerimiento(self.hospital, "Factura", "Falta una factura", orden=self.segunda)
        self.entrar("vendedora@cofrial.cl")
        self.assertNotContains(self.client.get(f"/crm/requerimientos/{r.pk}/"), "Dato real de la base")
