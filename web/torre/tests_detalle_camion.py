"""Extras: detalle del camión en la Torre y aviso al cliente desde las alertas de frío del CRM."""
from django.contrib.auth import get_user_model

from clientes.models import Vendedor
from crm.models import Interaccion
from crm import servicios as crm
from flota.models import Camion
from torre import servicios
from torre.tests_pulso import Base


class DetalleDelCamion(Base):
    def test_el_camion_trae_lectura_y_clientes_a_bordo(self):
        v = self.viaje()
        c = self.cliente("Hospital A")
        self.pedido(c, "Despachada", despacho=v)
        self.lectura(v.camion, True)
        cam = servicios.datos_negocio(self.gerencia)["camiones"][0]
        self.assertEqual((cam["id"], cam["temp"], cam["combustible"], cam["alerta"]), (v.camion_id, 9.0, 70, True))
        self.assertEqual([x["nombre"] for x in cam["a_bordo"]], ["Hospital A"])
        self.assertEqual(cam["a_bordo"][0]["url"], f"/crm/clientes/{c.pk}/")

    def test_no_lleva_a_bordo_lo_ya_recibido_ni_lo_cancelado(self):
        v = self.viaje()
        self.pedido(self.cliente("Recibió"), "Entregada", despacho=v)
        self.pedido(self.cliente("Canceló"), "Cancelada", despacho=v)
        self.lectura(v.camion, False)
        self.assertEqual(servicios.datos_negocio(self.gerencia)["camiones"][0]["a_bordo"], [])

    def test_un_vendedor_solo_ve_a_bordo_su_cartera(self):
        v = self.viaje()
        ajeno = self.cliente("Cartera ajena")
        self.pedido(ajeno, "Despachada", despacho=v)
        self.lectura(v.camion, False)
        vendedor = get_user_model().objects.get(username="vendedora@cofrial.cl")
        self.assertEqual(servicios.datos_negocio(vendedor)["camiones"][0]["a_bordo"], [])

    def test_las_consultas_no_crecen_con_los_camiones(self):
        for i, cam in enumerate(Camion.objects.all()[:3]):
            v = self.viaje(cam.pk)
            self.pedido(self.cliente(f"C{i}"), "Despachada", despacho=v)
            self.lectura(cam, False)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as uno:
            servicios.datos_negocio(self.gerencia)
        for i, cam in enumerate(Camion.objects.all()[3:6]):
            v = self.viaje(cam.pk)
            self.pedido(self.cliente(f"D{i}"), "Despachada", despacho=v)
            self.lectura(cam, False)
        with CaptureQueriesContext(connection) as dos:
            servicios.datos_negocio(self.gerencia)
        self.assertEqual(len(uno), len(dos))


class AvisoDeFrio(Base):
    def escenario(self):
        v = self.viaje()
        c = self.cliente("Hospital B")
        c.vendedor = Vendedor.objects.first()
        c.save()
        o = self.pedido(c, "Despachada", despacho=v)
        self.lectura(v.camion, True)
        return c, o

    def admin(self):
        return get_user_model().objects.get(username="admin@cofrial.cl")

    def test_la_alerta_trae_maximo_y_primera_lectura(self):
        c, o = self.escenario()
        o = [x for x in crm.ordenes_afectadas(self.admin()) if x.orden_id == o.orden_id][0]
        self.assertEqual(o.temp_maxima, 9.0)
        self.assertIsNotNone(o.primera_alerta)
        self.assertIsNone(o.aviso)

    def test_avisar_deja_una_interaccion_y_marca_la_orden(self):
        c, o = self.escenario()
        crm.avisar_alerta_frio(self.admin(), o.orden_id, "llamada", "Reprogramamos la entrega")
        i = Interaccion.objects.get(cliente=c, detalle__startswith=crm.AVISO_FRIO)
        self.assertTrue(i.detalle.startswith(f"{crm.AVISO_FRIO}{o.orden_id}: Reprogramamos"))
        marcada = [x for x in crm.ordenes_afectadas(self.admin()) if x.orden_id == o.orden_id][0]
        self.assertEqual(marcada.aviso.pk, i.pk)

    def test_rechaza_tipo_invalido_y_orden_sin_alerta(self):
        c, o = self.escenario()
        sin = self.pedido(self.cliente("Sin alerta"), "Despachada")
        with self.assertRaises(crm.ErrorDeNegocio):
            crm.avisar_alerta_frio(self.admin(), o.orden_id, "nota", "x")
        with self.assertRaises(crm.ErrorDeNegocio):
            crm.avisar_alerta_frio(self.admin(), sin.orden_id, "llamada", "x")

    def test_gerencia_y_despacho_no_registran_avisos(self):
        c, o = self.escenario()
        for usuario, codigo in (("gerencia@cofrial.cl", 302), ("despacho@cofrial.cl", 403)):    # gerencia solo lee: la pantalla se lo explica; despacho ni entra
            self.client.logout()
            self.assertTrue(self.client.login(username=usuario, password="demo-cofrial-2026"))
            self.assertEqual(self.client.post(f"/crm/alertas/{o.orden_id}/avisar/", {"tipo": "llamada"}).status_code, codigo, usuario)
        self.assertFalse(Interaccion.objects.filter(detalle__startswith=crm.AVISO_FRIO).exists())

    def test_la_pantalla_muestra_contacto_y_registra_el_aviso(self):
        c, o = self.escenario()
        self.assertTrue(self.client.login(username="admin@cofrial.cl", password="demo-cofrial-2026"))
        html = self.client.get("/crm/alertas/").content.decode()
        for esperado in (c.email, "máx. 9,0 °C", "Registrar aviso"):
            self.assertIn(esperado, html)
        r = self.client.post(f"/crm/alertas/{o.orden_id}/avisar/", {"tipo": "correo", "detalle": "Se avisó por correo"})
        self.assertRedirects(r, "/crm/alertas/")
        html = self.client.get("/crm/alertas/").content.decode()
        self.assertIn("Avisado", html)
        self.assertNotIn("Registrar aviso", html)
