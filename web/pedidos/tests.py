import threading

from django.core.management import call_command
from django.db import connections
from django.test import TestCase, TransactionTestCase

from catalogo.models import Producto
from clientes.models import Cliente, Direccion
from pedidos import servicios as s
from pedidos.models import Carrito, EstadoOrden, Orden, OrdenItem

CLAVE = "demo-cofrial-2026"


class ReglasDePedidos(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.hospital = Cliente.objects.get(rut="61.973.200-4")      # B2B
        cls.ana = Cliente.objects.get(rut="12.345.678-5")           # B2C
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")
        cls.pollo = Producto.objects.get(sku="POL-PEC-10K")

    def dir_de(self, cliente):
        return cliente.direccion_set.first().pk

    def stock(self, producto):
        return Producto.objects.get(pk=producto.pk).stock_disponible

    def test_rn01_precio_segun_la_lista_del_perfil(self):
        self.assertEqual(s.precio_de(self.hospital, self.lomo.pk), 38990)
        self.assertEqual(s.precio_de(self.ana, self.lomo.pk), 45990)

    def test_rn03_un_solo_carrito_abierto_y_pasa_a_convertido(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        s.agregar(self.ana, self.pollo.pk, 2)
        self.assertEqual(Carrito.objects.filter(cliente=self.ana, estado="abierto").count(), 1)
        orden = s.generar_orden(self.ana, self.dir_de(self.ana))
        self.assertEqual(Carrito.objects.filter(cliente=self.ana, estado="convertido").count(), 1)
        self.assertFalse(Carrito.objects.filter(cliente=self.ana, estado="abierto").exists())
        self.assertEqual(orden.estado_orden.nombre, "Recibida")

    def test_rn02_descuenta_stock_y_rechaza_si_no_alcanza(self):
        antes = self.stock(self.lomo)
        s.agregar(self.ana, self.lomo.pk, 3)
        s.generar_orden(self.ana, self.dir_de(self.ana))
        self.assertEqual(self.stock(self.lomo), antes - 3)
        s.agregar(self.ana, self.lomo.pk, antes + 1)
        with self.assertRaises(s.ErrorDeNegocio) as e:
            s.generar_orden(self.ana, self.dir_de(self.ana))
        self.assertIn("stock", e.exception.mensajes[0])
        self.assertEqual(self.stock(self.lomo), antes - 3)           # la transacción no dejó nada a medias
        self.assertEqual(Orden.objects.filter(direccion__cliente=self.ana).count(), 1)

    def test_rn04_la_direccion_debe_ser_del_cliente(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        with self.assertRaises(s.ErrorDeNegocio):
            s.generar_orden(self.ana, self.dir_de(self.hospital))

    def test_rn05_b2b_sin_oc_queda_pendiente_con_referencia_propia_y_b2c_no(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        pendiente = s.generar_orden(self.hospital, self.dir_de(self.hospital), "")
        self.assertTrue(pendiente.oc_pendiente)
        self.assertEqual(pendiente.numero_oc, f"WEB-{pendiente.creada_en.year}-{pendiente.orden_id:04d}")
        s.agregar(self.hospital, self.lomo.pk, 1)
        con_oc = s.generar_orden(self.hospital, self.dir_de(self.hospital), "OC-77")
        self.assertEqual((con_oc.numero_oc, con_oc.oc_pendiente), ("OC-77", False))
        s.agregar(self.ana, self.pollo.pk, 1)
        b2c = s.generar_orden(self.ana, self.dir_de(self.ana), "")
        self.assertEqual((b2c.numero_oc, b2c.oc_pendiente), ("", False))          # a B2C no se le pide ni se le marca

    def test_registrar_la_oc_real_reemplaza_la_referencia(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        orden = s.generar_orden(self.hospital, self.dir_de(self.hospital), "")
        s.registrar_oc(self.hospital, orden.pk, "  OC-2026-555  ")
        orden.refresh_from_db()
        self.assertEqual((orden.numero_oc, orden.oc_pendiente), ("OC-2026-555", False))

    def test_registrar_oc_valida_dueno_estado_y_formato(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        pendiente = s.generar_orden(self.hospital, self.dir_de(self.hospital), "")
        for cliente, orden_id, oc in ((self.hospital, pendiente.pk, ""), (self.hospital, pendiente.pk, "X" * 31), (self.ana, pendiente.pk, "OC-1"),
                                      (self.hospital, 99999, "OC-1")):
            with self.assertRaises(s.ErrorDeNegocio):
                s.registrar_oc(cliente, orden_id, oc)
        s.registrar_oc(self.hospital, pendiente.pk, "OC-1")
        with self.assertRaises(s.ErrorDeNegocio):                                  # ya no está pendiente
            s.registrar_oc(self.hospital, pendiente.pk, "OC-2")
        s.agregar(self.hospital, self.lomo.pk, 1)
        otra = s.generar_orden(self.hospital, self.dir_de(self.hospital), "")
        s.cancelar(otra, como="cliente")
        with self.assertRaises(s.ErrorDeNegocio):                                  # orden cancelada: no se modifica
            s.registrar_oc(self.hospital, otra.pk, "OC-3")

    def test_rn06_precio_congelado(self):
        s.agregar(self.hospital, self.lomo.pk, 2)
        orden = s.generar_orden(self.hospital, self.dir_de(self.hospital), "OC-1")
        self.lomo.precioproducto_set.filter(lista_precio=self.hospital.tipo_cliente.lista_precio).update(precio_clp=99999)
        self.assertEqual(OrdenItem.objects.get(orden=orden).precio_unitario_clp, 38990)
        self.assertEqual(s.total_orden(orden), 2 * 38990)

    def test_rn07_cancelacion_por_estado_y_reposicion_de_stock(self):
        antes = self.stock(self.lomo)
        s.agregar(self.ana, self.lomo.pk, 4)
        orden = s.generar_orden(self.ana, self.dir_de(self.ana))
        s.cancelar(orden, como="cliente")
        self.assertEqual(self.stock(self.lomo), antes)               # repuesto
        s.agregar(self.ana, self.lomo.pk, 1)
        orden2 = s.generar_orden(self.ana, self.dir_de(self.ana))
        s.avanzar(orden2)                                            # Confirmada
        with self.assertRaises(s.ErrorDeNegocio):
            s.cancelar(orden2, como="cliente")                       # el cliente ya no puede
        s.avanzar(orden2)                                            # En preparación
        s.cancelar(orden2, como="vendedor")                          # el vendedor sí
        self.assertEqual(Orden.objects.get(pk=orden2.pk).estado_orden.nombre, "Cancelada")

    def test_despachada_exige_despacho(self):
        s.agregar(self.ana, self.lomo.pk, 1)
        orden = s.generar_orden(self.ana, self.dir_de(self.ana))
        s.avanzar(orden), s.avanzar(orden)                           # hasta En preparación
        with self.assertRaises(s.ErrorDeNegocio):
            s.avanzar(orden)

    def test_rn08_repetir_ajusta_al_stock_y_avisa(self):
        s.agregar(self.ana, self.pollo.pk, 5)
        s.generar_orden(self.ana, self.dir_de(self.ana))
        Producto.objects.filter(pk=self.pollo.pk).update(stock_disponible=2)
        avisos = s.repetir_ultimo_pedido(self.ana)
        self.assertEqual(s.lineas(self.ana)[0]["cantidad"], 2)
        self.assertTrue(any("ajustó de 5 a 2" in a for a in avisos))

    def test_carrito_vacio_no_genera_orden(self):
        with self.assertRaises(s.ErrorDeNegocio):
            s.generar_orden(self.ana, self.dir_de(self.ana))


class FlujoWeb(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_compra_completa_desde_el_navegador(self):
        c = self.client
        self.assertEqual(c.get("/carrito/").status_code, 302)                       # sin sesión va al login
        self.assertTrue(c.login(username="ana@correo.test", password=CLAVE))
        producto = Producto.objects.get(sku="VAC-LOM-5K")
        c.post("/carrito/agregar/", {"producto": producto.pk, "cantidad": 2})
        self.assertContains(c.get("/carrito/"), "Lomo vetado")
        direccion = Direccion.objects.get(cliente__rut="12.345.678-5")
        r = c.post("/carrito/confirmar/", {"direccion": direccion.pk}, follow=True)
        self.assertContains(r, "Recibida")
        self.assertContains(c.get("/pedidos/"), "N.º")

    def test_una_orden_ajena_responde_404(self):
        ana = Cliente.objects.get(rut="12.345.678-5")
        s.agregar(ana, Producto.objects.first().pk, 1)
        orden = s.generar_orden(ana, ana.direccion_set.first().pk)
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/").status_code, 404)


class CompraSimultanea(TransactionTestCase):
    """RN-02: dos compras a la vez de la última unidad; solo una puede ganar."""

    def test_no_se_vende_dos_veces_la_ultima_unidad(self):
        call_command("cargar_demo", verbosity=0)
        producto = Producto.objects.get(sku="VAC-LOM-5K")
        Producto.objects.filter(pk=producto.pk).update(stock_disponible=1)
        clientes = [Cliente.objects.get(rut="12.345.678-5"), Cliente.objects.get(rut="61.973.200-4")]
        for c in clientes:
            s.agregar(c, producto.pk, 1)
        resultados = []
        arranque = threading.Barrier(2)

        def comprar(cliente):
            try:
                arranque.wait()
                s.generar_orden(cliente, cliente.direccion_set.first().pk, "OC-X")
                resultados.append("ok")
            except s.ErrorDeNegocio:
                resultados.append("sin stock")
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=comprar, args=(c,)) for c in clientes]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertEqual(sorted(resultados), ["ok", "sin stock"])
        self.assertEqual(Producto.objects.get(pk=producto.pk).stock_disponible, 0)


class AvisosDeLaCampanita(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_solo_clientes_con_sesion(self):
        self.assertEqual(self.client.get("/api/avisos/").status_code, 403)

    def test_cada_cliente_ve_solo_lo_suyo(self):
        from django.utils import timezone
        from datetime import timedelta
        from pedidos.models import Orden
        orden = Orden.objects.exclude(despacho=None).first()
        if orden is None:
            self.skipTest("la demostración no trae órdenes despachadas")
        Orden.objects.filter(pk=orden.pk).update()
        d = orden.despacho
        type(d).objects.filter(pk=d.pk).update(salida_en=timezone.now() - timedelta(minutes=5), llegada_en=None)
        duenio = orden.direccion.cliente
        usuario = duenio.usuario if hasattr(duenio, "usuario") else None
        ajeno = Cliente.objects.exclude(pk=duenio.pk).first()
        self.client.force_login(ajeno.usuario)
        self.assertFalse([a for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.orden_id])
        if usuario:
            self.client.force_login(usuario)
            tipos = {a["tipo"] for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.orden_id}
            self.assertIn("salio", tipos)


class AgregarSinRecargar(TestCase):
    """Con el encabezado de la tienda, «Agregar» responde JSON (sin redirección); sin él, todo sigue igual que antes."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        self.client.login(username="ana@correo.test", password=CLAVE)
        self.lomo = Producto.objects.get(sku="VAC-LOM-5K")

    def test_json_con_mensajes_y_contador(self):
        r = self.client.post("/carrito/agregar/", {"producto": self.lomo.pk, "cantidad": 2}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["carrito_n"], 2)
        self.assertEqual(d["mensajes"][0]["tipo"], "success")
        self.assertNotContains(self.client.get("/catalogo/"), "Producto agregado al carrito")      # el mensaje no reaparece en la página siguiente

    def test_error_de_negocio_vuelve_como_json_con_ok_falso(self):
        r = self.client.post("/carrito/agregar/", {"producto": self.lomo.pk, "cantidad": 0}, headers={"X-Requested-With": "fetch"})
        d = r.json()
        self.assertFalse(d["ok"])
        self.assertEqual(d["mensajes"][0]["tipo"], "error")

    def test_sin_el_encabezado_sigue_redirigiendo(self):
        r = self.client.post("/carrito/agregar/", {"producto": self.lomo.pk, "cantidad": 1, "volver": "/catalogo/"})
        self.assertRedirects(r, "/catalogo/", fetch_redirect_response=False)

    def test_la_miniatura_del_carrito_usa_la_imagen_del_producto(self):
        self.client.post("/carrito/agregar/", {"producto": self.lomo.pk, "cantidad": 1})
        html = self.client.get("/carrito/").content.decode()
        linea = html[html.index('class="linea-img"'):].split("</a>")[0]
        self.assertIn("productos/", linea)                                   # foto propia, de Commons o ilustración de IA...
        self.assertNotIn('class="ilus"', linea)                              # ...y no el dibujo genérico de la categoría


class OcPendienteEnLaWeb(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _pedido_sin_oc(self, usuario="felipe@cofrial.cl"):
        self.client.login(username=usuario, password=CLAVE)
        lomo = Producto.objects.get(sku="VAC-LOM-5K")
        self.client.post("/carrito/agregar/", {"producto": lomo.pk, "cantidad": 1})
        direccion = Cliente.objects.get(usuario__username=usuario).direccion_set.first().pk
        self.client.post("/carrito/confirmar/", {"direccion": direccion, "numero_oc": ""})
        return Orden.objects.order_by("-orden_id").first()

    def test_el_formulario_ya_no_exige_la_oc_y_explica_que_queda_pendiente(self):
        self.client.login(username="felipe@cofrial.cl", password=CLAVE)
        self.client.post("/carrito/agregar/", {"producto": Producto.objects.get(sku="VAC-LOM-5K").pk, "cantidad": 1})
        html = self.client.get("/carrito/").content.decode()
        campo = html[html.index('name="numero_oc"'):].split(">")[0]
        self.assertNotIn("required", campo)
        self.assertIn("OC pendiente", html)

    def test_compra_sin_oc_se_ve_pendiente_y_el_cliente_la_completa(self):
        orden = self._pedido_sin_oc()
        self.assertTrue(orden.oc_pendiente)
        self.assertContains(self.client.get("/pedidos/"), "OC pendiente")
        detalle = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(detalle, "OC pendiente")
        self.assertContains(detalle, "Agregar mi orden de compra")
        r = self.client.post(f"/pedidos/{orden.pk}/oc/", {"numero_oc": "OC-FELIPE-9"}, follow=True)
        self.assertContains(r, "Registramos tu orden de compra")
        orden.refresh_from_db()
        self.assertEqual((orden.numero_oc, orden.oc_pendiente), ("OC-FELIPE-9", False))
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), "Agregar mi orden de compra")

    def test_otro_cliente_no_puede_completar_la_oc_ajena(self):
        orden = self._pedido_sin_oc("felipe@cofrial.cl")
        self.client.logout()
        self.client.login(username="abastecimiento@hospital.test", password=CLAVE)
        self.client.post(f"/pedidos/{orden.pk}/oc/", {"numero_oc": "OC-HACK"})
        orden.refresh_from_db()
        self.assertTrue(orden.oc_pendiente)

    def test_ventas_ve_el_indicador_y_el_chip_en_la_ficha_del_cliente(self):
        orden = self._pedido_sin_oc()
        self.client.logout()
        self.client.login(username="gerencia@cofrial.cl", password=CLAVE)
        panel = self.client.get("/crm/")
        self.assertContains(panel, "Órdenes con OC pendiente")
        self.assertEqual(panel.context["ind"]["oc_pendientes"], 1)
        ficha = self.client.get(f"/crm/clientes/{orden.direccion.cliente_id}/")
        self.assertContains(ficha, "OC pendiente")

    def test_la_api_de_pedidos_informa_si_la_oc_esta_pendiente(self):
        orden = self._pedido_sin_oc()
        datos = self.client.get("/api/pedidos/").json()["ordenes"]
        self.assertTrue([o for o in datos if o["orden_id"] == orden.pk][0]["oc_pendiente"])


class EstadosDeLasRutas(TestCase):
    """Los estados que no son el camino feliz: vacíos, bloqueos, errores y avisos al volver de una redirección."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.ana = Cliente.objects.get(rut="12.345.678-5")
        cls.lomo = Producto.objects.get(sku="VAC-LOM-5K")

    def entrar(self, usuario="ana@correo.test"):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_seguimiento_sin_pedidos_en_curso_explica_por_que_cae_en_la_lista(self):
        self.entrar()
        s.agregar(self.ana, self.lomo.pk, 1)
        s.generar_orden(self.ana, self.ana.direccion_set.first().pk)
        Orden.objects.filter(direccion__cliente=self.ana).update(estado_orden=EstadoOrden.objects.get(nombre="Entregada"))
        r = self.client.get("/seguimiento/", follow=True)
        self.assertRedirects(r, "/pedidos/")
        self.assertContains(r, "No tienes pedidos en curso")

    def test_lista_de_pedidos_vacia_muestra_el_vacio_fuera_de_la_tabla(self):
        """En móvil la tabla está oculta: el estado vacío no puede vivir dentro de ella."""
        self.entrar()
        Orden.objects.filter(direccion__cliente=self.ana).delete()
        html = self.client.get("/pedidos/").content.decode()
        self.assertIn("Aún no tienes pedidos", html)
        self.assertNotIn('id="filas-pedidos"', html)

    def test_carrito_con_producto_sin_stock_bloquea_la_orden_y_lo_explica(self):
        self.entrar()
        s.agregar(self.ana, self.lomo.pk, 1)
        Producto.objects.filter(pk=self.lomo.pk).update(stock_disponible=0)
        r = self.client.get("/carrito/")
        self.assertEqual(len(r.context["sin_stock"]), 1)
        self.assertContains(r, "Agotado por ahora")
        self.assertContains(r, "supera el stock")
        self.assertContains(r, 'aria-describedby="why-confirmar"')

    def test_carrito_con_stock_no_bloquea_la_orden(self):
        self.entrar()
        s.agregar(self.ana, self.lomo.pk, 1)
        r = self.client.get("/carrito/")
        self.assertEqual(r.context["sin_stock"], [])
        self.assertNotContains(r, "why-confirmar")

    def test_orden_cancelada_explica_que_paso_y_ofrece_salida(self):
        self.entrar()
        s.agregar(self.ana, self.lomo.pk, 1)
        orden = s.generar_orden(self.ana, self.ana.direccion_set.first().pk)
        s.cancelar(orden, como="cliente")
        r = self.client.get(f"/pedidos/{orden.orden_id}/")
        self.assertContains(r, "Esta orden fue cancelada")
        self.assertContains(r, "Ir al catálogo")
        self.assertNotContains(r, "Seguimiento del envío")

    def test_cancelar_pide_confirmacion_en_dos_pasos(self):
        self.entrar()
        s.agregar(self.ana, self.lomo.pk, 1)
        orden = s.generar_orden(self.ana, self.ana.direccion_set.first().pk)
        self.assertContains(self.client.get(f"/pedidos/{orden.orden_id}/"), "data-confirmar=")

    def test_404_de_una_orden_ajena_habla_de_ordenes(self):
        self.entrar()
        r = self.client.get("/pedidos/999999/")
        self.assertContains(r, "no pertenece a tu cuenta", status_code=404)

    def test_formulario_vencido_muestra_la_pagina_propia_y_no_la_de_django(self):
        cliente = self.client_class(enforce_csrf_checks=True)
        r = cliente.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE})
        self.assertContains(r, "Formulario vencido", status_code=403)

    def test_login_fallido_resume_el_error_y_no_lo_repite(self):
        r = self.client.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": "mal"})
        self.assertContains(r, 'id="resumen-errores"')
        self.assertContains(r, "No pudimos ingresarte")
        self.assertContains(r, "no coinciden")

    def test_soporte_sin_consultas_usa_el_vacio_compartido(self):
        self.entrar()
        self.assertContains(self.client.get("/soporte/"), "Aún no has enviado consultas")
