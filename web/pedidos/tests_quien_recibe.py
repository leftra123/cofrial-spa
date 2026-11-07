"""El comprador elige quién recibe el pedido: de una lista en pantalla (personas que ya usó) o escribiendo un nombre nuevo."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogo import asistente
from catalogo.models import Producto
from crm.models import Requerimiento
from pedidos import mercadopago as mp, servicios as s
from pedidos.models import CheckoutPago, Orden

from .tests_entrega import CLAVE, EntregaBase


class QuienRecibeBase(EntregaBase):
    def entrar_como(self, usuario):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))
        return s.cliente_de(get_user_model().objects.get(username=usuario))

    def congelado(self):
        """SKU de un producto congelado con stock (para armar un carrito mixto)."""
        return Producto.objects.filter(categoria__rango_temperatura__nombre="Congelado", activo=True, stock_disponible__gte=3).order_by("sku").first().sku

    def cargar_carrito(self, cliente, *skus):
        for sku in skus:
            s.agregar(cliente, Producto.objects.get(sku=sku).pk, 1)

    def comprar(self, cliente, **campos):
        """Confirma el carrito por el formulario del portal (sin JavaScript) y devuelve las órdenes creadas."""
        antes = set(Orden.objects.values_list("pk", flat=True))
        r = self.client.post("/carrito/confirmar/", {"direccion": cliente.direccion_set.first().pk, **campos}, follow=True)
        return r, list(Orden.objects.exclude(pk__in=antes).order_by("pk"))


class ElegirQuienRecibeTests(QuienRecibeBase):
    def test_sin_elegir_recibe_el_titular(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana)
        self.assertEqual(orden.recibe_nombre, "")
        self.assertEqual(orden.quien_recibe, ana.nombre)
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), f"<dt>Recibe</dt><dd>{ana.nombre}</dd>", html=False)

    def test_escribir_un_nombre_nuevo_lo_guarda_normalizado_y_se_ve_en_el_pedido(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe_nuevo="   María   José  O'Higgins-Soto Jr.  ")
        self.assertEqual(orden.recibe_nombre, "María José O'Higgins-Soto Jr.")
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "<dt>Recibe</dt><dd>María José O&#x27;Higgins-Soto Jr.</dd>", html=False)

    def test_nombre_vacio_o_solo_espacios_es_el_titular_y_no_da_error(self):
        ana = self.entrar_como("ana@correo.test")
        for vacio in ("", "    ", "\t\n"):
            self.cargar_carrito(ana, "VAC-LOM-5K")
            _, ordenes = self.comprar(ana, recibe_nuevo=vacio, recibe="")
            self.assertEqual([o.recibe_nombre for o in ordenes], [""], repr(vacio))

    def test_nombre_muy_largo_se_rechaza_y_el_carrito_queda_intacto(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        r, ordenes = self.comprar(ana, recibe_nuevo="A" * 81)
        self.assertEqual(ordenes, [])
        self.assertContains(r, "admite hasta 80 caracteres")
        self.assertEqual(s.lineas_en_carrito(ana), 1)                          # el carrito sigue abierto con su producto
        _, (orden,) = self.comprar(ana, recibe_nuevo="A" * 80)                  # justo el máximo sí pasa
        self.assertEqual(len(orden.recibe_nombre), 80)

    def test_caracteres_que_no_son_de_un_nombre_se_rechazan(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        for malo in ("Juan123", "<script>alert(1)</script>", "a", "..", "12", "Pedro; DROP TABLE orden"):
            r, ordenes = self.comprar(ana, recibe_nuevo=malo)
            self.assertEqual(ordenes, [], repr(malo))
            self.assertContains(r, "solo con letras", msg_prefix=repr(malo))
        self.assertEqual(s.lineas_en_carrito(ana), 1)

    def test_un_nombre_nuevo_gana_sobre_la_lista(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        self.comprar(ana, recibe_nuevo="Pedro Rojas")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe="Pedro Rojas", recibe_nuevo="Rosa Díaz")
        self.assertEqual(orden.recibe_nombre, "Rosa Díaz")

    def test_carrito_mixto_genera_mas_de_una_orden_y_todas_llevan_a_la_misma_persona(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K", self.congelado())                # refrigerado + congelado
        _, ordenes = self.comprar(ana, recibe_nuevo="Rosa Díaz")
        self.assertGreater(len(ordenes), 1)
        self.assertEqual({o.recibe_nombre for o in ordenes}, {"Rosa Díaz"})
        self.assertEqual(len({o.direccion_id for o in ordenes}), 1)


class ListaDePersonasTests(QuienRecibeBase):
    def test_la_lista_trae_las_personas_usadas_antes_sin_repetir_y_sin_el_titular(self):
        ana = self.entrar_como("ana@correo.test")
        for nombre in ("Pedro Rojas", "Rosa Díaz", "pedro rojas", ana.nombre):
            self.cargar_carrito(ana, "VAC-LOM-5K")
            self.comprar(ana, recibe_nuevo=nombre)
        self.assertEqual(s.opciones_de_quien_recibe(ana), ["pedro rojas", "Rosa Díaz"])        # sin repetidos (gana la escritura más reciente) ni el titular
        self.cargar_carrito(ana, "VAC-LOM-5K")                                  # el formulario solo aparece con productos en el carrito
        pagina = self.client.get("/carrito/")
        self.assertContains(pagina, '<option value="Rosa Díaz">Rosa Díaz</option>', html=False)
        self.assertContains(pagina, 'name="recibe_nuevo"')
        self.assertContains(pagina, f"Yo ({ana.nombre})")

    def test_elegir_de_la_lista_funciona_sin_javascript(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        self.comprar(ana, recibe_nuevo="Pedro Rojas")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe="Pedro Rojas")
        self.assertEqual(orden.recibe_nombre, "Pedro Rojas")

    def test_la_lista_solo_muestra_personas_del_propio_cliente(self):
        hospital = self.entrar_como("abastecimiento@hospital.test")
        self.cargar_carrito(hospital, "VAC-LOM-5K")
        self.comprar(hospital, recibe_nuevo="Bodeguero Secreto")
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        self.assertNotIn("Bodeguero Secreto", s.opciones_de_quien_recibe(ana))
        self.assertNotContains(self.client.get("/carrito/"), "Bodeguero Secreto")
        self.assertIn("Bodeguero Secreto", s.opciones_de_quien_recibe(hospital))

    def test_el_titular_institucional_se_llama_titular_de_la_cuenta(self):
        hospital = self.entrar_como("abastecimiento@hospital.test")
        self.cargar_carrito(hospital, "VAC-LOM-5K")
        self.assertContains(self.client.get("/carrito/"), f"Titular de la cuenta ({hospital.nombre})")


class QuienRecibeSeVeTests(QuienRecibeBase):
    def orden_en_la_puerta(self):
        cliente = self.entrar_como("ana@correo.test")
        self.cargar_carrito(cliente, "VAC-LOM-5K")
        _, (orden,) = self.comprar(cliente, recibe_nuevo="Rosa Díaz")
        from flota import servicios as flota
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == flota.rangos_de(orden)[0])
        flota.despachar(camion.camion_id, [orden.pk])
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        return cliente, orden

    def test_la_revision_al_recibir_dice_quien_recibe(self):
        cliente, orden = self.orden_en_la_puerta()
        self.assertEqual(s.revision_de(orden)["recibe"], "Rosa Díaz")
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), '<p class="revision-recibe" id="revision-recibe"><b>Recibe:</b> Rosa Díaz</p>', html=False)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/entrega/?revision=1").json()["revision"]["recibe"], "Rosa Díaz")

    def test_la_confirmacion_del_pedido_nuevo_dice_quien_recibe(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        r, (orden,) = self.comprar(ana, recibe_nuevo="Rosa Díaz")
        self.assertContains(r, "Recibe <b>Rosa Díaz</b>", html=False)

    def test_el_crm_muestra_quien_recibe_en_la_ficha_del_cliente(self):
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe_nuevo="Rosa Díaz")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        self.comprar(ana)                                                      # este otro pedido lo recibe la titular
        self.entrar_como("gerencia@cofrial.cl")
        pagina = self.client.get(f"/crm/clientes/{ana.pk}/")
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "<th>Recibe</th>", html=False)
        self.assertContains(pagina, "<td>Rosa Díaz</td>", html=False)
        self.assertContains(pagina, f"<td>{ana.nombre}</td>", html=False)       # sin elegir a nadie, la ficha muestra a la titular

    def test_el_nombre_de_quien_recibe_no_viaja_a_los_proveedores_de_ia(self):
        """Regla de privacidad (docs/decisiones.md): al asistente y a la clasificación solo van datos sin identificar a la persona."""
        from unittest.mock import patch
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe_nuevo="Zoila Quispe Contreras")
        ctx, _ = asistente.construir_contexto("como va mi pedido", ana, ana.tipo_cliente, orden_id=orden.pk)
        texto = json.dumps(ctx, ensure_ascii=False)
        self.assertIn(f'"numero": {orden.pk}', texto)                          # el pedido sí va, sin la persona
        self.assertNotIn("Zoila", texto)
        prompts = []
        with patch("crm.ia._llamar", side_effect=lambda prompt, **kw: prompts.append(prompt) or ""):
            self.client.post("/api/asistente/", json.dumps({"mensaje": "¿Cómo va mi pedido y quién lo recibe?", "orden_id": orden.pk}), content_type="application/json")
        self.assertTrue(prompts, "el asistente no llegó a armar el prompt")
        self.assertFalse(any("Zoila" in p or "Quispe" in p for p in prompts))


class QuienRecibeConMercadoPagoTests(QuienRecibeBase):
    def test_el_checkout_guarda_a_quien_recibe_y_las_ordenes_lo_heredan_al_aprobarse_el_pago(self):
        ana = s.cliente_de(get_user_model().objects.get(username="ana@correo.test"))
        self.cargar_carrito(ana, "VAC-LOM-5K", self.congelado())
        ctx = s._contexto_desde_carrito(ana, ana.direccion_set.first().pk, "", "  Rosa   Díaz ")
        checkout, monto = mp._crear_checkout(ana, ctx)
        self.assertEqual(CheckoutPago.objects.get(pk=checkout.pk).recibe_nombre, "Rosa Díaz")
        mp._aplicar_respuesta_pago(checkout, {"status": "approved", "id": "999", "transaction_amount": monto})
        ordenes = list(Orden.objects.filter(checkout_pago=checkout))
        self.assertGreater(len(ordenes), 1)
        self.assertEqual({o.recibe_nombre for o in ordenes}, {"Rosa Díaz"})

    def test_pagar_con_un_nombre_invalido_falla_antes_de_crear_el_checkout_ni_llamar_a_mercado_pago(self):
        ana = s.cliente_de(get_user_model().objects.get(username="ana@correo.test"))
        self.cargar_carrito(ana, "VAC-LOM-5K")
        for malo in ("B" * 81, "Juan123"):
            with self.assertRaises(s.ErrorDeNegocio):
                mp.pagar_con_brick(ana, ana.direccion_set.first().pk, {"token": "x"}, recibe=malo)
        self.assertFalse(CheckoutPago.objects.exists())
        self.assertEqual(s.lineas_en_carrito(ana), 1)


class ReclamoNoLlevaElNombreTests(QuienRecibeBase):
    def test_el_reclamo_al_recibir_no_copia_el_nombre_de_quien_recibe(self):
        """El texto del requerimiento sí puede ir a la IA para clasificarlo: lo escribe el cliente y el sistema no le agrega la persona."""
        ana = self.entrar_como("ana@correo.test")
        self.cargar_carrito(ana, "VAC-LOM-5K")
        _, (orden,) = self.comprar(ana, recibe_nuevo="Zoila Quispe Contreras")
        from flota import servicios as flota
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == flota.rangos_de(orden)[0])
        flota.despachar(camion.camion_id, [orden.pk])
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(ana, orden.pk, "aceptar", "Una caja venía abierta", con_problema=True, tipo_problema="danado")
        req = Requerimiento.objects.get(orden=orden)
        self.assertNotIn("Zoila", req.asunto + req.descripcion)
