from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from crm import servicios as s
from crm.models import EtapaPipeline, Prospecto
from flota.models import Telemetria
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class ReglasDelCrm(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        from django.contrib.auth import get_user_model
        U = get_user_model()
        cls.maria = U.objects.get(username="vendedora@cofrial.test")
        cls.pedro = U.objects.get(username="vendedor2@cofrial.test")
        cls.gerente = U.objects.get(username="gerente@cofrial.test")
        cls.despachador = U.objects.get(username="despachador@cofrial.test")
        cls.ana_user = U.objects.get(username="ana@correo.test")

    def etapa(self, nombre):
        return EtapaPipeline.objects.get(nombre=nombre).pk

    def test_roles(self):
        self.assertEqual([s.rol(u) for u in (self.maria, self.gerente, self.despachador, self.ana_user)],
                         ["vendedor", "gerencia", "despachador", None])

    def test_rn09_cada_vendedor_ve_solo_su_cartera_y_gerencia_ve_todo(self):
        self.assertEqual({c.nombre for c in s.clientes_visibles(self.maria)}, {"Hospital Regional de Temuco"})
        self.assertEqual({c.nombre for c in s.clientes_visibles(self.pedro)}, {"Supermercados del Sur"})
        self.assertGreaterEqual(s.clientes_visibles(self.gerente).count(), 3)
        propios = s.prospectos_visibles(self.maria)
        self.assertTrue(all(p.vendedor.usuario == self.maria for p in propios))
        self.assertGreater(s.prospectos_visibles(self.gerente).count(), propios.count())

    def test_rn10_no_se_puede_saltar_etapas(self):
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")            # etapa Prospecto, de María
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Negociación"))
        with self.assertRaises(s.ErrorDeNegocio):                            # no se puede ni a Cliente ganado
            s.mover_prospecto(self.maria, p.pk, self.etapa("Cliente ganado"), rut="1-9")

    def test_contactado_exige_una_interaccion(self):
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado"))
        s.registrar_interaccion(self.maria, "llamada", "Primera llamada", prospecto=p)      # RN-12
        self.assertEqual(s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado")).etapa.nombre, "Contactado")

    def test_rn11_perder_exige_motivo_y_registra_cierre(self):
        p = Prospecto.objects.get(nombre_contacto="Carla Muñoz")
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Perdido"))
        perdido = s.mover_prospecto(self.maria, p.pk, self.etapa("Perdido"), motivo="Eligió otro proveedor")
        self.assertIsNotNone(perdido.cerrado_en)
        self.assertEqual(perdido.motivo_perdida, "Eligió otro proveedor")
        with self.assertRaises(s.ErrorDeNegocio):                            # una etapa final no sale de ahí
            s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado"))

    def test_rn11_ganar_crea_cliente_b2b_con_el_mismo_vendedor(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")              # Negociación, de Pedro
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"))   # falta el RUT
        ganado = s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut="77.111.222-3")
        self.assertEqual(ganado.cliente.tipo_cliente.codigo, "B2B")
        self.assertEqual(ganado.cliente.vendedor.usuario, self.pedro)
        self.assertIsNotNone(ganado.cerrado_en)

    def test_un_vendedor_no_mueve_prospectos_ajenos_y_gerencia_no_escribe(self):
        p = Prospecto.objects.get(nombre_contacto="Luis Soto")              # de Pedro
        with self.assertRaises(Prospecto.DoesNotExist):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Negociación"))
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.gerente, p.pk, self.etapa("Negociación"))

    def test_rn13_alerta_de_frio_marca_las_ordenes_del_viaje(self):
        hospital = Cliente.objects.get(rut="61.973.200-4")
        orden = Orden.objects.get(direccion__cliente=hospital)
        antes = s.ordenes_de_cliente(hospital)[0].alertas_frio
        despacho = orden.despacho
        Telemetria.objects.create(camion_id=despacho.camion_id, temp_camara=9.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=True)
        self.assertEqual(s.ordenes_de_cliente(hospital)[0].alertas_frio, antes + 1)
        afectadas = {o.orden_id for o in s.ordenes_afectadas(self.maria)}
        self.assertIn(orden.orden_id, afectadas)
        self.assertNotIn(orden.orden_id, {o.orden_id for o in s.ordenes_afectadas(self.pedro)})    # no es de su cartera

    def test_rn15_pedido_a_nombre_del_cliente_exige_la_interaccion(self):
        hospital = Cliente.objects.get(rut="61.973.200-4")
        from catalogo.models import Producto
        lomo = Producto.objects.get(sku="VAC-LOM-5K")
        dir_id = hospital.direccion_set.first().pk
        with self.assertRaises(s.ErrorDeNegocio):
            s.crear_pedido_para_cliente(self.maria, hospital.pk, {lomo.pk: 2}, dir_id, "OC-9", "whatsapp", "x")
        antes = Orden.objects.count()
        orden = s.crear_pedido_para_cliente(self.maria, hospital.pk, {lomo.pk: 2}, dir_id, "OC-9", "llamada", "Pidió 2 cajas por teléfono")
        self.assertEqual(Orden.objects.count(), antes + 1)
        self.assertTrue(hospital.interaccion_set.filter(tipo="llamada", detalle__contains="2 cajas").exists())
        self.assertEqual(orden.estado_orden.nombre, "Recibida")

    def test_indicadores_propios_vs_todos(self):
        self.assertLess(s.indicadores(self.maria)["abiertos"], s.indicadores(self.gerente)["abiertos"])


class AccesoWeb(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_clientes_del_portal_no_entran_al_crm(self):
        self.entrar("ana@correo.test")
        self.assertEqual(self.client.get("/crm/").status_code, 403)

    def test_vendedor_no_ve_la_ficha_de_otro_vendedor(self):
        self.entrar("vendedora@cofrial.test")
        sur = Cliente.objects.get(rut="76.543.210-K")
        self.assertEqual(self.client.get(f"/crm/clientes/{sur.pk}/").status_code, 404)
        hospital = Cliente.objects.get(rut="61.973.200-4")
        self.assertContains(self.client.get(f"/crm/clientes/{hospital.pk}/"), "Hospital Regional")

    def test_despachador_solo_ve_alertas(self):
        self.entrar("despachador@cofrial.test")
        self.assertEqual(self.client.get("/crm/clientes/").status_code, 403)
        self.assertEqual(self.client.get("/crm/alertas/").status_code, 200)
        self.assertRedirects(self.client.get("/crm/"), "/crm/alertas/")

    def test_flujo_del_vendedor_en_el_navegador(self):
        self.entrar("vendedora@cofrial.test")
        r = self.client.post("/crm/prospectos/nuevo/", {"nombre_contacto": "Sofía Paz", "empresa": "Residencial Sur", "email": "sofia@res.test", "origen": "referido", "monto": "2500000"}, follow=True)
        self.assertContains(r, "Residencial Sur")
        self.assertContains(self.client.get("/crm/embudo/"), "Residencial Sur")
        self.assertContains(self.client.get("/crm/"), "oportunidades abiertas")

    def test_gerencia_ve_todo_pero_no_modifica(self):
        self.entrar("gerente@cofrial.test")
        self.assertContains(self.client.get("/crm/embudo/"), "Casino Escolar")
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")
        self.client.post(f"/crm/prospectos/{p.pk}/interaccion/", {"tipo": "nota", "detalle": "intento"})
        self.assertFalse(p.interaccion_set.exists())


class ClasificacionIA(TestCase):
    """RN-14 y CU-09: la IA clasifica, guarda su confianza y, si falla o duda, el requerimiento no se pierde."""

    CATS = ["Consulta de producto", "Reclamo por temperatura", "Atraso en entrega", "Facturación", "Otro"]

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def _req(self, **extra):
        from crm.models import Requerimiento
        return Requerimiento.objects.create(cliente=Cliente.objects.get(rut="12.345.678-5"), asunto="Pedido tibio",
                                            descripcion="La carga llegó tibia", **extra)

    def test_respuesta_valida_con_confianza_alta_clasifica(self):
        from unittest.mock import patch
        with patch("crm.ia._llamar", return_value='{"categoria": "Reclamo por temperatura", "confianza": 0.93}'):
            r = s.clasificar_con_ia(self._req())
        r.refresh_from_db()
        self.assertEqual((r.estado, str(r.categoria_requerimiento), float(r.confianza_ia)), ("clasificado", "Reclamo por temperatura", 0.93))

    def test_tolera_json_dentro_de_texto_y_mayusculas(self):
        from unittest.mock import patch
        from crm import ia
        with patch("crm.ia._llamar", return_value='Claro:\n```json\n{"categoria": "ATRASO EN ENTREGA", "confianza": "0.8"}\n```'):
            self.assertEqual(ia.clasificar("a", "b", self.CATS), ("Atraso en entrega", 0.8))

    def test_confianza_bajo_el_umbral_queda_para_revision_manual(self):
        from unittest.mock import patch
        with patch("crm.ia._llamar", return_value='{"categoria": "Otro", "confianza": 0.4}'):
            r = s.clasificar_con_ia(self._req())
        r.refresh_from_db()
        self.assertEqual((r.estado, r.categoria_requerimiento_id, float(r.confianza_ia)), ("sin_clasificar", None, 0.4))

    def test_si_la_api_falla_el_requerimiento_se_conserva(self):
        from unittest.mock import patch
        from crm import ia
        with patch("crm.ia._llamar", side_effect=ia.ErrorIA("sin red")):
            r = s.clasificar_con_ia(self._req())
        r.refresh_from_db()
        self.assertEqual((r.estado, r.confianza_ia), ("sin_clasificar", None))

    def test_respuestas_invalidas_son_error_de_ia(self):
        from unittest.mock import patch
        from crm import ia
        for texto in ("no es json", '{"categoria": "Inventada", "confianza": 0.9}', '{"categoria": "Otro"}'):
            with patch("crm.ia._llamar", return_value=texto), self.assertRaises(ia.ErrorIA, msg=texto):
                ia.clasificar("a", "b", self.CATS)

    def test_sin_claves_no_hay_proveedor(self):
        from unittest.mock import patch
        from crm import ia
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ia.ErrorIA):
            ia.clasificar("a", "b", self.CATS)

    def test_confianza_se_acota_entre_0_y_1(self):
        from unittest.mock import patch
        from crm import ia
        with patch("crm.ia._llamar", return_value='{"categoria": "Otro", "confianza": 7}'):
            self.assertEqual(ia.clasificar("a", "b", self.CATS)[1], 1.0)

    def entrar(self, usuario):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_cliente_envia_consulta_desde_el_portal_y_se_clasifica(self):
        from unittest.mock import patch
        from crm.models import Requerimiento
        self.entrar("ana@correo.test")
        with patch("crm.ia._llamar", return_value='{"categoria": "Facturación", "confianza": 0.9}'):
            r = self.client.post("/soporte/", {"asunto": "Cobro doble", "descripcion": "Me cobraron dos veces"}, follow=True)
        self.assertContains(r, "Facturación")
        self.assertEqual(Requerimiento.objects.get(asunto="Cobro doble").estado, "clasificado")

    def test_consulta_vacia_se_rechaza_y_la_api_caida_no_impide_registrarla(self):
        from unittest.mock import patch
        from crm import ia
        from crm.models import Requerimiento
        self.entrar("ana@correo.test")
        antes = Requerimiento.objects.count()
        self.client.post("/soporte/", {"asunto": " ", "descripcion": ""})
        self.assertEqual(Requerimiento.objects.count(), antes)
        with patch("crm.ia._llamar", side_effect=ia.ErrorIA("caída")):
            self.client.post("/soporte/", {"asunto": "Duda", "descripcion": "Una duda cualquiera"})
        self.assertEqual(Requerimiento.objects.get(asunto="Duda").estado, "sin_clasificar")

    def test_soporte_exige_cuenta_de_cliente(self):
        self.assertEqual(self.client.get("/soporte/").status_code, 302)
        self.entrar("vendedora@cofrial.test")
        self.assertEqual(self.client.get("/soporte/").status_code, 302)

    def test_vendedor_reintenta_con_ia_pero_gerencia_no(self):
        from unittest.mock import patch
        r = self._req()
        with patch("crm.ia._llamar", return_value='{"categoria": "Reclamo por temperatura", "confianza": 0.9}'):
            self.entrar("gerente@cofrial.test")
            self.client.post(f"/crm/requerimientos/{r.pk}/ia/")
            r.refresh_from_db(); self.assertEqual(r.estado, "sin_clasificar")
            self.entrar("vendedora@cofrial.test")
            self.client.post(f"/crm/requerimientos/{r.pk}/ia/")
            r.refresh_from_db(); self.assertEqual(r.estado, "clasificado")

    def test_el_aviso_distingue_ia_caida_de_confianza_baja(self):
        from unittest.mock import patch
        from crm import ia
        self.entrar("vendedora@cofrial.test")
        with patch("crm.ia._llamar", side_effect=ia.ErrorIA("sin red")):
            r = self.client.post(f"/crm/requerimientos/{self._req().pk}/ia/", follow=True)
        self.assertContains(r, "no está disponible")
        with patch("crm.ia._llamar", return_value='{"categoria": "Otro", "confianza": 0.3}'):
            r = self.client.post(f"/crm/requerimientos/{self._req().pk}/ia/", follow=True)
        self.assertContains(r, "no estuvo lo bastante segura")


class ClienteGemini(TestCase):
    """Interactions API de Gemini: forma de la respuesta, cambio de modelo ante fallas y presupuesto de tiempo (todo simulado)."""

    RESPUESTA = {"status": "completed", "steps": [{"type": "thought", "signature": "x"},
                 {"type": "model_output", "content": [{"type": "text", "text": '{"categoria": "Otro", "confianza": 0.9}'}]}]}

    def test_extrae_el_texto_del_paso_model_output(self):
        from crm import ia
        self.assertIn("Otro", ia._texto_de_interaccion(self.RESPUESTA))
        with self.assertRaises(ia.ErrorIA):
            ia._texto_de_interaccion({"steps": [{"type": "thought"}]})

    def test_si_el_primer_modelo_esta_saturado_usa_el_siguiente(self):
        from unittest.mock import patch
        from crm import ia
        llamados = []

        def falso(url, cuerpo, cabeceras, plazo):
            llamados.append(cuerpo["model"])
            if len(llamados) == 1:
                raise ia.ErrorIA("HTTP 503")
            return self.RESPUESTA
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k", "GEMINI_MODELS": "a-lite, b-flash"}, clear=True), patch("crm.ia._post", side_effect=falso):
            texto = ia._gemini("prompt", 12)
        self.assertEqual(llamados, ["a-lite", "b-flash"])
        self.assertEqual(ia.ultimo_modelo, "Gemini b-flash")
        self.assertIn("Otro", texto)

    def test_envia_clave_en_cabecera_y_razonamiento_bajo_y_nunca_en_la_url(self):
        from unittest.mock import patch
        from crm import ia
        capturado = {}

        def falso(url, cuerpo, cabeceras, plazo):
            capturado.update(url=url, cuerpo=cuerpo, cabeceras=cabeceras)
            return self.RESPUESTA
        with patch.dict("os.environ", {"GEMINI_API_KEY": "SECRETA"}, clear=True), patch("crm.ia._post", side_effect=falso):
            ia._gemini("p", 12)
        self.assertEqual(capturado["cabeceras"], {"x-goog-api-key": "SECRETA"})
        self.assertNotIn("SECRETA", capturado["url"])
        self.assertTrue(capturado["url"].endswith("/v1beta/interactions"))
        self.assertEqual(capturado["cuerpo"]["generation_config"]["thinking_level"], "low")

    def test_modelos_por_defecto_y_override(self):
        from unittest.mock import patch
        from crm import ia
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(ia._modelos()[0], "gemini-3.5-flash-lite")
        with patch.dict("os.environ", {"GEMINI_MODEL": "solo-uno"}, clear=True):
            self.assertEqual(ia._modelos(), ["solo-uno"])

    def test_los_errores_no_incluyen_el_cuerpo_ni_la_clave(self):
        from unittest.mock import patch
        import urllib.error
        from crm import ia
        err = urllib.error.HTTPError("https://x", 503, "busy", {}, None)
        with patch("urllib.request.urlopen", side_effect=err), self.assertRaises(ia.ErrorIA) as cm:
            ia._post("https://x", {}, {"x-goog-api-key": "SECRETA"}, 5)
        self.assertEqual(str(cm.exception), "HTTP 503")

    def test_sin_tiempo_restante_no_llama_a_la_api(self):
        from unittest.mock import patch
        from crm import ia
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k"}, clear=True), patch("crm.ia._post") as p, self.assertRaises(ia.ErrorIA):
            ia._gemini("p", 0.2)
        p.assert_not_called()


class ClienteGroq(TestCase):
    """Respaldo con Groq: cascada de modelos, identificador propio y orden de proveedores (todo simulado)."""

    OK = {"choices": [{"message": {"content": '{"categoria": "Otro", "confianza": 0.8}'}}]}

    def test_cascada_de_modelos_y_razonamiento_bajo(self):
        from unittest.mock import patch
        from crm import ia
        vistos = []

        def falso(url, cuerpo, cabeceras, plazo):
            vistos.append(cuerpo)
            if len(vistos) == 1:
                raise ia.ErrorIA("HTTP 503")
            return self.OK
        with patch.dict("os.environ", {"GROQ_API_KEY": "k", "GROQ_MODELS": "openai/gpt-oss-20b,otro/modelo"}, clear=True), patch("crm.ia._post", side_effect=falso):
            texto = ia._groq("p", 12)
        self.assertEqual([c["model"] for c in vistos], ["openai/gpt-oss-20b", "otro/modelo"])
        self.assertEqual(vistos[0].get("reasoning_effort"), "low")
        self.assertNotIn("reasoning_effort", vistos[1])
        self.assertEqual(ia.ultimo_modelo, "Groq otro/modelo")
        self.assertIn("Otro", texto)

    def test_la_clave_va_en_cabecera_y_hay_modelos_por_defecto(self):
        from unittest.mock import patch
        from crm import ia
        visto = {}

        def falso(url, cuerpo, cabeceras, plazo):
            visto.update(cab=cabeceras, url=url)
            return self.OK
        with patch.dict("os.environ", {"GROQ_API_KEY": "SECRETA"}, clear=True), patch("crm.ia._post", side_effect=falso):
            ia._groq("p", 12)
        self.assertEqual(visto["cab"], {"Authorization": "Bearer SECRETA"})
        self.assertNotIn("SECRETA", visto["url"])
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(ia._modelos_groq()[0], "openai/gpt-oss-20b")

    def test_todas_las_llamadas_llevan_identificador_propio(self):
        from unittest.mock import patch, MagicMock
        from crm import ia
        capturado = {}

        def abrir(pedido, timeout):
            capturado["ua"] = pedido.get_header("User-agent")
            r = MagicMock(); r.read.return_value = b"{}"; r.__enter__.return_value = r
            return r
        with patch("urllib.request.urlopen", side_effect=abrir):
            ia._post("https://x", {}, {}, 5)
        self.assertEqual(capturado["ua"], "cofrial-crm/1.0")          # el de urllib lo bloquea Cloudflare (error 1010)

    def test_orden_de_proveedores_configurable(self):
        from unittest.mock import patch
        from crm import ia
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual([f.__name__ for f in ia._proveedores()], ["_gemini", "_groq"])
        with patch.dict("os.environ", {"IA_PROVEEDORES": "groq, gemini"}, clear=True):
            self.assertEqual([f.__name__ for f in ia._proveedores()], ["_groq", "_gemini"])
        with patch.dict("os.environ", {"IA_PROVEEDORES": "inventado"}, clear=True):
            self.assertEqual([f.__name__ for f in ia._proveedores()], ["_gemini", "_groq"])

    def test_si_gemini_falla_responde_groq(self):
        from unittest.mock import patch
        from crm import ia
        with patch.dict("os.environ", {"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q"}, clear=True), \
                patch("crm.ia._gemini", side_effect=ia.ErrorIA("HTTP 503")), patch("crm.ia._groq", return_value='{"categoria": "Otro", "confianza": 0.7}'):
            self.assertEqual(ia.clasificar("a", "b", ["Otro", "Facturación"]), ("Otro", 0.7))

    def test_un_proveedor_lento_no_deja_sin_tiempo_al_respaldo(self):
        from unittest.mock import patch
        from crm import ia
        plazos = {}

        def lento(prompt, plazo):
            plazos["gemini"] = plazo
            raise ia.ErrorIA("TimeoutError")

        def respaldo(prompt, plazo):
            plazos["groq"] = plazo
            return '{"categoria": "Otro", "confianza": 0.9}'
        with patch.dict("os.environ", {"IA_TIMEOUT_SEG": "12"}, clear=True), patch("crm.ia._gemini", side_effect=lento), patch("crm.ia._groq", side_effect=respaldo):
            ia._llamar("p")
        self.assertLessEqual(plazos["gemini"], 12 * ia.PARTE_MAXIMA_CON_RESPALDO + 0.01)
        self.assertGreaterEqual(plazos["groq"], 3)               # a Groq le basta ~1 s; aquí le quedan más de 3
