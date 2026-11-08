from django.test import TestCase

from catalogo.models import ListaPrecio
from clientes.models import Cliente, SegmentoCliente, TipoCliente


class SegmentoClienteTests(TestCase):
    def _cliente(self, segmento=None):
        lista = ListaPrecio.objects.first() or ListaPrecio.objects.create(nombre="Lista de prueba")
        tipo = TipoCliente.objects.filter(codigo="B2B").first() or TipoCliente.objects.create(
            codigo="B2B", nombre="Institucional", lista_precio=lista)
        return Cliente.objects.create(tipo_cliente=tipo, rut="11111111-1", nombre="Cliente de prueba",
                                      email="prueba@example.com", segmento=segmento)

    def test_los_cuatro_segmentos_existen(self):
        self.assertEqual(set(SegmentoCliente.objects.values_list("nombre", flat=True)),
                         {"Hospital", "Supermercado", "Feria", "Institucional"})

    def test_cliente_sin_segmento_es_valido(self):
        cliente = self._cliente(segmento=None)
        cliente.full_clean(exclude=["usuario"])

    def test_borrar_segmento_no_borra_cliente(self):
        segmento = SegmentoCliente.objects.get(nombre="Hospital")
        cliente = self._cliente(segmento=segmento)
        segmento.delete()
        cliente.refresh_from_db()
        self.assertIsNone(cliente.segmento_id)
