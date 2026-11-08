"""Activar y desactivar cuentas: sin dejar el sistema sin administradores y sin confundir la cola de solicitudes de empresa."""
from django.contrib.auth import get_user_model
from django.test import Client

from clientes.models import Cliente, TipoCliente, Vendedor
from crm import servicios as crm
from crm.models import Prospecto
from operacion import servicios as s

from .tests_datos import CLAVE, Base

Usuario = get_user_model()


class Estado(Base):
    def setUp(self):
        super().setUp()
        self.yo = Usuario.objects.get(username="admin@cofrial.cl")

    def cambiar(self, u, activa, cliente=None):
        return (cliente or self.admin).post(f"/operacion/cuentas/{u.pk}/activa/", {"activa": "1" if activa else "0"}, follow=True)

    def cuenta(self, username):
        return Usuario.objects.get(username=username)

    def empresa(self, activa=False, vendedor=None):
        u = Usuario.objects.create_user("empresa@nueva.test", password=CLAVE, is_active=activa)
        return Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2B"), vendedor=vendedor, rut="76.086.428-5", nombre="Nueva SpA", email="empresa@nueva.test")

    def vendedor_sin_cartera(self):
        u = Usuario.objects.create_user("nuevo@cofrial.cl", password=CLAVE, is_staff=True)
        return Vendedor.objects.create(usuario=u, nombre="Vendedor Nuevo")

    def test_permisos(self):
        ana = self.cuenta("ana@correo.test")
        for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            self.assertEqual(self.entrar(u).post(f"/operacion/cuentas/{ana.pk}/activa/", {"activa": "0"}).status_code, 403, u)
        self.assertEqual(self.admin.get(f"/operacion/cuentas/{ana.pk}/activa/").status_code, 405)

    def test_cuenta_desactivada_no_ingresa(self):
        ana = self.cuenta("ana@correo.test")
        self.cambiar(ana, False)
        ana.refresh_from_db()
        self.assertFalse(ana.is_active)
        self.assertFalse(Client().login(username="ana@correo.test", password=CLAVE))

    def test_sesion_abierta_se_corta(self):
        c = self.entrar("ana@correo.test")
        self.assertEqual(c.get("/pedidos/").status_code, 200)
        self.cambiar(self.cuenta("ana@correo.test"), False)
        self.assertEqual(c.get("/pedidos/").status_code, 302)

    def test_se_vuelve_a_activar(self):
        ana = self.cuenta("ana@correo.test")
        self.cambiar(ana, False)
        self.cambiar(ana, True)
        ana.refresh_from_db()
        self.assertTrue(ana.is_active)

    def test_no_se_desactiva_la_propia_cuenta(self):
        r = self.cambiar(self.yo, False)
        self.assertIn("tu propia cuenta", self.mensajes(r))
        self.yo.refresh_from_db()
        self.assertTrue(self.yo.is_active)

    def test_no_se_desactiva_el_ultimo_administrador(self):
        Usuario.objects.filter(is_superuser=True).exclude(pk=self.yo.pk).update(is_active=False)
        otro = Usuario.objects.create_user("x@cofrial.cl", password=CLAVE)
        with self.assertRaises(s.ErrorOperacion):
            s.cambiar_activa(self.yo, False, otro)
        self.yo.refresh_from_db()
        self.assertTrue(self.yo.is_active)

    def test_otro_administrador_si_se_desactiva(self):
        eric = self.cuenta("eric@cofrial.cl")
        self.cambiar(eric, False)
        eric.refresh_from_db()
        self.assertFalse(eric.is_active)

    def test_no_se_activa_una_solicitud_pendiente(self):
        c = self.empresa()
        r = self.cambiar(c.usuario, True)
        self.assertIn("Solicitudes", self.mensajes(r))
        c.usuario.refresh_from_db()
        self.assertFalse(c.usuario.is_active)

    def test_no_se_desactiva_b2b_sin_vendedor(self):
        c = self.empresa(activa=True)
        antes = crm.solicitudes_empresa().count()
        r = self.cambiar(c.usuario, False)
        self.assertIn("vendedor", self.mensajes(r))
        c.usuario.refresh_from_db()
        self.assertTrue(c.usuario.is_active)
        self.assertEqual(crm.solicitudes_empresa().count(), antes)

    def test_b2b_con_vendedor_si_se_desactiva_sin_ser_solicitud(self):
        c = self.empresa(activa=True, vendedor=Vendedor.objects.first())
        self.cambiar(c.usuario, False)
        c.usuario.refresh_from_db()
        self.assertFalse(c.usuario.is_active)
        self.assertNotIn(c, crm.solicitudes_empresa())

    def test_vendedor_con_clientes_no_se_desactiva(self):
        u = self.cuenta("vendedora@cofrial.cl")
        r = self.cambiar(u, False)
        self.assertIn("reasigna", self.mensajes(r))
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        self.assertTrue(u.vendedor.activo)

    def test_vendedor_con_prospecto_abierto_no_se_desactiva(self):
        v = self.vendedor_sin_cartera()
        p = Prospecto.objects.filter(etapa__es_final=False).first()
        Prospecto.objects.filter(pk=p.pk).update(vendedor=v)
        self.assertIn("reasigna", self.mensajes(self.cambiar(v.usuario, False)))
        v.refresh_from_db()
        self.assertTrue(v.activo)

    def test_vendedor_sin_cartera_cambia_ambos_interruptores(self):
        v = self.vendedor_sin_cartera()
        self.cambiar(v.usuario, False)
        v.refresh_from_db()
        v.usuario.refresh_from_db()
        self.assertEqual((v.usuario.is_active, v.activo), (False, False))
        self.cambiar(v.usuario, True)
        v.refresh_from_db()
        v.usuario.refresh_from_db()
        self.assertEqual((v.usuario.is_active, v.activo), (True, True))

    def test_valor_invalido_no_cambia_nada(self):
        ana = self.cuenta("ana@correo.test")
        self.admin.post(f"/operacion/cuentas/{ana.pk}/activa/", {"activa": "tal-vez"})
        ana.refresh_from_db()
        self.assertTrue(ana.is_active)

    def test_la_lista_ofrece_el_boton(self):
        ana = self.cuenta("ana@correo.test")
        self.assertContains(self.admin.get("/operacion/cuentas/"), f'action="/operacion/cuentas/{ana.pk}/activa/"')
