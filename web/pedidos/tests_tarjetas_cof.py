"""COF-01 itinerario explicado, COF-02 «Pedido entregado exitosamente» cuando el cliente confirma y COF-03 botones de los avisos con datos del pedido."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from crm.models import Requerimiento
from flota.models import Telemetria
from pedidos import documentos, servicios as s
from pedidos.models import Orden

from .tests_entrega import EntregaBase
from .tests_ruta_cliente import ViajeDeDosClientesBase, redondeado

EXITO = "Pedido entregado exitosamente"


class ItinerarioTests(ViajeDeDosClientesBase):
    def itinerario(self, cliente, orden):
        self.client.logout()
        self.assertTrue(self.client.login(username=cliente.usuario.username, password="demo-cofrial-2026"))
        r = self.client.get(f"/api/pedidos/{orden.pk}/seguimiento/")
        return r.json()["seguimiento"]["itinerario"], r.content.decode()

    def test_la_primera_parada_dice_que_es_la_primera(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, (p1[0] + 0.01, p1[1]))
        it, _ = self.itinerario(c1, o1)
        self.assertEqual((it["parada"], it["total"], it["antes"]), (1, 2, 0))
        self.assertIn("parada 1 de 2", it["texto"])

    def test_la_segunda_explica_que_antes_pasan_por_otra_entrega_sin_datos_del_otro_cliente(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, (p1[0] + 0.01, p1[1] + 0.003))             # el camión va cerca, pero no en la misma coordenada que la casa de nadie
        it, crudo = self.itinerario(c2, o2)
        self.assertEqual((it["parada"], it["total"], it["antes"]), (2, 2, 1))
        self.assertIn("parada 2 de 2", it["texto"])
        self.assertIn("Antes pasamos por otra entrega", it["texto"])
        # nada que identifique al otro cliente en toda la respuesta: ni nombre, ni calle, ni coordenadas
        for dato in (c1.nombre, o1.direccion.calle_numero, str(p1[0]), str(p1[1]), f"{p1[0]:.4f}"):
            self.assertNotIn(dato, crudo, dato)
        self.assertNotIn(redondeado(p1), {redondeado(p) for p in self.pedir_ruta(c2, o2)["puntos"]})

    def test_pasada_la_primera_parada_la_segunda_ya_va_directo(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, p1)
        s.llegar_a_la_puerta([o1])
        it, _ = self.itinerario(c2, o2)
        self.assertEqual((it["parada"], it["antes"]), (2, 0))
        self.assertIn("Ya hicimos las entregas anteriores", it["texto"])

    def test_la_pantalla_del_pedido_muestra_el_itinerario(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, (p1[0] + 0.01, p1[1]))
        self.client.logout()
        self.assertTrue(self.client.login(username=c2.usuario.username, password="demo-cofrial-2026"))
        pagina = self.client.get(f"/pedidos/{o2.pk}/").content.decode()
        self.assertIn('id="itinerario"', pagina)
        self.assertIn("Tu pedido es la parada 2 de 2", pagina)
        self.assertNotIn(c1.nombre, pagina)

    def test_un_viaje_con_un_solo_pedido_lo_dice(self):
        cliente, orden, despacho = self.orden_despachada()
        self.poner_camion(despacho, (orden.direccion.lat + 0.01, orden.direccion.long))
        it, _ = self.itinerario(cliente, orden)
        self.assertEqual((it["parada"], it["total"]), (1, 1))
        self.assertIn("solo tu pedido", it["texto"])

    def test_sin_mapa_en_vivo_no_hay_itinerario(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        orden.refresh_from_db()
        self.assertIsNone(s.seguimiento(orden)["itinerario"])


class EntregadoExitosamenteTests(EntregaBase):
    def en_la_puerta(self, usuario="ana@correo.test"):
        cliente, orden, despacho = self.orden_despachada(usuario)
        s.llegar_a_la_puerta([orden])
        self.entrar(usuario)
        return cliente, orden

    def comprobar_cerrado(self, orden, reclamo=False):
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, f'<h2 id="ep-t">{EXITO}</h2>', html=False)
        self.assertContains(pagina, "Recorrido cerrado")
        self.assertNotContains(pagina, "Revisa tu pedido antes de confirmar")           # ya no queda nada por responder
        llego = next(a for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.pk and a["tipo"] == "llego")
        self.assertIn(EXITO, llego["texto"])
        return pagina, llego

    def test_todo_bien(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "bien"}, headers={"X-Requested-With": "fetch"})
        self.assertIn(EXITO, r.json()["mensaje"])
        self.comprobar_cerrado(orden)

    def test_algo_fallo(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", "tipo_problema": "danado", "problema": "Una caja rota"},
                             headers={"X-Requested-With": "fetch"})
        self.assertIn(EXITO, r.json()["mensaje"])
        pagina, _ = self.comprobar_cerrado(orden)
        self.assertContains(pagina, "Ventas ya tiene tu aviso")
        self.assertTrue(Requerimiento.objects.filter(orden=orden).exists())

    def test_sin_javascript_el_mensaje_de_la_redireccion_tambien_lo_dice(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "bien"}, follow=True)
        self.assertContains(r, EXITO)

    def test_confirmacion_automatica_por_plazo(self):
        cliente, orden = self.en_la_puerta()
        Orden.objects.filter(pk=orden.pk).update(puerta_en=timezone.now() - timedelta(hours=1))
        s.confirmar_vencidas()
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "Recorrido cerrado")
        self.assertContains(pagina, "lo dimos por entregado")
        self.assertNotContains(pagina, EXITO)                                   # nadie confirmó: no se presenta como exitosa
        llego = next(a for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.pk and a["tipo"] == "llego")
        self.assertIn("confirmado automáticamente", llego["texto"])
        self.assertNotIn(EXITO, llego["texto"])

    def test_no_pude_recibirlo_no_es_una_entrega_exitosa(self):
        cliente, orden = self.en_la_puerta()
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en casa")
        self.assertNotContains(self.client.get(f"/pedidos/{orden.pk}/"), EXITO)
        self.assertFalse(any(EXITO in a["texto"] for a in self.client.get("/api/avisos/").json()["avisos"]))


class BotonesDeLosAvisosTests(EntregaBase):
    def cerca(self, despacho, orden):
        d = orden.direccion
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=d.lat + 0.005, long=d.long, combustible_pct=80, alerta_ruptura_frio=False)

    def avisos(self, usuario="ana@correo.test"):
        self.entrar(usuario)
        return self.client.get("/api/avisos/").json()["avisos"]

    def test_cada_tipo_de_aviso_trae_un_boton_que_lleva_a_una_pantalla_real_con_los_datos_del_pedido(self):
        # un pedido de cada situación: en camino cerca y con alerta de frío, en la puerta, entregado y entrega no concretada
        _, camino, d1 = self.orden_despachada()
        self.cerca(d1, camino)
        Telemetria.objects.create(camion=d1.camion, temp_camara=9.0, lat=camino.direccion.lat + 0.005, long=camino.direccion.long, combustible_pct=80, alerta_ruptura_frio=True)
        _, puerta, _ = self.orden_despachada()
        s.llegar_a_la_puerta([puerta])
        cliente, entregada, _ = self.orden_despachada()
        s.llegar_a_la_puerta([entregada])
        s.resolver_entrega(cliente, entregada.pk, "aceptar")
        _, fallida, _ = self.orden_despachada()
        s.llegar_a_la_puerta([fallida])
        s.resolver_entrega(cliente, fallida.pk, "no_recibido", "No había nadie en casa")

        avisos = self.avisos()
        tipos = {a["tipo"] for a in avisos}
        self.assertEqual(tipos, {"salio", "ventana", "cerca", "frio", "puerta", "llego", "no_concretada"})
        esperado = {"salio": "Ver dónde va", "ventana": "Ver dónde va", "cerca": "Ver dónde va", "frio": "Reportar un problema",
                    "no_concretada": "Escribir a ventas", "llego": "Ver boleta"}
        for a in avisos:
            n = a["orden_id"]
            orden = Orden.objects.get(pk=n)
            self.assertTrue(a["accion"]["texto"] and a["accion"]["url"], a["tipo"])
            if a["tipo"] == "puerta":
                self.assertEqual(a["accion"]["texto"], "Revisar y recibir" if a["destacado"] else "Ver pedido")
            else:
                self.assertEqual(a["accion"]["texto"], esperado[a["tipo"]], a["tipo"])
            # el botón lleva a una pantalla que existe (sin el ancla) y del propio cliente
            destino = a["accion"]["url"].split("#")[0]
            self.assertEqual(self.client.get(destino).status_code, 200, f"{a['tipo']} → {a['accion']['url']}")
            # los datos del pedido que muestra el aviso son los de ese pedido
            self.assertEqual(a["pedido"]["estado"], orden.estado_orden.nombre)
            self.assertEqual(a["pedido"]["total_clp"], s.total_orden(orden))
            boleta = documentos.Documento.objects.get(orden=orden, tipo="boleta")
            self.assertEqual(a["pedido"]["documento"], {"tipo": "boleta", "nombre": "Boleta", "etiqueta": str(boleta)})
            self.assertIn(f"orden={n}" if a["tipo"] in ("no_concretada", "frio") else f"/pedidos/{n}/", a["accion"]["url"])
        # las anclas a las que apuntan existen en la pantalla del pedido
        self.assertContains(self.client.get(f"/pedidos/{puerta.pk}/"), 'id="entrega"')
        self.assertContains(self.client.get(f"/pedidos/{entregada.pk}/"), 'id="documentos"')
        self.assertContains(self.client.get(f"/pedidos/{camino.pk}/"), 'id="seg"')
        self.assertContains(self.client.get(f"/soporte/?orden={fallida.pk}"), f"{fallida.pk}")

    def test_cliente_institucional_ve_guia_antes_y_factura_despues_con_iva(self):
        cliente, orden, despacho = self.orden_despachada("abastecimiento@hospital.test")
        self.cerca(despacho, orden)
        cerca = next(a for a in self.avisos("abastecimiento@hospital.test") if a["tipo"] == "cerca")
        self.assertEqual(cerca["pedido"]["documento"]["tipo"], "guia_despacho")
        self.assertTrue(cerca["pedido"]["con_iva"])
        self.assertEqual(cerca["pedido"]["total_clp"], documentos.monto_con_iva(orden))
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        orden.refresh_from_db()
        documentos.emitir_factura(orden)
        llego = next(a for a in self.avisos("abastecimiento@hospital.test") if a["tipo"] == "llego")
        self.assertEqual(llego["pedido"]["documento"]["tipo"], "factura")
        self.assertEqual(llego["accion"]["texto"], "Ver factura")

    def test_los_botones_del_banner_y_de_la_campanita_estan_en_el_script(self):
        js = open("static/js/campana.js", encoding="utf-8").read()
        for esperado in ("a.accion", "datosDelPedido", "CofrialEntrega.revisar", "CofrialEntrega.modal", 'ir.className = "btn"', "conMarca(ir, marcaDe(a.tipo))"):
            self.assertIn(esperado, js)
        css = open("static/css/tienda.css", encoding="utf-8").read()
        self.assertIn(".campana-item > a", css)
        self.assertIn(".campana-item.nuevo { background: var(--lima-suave); }", css)
        self.assertIn("campana-acciones campana-par", js)
        self.assertIn(".campana-par { flex-wrap: nowrap;", css)
        self.assertNotIn(".campana-item a {", css)
        self.assertNotIn(".campana-item.nuevo a", css)

    def test_la_lista_de_avisos_no_trae_datos_de_otro_cliente(self):
        _, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        ajenos = self.avisos("abastecimiento@hospital.test")
        self.assertFalse(any(a["orden_id"] == orden.pk for a in ajenos))
