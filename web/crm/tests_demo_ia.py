"""restablecer_demo_ia: deja «Mi pedido llegó tibio» como lo siembra cargar_demo (sin clasificar) para clasificarlo en vivo en la defensa."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from clientes.models import Cliente
from crm.models import CategoriaRequerimiento, Requerimiento

ASUNTO = "Mi pedido llegó tibio"


def correr():
    salida = StringIO()
    call_command("restablecer_demo_ia", stdout=salida)
    return salida.getvalue()


class RestablecerDemoIA(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)
        cls.sur = Cliente.objects.get(nombre="Supermercados del Sur")

    def demo(self):
        return Requerimiento.objects.filter(cliente=self.sur, asunto=ASUNTO).order_by("pk").first()      # el más antiguo: el que siembra cargar_demo

    def clasificar_en_vivo(self):
        """Lo que deja una demostración o un ensayo: clasificado por la IA, con desglose, respondido y marcado a mano."""
        categoria = CategoriaRequerimiento.objects.first()
        Requerimiento.objects.filter(pk=self.demo().pk).update(
            categoria_requerimiento=categoria, categoria_ia=categoria, confianza_ia="0.93", clasificado_manual=True,
            desglose={"resumen": "x"}, estado="resuelto", respondido_en="2026-11-10T12:00:00Z")

    def test_la_siembra_deja_el_requerimiento_sin_clasificar(self):
        r = self.demo()
        self.assertEqual((r.estado, r.categoria_requerimiento_id, r.categoria_ia_id, r.confianza_ia, r.desglose, r.clasificado_manual, r.respondido_en),
                         ("sin_clasificar", None, None, None, None, False, None))

    def test_deja_sin_clasificar_uno_ya_clasificado(self):
        self.clasificar_en_vivo()
        correr()
        r = self.demo()
        self.assertEqual((r.estado, r.categoria_requerimiento_id, r.categoria_ia_id, r.confianza_ia, r.desglose, r.clasificado_manual, r.respondido_en),
                         ("sin_clasificar", None, None, None, None, False, None))

    def test_el_estado_final_es_el_mismo_que_deja_la_siembra(self):
        antes = Requerimiento.objects.filter(pk=self.demo().pk).values().get()
        self.clasificar_en_vivo()
        correr()
        despues = Requerimiento.objects.filter(pk=antes["requerimiento_id"]).values().get()
        despues.pop("creado_en"), antes.pop("creado_en")             # la fecha de alta no cambia, pero no es lo que se prueba
        self.assertEqual(despues, antes)

    def test_corrida_repetida_no_cambia_nada_ni_duplica(self):
        self.clasificar_en_vivo()
        self.assertIn("restablecido", correr())
        self.assertIn("sin cambios", correr())
        self.assertEqual(Requerimiento.objects.filter(asunto=ASUNTO).count(), 1)

    def test_lo_crea_si_no_existe(self):
        Requerimiento.objects.filter(asunto=ASUNTO).delete()
        self.assertIn("creado", correr())
        r = self.demo()
        self.assertEqual((r.estado, r.cliente_id), ("sin_clasificar", self.sur.pk))
        self.assertIn("rechazamos dos cajas", r.descripcion)
        self.assertIn("sin cambios", correr())
        self.assertEqual(Requerimiento.objects.filter(asunto=ASUNTO).count(), 1)

    def test_no_toca_otros_requerimientos(self):
        otro = Requerimiento.objects.create(cliente=self.sur, asunto="Otra consulta", descripcion="d", estado="clasificado",
                                            categoria_requerimiento=CategoriaRequerimiento.objects.first(), confianza_ia="0.8")
        self.clasificar_en_vivo()
        correr()
        otro.refresh_from_db()
        self.assertEqual((otro.estado, str(otro.confianza_ia)), ("clasificado", "0.80"))

    def test_si_hay_otro_con_el_mismo_asunto_de_otro_cliente_no_lo_toca(self):
        ajeno = Requerimiento.objects.create(cliente=Cliente.objects.exclude(pk=self.sur.pk).first(), asunto=ASUNTO, descripcion="otro",
                                             estado="clasificado", categoria_requerimiento=CategoriaRequerimiento.objects.first(), confianza_ia="0.9")
        self.clasificar_en_vivo()
        correr()
        ajeno.refresh_from_db()
        self.assertEqual((ajeno.estado, ajeno.descripcion), ("clasificado", "otro"))

    def test_avisa_si_hay_duplicados_y_solo_restablece_el_mas_antiguo(self):
        copia = Requerimiento.objects.create(cliente=self.sur, asunto=ASUNTO, descripcion="copia", estado="clasificado",
                                             categoria_requerimiento=CategoriaRequerimiento.objects.first(), confianza_ia="0.9")
        self.clasificar_en_vivo()
        salida = correr()
        self.assertIn("1 más con el mismo asunto", salida)
        copia.refresh_from_db()
        self.assertEqual(copia.estado, "clasificado")
        self.assertEqual(self.demo().estado, "sin_clasificar")

    def test_sin_el_cliente_de_la_demo_explica_que_falta_cargar_datos(self):
        Requerimiento.objects.filter(asunto=ASUNTO).delete()
        Cliente.objects.filter(pk=self.sur.pk).update(rut="1-9")              # el comando busca al cliente por su RUT, como cargar_demo
        with self.assertRaisesMessage(CommandError, "Supermercados del Sur"):
            correr()
