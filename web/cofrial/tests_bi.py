"""El panel de BI (Grafana) solo se abre por /bi/, con sesión y rol de administración o gerencia, y Grafana recibe la identidad correcta."""
import http.server
import json
import re
import threading

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

CLAVE = "demo-cofrial-2026"
RECIBIDO = []


class GrafanaFalso(http.server.BaseHTTPRequestHandler):
    """Hace de Grafana: anota lo que le llega y responde según la ruta."""

    def _responder(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo).decode() if largo else ""
        RECIBIDO.append({"metodo": self.command, "ruta": self.path, "cabeceras": {k.lower(): v for k, v in self.headers.items()}, "cuerpo": cuerpo})
        if self.path.startswith("/bi/falta"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "grafana_session=abc; Path=/bi/; HttpOnly; SameSite=Lax")
        self.send_header("Set-Cookie", "grafana_session_expiry=123; Path=/bi/; SameSite=Lax")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    do_GET = do_POST = do_DELETE = _responder

    def log_message(self, *args):
        pass


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), GrafanaFalso)
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.servidor.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        super().tearDownClass()

    def setUp(self):
        RECIBIDO.clear()
        cache.clear()
        self._ajuste = override_settings(GRAFANA_INTERNA_URL=self.url)
        self._ajuste.enable()
        self.addCleanup(self._ajuste.disable)

    def entrar(self, usuario):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c


class QuienEntra(Base):
    def test_sin_sesion_va_a_la_pantalla_de_entrar_y_grafana_no_recibe_nada(self):
        r = Client().get("/bi/")
        self.assertRedirects(r, "/cuenta/entrar/?next=/bi/", fetch_redirect_response=False)
        self.assertEqual(RECIBIDO, [])

    def test_los_demas_roles_reciben_403_y_grafana_no_recibe_nada(self):
        for usuario in ("vendedora@cofrial.cl", "despacho@cofrial.cl", "felipe@cofrial.cl", "ana@correo.test"):
            r = self.entrar(usuario).get("/bi/")
            self.assertEqual(r.status_code, 403, usuario)
            self.assertEqual(self.entrar(usuario).get("/bi/api/ds/query").status_code, 403, usuario)
        self.assertEqual(RECIBIDO, [])

    def test_admin_y_gerencia_ven_el_tablero(self):
        for usuario in ("admin@cofrial.cl", "gerencia@cofrial.cl"):
            r = self.entrar(usuario).get("/bi/")
            self.assertEqual(r.status_code, 200, usuario)
            self.assertEqual(json.loads(b"".join(r.streaming_content)), {"ok": True})

    def test_el_enlace_del_menu_solo_les_aparece_a_ellos(self):
        for usuario, ve in (("admin@cofrial.cl", True), ("gerencia@cofrial.cl", True), ("vendedora@cofrial.cl", False),
                            ("despacho@cofrial.cl", False), ("felipe@cofrial.cl", False)):
            r = self.entrar(usuario).get("/crm/" if usuario != "felipe@cofrial.cl" else "/catalogo/")
            self.assertEqual('href="/bi/"' in r.content.decode(), ve, usuario)


class LoQueRecibeGrafana(Base):
    def test_identidad_y_rol_los_pone_django(self):
        self.entrar("gerencia@cofrial.cl").get("/bi/d/cofrial")
        gerencia = RECIBIDO[-1]
        self.assertEqual(gerencia["ruta"], "/bi/d/cofrial")
        self.assertEqual(gerencia["cabeceras"]["x-webauth-user"], "django-gerencia@cofrial.cl")
        self.assertEqual(gerencia["cabeceras"]["x-webauth-role"], "Viewer")
        self.entrar("admin@cofrial.cl").get("/bi/")
        self.assertEqual(RECIBIDO[-1]["cabeceras"]["x-webauth-role"], "Admin")

    def test_lo_que_manda_el_navegador_no_puede_suplantar_la_identidad(self):
        self.entrar("gerencia@cofrial.cl").get("/bi/", HTTP_X_WEBAUTH_USER="admin", HTTP_X_WEBAUTH_ROLE="Admin",
                                               HTTP_X_FORWARDED_FOR="1.2.3.4", HTTP_AUTHORIZATION="Basic YWRtaW46YWRtaW4=")
        c = RECIBIDO[-1]["cabeceras"]
        self.assertEqual(c["x-webauth-user"], "django-gerencia@cofrial.cl")
        self.assertEqual(c["x-webauth-role"], "Viewer")
        self.assertNotIn("x-forwarded-for", c)
        self.assertNotIn("authorization", c)

    def test_la_cookie_de_django_no_llega_a_grafana_pero_la_de_grafana_si(self):
        c = self.entrar("admin@cofrial.cl")
        c.cookies["grafana_session"] = "xyz"
        c.get("/bi/")
        cookies = RECIBIDO[-1]["cabeceras"].get("cookie", "")
        self.assertIn("grafana_session=xyz", cookies)
        self.assertNotIn("sessionid", cookies)
        self.assertNotIn("csrftoken", cookies)

    def test_las_cookies_de_grafana_vuelven_al_navegador(self):
        r = self.entrar("admin@cofrial.cl").get("/bi/")
        self.assertIn("grafana_session", r.cookies)
        self.assertIn("grafana_session_expiry", r.cookies)
        self.assertTrue(r.cookies["grafana_session"]["httponly"])

    def test_las_consultas_del_tablero_pasan_con_su_cuerpo(self):
        r = self.entrar("gerencia@cofrial.cl").post("/bi/api/ds/query?ds_type=postgres", data='{"queries":[]}', content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(RECIBIDO[-1]["metodo"], "POST")
        self.assertEqual(RECIBIDO[-1]["ruta"], "/bi/api/ds/query?ds_type=postgres")
        self.assertEqual(RECIBIDO[-1]["cuerpo"], '{"queries":[]}')
        self.assertIn("no-store", r["Cache-Control"])


class Defensas(Base):
    def test_una_escritura_desde_otro_sitio_se_rechaza(self):
        c = self.entrar("admin@cofrial.cl")
        r = c.post("/bi/api/dashboards/db", data="{}", content_type="application/json", HTTP_ORIGIN="https://sitio-malo.example")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(RECIBIDO, [])
        r = c.post("/bi/api/dashboards/db", data="{}", content_type="application/json", HTTP_ORIGIN="http://testserver")
        self.assertEqual(r.status_code, 200)

    def test_si_grafana_no_responde_es_un_502_controlado(self):
        with override_settings(GRAFANA_INTERNA_URL="http://127.0.0.1:1"):
            r = self.entrar("admin@cofrial.cl").get("/bi/")
        self.assertEqual(r.status_code, 502)
        self.assertContains(r, "no está disponible", status_code=502)

    def test_los_404_de_grafana_no_cuentan_como_barrido_de_rutas(self):
        c = self.entrar("admin@cofrial.cl")
        for _ in range(80):
            self.assertEqual(c.get("/bi/falta").status_code, 404)
        self.assertEqual(c.get("/crm/").status_code, 200)


class GrafanaNoSePublica(TestCase):
    """Grafana confía en la cabecera X-WEBAUTH-USER: si su puerto se abre, cualquiera puede declararse administrador. Estas pruebas vigilan que no vuelva a publicarse."""

    RAIZ = settings.BASE_DIR.parent

    def _bloque(self, texto, servicio):
        inicio = texto.index(f"\n  {servicio}:\n")
        resto = texto[inicio + 1:]
        fin = re.search(r"\n  \S", resto[len(servicio) + 4:])
        return resto if fin is None else resto[:len(servicio) + 4 + fin.start()]

    def test_ningun_compose_publica_el_puerto_de_grafana(self):
        for ruta in ("docker-compose.yml", "aws/docker-compose.web.yml"):
            archivo = self.RAIZ / ruta
            if not archivo.exists():                      # la imagen del servidor solo trae web/
                self.skipTest("sin los archivos de despliegue")
            bloque = self._bloque(archivo.read_text(), "grafana")
            self.assertNotIn("ports:", bloque, f"{ruta}: Grafana no debe publicar puertos (solo expose)")
            self.assertIn("GF_AUTH_PROXY_ENABLED", bloque)
            self.assertIn('GF_AUTH_DISABLE_LOGIN_FORM: "true"', bloque)

    def test_el_security_group_no_abre_el_3000(self):
        archivo = self.RAIZ / "aws" / "provision.sh"
        if not archivo.exists():
            self.skipTest("sin los archivos de despliegue")
        abre = [l for l in archivo.read_text().splitlines() if l.startswith("regla ") and "--port 3000" in l]
        self.assertEqual(abre, [], "provision.sh no debe abrir el puerto 3000")
