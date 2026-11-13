"""Información legal y derechos del titular: páginas públicas, casilla de términos con constancia, descarga y eliminación de datos."""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from datetime import date, datetime

from clientes.models import AceptacionLegal, Cliente, Comuna, Direccion, SolicitudDerecho
from cofrial import legal
from pedidos.models import EstadoOrden, Orden

CLAVE = "una-clave-larga-92"


class PaginasLegales(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_las_paginas_son_publicas_y_dicen_lo_que_importa(self):
        esperado = {"privacidad": ["Ley N.º 21.719", "Amazon Web Services", "Seis años", "Mis datos"],
                    "terminos": ["Cancelaciones", "no garantizamos un porcentaje de disponibilidad"],
                    "devoluciones": ["derecho de retracto", "nota de crédito"],
                    "cookies": ["sessionid", "csrftoken", "AWSALB", "no usa cookies de publicidad"],
                    "licencias": ["OpenStreetMap", "SIL Open Font License", "generadas con IA"]}
        for nombre, textos in esperado.items():
            with self.subTest(nombre=nombre):
                r = self.client.get(f"/legal/{nombre}/")
                self.assertEqual(r.status_code, 200)
                for t in textos:
                    self.assertContains(r, t)

    def test_una_pagina_que_no_existe_da_404(self):
        self.assertEqual(self.client.get("/legal/otra/").status_code, 404)

    def test_el_pie_enlaza_lo_legal_y_trae_el_aviso_de_cookies(self):
        r = self.client.get("/portada/")
        for enlace in ("/legal/privacidad/", "/legal/terminos/", "/legal/devoluciones/", "/legal/cookies/", "/legal/licencias/"):
            self.assertContains(r, f'href="{enlace}"')
        self.assertContains(r, 'id="aviso-cookies"')
        self.assertContains(r, "js/aviso-cookies.js")


class SinTope(TestCase):
    """El registro tiene tope por hora por IP en la caché del proceso: se limpia antes y después para no gastarle el cupo a otras pruebas."""
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()


class CasillaDeTerminos(SinTope):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def datos(self, **cambios):
        return {"nombre": "Luis Mora", "rut": "11.111.111-1", "email": "luis@correo.test", "telefono": "", "direccion": "Calle 1 123",
                "comuna": Comuna.objects.get(nombre="Temuco").pk, "clave": CLAVE, "clave2": CLAVE, **cambios}

    def test_la_casilla_parte_sin_marcar(self):
        r = self.client.get("/cuenta/registro/")
        self.assertContains(r, 'name="acepta"')
        self.assertNotContains(r, 'name="acepta" checked')
        self.assertContains(r, 'href="/legal/terminos/"')

    def test_sin_aceptar_no_se_crea_la_cuenta(self):
        r = self.client.post("/cuenta/registro/", self.datos())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "tienes que aceptar los términos")
        self.assertFalse(get_user_model().objects.filter(username="luis@correo.test").exists())

    def test_al_aceptar_queda_constancia_de_quien_cuando_version_e_ip(self):
        r = self.client.post("/cuenta/registro/", self.datos(acepta="on"), REMOTE_ADDR="190.5.6.7")
        self.assertEqual(r.status_code, 302)
        a = AceptacionLegal.objects.get(usuario__username="luis@correo.test")
        self.assertEqual((a.version, a.ip), (legal.VERSION, "190.5.6.7"))
        self.assertIsNotNone(a.aceptado_en)

    def test_la_empresa_tambien_deja_constancia(self):
        r = self.client.post("/cuenta/registro/empresa/", self.datos(email="compras@hotel.test", rut="77.123.456-9", giro="Hotelería", acepta="on"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(AceptacionLegal.objects.filter(usuario__username="compras@hotel.test", version=legal.VERSION).exists())


class MisDatos(SinTope):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        super().setUp()
        self.client.post("/cuenta/registro/", {"nombre": "Luis Mora", "rut": "11.111.111-1", "email": "luis@correo.test", "telefono": "4512345",
                                                "direccion": "Calle 1 123", "comuna": Comuna.objects.get(nombre="Temuco").pk,
                                                "clave": CLAVE, "clave2": CLAVE, "acepta": "on"})
        self.cliente = Cliente.objects.get(email="luis@correo.test")
        self.client.login(username="luis@correo.test", password=CLAVE)

    def orden(self, estado):
        return Orden.objects.create(direccion=self.cliente.direccion_set.first(), estado_orden=EstadoOrden.objects.get(nombre=estado))

    def test_la_pagina_muestra_la_cuenta_y_la_aceptacion(self):
        r = self.client.get("/cuenta/mis-datos/")
        self.assertContains(r, "11.111.111-1")
        self.assertContains(r, f"Versión {legal.VERSION}")
        self.assertContains(r, 'action="/cuenta/mis-datos/eliminar/"')

    def test_la_descarga_trae_todo_en_json(self):
        o = self.orden("Entregada")
        r = self.client.get("/cuenta/mis-datos/descargar/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        d = json.loads(r.content)
        self.assertEqual(d["cliente"]["rut"], "11.111.111-1")
        self.assertEqual(d["direcciones"][0]["direccion"], "Calle 1 123")
        self.assertEqual([p["orden"] for p in d["pedidos"]], [o.orden_id])
        self.assertEqual(d["aceptaciones_de_terminos"][0]["version"], legal.VERSION)

    def test_con_la_clave_equivocada_no_se_elimina(self):
        self.client.post("/cuenta/mis-datos/eliminar/", {"clave": "otra"})
        self.assertTrue(get_user_model().objects.get(username="luis@correo.test").is_active)

    def test_con_pedidos_en_curso_no_se_elimina(self):
        self.orden("Recibida")
        self.client.post("/cuenta/mis-datos/eliminar/", {"clave": CLAVE})
        self.assertTrue(get_user_model().objects.get(username="luis@correo.test").is_active)

    def test_una_cuenta_de_demostracion_no_se_elimina(self):
        with mock.patch.object(legal, "CUENTAS_DEMO", ["luis@correo.test"]):
            self.client.post("/cuenta/mis-datos/eliminar/", {"clave": CLAVE})
        self.assertTrue(get_user_model().objects.get(username="luis@correo.test").is_active)

    def test_eliminar_borra_lo_personal_y_conserva_lo_tributario(self):
        o = self.orden("Entregada")
        u = get_user_model().objects.get(username="luis@correo.test")
        r = self.client.post("/cuenta/mis-datos/eliminar/", {"clave": CLAVE})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        u.refresh_from_db()
        self.cliente.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertFalse(u.has_usable_password())
        self.assertNotIn("luis", u.username + u.email + self.cliente.email)
        self.assertEqual((self.cliente.nombre, self.cliente.telefono, self.cliente.rut), ("Cuenta eliminada", "", "11.111.111-1"))
        self.assertEqual(Direccion.objects.get(cliente=self.cliente).calle_numero, "(dirección eliminada)")
        self.assertTrue(Orden.objects.filter(pk=o.pk).exists())
        self.assertTrue(AceptacionLegal.objects.filter(usuario=u).exists())
        self.assertFalse(self.client.login(username="luis@correo.test", password=CLAVE))
        self.assertEqual(self.client.get("/cuenta/mis-datos/").status_code, 302)       # la sesión se cerró


class SolicitudesDeDerechos(SinTope):
    """Ley 21.719: rectificación, oposición y bloqueo (y la supresión del equipo) por solicitud, con número, plazo y respuesta."""
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        for u in get_user_model().objects.filter(username__in=["ana@correo.test", "vendedora@cofrial.cl", "admin@cofrial.cl", "despacho@cofrial.cl"]):
            u.set_password(CLAVE); u.save()

    def entrar(self, usuario):
        self.client.login(username=usuario, password=CLAVE)

    def pedir(self, tipo="rectificacion", detalle="Mi teléfono correcto es +56 9 1234 5678."):
        return self.client.post("/cuenta/mis-datos/solicitar/", {"tipo": tipo, "detalle": detalle})

    def test_el_cliente_pide_una_rectificacion_y_ve_su_plazo(self):
        self.entrar("ana@correo.test")
        r = self.pedir()
        self.assertRedirects(r, "/cuenta/mis-datos/#md-solicitudes", fetch_redirect_response=False)
        x = SolicitudDerecho.objects.get(usuario__username="ana@correo.test")
        self.assertEqual((x.tipo, x.estado), ("rectificacion", "recibida"))
        self.assertEqual((x.vence_el - x.creada_en.date()).days, 30)
        r = self.client.get("/cuenta/mis-datos/")
        self.assertContains(r, f"N.º {x.solicitud_id} · Rectificación")
        self.assertContains(r, x.vence_el.strftime("%d/%m/%Y"))

    def test_no_se_duplica_ni_acepta_un_tipo_ajeno_o_un_texto_vacio(self):
        self.entrar("ana@correo.test")
        self.pedir(); self.pedir()                                          # doble clic
        self.pedir(tipo="supresion")                                        # el cliente la resuelve con el botón, no por solicitud
        self.pedir(tipo="oposicion", detalle="corto")
        self.assertEqual(SolicitudDerecho.objects.count(), 1)

    def test_el_equipo_tiene_mis_datos_en_el_menu_lateral_y_puede_pedir_la_supresion(self):
        self.entrar("vendedora@cofrial.cl")
        r = self.client.get("/cuenta/mis-datos/")
        self.assertTemplateUsed(r, "cuenta/mis_datos_equipo.html")
        self.assertContains(r, 'href="/cuenta/mis-datos/" aria-current="page"')
        self.assertContains(r, "María Paz Soto")
        self.assertNotContains(r, 'action="/cuenta/mis-datos/eliminar/"')
        self.pedir(tipo="supresion", detalle="Dejé la empresa: borren mi ficha de vendedora.")
        self.assertTrue(SolicitudDerecho.objects.filter(usuario__username="vendedora@cofrial.cl", tipo="supresion").exists())
        d = json.loads(self.client.get("/cuenta/mis-datos/descargar/").content)
        self.assertEqual(d["cuenta"]["rol"], "vendedor")
        self.assertEqual(d["ficha_de_vendedor"]["nombre"], "María Paz Soto")
        self.assertEqual(d["solicitudes_sobre_mis_datos"][0]["tipo"], "Supresión")

    def test_el_administrador_responde_y_el_titular_ve_la_respuesta(self):
        self.entrar("ana@correo.test"); self.pedir(); self.client.logout()
        x = SolicitudDerecho.objects.get()
        self.entrar("admin@cofrial.cl")
        self.assertContains(self.client.get("/operacion/privacidad/"), f"N.º {x.solicitud_id} · Rectificación")
        aviso = self.client.get("/api/avisos-equipo/").json()["avisos"]
        self.assertIn("datos_personales", [a["id"] for a in aviso])
        self.client.post(f"/operacion/privacidad/{x.pk}/responder/", {"respuesta": "Listo: actualizamos tu teléfono."})
        x.refresh_from_db()
        self.assertEqual((x.estado, x.atendida_por.username), ("respondida", "admin@cofrial.cl"))
        self.client.logout(); self.entrar("ana@correo.test")
        self.assertContains(self.client.get("/cuenta/mis-datos/"), "Listo: actualizamos tu teléfono.")

    def test_la_prorroga_es_una_sola_vez_y_no_aplica_al_bloqueo(self):
        self.entrar("ana@correo.test"); self.pedir(); self.pedir(tipo="bloqueo", detalle="Suspendan el uso mientras corrigen mi teléfono."); self.client.logout()
        rect, bloq = SolicitudDerecho.objects.get(tipo="rectificacion"), SolicitudDerecho.objects.get(tipo="bloqueo")
        self.entrar("admin@cofrial.cl")
        self.client.post(f"/operacion/privacidad/{rect.pk}/prorrogar/"); self.client.post(f"/operacion/privacidad/{rect.pk}/prorrogar/")
        self.client.post(f"/operacion/privacidad/{bloq.pk}/prorrogar/")
        rect.refresh_from_db(); bloq.refresh_from_db()
        self.assertEqual((rect.vence_el - rect.creada_en.date()).days, 60)
        self.assertFalse(bloq.prorrogada)

    def test_otros_roles_no_ven_ni_responden_solicitudes(self):
        self.entrar("ana@correo.test"); self.pedir(); self.client.logout()
        x = SolicitudDerecho.objects.get()
        for u in ("vendedora@cofrial.cl", "despacho@cofrial.cl"):
            self.entrar(u)
            self.assertEqual(self.client.get("/operacion/privacidad/").status_code, 403)
            self.assertEqual(self.client.post(f"/operacion/privacidad/{x.pk}/responder/", {"respuesta": "No debería poder."}).status_code, 403)
            self.client.logout()
        x.refresh_from_db()
        self.assertEqual(x.estado, "recibida")

    def test_el_bloqueo_vence_en_dos_dias_habiles(self):
        x = SolicitudDerecho(tipo="bloqueo", creada_en=timezone.make_aware(datetime(2026, 11, 20, 10)))     # viernes
        self.assertEqual(x.vence_el, date(2026, 11, 24))                                                   # martes: salta el fin de semana
