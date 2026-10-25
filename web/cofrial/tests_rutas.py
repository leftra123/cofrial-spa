"""Navegación por rol: dónde cae cada cuenta al entrar, qué enlaces ve y quién entra a cada ruta (la tabla de docs/rutas-y-roles.md).

La prueba recorre TODAS las rutas del proyecto con una cuenta de cada tipo. Una ruta nueva sin fila en ESPERADO la hace fallar:
así ninguna ruta queda sin decidir quién entra."""
import re

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import URLResolver, get_resolver

CLAVE = "demo-cofrial-2026"
CUENTAS = {"anonimo": None, "B2B": "abastecimiento@hospital.test", "B2C": "ana@correo.test", "vendedor": "vendedora@cofrial.cl",
           "gerencia": "gerencia@cofrial.cl", "despachador": "despacho@cofrial.cl", "admin": "admin@cofrial.cl"}
ROLES = list(CUENTAS)
INICIO = {"B2B": "/catalogo/", "B2C": "/catalogo/", "vendedor": "/crm/", "gerencia": "/crm/", "despachador": "/flota/", "admin": "/crm/"}

# url (con 999999 y NO-EXISTE donde va un id) -> (GET, POST) para [anonimo, B2B, B2C, vendedor, gerencia, despachador, admin].
# 200 = entra · L = redirige al login · 403/404/405/400 = ese código · →destino = redirige ahí (N = un número).
# Generada recorriendo las rutas (ver docs/rutas-y-roles.md); revisada a mano. Los comentarios de abajo marcan lo que se decidió.
ESPERADO = {
    '/': ('200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/', '200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/'),
    '/portada/': ('200 200 200 200 200 200 200', '200 200 200 200 200 200 200'),
    '/guia/': ('200 200 200 200 200 200 200', '200 200 200 200 200 200 200'),
    '/catalogo/': ('200 200 200 200 200 200 200', '200 200 200 200 200 200 200'),
    '/catalogo/999999/': ('404 404 404 404 404 404 404', '404 404 404 404 404 404 404'),
    '/crm/': ('L 403 403 200 200 →/crm/alertas/ 200', 'L 403 403 200 200 →/crm/alertas/ 200'),
    '/crm/embudo/': ('L 403 403 200 200 403 200', 'L 403 403 200 200 403 200'),
    '/crm/prospectos/nuevo/': ('L 403 403 200 403 403 200', 'L 403 403 200 403 403 200'),
    '/crm/prospectos/999999/': ('L 403 403 404 404 403 404', 'L 403 403 404 404 403 404'),
    '/crm/prospectos/999999/mover/': ('405 405 405 405 405 405 405', 'L 403 403 404 404 403 404'),
    '/crm/prospectos/999999/interaccion/': ('405 405 405 405 405 405 405', 'L 403 403 404 404 403 404'),
    '/crm/clientes/': ('L 403 403 200 200 403 200', 'L 403 403 200 200 403 200'),
    '/crm/clientes/999999/': ('L 403 403 404 404 403 404', 'L 403 403 404 404 403 404'),
    '/crm/clientes/999999/interaccion/': ('405 405 405 405 405 405 405', 'L 403 403 404 404 403 404'),
    '/crm/clientes/999999/pedido/': ('405 405 405 405 405 405 405', 'L 403 403 404 404 403 404'),
    '/crm/requerimientos/': ('L 403 403 200 200 403 200', 'L 403 403 200 200 403 200'),
    '/crm/requerimientos/999999/': ('L 403 403 404 404 403 404', 'L 403 403 404 404 403 404'),
    '/crm/requerimientos/999999/ia/': ('405 405 405 405 405 405 405', 'L 403 403 →/crm/requerimientos/ →/crm/requerimientos/ 403 →/crm/requerimientos/'),
    '/crm/requerimientos/999999/clasificar/': ('405 405 405 405 405 405 405', 'L 403 403 →/crm/requerimientos/ →/crm/requerimientos/ 403 →/crm/requerimientos/'),
    '/crm/ia/': ('L 403 403 200 200 403 200', 'L 403 403 200 200 403 200'),
    '/crm/demanda/': ('L 403 403 200 200 200 200', 'L 403 403 200 200 200 200'),
    '/crm/alertas/': ('L 403 403 200 200 200 200', 'L 403 403 200 200 200 200'),
    '/flota/': ('L 403 403 403 200 200 200', 'L 403 403 403 200 200 200'),
    '/flota/despachar/': ('L 403 403 403 200 200 200', 'L 403 403 403 →/flota/despachar/ →/flota/despachar/ →/flota/despachar/'),
    '/flota/viajes/999999/cerrar/': ('405 405 405 405 405 405 405', 'L 403 403 403 403 →/flota/ →/flota/'),
    '/flota/despachar/ruta/': ('L 403 403 403 200 200 200', 'L 403 403 403 200 200 200'),
    '/flota/despachar/ubicar/999999/': ('405 405 405 405 405 405 405', 'L 403 403 403 404 404 404'),
    '/demo/': ('L 403 403 403 403 403 200', 'L 403 403 403 403 403 200'),
    '/demo/pulso/': ('405 405 405 405 405 405 405', 'L 403 403 403 403 403 400'),
    '/demo/apagar/': ('405 405 405 405 405 405 405', 'L 403 403 403 403 403 400'),
    '/demo/limpiar/': ('405 405 405 405 405 405 405', 'L 403 403 403 403 403 400'),
    '/api/asistente/': ('404 404 404 404 404 404 404', '400 400 400 400 400 400 400'),
    '/api/productos/': ('200 200 200 200 200 200 200', '200 200 200 200 200 200 200'),
    '/api/productos/NO-EXISTE/': ('404 404 404 404 404 404 404', '404 404 404 404 404 404 404'),
    '/api/flota/': ('403 403 403 403 200 200 200', '403 403 403 403 405 405 405'),
    '/api/pedidos/': ('403 200 200 403 403 403 403', '403 405 405 405 405 405 405'),
    '/api/pedidos/999999/seguimiento/': ('403 404 404 403 403 403 403', '403 405 405 405 405 405 405'),
    '/api/pedidos/999999/ruta/': ('403 404 404 403 403 403 403', '403 405 405 405 405 405 405'),
    '/carrito/': ('L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/carrito/agregar/': ('405 405 405 405 405 405 405', 'L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/carrito/actualizar/': ('405 405 405 405 405 405 405', 'L →/carrito/ →/carrito/ →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/carrito/repetir/': ('405 405 405 405 405 405 405', 'L →/carrito/ →/carrito/ →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/carrito/confirmar/': ('405 405 405 405 405 405 405', 'L →/carrito/ →/carrito/ →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/api/avisos/': ('403 200 200 403 403 403 403', '403 200 200 403 403 403 403'),
    '/avisos/': ('L 200 200 →/crm/ →/crm/ →/flota/ →/crm/', 'L 200 200 →/crm/ →/crm/ →/flota/ →/crm/'),
    '/avisos/pedir/': ('405 405 405 405 405 405 405', 'L →/avisos/ →/avisos/ →/crm/ →/crm/ →/flota/ →/crm/'),
    '/avisos/999999/quitar/': ('405 405 405 405 405 405 405', '→/avisos/ →/avisos/ →/avisos/ →/avisos/ →/avisos/ →/avisos/ →/avisos/'),
    '/seguimiento/': ('L →/pedidos/… →/pedidos/… →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L →/pedidos/… →/pedidos/… →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/pedidos/': ('L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/soporte/': ('L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L 200 200 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/pedidos/999999/': ('L 404 404 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L 404 404 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/pedidos/999999/oc/': ('405 405 405 405 405 405 405', 'L →/pedidos/… →/pedidos/… →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/pedidos/999999/entrega/': ('L 404 404 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/', 'L 404 404 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/pedidos/999999/cancelar/': ('405 405 405 405 405 405 405', 'L 404 404 →/catalogo/ →/catalogo/ →/catalogo/ →/catalogo/'),
    '/cuenta/entrar/': ('200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/', '200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/'),
    '/cuenta/registro/': ('200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/', '200 →/catalogo/ →/catalogo/ →/crm/ →/crm/ →/flota/ →/crm/'),
    '/cuenta/clave/': ('L 200 200 200 200 200 200', 'L 200 200 200 200 200 200'),
    '/cuenta/clave/hecho/': ('L 200 200 200 200 200 200', 'L 405 405 405 405 405 405'),
    '/salud/': ('200 200 200 200 200 200 200', '200 200 200 200 200 200 200'),
    '/admin/': ('L L L L L L 200', 'L L L L L L 200'),
}


def _rutas(resolver=None, prefijo=""):
    for p in (resolver or get_resolver()).url_patterns:
        if isinstance(p, URLResolver):
            yield from _rutas(p, prefijo + str(p.pattern))
        else:
            yield prefijo + str(p.pattern)


def _concreta(r):
    r = re.sub(r"<int:\w+>", "999999", r)
    r = re.sub(r"<str:\w+>", "NO-EXISTE", r)
    return "/" + r.lstrip("^").replace("$", "")


def rutas_del_proyecto():
    vistas = []
    for r in _rutas():
        url = _concreta(r)
        if url.startswith("/admin/") and url != "/admin/" or "salir" in url or re.search(r"[()\[\]?\\]", url) or url in vistas:
            continue
        vistas.append(url)
    return vistas


def _resultado(resp):
    if resp.status_code != 302:
        return str(resp.status_code)
    destino = resp["Location"]
    if "/cuenta/entrar/" in destino or "/admin/login" in destino:
        return "L"
    destino = destino.split("?")[0]
    if re.fullmatch(r"/pedidos/(\d+/)?", destino):
        return "→/pedidos/…"                    # «Seguir mi pedido»: a su último pedido, o a la lista si todavía no tiene
    return "→" + re.sub(r"/\d+/", "/N/", destino)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def cliente(self, rol):
        c = Client()
        if CUENTAS[rol]:
            self.assertTrue(c.login(username=CUENTAS[rol], password=CLAVE), rol)
        return c


class TablaDeRutas(Base):
    def test_toda_ruta_tiene_su_fila(self):
        sin_fila = [u for u in rutas_del_proyecto() if u not in ESPERADO]
        sobran = [u for u in ESPERADO if u not in rutas_del_proyecto()]
        self.assertEqual((sin_fila, sobran), ([], []), "agrega la ruta nueva a ESPERADO y a docs/rutas-y-roles.md decidiendo quién entra")

    def test_cada_rol_ve_lo_que_le_corresponde(self):
        fallas = []
        for rol in ROLES:
            c = self.cliente(rol)
            for url, (get, post) in ESPERADO.items():
                for metodo, esperado in (("get", get), ("post", post)):
                    kw = {"HTTP_X_REQUESTED_WITH": "fetch"} if metodo == "post" else {}
                    obtenido = _resultado(getattr(c, metodo)(url, **kw))
                    if obtenido != esperado.split()[ROLES.index(rol)]:
                        fallas.append(f"{rol} {metodo.upper()} {url}: {obtenido} (esperado {esperado.split()[ROLES.index(rol)]})")
        self.assertEqual(fallas, [])

    def test_el_documento_lista_todas_las_rutas(self):
        import os
        if not os.path.exists("../docs/rutas-y-roles.md"):
            self.skipTest("docs/rutas-y-roles.md no está en este checkout")
        texto = open("../docs/rutas-y-roles.md", encoding="utf-8").read()
        self.assertEqual([u for u in ESPERADO if f"`{u}`" not in texto], [])


class InicioPorRol(Base):
    def test_al_entrar_cada_cuenta_aterriza_en_su_inicio(self):
        for rol, destino in INICIO.items():
            r = Client().post("/cuenta/entrar/", {"username": CUENTAS[rol], "password": CLAVE})
            self.assertRedirects(r, destino, fetch_redirect_response=False, msg_prefix=rol)

    def test_con_sesion_la_raiz_lleva_al_inicio_y_la_portada_sigue_para_el_personal(self):
        for rol, destino in INICIO.items():
            c = self.cliente(rol)
            self.assertRedirects(c.get("/"), destino, fetch_redirect_response=False, msg_prefix=rol)
            self.assertEqual(c.get("/portada/").status_code, 200)
        self.assertEqual(Client().get("/").status_code, 200)                      # el visitante ve la portada

    def test_el_logo_lleva_al_inicio_de_la_cuenta(self):
        for rol, destino in INICIO.items():
            for url in ("/catalogo/", "/guia/", "/cuenta/clave/", "/crm/alertas/" if rol in ("vendedor", "gerencia", "despachador", "admin") else "/pedidos/"):
                html = self.cliente(rol).get(url).content.decode()
                self.assertIn(f'href="{destino}"', html, f"{rol} {url}")
                self.assertNotRegex(html, r'class="(tb-marca|marca)" href="/"', f"{rol} {url}")
        self.assertRegex(Client().get("/catalogo/").content.decode(), r'class="tb-marca" href="/"')

    def test_next_seguro_se_respeta_y_el_malicioso_no(self):
        def entrar(siguiente):
            return Client().post("/cuenta/entrar/?next=" + siguiente, {"username": CUENTAS["vendedor"], "password": CLAVE})["Location"]
        self.assertEqual(entrar("/crm/clientes/"), "/crm/clientes/")
        for malo in ("https://evil.example/", "//evil.example/", "/\\evil.example", "javascript:alert(1)", "http:evil.example"):
            self.assertEqual(entrar(malo), "/crm/", malo)

    def test_quien_ya_entro_no_se_queda_en_el_login_ni_en_bucles(self):
        c = self.cliente("vendedor")
        self.assertRedirects(c.get("/cuenta/entrar/?next=/avisos/"), "/crm/", fetch_redirect_response=False)
        self.assertRedirects(c.get("/avisos/"), "/crm/", fetch_redirect_response=False)


class MenuPorRol(Base):
    PROHIBIDOS = {   # enlaces del menú que darían 403/redirección a esa cuenta
        "B2B": ['href="/crm/', 'href="/flota/', 'href="/admin/', 'href="/demo/'],
        "B2C": ['href="/crm/', 'href="/flota/', 'href="/admin/', 'href="/demo/'],
        "vendedor": ['href="/flota/', 'href="/admin/', 'href="/demo/', 'href="/carrito/', 'href="/pedidos/', 'href="/soporte/', 'href="/avisos/', 'href="/seguimiento/', 'href="/catalogo/'],
        "gerencia": ['href="/flota/despachar/', 'href="/admin/', 'href="/demo/', 'href="/carrito/', 'href="/pedidos/', 'href="/soporte/', 'href="/avisos/', 'href="/seguimiento/', 'href="/catalogo/'],
        "despachador": ['href="/crm/embudo/', 'href="/crm/clientes/', 'href="/admin/', 'href="/demo/', 'href="/carrito/', 'href="/pedidos/', 'href="/soporte/', 'href="/avisos/', 'href="/seguimiento/', 'href="/catalogo/'],
    }

    def test_el_menu_no_ofrece_enlaces_que_dan_403(self):
        paginas = {"B2B": "/pedidos/", "B2C": "/pedidos/", "vendedor": "/crm/", "gerencia": "/crm/", "despachador": "/flota/"}
        for rol, enlaces in self.PROHIBIDOS.items():
            html = self.cliente(rol).get(paginas[rol]).content.decode()
            for e in enlaces:
                self.assertNotIn(e, html, f"{rol} ve {e}")

    def test_cada_rol_si_ve_lo_suyo(self):
        esperado = {"B2B": ('href="/pedidos/"', 'href="/carrito/"', 'href="/soporte/"', 'href="/avisos/"'), "vendedor": ('href="/crm/embudo/"', 'href="/crm/ia/"'),
                    "gerencia": ('href="/crm/embudo/"', 'href="/flota/"'), "despachador": ('href="/flota/"', 'href="/crm/alertas/"'),
                    "admin": ('href="/flota/"', 'href="/demo/"', 'href="/admin/"', 'href="/catalogo/"', 'href="/portada/"')}
        paginas = {"B2B": "/catalogo/", "vendedor": "/crm/", "gerencia": "/crm/", "despachador": "/flota/", "admin": "/crm/"}
        for rol, enlaces in esperado.items():
            html = self.cliente(rol).get(paginas[rol]).content.decode()
            for e in enlaces:
                self.assertIn(e, html, f"{rol} no ve {e}")

    def test_el_menu_interno_no_tiene_el_inicio_generico_con_sesion(self):
        html = self.cliente("admin").get("/crm/").content.decode()
        self.assertNotRegex(html, r'<a href="/" [^>]*>(<svg.*?</svg>)?Inicio</a>')
        self.assertNotIn(">Tienda</div>", self.cliente("vendedor").get("/crm/").content.decode())
        self.assertIn(">Tienda</div>", self.cliente("admin").get("/crm/").content.decode())

    def test_el_inicio_muestra_nombre_y_rol(self):
        for rol, etiqueta in (("vendedor", "Vendedor"), ("admin", "Administrador"), ("gerencia", "Gerencia")):
            html = self.cliente(rol).get("/crm/").content.decode()
            self.assertIn(CUENTAS[rol], html)
            self.assertIn(etiqueta, html)
        self.assertIn("Despachador", self.cliente("despachador").get("/flota/").content.decode())

    def test_el_administrador_tiene_accesos_directos(self):
        html = self.cliente("admin").get("/crm/").content.decode()
        self.assertIn('aria-label="Accesos directos del administrador"', html)
        for e in ('href="/flota/"', 'href="/demo/"', 'href="/admin/"', 'href="/catalogo/"'):
            self.assertIn(e, html)
        self.assertNotIn("Accesos directos del administrador", self.cliente("vendedor").get("/crm/").content.decode())

    def test_403_y_404_ofrecen_ir_a_mi_inicio(self):
        for rol in ("vendedor", "B2C", "despachador"):
            c = self.cliente(rol)
            forbidden = c.get("/demo/")
            self.assertIn(f'href="{INICIO[rol]}">Ir a mi inicio', forbidden.content.decode(), rol)
            self.assertIn(f'href="{INICIO[rol]}">Ir a mi inicio', c.get("/catalogo/999999/").content.decode(), rol)
        self.assertIn('href="/">Ir a mi inicio', Client().get("/catalogo/999999/").content.decode())

    def test_el_admin_de_django_es_solo_del_superusuario(self):
        for rol in ("vendedor", "gerencia", "despachador", "B2C"):
            self.assertEqual(_resultado(self.cliente(rol).get("/admin/")), "L", rol)
        self.assertEqual(self.cliente("admin").get("/admin/").status_code, 200)
