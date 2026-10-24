import threading

from django.core.management import call_command
from django.db import connections
from django.test import TestCase, TransactionTestCase

from catalogo.models import Producto
from clientes.models import Cliente, Direccion
from pedidos import servicios as s
from pedidos.models import Carrito, Orden, OrdenItem

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

    def test_rn05_b2b_exige_orden_de_compra_y_b2c_no(self):
        s.agregar(self.hospital, self.lomo.pk, 1)
        with self.assertRaises(s.ErrorDeNegocio):
            s.generar_orden(self.hospital, self.dir_de(self.hospital), "")
        orden = s.generar_orden(self.hospital, self.dir_de(self.hospital), "OC-77")
        self.assertEqual(orden.numero_oc, "OC-77")

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
