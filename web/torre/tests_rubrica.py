"""Evidencia viva de la rúbrica: verde solo cuando la evidencia lo sostiene."""
import json
import os
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, connection
from django.utils import timezone

from crm.models import CategoriaRequerimiento, Requerimiento
from flota.models import Camion, Telemetria
from pedidos.models import EstadoOrden
from torre import rubrica
from torre.tests_pulso import Base

HOST_RDS = "cofrial.abc123xyz.us-east-1.rds.amazonaws.com"


class Rubrica(Base):
    def setUp(self):
        super().setUp()
        Requerimiento.objects.all().delete()
        rubrica.limpiar_cache()
        self.addCleanup(rubrica.limpiar_cache)

    def fila(self, dim):
        filas = rubrica.evaluar()
        self.assertEqual([f["dim"] for f in filas], ["D1", "D2", "D3", "D4", "D5"])
        return next(f for f in filas if f["dim"] == dim)

    def d1(self, host, instancia=None):
        with mock.patch.dict(connection.settings_dict, {"HOST": host}), mock.patch.object(rubrica, "instancia_ec2", return_value=instancia):
            return self.fila("D1")

    def grafana(self, arriba):
        return mock.patch.object(rubrica, "_consultar_grafana", return_value=arriba)

    def pedido_canal(self, nombre, tipo, oc="", hace_dias=1):
        o = self.pedido(self.cliente(nombre, tipo=tipo), hace_dias=hace_dias)
        type(o).objects.filter(pk=o.pk).update(numero_oc=oc)
        return o

    # D1
    def test_d1_host_local_no_es_verde(self):
        f = self.d1("db")
        self.assertEqual(f["estado"], rubrica.SIN_EVIDENCIA)
        self.assertTrue(f["titulo"] and f["exigencia"] and f["url"] == "/salud/")

    def test_d1_rds_sin_instancia(self):
        self.assertEqual(self.d1(HOST_RDS)["estado"], rubrica.NO_COMPROBADO)

    def test_d1_rds_con_instancia(self):
        f = self.d1(HOST_RDS, "i-0abc123")
        self.assertEqual(f["estado"], rubrica.VERIFICADO)
        self.assertNotIn(HOST_RDS, json.dumps(f))
        self.assertIn("…", " ".join(f["evidencia"]))
        self.assertIn(".rds.amazonaws.com", " ".join(f["evidencia"]))

    def test_instancia_ec2_usa_variable_si_no_hay_imds(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError), mock.patch.dict(os.environ, {"INSTANCIA_EC2": "i-0a1b2c3d4e"}):
            self.assertEqual(rubrica.instancia_ec2(), "i-0a1b2c3d4e")

    def test_d1_instancia_invalida_no_es_verde(self):
        basura = "<html>\n<head><title>401 - Unauthorized</title></head>\n</html>"
        with mock.patch("urllib.request.urlopen", side_effect=OSError), mock.patch.dict(os.environ, {"INSTANCIA_EC2": basura}):
            self.assertIsNone(rubrica.instancia_ec2())
        self.assertIsNone(rubrica._id_valido("401 Unauthorized"))
        self.assertIsNone(rubrica._id_valido(""))
        f = self.d1(HOST_RDS, rubrica._id_valido(basura))
        self.assertNotEqual(f["estado"], rubrica.VERIFICADO)

    # D2
    def test_d2_solo_historial_no_es_verde(self):
        self.pedido_canal("H1", self.b2b, "HIS-1")
        self.pedido_canal("H2", self.b2c, "HIS-2")
        self.assertEqual(self.fila("D2")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d2_ambos_canales(self):
        self.pedido_canal("A", self.b2b, "OC-1")
        self.pedido_canal("B", self.b2c)
        f = self.fila("D2")
        self.assertEqual(f["estado"], rubrica.VERIFICADO)
        self.assertEqual(f["url"], "/catalogo/")

    # D3
    def test_d3_lectura_reciente(self):
        self.lectura(Camion.objects.first(), False)
        f = self.fila("D3")
        self.assertEqual(f["estado"], rubrica.VERIFICADO)
        texto = " ".join(f["evidencia"])
        for campo in ("camion_id", "temp_camara", "lat", "long", "combustible_pct", "alerta_ruptura_frio"):
            self.assertIn(campo, texto)

    def test_d3_simulador_detenido(self):
        self.lectura(Camion.objects.first(), False)
        Telemetria.objects.update(registrado_en=timezone.now() - timedelta(minutes=3))
        self.assertEqual(self.fila("D3")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d3_solo_forzadas(self):
        self.lectura(Camion.objects.first(), True, forzada=True)
        self.assertEqual(self.fila("D3")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d2_pedidos_sembrados_no_son_ventas(self):
        self.pedido_canal("A", self.b2b, "OC-REG-001")
        self.pedido_canal("B", self.b2c, "OC-2026-0457")
        f = self.fila("D2")
        self.assertEqual(f["estado"], rubrica.SIN_EVIDENCIA)
        self.assertIn("Último pedido B2B: ninguno", " ".join(f["evidencia"]))

    def test_d2_canceladas_no_cuentan(self):
        o = self.pedido_canal("A", self.b2b, "OC-1")
        self.pedido_canal("B", self.b2c)
        type(o).objects.filter(pk=o.pk).update(estado_orden=EstadoOrden.objects.get(nombre="Cancelada"))
        self.assertEqual(self.fila("D2")["estado"], rubrica.SIN_EVIDENCIA)

    # D4
    def test_d4_pedidos_sembrados_no_son_ventas(self):
        self.pedido_canal("A", self.b2b, "OC-SUR-118")
        self.pedido_canal("B", self.b2b, "OC-REG-003")
        with self.grafana(True):
            f = self.fila("D4")
        self.assertEqual(f["estado"], rubrica.SIN_EVIDENCIA)
        self.assertNotIn("Ventas B2B", " ".join(f["evidencia"]))
        self.assertIn("Pedidos en la ventana: 0", " ".join(f["evidencia"]))

    def test_d4_grafana_caido(self):
        self.pedido_canal("A", self.b2b, "OC-1")
        with self.grafana(False):
            self.assertEqual(self.fila("D4")["estado"], rubrica.NO_COMPROBADO)

    def test_d4_sin_ventas(self):
        with self.grafana(True):
            self.assertEqual(self.fila("D4")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d4_sin_alertas_es_verde(self):
        self.pedido_canal("A", self.b2b, "OC-1")
        with self.grafana(True):
            f = self.fila("D4")
        self.assertEqual(f["estado"], rubrica.VERIFICADO)
        self.assertIn("7 días", " ".join(f["evidencia"]))

    def test_d4_cuenta_ilustrativas(self):
        self.pedido_canal("A", self.b2b, "HIS-1")
        self.pedido_canal("B", self.b2c, "HIS-2")
        self.pedido_canal("C", self.b2c)
        self.pedido_canal("Vieja", self.b2c, hace_dias=30)
        with self.grafana(True):
            f = self.fila("D4")
        texto = " ".join(f["evidencia"])
        self.assertIn("3 (2 del historial", texto)
        self.assertEqual(f["estado"], rubrica.VERIFICADO)

    def test_d4_solo_ilustrativas_no_es_verde(self):
        self.pedido_canal("A", self.b2b, "HIS-1")
        self.pedido_canal("B", self.b2c, "HIS-2")
        with self.grafana(True):
            f = self.fila("D4")
        self.assertEqual(f["estado"], rubrica.SIN_EVIDENCIA)
        self.assertIn("2 del historial", " ".join(f["evidencia"]))

    def test_d4_grafana_se_consulta_una_vez_en_30_s(self):
        with self.grafana(True) as consulta:
            self.fila("D4")
            self.fila("D4")
        self.assertEqual(consulta.call_count, 1)

    # D5
    def clasificar(self):
        cat, _ = CategoriaRequerimiento.objects.get_or_create(nombre="Reclamo")
        return Requerimiento.objects.create(asunto="x", descripcion="y", categoria_requerimiento=cat, categoria_ia=cat, confianza_ia="0.90", estado="clasificado")

    def test_d5_ia_de_pago_no_es_verde(self):
        self.clasificar()
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-secreta"}):
            self.assertEqual(self.fila("D5")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d5_sin_clasificacion(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertEqual(self.fila("D5")["estado"], rubrica.SIN_EVIDENCIA)

    def test_d5_verde_con_clasificacion_y_sin_ia_de_pago(self):
        self.clasificar()
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "g-secreta"}):
            f = self.fila("D5")
        self.assertEqual(f["estado"], rubrica.VERIFICADO)
        self.assertIn("Gemini", " ".join(f["evidencia"]))
        self.assertIn("La defensa en vivo la hace el equipo", f["evidencia"])

    def test_d5_sin_proveedor_gratuito_no_es_verde(self):
        self.clasificar()
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "", "GROQ_API_KEY": ""}):
            f = self.fila("D5")
        self.assertEqual(f["estado"], rubrica.SIN_EVIDENCIA)
        self.assertIn("Proveedores gratuitos configurados: ninguno", f["evidencia"])

    def test_d5_no_muestra_claves(self):
        self.clasificar()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "g-secreta", "GROQ_API_KEY": "q-secreta", "ANTHROPIC_API_KEY": "sk-secreta"}):
            todo = json.dumps(rubrica.evaluar())
        for valor in ("g-secreta", "q-secreta", "sk-secreta"):
            self.assertNotIn(valor, todo)

    # Aislamiento
    def test_error_de_base_aisla_la_fila(self):
        with mock.patch.object(rubrica, "_d2", side_effect=DatabaseError("boom")):
            filas = rubrica.evaluar()
        estados = {f["dim"]: f["estado"] for f in filas}
        self.assertEqual(estados["D2"], rubrica.NO_COMPROBADO)
        self.assertEqual(len(filas), 5)
