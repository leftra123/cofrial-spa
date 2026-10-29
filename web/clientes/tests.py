from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes import cuentas_demo
from clientes.cuentas_demo import clave_de
from clientes.models import Cliente
from crm import servicios as crm
from pedidos import servicios as pedidos

CLAVE_NUEVA = "clave-segura-2026"


class CuentasTests(TestCase):
    """Herramientas para crear cuentas y rotar la clave de demostración."""

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def crear(self, *args, clave=CLAVE_NUEVA, **kw):
        with patch.dict("os.environ", {"CUENTA_CLAVE": clave}):
            call_command("crear_cuenta", *args, **kw)

    def entra(self, usuario, clave=CLAVE_NUEVA):
        self.client.logout()
        return self.client.login(username=usuario, password=clave)

    def test_cada_rol_queda_con_el_acceso_que_le_corresponde(self):
        casos = {"jefa@t.test": ("vendedor", {"nombre": "Camila Soto"}, "vendedor"), "gte@t.test": ("gerencia", {}, "gerencia"),
                 "des@t.test": ("despachador", {}, "despachador"), "adm@t.test": ("admin", {}, "admin")}
        for usuario, (rol, extra, esperado) in casos.items():
            self.crear(usuario, rol=rol, **extra)
            u = get_user_model().objects.get(username=usuario)
            self.assertEqual(crm.rol(u), esperado, usuario)
            self.assertTrue(self.entra(usuario), usuario)

    def test_cliente_b2b_con_direccion_y_vendedor(self):
        self.crear("compras@hotel.test", rol="cliente-b2b", nombre="Hotel Villarrica", rut="76.111.222-3", direccion="Av. Pedro de Valdivia 100",
                   vendedor="vendedora@cofrial.cl")
        c = Cliente.objects.get(rut="76.111.222-3")
        self.assertEqual((c.tipo_cliente.codigo, c.vendedor.usuario.username, c.direccion_set.count()), ("B2B", "vendedora@cofrial.cl", 1))
        self.assertIsNone(crm.rol(c.usuario))                       # un cliente no entra al CRM
        self.assertEqual(pedidos.cliente_de(c.usuario), c)           # pero sí compra en el portal
        self.assertTrue(self.entra("compras@hotel.test"))

    def test_cliente_b2c(self):
        self.crear("ana2@t.test", rol="cliente-b2c", nombre="Ana Díaz", rut="11.222.333-4", direccion="Calle 1 123")
        self.assertEqual(Cliente.objects.get(rut="11.222.333-4").tipo_cliente.codigo, "B2C")

    def test_errores_claros_y_sin_efectos_a_medias(self):
        usuarios = get_user_model().objects.count()
        with self.assertRaisesMessage(CommandError, "ya existe"):
            self.crear("admin@cofrial.cl", rol="admin")
        with self.assertRaisesMessage(CommandError, "necesita --nombre, --rut y --direccion"):
            self.crear("x@t.test", rol="cliente-b2c", nombre="X")
        with self.assertRaisesMessage(CommandError, "comuna"):
            self.crear("x@t.test", rol="cliente-b2c", nombre="X", rut="9.999.999-9", direccion="Calle 1", comuna="Inexistente")
        with self.assertRaisesMessage(CommandError, "vendedor"):
            self.crear("x@t.test", rol="cliente-b2b", nombre="X", rut="9.999.999-9", direccion="Calle 1", vendedor="nadie@t.test")
        with self.assertRaisesMessage(CommandError, "Clave no válida"):
            self.crear("x@t.test", rol="gerencia", clave="1234")
        with self.assertRaisesMessage(CommandError, "Ya existe un cliente con el RUT"):
            self.crear("y@t.test", rol="cliente-b2c", nombre="Y", rut="12.345.678-5", direccion="Calle 2")
        self.assertEqual(get_user_model().objects.count(), usuarios)    # nada quedó creado

    def test_cambiar_clave_demo_permite_entrar_con_la_nueva_y_no_con_la_vieja(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": CLAVE_NUEVA}):
            call_command("cambiar_clave_demo")
        for u in ("admin@cofrial.cl", "ana@correo.test", "vendedora@cofrial.cl", "despacho@cofrial.cl"):
            self.assertTrue(self.entra(u, clave=clave_de(u, CLAVE_NUEVA)), u)          # cada cuenta con su clave propia
            self.assertFalse(self.entra(u), u)                                         # la base no sirve como clave
        self.assertFalse(self.entra("ana@correo.test", clave="demo-cofrial-2026"))

    def test_cambiar_clave_demo_no_toca_cuentas_ajenas_ni_actua_sin_clave_si_se_pide(self):
        self.crear("otra@t.test", rol="gerencia")
        with patch.dict("os.environ", {"DEMO_PASSWORD": "otra-clave-larga-9"}):
            call_command("cambiar_clave_demo")
        self.assertTrue(self.entra("otra@t.test"))                   # su clave no cambió
        with patch.dict("os.environ", {}, clear=True):
            call_command("cambiar_clave_demo", "--si-hay-clave")      # sin variable no hace nada ni falla
        self.assertTrue(self.entra("ana@correo.test", clave=clave_de("ana@correo.test", "otra-clave-larga-9")))

    def test_clave_debil_se_rechaza_salvo_que_se_pida_expresamente(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "12345678"}):
            with self.assertRaisesMessage(CommandError, "permitir-clave-debil"):
                call_command("cambiar_clave_demo")
            self.assertTrue(self.entra("ana@correo.test", clave="demo-cofrial-2026"))      # no cambió nada al rechazarla
            call_command("cambiar_clave_demo", "--permitir-clave-debil", "--misma")
        for u in ("admin@cofrial.cl", "ana@correo.test", "abastecimiento@hospital.test", "vendedora@cofrial.cl", "vendedor2@cofrial.cl",
                  "gerencia@cofrial.cl", "despacho@cofrial.cl"):
            self.assertTrue(self.entra(u, clave="12345678"), u)


class RegistroB2CTests(TestCase):
    datos = {"nombre": "Luis Mora", "rut": "11.111.111-1", "email": "luis@correo.test", "telefono": "",
             "direccion": "Calle 1 123", "clave": "una-clave-larga-92", "clave2": "una-clave-larga-92"}

    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        from clientes.models import Comuna
        cls.datos = dict(cls.datos, comuna=Comuna.objects.first().pk)

    def test_rut_valido_e_invalido(self):
        from clientes import rut
        self.assertTrue(rut.es_valido("11.111.111-1"))
        self.assertTrue(rut.es_valido("12.345.678-5"))
        self.assertFalse(rut.es_valido("11.111.111-2"))
        self.assertEqual(rut.formatear("111111111"), "11.111.111-1")

    def test_registro_crea_cliente_b2c_y_abre_sesion(self):
        from clientes.models import Cliente
        r = self.client.post("/cuenta/registro/", self.datos)
        self.assertRedirects(r, "/catalogo/", fetch_redirect_response=False)
        c = Cliente.objects.get(email="luis@correo.test")
        self.assertEqual(c.tipo_cliente.codigo, "B2C")
        self.assertEqual(c.direccion_set.filter(es_principal=True).count(), 1)
        self.assertEqual(self.client.get("/carrito/").status_code, 200)

    def test_rut_malo_o_duplicado_no_crea(self):
        from clientes.models import Cliente
        antes = Cliente.objects.count()
        r = self.client.post("/cuenta/registro/", dict(self.datos, rut="11.111.111-9"))
        self.assertContains(r, "RUT no es válido")
        r = self.client.post("/cuenta/registro/", dict(self.datos, rut="12.345.678-5"))
        self.assertContains(r, "Ya existe una cuenta con ese RUT")
        self.assertEqual(Cliente.objects.count(), antes)

    def test_claves_distintas_o_debiles(self):
        self.assertContains(self.client.post("/cuenta/registro/", dict(self.datos, clave2="otra")), "no coinciden")
        self.assertContains(self.client.post("/cuenta/registro/", dict(self.datos, clave="123", clave2="123")), "demasiado corta")

    def test_login_lleva_al_personal_al_crm_y_a_los_clientes_al_catalogo(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        U.objects.filter(username="ana@correo.test").first().set_password("x-clave-larga-77") or None
        for usuario, destino in [("ana@correo.test", "/catalogo/"), ("vendedora@cofrial.cl", "/crm/")]:
            u = U.objects.get(username=usuario)
            u.set_password("x-clave-larga-77")
            u.save()
            r = self.client.post("/cuenta/entrar/", {"username": usuario, "password": "x-clave-larga-77"})
            self.assertRedirects(r, destino, fetch_redirect_response=False)
            self.client.logout()


class CuentasDelEquipoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def test_felipe_sergio_y_eric_existen_con_su_perfil(self):
        U = get_user_model()
        felipe = Cliente.objects.get(usuario__username="felipe@cofrial.cl")
        sergio = Cliente.objects.get(usuario__username="sergio@cofrial.cl")
        self.assertEqual((felipe.nombre, felipe.tipo_cliente.codigo), ("Felipe Henríquez", "B2B"))
        self.assertEqual((sergio.nombre, sergio.tipo_cliente.codigo), ("Sergio Vásquez", "B2C"))
        for c in (felipe, sergio):
            d = c.direccion_set.get(es_principal=True)
            self.assertIsNotNone(d.lat)                              # direcciones ubicadas: se pueden despachar con ruta
        self.assertEqual(crm.rol(U.objects.get(username="eric@cofrial.cl")), "admin")

    def test_cargar_demo_no_duplica_las_cuentas_del_equipo(self):
        n = Cliente.objects.count()
        call_command("cargar_demo", verbosity=0)
        self.assertEqual(Cliente.objects.count(), n)
        self.assertEqual(get_user_model().objects.filter(username__in=["felipe@cofrial.cl", "sergio@cofrial.cl", "eric@cofrial.cl"]).count(), 3)


class ClavesPersistentesTests(TestCase):
    """Las claves se fijan solo al crear la cuenta: una clave cambiada desde adentro sobrevive a cada arranque."""

    def test_cargar_demo_no_pisa_una_clave_cambiada_y_el_admin_usa_admin_password(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-demo-larga-71", "ADMIN_PASSWORD": "clave-admin-larga-72"}):
            call_command("cargar_demo", verbosity=0)
            User = get_user_model()
            for u, base in (("admin@cofrial.cl", "clave-admin-larga-72"), ("eric@cofrial.cl", "clave-admin-larga-72"), ("ana@correo.test", "clave-demo-larga-71")):
                self.assertTrue(User.objects.get(username=u).check_password(clave_de(u, base)), u)
            for u, nueva in (("ana@correo.test", "ana-cambio-clave-83"), ("admin@cofrial.cl", "admin-cambio-clave-84")):
                x = User.objects.get(username=u)
                x.set_password(nueva)
                x.save()
            call_command("cargar_demo", verbosity=0)                  # reinicio del contenedor
            self.assertTrue(User.objects.get(username="ana@correo.test").check_password("ana-cambio-clave-83"))
            self.assertTrue(User.objects.get(username="admin@cofrial.cl").check_password("admin-cambio-clave-84"))

    def test_pagina_cambiar_mi_clave(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-demo-larga-71"}):
            call_command("cargar_demo", verbosity=0)
        self.assertEqual(self.client.get("/cuenta/clave/").status_code, 302)       # exige sesión
        clave_ana = clave_de("ana@correo.test", "clave-demo-larga-71")
        self.assertTrue(self.client.login(username="ana@correo.test", password=clave_ana))
        r = self.client.get("/cuenta/clave/")
        self.assertContains(r, "Cambiar mi clave")
        r = self.client.post("/cuenta/clave/", {"old_password": clave_ana, "new_password1": "ana-nueva-clave-95", "new_password2": "ana-nueva-clave-95"})
        self.assertRedirects(r, "/cuenta/clave/hecho/")
        self.assertContains(self.client.get("/cuenta/clave/hecho/"), "Clave actualizada")
        self.client.logout()
        self.assertFalse(self.client.login(username="ana@correo.test", password=clave_ana))
        self.assertTrue(self.client.login(username="ana@correo.test", password="ana-nueva-clave-95"))
        self.assertContains(self.client.get("/catalogo/"), "/cuenta/clave/")       # enlace en el menú (con sesión «/» lleva al inicio del rol)


class ClavePropiaPorCuentaTests(TestCase):
    """Cada cuenta de demostración tiene su clave, derivada de DEMO_PASSWORD; la hoja para el profesor se calcula con el mismo .env."""

    def test_claves_distintas_estables_y_que_dependen_de_la_base(self):
        c = cuentas_demo.claves("base-larga-de-prueba-1")
        self.assertEqual(len(set(c.values())), len(cuentas_demo.USUARIOS))       # ninguna se repite
        self.assertEqual(c, cuentas_demo.claves("base-larga-de-prueba-1"))        # siempre las mismas
        self.assertNotEqual(c["ana@correo.test"], cuentas_demo.claves("otra-base-larga-2")["ana@correo.test"])
        self.assertRegex(c["ana@correo.test"], r"^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$")
        con_admin = cuentas_demo.claves("base-larga-de-prueba-1", "base-admin-larga-3")
        self.assertNotEqual(con_admin["admin@cofrial.cl"], c["admin@cofrial.cl"])  # las administradoras salen de ADMIN_PASSWORD
        self.assertEqual(con_admin["ana@correo.test"], c["ana@correo.test"])

    def test_las_cuentas_con_la_clave_comun_pasan_a_la_propia_sin_pisar_una_cambiada(self):
        User = get_user_model()
        with patch.dict("os.environ", {"DEMO_PASSWORD": "base-comun-larga-44"}):
            call_command("cargar_demo", verbosity=0)
            call_command("cambiar_clave_demo", "--misma")                       # como quedó AWS antes: todas con la común
            gerencia = User.objects.get(username="gerencia@cofrial.cl")
            gerencia.set_password("gerencia-la-cambio-55")
            gerencia.save()
            call_command("cargar_demo", verbosity=0)                            # el siguiente arranque
        for u in ("ana@correo.test", "vendedora@cofrial.cl", "admin@cofrial.cl", "eric@cofrial.cl"):
            self.assertTrue(User.objects.get(username=u).check_password(clave_de(u, "base-comun-larga-44")), u)
        self.assertTrue(User.objects.get(username="gerencia@cofrial.cl").check_password("gerencia-la-cambio-55"))

    def test_la_hoja_trae_cada_cuenta_con_su_clave_y_queda_privada(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            env, salida = os.path.join(d, ".env"), os.path.join(d, "hoja-cuentas.md")
            with open(env, "w") as f:
                f.write("# comentario\nDEMO_PASSWORD='base-de-la-hoja-66'\nADMIN_PASSWORD=\n")
            cuentas_demo.main(["--env", env, "--url", "http://10.0.0.1/", "--salida", salida])
            texto = open(salida, encoding="utf-8").read()
            self.assertEqual(os.stat(salida).st_mode & 0o777, 0o600)
        for u, clave in cuentas_demo.claves("base-de-la-hoja-66").items():
            self.assertIn(f"`{u}`", texto)
            self.assertIn(f"`{clave}`", texto)
        self.assertIn("http://10.0.0.1/cuenta/registro/empresa/", texto)
        self.assertNotIn("base-de-la-hoja-66", texto)                          # la base nunca aparece
