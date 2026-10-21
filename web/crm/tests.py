from django.core.management import call_command
from django.test import TestCase

from clientes.models import Cliente
from crm import servicios as s
from crm.models import EtapaPipeline, Prospecto
from flota.models import Telemetria
from pedidos.models import Orden

CLAVE = "demo-cofrial-2026"


class ReglasDelCrm(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        from django.contrib.auth import get_user_model
        U = get_user_model()
        cls.maria = U.objects.get(username="vendedora@cofrial.test")
        cls.pedro = U.objects.get(username="vendedor2@cofrial.test")
        cls.gerente = U.objects.get(username="gerente@cofrial.test")
        cls.despachador = U.objects.get(username="despachador@cofrial.test")
        cls.ana_user = U.objects.get(username="ana@correo.test")

    def etapa(self, nombre):
        return EtapaPipeline.objects.get(nombre=nombre).pk

    def test_roles(self):
        self.assertEqual([s.rol(u) for u in (self.maria, self.gerente, self.despachador, self.ana_user)],
                         ["vendedor", "gerencia", "despachador", None])

    def test_rn09_cada_vendedor_ve_solo_su_cartera_y_gerencia_ve_todo(self):
        self.assertEqual({c.nombre for c in s.clientes_visibles(self.maria)}, {"Hospital Regional de Temuco"})
        self.assertEqual({c.nombre for c in s.clientes_visibles(self.pedro)}, {"Supermercados del Sur"})
        self.assertGreaterEqual(s.clientes_visibles(self.gerente).count(), 3)
        propios = s.prospectos_visibles(self.maria)
        self.assertTrue(all(p.vendedor.usuario == self.maria for p in propios))
        self.assertGreater(s.prospectos_visibles(self.gerente).count(), propios.count())

    def test_rn10_no_se_puede_saltar_etapas(self):
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")            # etapa Prospecto, de María
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Negociación"))
        with self.assertRaises(s.ErrorDeNegocio):                            # no se puede ni a Cliente ganado
            s.mover_prospecto(self.maria, p.pk, self.etapa("Cliente ganado"), rut="1-9")

    def test_contactado_exige_una_interaccion(self):
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado"))
        s.registrar_interaccion(self.maria, "llamada", "Primera llamada", prospecto=p)      # RN-12
        self.assertEqual(s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado")).etapa.nombre, "Contactado")

    def test_rn11_perder_exige_motivo_y_registra_cierre(self):
        p = Prospecto.objects.get(nombre_contacto="Carla Muñoz")
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Perdido"))
        perdido = s.mover_prospecto(self.maria, p.pk, self.etapa("Perdido"), motivo="Eligió otro proveedor")
        self.assertIsNotNone(perdido.cerrado_en)
        self.assertEqual(perdido.motivo_perdida, "Eligió otro proveedor")
        with self.assertRaises(s.ErrorDeNegocio):                            # una etapa final no sale de ahí
            s.mover_prospecto(self.maria, p.pk, self.etapa("Contactado"))

    def test_rn11_ganar_crea_cliente_b2b_con_el_mismo_vendedor(self):
        p = Prospecto.objects.get(nombre_contacto="Rosa Vega")              # Negociación, de Pedro
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"))   # falta el RUT
        ganado = s.mover_prospecto(self.pedro, p.pk, self.etapa("Cliente ganado"), rut="77.111.222-3")
        self.assertEqual(ganado.cliente.tipo_cliente.codigo, "B2B")
        self.assertEqual(ganado.cliente.vendedor.usuario, self.pedro)
        self.assertIsNotNone(ganado.cerrado_en)

    def test_un_vendedor_no_mueve_prospectos_ajenos_y_gerencia_no_escribe(self):
        p = Prospecto.objects.get(nombre_contacto="Luis Soto")              # de Pedro
        with self.assertRaises(Prospecto.DoesNotExist):
            s.mover_prospecto(self.maria, p.pk, self.etapa("Negociación"))
        with self.assertRaises(s.ErrorDeNegocio):
            s.mover_prospecto(self.gerente, p.pk, self.etapa("Negociación"))

    def test_rn13_alerta_de_frio_marca_las_ordenes_del_viaje(self):
        hospital = Cliente.objects.get(rut="61.973.200-4")
        orden = Orden.objects.get(direccion__cliente=hospital)
        antes = s.ordenes_de_cliente(hospital)[0].alertas_frio
        despacho = orden.despacho
        Telemetria.objects.create(camion_id=despacho.camion_id, temp_camara=9.0, lat=-38.7, long=-72.6, combustible_pct=50, alerta_ruptura_frio=True)
        self.assertEqual(s.ordenes_de_cliente(hospital)[0].alertas_frio, antes + 1)
        afectadas = {o.orden_id for o in s.ordenes_afectadas(self.maria)}
        self.assertIn(orden.orden_id, afectadas)
        self.assertNotIn(orden.orden_id, {o.orden_id for o in s.ordenes_afectadas(self.pedro)})    # no es de su cartera

    def test_rn15_pedido_a_nombre_del_cliente_exige_la_interaccion(self):
        hospital = Cliente.objects.get(rut="61.973.200-4")
        from catalogo.models import Producto
        lomo = Producto.objects.get(sku="VAC-LOM-5K")
        dir_id = hospital.direccion_set.first().pk
        with self.assertRaises(s.ErrorDeNegocio):
            s.crear_pedido_para_cliente(self.maria, hospital.pk, {lomo.pk: 2}, dir_id, "OC-9", "whatsapp", "x")
        antes = Orden.objects.count()
        orden = s.crear_pedido_para_cliente(self.maria, hospital.pk, {lomo.pk: 2}, dir_id, "OC-9", "llamada", "Pidió 2 cajas por teléfono")
        self.assertEqual(Orden.objects.count(), antes + 1)
        self.assertTrue(hospital.interaccion_set.filter(tipo="llamada", detalle__contains="2 cajas").exists())
        self.assertEqual(orden.estado_orden.nombre, "Recibida")

    def test_indicadores_propios_vs_todos(self):
        self.assertLess(s.indicadores(self.maria)["abiertos"], s.indicadores(self.gerente)["abiertos"])


class AccesoWeb(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def entrar(self, usuario):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))

    def test_clientes_del_portal_no_entran_al_crm(self):
        self.entrar("ana@correo.test")
        self.assertEqual(self.client.get("/crm/").status_code, 403)

    def test_vendedor_no_ve_la_ficha_de_otro_vendedor(self):
        self.entrar("vendedora@cofrial.test")
        sur = Cliente.objects.get(rut="76.543.210-K")
        self.assertEqual(self.client.get(f"/crm/clientes/{sur.pk}/").status_code, 404)
        hospital = Cliente.objects.get(rut="61.973.200-4")
        self.assertContains(self.client.get(f"/crm/clientes/{hospital.pk}/"), "Hospital Regional")

    def test_despachador_solo_ve_alertas(self):
        self.entrar("despachador@cofrial.test")
        self.assertEqual(self.client.get("/crm/clientes/").status_code, 403)
        self.assertEqual(self.client.get("/crm/alertas/").status_code, 200)
        self.assertRedirects(self.client.get("/crm/"), "/crm/alertas/")

    def test_flujo_del_vendedor_en_el_navegador(self):
        self.entrar("vendedora@cofrial.test")
        r = self.client.post("/crm/prospectos/nuevo/", {"nombre_contacto": "Sofía Paz", "empresa": "Residencial Sur", "email": "sofia@res.test", "origen": "referido", "monto": "2500000"}, follow=True)
        self.assertContains(r, "Residencial Sur")
        self.assertContains(self.client.get("/crm/embudo/"), "Residencial Sur")
        self.assertContains(self.client.get("/crm/"), "oportunidades abiertas")

    def test_gerencia_ve_todo_pero_no_modifica(self):
        self.entrar("gerente@cofrial.test")
        self.assertContains(self.client.get("/crm/embudo/"), "Casino Escolar")
        p = Prospecto.objects.get(nombre_contacto="Jorge Rivas")
        self.client.post(f"/crm/prospectos/{p.pk}/interaccion/", {"tipo": "nota", "detalle": "intento"})
        self.assertFalse(p.interaccion_set.exists())
