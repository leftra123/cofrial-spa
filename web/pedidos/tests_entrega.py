"""Ciclo de entrega: el camión llega a la puerta, el cliente confirma o explica, y el plazo vencido lo da por entregado."""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from catalogo.models import Producto
from crm.models import Requerimiento
from flota import servicios as flota
from flota.models import Despacho
from pedidos import servicios as s
from pedidos.models import EstadoOrden, Orden

CLAVE = "demo-cofrial-2026"


class EntregaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def orden_despachada(self, usuario="ana@correo.test", camion="CAM-04"):
        """Una orden recién creada por el cliente y despachada con un camión libre (con la ruta de respaldo: sin red en las pruebas)."""
        cliente = s.cliente_de(__import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.get(username=usuario))
        s.agregar(cliente, Producto.objects.get(sku="POL-PEC-10K").pk if usuario != "ana@correo.test" else Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        orden = s.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]
        rango = flota.rangos_de(orden)[0]
        elegido = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        despacho = flota.despachar(elegido.camion_id, [orden.pk])
        orden.refresh_from_db()
        return cliente, orden, despacho

    def entrar(self, usuario="ana@correo.test"):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))


class EstadosTests(EntregaBase):
    def test_flujo_con_los_dos_estados_nuevos(self):
        nombres = list(EstadoOrden.objects.order_by("orden_flujo").values_list("nombre", "es_final"))
        self.assertEqual(nombres, [("Recibida", False), ("Confirmada", False), ("En preparación", False), ("Despachada", False),
                                   ("Camión en la puerta", False), ("Entregada", True), ("Entrega no concretada", False), ("Cancelada", True)])

    def test_avanzar_no_salta_a_estados_de_excepcion(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        self.assertEqual(s.avanzar(orden).estado_orden.nombre, "Entregada")           # desde la puerta solo se entrega
        no_concretada = Orden.objects.filter(estado_orden__nombre="Entregada").first()
        no_concretada.estado_orden = EstadoOrden.objects.get(nombre="Entrega no concretada")
        no_concretada.save()
        with self.assertRaises(s.ErrorDeNegocio):
            s.avanzar(no_concretada)

    def test_entrega_no_concretada_no_es_final_y_ventas_puede_darla_de_baja(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en la casa")
        orden.refresh_from_db()
        self.assertFalse(orden.estado_orden.es_final)
        with self.assertRaises(s.ErrorDeNegocio):
            s.cancelar(orden, como="cliente")
        stock = Producto.objects.get(sku="VAC-LOM-5K").stock_disponible
        s.cancelar(orden, como="vendedor")
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Cancelada")
        self.assertEqual(Producto.objects.get(sku="VAC-LOM-5K").stock_disponible, stock + 1)       # repone el stock


class PuertaYConfirmacionTests(EntregaBase):
    def test_llegar_a_la_puerta_solo_cambia_las_despachadas_y_es_idempotente(self):
        cliente, orden, _ = self.orden_despachada()
        self.assertEqual(s.llegar_a_la_puerta([orden]), 1)
        self.assertEqual(s.llegar_a_la_puerta([orden]), 0)
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.puerta_en is not None), ("Camión en la puerta", True))

    def test_aceptar_deja_la_orden_entregada(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Entregada")
        self.assertFalse(orden.entrega_automatica)
        self.assertIsNotNone(orden.entrega_resuelta_en)

    def test_no_recibido_exige_motivo_crea_requerimiento_ligado_y_guarda_el_motivo(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        with self.assertRaisesMessage(s.ErrorDeNegocio, "por qué"):
            s.resolver_entrega(cliente, orden.pk, "no_recibido", "  ")
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Camión en la puerta")          # el rechazo no cambió nada
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "Estaba cerrado el local")
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.entrega_motivo), ("Entrega no concretada", "Estaba cerrado el local"))
        r = Requerimiento.objects.get(orden=orden)
        self.assertEqual((r.cliente, r.descripcion), (cliente, "Estaba cerrado el local"))
        self.assertIn(str(orden.pk), r.asunto)

    def test_solo_se_responde_estando_en_la_puerta_y_una_sola_vez(self):
        cliente, orden, _ = self.orden_despachada()
        with self.assertRaisesMessage(s.ErrorDeNegocio, "ya no hay una entrega"):
            s.resolver_entrega(cliente, orden.pk, "aceptar")                 # todavía va en camino
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        with self.assertRaises(s.ErrorDeNegocio):
            s.resolver_entrega(cliente, orden.pk, "no_recibido", "ahora sí hay problema")
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Entregada")

    def test_accion_invalida(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        with self.assertRaises(s.ErrorDeNegocio):
            s.resolver_entrega(cliente, orden.pk, "otra", "")

    @override_settings(CONFIRMACION_AUTO_SEG=120)
    def test_el_plazo_vencido_da_por_entregado_y_no_pisa_lo_que_el_cliente_ya_decidio(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        ahora = timezone.now()
        self.assertEqual(s.confirmar_vencidas(ahora + timedelta(seconds=60)), 0)             # aún en plazo
        self.assertEqual(s.confirmar_vencidas(ahora + timedelta(seconds=121)), 1)
        self.assertEqual(s.confirmar_vencidas(ahora + timedelta(seconds=500)), 0)            # repetirla no cambia nada
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.entrega_automatica), ("Entregada", True))
        # una orden cuyo cliente rechazó la entrega no se da por entregada aunque pase el plazo
        c2, o2, _ = self.orden_despachada("abastecimiento@hospital.test")
        s.llegar_a_la_puerta([o2])
        s.resolver_entrega(c2, o2.pk, "no_recibido", "Nos faltó personal para recibir")
        self.assertEqual(s.confirmar_vencidas(timezone.now() + timedelta(hours=1)), 0)
        self.assertEqual(Orden.objects.get(pk=o2.pk).estado_orden.nombre, "Entrega no concretada")

    @override_settings(CONFIRMACION_AUTO_SEG=120)
    def test_quien_lee_las_ordenes_ve_aplicada_la_confirmacion_automatica(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        Orden.objects.filter(pk=orden.pk).update(puerta_en=timezone.now() - timedelta(seconds=300))
        self.assertEqual(s.ordenes_de(cliente).get(pk=orden.pk).estado_orden.nombre, "Entregada")


class EndpointEntregaTests(EntregaBase):
    def test_get_informa_el_estado_y_el_tiempo_que_queda(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        d = self.client.get(f"/pedidos/{orden.pk}/entrega/").json()
        self.assertTrue(d["puede_responder"])
        self.assertEqual(d["estado"], "Camión en la puerta")
        self.assertGreater(d["se_confirma_sola_en_seg"], 0)

    def test_post_aceptar_y_no_recibido_por_json(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        malo = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "no_recibido"}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(malo.status_code, 400)
        self.assertFalse(malo.json()["ok"])
        ok = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar"}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["entrega"]["estado"], "Entregada")

    def test_post_sin_js_vuelve_a_la_orden_con_mensaje(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "no_recibido", "motivo": "No estaba el encargado"}, follow=True)
        self.assertContains(r, "Registramos que no pudiste recibir")
        self.assertContains(r, "No pudimos entregar tu pedido")

    def test_una_orden_ajena_no_se_puede_confirmar(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar("abastecimiento@hospital.test")
        self.assertEqual(self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar"}).status_code, 404)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/entrega/").status_code, 404)
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Camión en la puerta")
        self.client.logout()
        self.assertEqual(self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar"}).status_code, 302)      # sin sesión: al acceso

    def test_pantalla_del_pedido_ofrece_las_dos_acciones_solo_en_la_puerta(self):
        cliente, orden, _ = self.orden_despachada()
        self.entrar()
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), "Recibí mi pedido")
        s.llegar_a_la_puerta([orden])
        r = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(r, "Estamos afuera de tu dirección")
        self.assertContains(r, "Recibí mi pedido")
        self.assertContains(r, "No pude recibirlo")

    def test_aviso_de_la_campanita_cuando_el_camion_esta_afuera(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        avisos = self.client.get("/api/avisos/").json()["avisos"]
        self.assertTrue(any(a["tipo"] == "puerta" and "afuera" in a["texto"] for a in avisos))


class MapaSegunEstadoTests(EntregaBase):
    """El cliente ve el mapa en vivo solo con el pedido en ruta o con el camión en la puerta."""

    def seguimiento(self, orden):
        self.entrar()
        return self.client.get(f"/api/pedidos/{orden.pk}/seguimiento/").json()

    def test_antes_de_salir_no_hay_mapa_ni_camion(self):
        cliente = s.cliente_de(__import__("django.contrib.auth", fromlist=["x"]).get_user_model().objects.get(username="ana@correo.test"))
        s.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        orden = s.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]
        for nombre in ("Recibida", "Confirmada", "En preparación"):
            Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre=nombre))
            d = self.seguimiento(orden)
            self.assertFalse(d["mapa_en_vivo"], nombre)
            self.assertIsNone(d["seguimiento"], nombre)
            self.assertEqual(d["mensaje"], "Tu pedido aún no sale.")
            self.assertEqual(self.client.get(f"/api/pedidos/{orden.pk}/ruta/").status_code, 404)

    def test_en_ruta_y_en_la_puerta_si_hay_mapa(self):
        cliente, orden, despacho = self.orden_despachada()
        from flota.models import Telemetria
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=False)
        for etapa in ("Despachada", "Camión en la puerta"):
            Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre=etapa))
            d = self.seguimiento(orden)
            self.assertTrue(d["mapa_en_vivo"], etapa)
            self.assertIsNotNone(d["seguimiento"]["ultima"]["lat"], etapa)
            r = self.client.get(f"/api/pedidos/{orden.pk}/ruta/")
            self.assertEqual(r.status_code, 200, etapa)
            self.assertTrue(r.json()["puntos"])

    def test_entregada_o_no_concretada_muestran_el_resumen_sin_posicion(self):
        cliente, orden, despacho = self.orden_despachada()
        from flota.models import Telemetria
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=False)
        for etapa in ("Entregada", "Entrega no concretada"):
            Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre=etapa))
            d = self.seguimiento(orden)
            self.assertFalse(d["mapa_en_vivo"], etapa)
            u = d["seguimiento"]["ultima"]
            self.assertIsNotNone(u["temp_camara"])
            self.assertIsNone(u["lat"])
            self.assertIsNone(d["seguimiento"]["destino"])
            self.assertEqual(self.client.get(f"/api/pedidos/{orden.pk}/ruta/").status_code, 404)

    def test_la_pagina_del_pedido_no_dibuja_mapa_en_vivo_al_entregar(self):
        cliente, orden, despacho = self.orden_despachada()
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        self.entrar()
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), "El mapa en vivo ya no está disponible")


class ReprogramarTests(EntregaBase):
    def test_una_entrega_no_concretada_se_puede_reprogramar_en_otro_viaje(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "No pude recibirlo hoy")
        self.assertIn(orden.pk, [o.pk for o in flota.pedidos_por_despachar()])               # vuelve a la lista del despachador
        rango = flota.rangos_de(orden)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango and c.camion_id != despacho.camion_id)
        nuevo = flota.despachar(camion.camion_id, [orden.pk])
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.despacho_id), ("Despachada", nuevo.pk))
        self.assertIsNone(orden.puerta_en)
        self.assertEqual(orden.entrega_motivo, "No pude recibirlo hoy")                       # el historial del motivo se conserva
        self.assertNotEqual(nuevo.pk, despacho.pk)
