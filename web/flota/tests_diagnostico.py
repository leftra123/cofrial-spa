"""Diagnóstico de un camión (ruptura real, falla de sensor o sensor pegado) y envío a revisión técnica."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from crm import ia
from flota import diagnostico, servicios
from flota.diagnostico import ErrorRevision
from flota.models import Camion, RevisionCamion, Telemetria
from pedidos.servicios import ErrorDeNegocio

CLAVE = "demo-cofrial-2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        cache.clear()
        self.camion = next(c for c in servicios.camiones_libres() if not c.dos_camaras)             # uno sin viaje: los de la demostración ya salieron
        Telemetria.objects.filter(camion=self.camion).delete()
        self.tmax = float(self.camion.rango_temperatura.temp_max_c)
        self.tmin = float(self.camion.rango_temperatura.temp_min_c)

    def leer(self, temps, camara=1, camion=None):
        """Inserta lecturas de la más antigua a la más nueva, una cada 5 s, con la alerta que corresponde al rango del camión."""
        camion = camion or self.camion
        ahora = timezone.now()
        for i, t in enumerate(temps):
            fila = Telemetria.objects.create(camion=camion, camara=camara, temp_camara=t, lat=-38.7, long=-72.6, combustible_pct=80,
                                             alerta_ruptura_frio=t > self.tmax or t < self.tmin)
            Telemetria.objects.filter(pk=fila.pk).update(registrado_en=ahora - timedelta(seconds=5 * (len(temps) - i)))

    def normal(self):
        return (self.tmin + self.tmax) / 2


class DiagnosticoTests(Base):
    def test_normal_sin_accion(self):
        self.leer([round(self.normal() + d, 1) for d in (0.1, -0.1, 0.2, 0.0, 0.1, -0.2, 0.1, 0.0)])
        d = diagnostico.diagnosticar(self.camion)
        self.assertEqual(d["estado"], "normal")
        self.assertIsNone(d["accion"])

    def test_la_temperatura_que_sube_de_a_poco_es_ruptura_de_frio(self):
        n = self.normal()
        self.leer([round(n + k * 0.9, 1) for k in range(10)])
        d = diagnostico.diagnosticar(self.camion)
        self.assertEqual(d["estado"], "ruptura")
        self.assertEqual(d["accion"]["motivo"], "equipo_frio")
        self.assertIn("equipo de frío", d["accion"]["texto"])

    def test_un_salto_imposible_es_falla_del_sensor(self):
        n = self.normal()
        self.leer([round(n, 1)] * 5 + [round(n + 11.0, 1), round(n + 12.5, 1)])
        d = diagnostico.diagnosticar(self.camion)
        self.assertEqual(d["estado"], "sensor_alerta")
        self.assertEqual(d["accion"]["motivo"], "sensor")
        self.assertIn("carga podría estar bien", d["texto"])

    def test_un_sensor_clavado_en_normal_se_detecta_aunque_no_avise(self):
        self.leer([round(self.normal(), 1)] * 9)
        d = diagnostico.diagnosticar(self.camion)
        self.assertEqual(d["estado"], "sensor_pegado")
        self.assertEqual(d["accion"]["motivo"], "sensor")

    def test_poca_historia_no_alcanza_para_decir_que_esta_pegado(self):
        self.leer([round(self.normal(), 1)] * 4)
        self.assertEqual(diagnostico.diagnosticar(self.camion)["estado"], "normal")

    def test_la_ia_solo_redacta_y_su_texto_se_descarta_si_inventa_un_camion(self):
        n = self.normal()
        self.leer([round(n + k * 0.9, 1) for k in range(10)])
        with patch.object(ia, "redactar", return_value="Revisa el equipo de CAM-999 de inmediato."):
            d = diagnostico.diagnosticar(self.camion, con_ia=True)
        self.assertFalse(d["por_ia"])
        self.assertIn(self.camion.camion_id, d["texto"])
        cache.clear()
        with patch.object(ia, "redactar", return_value=f"{self.camion.camion_id} se entibia; conviene revisar el equipo."):
            d = diagnostico.diagnosticar(self.camion, con_ia=True)
        self.assertTrue(d["por_ia"])
        self.assertEqual(d["texto"], f"{self.camion.camion_id} se entibia; conviene revisar el equipo.")

    def test_sin_ia_o_sin_pedirla_usa_el_texto_del_sistema_y_no_llama(self):
        n = self.normal()
        self.leer([round(n + k * 0.9, 1) for k in range(10)])
        with patch.object(ia, "redactar", side_effect=AssertionError("no debía llamar")) as llamada:
            d = diagnostico.diagnosticar(self.camion)
        self.assertFalse(d["por_ia"])
        llamada.assert_not_called()
        with patch.object(ia, "redactar", side_effect=ia.ErrorIA("sin cuota")):
            self.assertFalse(diagnostico.diagnosticar(self.camion, con_ia=True)["por_ia"])

    def test_lo_que_se_manda_a_la_ia_no_lleva_clientes(self):
        n = self.normal()
        self.leer([round(n + k * 0.9, 1) for k in range(10)])
        with patch.object(ia, "redactar", return_value="ok") as llamada:
            diagnostico.diagnosticar(self.camion, con_ia=True)
        enviado = llamada.call_args[0][0]
        self.assertIn(self.camion.camion_id, enviado)
        for c in ("Hospital", "Supermercados", "@"):
            self.assertNotIn(c, enviado)


class RevisionTests(Base):
    def test_abrir_y_cerrar_revision(self):
        self.leer([round(self.normal() + k * 0.9, 1) for k in range(10)])
        r = diagnostico.abrir_revision(self.camion.camion_id, "equipo_frio", None)
        self.assertIsNone(r.cerrada_en)
        self.assertIn("equipo de frío", r.nota)
        d = diagnostico.diagnosticar(self.camion)
        self.assertIsNone(d["accion"])                                   # ya está en revisión: no se ofrece de nuevo
        self.assertEqual(d["revision"]["motivo"], "equipo de frío")
        diagnostico.cerrar_revision(self.camion.camion_id, None)
        self.assertEqual(RevisionCamion.objects.filter(cerrada_en__isnull=True).count(), 0)

    def test_no_se_abren_dos_ni_con_motivo_raro(self):
        diagnostico.abrir_revision(self.camion.camion_id, "sensor", None)
        with self.assertRaises(ErrorRevision):
            diagnostico.abrir_revision(self.camion.camion_id, "sensor", None)
        with self.assertRaises(ErrorRevision):
            diagnostico.abrir_revision(self.camion.camion_id, "borrar_todo", None)
        with self.assertRaises(ErrorRevision):
            diagnostico.abrir_revision("CAM-999", "sensor", None)
        with self.assertRaises(ErrorRevision):
            diagnostico.cerrar_revision("CAM-02", None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RevisionCamion.objects.create(camion=self.camion, motivo="otro")        # la base también lo impide

    def test_un_camion_en_revision_no_esta_libre_ni_se_despacha(self):
        self.assertIn(self.camion.camion_id, [c.camion_id for c in servicios.camiones_libres()])
        diagnostico.abrir_revision(self.camion.camion_id, "sensor", None)
        self.assertNotIn(self.camion.camion_id, [c.camion_id for c in servicios.camiones_libres()])
        with self.assertRaises(ErrorDeNegocio) as e:
            servicios.despachar(self.camion.camion_id, [1])
        self.assertIn("revisión", " ".join(e.exception.mensajes))
        diagnostico.cerrar_revision(self.camion.camion_id, None)
        self.assertIn(self.camion.camion_id, [c.camion_id for c in servicios.camiones_libres()])

    def test_la_flota_marca_el_camion_en_revision(self):
        diagnostico.abrir_revision(self.camion.camion_id, "sensor", None)
        tarjetas, resumen = servicios.estado_flota()
        x = next(t for t in tarjetas if t["camion"].camion_id == self.camion.camion_id)
        self.assertTrue(x["en_revision"])
        self.assertTrue(x["en_operacion"])                               # no se esconde entre los guardados
        self.assertEqual(resumen["en_revision"], 1)


class VistasTests(Base):
    def entrar(self, usuario):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def url(self, sufijo):
        return f"/flota/camion/{self.camion.camion_id}/{sufijo}/"

    def test_el_diagnostico_lo_ven_admin_gerencia_y_despacho_pero_no_clientes_ni_ventas(self):
        self.leer([round(self.normal() + k * 0.9, 1) for k in range(10)])
        for u, puede in (("admin@cofrial.cl", True), ("despacho@cofrial.cl", True), ("gerencia@cofrial.cl", False)):
            self.entrar(u)
            r = self.client.get(self.url("diagnostico"))
            self.assertEqual(r.status_code, 200, u)
            self.assertEqual(r.json()["puede_actuar"], puede)
            self.assertEqual(bool(r.json()["accion"]), puede, u)             # gerencia consulta, no actúa
        for u in ("vendedora@cofrial.cl", "ana@correo.test"):
            self.entrar(u)
            self.assertIn(self.client.get(self.url("diagnostico")).status_code, (302, 403), u)
        self.client.logout()
        self.assertEqual(self.client.get(self.url("diagnostico")).status_code, 302)

    def test_enviar_a_revision_exige_confirmar_y_rol(self):
        self.entrar("despacho@cofrial.cl")
        self.assertEqual(self.client.post(self.url("revision"), {"accion": "abrir", "motivo": "sensor"}).status_code, 400)
        r = self.client.post(self.url("revision"), {"accion": "abrir", "motivo": "sensor", "confirmar": "1"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(RevisionCamion.objects.get().abierta_por.username, "despacho@cofrial.cl")
        r = self.client.post(self.url("revision"), {"accion": "volver", "confirmar": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(RevisionCamion.objects.filter(cerrada_en__isnull=True).count(), 0)
        for u in ("gerencia@cofrial.cl", "vendedora@cofrial.cl", "ana@correo.test"):
            self.entrar(u)
            self.assertIn(self.client.post(self.url("revision"), {"accion": "abrir", "motivo": "sensor", "confirmar": "1"}).status_code, (302, 403), u)
        self.assertEqual(RevisionCamion.objects.count(), 1)

    def test_el_panel_trae_el_bloque_del_diagnostico(self):
        self.entrar("despacho@cofrial.cl")
        html = self.client.get("/flota/").content.decode()
        self.assertIn("data-diagnostico", html)
        self.assertIn("diagnostico-camion.js", html)
