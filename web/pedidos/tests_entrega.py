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
                                   ("Camión en la puerta", False), ("Entregada", True), ("Entrega no concretada", False), ("Cancelada", True), ("Rechazada en recepción", True)])

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
        self.assertContains(r, "Tu paquete llegó")
        self.assertNotContains(r, "Pedido entregado exitosamente")
        self.assertContains(r, "Recibí mi pedido")
        self.assertContains(r, "No recibiré mi pedido")

    def test_aviso_de_la_campanita_cuando_el_camion_esta_afuera(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        avisos = self.client.get("/api/avisos/").json()["avisos"]
        self.assertTrue(any(a["tipo"] == "puerta" and "afuera" in a["texto"] for a in avisos))


class MapaSegunEstadoTests(EntregaBase):
    """El cliente ve el mapa en vivo solo mientras el pedido va en camino y el camión no llegó a esta parada."""

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

    def test_la_pantalla_abierta_pasa_sola_a_en_camino_y_el_catalogo_no(self):
        cliente = s.cliente_de(__import__("django.contrib.auth", fromlist=["x"]).get_user_model().objects.get(username="ana@correo.test"))
        s.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        orden = s.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]
        Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre="En preparación"))
        self.entrar()
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "Estamos preparando tu pedido")
        self.assertContains(pagina, "pasa sola a «en camino»")
        self.assertContains(pagina, "espera-salida")
        self.assertContains(pagina, f"/api/pedidos/{orden.pk}/seguimiento/")
        self.assertNotContains(pagina, "Tu pedido va en camino")
        self.assertNotContains(pagina, 'id="seg"', html=False)
        self.assertNotContains(self.client.get("/catalogo/"), "espera-salida")
        rango = flota.rangos_de(orden)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        flota.despachar(camion.camion_id, [orden.pk])
        salida = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(salida, "Tu pedido va en camino")
        self.assertContains(salida, 'id="seg"', html=False)
        self.assertContains(salida, 'id="mapa"', html=False)
        self.assertNotContains(salida, "espera-salida")

    def test_en_ruta_si_hay_mapa(self):
        cliente, orden, despacho = self.orden_despachada()
        from flota.models import Telemetria
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=False)
        d = self.seguimiento(orden)
        self.assertEqual(d["estado"], "Despachada")
        self.assertTrue(d["mapa_en_vivo"])
        self.assertIsNotNone(d["seguimiento"]["ultima"]["lat"])
        r = self.client.get(f"/api/pedidos/{orden.pk}/ruta/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["puntos"])
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, 'id="mapa"', html=False)
        self.assertContains(pagina, "Última señal")

    def test_en_la_puerta_no_vuelve_el_mapa_aunque_se_recargue(self):
        cliente, orden, despacho = self.orden_despachada()
        from flota.models import Telemetria
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=False)
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        d = self.seguimiento(orden)
        self.assertEqual(d["estado"], "Camión en la puerta")
        self.assertFalse(d["mapa_en_vivo"])
        u = d["seguimiento"]["ultima"]
        self.assertIsNotNone(u["temp_camara"])
        self.assertIsNone(u["lat"])
        self.assertIsNone(u["long"])
        self.assertIsNone(d["seguimiento"]["destino"])
        self.assertIsNone(d["seguimiento"]["ruta_url"])
        self.assertIsNotNone(d["seguimiento"]["llegada_en"])
        self.assertEqual(self.client.get(f"/api/pedidos/{orden.pk}/ruta/").status_code, 404)
        for _ in range(2):                                          # la recarga pide la misma página y tampoco dibuja el mapa
            pagina = self.client.get(f"/pedidos/{orden.pk}/")
            self.assertContains(pagina, "Tu paquete llegó")
            self.assertContains(pagina, "Tu pedido llegó a su destino")
            self.assertContains(pagina, "Registro de temperatura del viaje")
            self.assertContains(pagina, "Llegó")
            self.assertContains(pagina, orden.quien_recibe)
            self.assertContains(pagina, str(orden.direccion))
            self.assertNotContains(pagina, "Última señal")
            self.assertNotContains(pagina, "Llega entre")
            self.assertNotContains(pagina, 'id="mapa"', html=False)
            self.assertNotContains(pagina, 'id="seg-vivo"', html=False)
            self.assertNotContains(pagina, "El mapa en vivo ya no está disponible")
            self.assertNotContains(pagina, "Pedido entregado exitosamente")

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
        self.entrar()
        for etapa, titulo in (("Entregada", "Tu pedido llegó a su destino"),
                              ("Rechazada en recepción", "Tu pedido llegó a su destino"),
                              ("Entrega no concretada", "El seguimiento de este pedido terminó")):
            Orden.objects.filter(pk=orden.pk).update(estado_orden=EstadoOrden.objects.get(nombre=etapa))
            pagina = self.client.get(f"/pedidos/{orden.pk}/")
            self.assertContains(pagina, titulo, msg_prefix=etapa)
            self.assertContains(pagina, "Registro de temperatura del viaje", msg_prefix=etapa)
            self.assertNotContains(pagina, "Última señal", msg_prefix=etapa)
            self.assertNotContains(pagina, 'id="mapa"', html=False, msg_prefix=etapa)
            self.assertNotContains(pagina, "El mapa en vivo ya no está disponible", msg_prefix=etapa)
            self.assertNotContains(pagina, "Pedido entregado exitosamente", msg_prefix=etapa)            # no lo confirmó el cliente


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


class ParadasDelViajeTests(EntregaBase):
    """COF-01: el conductor ve las paradas en el mismo orden del viaje guardado."""

    def _dos_en_el_mismo_camion(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ana = s.cliente_de(User.objects.get(username="ana@correo.test"))
        hospital = s.cliente_de(User.objects.get(username="abastecimiento@hospital.test"))
        s.agregar(ana, Producto.objects.get(sku="POL-PEC-10K").pk, 1)
        s.agregar(hospital, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        oa = s.generar_ordenes(ana, ana.direccion_set.first().pk)[0]
        ob = s.generar_ordenes(hospital, hospital.direccion_set.first().pk)[0]
        rango = flota.rangos_de(oa)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        despacho = flota.despachar(camion.camion_id, [oa.pk, ob.pk])
        oa.refresh_from_db()
        ob.refresh_from_db()
        return oa, ob, despacho

    def test_el_conductor_lista_las_paradas_en_el_mismo_orden(self):
        oa, ob, despacho = self._dos_en_el_mismo_camion()
        esperado = []
        for parada in despacho.ruta_geojson["paradas"]:
            esperado.append(oa.orden_id if parada["direccion_id"] == oa.direccion_id else ob.orden_id)
        self.entrar("despacho@cofrial.cl")
        html = self.client.get("/flota/").content.decode()
        posiciones = [html.index(f"Orden N.º {n}") for n in esperado]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIn("Un solo recorrido. Las paradas se atienden en este orden.", html)


class EntregaExitosaTests(EntregaBase):
    """COF-02: el paquete llegado no se da por entregado hasta confirmar, y ahí se cierra el recorrido de ese viaje."""

    def test_al_confirmar_la_pantalla_dice_entregado_y_el_viaje_queda_finalizado(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        puerta = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(puerta, "Tu paquete llegó")
        self.assertNotContains(puerta, "Pedido entregado exitosamente")
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        despacho.refresh_from_db()
        self.assertEqual(despacho.fase, "volviendo")
        self.assertIsNotNone(despacho.llegada_en)
        self.assertIsNone(despacho.regreso_en)
        hecho = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(hecho, "Pedido entregado exitosamente")
        self.assertContains(hecho, "Recorrido cerrado")
        self.assertContains(hecho, "el camión vuelve a la bodega")
        self.assertNotContains(hecho, "Tu paquete llegó")

    def test_si_queda_otra_parada_el_camion_no_cierra_el_viaje(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ana = s.cliente_de(User.objects.get(username="ana@correo.test"))
        hospital = s.cliente_de(User.objects.get(username="abastecimiento@hospital.test"))
        s.agregar(ana, Producto.objects.get(sku="POL-PEC-10K").pk, 1)
        s.agregar(hospital, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
        oa = s.generar_ordenes(ana, ana.direccion_set.first().pk)[0]
        ob = s.generar_ordenes(hospital, hospital.direccion_set.first().pk)[0]
        rango = flota.rangos_de(oa)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        despacho = flota.despachar(camion.camion_id, [oa.pk, ob.pk])
        s.llegar_a_la_puerta([oa])
        s.resolver_entrega(ana, oa.pk, "aceptar")
        despacho.refresh_from_db()
        ob.refresh_from_db()
        self.assertEqual(despacho.fase, "en_ruta")
        self.assertEqual(ob.estado_orden.nombre, "Despachada")
        self.entrar()
        self.assertContains(self.client.get(f"/pedidos/{oa.pk}/"), "El camión sigue con otros pedidos")

    def test_la_confirmacion_automatica_no_se_presenta_como_exitosa(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        s.confirmar_vencidas(orden.puerta_en + timedelta(seconds=121))
        self.entrar()
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "lo dimos por entregado")
        self.assertNotContains(pagina, "Pedido entregado exitosamente")
        despacho.refresh_from_db()
        self.assertEqual(despacho.fase, "volviendo")

    def test_si_la_ultima_parada_no_pudo_recibir_tambien_termina_el_recorrido(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en casa")
        despacho.refresh_from_db()
        self.assertEqual(despacho.fase, "volviendo")
        self.assertIsNotNone(despacho.llegada_en)

    def test_confirmar_una_entrega_no_cierra_el_viaje_de_otro_camion(self):
        from flota.models import Despacho
        cliente, orden, despacho = self.orden_despachada()
        otro = Despacho.objects.create(camion=flota.camiones_libres()[0], programado_para=despacho.programado_para, salida_en=despacho.salida_en, fase="en_ruta")     # sin pedidos pendientes
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        otro.refresh_from_db()
        self.assertEqual(otro.fase, "en_ruta")
        self.assertIsNone(otro.llegada_en)
