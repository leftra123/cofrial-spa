from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

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
                   vendedor="vendedora@cofrial.test")
        c = Cliente.objects.get(rut="76.111.222-3")
        self.assertEqual((c.tipo_cliente.codigo, c.vendedor.usuario.username, c.direccion_set.count()), ("B2B", "vendedora@cofrial.test", 1))
        self.assertIsNone(crm.rol(c.usuario))                       # un cliente no entra al CRM
        self.assertEqual(pedidos.cliente_de(c.usuario), c)           # pero sí compra en el portal
        self.assertTrue(self.entra("compras@hotel.test"))

    def test_cliente_b2c(self):
        self.crear("ana2@t.test", rol="cliente-b2c", nombre="Ana Díaz", rut="11.222.333-4", direccion="Calle 1 123")
        self.assertEqual(Cliente.objects.get(rut="11.222.333-4").tipo_cliente.codigo, "B2C")

    def test_errores_claros_y_sin_efectos_a_medias(self):
        usuarios = get_user_model().objects.count()
        with self.assertRaisesMessage(CommandError, "ya existe"):
            self.crear("admin", rol="admin")
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
        for u in ("admin", "ana@correo.test", "vendedora@cofrial.test", "despachador@cofrial.test"):
            self.assertTrue(self.entra(u), u)
        self.assertFalse(self.entra("ana@correo.test", clave="demo-cofrial-2026"))

    def test_cambiar_clave_demo_no_toca_cuentas_ajenas_ni_actua_sin_clave_si_se_pide(self):
        self.crear("otra@t.test", rol="gerencia")
        with patch.dict("os.environ", {"DEMO_PASSWORD": "otra-clave-larga-9"}):
            call_command("cambiar_clave_demo")
        self.assertTrue(self.entra("otra@t.test"))                   # su clave no cambió
        with patch.dict("os.environ", {}, clear=True):
            call_command("cambiar_clave_demo", "--si-hay-clave")      # sin variable no hace nada ni falla
        self.assertTrue(self.entra("ana@correo.test", clave="otra-clave-larga-9"))

    def test_clave_debil_se_rechaza_salvo_que_se_pida_expresamente(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "123456"}):
            with self.assertRaisesMessage(CommandError, "permitir-clave-debil"):
                call_command("cambiar_clave_demo")
            self.assertTrue(self.entra("ana@correo.test", clave="demo-cofrial-2026"))      # no cambió nada al rechazarla
            call_command("cambiar_clave_demo", "--permitir-clave-debil")
        for u in ("admin", "ana@correo.test", "abastecimiento@hospital.test", "vendedora@cofrial.test", "vendedor2@cofrial.test",
                  "gerente@cofrial.test", "despachador@cofrial.test"):
            self.assertTrue(self.entra(u, clave="123456"), u)
