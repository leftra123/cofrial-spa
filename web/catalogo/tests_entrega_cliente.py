"""Pantalla del cliente «Estamos afuera» y cierre del circuito con la IA del CRM (usa el ciclo de entrega de pedidos/ sin modificarlo)."""
import json
from unittest.mock import patch

from crm import servicios as crm
from crm.models import Requerimiento
from pedidos import servicios as s
from pedidos.tests_entrega import EntregaBase

DESGLOSE = json.dumps({"resumen": "No había nadie en la casa.", "motivo_principal": "nadie_en_casa", "hechos": [{"afirmacion": "Nadie recibió", "cita": "No había nadie"}],
                       "urgencia": "baja", "accion_sugerida": "reprogramar_entrega", "confianza": 0.9})


class PantallaEstamosAfuera(EntregaBase):
    def en_la_puerta(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        return cliente, orden

    def test_en_la_puerta_muestra_las_dos_respuestas_con_limites_y_contador(self):
        _, orden = self.en_la_puerta()
        html = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        for esperado in ("Estamos afuera de tu dirección", "Recibí mi pedido", "No pude recibirlo", 'id="entrega"', 'maxlength="500"', 'minlength="5"',
                         'id="motivo-cuenta"', 'role="alert"', "js/entrega.js", "CofrialEntrega.iniciar"):
            self.assertIn(esperado, html, esperado)

    def test_sin_javascript_los_formularios_siguen_funcionando(self):
        cliente, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "no_recibido", "motivo": "No había nadie"})
        self.assertEqual(r.status_code, 302)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Entrega no concretada")

    def test_el_servidor_rechaza_un_motivo_corto_y_no_cambia_el_estado(self):
        _, orden = self.en_la_puerta()
        r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "no_recibido", "motivo": "no"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.nombre, "Camión en la puerta")

    def test_estados_entregada_automatica_y_no_concretada(self):
        cliente, orden = self.en_la_puerta()
        orden.refresh_from_db()
        from django.utils import timezone
        orden.estado_orden = s._estado("Entregada")
        orden.entrega_automatica, orden.entrega_resuelta_en = True, timezone.now()
        orden.save()
        self.assertContains(self.client.get(f"/pedidos/{orden.pk}/"), "lo dimos por entregado")
        s.llegar_a_la_puerta([orden])                                              # no cambia: ya no está «Despachada»
        orden.estado_orden, orden.entrega_automatica, orden.entrega_motivo = s._estado("Entrega no concretada"), False, "Nadie en la bodega"
        orden.save()
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, "Nadie en la bodega")
        self.assertContains(pagina, "Qué sigue")

    def test_antes_de_salir_no_hay_mapa(self):
        cliente, orden, _ = self.orden_despachada()
        orden.despacho = None
        orden.estado_orden = s._estado("En preparación")
        orden.save()
        self.entrar()
        pagina = self.client.get(f"/pedidos/{orden.pk}/").content.decode()
        self.assertIn("aún no sale", pagina)
        self.assertNotIn('id="mapa"', pagina)

    def test_la_campanita_trae_el_aviso_y_los_botones(self):
        _, orden = self.en_la_puerta()
        avisos = self.client.get("/api/avisos/").json()["avisos"]
        puerta = next(a for a in avisos if a["tipo"] == "puerta" and a["orden_id"] == orden.pk)
        self.assertTrue(puerta["texto"].startswith("Estamos afuera"))          # el JS de la campanita enseña los botones con este texto
        self.assertIn("CofrialEntrega", open("static/js/campana.js", encoding="utf-8").read())


class CircuitoConLaIA(EntregaBase):
    def test_no_pude_recibirlo_crea_requerimiento_con_categoria_y_desglose(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        self.entrar()
        with patch("crm.ia._llamar", return_value=DESGLOSE) as m:
            r = self.client.post(f"/pedidos/{orden.pk}/entrega/", {"accion": "no_recibido", "motivo": "No había nadie en la casa"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(r.json()["ok"])
        self.assertEqual(m.call_count, 1)                                       # solo el desglose: la categoría se conoce
        req = Requerimiento.objects.get(orden=orden)
        self.assertEqual(req.descripcion, "No había nadie en la casa")          # el texto del cliente, intacto
        self.assertEqual((req.categoria_requerimiento.nombre, req.estado), (crm.CATEGORIA_ENTREGA, "clasificado"))
        self.assertEqual(req.desglose["motivo_principal"], "nadie_en_casa")
        self.assertEqual(req.desglose["urgencia"], "baja")

    def test_si_la_ia_falla_el_requerimiento_igual_queda_en_la_categoria(self):
        from crm.ia import ErrorIA
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        with patch("crm.ia._llamar", side_effect=ErrorIA("sin red")):
            s.resolver_entrega(cliente, orden.pk, "no_recibido", "Llegó tarde y no pude recibirlo")
        req = Requerimiento.objects.get(orden=orden)
        self.assertEqual(req.categoria_requerimiento.nombre, crm.CATEGORIA_ENTREGA)
        self.assertIsNone(req.desglose)

    def test_recibi_mi_pedido_no_crea_requerimiento(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        with patch("crm.ia._llamar") as m:
            s.resolver_entrega(cliente, orden.pk, "aceptar")
        self.assertEqual(m.call_count, 0)
        self.assertFalse(Requerimiento.objects.filter(orden=orden).exists())

    def test_ventas_ve_el_requerimiento_con_su_desglose(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        with patch("crm.ia._llamar", return_value=DESGLOSE):
            s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en la casa")
        req = Requerimiento.objects.get(orden=orden)
        self.client.logout()
        self.assertTrue(self.client.login(username="vendedora@cofrial.cl", password="demo-cofrial-2026"))
        pagina = self.client.get(f"/crm/requerimientos/{req.pk}/")
        for esperado in ("Desglose de la IA", "No había nadie en la casa", "Problema en la entrega", "Por entrega"):
            self.assertContains(pagina, esperado)


class AsistenteConElCamionEnLaPuerta(EntregaBase):
    def test_el_contexto_dice_que_el_camion_esta_en_la_puerta(self):
        from catalogo.asistente import estado_de_pedido, _pedido
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        orden.refresh_from_db()
        ctx = _pedido(orden, None)
        self.assertEqual(ctx["estado"], "con el camión en la puerta")
        self.assertIn("No pude recibirlo", ctx["que_pasa_ahora"])
        self.assertEqual(estado_de_pedido("Entrega no concretada"), "con la entrega sin concretar")


class DesgloseSinElAsuntoAutomatico(EntregaBase):
    def test_a_la_ia_solo_va_lo_que_escribio_el_cliente(self):
        cliente, orden, _ = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        enviados = []
        with patch("crm.ia._llamar", side_effect=lambda prompt, plazo=None, orden=None: enviados.append(prompt) or DESGLOSE):
            s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en la casa")
        self.assertEqual(len(enviados), 1)
        self.assertNotIn("Entrega no concretada del pedido", enviados[0])
        self.assertIn("No había nadie en la casa", enviados[0])
        req = Requerimiento.objects.get(orden=orden)
        self.assertEqual(req.asunto, f"Entrega no concretada del pedido N.º {orden.pk}")          # el asunto se guarda igual
        self.assertTrue(all("Entrega no concretada" not in h["afirmacion"] for h in req.desglose["hechos"]))

    def test_un_asunto_escrito_por_el_cliente_si_va(self):
        cliente, orden, _ = self.orden_despachada()
        enviados = []
        with patch("crm.ia._llamar", side_effect=lambda prompt, plazo=None, orden=None: enviados.append(prompt) or DESGLOSE):
            crm.crear_requerimiento(cliente, "Camión con carga caliente", "No quise recibirla", orden=orden)
        self.assertTrue(any("Camión con carga caliente" in p for p in enviados))


class ContadorDeLaCampanita(EntregaBase):
    def test_solo_cuenta_lo_que_espera_una_respuesta_o_es_nuevo(self):
        import json
        import os
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("sin node")
        ahora = 1_800_000_000_000
        iso = lambda ms: __import__("datetime").datetime.fromtimestamp(ahora / 1000 - ms / 1000, __import__("datetime").timezone.utc).isoformat()
        avisos = [
            {"id": "1-puerta", "tipo": "puerta", "texto": "Estamos afuera de tu dirección con tu pedido N.º 1.", "cuando": iso(3 * 86400_000)},   # pendiente de respuesta, aunque sea viejo
            {"id": "2-no-concretada", "tipo": "no_concretada", "texto": "No pudimos entregar", "cuando": iso(86400_000)},
            {"id": "3-llego", "tipo": "llego", "texto": "Tu pedido quedó entregado", "cuando": iso(60_000)},                                          # nuevo y reciente
            {"id": "4-llego", "tipo": "llego", "texto": "Tu pedido quedó entregado", "cuando": iso(86400_000)},                                       # viejo: no suma
            {"id": "5-salio", "tipo": "salio", "texto": "salió", "cuando": iso(60_000)},                                                             # ya visto: no suma
            {"id": "6-puerta", "tipo": "puerta", "texto": "El camión llegó a tu dirección con el pedido N.º 6", "cuando": iso(60_000)},               # ya respondido, visto
        ]
        guion = "global.window = global; global.document = {}; require(process.argv[1]);" \
                f"console.log(CofrialEntrega.contarAvisos({json.dumps(avisos)}, ['5-salio', '6-puerta'], {ahora}));"
        salida = subprocess.run(["node", "-e", guion, os.path.abspath("static/js/entrega.js")], capture_output=True, text=True, timeout=20)
        self.assertEqual(salida.stdout.strip(), "3", salida.stderr)                 # 1-puerta, 2-no-concretada y 3-llego
