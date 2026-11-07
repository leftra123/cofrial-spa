"""Panel común de /operacion/datos/: permisos, altas, ediciones y borrados, y lo que no se puede tocar."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from catalogo.models import Categoria, ListaPrecio, RangoTemperatura
from clientes.models import Cliente, Comuna, Direccion, Region, TipoCliente, Vendedor
from crm.models import CategoriaRequerimiento, EtapaPipeline, Prospecto, Requerimiento
from flota.models import Camion
from pedidos.models import EstadoOrden, Orden

Usuario = get_user_model()

CLAVE = "demo-cofrial-2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", verbosity=0)

    def setUp(self):
        self.admin = self.entrar()

    def entrar(self, usuario="admin@cofrial.cl"):
        c = Client()
        self.assertTrue(c.login(username=usuario, password=CLAVE), usuario)
        return c

    def mensajes(self, r):
        return " ".join(str(m) for m in r.context["messages"])


class Permisos(Base):
    RUTAS = ("/operacion/datos/", "/operacion/datos/categorias/", "/operacion/datos/categorias/nuevo/")

    def test_anonimo_va_a_ingresar(self):
        for url in self.RUTAS:
            r = Client().get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/cuenta/entrar/", r["Location"])

    def test_el_resto_de_los_roles_recibe_403(self):
        for u in ("vendedora@cofrial.cl", "gerencia@cofrial.cl", "despacho@cofrial.cl", "ana@correo.test"):
            c = self.entrar(u)
            for url in self.RUTAS:
                self.assertEqual(c.get(url).status_code, 403, (u, url))
            self.assertEqual(c.post("/operacion/datos/categorias/nuevo/", {"nombre": "X"}).status_code, 403, u)

    def test_admin_entra(self):
        for url in self.RUTAS:
            self.assertEqual(self.admin.get(url).status_code, 200, url)

    def test_indice_lista_las_tablas(self):
        html = self.admin.get("/operacion/datos/").content.decode()
        for slug in ("categorias", "rangos", "listas", "regiones", "comunas", "camiones", "tipos-cliente", "estados-orden"):
            self.assertIn(f'href="/operacion/datos/{slug}/"', html)


class Categorias(Base):
    def test_crear_editar_y_borrar(self):
        rango = RangoTemperatura.objects.first()
        r = self.admin.post("/operacion/datos/categorias/nuevo/", {"nombre": "Helados", "rango_temperatura": rango.pk})
        self.assertRedirects(r, "/operacion/datos/categorias/")
        cat = Categoria.objects.get(nombre="Helados")
        self.admin.post(f"/operacion/datos/categorias/{cat.pk}/", {"nombre": "Helados y postres", "rango_temperatura": rango.pk})
        cat.refresh_from_db()
        self.assertEqual(cat.nombre, "Helados y postres")
        self.admin.post(f"/operacion/datos/categorias/{cat.pk}/borrar/")
        self.assertFalse(Categoria.objects.filter(pk=cat.pk).exists())

    def test_borrar_con_productos_avisa(self):
        cat = Categoria.objects.get(nombre="Aves")
        r = self.admin.post(f"/operacion/datos/categorias/{cat.pk}/borrar/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("No se puede borrar", self.mensajes(r))
        self.assertTrue(Categoria.objects.filter(pk=cat.pk).exists())

    def test_borrar_por_get_no_se_permite(self):
        cat = Categoria.objects.get(nombre="Aves")
        self.assertEqual(self.admin.get(f"/operacion/datos/categorias/{cat.pk}/borrar/").status_code, 405)

    def test_nombre_repetido_es_error_de_campo(self):
        rango = RangoTemperatura.objects.first()
        r = self.admin.post("/operacion/datos/categorias/nuevo/", {"nombre": "Aves", "rango_temperatura": rango.pk})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors["nombre"])

    def test_busqueda(self):
        html = self.admin.get("/operacion/datos/categorias/?q=aves").content.decode()
        self.assertIn("Aves", html)
        self.assertNotIn("Congelados", html)

    def test_busqueda_con_simbolos_no_falla(self):
        self.assertEqual(self.admin.get("/operacion/datos/categorias/?q=%25%27%22%3C").status_code, 200)


class UrlsManipuladas(Base):
    def test_slug_y_pk_inexistentes_dan_404(self):
        for url in ("/operacion/datos/no-existe/", "/operacion/datos/no-existe/nuevo/", "/operacion/datos/categorias/999999/", "/operacion/datos/categorias/abc/"):
            self.assertEqual(self.admin.get(url).status_code, 404, url)
        self.assertEqual(self.admin.post("/operacion/datos/categorias/999999/borrar/").status_code, 404)


class Camiones(Base):
    def datos(self, **extra):
        return {"camion_id": "CAM-99", "patente": "ZZZZ99", "capacidad_kg": 1000, "rango_temperatura": RangoTemperatura.objects.first().pk, "activo": "on"} | extra

    def test_se_edita_por_su_codigo_sin_cambiarlo(self):
        self.assertEqual(self.admin.get("/operacion/datos/camiones/CAM-01/").status_code, 200)
        camion = Camion.objects.get(pk="CAM-01")
        r = self.admin.post("/operacion/datos/camiones/CAM-01/", self.datos(camion_id="CAM-77", patente=camion.patente, capacidad_kg=4321))
        self.assertEqual(r.status_code, 302)
        camion.refresh_from_db()
        self.assertEqual(camion.capacidad_kg, 4321)
        self.assertFalse(Camion.objects.filter(pk="CAM-77").exists())

    def test_nuevo_avisa_del_simulador(self):
        html = self.admin.get("/operacion/datos/camiones/nuevo/").content.decode()
        self.assertIn("CAM-01", html)
        self.assertIn("CAM-50", html)

    def test_codigo_con_caracteres_raros_es_error(self):
        for codigo in ("cam/1", "nuevo", "CAM 1"):
            r = self.admin.post("/operacion/datos/camiones/nuevo/", self.datos(camion_id=codigo))
            self.assertEqual(r.status_code, 200, codigo)
            self.assertTrue(r.context["form"].errors["camion_id"], codigo)

    def test_capacidad_negativa_no_da_500(self):
        r = self.admin.post("/operacion/datos/camiones/nuevo/", self.datos(capacidad_kg=-5))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Camion.objects.filter(pk="CAM-99").exists())

    def test_camion_con_viajes_no_se_borra(self):
        from flota.models import Despacho
        camion = Despacho.objects.first().camion
        r = self.admin.post(f"/operacion/datos/camiones/{camion.pk}/borrar/", follow=True)
        self.assertIn("No se puede borrar", self.mensajes(r))
        self.assertTrue(Camion.objects.filter(pk=camion.pk).exists())


class Limites(Base):
    def test_rango_no_cambia_de_nombre(self):
        rango = RangoTemperatura.objects.get(nombre="Refrigerado")
        self.admin.post(f"/operacion/datos/rangos/{rango.pk}/", {"nombre": "Otro", "temp_min_c": "1.0", "temp_max_c": "5.0"})
        rango.refresh_from_db()
        self.assertEqual(rango.nombre, "Refrigerado")
        self.assertEqual(str(rango.temp_min_c), "1.0")

    def test_tipo_cliente_no_cambia_de_codigo(self):
        tipo = TipoCliente.objects.get(codigo="B2C")
        lista = ListaPrecio.objects.get(nombre="Institucional B2B")
        self.admin.post(f"/operacion/datos/tipos-cliente/{tipo.pk}/", {"codigo": "B2B", "nombre": "Cambiado", "lista_precio": lista.pk, "dias_credito": 15})
        tipo.refresh_from_db()
        self.assertEqual((tipo.codigo, tipo.nombre, tipo.lista_precio_id, tipo.dias_credito), ("B2C", "Público general", lista.pk, 15))

    def test_tipos_de_cliente_no_se_crean_ni_borran(self):
        tipo = TipoCliente.objects.get(codigo="B2C")
        self.assertEqual(self.admin.post("/operacion/datos/tipos-cliente/nuevo/", {}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/tipos-cliente/{tipo.pk}/borrar/").status_code, 403)

    def test_estados_de_orden_son_solo_lectura(self):
        estado = EstadoOrden.objects.get(nombre="Recibida")
        self.assertContains(self.admin.get("/operacion/datos/estados-orden/"), "Recibida")
        self.assertEqual(self.admin.post("/operacion/datos/estados-orden/nuevo/", {"nombre": "X", "orden_flujo": 99}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/estados-orden/{estado.pk}/", {"nombre": "X", "orden_flujo": 1}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/estados-orden/{estado.pk}/borrar/").status_code, 403)
        estado.refresh_from_db()
        self.assertEqual(estado.nombre, "Recibida")

    def test_comuna_repetida_en_la_region_no_da_500(self):
        comuna = Comuna.objects.get(nombre="Temuco")
        r = self.admin.post("/operacion/datos/comunas/nuevo/", {"region": comuna.region_id, "nombre": "Temuco"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Comuna.objects.filter(nombre="Temuco").count(), 1)

    def test_region_con_comunas_no_se_borra(self):
        region = Region.objects.get(nombre="La Araucanía")
        self.admin.post(f"/operacion/datos/regiones/{region.pk}/borrar/")
        self.assertTrue(Region.objects.filter(pk=region.pk).exists())


class Etapas(Base):
    def datos(self, etapa, **extra):
        return {"nombre": etapa.nombre, "orden_etapa": etapa.orden_etapa} | ({"es_final": "on"} if etapa.es_final else {}) | ({"es_ganada": "on"} if etapa.es_ganada else {}) | extra

    def test_etapas_fijas_no_se_renombran(self):
        etapa = EtapaPipeline.objects.get(nombre="Contactado")
        r = self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/", self.datos(etapa, nombre="Llamado"))
        self.assertEqual(r.status_code, 200)
        etapa.refresh_from_db()
        self.assertEqual(etapa.nombre, "Contactado")

    def test_etapas_fijas_no_se_borran(self):
        etapa = EtapaPipeline.objects.get(nombre="Propuesta enviada")
        Prospecto.objects.filter(etapa=etapa).delete()
        r = self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/borrar/", follow=True)
        self.assertIn("No se puede borrar", self.mensajes(r))
        self.assertTrue(EtapaPipeline.objects.filter(pk=etapa.pk).exists())

    def test_otra_etapa_si_se_renombra(self):
        etapa = EtapaPipeline.objects.get(nombre="Negociación")
        self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/", self.datos(etapa, nombre="Cierre comercial"))
        etapa.refresh_from_db()
        self.assertEqual(etapa.nombre, "Cierre comercial")

    def test_no_se_quita_la_unica_ganada_al_editar(self):
        etapa = EtapaPipeline.objects.get(es_ganada=True)
        datos = self.datos(etapa)
        del datos["es_ganada"]
        r = self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/", datos)
        self.assertEqual(r.status_code, 200)
        etapa.refresh_from_db()
        self.assertTrue(etapa.es_ganada)

    def test_no_se_borra_la_unica_ganada(self):
        etapa = EtapaPipeline.objects.get(es_ganada=True)
        Prospecto.objects.filter(etapa=etapa).delete()
        self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/borrar/")
        self.assertTrue(EtapaPipeline.objects.filter(pk=etapa.pk).exists())

    def test_no_se_quita_la_unica_perdida(self):
        etapa = EtapaPipeline.objects.get(es_final=True, es_ganada=False)
        r = self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/", self.datos(etapa, es_ganada="on"))
        self.assertEqual(r.status_code, 200)
        etapa.refresh_from_db()
        self.assertFalse(etapa.es_ganada)
        Prospecto.objects.filter(etapa=etapa).delete()
        self.admin.post(f"/operacion/datos/etapas/{etapa.pk}/borrar/")
        self.assertTrue(EtapaPipeline.objects.filter(pk=etapa.pk).exists())

    def test_ganada_sin_final_no_da_500(self):
        r = self.admin.post("/operacion/datos/etapas/nuevo/", {"nombre": "Rara", "orden_etapa": 50, "es_ganada": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(EtapaPipeline.objects.filter(nombre="Rara").exists())


class CategoriasRequerimiento(Base):
    def test_categorias_fijas_no_se_renombran(self):
        for nombre in ("Reclamo por temperatura", "Problema en la entrega"):
            cat = CategoriaRequerimiento.objects.get(nombre=nombre)
            r = self.admin.post(f"/operacion/datos/categorias-requerimiento/{cat.pk}/", {"nombre": "Otra"})
            self.assertEqual(r.status_code, 200, nombre)
            cat.refresh_from_db()
            self.assertEqual(cat.nombre, nombre)

    def test_categorias_fijas_no_se_borran(self):
        cat = CategoriaRequerimiento.objects.get(nombre="Problema en la entrega")
        r = self.admin.post(f"/operacion/datos/categorias-requerimiento/{cat.pk}/borrar/", follow=True)
        self.assertIn("No se puede borrar", self.mensajes(r))
        self.assertTrue(CategoriaRequerimiento.objects.filter(pk=cat.pk).exists())

    def test_otra_categoria_se_crea_y_borra(self):
        self.admin.post("/operacion/datos/categorias-requerimiento/nuevo/", {"nombre": "Sugerencia"})
        cat = CategoriaRequerimiento.objects.get(nombre="Sugerencia")
        self.admin.post(f"/operacion/datos/categorias-requerimiento/{cat.pk}/borrar/")
        self.assertFalse(CategoriaRequerimiento.objects.filter(nombre="Sugerencia").exists())


class Prospectos(Base):
    def setUp(self):
        super().setUp()
        self.p = Prospecto.objects.exclude(email="").first()

    def datos(self, **extra):
        p = self.p
        return {"nombre_contacto": p.nombre_contacto, "empresa": p.empresa, "email": p.email, "telefono": p.telefono, "origen": p.origen,
                "monto_estimado_clp": p.monto_estimado_clp or "", "vendedor": p.vendedor_id} | extra

    def test_no_cambia_de_etapa(self):
        otra = EtapaPipeline.objects.exclude(pk=self.p.etapa_id).first()
        self.admin.post(f"/operacion/datos/prospectos/{self.p.pk}/", self.datos(etapa=otra.pk, empresa="Empresa Editada"))
        etapa = self.p.etapa_id
        self.p.refresh_from_db()
        self.assertEqual((self.p.etapa_id, self.p.empresa), (etapa, "Empresa Editada"))

    def test_sin_correo_ni_telefono_es_error(self):
        r = self.admin.post(f"/operacion/datos/prospectos/{self.p.pk}/", self.datos(email="", telefono=""))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)

    def test_no_se_crean_ni_borran_aqui(self):
        self.assertEqual(self.admin.post("/operacion/datos/prospectos/nuevo/", {}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/prospectos/{self.p.pk}/borrar/").status_code, 403)


class Clientes(Base):
    def setUp(self):
        super().setUp()
        self.c = Cliente.objects.get(usuario__username="abastecimiento@hospital.test")

    def datos(self, **extra):
        c = self.c
        return {"nombre": c.nombre, "rut": c.rut, "email": c.email, "telefono": c.telefono, "giro": c.giro, "vendedor": c.vendedor_id or ""} | extra

    def solicitud(self):
        u = Usuario.objects.create_user("pendiente@empresa.test", password=CLAVE, is_active=False)
        return Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2B"), rut="76.086.428-5", nombre="Pendiente SpA", email="pendiente@empresa.test")

    def test_edita_datos(self):
        self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/", self.datos(telefono="+56900000000"))
        self.c.refresh_from_db()
        self.assertEqual(self.c.telefono, "+56900000000")

    def test_rut_invalido_es_error(self):
        r = self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/", self.datos(rut="11.111.111-2"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors["rut"])

    def test_rut_repetido_con_otro_formato_es_error(self):
        otro = Cliente.objects.exclude(pk=self.c.pk).first()
        r = self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/", self.datos(rut=otro.rut.replace(".", "")))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors["rut"])

    def test_rut_se_guarda_con_formato(self):
        self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/", self.datos(rut="760864285"))
        self.c.refresh_from_db()
        self.assertEqual(self.c.rut, "76.086.428-5")

    def test_solicitud_pendiente_no_se_edita(self):
        c = self.solicitud()
        vendedor = Vendedor.objects.first()
        r = self.admin.post(f"/operacion/datos/clientes/{c.pk}/", {"nombre": "Otro", "rut": c.rut, "email": c.email, "vendedor": vendedor.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Solicitudes")
        c.refresh_from_db()
        self.assertEqual((c.nombre, c.vendedor_id), ("Pendiente SpA", None))

    def test_no_se_quita_vendedor_si_lo_vuelve_solicitud(self):
        Usuario.objects.filter(pk=self.c.usuario_id).update(is_active=False)
        self.assertIsNotNone(self.c.vendedor_id)
        r = self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/", self.datos(vendedor=""))
        self.assertEqual(r.status_code, 200)
        self.c.refresh_from_db()
        self.assertIsNotNone(self.c.vendedor_id)

    def test_no_se_crean_ni_borran_aqui(self):
        self.assertEqual(self.admin.post("/operacion/datos/clientes/nuevo/", {}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/clientes/{self.c.pk}/borrar/").status_code, 403)


class Direcciones(Base):
    def setUp(self):
        super().setUp()
        self.d = Direccion.objects.exclude(orden__isnull=False).filter(lat__isnull=False).first() or Direccion.objects.exclude(orden__isnull=False).first()
        Direccion.objects.filter(pk=self.d.pk).update(lat=-38.7, long=-72.6)
        self.d.refresh_from_db()

    def datos(self, d=None, **extra):
        d = d or self.d
        return {"calle_numero": d.calle_numero, "comuna": d.comuna_id, "referencia": d.referencia} | ({"es_principal": "on"} if d.es_principal else {}) | extra

    def test_con_orden_en_curso_no_se_edita(self):
        d = Orden.objects.filter(estado_orden__es_final=False).first().direccion
        r = self.admin.post(f"/operacion/datos/direcciones/{d.pk}/", self.datos(d, calle_numero="Otra calle 1"))
        self.assertEqual(r.status_code, 200)
        calle = d.calle_numero
        d.refresh_from_db()
        self.assertEqual(d.calle_numero, calle)

    def test_cambiar_calle_borra_coordenadas(self):
        self.admin.post(f"/operacion/datos/direcciones/{self.d.pk}/", self.datos(calle_numero="Calle Nueva 123"))
        self.d.refresh_from_db()
        self.assertEqual((self.d.calle_numero, self.d.lat, self.d.long), ("Calle Nueva 123", None, None))

    def test_cambiar_referencia_conserva_coordenadas(self):
        self.admin.post(f"/operacion/datos/direcciones/{self.d.pk}/", self.datos(referencia="Portón azul"))
        self.d.refresh_from_db()
        self.assertEqual(self.d.lat, -38.7)

    def test_una_sola_direccion_principal(self):
        cliente = self.d.cliente
        Direccion.objects.filter(cliente=cliente).update(es_principal=False)
        Direccion.objects.filter(pk=self.d.pk).update(es_principal=True)
        otra = Direccion.objects.create(cliente=cliente, calle_numero="Segunda 2", comuna=self.d.comuna)
        r = self.admin.post(f"/operacion/datos/direcciones/{otra.pk}/", self.datos(otra, es_principal="on"))
        self.assertEqual(r.status_code, 302)
        self.d.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual((self.d.es_principal, otra.es_principal), (False, True))

    def test_con_ordenes_no_se_borra(self):
        d = Orden.objects.first().direccion
        self.admin.post(f"/operacion/datos/direcciones/{d.pk}/borrar/")
        self.assertTrue(Direccion.objects.filter(pk=d.pk).exists())


class Vendedores(Base):
    def test_solo_edita_nombre_y_telefono(self):
        v = Vendedor.objects.first()
        self.admin.post(f"/operacion/datos/vendedores/{v.pk}/", {"nombre": "Nombre Nuevo", "telefono": "+56911111111"})
        activo = v.activo
        v.refresh_from_db()
        self.assertEqual((v.nombre, v.telefono, v.activo), ("Nombre Nuevo", "+56911111111", activo))
        self.admin.post(f"/operacion/datos/vendedores/{v.pk}/", {"nombre": "Nombre Nuevo", "telefono": "", "activo": ""})
        v.refresh_from_db()
        self.assertTrue(v.activo)

    def test_no_se_crean_ni_borran_aqui(self):
        v = Vendedor.objects.first()
        self.assertEqual(self.admin.post("/operacion/datos/vendedores/nuevo/", {}).status_code, 403)
        self.assertEqual(self.admin.post(f"/operacion/datos/vendedores/{v.pk}/borrar/").status_code, 403)


class Formularios(Base):
    def test_en_espanol(self):
        for url, textos in (("/operacion/productos/nuevo/", ("SKU", "Descripción", "Unidad de medida", "Elige una opción")),
                            ("/operacion/datos/camiones/nuevo/", ("Código", "Capacidad (kg)", "Rango de temperatura", "Elige una opción")),
                            ("/operacion/datos/rangos/nuevo/", ("Temperatura mínima (°C)",)),
                            ("/operacion/datos/etapas/nuevo/", ("Orden en el embudo", "Etapa final", "Etapa ganada"))):
            html = self.admin.get(url).content.decode()
            self.assertNotIn("Select an option", html, url)
            for texto in textos:
                self.assertIn(texto, html, url)

    def test_ninguna_tabla_muestra_una_etiqueta_sin_traducir(self):
        from operacion.tablas import ETIQUETAS, TABLAS
        for tabla in TABLAS.values():
            for campo in tabla.campos:
                if campo not in ("nombre", "activo", "giro", "email", "telefono", "referencia", "region", "comuna", "categoria", "origen", "empresa", "vendedor", "patente"):
                    self.assertIn(campo, ETIQUETAS, f"{tabla.slug}.{campo}")


class HallazgosDeLaRevision(Base):
    def test_categoria_con_requerimientos_no_se_borra(self):
        cat = CategoriaRequerimiento.objects.create(nombre="Sugerencia")
        r = Requerimiento.objects.first()
        Requerimiento.objects.filter(pk=r.pk).update(categoria_requerimiento=cat, estado="clasificado")
        respuesta = self.admin.post(f"/operacion/datos/categorias-requerimiento/{cat.pk}/borrar/", follow=True)
        self.assertIn("No se puede borrar", self.mensajes(respuesta))
        self.assertTrue(CategoriaRequerimiento.objects.filter(pk=cat.pk).exists())
        r.refresh_from_db()
        self.assertEqual(r.categoria_requerimiento_id, cat.pk)

    def test_categoria_propuesta_por_la_ia_no_se_borra(self):
        cat = CategoriaRequerimiento.objects.create(nombre="Sugerencia")
        Requerimiento.objects.filter(pk=Requerimiento.objects.first().pk).update(categoria_ia=cat)
        self.admin.post(f"/operacion/datos/categorias-requerimiento/{cat.pk}/borrar/")
        self.assertTrue(CategoriaRequerimiento.objects.filter(pk=cat.pk).exists())

    def errores(self, url, datos, campo):
        r = self.admin.post(url, datos)
        self.assertEqual(r.status_code, 200)
        texto = " ".join(r.context["form"].errors.get(campo, []))
        self.assertTrue(texto, r.context["form"].errors)
        self.assertNotIn("restricci", texto.lower())
        self.assertNotIn("constraint", " ".join(str(e) for e in r.context["form"].non_field_errors()).lower())

    def test_rango_con_minima_mayor_avisa_en_el_campo(self):
        self.errores("/operacion/datos/rangos/nuevo/", {"nombre": "Raro", "temp_min_c": "5.0", "temp_max_c": "1.0"}, "temp_max_c")

    def test_capacidad_cero_avisa_en_el_campo(self):
        self.errores("/operacion/datos/camiones/nuevo/", {"camion_id": "CAM-98", "patente": "YYYY98", "capacidad_kg": 0,
                                                          "rango_temperatura": RangoTemperatura.objects.first().pk}, "capacidad_kg")

    def test_ganada_sin_final_avisa_en_el_campo(self):
        self.errores("/operacion/datos/etapas/nuevo/", {"nombre": "Rara", "orden_etapa": 50, "es_ganada": "on"}, "es_final")

    def test_prospecto_sin_contacto_avisa_en_el_campo(self):
        p = Prospecto.objects.exclude(email="").first()
        self.errores(f"/operacion/datos/prospectos/{p.pk}/", {"nombre_contacto": p.nombre_contacto, "email": "", "telefono": "", "origen": p.origen, "vendedor": p.vendedor_id}, "email")
