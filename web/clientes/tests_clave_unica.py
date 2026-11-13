"""cambiar_clave_demo --clave-stdin --todos-los-activos: la misma clave simple en todos los usuarios activos (aws/activar.sh --clave-unica)."""
import io
import os
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


def aplicar(clave, *extra, entorno=None):
    """Corre el comando con la clave en la entrada estándar (como lo hace activar.sh). Devuelve lo que imprimió."""
    salida = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(clave + "\n")), mock.patch.dict(os.environ, entorno or {}, clear=False):
        call_command("cambiar_clave_demo", "--clave-stdin", *extra, stdout=salida)
    return salida.getvalue()


class ClaveUnicaParaTodos(TestCase):
    def setUp(self):
        U = get_user_model()
        self.cliente = U.objects.create_user("cliente@correo.test", password="vieja-cliente-1")
        self.equipo = U.objects.create_user("vendedora@cofrial.cl", password="vieja-equipo-2", is_staff=True)
        self.admin = U.objects.create_superuser("admin@cofrial.cl", "admin@cofrial.cl", "vieja-admin-3")
        self.inactivo = U.objects.create_user("baja@correo.test", password="vieja-baja-4", is_active=False)

    def test_la_misma_clave_entra_en_todos_los_activos_y_no_toca_a_los_inactivos(self):
        aplicar("abcd", "--todos-los-activos", "--permitir-clave-debil")
        for u in (self.cliente, self.equipo, self.admin):
            self.assertIsNotNone(authenticate(username=u.username, password="abcd"), u.username)
            self.assertIsNone(authenticate(username=u.username, password="vieja-cliente-1"), u.username)
        self.inactivo.refresh_from_db()
        self.assertTrue(self.inactivo.check_password("vieja-baja-4"), "una cuenta dada de baja conserva su clave")

    def test_cada_usuario_guarda_su_propio_hash(self):
        aplicar("abcd", "--todos-los-activos", "--permitir-clave-debil")
        hashes = {get_user_model().objects.get(pk=u.pk).password for u in (self.cliente, self.equipo, self.admin)}
        self.assertEqual(len(hashes), 3, "sal distinta por usuario: los hashes no deben coincidir")

    def test_nunca_imprime_la_clave_y_cuenta_el_equipo(self):
        texto = aplicar("clave-secreta-777", "--todos-los-activos", "--permitir-clave-debil")
        self.assertNotIn("clave-secreta-777", texto)
        self.assertIn("3 usuario(s) activo(s), 2 de ellos del equipo", texto)

    def test_sin_permitir_clave_debil_aplica_las_reglas_de_calidad(self):
        with self.assertRaises(CommandError):
            aplicar("abcd", "--todos-los-activos")
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password("vieja-cliente-1"), "si se rechaza, nadie cambia")

    def test_una_clave_de_menos_de_4_caracteres_o_con_espacios_se_rechaza_aun_permitiendo_debiles(self):
        for mala in ("abc", "ab cd"):
            with self.assertRaises(CommandError, msg=mala):
                aplicar(mala, "--todos-los-activos", "--permitir-clave-debil")
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password("vieja-cliente-1"))

    def test_rechaza_una_clave_igual_a_demo_password_o_admin_password(self):
        """cargar_demo devuelve a su clave propia a quien siga con la común: la clave nueva se perdería en la próxima carga."""
        for variable in ("DEMO_PASSWORD", "ADMIN_PASSWORD"):
            with self.assertRaises(CommandError, msg=variable):
                aplicar("abcd", "--todos-los-activos", "--permitir-clave-debil", entorno={variable: "abcd"})

    def test_sin_clave_en_la_entrada_falla(self):
        with mock.patch("sys.stdin", io.StringIO("")), self.assertRaises(CommandError):
            call_command("cambiar_clave_demo", "--clave-stdin", "--todos-los-activos", "--permitir-clave-debil")

    def test_no_se_combina_con_cuenta(self):
        with self.assertRaises(CommandError):
            aplicar("abcd", "--todos-los-activos", "--cuenta", "ana@correo.test", "--permitir-clave-debil")

    def test_el_comportamiento_anterior_con_demo_password_sigue_igual(self):
        """Sin --clave-stdin ni --todos-los-activos el comando usa DEMO_PASSWORD como siempre: solo toca las cuentas de demostración."""
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": "Base-Segura-2026-x", "ADMIN_PASSWORD": ""}):
            call_command("cambiar_clave_demo", "--misma", stdout=io.StringIO())
        self.admin.refresh_from_db(); self.cliente.refresh_from_db()
        self.assertTrue(self.admin.check_password("Base-Segura-2026-x"), "admin@cofrial.cl es cuenta de demostración: --misma la cambia")
        self.assertTrue(self.cliente.check_password("vieja-cliente-1"), "un cliente que no es de demostración no se toca sin --todos-los-activos")
