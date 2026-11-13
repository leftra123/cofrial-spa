"""RN-13 en lo que ve el cliente: una ruptura de frío cuenta hasta que su pedido se entregó, no después."""
from datetime import timedelta

from django.utils import timezone

from catalogo import asistente
from flota.models import Despacho, Telemetria
from pedidos import servicios as s
from pedidos.models import Orden

from .tests_entrega import EntregaBase
from .tests_ruta_cliente import ViajeDeDosClientesBase


def lectura(despacho, temp, alerta, **extra):
    return Telemetria.objects.create(camion=despacho.camion, temp_camara=temp, lat=-38.74, long=-72.60, combustible_pct=60, alerta_ruptura_frio=alerta, **extra)


class RupturaYEntregaTests(EntregaBase):
    def entregada(self):
        cliente, orden, despacho = self.orden_despachada()
        lectura(despacho, 2.0, False)
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        orden.refresh_from_db()
        return cliente, orden, despacho

    def test_quien_ya_recibio_no_ve_una_ruptura_posterior(self):
        cliente, orden, despacho = self.entregada()
        lectura(despacho, 9.0, True)                                        # el camión falla después de entregarle
        seg = s.seguimiento(orden)
        self.assertFalse(seg["hubo_ruptura"])
        self.assertFalse(seg["ultima"]["alerta_ruptura_frio"])             # tampoco como «última lectura»
        self.assertEqual(seg["ultima"]["temp_camara"], 2.0)                # el resumen termina en su entrega
        self.entrar()
        pagina = self.client.get(f"/pedidos/{orden.pk}/")
        self.assertContains(pagina, 'class="chip entregado" id="seg-estado"', html=False)     # «Dentro de rango», no «Fuera de rango»
        self.assertContains(pagina, 'id="seg-ruptura" style="margin-top:14px" hidden', html=False)

    def test_una_ruptura_anterior_a_la_entrega_si_se_informa(self):
        cliente, orden, despacho = self.orden_despachada()
        lectura(despacho, 9.0, True)                                        # ocurrió con su carga a bordo
        s.llegar_a_la_puerta([orden])
        s.resolver_entrega(cliente, orden.pk, "aceptar")
        orden.refresh_from_db()
        seg = s.seguimiento(orden)
        self.assertTrue(seg["hubo_ruptura"])

    def test_el_modo_demostracion_no_cambia_una_entrega_ya_cerrada(self):
        cliente, orden, despacho = self.entregada()
        lectura(despacho, 12.0, True, forzada=True)                         # lectura forzada desde el panel de la demostración
        orden.refresh_from_db()
        seg = s.seguimiento(orden)
        self.assertFalse(seg["hubo_ruptura"])
        self.assertFalse(seg["ultima"]["alerta_ruptura_frio"])

    def test_el_resumen_se_arma_aunque_pasara_mas_de_una_hora(self):
        cliente, orden, despacho = self.entregada()
        Orden.objects.filter(pk=orden.pk).update(entrega_resuelta_en=timezone.now() - timedelta(hours=3))
        Telemetria.objects.filter(camion=despacho.camion).update(registrado_en=timezone.now() - timedelta(hours=3, minutes=5))
        Despacho.objects.filter(pk=despacho.pk).update(salida_en=timezone.now() - timedelta(hours=4))     # el viaje salió antes de esa lectura
        orden.refresh_from_db()
        self.assertEqual(len(s.seguimiento(orden)["serie"]), 1)             # la ventana es la hora previa a la entrega, no la hora previa a ahora

    def test_quien_aun_no_recibe_sigue_viendo_la_ruptura(self):
        cliente, orden, despacho = self.orden_despachada()
        s.llegar_a_la_puerta([orden])
        lectura(despacho, 9.0, True)
        orden.refresh_from_db()
        self.assertTrue(s.seguimiento(orden)["hubo_ruptura"])               # en la puerta: la carga sigue a bordo
        s.resolver_entrega(cliente, orden.pk, "no_recibido", "No había nadie en casa")
        orden.refresh_from_db()
        self.assertTrue(s.seguimiento(orden)["hubo_ruptura"])               # entrega sin concretar: sigue a bordo hasta el regreso

    def test_la_revision_al_recibir_y_el_asistente_siguen_la_misma_regla(self):
        cliente, orden, despacho = self.entregada()
        lectura(despacho, 9.0, True)
        orden.refresh_from_db()
        ctx, _ = asistente.construir_contexto("como va mi pedido", cliente, cliente.tipo_cliente, orden_id=orden.pk)
        envio = ctx["pedidos"][0]["envio"]
        self.assertFalse(envio["hubo_ruptura_de_frio_en_la_ultima_hora"])

    def test_el_aviso_de_temperatura_no_aparece_despues_de_entregar(self):
        cliente, orden, despacho = self.entregada()
        lectura(despacho, 9.0, True)
        self.entrar()
        self.assertFalse(any(a["tipo"] == "frio" for a in self.client.get("/api/avisos/").json()["avisos"]))


class RupturaConDosClientesTests(ViajeDeDosClientesBase):
    def test_el_primero_recibe_y_la_ruptura_posterior_solo_afecta_al_segundo(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, p1)
        s.llegar_a_la_puerta([o1])
        s.resolver_entrega(c1, o1.pk, "aceptar")
        lectura(despacho, 9.0, True)                                        # camino a la segunda parada
        o1.refresh_from_db()
        o2.refresh_from_db()
        self.assertFalse(s.seguimiento(o1)["hubo_ruptura"])
        self.assertTrue(s.seguimiento(o2)["hubo_ruptura"])


class SerieDelViajeTests(EntregaBase):
    def test_una_ruptura_de_un_viaje_anterior_no_cuenta_en_el_pedido_nuevo(self):
        cliente, orden, despacho = self.orden_despachada()
        lectura(despacho, 9.0, True)
        Telemetria.objects.filter(camion=despacho.camion).update(registrado_en=timezone.now() - timedelta(minutes=30))
        Despacho.objects.filter(pk=despacho.pk).update(salida_en=timezone.now() - timedelta(minutes=5))      # salió después de esa falla
        orden.refresh_from_db()
        seg = s.seguimiento(orden)
        self.assertFalse(seg["hubo_ruptura"])
        self.assertEqual(seg["serie"], [])
