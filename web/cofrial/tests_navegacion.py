"""Navegación y filtros: el menú de cada rol no ofrece enlaces que den 403, marca la sección actual y carga los scripts que mantienen la barra y los filtros."""
from html.parser import HTMLParser

from django.core.management import call_command
from django.test import Client, TestCase

CLAVE = "demo-cofrial-2026"
CLIENTES = ("ana@correo.test", "abastecimiento@hospital.test")
EQUIPO = ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "admin@cofrial.cl")


class EnlacesDeNavegacion(HTMLParser):
    """Junta los enlaces internos que están dentro de un <nav> y los que llevan aria-current (la sección marcada)."""
    def __init__(self):
        super().__init__()
        self.en_nav = 0
        self.enlaces, self.actuales = [], []
        self._href = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav":
            self.en_nav += 1
        if tag == "a" and self.en_nav and (a.get("href") or "").startswith("/"):
            self.enlaces.append(a["href"])
            if a.get("aria-current") == "page":
                self.actuales.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "nav" and self.en_nav:
            self.en_nav -= 1


def enlaces_de(html):
    p = EnlacesDeNavegacion()
    p.feed(html)
    return p


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c


class MenuSinEnlacesProhibidos(Base):
    """Regla de cofrial/contexto.py: el menú es solo presentación, pero no debe ofrecer enlaces que darían 403 (ni rotos)."""
    def _revisar(self, cliente, partida, quien):
        vistos = set()
        for pagina in (partida, "/catalogo/", "/crm/", "/flota/", "/pedidos/"):
            r = cliente.get(pagina)
            if r.status_code >= 400:
                continue      # esa pantalla no es de este rol; el menú que importa es el de las que sí abre
            for href in enlaces_de(r.content.decode()).enlaces:
                if href in vistos or href.startswith(("/bi/", "/cuenta/salir/")):
                    continue
                vistos.add(href)
                with self.subTest(quien=quien, desde=pagina, enlace=href):
                    self.assertLess(cliente.get(href).status_code, 400, f"{quien}: «{href}» está en el menú de {pagina} y no se puede abrir")
        self.assertTrue(vistos, f"{quien}: el menú no tiene enlaces")

    def test_anonimo(self):
        self._revisar(Client(), "/", "anónimo")

    def test_clientes(self):
        for u in CLIENTES:
            self._revisar(self.entrar(u), "/catalogo/", u)

    def test_equipo(self):
        for u in EQUIPO:
            self._revisar(self.entrar(u), "/crm/" if u != "despacho@cofrial.cl" else "/flota/", u)


class SeccionActualYScripts(Base):
    def test_tienda_marca_el_catalogo_y_ofrece_soporte(self):
        html = self.entrar("ana@correo.test").get("/catalogo/").content.decode()
        e = enlaces_de(html)
        self.assertIn("/catalogo/", e.actuales)
        self.assertIn("/soporte/", e.enlaces)
        for js in ("js/nav.js", "js/filtros.js"):
            self.assertIn(js, html)

    def test_soporte_queda_marcado_en_su_pantalla(self):
        self.assertIn("/soporte/", enlaces_de(self.entrar("ana@correo.test").get("/soporte/").content.decode()).actuales)

    def test_submenu_del_crm_marca_la_seccion_con_aria_current(self):
        c = self.entrar("vendedora@cofrial.cl")
        for ruta in ("/crm/clientes/", "/crm/embudo/", "/crm/cobranza/", "/crm/requerimientos/", "/crm/ia/", "/crm/demanda/", "/crm/alertas/"):
            with self.subTest(ruta=ruta):
                self.assertIn(ruta, enlaces_de(c.get(ruta).content.decode()).actuales)

    def test_el_panel_interno_carga_los_dos_scripts(self):
        html = self.entrar("vendedora@cofrial.cl").get("/crm/clientes/").content.decode()
        for js in ("js/nav.js", "js/filtros.js"):
            self.assertIn(js, html)

    def test_data_u_separa_los_filtros_por_cuenta_sin_datos_personales(self):
        anonimo = Client().get("/catalogo/").content.decode()
        self.assertIn('data-u=""', anonimo)
        c = self.entrar("ana@correo.test")
        html = c.get("/catalogo/").content.decode()
        self.assertRegex(html, r'data-u="\d+"')
        self.assertNotIn("ana@correo.test", html.split("<body", 1)[1].split(">", 1)[0])      # en la etiqueta <body> solo va el id numérico
