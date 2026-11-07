"""Operación del administrador: reponer stock, crear cuentas y dar clave a cuentas existentes."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from catalogo import avisos
from catalogo.models import AvisoStock, Producto
from clientes import cuentas_demo
from clientes.models import Cliente, Comuna, Vendedor
from cofrial.acceso import tipo_de
from crm import servicios as crm
from operacion import servicios as s

CLAVE = "demo-cofrial-2026"            # la fija cargar_demo en las pruebas (sin DEMO_PASSWORD)
NUEVA = "Op3ra-cion-9x2-clave"         # clave de prueba que pasa los validadores

Usuario = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario="admin@cofrial.cl", **kw):
        c = Client(**kw)
        self.assertTrue(c.login(username=usuario, password=CLAVE), usuario)
        return c

    def producto(self, stock):
        p = Producto.objects.filter(activo=True).first()
        Producto.objects.filter(pk=p.pk).update(stock_disponible=stock)
        return p


class ReponerStock(Base):
    def sumar(self, c, p, cantidad, **extra):
        return c.post(f"/operacion/stock/{p.pk}/sumar/", {"cantidad": cantidad, **extra})

    def test_suma_al_stock_actual_en_vez_de_reemplazarlo(self):
        p = self.producto(10)
        r = self.sumar(self.entrar(), p, 25)
        self.assertRedirects(r, "/operacion/stock/", fetch_redirect_response=False)
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 35)

    def test_la_suma_es_relativa_aunque_el_stock_cambie_mientras_el_formulario_estaba_abierto(self):
        """El formulario de /admin/ escribe un número absoluto y pisa la venta que ocurrió mientras tanto; aquí se suma sobre lo que hay."""
        p = self.producto(10)
        c = self.entrar()
        c.get("/operacion/stock/")                                                 # la pantalla muestra 10
        Producto.objects.filter(pk=p.pk).update(stock_disponible=4)                # entretanto se vendieron 6
        self.sumar(c, p, 5)
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 9)                                    # 4 + 5; un valor absoluto habría dejado 15

    def test_el_mensaje_dice_cuanto_stock_hay_ahora(self):
        p = self.producto(0)
        r = self.sumar(self.entrar(), p, 7, q="")
        self.assertContains(self.entrar().get("/operacion/stock/"), "7")
        self.assertIn(f"{p.nombre} ahora tiene 7", " ".join(m.message for m in r.wsgi_request._messages))

    def test_rechaza_cantidades_no_validas_sin_tocar_el_stock(self):
        p = self.producto(10)
        c = self.entrar()
        for malo in ("0", "-3", "1.5", "1,5", "abc", "", " ", "²", "٣", "100001", "99999999999999999999", "1e3", "+5"):
            with self.subTest(cantidad=malo):
                r = self.sumar(c, p, malo)
                self.assertRedirects(r, "/operacion/stock/", fetch_redirect_response=False)
                self.assertIn("cantidad entera entre 1 y 100.000", " ".join(m.message for m in r.wsgi_request._messages))
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 10)

    def test_el_limite_de_una_reposicion_si_pasa(self):
        p = self.producto(0)
        self.sumar(self.entrar(), p, 100000)
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 100000)

    def test_no_deja_pasar_el_maximo_de_la_base(self):
        p = self.producto(2_147_483_600)
        with self.assertRaises(s.ErrorOperacion):
            s.reponer(p.pk, 100)
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 2_147_483_600)
        r = self.sumar(self.entrar(), p, 100)
        self.assertEqual(r.status_code, 302)                                      # mensaje de error, no un 500

    def test_producto_inexistente_da_404_y_get_da_405(self):
        c = self.entrar()
        self.assertEqual(c.post("/operacion/stock/999999/sumar/", {"cantidad": 5}).status_code, 404)
        self.assertEqual(c.get(f"/operacion/stock/{self.producto(1).pk}/sumar/").status_code, 405)

    def test_la_busqueda_filtra_por_sku_y_por_nombre_y_conserva_el_filtro_al_sumar(self):
        c = self.entrar()
        p = Producto.objects.first()
        r = c.get("/operacion/stock/", {"q": p.sku})
        self.assertContains(r, p.nombre)
        self.assertNotContains(r, Producto.objects.exclude(pk=p.pk).first().sku)
        self.assertEqual(list(r.context["filas"]), [p])
        self.assertContains(c.get("/operacion/stock/", {"q": "zzz-no-existe"}), "Ningún producto coincide")
        r = c.post(f"/operacion/stock/{p.pk}/sumar/", {"cantidad": 1, "q": p.sku})
        self.assertEqual(r["Location"], f"/operacion/stock/?q={p.sku}")

    def test_la_busqueda_no_rompe_con_caracteres_raros(self):
        c = self.entrar()
        for q in ("%", "_", "'", '"; DROP TABLE producto;--', "ñ" * 200, "<script>"):
            self.assertEqual(c.get("/operacion/stock/", {"q": q}).status_code, 200, repr(q))

    def test_requiere_token_csrf(self):
        p = self.producto(10)
        c = self.entrar(enforce_csrf_checks=True)
        self.assertEqual(self.sumar(c, p, 5).status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.stock_disponible, 10)
        self.assertContains(c.get("/operacion/stock/"), "csrfmiddlewaretoken")

    def test_los_avisos_de_stock_se_activan_al_reponer(self):
        p = self.producto(0)
        ana = Cliente.objects.get(rut="12.345.678-5")
        avisos.pedir(ana, p.pk, 20)
        self.assertEqual(avisos.cuantos_disponibles(ana), 0)
        self.sumar(self.entrar(), p, 10)                                           # todavía no alcanza
        self.assertEqual(avisos.cuantos_disponibles(ana), 0)
        r = self.sumar(self.entrar(), p, 10)
        self.assertEqual(avisos.cuantos_disponibles(ana), 1)
        self.assertIn("1 aviso de clientes ya se pueden atender", " ".join(m.message for m in r.wsgi_request._messages))
        cliente = self.entrar("ana@correo.test")
        self.assertContains(cliente.get("/avisos/"), p.nombre)
        self.assertEqual(AvisoStock.objects.filter(atendido_en__isnull=True).count(), 1)     # sigue pendiente hasta que lo agregue al carrito

    def test_la_demanda_enlaza_a_reponer_solo_al_administrador(self):
        p = self.producto(0)
        avisos.pedir(Cliente.objects.get(rut="12.345.678-5"), p.pk, 5)
        enlace = f'href="/operacion/stock/?q={p.sku}"'
        self.assertContains(self.entrar().get("/crm/demanda/"), enlace)
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl"):
            self.assertNotContains(self.entrar(usuario).get("/crm/demanda/"), "/operacion/", msg_prefix=usuario)
        self.assertContains(self.entrar().get(f"/operacion/stock/?q={p.sku}"), p.nombre)


class CrearCuenta(Base):
    def crear(self, c=None, **datos):
        base = {"usuario": "nuevo@t.test", "rol": "gerencia", "clave": NUEVA, "clave2": NUEVA}
        return (c or self.entrar()).post("/operacion/cuentas/nueva/", {**base, **datos})

    def test_cada_rol_queda_con_el_acceso_que_le_corresponde_y_entra_con_su_clave(self):
        vendedora = Vendedor.objects.get(usuario__username="vendedora@cofrial.cl")
        casos = [("jefa@t.test", "vendedor", {"nombre": "Camila Soto"}, "vendedor"), ("gte@t.test", "gerencia", {}, "gerencia"),
                 ("des@t.test", "despachador", {}, "despachador"), ("adm@t.test", "admin", {}, "admin"),
                 ("b2b@t.test", "cliente-b2b", {"nombre": "Hotel Villarrica", "rut": "76.111.222-8", "direccion": "Av. Pedro de Valdivia 100",
                                                "comuna": Comuna.objects.get(nombre="Temuco").pk, "vendedor": vendedora.pk}, "cliente-b2b"),
                 ("b2c@t.test", "cliente-b2c", {"nombre": "Ana Díaz", "rut": "11.222.333-9", "direccion": "Calle 1 123",
                                                "comuna": Comuna.objects.get(nombre="Temuco").pk}, "cliente-b2c")]
        for usuario, rol, extra, esperado in casos:
            with self.subTest(rol=rol):
                r = self.crear(usuario=usuario, rol=rol, **extra)
                self.assertRedirects(r, "/operacion/cuentas/", fetch_redirect_response=False)
                u = Usuario.objects.get(username=usuario)
                self.assertTrue(u.check_password(NUEVA))
                self.assertEqual(s.rol_de(Usuario.objects.get(pk=u.pk)), esperado)
                self.assertTrue(Client().login(username=usuario, password=NUEVA))
        b2b = Cliente.objects.get(rut="76.111.222-8")
        self.assertEqual((b2b.tipo_cliente.codigo, b2b.vendedor, b2b.direccion_set.count()), ("B2B", vendedora, 1))
        self.assertEqual(Cliente.objects.get(rut="11.222.333-9").tipo_cliente.codigo, "B2C")
        self.assertIsNone(crm.rol(b2b.usuario))                                   # un cliente no entra al CRM
        self.assertTrue(Usuario.objects.get(username="adm@t.test").is_superuser)
        self.assertFalse(Usuario.objects.get(username="b2c@t.test").is_staff)

    def test_el_usuario_se_guarda_en_minusculas(self):
        self.crear(usuario="  Gte.Nuevo@T.Test ")
        self.assertTrue(Usuario.objects.filter(username="gte.nuevo@t.test").exists())

    def test_errores_claros_y_nada_queda_a_medias(self):
        antes = (Usuario.objects.count(), Cliente.objects.count(), Vendedor.objects.count())
        temuco = Comuna.objects.get(nombre="Temuco").pk
        cliente = {"rol": "cliente-b2c", "nombre": "Ana", "rut": "11.222.333-9", "direccion": "Calle 1", "comuna": temuco}
        casos = [({"usuario": "admin@cofrial.cl"}, "ya existe"), ({"usuario": "ADMIN@cofrial.cl"}, "ya existe"),
                 ({"usuario": "con espacio@t.test"}, "usuario"), ({"usuario": ""}, "Este campo es requerido"),
                 ({"rol": "cliente-b2c", "nombre": "", "rut": "", "direccion": ""}, "Indica el RUT"),
                 ({**cliente, "rut": "11.222.333-4"}, "dígito verificador"), ({**cliente, "rut": "12.345.678-5"}, "Ya existe un cliente con el RUT"),
                 ({"rol": "vendedor", "nombre": ""}, "Indica el nombre del vendedor"), ({"rol": "inventado"}, "Escoja una opción"),
                 ({"clave": "1234", "clave2": "1234"}, "demasiado corta"), ({"clave": NUEVA, "clave2": NUEVA + "x"}, "no coinciden"),
                 ({"clave": "password", "clave2": "password"}, "demasiado común")]
        c = self.entrar()
        for datos, texto in casos:
            with self.subTest(datos=datos):
                r = self.crear(c, **datos)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, texto)
                self.assertFalse(r.context["form"].is_valid())
        self.assertEqual((Usuario.objects.count(), Cliente.objects.count(), Vendedor.objects.count()), antes)

    def test_la_clave_nunca_vuelve_en_la_pagina_ni_en_la_url_ni_en_los_registros(self):
        c = self.entrar()
        with self.assertLogs("cofrial.operacion", level="INFO") as registro:
            r = self.crear(c, usuario="otra@t.test")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn(NUEVA, r["Location"])
        self.assertNotIn(NUEVA, " ".join(registro.output))
        self.assertNotIn(NUEVA, c.get("/operacion/cuentas/").content.decode())
        r = self.crear(c, usuario="otra@t.test", clave2="distinta-de-la-otra")      # con errores el formulario no devuelve las claves
        self.assertNotContains(r, NUEVA)
        self.assertNotContains(r, "distinta-de-la-otra")
        self.assertContains(r, 'type="password"')
        self.assertNotRegex(r.content.decode(), r'type="password"[^>]*value=')

    def test_requiere_token_csrf(self):
        c = self.entrar(enforce_csrf_checks=True)
        self.assertEqual(self.crear(c, usuario="sin-csrf@t.test").status_code, 403)
        self.assertFalse(Usuario.objects.filter(username="sin-csrf@t.test").exists())

    def test_el_formulario_se_abre_con_los_campos_de_cada_rol(self):
        r = self.entrar().get("/operacion/cuentas/nueva/")
        for texto in ('name="usuario"', 'name="rol"', 'name="rut"', 'name="vendedor"', 'name="clave2"', "Cliente institucional (B2B)", "Despachador"):
            self.assertContains(r, texto)
        self.assertEqual(r.context["form"]["comuna"].value(), Comuna.objects.get(nombre="Temuco").pk)


class DarClave(Base):
    def asignar(self, c, usuario, clave=NUEVA, clave2=None):
        u = Usuario.objects.get(username=usuario)
        return c.post(f"/operacion/cuentas/{u.pk}/clave/", {"clave": clave, "clave2": clave2 or clave})

    def test_la_lista_busca_por_usuario_nombre_y_rut_y_muestra_el_rol(self):
        c = self.entrar()
        r = c.get("/operacion/cuentas/")
        for usuario in ("admin@cofrial.cl", "ana@correo.test", "despacho@cofrial.cl"):
            self.assertContains(r, usuario)
        self.assertEqual(len(c.get("/operacion/cuentas/", {"q": "hospital regional"}).context["cuentas"]), 1)
        self.assertEqual(len(c.get("/operacion/cuentas/", {"q": "12.345.678"}).context["cuentas"]), 1)
        self.assertEqual(len(c.get("/operacion/cuentas/", {"q": "supermercados"}).context["cuentas"]), 0)      # esa empresa no tiene cuenta de acceso
        self.assertEqual([x["u"].username for x in c.get("/operacion/cuentas/", {"q": "vendedor2"}).context["cuentas"]], ["vendedor2@cofrial.cl"])
        self.assertContains(c.get("/operacion/cuentas/", {"q": "zzz-no-existe"}), "Ninguna cuenta coincide")

    def test_el_rol_de_la_lista_coincide_con_el_del_resto_del_sistema(self):
        for u in s.cuentas_con_rol():
            esperado = crm.rol(u) or ("cliente" if hasattr(u, "cliente") else "personal" if u.is_staff else "sin rol")
            rol = s.rol_de(u)
            self.assertEqual(rol.split("-")[0] if rol.startswith("cliente") else rol, esperado, u.username)
            self.assertEqual(tipo_de(u), "cliente" if rol.startswith("cliente") else rol if rol != "sin rol" else "anonimo", u.username)

    def test_asigna_la_clave_nueva_y_la_vieja_deja_de_servir(self):
        c = self.entrar()
        r = self.asignar(c, "ana@correo.test")
        self.assertRedirects(r, "/operacion/cuentas/", fetch_redirect_response=False)
        self.assertNotIn(NUEVA, r["Location"])
        self.assertTrue(Client().login(username="ana@correo.test", password=NUEVA))
        self.assertFalse(Client().login(username="ana@correo.test", password=CLAVE))
        u = Usuario.objects.get(username="ana@correo.test")
        self.assertNotEqual(u.password, NUEVA)                                     # se guarda con hash, no en claro
        self.assertTrue(u.password.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt")))

    def test_valida_la_clave_y_no_cambia_nada_si_no_sirve(self):
        c = self.entrar()
        antes = Usuario.objects.get(username="ana@correo.test").password
        for clave, clave2, texto in (("1234", "1234", "demasiado corta"), ("password", "password", "demasiado común"), 
                                     (NUEVA, NUEVA + "x", "no coinciden"), ("", "", "Este campo es requerido")):
            with self.subTest(clave=clave):
                r = self.asignar(c, "ana@correo.test", clave, clave2)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, texto)
                self.assertNotContains(r, NUEVA)
        self.assertEqual(Usuario.objects.get(username="ana@correo.test").password, antes)
        self.assertTrue(Client().login(username="ana@correo.test", password=CLAVE))

    def test_la_clave_no_aparece_en_la_respuesta_ni_en_los_registros(self):
        c = self.entrar()
        with self.assertLogs("cofrial.operacion", level="INFO") as registro:
            r = self.asignar(c, "ana@correo.test")
        self.assertNotIn(NUEVA, " ".join(registro.output))
        self.assertIn("ana@correo.test", " ".join(registro.output))
        self.assertNotContains(c.get(r["Location"]), NUEVA)
        mala = self.asignar(c, "ana@correo.test", "corta", "corta")
        self.assertNotContains(mala, "corta</")                                    # el campo de clave no devuelve lo escrito
        self.assertNotRegex(mala.content.decode(), r'type="password"[^>]*value=')

    def test_requiere_token_csrf(self):
        c = self.entrar(enforce_csrf_checks=True)
        self.assertEqual(self.asignar(c, "ana@correo.test").status_code, 403)
        self.assertTrue(Client().login(username="ana@correo.test", password=CLAVE))

    def test_el_administrador_no_pierde_el_acceso_al_cambiar_su_propia_clave(self):
        c = self.entrar()
        self.assertRedirects(self.asignar(c, "admin@cofrial.cl"), "/operacion/cuentas/", fetch_redirect_response=False)
        self.assertEqual(c.get("/operacion/").status_code, 200)                    # la sesión sigue abierta
        u = Usuario.objects.get(username="admin@cofrial.cl")
        self.assertTrue(u.is_active and u.is_superuser and u.is_staff)
        self.assertTrue(Client().login(username="admin@cofrial.cl", password=NUEVA))
        self.assertContains(c.get("/operacion/cuentas/"), "Tú")

    def test_la_pantalla_no_ofrece_desactivar_ni_quitar_el_rol(self):
        """El administrador solo cambia claves aquí: el formulario no trae campos de activo, superusuario ni grupos."""
        u = Usuario.objects.get(username="admin@cofrial.cl")
        r = self.entrar().get(f"/operacion/cuentas/{u.pk}/clave/")
        self.assertEqual(list(r.context["form"].fields), ["clave", "clave2"])
        c = self.entrar()
        c.post(f"/operacion/cuentas/{u.pk}/clave/", {"clave": NUEVA, "clave2": NUEVA, "is_active": "", "is_superuser": "", "is_staff": ""})
        u.refresh_from_db()
        self.assertTrue(u.is_active and u.is_superuser)

    def test_una_cuenta_inactiva_sigue_inactiva(self):
        Usuario.objects.filter(username="felipe@cofrial.cl").update(is_active=False)
        u = Usuario.objects.get(username="felipe@cofrial.cl")
        self.assertContains(self.entrar().get(f"/operacion/cuentas/{u.pk}/clave/"), "inactiva")
        self.asignar(self.entrar(), "felipe@cofrial.cl")
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.assertTrue(u.check_password(NUEVA))

    def test_cuenta_inexistente_da_404(self):
        self.assertEqual(self.entrar().get("/operacion/cuentas/999999/clave/").status_code, 404)

    def test_las_cuentas_de_la_defensa_siguen_con_su_clave_derivada_y_la_asignada_no_se_pisa(self):
        """cargar_demo corre en cada arranque: con DEMO_PASSWORD cada cuenta tiene su clave propia y una clave asignada aquí no se pisa."""
        with patch.dict(os.environ, {"DEMO_PASSWORD": "base-de-la-defensa-2026", "ADMIN_PASSWORD": ""}):
            call_command("cambiar_clave_demo")
            propias = {u: cuentas_demo.clave_de(u, "base-de-la-defensa-2026") for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl")}
            c = Client()
            self.assertTrue(c.login(username="admin@cofrial.cl", password=cuentas_demo.clave_de("admin@cofrial.cl", "base-de-la-defensa-2026")))
            self.asignar(c, "ana@correo.test")
            self.crear_cuenta_extra(c)
            call_command("cargar_demo", verbosity=0)                               # un arranque más
            self.assertTrue(Client().login(username="ana@correo.test", password=NUEVA))
            for usuario, clave in propias.items():
                self.assertTrue(Client().login(username=usuario, password=clave), usuario)
            self.assertTrue(Client().login(username="admin@cofrial.cl", password=cuentas_demo.clave_de("admin@cofrial.cl", "base-de-la-defensa-2026")))
            self.assertTrue(Client().login(username="extra@t.test", password=NUEVA))

    def crear_cuenta_extra(self, c):
        r = c.post("/operacion/cuentas/nueva/", {"usuario": "extra@t.test", "rol": "gerencia", "clave": NUEVA, "clave2": NUEVA})
        self.assertEqual(r.status_code, 302)


class UsuariosPorTipo(Base):
    """Pantalla Usuarios: una tarjeta por tipo con su cantidad y su botón Agregar, tabla filtrable y formulario por tipo."""
    TIPOS = ("cliente-b2b", "cliente-b2c", "vendedor", "gerencia", "despachador", "admin")

    def test_hay_una_tarjeta_por_tipo_con_su_cantidad_y_su_boton_agregar(self):
        r = self.entrar().get("/operacion/cuentas/")
        tarjetas = {t["rol"]: t["n"] for t in r.context["tarjetas"]}
        self.assertEqual(list(tarjetas), list(self.TIPOS))
        self.assertEqual(tarjetas, {"cliente-b2b": 5, "cliente-b2c": 2, "vendedor": 2, "gerencia": 1, "despachador": 1, "admin": 2})   # las cuentas de la demo
        self.assertEqual(sum(tarjetas.values()) + r.context["otros"], Usuario.objects.count())
        for rol in self.TIPOS:
            self.assertContains(r, f'href="/operacion/cuentas/nueva/?tipo={rol}"')
            self.assertContains(r, f'href="?tipo={rol}')

    def test_las_cantidades_cuentan_las_cuentas_nuevas(self):
        c = self.entrar()
        c.post("/operacion/cuentas/nueva/?tipo=despachador", {"usuario": "des2@t.test", "clave": NUEVA, "clave2": NUEVA})
        tarjetas = {t["rol"]: t["n"] for t in c.get("/operacion/cuentas/").context["tarjetas"]}
        self.assertEqual(tarjetas["despachador"], 2)

    def test_filtra_por_tipo_y_la_busqueda_sigue_funcionando_junto(self):
        c = self.entrar()
        r = c.get("/operacion/cuentas/", {"tipo": "vendedor"})
        self.assertEqual(sorted(x["u"].username for x in r.context["cuentas"]), ["vendedor2@cofrial.cl", "vendedora@cofrial.cl"])
        self.assertEqual([t["rol"] for t in r.context["tarjetas"] if t["activa"]], ["vendedor"])
        self.assertContains(r, "Asignar clave")
        r = c.get("/operacion/cuentas/", {"tipo": "vendedor", "q": "vendedor2"})
        self.assertEqual([x["u"].username for x in r.context["cuentas"]], ["vendedor2@cofrial.cl"])
        self.assertEqual({t["rol"]: t["n"] for t in r.context["tarjetas"]}["vendedor"], 2)         # los conteos no dependen de la búsqueda
        self.assertEqual(c.get("/operacion/cuentas/", {"tipo": "gerencia", "q": "vendedor"}).context["cuentas"], [])
        self.assertEqual({x["rol"] for x in c.get("/operacion/cuentas/", {"tipo": "cliente-b2c"}).context["cuentas"]}, {"Cliente particular (B2C)"})

    def test_un_tipo_que_no_existe_se_ignora(self):
        c = self.entrar()
        for malo in ("inventado", "admin' OR 1=1", "<script>", "personal", "sin rol", "../../", ""):
            r = c.get("/operacion/cuentas/", {"tipo": malo})
            self.assertEqual(r.status_code, 200, malo)
            self.assertEqual(r.context["tipo"], "", malo)
            self.assertEqual(len(r.context["cuentas"]), Usuario.objects.count(), malo)
            r = c.get("/operacion/cuentas/nueva/", {"tipo": malo})
            self.assertEqual(r.status_code, 200, malo)
            self.assertEqual(r.context["tipo"], "", malo)

    def test_el_formulario_pide_solo_los_campos_de_cada_tipo(self):
        c = self.entrar()
        esperados = {"cliente-b2b": ["nombre", "rut", "direccion", "comuna", "vendedor", "clave", "clave2"],
                     "cliente-b2c": ["nombre", "rut", "direccion", "comuna", "clave", "clave2"],
                     "vendedor": ["nombre", "clave", "clave2"], "gerencia": ["nombre", "clave", "clave2"],
                     "despachador": ["nombre", "clave", "clave2"], "admin": ["nombre", "clave", "clave2"]}
        for rol, campos in esperados.items():
            with self.subTest(rol=rol):
                r = c.get("/operacion/cuentas/nueva/", {"tipo": rol})
                self.assertEqual([n for n in r.context["form"].fields if n not in ("usuario", "rol")], campos)
                self.assertContains(r, f'name="rol" value="{rol}"')
                for campo in ("rut", "direccion", "vendedor"):
                    self.assertEqual(f'name="{campo}"' in r.content.decode(), campo in campos, campo)

    def test_con_tipo_en_la_url_el_rol_es_ese_aunque_el_formulario_diga_otro(self):
        """Un POST manipulado no puede crear un administrador desde la pantalla de otro tipo."""
        r = self.entrar().post("/operacion/cuentas/nueva/?tipo=gerencia", {"usuario": "falso@t.test", "rol": "admin", "clave": NUEVA, "clave2": NUEVA})
        self.assertRedirects(r, "/operacion/cuentas/?tipo=gerencia", fetch_redirect_response=False)
        u = Usuario.objects.get(username="falso@t.test")
        self.assertFalse(u.is_superuser)
        self.assertEqual(s.rol_de(Usuario.objects.get(pk=u.pk)), "gerencia")

    def test_crear_un_cliente_desde_su_tarjeta(self):
        c = self.entrar()
        temuco = Comuna.objects.get(nombre="Temuco").pk
        r = c.post("/operacion/cuentas/nueva/?tipo=cliente-b2b", {"usuario": "compras@hotel.test", "nombre": "Hotel Villarrica", "rut": "76.111.222-8",
                                                                  "direccion": "Av. Pedro de Valdivia 100", "comuna": temuco, "clave": NUEVA, "clave2": NUEVA})
        self.assertRedirects(r, "/operacion/cuentas/?tipo=cliente-b2b", fetch_redirect_response=False)
        self.assertEqual(Cliente.objects.get(rut="76.111.222-8").tipo_cliente.codigo, "B2B")
        r = c.post("/operacion/cuentas/nueva/?tipo=cliente-b2c", {"usuario": "x@t.test", "nombre": "X", "clave": NUEVA, "clave2": NUEVA})
        self.assertEqual(r.status_code, 200)                                                    # sin RUT ni dirección no se crea
        self.assertContains(r, "Indica el RUT")
        self.assertFalse(Usuario.objects.filter(username="x@t.test").exists())

    def test_el_acceso_se_encuentra_sin_buscarlo(self):
        r = self.entrar().get("/operacion/")
        self.assertContains(r, 'href="/operacion/cuentas/"')
        self.assertContains(r, "Ver usuarios y agregar")
        panel = self.entrar().get("/crm/")
        self.assertContains(panel, 'href="/operacion/cuentas/"')
        self.assertContains(panel, "Accesos directos del administrador")
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl"):
            self.assertNotContains(self.entrar(usuario).get("/crm/"), "/operacion/", msg_prefix=usuario)


class ClienteSinCuenta(Base):
    """Un cliente ganado (nace en el CRM sin cuenta del portal) debe poder ingresar sin duplicarlo."""

    def cliente_ganado(self):
        from clientes.models import Direccion, TipoCliente
        c = Cliente.objects.create(tipo_cliente=TipoCliente.objects.get(codigo="B2B"), vendedor=Vendedor.objects.first(), rut="76.111.222-8",
                                   nombre="Hotel Villarrica", email="Compras@Hotel.test")
        Direccion.objects.create(cliente=c, calle_numero="Av. Pedro de Valdivia 100", comuna=Comuna.objects.get(nombre="Temuco"), es_principal=True)
        return c

    def crear(self, c, cliente, **datos):
        return c.post(f"/operacion/clientes/{cliente.pk}/cuenta/", {"usuario": "compras@hotel.test", "clave": NUEVA, "clave2": NUEVA, **datos})

    def test_se_crea_la_cuenta_enlazada_al_cliente_existente_sin_duplicarlo(self):
        from pedidos import servicios as pedidos
        cliente = self.cliente_ganado()
        total, direcciones = Cliente.objects.count(), cliente.direccion_set.count()
        r = self.crear(self.entrar(), cliente)
        self.assertRedirects(r, f"/crm/clientes/{cliente.pk}/", fetch_redirect_response=False)
        cliente.refresh_from_db()
        self.assertEqual(cliente.usuario.username, "compras@hotel.test")
        self.assertEqual((Cliente.objects.count(), cliente.direccion_set.count()), (total, direcciones))           # el mismo cliente
        self.assertEqual(pedidos.cliente_de(cliente.usuario), cliente)
        self.assertIsNone(crm.rol(cliente.usuario))                                  # entra al portal, no al CRM
        self.assertFalse(cliente.usuario.is_staff)
        cli = Client()
        self.assertTrue(cli.login(username="compras@hotel.test", password=NUEVA))
        self.assertEqual(cli.get("/catalogo/").status_code, 200)
        self.assertEqual(cli.get("/pedidos/").status_code, 200)

    def test_la_pantalla_ofrece_el_correo_del_cliente_y_la_ficha_el_boton(self):
        cliente = self.cliente_ganado()
        c = self.entrar()
        r = c.get(f"/operacion/clientes/{cliente.pk}/cuenta/")
        self.assertEqual(r.context["form"].initial["usuario"], "compras@hotel.test")
        self.assertContains(r, "Hotel Villarrica")
        self.assertContains(c.get(f"/crm/clientes/{cliente.pk}/"), f'href="/operacion/clientes/{cliente.pk}/cuenta/"')
        self.assertContains(c.get("/crm/clientes/"), f'href="/operacion/clientes/{cliente.pk}/cuenta/"')
        self.assertContains(c.get("/operacion/cuentas/"), f'href="/operacion/clientes/{cliente.pk}/cuenta/"')
        self.assertIn(cliente, c.get("/operacion/cuentas/").context["sin_cuenta"])
        for usuario in ("vendedora@cofrial.cl", "gerencia@cofrial.cl"):
            ficha = self.entrar(usuario).get(f"/crm/clientes/{cliente.pk}/")
            self.assertNotContains(ficha, "/operacion/", msg_prefix=usuario)

    def test_despues_de_crearla_el_boton_desaparece_y_no_se_puede_repetir(self):
        cliente = self.cliente_ganado()
        c = self.entrar()
        self.crear(c, cliente)
        self.assertNotContains(c.get(f"/crm/clientes/{cliente.pk}/"), "Crear cuenta del portal")
        self.assertContains(c.get(f"/crm/clientes/{cliente.pk}/"), "compras@hotel.test")
        usuarios = Usuario.objects.count()
        r = self.crear(c, cliente, usuario="otra@hotel.test")
        self.assertRedirects(r, f"/crm/clientes/{cliente.pk}/", fetch_redirect_response=False)
        self.assertEqual(Usuario.objects.count(), usuarios)
        cliente.refresh_from_db()
        self.assertEqual(cliente.usuario.username, "compras@hotel.test")

    def test_valida_usuario_y_clave_y_no_deja_nada_a_medias(self):
        cliente = self.cliente_ganado()
        c = self.entrar()
        usuarios = Usuario.objects.count()
        for datos, texto in (({"usuario": "ana@correo.test"}, "ya existe"), ({"usuario": "ANA@correo.test"}, "ya existe"), ({"usuario": "con espacio"}, "usuario"),
                             ({"clave": "1234", "clave2": "1234"}, "demasiado corta"), ({"clave2": NUEVA + "x"}, "no coinciden"), ({"usuario": ""}, "requerido")):
            with self.subTest(datos=datos):
                r = self.crear(c, cliente, **datos)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, texto)
                self.assertNotContains(r, NUEVA)
        self.assertEqual(Usuario.objects.count(), usuarios)
        cliente.refresh_from_db()
        self.assertIsNone(cliente.usuario)

    def test_la_clave_no_se_muestra_ni_se_registra(self):
        cliente = self.cliente_ganado()
        c = self.entrar()
        with self.assertLogs("cofrial.operacion", level="INFO") as registro:
            r = self.crear(c, cliente)
        self.assertNotIn(NUEVA, r["Location"])
        self.assertNotIn(NUEVA, " ".join(registro.output))
        self.assertFalse(Client().login(username="compras@hotel.test", password=CLAVE))

    def test_requiere_csrf_y_cliente_inexistente_da_404(self):
        cliente = self.cliente_ganado()
        self.assertEqual(self.crear(self.entrar(enforce_csrf_checks=True), cliente).status_code, 403)
        cliente.refresh_from_db()
        self.assertIsNone(cliente.usuario)
        self.assertEqual(self.entrar().get("/operacion/clientes/999999/cuenta/").status_code, 404)

    def test_un_cliente_que_ya_tiene_cuenta_no_cambia(self):
        ana = Cliente.objects.get(rut="12.345.678-5")
        r = self.entrar().get(f"/operacion/clientes/{ana.pk}/cuenta/")
        self.assertRedirects(r, f"/crm/clientes/{ana.pk}/", fetch_redirect_response=False)
