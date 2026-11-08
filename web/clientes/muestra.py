"""Clientes de muestra e historial de pedidos para que la Torre de control tenga qué mostrar en cada segmento y en cada nivel del embudo.

Los nombres y las direcciones son públicos (supermercados, una feria, universidades y hospitales fuera de La Araucanía) y las coordenadas son
las de OpenStreetMap, consultadas una sola vez en Nominatim el 08-nov-2026 y fijadas aquí. Los RUT (serie 70.400.1xx, con dígito verificador
válido) y los correos (`.test`) son ficticios: ninguno es cliente confirmado de Cofrial, no hay cuentas de acceso ni vendedor.

Notas de la consulta a OpenStreetMap:
- «Internados municipales de Temuco» no aparece como lugar en OpenStreetMap: se reemplazó por la Universidad Católica de Temuco (Institucional).
- «Hospital Base Valdivia» figura en OpenStreetMap como Hospital Regional de Valdivia (es el mismo recinto): se usa ese nombre.
- «Supermercados Eltit» solo aparece en Pucón (Bernardo O'Higgins 336); no hay local confirmado en Temuco.
- Feria Pinto es un mercado en Temuco sin número de calle: se anota la calle con que figura en OpenStreetMap.

`sembrar` corre en cada arranque contra una base con datos, por eso solo crea lo que falta y nunca cambia lo que ya existe (el segmento solo se
asigna si está vacío). El historial son pedidos «Entregada» sin despacho, con líneas al precio de la lista, sin descontar stock y con factura
pagada: no cruzan con alertas de frío ni suben la cobranza. `limpiar` lo deshace (comando `limpiar_muestra`).
"""
import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalogo.models import Producto
from crm.models import EtapaPipeline, Prospecto
from pedidos import documentos, servicios as pedidos
from pedidos.models import EstadoOrden, Orden, OrdenItem, Pago, Documento

from . import regionales
from .models import Cliente, Comuna, Direccion, Region, SegmentoCliente, Vendedor
from . import rut as rut_chileno

# región, comuna, segmento, nombre, RUT ficticio, calle y número, latitud, longitud
MUESTRA = [
    ("La Araucanía", "Temuco", "Supermercado", "Jumbo Temuco", "70.400.101-0", "Avenida Alemania 0671", -38.7345169, -72.6105148),
    ("La Araucanía", "Temuco", "Supermercado", "Unimarc Temuco", "70.400.102-9", "Bernardo O'Higgins 0160", -38.7419658, -72.6053923),
    ("La Araucanía", "Temuco", "Supermercado", "Lider Temuco", "70.400.103-7", "Avenida Gabriela Mistral 2621", -38.7348227, -72.6415350),
    ("La Araucanía", "Temuco", "Supermercado", "Santa Isabel Temuco", "70.400.104-5", "Avenida Caupolicán 650", -38.7461845, -72.6084010),
    ("La Araucanía", "Pucón", "Supermercado", "Supermercados Eltit", "70.400.105-3", "Bernardo O'Higgins 336", -39.2763025, -71.9753357),
    ("La Araucanía", "Temuco", "Feria", "Feria Pinto", "70.400.106-1", "Francisco Antonio Pinto, Avenida Balmaceda", -38.7352920, -72.5798328),
    ("La Araucanía", "Temuco", "Institucional", "Universidad de La Frontera", "70.400.107-K", "Francisco Salazar 01145", -38.7480605, -72.6182905),
    ("La Araucanía", "Temuco", "Institucional", "Universidad Católica de Temuco", "70.400.108-8", "Manuel Montt 56", -38.7378420, -72.6017836),
    ("Los Ríos", "Valdivia", "Hospital", "Hospital Regional de Valdivia", "70.400.109-6", "Santiago Bueras 1003", -39.8317025, -73.2402519),
    ("Biobío", "Los Ángeles", "Hospital", "Complejo Asistencial Dr. Víctor Ríos Ruiz", "70.400.110-K", "Avenida Ricardo Vicuña 0147", -37.4747109, -72.3458458),
]
HOSPITAL_REGIONAL = "61.973.200-4"
SUPERMERCADOS_DEL_SUR = "76.543.210-K"
RUT_ILUSTRATIVOS = frozenset({m[4] for m in MUESTRA} | {h[2] for h in regionales.HOSPITALES} | {HOSPITAL_REGIONAL, SUPERMERCADOS_DEL_SUR})
# Pedidos que crea la carga de demostración (`cargar_demo` y `regionales`): valores exactos de numero_oc, no un prefijo, porque un cliente real podría
# escribir «OC-…». No prueban una venta real, así que la Torre no los cuenta en D2, D4 ni en las ventas de 24 h (el historial se reconoce por «HIS-»).
REFERENCIAS_SEMBRADAS = frozenset({"OC-2026-0457", "OC-SUR-118", "OC-SUR-119", "OC-2026-0301", "OC-2026-0388", "OC-SUR-102", "OC-SUR-117"}
                                  | {p[0] for p in regionales.PEDIDOS})
SEGMENTO_DE_LOS_YA_SEMBRADOS = {**{h[2]: "Hospital" for h in regionales.HOSPITALES}, HOSPITAL_REGIONAL: "Hospital", SUPERMERCADOS_DEL_SUR: "Supermercado"}

# Historial: RUT, perfil y cantidad de pedidos. Reciben historial los clientes nuevos y estos seis hospitales sin cuenta ni vendedor; quedan fuera
# Hospital Regional, Supermercados del Sur, Angol, Villarrica y Pucón (cuentas de acceso o vendedor) y las dos universidades que no compran aún.
# Fidelizado: 4 o más pedidos en la ventana y el último reciente. Recompra: 2 o 3 recientes. Primer pedido: uno reciente. En riesgo: sin pedidos hace más de 30 días.
HISTORIAL = [
    ("70.400.101-0", "fidelizado", 9), ("70.400.102-9", "fidelizado", 8), ("70.400.103-7", "fidelizado", 7), ("70.400.104-5", "recompra", 3),
    ("70.400.105-3", "en_riesgo", 4), ("70.400.106-1", "recompra", 2), ("70.400.107-K", "primer", 1),
    ("70.400.109-6", "fidelizado", 8), ("70.400.110-K", "en_riesgo", 4),
    ("70.300.101-7", "fidelizado", 9), ("70.300.102-5", "recompra", 2), ("70.300.103-3", "en_riesgo", 3),
    ("70.300.105-K", "primer", 1), ("70.300.106-8", "recompra", 3), ("70.300.109-2", "en_riesgo", 3),
]
# (rango en días desde hoy hacia atrás) del historial; el mínimo deja al menos 24 h entre el pedido y el momento de sembrar
RANGOS_DIAS = {"fidelizado": (1.5, 85), "recompra": (1.5, 27), "primer": (1.5, 27), "en_riesgo": (33, 85)}

# vendedor, contacto, empresa, correo, etapa, monto estimado, origen. Uno queda «Perdido» con motivo, para que esa fila tenga un caso.
PROSPECTOS = [
    ("vendedora@cofrial.cl", "Marcela Fuentes", "Supermercado Mayorista de Lautaro", "marcela@mayorista.test", "Propuesta enviada", 5400000, "referido"),
    ("vendedora@cofrial.cl", "Patricio Henríquez", "Internado Municipal de Freire", "patricio@internado.test", "Prospecto", 2800000, "llamada"),
    ("vendedor2@cofrial.cl", "Daniela Oyarzún", "Hospital Comunitario de Cunco", "daniela@hospitalcunco.test", "Negociación", 6100000, "web"),
    ("vendedor2@cofrial.cl", "Gonzalo Beltrán", "Feria Libre de Villarrica", "gonzalo@feriavillarrica.test", "Perdido", 1900000, "feria"),
]
MOTIVO_PERDIDA = "Compra directo a un mayorista de la zona"


def sembrar(tipo_b2b):
    """Crea lo que falte y devuelve los avisos (lo que no se pudo crear). `tipo_b2b` es el TipoCliente institucional."""
    avisos = []
    # los crea la migración, pero un flush de pruebas con --keepdb los vacía (docs/decisiones.md)
    segmentos = {n: SegmentoCliente.objects.get_or_create(nombre=n)[0] for n in sorted({m[2] for m in MUESTRA} | set(SEGMENTO_DE_LOS_YA_SEMBRADOS.values()))}
    for rut, segmento in SEGMENTO_DE_LOS_YA_SEMBRADOS.items():
        Cliente.objects.filter(rut=rut, segmento__isnull=True).update(segmento=segmentos[segmento])
    for region_nombre, comuna_nombre, segmento, nombre, rut, calle, lat, lon in MUESTRA:
        region, _ = Region.objects.get_or_create(nombre=region_nombre)
        comuna, _ = Comuna.objects.get_or_create(region=region, nombre=comuna_nombre)
        cliente = Cliente.objects.filter(rut=rut).first()
        if cliente is None:
            cliente = Cliente.objects.create(rut=rut, tipo_cliente=tipo_b2b, nombre=nombre, segmento=segmentos[segmento],
                                             email=f"compras.{rut[7:10]}@muestra.test")
        if not cliente.direccion_set.exists():
            Direccion.objects.create(cliente=cliente, calle_numero=calle, comuna=comuna, es_principal=True, lat=lat, long=lon)
    avisos += _historial()
    avisos += _prospectos()
    return avisos


def _historial():
    azar = random.Random(2026)
    ahora = timezone.now()
    entregada = EstadoOrden.objects.get(nombre="Entregada")
    productos = list(Producto.objects.order_by("sku"))
    avisos = []
    for rut, perfil, cantidad in HISTORIAL:
        cliente = Cliente.objects.filter(rut=rut).select_related("tipo_cliente").first()
        # el azar se consume igual en cada corrida, exista o no el cliente, para que los pedidos que faltan salgan iguales
        minimo, maximo = RANGOS_DIAS[perfil]
        dias = sorted((azar.uniform(minimo, maximo) for _ in range(cantidad)), reverse=True)
        if perfil == "fidelizado":                                   # el último pedido siempre reciente
            dias[-1] = azar.uniform(1.5, 18)
        lineas = [[(p, azar.randint(2, 12)) for p in azar.sample(productos, azar.randint(1, 3))] for _ in range(cantidad)]
        if cliente is None:
            avisos.append(f"Sin historial para {rut}: el cliente no existe")
            continue
        direccion = cliente.direccion_set.first()
        for n, (hace, lineas_n) in enumerate(zip(dias, lineas), start=1):
            referencia = f"HIS-{rut_chileno.limpiar(rut)}-{n}"
            if Orden.objects.filter(numero_oc=referencia).exists():
                continue
            precios = [(p, c, pedidos.precio_de(cliente, p.pk)) for p, c in lineas_n]
            precios = [(p, c, precio) for p, c, precio in precios if precio]
            if not precios:
                avisos.append(f"{referencia}: ningún producto con precio en la lista del cliente")
                continue
            creada = ahora - timedelta(days=hace)
            with transaction.atomic():
                orden = Orden.objects.create(direccion=direccion, estado_orden=entregada, numero_oc=referencia)
                OrdenItem.objects.bulk_create([OrdenItem(orden=orden, producto=p, cantidad=c, precio_unitario_clp=precio) for p, c, precio in precios])
                factura = documentos.emitir_factura(orden)
                documentos.registrar_pago(factura.pk, factura.monto_clp, "transferencia")
                emitida = creada + timedelta(hours=22)
                Orden.objects.filter(pk=orden.pk).update(creada_en=creada, entrega_resuelta_en=creada + timedelta(hours=20))
                Documento.objects.filter(pk=factura.pk).update(emitido_en=emitida, vence_en=emitida.date() + timedelta(days=cliente.tipo_cliente.dias_credito))
    return avisos


def _prospectos():
    avisos = []
    etapas = {e.nombre: e for e in EtapaPipeline.objects.all()}
    ahora = timezone.now()
    for usuario, contacto, empresa, email, etapa, monto, origen in PROSPECTOS:
        vendedor = Vendedor.objects.filter(usuario__username=usuario).first()
        if vendedor is None or etapa not in etapas:
            avisos.append(f"Prospecto {empresa} sin crear: falta {'el vendedor ' + usuario if vendedor is None else 'la etapa ' + etapa}")
            continue
        perdido = etapa == "Perdido"
        Prospecto.objects.get_or_create(nombre_contacto=contacto, empresa=empresa, defaults=dict(
            vendedor=vendedor, etapa=etapas[etapa], email=email, origen=origen, monto_estimado_clp=monto,
            cerrado_en=ahora - timedelta(days=20) if perdido else None, motivo_perdida=MOTIVO_PERDIDA if perdido else ""))
    return avisos


def limpiar():
    """Deshace `sembrar`: borra los pedidos `HIS-`, sus documentos, pagos y líneas, los clientes de muestra que ya no tengan pedidos y los
    prospectos nuevos. No toca el segmento de los clientes que ya existían ni las regiones y comunas. Devuelve lo borrado."""
    with transaction.atomic():
        ordenes = Orden.objects.filter(numero_oc__startswith="HIS-")
        docs = Documento.objects.filter(orden__in=ordenes)
        resultado = {"pagos": Pago.objects.filter(documento__in=docs).delete()[0]}
        # una nota de crédito apunta a su factura: se borran primero
        resultado["facturas"] = docs.filter(tipo="nota_credito").delete()[0] + docs.delete()[0]
        resultado["lineas"] = OrdenItem.objects.filter(orden__in=ordenes).delete()[0]
        resultado["pedidos"] = ordenes.delete()[0]
        sin_pedidos = Cliente.objects.filter(rut__in=[m[4] for m in MUESTRA]).exclude(direccion__orden__isnull=False)
        resultado["clientes"] = sin_pedidos.delete()[1].get("clientes.Cliente", 0)
        propios = Prospecto.objects.none()
        for _, contacto, empresa, *_ in PROSPECTOS:
            propios |= Prospecto.objects.filter(nombre_contacto=contacto, empresa=empresa)
        resultado["prospectos"] = propios.delete()[1].get("crm.Prospecto", 0)
    return resultado
