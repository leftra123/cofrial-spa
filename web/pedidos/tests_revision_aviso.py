"""Experiencia del cliente que recibe: aviso destacado de llegada y revisión de la entrega (productos, temperatura, todo bien o qué falló)."""
from crm.models import Requerimiento
from flota.models import Telemetria
from pedidos import servicios as s
from pedidos.models import Orden

from .tests_entrega import EntregaBase


class AvisoDestacadoDeLlegadaTests(EntregaBase):
    def camion_a(self, despacho, orden, desplazamiento_grados):
        d = orden.direccion
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=d.lat + desplazamiento_grados, long=d.long, combustible_pct=80,
                                  alerta_ruptura_frio=False)

    def avisos(self, orden):
        self.entrar()
        return {a["tipo"]: a for a in self.client.get("/api/avisos/").json()["avisos"] if a["orden_id"] == orden.pk}

    def test_cerca_es_un_aviso_destacado_con_los_minutos_que_faltan(self):
        cliente, orden, despacho = self.orden_despachada()
        self.camion_a(despacho, orden, 0.005)                                  # ~0,5 km: a menos de 2 km
        a = self.avisos(orden)
        self.assertTrue(a["cerca"]["destacado"])
        self.assertGreaterEqual(a["cerca"]["minutos"], 1)
        self.assertIn("está por llegar", a["cerca"]["texto"])
        self.assertIn("menos de 2 km", a["cerca"]["texto"])
        self.assertIn("llega en", a["cerca"]["texto"])
        self.assertFalse(a["ventana"].get("destacado", False))                 # la ventana horaria es informativa: no hace ruido

    def test_lejos_no_hay_aviso_de_cerca(self):
        cliente, orden, despacho = self.orden_despachada()
        self.camion_a(despacho, orden, 0.05)                                   # ~5,5 km
        self.assertNotIn("cerca", self.avisos(orden))

    def test_en_la_puerta_el_aviso_es_destacado_y_pide_revisar(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        puerta = self.avisos(orden)["puerta"]
        self.assertTrue(puerta["destacado"])
        self.assertTrue(puerta["texto"].startswith("Estamos afuera"))          # el banner y la campanita reconocen el aviso que espera respuesta por este texto
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        self.assertFalse(self.avisos(orden)["puerta"]["destacado"])            # ya respondió: queda el registro, no el banner

    def test_el_banner_y_la_revision_estan_en_los_scripts_de_todas_las_paginas(self):
        js = open("static/js/campana.js", encoding="utf-8").read()
        self.assertIn("aviso-llegada", js)
        self.assertIn("CofrialEntrega.revisar", js)
        self.assertIn("cofrial-aviso-cerrado", js)                             # el aviso de «cerca» se puede cerrar; el que espera tu respuesta no
        self.assertIn("ac.appendChild(x)", js)                                 # la cruz va en la misma fila que «Ver dónde va»
        self.assertNotIn("it.appendChild(x)", js)
        css = open("static/css/tienda.css", encoding="utf-8").read()
        self.assertIn("button.al-cerrar:not(#mp-brick-container button)", css)
        self.assertNotIn(".al-cerrar { position: absolute", css)
        self.entrar()
        self.assertContains(self.client.get("/catalogo/"), "js/campana.js")


class RevisionAlRecibirTests(EntregaBase):
    def en_la_puerta(self, con_lectura=True):
        cliente, orden, despacho = self.orden_despachada()
        if con_lectura:
            Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=False)
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        self.entrar()
        return cliente, orden

    def test_la_pantalla_muestra_productos_cantidades_y_temperatura_del_viaje(self):
        cliente, orden = self.en_la_puerta()
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn("Revisa tu pedido antes de confirmar", html)
        for item in orden.ordenitem_set.select_related("producto"):
            self.assertIn(item.producto.nombre, html)
            self.assertIn(f"<b>{item.cantidad}</b> × {item.producto.nombre}", html)
        self.assertIn("Temperatura del viaje", html)
        self.assertIn("Dentro de rango", html)
        for esperado in ("Sí, todo llegó bien", "No, algo falló", "No recibiré mi pedido", 'value="no"', 'name="resultado"', 'name="tipo_problema"', 'name="problema"', "Recibí mi pedido", 'value="no_recibido"'):
            self.assertIn(esperado, html, esperado)
        js = open("static/js/entrega.js", encoding="utf-8").read()
        self.assertIn('["no", "No recibiré mi pedido"]', js)
        self.assertIn('value: "no_recibido"', js)
        self.assertIn('type: "button", "class": "btn-sec"}, "Cancelar"', js)
        self.assertIn('enviar(ordenId, "no_recibido"', js)

    def test_la_revision_marca_la_temperatura_fuera_de_rango(self):
        cliente, orden = self.en_la_puerta(con_lectura=False)
        Telemetria.objects.create(camion=orden.despacho.camion, temp_camara=12.0, lat=-38.74, long=-72.60, combustible_pct=80, alerta_ruptura_frio=True)
        r = s.revision_de(orden)
        self.assertFalse(r["temperatura"]["en_rango"])
        self.assertTrue(r["temperatura"]["hubo_ruptura"])
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), "Fuera de rango")

    def test_sin_lecturas_la_revision_igual_muestra_los_productos(self):
        cliente, orden = self.en_la_puerta(con_lectura=False)
        r = s.revision_de(orden)
        self.assertEqual([p["cantidad"] for p in r["productos"]], [1])
        self.assertTrue(all(t["etiqueta"] for t in r["problemas"]))

    def test_el_json_para_el_dialogo_trae_la_revision_solo_si_se_pide_y_se_puede_responder(self):
        cliente, orden = self.en_la_puerta()
        self.assertNotIn("revision", self.client.get(f"/pedidos/{orden.pk}/entrega/").json())
        rev = self.client.get(f"/pedidos/{orden.pk}/entrega/?revision=1").json()["revision"]
        self.assertEqual(rev["orden_id"], orden.pk)
        self.assertTrue(rev["productos"])
        self.assertIn("temperatura", rev)
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        self.assertNotIn("revision", self.client.get(f"/pedidos/{orden.pk}/entrega/?revision=1").json())

    def test_todo_bien_deja_la_orden_entregada_sin_reclamo(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "bien"}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Entregada")
        self.assertFalse(Requerimiento.objects.filter(orden=orden).exists())

    def test_algo_fallo_deja_entregada_y_crea_el_reclamo_para_ventas(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", "tipo_problema": "temperatura",
                             "problema": "Las cajas llegaron tibias al tacto"}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ventas", r.json()["mensaje"])
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Entregada")               # el camión sí entregó: lo que falló es un reclamo, no una entrega fallida
        req = Requerimiento.objects.get(orden=orden)
        self.assertEqual((req.cliente, req.descripcion), (cliente, "Las cajas llegaron tibias al tacto"))
        self.assertEqual(str(req.categoria_requerimiento), "Reclamo por temperatura")
        self.assertEqual(req.estado, "clasificado")
        self.assertIn(f"N.º {orden.pk}", req.asunto)
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "Ventas ya tiene tu aviso")
        self.assertContains(pagina, "Las cajas llegaron tibias al tacto")

    def test_cada_tipo_de_falla_va_a_su_categoria_del_crm(self):
        for tipo, categoria in (("faltante", "Problema en la entrega"), ("danado", "Problema en la entrega")):
            with self.subTest(tipo):
                cliente, orden = self.en_la_puerta()
                s.resolver_entrega(cliente, orden.pk, "aceptar", "Una caja venía abierta", con_problema=True, tipo_problema=tipo)
                self.assertEqual(str(Requerimiento.objects.get(orden=orden).categoria_requerimiento), categoria)

    def test_decir_que_no_recibe_no_confirma_la_entrega(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "no", "motivo": "No había nadie en la casa"},
                             headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("exitosamente", r.json()["mensaje"])
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Entrega no concretada")
        self.assertEqual(orden.entrega_motivo, "No había nadie en la casa")

    def test_si_algo_fallo_hay_que_contar_que_y_no_cambia_nada_hasta_hacerlo(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", "problema": "no"}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("qué falló", r.json()["mensaje"])
        self.assertEqual(Orden.objects.get(pk=orden.pk).estado_orden.nombre, "Camión en la puerta")
        self.assertFalse(Requerimiento.objects.filter(orden=orden).exists())

    def test_sin_javascript_el_formulario_de_revision_tambien_funciona(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", "tipo_problema": "faltante",
                             "problema": "Faltó una caja de lomo"}, follow=True)
        self.assertContains(r, "Registramos el problema")
        self.assertEqual(Requerimiento.objects.filter(orden=orden).count(), 1)

    def test_el_reclamo_solo_se_crea_una_vez_aunque_se_repita_la_respuesta(self):
        cliente, orden = self.en_la_puerta()
        datos = {"accion": "aceptar", "resultado": "falla", "tipo_problema": "danado", "problema": "Caja rota"}
        self.assertEqual(self.client.post(f"/pedidos/{orden.pk}/entrega/", datos, headers={"X-Requested-With": "fetch"}).status_code, 200)
        self.assertEqual(self.client.post(f"/pedidos/{orden.pk}/entrega/", datos, headers={"X-Requested-With": "fetch"}).status_code, 400)
        self.assertEqual(Requerimiento.objects.filter(orden=orden).count(), 1)

    def test_una_orden_ajena_no_se_revisa(self):
        cliente, orden = self.en_la_puerta()
        self.entrar("abastecimiento@hospital.test")
        self.assertEqual(self.client.get(f"/pedidos/{orden.pk}/entrega/?revision=1").status_code, 404)
        self.assertEqual(self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "aceptar", "resultado": "falla", "problema": "intruso intruso"}).status_code, 404)
