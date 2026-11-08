"""Productos y precios desde /operacion/productos/: nunca se pisa el stock vendido y un precio malo no deja nada a medias."""
from catalogo.models import Categoria, ListaPrecio, PrecioProducto, Producto

from .tests_datos import Base


class Productos(Base):
    def setUp(self):
        super().setUp()
        self.b2b = ListaPrecio.objects.get(nombre="Institucional B2B")
        self.b2c = ListaPrecio.objects.get(nombre="Público B2C")
        self.p = Producto.objects.get(sku="VAC-LOM-5K")

    def datos(self, **extra):
        p = self.p
        return {"sku": p.sku, "nombre": p.nombre, "descripcion": p.descripcion, "categoria": p.categoria_id, "unidad_medida": p.unidad_medida, "activo": "on",
                f"precio_{self.b2b.pk}": 38990, f"precio_{self.b2c.pk}": 45990} | extra

    def nuevo(self, **extra):
        return self.datos(sku="NUE-001", nombre="Producto nuevo", stock_inicial=30, **extra)

    def precio(self, lista, producto=None):
        return PrecioProducto.objects.filter(lista_precio=lista, producto=producto or self.p).values_list("precio_clp", flat=True).first()

    def test_permisos(self):
        for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            c = self.entrar(u)
            for url in ("/operacion/productos/", "/operacion/productos/nuevo/", f"/operacion/productos/{self.p.pk}/"):
                self.assertEqual(c.get(url).status_code, 403, (u, url))

    def test_lista_con_busqueda(self):
        html = self.admin.get("/operacion/productos/?q=VAC-LOM").content.decode()
        self.assertIn("Lomo vetado", html)
        self.assertNotIn("Pechuga de pollo", html)

    def test_crear_con_precios_y_stock_inicial(self):
        r = self.admin.post("/operacion/productos/nuevo/", self.nuevo())
        self.assertRedirects(r, "/operacion/productos/")
        p = Producto.objects.get(sku="NUE-001")
        self.assertEqual(p.stock_disponible, 30)
        self.assertEqual((self.precio(self.b2b, p), self.precio(self.b2c, p)), (38990, 45990))

    def test_editar_precios(self):
        self.admin.post(f"/operacion/productos/{self.p.pk}/", self.datos(**{f"precio_{self.b2c.pk}": 50000}))
        self.assertEqual(self.precio(self.b2c), 50000)

    def test_editar_no_toca_el_stock(self):
        self.admin.get(f"/operacion/productos/{self.p.pk}/")
        Producto.objects.filter(pk=self.p.pk).update(stock_disponible=7)        # una venta mientras el formulario estaba abierto
        r = self.admin.post(f"/operacion/productos/{self.p.pk}/", self.datos(nombre="Otro nombre", stock_disponible=0, stock_inicial=500))
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual((self.p.nombre, self.p.stock_disponible), ("Otro nombre", 7))

    def test_precio_vacio_quita_de_la_lista(self):
        self.admin.post(f"/operacion/productos/{self.p.pk}/", self.datos(**{f"precio_{self.b2c.pk}": ""}))
        self.assertIsNone(self.precio(self.b2c))
        self.assertEqual(self.precio(self.b2b), 38990)

    def test_precio_invalido_no_guarda_nada(self):
        for malo in ("-1", "0", "abc", "2147483648", "1.5"):
            r = self.admin.post(f"/operacion/productos/{self.p.pk}/", self.datos(nombre="No debe guardarse", **{f"precio_{self.b2b.pk}": 11111, f"precio_{self.b2c.pk}": malo}))
            self.assertEqual(r.status_code, 200, malo)
            self.assertTrue(r.context["form"].errors[f"precio_{self.b2c.pk}"], malo)
            self.p.refresh_from_db()
            self.assertNotEqual(self.p.nombre, "No debe guardarse", malo)
            self.assertNotEqual(self.precio(self.b2b), 11111, malo)

    def test_sku_repetido_es_error(self):
        r = self.admin.post("/operacion/productos/nuevo/", self.datos(stock_inicial=1))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors["sku"])

    def test_stock_inicial_invalido_es_error(self):
        for malo in ("-1", "100001"):
            r = self.admin.post("/operacion/productos/nuevo/", self.datos(sku="NUE-002", stock_inicial=malo))
            self.assertEqual(r.status_code, 200, malo)
        self.assertFalse(Producto.objects.filter(sku="NUE-002").exists())

    def test_nuevo_aparece_en_catalogo_sin_foto(self):
        self.admin.post("/operacion/productos/nuevo/", self.nuevo())
        p = Producto.objects.get(sku="NUE-001")
        self.assertContains(Base.client_class().get("/catalogo/"), "Producto nuevo")
        self.assertEqual(Base.client_class().get(f"/catalogo/{p.pk}/").status_code, 200)

    def test_desactivar_lo_oculta_del_catalogo(self):
        datos = self.datos()
        del datos["activo"]
        self.admin.post(f"/operacion/productos/{self.p.pk}/", datos)
        self.assertNotContains(Base.client_class().get("/catalogo/"), self.p.nombre)

    def test_no_hay_ruta_de_borrar(self):
        self.assertEqual(self.admin.post(f"/operacion/productos/{self.p.pk}/borrar/").status_code, 404)
