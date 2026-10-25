"""Pruebas de seguridad y de caídas controladas: lo que un atacante o un error de datos intentaría, y cómo responde el sistema.

Regla común: ante una entrada hostil o inexistente la respuesta es siempre controlada (302 al acceso, 400/403/404/405/429),
nunca un 500, nunca una traza y nunca un dato de otra cuenta.
"""
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import get_resolver

from catalogo.models import Producto
from clientes.models import Cliente
from crm.models import Prospecto, Requerimiento
from flota.models import Telemetria
from pedidos import servicios as s

CLAVE = "demo-cofrial-2026"
HOSTIL = ["' OR 1=1 --", "<script>alert(1)</script>", "../../etc/passwd", "%00", "9" * 400, "😈", "{{7*7}}", "\x00"]


class BaseSeguridad(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()                                   # los contadores de límite no se arrastran entre pruebas
        self.addCleanup(cache.clear)

    def entrar(self, usuario):
        c = Client(raise_request_exception=False)
        self.assertTrue(c.login(username=usuario, password=CLAVE))
        return c

    def anonimo(self):
        return Client(raise_request_exception=False)

    def sin_500(self, r, url):
        self.assertLess(r.status_code, 500, f"{url} respondió {r.status_code}")


# ---------------------------------------------------------------- 1. Quien no inició sesión no ve nada privado
class AccesoAnonimoTests(BaseSeguridad):
    PRIVADAS_GET = ["/crm/", "/crm/embudo/", "/crm/clientes/", "/crm/clientes/1/", "/crm/prospectos/1/", "/crm/prospectos/nuevo/",
                    "/crm/requerimientos/", "/crm/ia/", "/crm/demanda/", "/crm/alertas/", "/flota/", "/flota/despachar/",
                    "/carrito/", "/pedidos/", "/pedidos/1/", "/seguimiento/", "/soporte/", "/crm/requerimientos/1/", "/flota/sugerencias/",
                    "/flota/despachar/ruta/", "/demo/", "/pedidos/1/entrega/", "/cuenta/clave/", "/cuenta/clave/hecho/"]
    PRIVADAS_POST = ["/crm/prospectos/nuevo/", "/crm/prospectos/1/mover/", "/crm/prospectos/1/interaccion/", "/crm/clientes/1/interaccion/",
                     "/crm/clientes/1/pedido/", "/crm/requerimientos/1/ia/", "/crm/requerimientos/1/clasificar/", "/flota/despachar/",
                     "/flota/despachar/ubicar/1/", "/carrito/agregar/", "/carrito/actualizar/", "/carrito/repetir/", "/carrito/confirmar/",
                     "/pedidos/1/cancelar/", "/soporte/", "/flota/viajes/1/cerrar/", "/demo/pulso/", "/demo/apagar/", "/demo/limpiar/",
                     "/pedidos/1/oc/"]

    def test_las_pantallas_privadas_mandan_a_iniciar_sesion(self):
        for url in self.PRIVADAS_GET:
            with self.subTest(url=url):
                r = self.anonimo().get(url)
                self.assertEqual(r.status_code, 302, url)
                self.assertTrue(r["Location"].startswith("/cuenta/entrar/"), f"{url} -> {r['Location']}")

    def test_las_acciones_privadas_no_se_ejecutan_sin_sesion(self):
        for url in self.PRIVADAS_POST:
            with self.subTest(url=url):
                r = self.anonimo().post(url, {})
                self.assertIn(r.status_code, (302, 403), url)
                if r.status_code == 302:
                    self.assertTrue(r["Location"].startswith("/cuenta/entrar/"), f"{url} -> {r['Location']}")

    def test_la_api_no_responde_datos_sin_sesion(self):
        for url in ("/api/flota/", "/api/pedidos/", "/api/pedidos/1/seguimiento/"):
            with self.subTest(url=url):
                r = self.anonimo().get(url)
                self.assertEqual(r.status_code, 403)
                self.assertNotIn(b"orden_id", r.content)

    def test_cada_ruta_del_proyecto_esta_cubierta_o_es_publica(self):
        """Si alguien agrega una ruta nueva, esta prueba obliga a decidir si es pública o privada."""
        publicas = {"", "portada/", "guia/", "catalogo/", "catalogo/<int:producto_id>/", "cuenta/entrar/", "cuenta/registro/", "cuenta/salir/", "salud/",
                    "salud/bd/", "avisos/", "avisos/pedir/", "avisos/<int:aviso_id>/quitar/"}
        cubiertas = {u.strip("/") for u in self.PRIVADAS_GET + self.PRIVADAS_POST}
        pendientes = []
        for p in get_resolver().url_patterns:
            sub = getattr(p, "url_patterns", None)
            for q in (sub if sub is not None else [p]):
                ruta = (str(p.pattern) + str(q.pattern)) if sub is not None else str(p.pattern)
                if ruta.startswith(("admin", "static", "api/")) or ruta in publicas:
                    continue
                generica = ruta.replace("<int:pk>", "1").replace("<int:orden_id>", "1").replace("<int:direccion_id>", "1").replace("<int:despacho_id>", "1").strip("/")
                if generica not in cubiertas:
                    pendientes.append(ruta)
        self.assertEqual(pendientes, [], "Rutas sin prueba de acceso anónimo")


# ---------------------------------------------------------------- 2. Un rol no usa lo de otro
class SeparacionDeRolesTests(BaseSeguridad):
    def test_un_cliente_no_entra_a_crm_ni_flota_ni_api_de_flota(self):
        c = self.entrar("ana@correo.test")
        for url in ("/crm/", "/crm/clientes/", "/crm/ia/", "/flota/", "/flota/despachar/", "/crm/alertas/", "/crm/demanda/"):
            with self.subTest(url=url):
                self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(c.get("/api/flota/").status_code, 403)

    def test_el_personal_no_compra_como_cliente(self):
        c = self.entrar("vendedora@cofrial.cl")
        r = c.post("/carrito/agregar/", {"producto": Producto.objects.first().pk, "cantidad": 1})
        self.assertEqual(r.status_code, 403)                       # 403 claro, no una redirección con mensaje
        self.assertEqual(c.get("/api/pedidos/").status_code, 403)

    def test_el_despachador_no_toca_el_embudo_comercial(self):
        c = self.entrar("despacho@cofrial.cl")
        for url in ("/crm/embudo/", "/crm/clientes/", "/crm/prospectos/nuevo/", "/crm/requerimientos/", "/crm/ia/"):
            with self.subTest(url=url):
                self.assertEqual(c.get(url).status_code, 403)

    def test_un_cliente_no_puede_cancelar_ni_ver_la_orden_de_otro(self):
        ana = Cliente.objects.get(rut="12.345.678-5")
        s.agregar(ana, Producto.objects.first().pk, 1)
        orden = s.generar_orden(ana, ana.direccion_set.first().pk)
        c = self.entrar("abastecimiento@hospital.test")
        self.assertEqual(c.get(f"/pedidos/{orden.pk}/").status_code, 404)
        self.assertEqual(c.post(f"/pedidos/{orden.pk}/cancelar/").status_code, 404)
        self.assertEqual(c.get(f"/api/pedidos/{orden.pk}/seguimiento/").status_code, 404)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_orden.orden_flujo, 1)           # sigue como estaba

    def test_los_ids_mas_alla_de_lo_que_cabe_en_la_base_son_404_y_no_500(self):
        """`/pedidos/99999999999999999999/` desborda el entero de PostgreSQL: debe ser un 404 limpio."""
        c = self.entrar("abastecimiento@hospital.test")
        grande = "9" * 25
        for url in (f"/pedidos/{grande}/", f"/catalogo/{grande}/", f"/api/pedidos/{grande}/seguimiento/"):
            with self.subTest(url=url):
                self.assertEqual(c.get(url).status_code, 404)
        v = self.entrar("vendedora@cofrial.cl")
        for url in (f"/crm/clientes/{grande}/", f"/crm/prospectos/{grande}/"):
            with self.subTest(url=url):
                self.assertEqual(v.get(url).status_code, 404)


# ---------------------------------------------------------------- 3. 404 y rutas de escaneo
class PaginasNoEncontradasTests(BaseSeguridad):
    ESCANEO = ["/wp-admin/", "/wp-login.php", "/.env", "/.git/config", "/phpmyadmin/", "/administrator/", "/admin.php", "/config.php",
               "/backup.sql", "/server-status", "/actuator/health", "/api/v1/users/", "/static/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd",
               "/catalogo/abc/", "/pedidos/-1/", "/crm/clientes/0/", "/api/", "/api/usuarios/"]

    def test_las_rutas_de_escaneo_dan_404_con_pagina_propia(self):
        for url in self.ESCANEO:
            with self.subTest(url=url):
                r = self.anonimo().get(url)
                self.assertIn(r.status_code, (302, 400, 403, 404), url)
                self.assertNotContains(r, "Traceback", status_code=r.status_code)

    def test_el_404_no_revela_tecnologia_ni_rutas(self):
        r = self.anonimo().get("/no-existe/")
        self.assertEqual(r.status_code, 404)
        cuerpo = r.content.decode().lower()
        for pista in ("traceback", "urlconf", "you're seeing this", "debug = true", "settings.py"):
            self.assertNotIn(pista, cuerpo)
        self.assertIn("no encontramos", cuerpo)

    def test_el_404_funciona_tambien_con_sesion_de_cliente_y_de_personal(self):
        for usuario in ("ana@correo.test", "vendedora@cofrial.cl"):
            with self.subTest(usuario=usuario):
                self.assertEqual(self.entrar(usuario).get("/ruta/que/no/existe/").status_code, 404)

    def test_un_recurso_inexistente_y_uno_ajeno_responden_igual(self):
        """Quien sondea ids no puede distinguir «no existe» de «existe pero no es tuyo»."""
        ana = Cliente.objects.get(rut="12.345.678-5")
        s.agregar(ana, Producto.objects.first().pk, 1)
        ajena = s.generar_orden(ana, ana.direccion_set.first().pk)
        c = self.entrar("abastecimiento@hospital.test")
        a, b = c.get(f"/pedidos/{ajena.pk}/"), c.get("/pedidos/987654/")
        self.assertEqual(a.status_code, b.status_code)
        self.assertEqual(len(a.content), len(b.content))

    def test_el_producto_inactivo_no_se_ve(self):
        p = Producto.objects.first()
        Producto.objects.filter(pk=p.pk).update(activo=False)
        self.assertEqual(self.anonimo().get(f"/catalogo/{p.pk}/").status_code, 404)

    def test_el_panel_de_administracion_no_se_abre_a_un_cliente(self):
        r = self.entrar("ana@correo.test").get("/admin/")
        self.assertEqual(r.status_code, 302)                      # se le pide entrar como administrador: no ve el panel
        self.assertIn("/admin/login/", r["Location"])

    def test_el_personal_no_entra_al_admin_ni_a_sus_datos(self):
        """Vendedores, gerencia y despacho son `is_staff`, pero el admin de Django es solo del superusuario: se les pide entrar como administrador."""
        for usuario in ("vendedora@cofrial.cl", "despacho@cofrial.cl"):
            c = self.entrar(usuario)
            for url in ("/admin/", "/admin/clientes/cliente/", "/admin/auth/user/", "/admin/pedidos/orden/", "/admin/auth/user/add/"):
                with self.subTest(usuario=usuario, url=url):
                    r = c.get(url)
                    self.assertEqual(r.status_code, 302)
                    self.assertIn("/admin/login/", r["Location"])

    def test_el_admin_cambia_de_direccion_con_la_variable_de_entorno(self):
        """`DJANGO_ADMIN_URL` mueve el panel: la ruta conocida deja de existir y el menú apunta a la nueva."""
        from importlib import reload
        from django.test import override_settings
        from django.urls import clear_url_caches
        import cofrial.urls
        try:
            with override_settings(ADMIN_URL="panel-9f3k/"):
                reload(cofrial.urls)
                clear_url_caches()
                self.assertEqual(self.anonimo().get("/admin/").status_code, 404)
                self.assertEqual(self.anonimo().get("/panel-9f3k/").status_code, 302)
                self.assertContains(self.entrar("admin@cofrial.cl").get("/crm/"), 'href="/panel-9f3k/"')
        finally:
            reload(cofrial.urls)                  # deja las rutas como estaban para las demás pruebas
            clear_url_caches()


# ---------------------------------------------------------------- 4. Métodos, CSRF y redirecciones
class MetodosCsrfYRedireccionesTests(BaseSeguridad):
    def test_las_acciones_solo_aceptan_post(self):
        c = self.entrar("vendedora@cofrial.cl")
        for url in ("/crm/prospectos/1/mover/", "/crm/prospectos/1/interaccion/", "/crm/clientes/1/pedido/", "/crm/requerimientos/1/ia/"):
            with self.subTest(url=url):
                self.assertEqual(c.get(url).status_code, 405)
        k = self.entrar("ana@correo.test")
        for url in ("/carrito/agregar/", "/carrito/confirmar/", "/carrito/actualizar/", "/pedidos/1/cancelar/", "/avisos/pedir/"):
            with self.subTest(url=url):
                self.assertEqual(k.get(url).status_code, 405)

    def test_sin_token_csrf_los_post_se_rechazan(self):
        c = Client(enforce_csrf_checks=True, raise_request_exception=False)
        c.login(username="ana@correo.test", password=CLAVE)
        r = c.post("/carrito/agregar/", {"producto": Producto.objects.first().pk, "cantidad": 1})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(s.lineas(Cliente.objects.get(rut="12.345.678-5")), [])
        self.assertEqual(c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE}).status_code, 403)

    def test_volver_no_permite_enviar_a_un_sitio_externo(self):
        """Redirección abierta: `volver=https://malo.example` no debe sacar al usuario de la tienda."""
        c = self.entrar("ana@correo.test")
        producto = Producto.objects.filter(stock_disponible__gt=0).first()
        for destino in ("https://malo.example/", "//malo.example/", "http://malo.example", "javascript:alert(1)"):
            with self.subTest(destino=destino):
                r = c.post("/carrito/agregar/", {"producto": producto.pk, "cantidad": 1, "volver": destino})
                self.assertEqual(r.status_code, 302)
                self.assertNotIn("malo.example", r["Location"])
                self.assertFalse(r["Location"].lower().startswith("javascript"))

    def test_next_del_login_no_permite_sitios_externos(self):
        for destino in ("https://malo.example/", "//malo.example/"):
            with self.subTest(destino=destino):
                r = self.anonimo().post(f"/cuenta/entrar/?next={destino}", {"username": "ana@correo.test", "password": CLAVE})
                self.assertEqual(r.status_code, 302)
                self.assertNotIn("malo.example", r["Location"])

    def test_cerrar_sesion_exige_post(self):
        c = self.entrar("ana@correo.test")
        self.assertEqual(c.get("/cuenta/salir/").status_code, 405)
        self.assertEqual(c.get("/carrito/").status_code, 200)         # la sesión sigue viva
        c.post("/cuenta/salir/")
        self.assertEqual(c.get("/carrito/").status_code, 302)


# ---------------------------------------------------------------- 5. Entradas hostiles: ni 500 ni código inyectado
class EntradasHostilesTests(BaseSeguridad):
    def test_buscar_y_filtrar_el_catalogo_con_basura(self):
        c = self.anonimo()
        for texto in HOSTIL:
            for param in ("q", "categoria", "temperatura", "stock"):
                with self.subTest(param=param, texto=texto[:20]):
                    self.sin_500(c.get("/catalogo/", {param: texto}), "/catalogo/")

    def test_la_busqueda_no_ejecuta_html_del_visitante(self):
        r = self.anonimo().get("/catalogo/", {"q": "<script>alert(1)</script>"})
        self.assertNotContains(r, "<script>alert(1)</script>")

    def test_el_registro_con_basura_no_cae(self):
        c = self.anonimo()
        for texto in HOSTIL:
            with self.subTest(texto=texto[:20]):
                r = c.post("/cuenta/registro/", {"nombre": texto, "rut": texto, "email": texto, "direccion": texto, "comuna": texto,
                                                  "clave": texto, "clave2": texto})
                self.sin_500(r, "/cuenta/registro/")
                self.assertIn(r.status_code, (200, 400))           # vuelve al formulario con los errores (400 si trae un byte NUL)
        self.assertEqual(Cliente.objects.filter(nombre__contains="script").count(), 0)

    def test_el_login_con_basura_no_cae_ni_entra(self):
        c = self.anonimo()
        for texto in HOSTIL:
            with self.subTest(texto=texto[:20]):
                self.sin_500(c.post("/cuenta/entrar/", {"username": texto, "password": texto}), "/cuenta/entrar/")
                self.assertNotIn("_auth_user_id", c.session)

    def test_el_login_no_revela_si_el_correo_existe(self):
        c = self.anonimo()
        existe = c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": "mala"})
        no_existe = c.post("/cuenta/entrar/", {"username": "xyz@correo.test", "password": "mala"})      # mismo largo que el otro correo
        self.assertEqual(existe.status_code, no_existe.status_code)
        self.assertEqual(len(existe.content), len(no_existe.content))

    def test_el_carrito_con_cantidades_absurdas(self):
        c = self.entrar("ana@correo.test")
        producto = Producto.objects.filter(stock_disponible__gt=0).first()
        for cantidad in ("-5", "0", "abc", "", "1.5", "99999999999999999999", "²", " 3 ", "1e3"):
            for url in ("/carrito/agregar/", "/carrito/actualizar/"):
                with self.subTest(url=url, cantidad=cantidad):
                    self.sin_500(c.post(url, {"producto": producto.pk, "cantidad": cantidad}), url)

    def test_producto_inexistente_o_basura_en_el_carrito(self):
        c = self.entrar("ana@correo.test")
        for producto in ("0", "-1", "x", "", "9" * 30, "²"):
            with self.subTest(producto=producto):
                self.sin_500(c.post("/carrito/agregar/", {"producto": producto, "cantidad": 1}), "/carrito/agregar/")
                self.sin_500(c.post("/carrito/actualizar/", {"producto": producto, "cantidad": 1}), "/carrito/actualizar/")

    def test_confirmar_con_direccion_u_oc_hostil(self):
        c = self.entrar("abastecimiento@hospital.test")
        for valor in HOSTIL + ["²", "-1"]:
            with self.subTest(valor=valor[:20]):
                self.sin_500(c.post("/carrito/confirmar/", {"direccion": valor, "numero_oc": valor}), "/carrito/confirmar/")

    def test_soporte_con_referencias_hostiles(self):
        c = self.entrar("ana@correo.test")
        for ref in HOSTIL + ["²", "٣", "-1", "1e5"]:
            with self.subTest(ref=ref[:20]):
                self.sin_500(c.get("/soporte/", {"orden": ref}), "/soporte/")
                self.sin_500(c.post("/soporte/", {"orden": ref, "asunto": "x", "descripcion": "y" * 30}), "/soporte/")

    def test_el_texto_del_cliente_se_muestra_escapado_al_personal(self):
        c = self.entrar("ana@correo.test")
        c.post("/soporte/", {"asunto": "<img src=x onerror=alert(1)>", "descripcion": "<script>alert('xss')</script> la carga llegó tibia"})
        r = self.entrar("vendedora@cofrial.cl").get("/crm/requerimientos/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "<script>alert('xss')</script>")
        self.assertNotContains(r, "<img src=x onerror")

    def test_formularios_del_crm_con_basura(self):
        v = self.entrar("vendedora@cofrial.cl")
        for valor in HOSTIL + ["²", "-1"]:
            with self.subTest(valor=valor[:20]):
                self.sin_500(v.post("/crm/prospectos/nuevo/", {"nombre_contacto": valor, "email": valor, "telefono": valor, "monto": valor,
                                                                "origen": valor, "vendedor": valor}), "prospectos/nuevo")
                self.sin_500(v.post("/crm/requerimientos/1/clasificar/", {"categoria": valor}), "clasificar")
                self.sin_500(v.post("/crm/clientes/1/pedido/", {f"q_{valor}": valor, "direccion": valor}), "cliente/pedido")
                self.sin_500(v.post("/crm/clientes/1/interaccion/", {"tipo": valor, "detalle": valor}), "cliente/interaccion")
                self.sin_500(v.post("/crm/prospectos/1/mover/", {"etapa": valor, "motivo": valor, "rut": valor}), "prospecto/mover")
                self.sin_500(v.post("/crm/ia/", {"asunto": valor, "descripcion": valor}), "ia")

    def test_despacho_con_basura(self):
        d = self.entrar("despacho@cofrial.cl")
        for valor in HOSTIL + ["²", "-1"]:
            with self.subTest(valor=valor[:20]):
                self.sin_500(d.post("/flota/despachar/", {"camion": valor, "ordenes": [valor, "²", "1"]}), "/flota/despachar/")
        self.sin_500(d.post("/flota/despachar/ubicar/999999/"), "ubicar")

    def test_avisos_con_basura(self):
        c = self.entrar("ana@correo.test")
        for valor in HOSTIL + ["²", "-1"]:
            with self.subTest(valor=valor[:20]):
                self.sin_500(c.post("/avisos/pedir/", {"producto": valor, "cantidad": valor, "volver": valor}), "/avisos/pedir/")


# ---------------------------------------------------------------- 6. Configuración de producción
class ConfiguracionSeguraTests(TestCase):
    def test_la_depuracion_esta_apagada_por_defecto(self):
        self.assertFalse(settings.DEBUG)

    def test_las_cookies_de_sesion_no_se_leen_desde_javascript(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertIn(settings.SESSION_COOKIE_SAMESITE, ("Lax", "Strict"))
        self.assertIn(settings.CSRF_COOKIE_SAMESITE, ("Lax", "Strict"))

    def test_las_cabeceras_de_seguridad_estan_en_cada_respuesta(self):
        r = self.client.get("/")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn(r["X-Frame-Options"], ("DENY", "SAMEORIGIN"))
        self.assertIn("Referrer-Policy", r)

    def test_la_salud_no_filtra_detalles(self):
        self.assertEqual(self.client.get("/salud/").json(), {"estado": "ok"})


# ---------------------------------------------------------------- 7. Límites: quien insiste, se frena
class LimiteDeIntentosTests(BaseSeguridad):
    N = settings.ACCESO_MAX_FALLOS_USUARIO              # 10 por defecto (decisión B1)

    def fallar(self, c, usuario, veces, url="/cuenta/entrar/"):
        return [c.post(url, {"username": usuario, "password": "mala-clave-1"}).status_code for _ in range(veces)]

    def test_diez_claves_malas_bloquean_la_cuenta_incluso_con_la_clave_correcta(self):
        c = self.anonimo()
        self.assertEqual(self.fallar(c, "ana@correo.test", self.N), [200] * self.N)
        r = c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)
        self.assertNotIn("_auth_user_id", c.session)

    def test_el_bloqueo_de_una_cuenta_no_afecta_a_las_demas(self):
        c = self.anonimo()
        self.fallar(c, "ana@correo.test", self.N)
        self.assertEqual(self.anonimo().post("/cuenta/entrar/", {"username": "vendedora@cofrial.cl", "password": CLAVE}).status_code, 302)

    def test_entrar_bien_borra_los_fallos_anteriores(self):
        c = self.anonimo()
        self.fallar(c, "ana@correo.test", self.N - 1)
        self.assertEqual(c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE}).status_code, 302)
        self.assertEqual(self.fallar(self.anonimo(), "ana@correo.test", self.N - 1), [200] * (self.N - 1))         # el contador volvió a cero

    @override_settings(ACCESO_MAX_FALLOS_IP=20)
    def test_con_el_limite_por_ip_encendido_probar_muchas_cuentas_se_frena(self):
        c = self.anonimo()
        resultados = [c.post("/cuenta/entrar/", {"username": f"victima{i}@correo.test", "password": "x1y2z3w4"}).status_code for i in range(25)]
        self.assertEqual(resultados[:20], [200] * 20)
        self.assertEqual(set(resultados[20:]), {429})

    def test_el_login_del_admin_tiene_el_mismo_limite(self):
        c = self.anonimo()
        self.assertEqual(self.fallar(c, "admin@cofrial.cl", self.N, url="/admin/login/"), [200] * self.N)
        self.assertEqual(c.post("/admin/login/", {"username": "admin@cofrial.cl", "password": CLAVE}).status_code, 429)
        self.assertEqual(c.post("/cuenta/entrar/", {"username": "admin@cofrial.cl", "password": CLAVE}).status_code, 429)     # misma cuenta, misma puerta cerrada

    def test_el_bloqueo_se_levanta_cuando_pasa_la_ventana(self):
        c = self.anonimo()
        self.fallar(c, "ana@correo.test", self.N)
        cache.clear()                                      # equivale a que venzan los 15 minutos
        self.assertEqual(c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE}).status_code, 302)

    def test_la_pagina_de_bloqueo_no_revela_si_la_cuenta_existe(self):
        c = self.anonimo()
        self.fallar(c, "ana@correo.test", self.N)
        self.fallar(c, "inexistente@correo.test", self.N)
        a = c.post("/cuenta/entrar/", {"username": "ana@correo.test", "password": "x"})
        b = c.post("/cuenta/entrar/", {"username": "inexistente@correo.test", "password": "x"})
        self.assertEqual(a.status_code, 429)
        self.assertEqual((a.status_code, len(a.content)), (b.status_code, len(b.content)))

    def test_cada_ingreso_fallido_queda_en_el_registro(self):
        with self.assertLogs("cofrial.seguridad", level="WARNING") as log:
            self.fallar(self.anonimo(), "ana@correo.test", 1)
        self.assertIn("Ingreso fallido", log.output[0])
        self.assertNotIn("mala-clave", log.output[0])                  # nunca se escribe la clave

    @override_settings(CONFIAR_PROXY=True, ACCESO_MAX_FALLOS_IP=20)
    def test_detras_del_balanceador_se_cuenta_la_ip_real_y_no_la_del_balanceador(self):
        for i in range(20):
            self.anonimo().post("/cuenta/entrar/", {"username": f"v{i}@correo.test", "password": "x1y2z3w4"}, HTTP_X_FORWARDED_FOR=f"203.0.113.9, 10.0.0.{i}")
        bloqueada = self.anonimo().post("/cuenta/entrar/", {"username": "otro@correo.test", "password": "x"}, HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.77")
        self.assertEqual(bloqueada.status_code, 200)               # el último salto cambió: es otro cliente para el contador
        for i in range(20):
            self.anonimo().post("/cuenta/entrar/", {"username": f"w{i}@correo.test", "password": "x1y2z3w4"}, HTTP_X_FORWARDED_FOR="198.51.100.4")
        self.assertEqual(self.anonimo().post("/cuenta/entrar/", {"username": "z@correo.test", "password": "x"}, HTTP_X_FORWARDED_FOR="198.51.100.4").status_code, 429)

    @override_settings(ACCESO_MAX_FALLOS_IP=20)
    def test_sin_confiar_en_el_proxy_una_cabecera_falsa_no_evade_el_limite(self):
        for i in range(20):
            self.anonimo().post("/cuenta/entrar/", {"username": f"v{i}@correo.test", "password": "x1y2z3w4"}, HTTP_X_FORWARDED_FOR=f"1.2.3.{i}")
        r = self.anonimo().post("/cuenta/entrar/", {"username": "otro@correo.test", "password": "x"}, HTTP_X_FORWARDED_FOR="9.9.9.9")
        self.assertEqual(r.status_code, 429)

    def test_la_sala_detras_de_una_sola_ip_no_se_bloquea(self):
        """Decisión B1: en la defensa toda la sala sale por una IP pública. Muchas claves malas de cuentas distintas no cierran la puerta a los demás."""
        c = self.anonimo()
        resultados = [c.post("/cuenta/entrar/", {"username": f"alumno{i}@correo.test", "password": "x1y2z3w4"}).status_code for i in range(40)]
        self.assertEqual(resultados, [200] * 40)
        self.assertEqual(self.anonimo().post("/cuenta/entrar/", {"username": "ana@correo.test", "password": CLAVE}).status_code, 302)


class BarridoDeRutasTests(BaseSeguridad):
    M = settings.ESCANEO_MAX_404                        # 60 por defecto

    def test_pasado_el_umbral_de_no_encontrado_la_ip_queda_bloqueada_un_rato(self):
        c = self.anonimo()
        codigos = [c.get(f"/wp-admin/{i}").status_code for i in range(self.M + 5)]
        self.assertEqual(codigos[:self.M + 1], [404] * (self.M + 1))
        self.assertEqual(set(codigos[self.M + 1:]), {429})
        self.assertEqual(c.get("/catalogo/").status_code, 429)         # mientras dura el bloqueo no entra a nada

    def test_pasada_la_ventana_la_ip_vuelve_a_entrar(self):
        c = self.anonimo()
        for i in range(self.M + 5):
            c.get(f"/x/{i}")
        cache.clear()
        self.assertEqual(c.get("/catalogo/").status_code, 200)

    def test_el_uso_normal_no_se_acerca_al_limite(self):
        c = self.entrar("ana@correo.test")
        for _ in range(3):
            for url in ("/portada/", "/catalogo/", "/carrito/", "/pedidos/", "/soporte/", "/avisos/"):     # con sesión «/» redirige al inicio de la cuenta
                self.assertEqual(c.get(url).status_code, 200, url)
        self.assertEqual(c.get("/pedidos/999999/").status_code, 404)          # un enlace viejo ocasional es normal

    def test_el_barrido_queda_en_el_registro(self):
        c = self.anonimo()
        with self.assertLogs("cofrial.seguridad", level="WARNING") as log:
            for i in range(self.M + 2):
                c.get(f"/phpmyadmin/{i}")
        self.assertTrue(any("Barrido de rutas" in linea for linea in log.output))

    def test_otra_ip_no_sufre_el_bloqueo_de_la_primera(self):
        for i in range(self.M + 5):
            self.anonimo().get(f"/x/{i}")
        self.assertEqual(self.anonimo().get("/catalogo/", REMOTE_ADDR="198.51.100.77").status_code, 200)

    def test_un_recorrido_de_30_paginas_en_10_minutos_no_da_429(self):
        """Quien revisa el sitio en la defensa puede probar 30 direcciones (existan o no) desde la IP de la sala sin quedar bloqueado."""
        self.assertGreaterEqual(self.M, 30)
        c = self.anonimo()
        for i in range(30):
            self.assertEqual(c.get(f"/no-existe-{i}/").status_code, 404)
        for url in ("/", "/catalogo/", "/guia/", "/cuenta/entrar/"):
            self.assertEqual(c.get(url).status_code, 200, url)


class LimiteDeEnviosTests(BaseSeguridad):
    def test_el_registro_tiene_tope_por_hora_por_ip(self):
        c = self.anonimo()
        tope = settings.LIMITE_POST_POR_HORA["/cuenta/registro/"]
        codigos = [c.post("/cuenta/registro/", {"nombre": "x"}).status_code for _ in range(tope + 2)]
        self.assertEqual(codigos[:tope], [200] * tope)
        self.assertEqual(codigos[tope:], [429, 429])

    def test_soporte_tiene_tope_para_proteger_la_cuota_de_la_ia(self):
        c = self.entrar("ana@correo.test")
        tope = settings.LIMITE_POST_POR_HORA["/soporte/"]
        codigos = [c.post("/soporte/", {"asunto": "", "descripcion": ""}).status_code for _ in range(tope + 2)]
        self.assertEqual(codigos[:tope], [200] * tope)
        self.assertEqual(codigos[tope:], [429, 429])

    def test_una_consulta_enorme_se_rechaza_antes_de_llegar_a_la_ia(self):
        c = self.entrar("ana@correo.test")
        with mock.patch("crm.ia.clasificar") as ia:
            r = c.post("/soporte/", {"asunto": "Frío", "descripcion": "tibia " * 2000})
        ia.assert_not_called()
        self.assertContains(r, "admite hasta")


# ---------------------------------------------------------------- 8. Caídas controladas
class CaidasControladasTests(BaseSeguridad):
    def test_un_numero_que_no_cabe_en_la_columna_es_un_400_y_no_un_500(self):
        v = self.entrar("vendedora@cofrial.cl")
        r = v.post("/crm/prospectos/nuevo/", {"nombre_contacto": "A" * 500, "email": "a@b.cl", "origen": "web", "vendedor": ""})
        self.assertLess(r.status_code, 500)
        self.assertEqual(Prospecto.objects.filter(nombre_contacto__startswith="AAAA").count(), 0)

    def test_si_la_base_se_cae_a_media_peticion_se_responde_503_con_reintento(self):
        c = self.anonimo()
        with mock.patch("catalogo.views.Producto.objects") as m:
            m.filter.side_effect = OperationalError("connection refused")
            r = c.get("/catalogo/")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r["Retry-After"], "30")
        self.assertNotContains(r, "connection refused", status_code=503)
        self.assertContains(r, "Servicio no disponible", status_code=503)

    def test_si_la_base_esta_caida_desde_el_inicio_tambien_es_503(self):
        """La sesión, el menú y todo lo demás dependen de la base: la página de error no puede depender de ella."""
        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=OperationalError("could not connect to server")):
            r = self.anonimo().get("/catalogo/")
        self.assertEqual(r.status_code, 503)
        self.assertNotContains(r, "could not connect", status_code=503)

    def test_la_salud_simple_vive_aunque_la_base_no(self):
        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=OperationalError("down")):
            self.assertEqual(self.anonimo().get("/salud/").status_code, 200)

    def test_la_salud_con_base_avisa_503_si_no_la_alcanza(self):
        self.assertEqual(self.anonimo().get("/salud/bd/").json(), {"estado": "ok"})
        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=OperationalError("down")):
            r = self.anonimo().get("/salud/bd/")
        self.assertEqual((r.status_code, r.json()), (503, {"estado": "sin_base"}))

    def test_un_error_inesperado_muestra_una_pagina_propia_sin_traza(self):
        with mock.patch("catalogo.views.Producto.objects") as m:
            m.filter.side_effect = RuntimeError("secreto interno: DB_PASSWORD=hunter2")
            r = self.anonimo().get("/catalogo/")
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "Tuvimos un problema", status_code=500)
        for filtrado in ("secreto interno", "hunter2", "Traceback", "RuntimeError"):
            self.assertNotContains(r, filtrado, status_code=500)

    def test_el_token_csrf_vencido_muestra_una_pagina_clara(self):
        c = Client(enforce_csrf_checks=True, raise_request_exception=False)
        r = c.post("/cuenta/entrar/", {"username": "a", "password": "b"})
        self.assertContains(r, "Formulario vencido", status_code=403)
        self.assertNotContains(r, "CSRF", status_code=403)

    def test_la_ia_caida_no_impide_registrar_el_reclamo(self):
        from crm.ia import ErrorIA
        c = self.entrar("ana@correo.test")
        with mock.patch("crm.ia.clasificar", side_effect=ErrorIA("timeout")):
            r = c.post("/soporte/", {"asunto": "Frío", "descripcion": "La carga llegó tibia"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Requerimiento.objects.filter(asunto="Frío").count(), 1)

    def test_el_mapa_caido_no_impide_registrarse(self):
        from clientes.models import Comuna
        datos = {"nombre": "Pedro Pérez", "rut": "11.111.111-1", "email": "pedro@correo.test", "direccion": "Calle 1 100", "comuna": Comuna.objects.first().pk,
                 "clave": "una-clave-larga-9", "clave2": "una-clave-larga-9"}
        with override_settings(GEOCODIFICAR=True), mock.patch("urllib.request.urlopen", side_effect=OSError("sin red")):
            r = self.anonimo().post("/cuenta/registro/", datos)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Cliente.objects.filter(email="pedro@correo.test").exists())

    def test_sin_lecturas_de_telemetria_las_pantallas_no_caen(self):
        Telemetria.objects.all().delete()
        self.assertEqual(self.anonimo().get("/").status_code, 200)
        self.assertEqual(self.anonimo().get("/guia/").status_code, 200)
        d = self.entrar("despacho@cofrial.cl")
        self.assertEqual(d.get("/flota/").status_code, 200)
        self.assertEqual(d.get("/api/flota/").status_code, 200)

    def test_cantidades_fuera_de_rango_se_explican_y_no_cambian_el_carrito(self):
        c = self.entrar("ana@correo.test")
        p = Producto.objects.filter(stock_disponible__gt=0).first()
        r = c.post("/carrito/agregar/", {"producto": p.pk, "cantidad": "99999999999999999999"}, follow=True)
        self.assertContains(r, "Cantidad no válida")
        r = c.post("/carrito/agregar/", {"producto": p.pk, "cantidad": settings.CANTIDAD_MAXIMA_POR_LINEA + 1}, follow=True)
        self.assertContains(r, "cantidad máxima")
        c.post("/carrito/agregar/", {"producto": p.pk, "cantidad": settings.CANTIDAD_MAXIMA_POR_LINEA})
        r = c.post("/carrito/agregar/", {"producto": p.pk, "cantidad": 1}, follow=True)          # sumar una más pasaría el tope
        self.assertContains(r, "cantidad máxima")
        self.assertEqual(s.lineas(Cliente.objects.get(rut="12.345.678-5"))[0]["cantidad"], settings.CANTIDAD_MAXIMA_POR_LINEA)

    def test_clasificar_con_una_categoria_inexistente_no_la_guarda(self):
        ana = Cliente.objects.get(rut="12.345.678-5")
        r = Requerimiento.objects.create(cliente=ana, asunto="x", descripcion="y")
        v = self.entrar("vendedora@cofrial.cl")
        self.assertEqual(v.post(f"/crm/requerimientos/{r.pk}/clasificar/", {"categoria": "987654"}).status_code, 302)
        r.refresh_from_db()
        self.assertIsNone(r.categoria_requerimiento_id)


# ---------------------------------------------------------------- 9. Configuración
class ConfiguracionDeProduccionTests(TestCase):
    def test_el_modo_https_activa_cookies_seguras_y_hsts(self):
        """Con DJANGO_HTTPS=1 las cookies viajan solo por HTTPS y el navegador recuerda usar siempre HTTPS."""
        import importlib, os
        import cofrial.settings as ajustes
        anterior = os.environ.get("DJANGO_HTTPS")
        os.environ["DJANGO_HTTPS"] = "1"
        try:
            nuevos = importlib.reload(ajustes)
            self.assertTrue(nuevos.SESSION_COOKIE_SECURE and nuevos.CSRF_COOKIE_SECURE)
            self.assertGreaterEqual(nuevos.SECURE_HSTS_SECONDS, 31536000)
            self.assertEqual(nuevos.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        finally:
            if anterior is None:
                os.environ.pop("DJANGO_HTTPS", None)
            else:
                os.environ["DJANGO_HTTPS"] = anterior
            importlib.reload(ajustes)

    def test_los_limites_de_intentos_se_ajustan_por_entorno(self):
        """Decisión B1: por defecto 10 claves malas por cuenta y sin límite por IP; ambos (y el barrido de 404) se cambian por variable de entorno."""
        import importlib, os
        import cofrial.settings as ajustes
        self.assertEqual((settings.ACCESO_MAX_FALLOS_USUARIO, settings.ACCESO_MAX_FALLOS_IP), (10, 0))
        variables = {"ACCESO_MAX_FALLOS_CUENTA": "7", "ACCESO_MAX_FALLOS_IP": "50", "ESCANEO_MAX_404": "90", "ESCANEO_VENTANA_SEG": "300"}
        anteriores = {k: os.environ.get(k) for k in variables}
        os.environ.update(variables)
        try:
            nuevos = importlib.reload(ajustes)
            self.assertEqual((nuevos.ACCESO_MAX_FALLOS_USUARIO, nuevos.ACCESO_MAX_FALLOS_IP, nuevos.ESCANEO_MAX_404, nuevos.ESCANEO_VENTANA_SEG),
                             (7, 50, 90, 300))
        finally:
            for k, v in anteriores.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(ajustes)

    def test_sin_https_las_cookies_siguen_funcionando_en_http_de_demostracion(self):
        self.assertFalse(settings.SESSION_COOKIE_SECURE)

    def test_la_cabecera_x_frame_options_impide_incrustar_el_sitio(self):
        self.assertEqual(self.client.get("/").headers["X-Frame-Options"], "DENY")

    def test_el_sitio_no_acepta_mas_campos_de_los_razonables(self):
        self.assertLessEqual(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 1000)
        r = self.client.post("/cuenta/entrar/", {f"c{i}": "x" for i in range(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS + 5)})
        self.assertEqual(r.status_code, 400)

    def test_los_hosts_se_pueden_restringir_por_entorno(self):
        with override_settings(ALLOWED_HOSTS=["cofrial.example"]):
            self.assertEqual(self.client.get("/salud/", HTTP_HOST="malo.example").status_code, 400)
            self.assertEqual(self.client.get("/salud/", HTTP_HOST="cofrial.example").status_code, 200)
