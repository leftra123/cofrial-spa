"""RN-23, recepción parcial: al revisar la entrega el cliente rechaza unidades por línea; se factura o se rebaja solo lo que corresponde."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from catalogo.models import Producto
from crm import servicios as crm
from crm.models import Requerimiento
from flota import servicios as flota
from pedidos import documentos, servicios as s
from pedidos.models import CarritoItem, Documento, EstadoOrden, Orden, OrdenItem, Pago

CLAVE = "demo-cofrial-2026"
ANA = "ana@correo.test"
HOSPITAL = "abastecimiento@hospital.test"
LOMO, POSTA = "VAC-LOM-5K", "VAC-POS-5K"          # mismo rango de temperatura: quedan en una sola orden


class RecepcionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def en_la_puerta(self, usuario=ANA, lineas=None, comprobante=None, giro=""):
        """Orden con varias líneas despachada en un camión libre y con el camión ya en la dirección."""
        cliente = s.cliente_de(get_user_model().objects.get(username=usuario))
        CarritoItem.objects.filter(carrito__cliente=cliente, carrito__estado="abierto").delete()
        for sku, n in (lineas or {LOMO: 5, POSTA: 3}).items():
            s.agregar(cliente, Producto.objects.get(sku=sku).pk, n)
        orden = s.generar_ordenes(cliente, cliente.direccion_set.first().pk, "OC-RECEPCION" if usuario == HOSPITAL else "", comprobante=comprobante, giro=giro)[0]
        rango = flota.rangos_de(orden)[0]
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == rango)
        flota.despachar(camion.camion_id, [orden.pk])
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        return cliente, orden

    def linea(self, orden, sku):
        return OrdenItem.objects.get(orden=orden, producto__sku=sku)

    def id_de(self, sku):
        return Producto.objects.get(sku=sku).pk

    def rechazar(self, cliente, orden, rechazos, comentario=""):
        return s.resolver_entrega(cliente, orden.pk, "aceptar", comentario, con_problema=True,
                                  rechazos={self.id_de(sku): v for sku, v in rechazos.items()})

    def devoluciones(self, documento):
        return list(Pago.objects.filter(documento=documento, medio="devolucion").values_list("monto_clp", flat=True))

    def entrar(self, usuario=ANA):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))


class CanalB2CTests(RecepcionBase):
    def test_vienesas_con_la_bolsa_abierta_rebaja_lo_rechazado_y_lo_devuelve(self):
        cliente, orden = self.en_la_puerta()
        precio = self.linea(orden, LOMO).precio_unitario_clp
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        total_pagado = boleta.monto_clp
        orden = self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        linea = self.linea(orden, LOMO)
        self.assertEqual((linea.cantidad, linea.cantidad_rechazada, linea.cantidad_aceptada, linea.motivo_rechazo), (5, 2, 3, "danado"))
        self.assertEqual(self.linea(orden, POSTA).cantidad_rechazada, 0)
        self.assertEqual(orden.estado_orden.nombre, "Entregada")
        nota = Documento.objects.get(orden=orden, tipo="nota_credito")
        self.assertEqual((nota.monto_clp, nota.referencia), (2 * precio, boleta))
        self.assertTrue(nota.motivo.startswith(documentos.MOTIVO_RECHAZO))
        self.assertEqual(self.devoluciones(boleta), [-2 * precio])          # RN-21: lo ya pagado se devuelve, con medio «devolucion»
        boleta.refresh_from_db()
        self.assertEqual(boleta.monto_clp, total_pagado)                    # el documento es una foto: no cambia, lo rebaja la nota
        self.assertEqual(documentos.saldo(boleta), 0)
        self.assertEqual(s.total_orden(orden), total_pagado - 2 * precio)

    def test_factura_al_contado_del_publico_se_rebaja_igual(self):
        cliente, orden = self.en_la_puerta(comprobante="factura", giro="Almacén de barrio")      # el público que eligió factura también pagó al comprar
        factura = Documento.objects.get(orden=orden, tipo="factura")
        self.rechazar(cliente, orden, {POSTA: (1, "temperatura")})
        self.assertEqual(Documento.objects.get(orden=orden, tipo="nota_credito").referencia, factura)
        self.assertEqual(len(self.devoluciones(factura)), 1)

    def test_lo_rechazado_no_vuelve_al_stock(self):
        cliente, orden = self.en_la_puerta()
        antes = Producto.objects.get(sku=LOMO).stock_disponible
        self.rechazar(cliente, orden, {LOMO: (2, "temperatura")})
        self.assertEqual(Producto.objects.get(sku=LOMO).stock_disponible, antes)


class CanalB2BTests(RecepcionBase):
    def test_sin_factura_previa_la_factura_se_emite_por_lo_aceptado(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        l, p = self.linea(orden, LOMO), self.linea(orden, POSTA)
        orden = self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="nota_credito").exists())       # no hay nada que rebajar
        neto = 3 * l.precio_unitario_clp + 3 * p.precio_unitario_clp
        pendientes = documentos.entregadas_sin_factura([cliente])
        self.assertEqual(next(o.monto for o in pendientes if o.pk == orden.pk), round(neto * 1.19))
        factura = documentos.emitir_factura(orden)
        self.assertEqual(factura.monto_clp, round(neto * 1.19))
        self.assertEqual(documentos.saldo(factura), round(neto * 1.19))
        filas, neto_filas = documentos.lineas_de_documento(factura)
        self.assertEqual(neto_filas, neto)
        self.assertEqual({f["producto"]: f["cantidad"] for f in filas}, {l.producto.nombre: 3, p.producto.nombre: 3})

    def test_con_factura_previa_la_nota_deja_el_mismo_monto_que_facturar_lo_aceptado(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        factura = documentos._emitir(orden, "factura", documentos.monto_con_iva(orden), vence_en=timezone.localdate() + timedelta(days=30))
        orden = self.rechazar(cliente, orden, {LOMO: (1, "faltante")})
        nota = Documento.objects.get(orden=orden, tipo="nota_credito")
        self.assertEqual(nota.referencia, factura)
        self.assertEqual(factura.monto_clp - nota.monto_clp, documentos.monto_con_iva(orden))        # sin un peso de diferencia por redondear el IVA
        self.assertEqual(documentos.saldo(factura), documentos.monto_con_iva(orden))
        self.assertEqual(self.devoluciones(factura), [])                     # no había pagado nada: solo baja la deuda
        with self.assertRaises(documentos.ErrorDeNegocio):
            documentos.emitir_factura(orden)                                 # sigue siendo una sola factura

    def test_con_factura_parcialmente_pagada_lo_que_sobra_se_devuelve(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        factura = documentos._emitir(orden, "factura", documentos.monto_con_iva(orden), vence_en=timezone.localdate() + timedelta(days=30))
        documentos.registrar_pago(factura.pk, factura.monto_clp - 1000, "transferencia", "TRF-1")
        self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        nota = Documento.objects.get(orden=orden, tipo="nota_credito")
        self.assertEqual(self.devoluciones(factura), [-(nota.monto_clp - 1000)])
        self.assertEqual(documentos.saldo(factura), 0)

    def test_la_nota_no_supera_lo_que_el_documento_aun_no_tiene_rebajado(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        factura = documentos._emitir(orden, "factura", documentos.monto_con_iva(orden), vence_en=timezone.localdate() + timedelta(days=30))
        documentos.emitir_nota_credito(factura.pk, factura.monto_clp - 5000, "Reclamo anterior del vendedor")
        self.rechazar(cliente, orden, {LOMO: (5, "danado")})
        notas = Documento.objects.filter(orden=orden, tipo="nota_credito", motivo__startswith=documentos.MOTIVO_RECHAZO)
        self.assertEqual([n.monto_clp for n in notas], [5000])
        self.assertEqual(documentos.saldo(factura), 0)

    def test_documento_ya_rebajado_entero_no_genera_nota_ni_error(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        factura = documentos._emitir(orden, "factura", documentos.monto_con_iva(orden), vence_en=timezone.localdate() + timedelta(days=30))
        documentos.emitir_nota_credito(factura.pk, factura.monto_clp, "Anulada por el vendedor")
        orden = self.rechazar(cliente, orden, {LOMO: (1, "danado")})
        self.assertEqual(orden.estado_orden.nombre, "Entregada")
        self.assertEqual(Documento.objects.filter(orden=orden, tipo="nota_credito").count(), 1)


class RechazoTotalTests(RecepcionBase):
    def test_b2c_queda_rechazada_con_toda_la_plata_devuelta(self):
        cliente, orden = self.en_la_puerta()
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        stock = Producto.objects.get(sku=LOMO).stock_disponible
        orden = self.rechazar(cliente, orden, {LOMO: (5, "temperatura"), POSTA: (3, "temperatura")}, "Todo llegó descongelado")
        self.assertEqual(orden.estado_orden.nombre, s.RECHAZADA)
        self.assertNotEqual(orden.estado_orden.nombre, "Entrega no concretada")
        self.assertTrue(orden.estado_orden.es_final)
        self.assertEqual(orden.entrega_motivo, "Todo llegó descongelado")
        self.assertEqual(Documento.objects.get(orden=orden, tipo="nota_credito").monto_clp, boleta.monto_clp)
        self.assertEqual(self.devoluciones(boleta), [-boleta.monto_clp])
        self.assertEqual(documentos.documentos_de_orden(orden)[0].estado_pago, "anulado")
        self.assertEqual(s.total_orden(orden), 0)
        self.assertEqual(Producto.objects.get(sku=LOMO).stock_disponible, stock)     # tampoco vuelve a la venta

    def test_b2b_no_genera_factura_ni_queda_en_cobranza(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        orden = self.rechazar(cliente, orden, {LOMO: (5, "danado"), POSTA: (3, "faltante")})
        self.assertEqual(orden.estado_orden.nombre, s.RECHAZADA)
        self.assertFalse(Documento.objects.filter(orden=orden, tipo__in=("factura", "nota_credito")).exists())
        self.assertNotIn(orden.pk, [o.pk for o in documentos.entregadas_sin_factura([cliente])])
        with self.assertRaises(documentos.ErrorDeNegocio):
            documentos.emitir_factura(orden)

    def test_no_se_reprograma_ni_se_cancela(self):
        cliente, orden = self.en_la_puerta()
        orden = self.rechazar(cliente, orden, {LOMO: (5, "danado"), POSTA: (3, "danado")})
        self.assertNotIn(orden.pk, [o.pk for o in flota.pedidos_por_despachar()])
        with self.assertRaises(s.ErrorDeNegocio):
            s.cancelar(orden, como="vendedor")
        with self.assertRaises(s.ErrorDeNegocio):
            s.avanzar(orden)

    def test_rechazar_toda_una_linea_no_es_rechazo_total(self):
        cliente, orden = self.en_la_puerta()
        self.assertEqual(self.rechazar(cliente, orden, {LOMO: (5, "danado")}).estado_orden.nombre, "Entregada")

    def test_el_viaje_se_cierra_si_era_la_ultima_entrega(self):
        cliente, orden = self.en_la_puerta()
        orden = self.rechazar(cliente, orden, {LOMO: (5, "danado"), POSTA: (3, "danado")})
        orden.despacho.refresh_from_db()
        self.assertEqual(orden.despacho.fase, "volviendo")

    def test_la_exposicion_al_frio_termina_al_rechazar(self):
        cliente, orden = self.en_la_puerta()
        orden = self.rechazar(cliente, orden, {LOMO: (5, "danado"), POSTA: (3, "danado")})
        self.assertEqual(s.fin_de_exposicion(orden), orden.entrega_resuelta_en)
        self.assertEqual(crm.fin_de_exposicion(orden), orden.entrega_resuelta_en)


class LimitesTests(RecepcionBase):
    def intento_fallido(self, rechazos, comentario="", usuario=ANA):
        cliente, orden = self.en_la_puerta(usuario)
        stock = Producto.objects.get(sku=LOMO).stock_disponible
        with self.assertRaises(s.ErrorDeNegocio) as e:
            s.resolver_entrega(cliente, orden.pk, "aceptar", comentario, con_problema=True, rechazos=rechazos(self))
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Camión en la puerta")      # no cambió nada: se puede corregir y volver a enviar
        self.assertEqual(OrdenItem.objects.filter(orden=orden, cantidad_rechazada__gt=0).count(), 0)
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="nota_credito").exists())
        self.assertFalse(Requerimiento.objects.filter(orden=orden).exists())
        self.assertEqual(Producto.objects.get(sku=LOMO).stock_disponible, stock)
        return " ".join(e.exception.mensajes)

    def test_no_se_rechaza_mas_de_lo_pedido(self):
        self.assertIn("más de lo que pediste", self.intento_fallido(lambda t: {t.id_de(LOMO): (6, "danado")}))

    def test_cantidades_que_no_son_un_entero_positivo(self):
        for mala in ("-1", "1.5", "dos", "²", "99999999999"):
            with self.subTest(mala=mala):
                self.intento_fallido(lambda t: {t.id_de(LOMO): (mala, "danado")})

    def test_rechazar_exige_motivo_valido(self):
        for malo in ("", "porque_si"):
            with self.subTest(malo=malo):
                self.assertIn("motivo", self.intento_fallido(lambda t: {t.id_de(LOMO): (1, malo)}))

    def test_producto_ajeno_al_pedido(self):
        self.assertIn("no es parte", self.intento_fallido(lambda t: {t.id_de("EMB-JAM-3K"): (1, "danado")}))

    def test_un_error_en_una_linea_detiene_todo(self):
        self.intento_fallido(lambda t: {t.id_de(LOMO): (1, "danado"), t.id_de(POSTA): (9, "danado")})

    def test_otro_problema_pide_explicacion(self):
        self.assertIn("Cuéntanos", self.intento_fallido(lambda t: {t.id_de(LOMO): (1, "otro")}, "no"))
        cliente, orden = self.en_la_puerta()
        self.assertEqual(self.rechazar(cliente, orden, {LOMO: (1, "otro")}, "Venía con otra etiqueta").estado_orden.nombre, "Entregada")

    def test_cero_es_lo_normal_y_no_pide_motivo(self):
        cliente, orden = self.en_la_puerta()
        orden = self.rechazar(cliente, orden, {LOMO: ("0", ""), POSTA: ("", "")}, "Llegó con retraso")
        self.assertEqual(orden.estado_orden.nombre, "Entregada")
        self.assertEqual(s.unidades_rechazadas(orden), 0)
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="nota_credito").exists())
        self.assertTrue(Requerimiento.objects.filter(orden=orden).exists())          # algo falló sin rechazar: sigue siendo reclamo

    def test_algo_fallo_sin_rechazar_ni_explicar_se_rechaza(self):
        self.intento_fallido(lambda t: {t.id_de(LOMO): (0, "")}, "")

    def test_la_base_de_datos_tambien_impone_los_limites(self):
        _, orden = self.en_la_puerta()
        filas = OrdenItem.objects.filter(orden=orden, producto__sku=LOMO)
        for datos in ({"cantidad_rechazada": 6, "motivo_rechazo": "danado"}, {"cantidad_rechazada": -1, "motivo_rechazo": "danado"},
                      {"cantidad_rechazada": 1, "motivo_rechazo": ""}, {"cantidad_rechazada": 1, "motivo_rechazo": "porque_si"},
                      {"cantidad_rechazada": 0, "motivo_rechazo": "danado"}):
            with self.subTest(datos=datos), self.assertRaises(IntegrityError), transaction.atomic():
                filas.update(**datos)
        filas.update(cantidad_rechazada=5, motivo_rechazo="danado")          # el borde sí vale


class SinRechazoTests(RecepcionBase):
    def test_la_confirmacion_por_plazo_no_rechaza_nada(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        Orden.objects.filter(pk=orden.pk).update(puerta_en=timezone.now() - timedelta(days=1))
        total = documentos.monto_con_iva(orden)
        self.assertGreaterEqual(s.confirmar_vencidas(), 1)
        orden.refresh_from_db()
        self.assertEqual((orden.estado_orden.nombre, orden.entrega_automatica, s.unidades_rechazadas(orden)), ("Entregada", True, 0))
        self.assertEqual(documentos.emitir_factura(orden).monto_clp, total)
        with self.assertRaises(s.ErrorDeNegocio):                            # ya venció: no se puede rechazar después
            self.rechazar(cliente, orden, {LOMO: (1, "danado")})

    def test_todo_bien_factura_el_total(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        total = documentos.monto_con_iva(orden)
        orden = s.resolver_entrega(cliente, orden.pk, "aceptar")
        self.assertEqual(documentos.emitir_factura(orden).monto_clp, total)
        self.assertIsNone(s.rechazo_de(orden))

    def test_responder_dos_veces_no_emite_dos_notas(self):
        cliente, orden = self.en_la_puerta()
        self.rechazar(cliente, orden, {LOMO: (1, "danado")})
        with self.assertRaises(s.ErrorDeNegocio):
            self.rechazar(cliente, orden, {LOMO: (1, "danado")})
        self.assertEqual(Documento.objects.filter(orden=orden, tipo="nota_credito").count(), 1)

    def test_no_recibido_no_toca_las_lineas_aunque_lleguen_rechazos(self):
        cliente, orden = self.en_la_puerta()
        orden = s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en la casa", rechazos={self.id_de(LOMO): (1, "danado")})
        self.assertEqual(orden.estado_orden.nombre, "Entrega no concretada")
        self.assertEqual(s.unidades_rechazadas(orden), 0)
        self.assertFalse(Documento.objects.filter(orden=orden, tipo="nota_credito").exists())


class ReclamoTests(RecepcionBase):
    def reclamo(self, orden):
        return Requerimiento.objects.get(orden=orden)

    def test_el_reclamo_cuenta_que_se_rechazo_y_la_nota(self):
        cliente, orden = self.en_la_puerta()
        self.rechazar(cliente, orden, {LOMO: (2, "danado")}, "La bolsa venía abierta")
        r = self.reclamo(orden)
        nota = Documento.objects.get(orden=orden, tipo="nota_credito")
        self.assertEqual(r.asunto, f"{s.ASUNTO_RECLAMO_AL_RECIBIR} N.º {orden.pk}: Recepción parcial")
        for texto in ("2 de 5", "Producto dañado", "La bolsa venía abierta", str(nota)):
            self.assertIn(texto, r.descripcion)
        self.assertEqual(r.categoria_requerimiento.nombre, "Problema en la entrega")
        self.assertEqual(s.reclamo_al_recibir(orden), r)

    def test_rechazo_total_y_la_temperatura_manda_en_la_categoria(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        self.rechazar(cliente, orden, {LOMO: (5, "danado"), POSTA: (3, "temperatura")})
        r = self.reclamo(orden)
        self.assertTrue(r.asunto.endswith("Rechazo total"))
        self.assertEqual(r.categoria_requerimiento.nombre, "Reclamo por temperatura")

    def test_el_vendedor_lo_ve_en_la_ficha_y_en_el_reclamo(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        linea = self.linea(orden, LOMO)
        self.entrar("vendedora@cofrial.cl")
        ficha = self.client.get(f"/crm/clientes/{cliente.pk}/").content.decode()
        self.assertIn("Recepción parcial", ficha)
        self.assertIn(f"2 de 5 {linea.producto.nombre}", ficha)
        pagina = self.client.get(f"/crm/requerimientos/{self.reclamo(orden).pk}/").content.decode()
        self.assertIn("Recepción parcial del pedido", pagina)
        self.assertIn("Lo rechazado no volvió a la venta", pagina)


class PantallasTests(RecepcionBase):
    def post(self, orden, **datos):
        return self.client.post(f"/pedidos/{orden.pk}/entrega/", datos, HTTP_X_REQUESTED_WITH="fetch")

    def test_el_paso_de_revision_trae_lo_necesario_para_cada_linea(self):
        _, orden = self.en_la_puerta()
        self.entrar()
        datos = self.client.get(f"/pedidos/{orden.pk}/entrega/?revision=1").json()["revision"]
        self.assertEqual({p["producto_id"] for p in datos["productos"]}, {self.id_de(LOMO), self.id_de(POSTA)})
        self.assertEqual({k["codigo"] for k in datos["problemas"]}, set(s.PROBLEMAS_AL_RECIBIR))
        self.assertIn("nota de crédito", datos["efecto"])
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn(f'name="rechazo_{self.id_de(LOMO)}"', html)
        self.assertIn(f'name="motivo_{self.id_de(LOMO)}"', html)

    def test_b2b_sin_factura_ve_que_se_factura_lo_aceptado(self):
        _, orden = self.en_la_puerta(HOSPITAL)
        self.assertIn("factura se emite solo", s.revision_de(orden)["efecto"])

    def test_recepcion_parcial_por_la_pantalla(self):
        _, orden = self.en_la_puerta()
        self.entrar()
        r = self.post(orden, accion="aceptar", resultado="falla", problema="", tipo_problema="otro",
                      **{f"rechazo_{self.id_de(LOMO)}": "2", f"motivo_{self.id_de(LOMO)}": "danado", f"rechazo_{self.id_de(POSTA)}": "0"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("2 unidades rechazadas", r.json()["mensaje"])
        self.assertIn("devolución", r.json()["mensaje"])
        self.assertEqual(r.json()["entrega"]["unidades_rechazadas"], 2)
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn("Recibiste parte de tu pedido", html)
        self.assertIn("Rechazaste 2 de 5", html)
        self.assertNotIn("Pedido entregado exitosamente", html)

    def test_rechazo_total_por_la_pantalla(self):
        _, orden = self.en_la_puerta(HOSPITAL)
        self.entrar(HOSPITAL)
        r = self.post(orden, accion="aceptar", resultado="falla", **{f"rechazo_{self.id_de(LOMO)}": "5", f"motivo_{self.id_de(LOMO)}": "temperatura",
                                                                     f"rechazo_{self.id_de(POSTA)}": "3", f"motivo_{self.id_de(POSTA)}": "temperatura"})
        self.assertIn("rechazaste todo el pedido", r.json()["mensaje"])
        self.assertIn("No se emitirá factura", r.json()["mensaje"])
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn("Rechazaste este pedido al recibirlo", html)
        self.assertNotIn("No pudimos entregar tu pedido", html)
        self.assertIn('class="chip alerta">Rechazada en recepción', html)
        self.assertNotIn("La factura de este pedido se emite", html)
        self.assertNotIn('id="mapa"', html)                                # viaje cerrado: sin mapa, y sin decir que aparecerá cuando el camión parta
        self.assertIn("El mapa en vivo ya no está disponible", html)

    def test_con_todo_bien_se_ignoran_los_numeros_del_formulario(self):
        """Sin JavaScript el bloque de rechazo queda a la vista: si marcó «todo llegó bien», lo escrito ahí no cuenta."""
        _, orden = self.en_la_puerta()
        self.entrar()
        r = self.post(orden, accion="aceptar", resultado="bien", **{f"rechazo_{self.id_de(LOMO)}": "2", f"motivo_{self.id_de(LOMO)}": "danado"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(s.unidades_rechazadas(orden), 0)

    def test_error_de_cantidad_por_la_pantalla(self):
        _, orden = self.en_la_puerta()
        self.entrar()
        r = self.post(orden, accion="aceptar", resultado="falla", **{f"rechazo_{self.id_de(LOMO)}": "99", f"motivo_{self.id_de(LOMO)}": "danado"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("más de lo que pediste", r.json()["mensaje"])

    def test_sin_javascript_redirige_con_el_mensaje(self):
        _, orden = self.en_la_puerta()
        self.entrar()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", f"rechazo_{self.id_de(LOMO)}": "1", f"motivo_{self.id_de(LOMO)}": "faltante"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.linea(orden, LOMO).cantidad_rechazada, 1)

    def test_orden_ajena_no_existe(self):
        _, orden = self.en_la_puerta()
        self.entrar(HOSPITAL)
        self.assertEqual(self.post(orden, accion="aceptar", resultado="falla").status_code, 404)

    def test_la_boleta_muestra_lo_comprado_y_la_rebaja(self):
        cliente, orden = self.en_la_puerta()
        self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        boleta = Documento.objects.get(orden=orden, tipo="boleta")
        filas, neto = documentos.lineas_de_documento(boleta)
        self.assertEqual(neto, boleta.monto_clp)
        self.assertEqual(sum(f["cantidad"] for f in filas), 8)
        self.entrar()
        html = self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/").content.decode()
        self.assertIn("Rebajada por Nota de crédito", html)
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/documentos/{boleta.pk}/?descarga=1").status_code, 200)
        self.assertIn(b"Rebajada por Nota", documentos.comprobante_pdf(boleta))

    def test_la_factura_despues_del_rechazo_cuadra_con_sus_lineas(self):
        cliente, orden = self.en_la_puerta(HOSPITAL)
        orden = self.rechazar(cliente, orden, {LOMO: (5, "danado")})
        factura = documentos.emitir_factura(orden)
        self.entrar(HOSPITAL)
        html = self.client.get(f"/pedidos/{orden.pk}/documentos/{factura.pk}/").content.decode()
        self.assertNotIn(self.linea(orden, LOMO).producto.nombre + "</td>", html)
        self.assertIn("cubre solo lo que el cliente aceptó", html)
        pdf = documentos.comprobante_pdf(factura)
        self.assertNotIn(self.linea(orden, LOMO).producto.nombre.encode("latin-1"), pdf)

    def test_avisos_de_la_campanita(self):
        cliente, parcial = self.en_la_puerta()
        self.rechazar(cliente, parcial, {LOMO: (1, "danado")})
        _, total = self.en_la_puerta()
        self.rechazar(cliente, total, {LOMO: (5, "danado"), POSTA: (3, "danado")})
        avisos = s.avisos_de_llegada(cliente)
        llego = next(a for a in avisos if a["id"] == f"{parcial.pk}-llego")
        self.assertIn("rechazaste 1 unidad.", llego["texto"])
        rechazada = next(a for a in avisos if a["id"] == f"{total.pk}-rechazada")
        self.assertEqual(rechazada["accion"]["url"], f"/pedidos/{total.pk}/")
        self.assertEqual(rechazada["pedido"]["total_clp"], 0)


class BITests(RecepcionBase):
    def vista(self, orden):
        with connection.cursor() as c:
            c.execute("SELECT total_clp, unidades, rechazado_clp, unidades_rechazadas FROM v_orden_total WHERE orden_id = %s", [orden.pk])
            return c.fetchone()

    def test_la_vista_separa_lo_aceptado_de_lo_rechazado(self):
        cliente, orden = self.en_la_puerta()
        l, p = self.linea(orden, LOMO), self.linea(orden, POSTA)
        pedido = 5 * l.precio_unitario_clp + 3 * p.precio_unitario_clp
        self.assertEqual(self.vista(orden), (pedido, 8, 0, 0))
        self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        self.assertEqual(self.vista(orden), (pedido - 2 * l.precio_unitario_clp, 6, 2 * l.precio_unitario_clp, 2))

    def test_los_indicadores_del_crm_cuentan_lo_aceptado(self):
        cliente, orden = self.en_la_puerta()
        gerencia = get_user_model().objects.get(username="gerencia@cofrial.cl")
        antes = dict(crm.indicadores(gerencia)["ventas_por_canal"])["B2C"]
        self.rechazar(cliente, orden, {LOMO: (2, "danado")})
        despues = dict(crm.indicadores(gerencia)["ventas_por_canal"])["B2C"]
        self.assertEqual(antes - despues, 2 * self.linea(orden, LOMO).precio_unitario_clp)

    def test_el_estado_existe_en_el_catalogo(self):
        estado = EstadoOrden.objects.get(nombre=s.RECHAZADA)
        self.assertEqual((estado.orden_flujo, estado.es_final), (9, True))
