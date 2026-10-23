"""Carga datos de demostración (ficticios) de forma idempotente: se puede ejecutar varias veces."""
import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalogo.models import Categoria, ListaPrecio, PrecioProducto, Producto, RangoTemperatura
from clientes.models import Cliente, Comuna, Direccion, Region, TipoCliente, Vendedor
from crm.models import CategoriaRequerimiento, EtapaPipeline, Interaccion, Prospecto, Requerimiento
from flota.models import Camion, Despacho
from pedidos import servicios as pedidos
from pedidos.models import EstadoOrden, Orden

PRODUCTOS = [
    ("VAC-LOM-5K", "Lomo vetado de vacuno 5 kg", "Cárnicos refrigerados", "caja", 120, 38990, 45990),
    ("POL-PEC-10K", "Pechuga de pollo 10 kg", "Cárnicos refrigerados", "caja", 80, 29990, 34990),
    ("CER-COS-5K", "Costillar de cerdo 5 kg", "Cárnicos refrigerados", "caja", 60, 31990, 37990),
    ("MAR-CON-2K", "Mariscos congelados 2 kg", "Congelados", "caja", 60, 21990, 25990),
    ("PES-FIL-3K", "Filete de salmón congelado 3 kg", "Congelados", "caja", 45, 27990, 32990),
    ("VAC-POS-5K", "Posta rosada de vacuno 5 kg", "Cárnicos refrigerados", "caja", 90, 33990, 39990),
    ("VAC-MOL-5K", "Carne molida de vacuno 5 kg", "Cárnicos refrigerados", "caja", 150, 23990, 28990),
    ("CER-LOM-4K", "Lomo de cerdo 4 kg", "Cárnicos refrigerados", "caja", 70, 26990, 31990),
    ("COR-PIE-6K", "Pierna de cordero 6 kg", "Cárnicos refrigerados", "caja", 8, 52990, 61990),
    ("POL-TRU-8K", "Trutros de pollo 8 kg", "Aves", "caja", 110, 17990, 21990),
    ("POL-ENT-10K", "Pollo entero 10 kg", "Aves", "caja", 130, 19990, 24990),
    ("PAV-PEC-5K", "Pechuga de pavo 5 kg", "Aves", "caja", 55, 28990, 34990),
    ("PES-MER-5K", "Filete de merluza congelado 5 kg", "Congelados", "caja", 12, 24990, 29990),
    ("MAR-CAM-1K", "Camarones congelados 1 kg", "Congelados", "caja", 0, 11990, 14990),
    ("VER-MIX-10K", "Mix de verduras congeladas 10 kg", "Congelados", "caja", 95, 14990, 17990),
    ("PAP-FRI-10K", "Papas prefritas congeladas 10 kg", "Congelados", "caja", 140, 15990, 18990),
    ("LAC-QUE-5K", "Queso gauda laminado 5 kg", "Lácteos y embutidos", "caja", 65, 31990, 37990),
    ("LAC-MAN-10K", "Mantequilla en bloque 10 kg", "Lácteos y embutidos", "caja", 40, 54990, 64990),
    ("EMB-JAM-3K", "Jamón cocido 3 kg", "Lácteos y embutidos", "caja", 85, 16990, 20990),
    ("EMB-LON-4K", "Longaniza ahumada 4 kg", "Lácteos y embutidos", "caja", 18, 19990, 23990),
]
DESCRIPCIONES = {
    "VAC-LOM-5K": "Corte premium de vacuno para parrilla y plancha, envasado al vacío.",
    "POL-PEC-10K": "Pechuga de pollo sin hueso, fresca, lista para porcionar.",
    "CER-COS-5K": "Costillar de cerdo para horno o parrilla, envasado al vacío.",
    "MAR-CON-2K": "Mix de mariscos congelados individualmente (IQF), sin glaseado excesivo.",
    "PES-FIL-3K": "Filete de salmón sin espinas, congelado en origen.",
    "VAC-POS-5K": "Posta rosada magra, ideal para asados y cocidos.",
    "VAC-MOL-5K": "Carne molida de vacuno con baja materia grasa, para preparaciones de alto volumen.",
    "CER-LOM-4K": "Lomo de cerdo entero, para asar o cortar en medallones.",
    "COR-PIE-6K": "Pierna de cordero patagónico con hueso, para hornear.",
    "POL-TRU-8K": "Trutros de pollo con piel, frescos, para guisos y horno.",
    "POL-ENT-10K": "Pollo entero eviscerado, fresco, de venta por caja.",
    "PAV-PEC-5K": "Pechuga de pavo fresca, magra y sin hueso.",
    "PES-MER-5K": "Filete de merluza sin piel, congelado, para fritura u horno.",
    "MAR-CAM-1K": "Camarones pelados y desvenados, congelados individualmente.",
    "VER-MIX-10K": "Mezcla de zanahoria, arvejas y choclo congelada, lista para cocer.",
    "PAP-FRI-10K": "Papas prefritas en bastón, congeladas, para freír directo.",
    "LAC-QUE-5K": "Queso gauda en láminas separadas por papel, para sándwich y cocina.",
    "LAC-MAN-10K": "Mantequilla sin sal en bloque, para panadería y cocina.",
    "EMB-JAM-3K": "Jamón cocido de cerdo, pieza entera para cortar en fiambrería.",
    "EMB-LON-4K": "Longaniza ahumada tradicional, lista para cocer.",
}
ESTADOS_ORDEN = [("Recibida", False), ("Confirmada", False), ("En preparación", False), ("Despachada", False), ("Entregada", True), ("Cancelada", True)]
ETAPAS = [("Prospecto", False, False), ("Contactado", False, False), ("Propuesta enviada", False, False), ("Negociación", False, False), ("Cliente ganado", True, True), ("Perdido", True, False)]
CATEGORIAS_REQ = ["Consulta de producto", "Reclamo por temperatura", "Atraso en entrega", "Facturación", "Otro"]
CAMIONES = [("CAM-01", "HJKL-42", 8000, "Refrigerado"), ("CAM-02", "PQRS-17", 6000, "Congelado"), ("CAM-03", "TUVW-93", 8000, "Refrigerado")]


class Command(BaseCommand):
    help = "Carga catálogo, clientes, flota y datos base de demostración."

    def handle(self, *args, **opciones):
        clave = os.environ.get("DEMO_PASSWORD", "demo-cofrial-2026")
        Usuario = get_user_model()

        region, _ = Region.objects.get_or_create(nombre="La Araucanía")
        temuco, _ = Comuna.objects.get_or_create(region=region, nombre="Temuco")
        Comuna.objects.get_or_create(region=region, nombre="Villarrica")

        refrigerado, _ = RangoTemperatura.objects.get_or_create(nombre="Refrigerado", defaults=dict(temp_min_c=Decimal("0.0"), temp_max_c=Decimal("4.0")))
        congelado, _ = RangoTemperatura.objects.get_or_create(nombre="Congelado", defaults=dict(temp_min_c=Decimal("-25.0"), temp_max_c=Decimal("-18.0")))
        categorias = {
            "Cárnicos refrigerados": Categoria.objects.get_or_create(nombre="Cárnicos refrigerados", defaults=dict(rango_temperatura=refrigerado))[0],
            "Congelados": Categoria.objects.get_or_create(nombre="Congelados", defaults=dict(rango_temperatura=congelado))[0],
            "Aves": Categoria.objects.get_or_create(nombre="Aves", defaults=dict(rango_temperatura=refrigerado))[0],
            "Lácteos y embutidos": Categoria.objects.get_or_create(nombre="Lácteos y embutidos", defaults=dict(rango_temperatura=refrigerado))[0],
        }
        b2b, _ = ListaPrecio.objects.get_or_create(nombre="Institucional B2B")
        b2c, _ = ListaPrecio.objects.get_or_create(nombre="Público B2C")
        for sku, nombre, cat, unidad, stock, precio_b2b, precio_b2c in PRODUCTOS:
            p, _ = Producto.objects.get_or_create(sku=sku, defaults=dict(nombre=nombre, categoria=categorias[cat], unidad_medida=unidad, stock_disponible=stock))
            PrecioProducto.objects.get_or_create(lista_precio=b2b, producto=p, defaults=dict(precio_clp=precio_b2b))
            PrecioProducto.objects.get_or_create(lista_precio=b2c, producto=p, defaults=dict(precio_clp=precio_b2c))
            cambios = {}
            if not p.descripcion and sku in DESCRIPCIONES:
                cambios["descripcion"] = DESCRIPCIONES[sku]
            if p.categoria_id != categorias[cat].pk and cat == "Aves":     # la pechuga ya existía como «Cárnicos refrigerados»
                cambios["categoria"] = categorias[cat]
            if cambios:
                Producto.objects.filter(pk=p.pk).update(**cambios)

        tipo_b2b, _ = TipoCliente.objects.get_or_create(codigo="B2B", defaults=dict(nombre="Institucional", lista_precio=b2b))
        tipo_b2c, _ = TipoCliente.objects.get_or_create(codigo="B2C", defaults=dict(nombre="Público general", lista_precio=b2c))

        for i, (nombre, flujo_final) in enumerate(ESTADOS_ORDEN, start=1):
            EstadoOrden.objects.get_or_create(nombre=nombre, defaults=dict(orden_flujo=i, es_final=flujo_final))
        for i, (nombre, final, ganada) in enumerate(ETAPAS, start=1):
            EtapaPipeline.objects.get_or_create(nombre=nombre, defaults=dict(orden_etapa=i, es_final=final, es_ganada=ganada))
        for nombre in CATEGORIAS_REQ:
            CategoriaRequerimiento.objects.get_or_create(nombre=nombre)
        rangos = {"Refrigerado": refrigerado, "Congelado": congelado}
        for camion_id, patente, capacidad, rango in CAMIONES:
            Camion.objects.get_or_create(camion_id=camion_id, defaults=dict(patente=patente, capacidad_kg=capacidad, rango_temperatura=rangos[rango]))

        grupo_vendedores, _ = Group.objects.get_or_create(name="vendedores")
        u_vend, nuevo = Usuario.objects.get_or_create(username="vendedora@cofrial.test", defaults=dict(email="vendedora@cofrial.test", is_staff=True))
        if nuevo:
            u_vend.set_password(clave)
            u_vend.save()
        u_vend.groups.add(grupo_vendedores)
        vendedora, _ = Vendedor.objects.get_or_create(usuario=u_vend, defaults=dict(nombre="María Paz Soto", telefono="+56912345678"))

        for username, nombre, rut, tipo, vendedor, calle in [
            ("abastecimiento@hospital.test", "Hospital Regional de Temuco", "61.973.200-4", tipo_b2b, vendedora, "Manuel Montt 115"),
            ("ana@correo.test", "Ana Pérez", "12.345.678-5", tipo_b2c, None, "Av. Alemania 0671"),
        ]:
            u, nuevo = Usuario.objects.get_or_create(username=username, defaults=dict(email=username))
            if nuevo:
                u.set_password(clave)
                u.save()
            cliente, _ = Cliente.objects.get_or_create(rut=rut, defaults=dict(usuario=u, tipo_cliente=tipo, vendedor=vendedor, nombre=nombre, email=username))
            if not cliente.direccion_set.exists():
                Direccion.objects.create(cliente=cliente, calle_numero=calle, comuna=temuco, es_principal=True)

        # segunda vendedora, gerencia y despachador: sirven para mostrar los permisos por rol (RN-09)
        grupo_gerencia, _ = Group.objects.get_or_create(name="gerencia")
        grupo_despacho, _ = Group.objects.get_or_create(name="despachadores")
        for username, grupo in (("gerente@cofrial.test", grupo_gerencia), ("despachador@cofrial.test", grupo_despacho)):
            u, nuevo = Usuario.objects.get_or_create(username=username, defaults=dict(email=username, is_staff=True))
            if nuevo:
                u.set_password(clave)
                u.save()
            u.groups.add(grupo)
        u2, nuevo = Usuario.objects.get_or_create(username="vendedor2@cofrial.test", defaults=dict(email="vendedor2@cofrial.test", is_staff=True))
        if nuevo:
            u2.set_password(clave)
            u2.save()
        u2.groups.add(grupo_vendedores)
        pedro, _ = Vendedor.objects.get_or_create(usuario=u2, defaults=dict(nombre="Pedro Núñez", telefono="+56987654321"))
        sur, creado = Cliente.objects.get_or_create(rut="76.543.210-K", defaults=dict(tipo_cliente=tipo_b2b, vendedor=pedro, nombre="Supermercados del Sur", email="compras@supersur.test"))
        if creado:
            Direccion.objects.create(cliente=sur, calle_numero="Av. Pedro de Valdivia 1200", comuna=temuco, es_principal=True)

        etapas = {e.nombre: e for e in EtapaPipeline.objects.all()}
        for nombre, empresa, email, etapa, monto, v in [
            ("Jorge Rivas", "Casino Escolar Lautaro", "jorge@casino.test", "Prospecto", 4500000, vendedora),
            ("Carla Muñoz", "Clínica Alemana Temuco", "carla@clinica.test", "Contactado", 12000000, vendedora),
            ("Luis Soto", "Hotel Villarrica Lago", "luis@hotel.test", "Propuesta enviada", 6800000, pedro),
            ("Rosa Vega", "Feria Libre Padre Las Casas", "rosa@feria.test", "Negociación", 3200000, pedro),
        ]:
            p, creado = Prospecto.objects.get_or_create(nombre_contacto=nombre, defaults=dict(vendedor=v, etapa=etapas[etapa], empresa=empresa, email=email, origen="llamada", monto_estimado_clp=monto))
            if creado and etapa != "Prospecto":
                Interaccion.objects.create(vendedor=v, prospecto=p, tipo="llamada", detalle="Primera conversación sobre volúmenes y frecuencia de entrega.")

        # dos pedidos en ruta (para ver la alerta de frío cuando el simulador reporte una ruptura) y un reclamo sin clasificar
        if not Orden.objects.exists():
            ahora = timezone.now()
            for cliente, camion_id, oc, producto in ((Cliente.objects.get(rut="61.973.200-4"), "CAM-01", "OC-2026-0457", "VAC-LOM-5K"),
                                                      (sur, "CAM-02", "OC-SUR-118", "MAR-CON-2K")):
                pedidos.agregar(cliente, Producto.objects.get(sku=producto).pk, 5)
                orden = pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, oc)
                despacho = Despacho.objects.create(camion_id=camion_id, programado_para=ahora - timedelta(hours=1), salida_en=ahora - timedelta(minutes=30))
                orden = pedidos.avanzar(pedidos.avanzar(orden))             # Confirmada, En preparación
                orden.despacho = despacho
                orden.save(update_fields=["despacho"])
                pedidos.avanzar(orden)                                      # Despachada
            Requerimiento.objects.create(cliente=sur, asunto="Mi pedido llegó tibio", descripcion="El camión llegó con la carga sin la temperatura adecuada y rechazamos dos cajas. Necesitamos reposición urgente.")

        if not Usuario.objects.filter(username="admin").exists():
            Usuario.objects.create_superuser("admin", "admin@cofrial.test", clave)
        self.stdout.write(self.style.SUCCESS("Datos de demostración listos (usuarios de prueba: contraseña en DEMO_PASSWORD)."))
