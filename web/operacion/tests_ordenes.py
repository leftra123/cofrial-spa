"""Órdenes desde /operacion/ordenes/: pasan siempre por las reglas de pedidos.servicios y nunca se tocan en pleno viaje."""
from catalogo.models import Producto
from flota.models import Despacho
from operacion import servicios as s
from pedidos.models import EstadoOrden, Orden

from .tests_datos import Base


class Ordenes(Base):
    def orden(self, estado, despacho=None):
        o = Orden.objects.exclude(ordenitem=None).order_by("orden_id").first()
        Orden.objects.filter(pk=o.pk).update(estado_orden=EstadoOrden.objects.get(nombre=estado), despacho=despacho)
        o.refresh_from_db()
        return o

    def test_permisos(self):
        o = self.orden("Recibida")
        for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            c = self.entrar(u)
            self.assertEqual(c.get("/operacion/ordenes/").status_code, 403, u)
            self.assertEqual(c.post(f"/operacion/ordenes/{o.pk}/avanzar/").status_code, 403, u)
            self.assertEqual(c.post(f"/operacion/ordenes/{o.pk}/cancelar/").status_code, 403, u)

    def test_avanzar_de_recibida_a_confirmada(self):
        o = self.orden("Recibida")
        self.admin.post(f"/operacion/ordenes/{o.pk}/avanzar/")
        o.refresh_from_db()
        self.assertEqual(o.estado_orden.nombre, "Confirmada")

    def test_avanzar_por_get_no_se_permite(self):
        o = self.orden("Recibida")
        self.assertEqual(self.admin.get(f"/operacion/ordenes/{o.pk}/avanzar/").status_code, 405)

    def test_boton_avanzar_por_estado(self):
        despacho = Despacho.objects.first()
        casos = [("Recibida", None, True), ("Confirmada", None, True), ("En preparación", None, False), ("En preparación", despacho, True),
                 ("Despachada", despacho, False), ("Camión en la puerta", despacho, False), ("Entregada", despacho, False), ("Cancelada", None, False)]
        for estado, d, esperado in casos:
            self.assertEqual(s.puede_avanzar(self.orden(estado, d)), esperado, (estado, d))

    def test_post_a_orden_en_viaje_no_avanza(self):
        despacho = Despacho.objects.first()
        for estado in ("Despachada", "Camión en la puerta"):
            o = self.orden(estado, despacho)
            r = self.admin.post(f"/operacion/ordenes/{o.pk}/avanzar/", follow=True)
            o.refresh_from_db()
            self.assertEqual(o.estado_orden.nombre, estado)
            self.assertIn("no avanza", self.mensajes(r))

    def test_cancelar_repone_stock(self):
        o = self.orden("Recibida")
        item = o.ordenitem_set.first()
        antes = Producto.objects.get(pk=item.producto_id).stock_disponible
        self.admin.post(f"/operacion/ordenes/{o.pk}/cancelar/")
        o.refresh_from_db()
        self.assertEqual(o.estado_orden.nombre, "Cancelada")
        self.assertEqual(Producto.objects.get(pk=item.producto_id).stock_disponible, antes + item.cantidad)

    def test_cancelar_fuera_de_plazo_avisa(self):
        o = self.orden("Entregada", Despacho.objects.first())
        r = self.admin.post(f"/operacion/ordenes/{o.pk}/cancelar/", follow=True)
        self.assertIn("ya no puede cancelarla", self.mensajes(r))
        o.refresh_from_db()
        self.assertEqual(o.estado_orden.nombre, "Entregada")

    def test_orden_inexistente_da_404(self):
        self.assertEqual(self.admin.post("/operacion/ordenes/999999/avanzar/").status_code, 404)

    def test_filtro_por_estado(self):
        o = self.orden("Recibida")
        html = self.admin.get("/operacion/ordenes/?estado=Recibida").content.decode()
        self.assertIn(f"N.º {o.pk}", html)
        self.assertNotIn(f"N.º {o.pk}", self.admin.get("/operacion/ordenes/?estado=Cancelada").content.decode())

    def test_estado_inexistente_se_ignora(self):
        self.assertEqual(self.admin.get("/operacion/ordenes/?estado=no-existe").status_code, 200)

    def test_busqueda_por_cliente(self):
        o = self.orden("Recibida")
        nombre = o.direccion.cliente.nombre
        self.assertContains(self.admin.get("/operacion/ordenes/", {"q": nombre}), f"N.º {o.pk}")
        self.assertNotContains(self.admin.get("/operacion/ordenes/", {"q": "nadie-se-llama-asi"}), f"N.º {o.pk}")
