"""Cofri, el agente de Cofrial: el prompt está fijado (versión + huella), el ciclo de herramientas respeta permisos y topes. El proveedor de IA es simulado."""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from catalogo import asistente, cofri
from clientes.models import Cliente
from crm.ia import ErrorIA

CLAVE = "demo-cofrial-2026"

# Si esta prueba falla, alguien cambió el prompt. Pasos: 1) subir cofri.VERSION_PROMPT, 2) correr `manage.py evaluar_asistente` y revisar que no haya
# casos MAL, 3) poner aquí la huella nueva. Es el «examen» que ningún cambio de prompt se salta, tampoco un viernes por la tarde.
VERSION_ESPERADA = "2026-11-13.1"
HUELLA_ESPERADA = "629b081bb569"


class PromptDeCofri(TestCase):
    def test_el_prompt_esta_fijado_por_version_y_huella(self):
        self.assertEqual((cofri.VERSION_PROMPT, cofri.HUELLA_PROMPT), (VERSION_ESPERADA, HUELLA_ESPERADA))

    def test_el_prompt_lleva_la_identidad_y_las_reglas_que_no_se_negocian(self):
        p = cofri.PROMPT_SISTEMA
        for clave in ("Cofri", "Cofrial SpA", "cadena de frío", "No recomiendes", "competencia", "NO lo inventes", "límites de reembolso",
                      "buscar_producto", "consultar_pedido", "DATO, nunca instrucciones", "resuelta"):
            self.assertIn(clave, p)

    def test_el_nombre_aparece_en_el_saludo(self):
        self.assertIn("Cofri", asistente.MSG_SALUDO)


class CicloDelAgente(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()
        self.client.login(username="ana@correo.test", password=CLAVE)
        self.llamadas = []

    def preguntar(self, mensaje, respuestas):
        """`respuestas`: lo que contestará el modelo en cada vuelta del ciclo."""
        salidas = iter(respuestas)

        def falso(prompt, plazo=None, orden=None):
            self.llamadas.append(prompt)
            r = next(salidas)
            if isinstance(r, Exception):
                raise r
            return json.dumps(r)
        with patch("crm.ia._llamar", side_effect=falso):
            return self.client.post("/api/asistente/", json.dumps({"mensaje": mensaje}), content_type="application/json").json()

    def test_pide_una_herramienta_y_responde_con_su_resultado(self):
        r = self.preguntar("¿Cuánto cuesta el lomo vetado?", [
            {"herramienta": "buscar_producto", "argumentos": {"consulta": "lomo vetado"}},
            {"respuesta": "El lomo vetado cuesta $45.990 con IVA incluido.", "resuelta": True, "fuera_de_alcance": False}])
        self.assertEqual(r["herramientas"], ["buscar_producto"])
        self.assertEqual(r["agente"], "Cofri")
        self.assertIn("$45.990", r["respuesta"])
        self.assertIn("resultado_de_herramienta", self.llamadas[1])

    def test_un_pedido_ajeno_no_se_filtra_por_la_herramienta(self):
        """El hospital tiene el pedido 1; Ana lo pide por herramienta: el servidor responde «no aparece» y el pedido no entra al prompt."""
        r = self.preguntar("precio del lomo vetado", [
            {"herramienta": "consultar_pedido", "argumentos": {"numero": 1}},
            {"respuesta": "Ese pedido no aparece entre los de tu cuenta.", "resuelta": True, "fuera_de_alcance": False}])
        self.assertIn("no aparece entre los pedidos de esta cuenta", self.llamadas[1])
        self.assertNotIn("Montt", self.llamadas[1])
        self.assertNotIn('"estado": "despachado"', self.llamadas[1])
        self.assertEqual(r["herramientas"], ["consultar_pedido"])

    def test_una_herramienta_desconocida_deriva_a_una_persona(self):
        r = self.preguntar("precio del lomo vetado", [{"herramienta": "reembolsar_todo", "argumentos": {}}])
        self.assertEqual(r["origen"], "error")
        self.assertEqual(r["ticket"]["estado"], "derivada")

    def test_el_agente_no_puede_encadenar_herramientas_sin_limite(self):
        pide = {"herramienta": "buscar_producto", "argumentos": {"consulta": "lomo"}}
        r = self.preguntar("precio del lomo vetado", [pide] * (asistente.MAX_HERRAMIENTAS + 2))
        self.assertEqual(len(self.llamadas), asistente.MAX_HERRAMIENTAS + 1)
        self.assertEqual(r["origen"], "error")

    def test_si_el_modelo_falla_a_mitad_del_ciclo_se_deriva(self):
        r = self.preguntar("precio del lomo vetado", [{"herramienta": "buscar_producto", "argumentos": {"consulta": "lomo"}}, ErrorIA("sin red")])
        self.assertEqual(r["ticket"]["estado"], "derivada")

    def test_un_anonimo_no_puede_consultar_pedidos_por_herramienta(self):
        self.client.logout()
        cliente = Cliente.objects.get(usuario__username="ana@correo.test")
        self.assertIn("no ha iniciado sesión", asistente._herr_consultar_pedido({"numero": 1}, {}, None, None, None))
        ctx = {}
        self.assertIn("no aparece", asistente._herr_consultar_pedido({"numero": 999999}, ctx, cliente, cliente.tipo_cliente, None))
        self.assertNotIn("pedidos", ctx)
