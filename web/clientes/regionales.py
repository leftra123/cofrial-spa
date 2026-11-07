"""Clientes y pedidos de demostración repartidos por La Araucanía, para despachar viajes de más de 100 km desde el frigorífico de Temuco.

Los nombres y las direcciones son públicos: hospitales de cada comuna, con la dirección y las coordenadas de OpenStreetMap (consultadas el
06-nov-2026). Las coordenadas quedan fijas aquí para que la demostración no dependa de Nominatim. Los RUT y los correos son ficticios, y no
hay personas: cada cuenta es la de abastecimiento de un hospital.

`cargar_demo` corre en cada arranque contra una base con datos, por eso `sembrar` solo crea lo que falta (cliente por RUT, cuenta por usuario,
pedido por número de OC): nunca cambia ni duplica lo que ya existe, y un pedido ya despachado no vuelve a aparecer.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from catalogo.models import Producto
from pedidos import servicios as pedidos
from pedidos.models import Orden

from .models import Cliente, Comuna, Direccion

# comuna, nombre, RUT ficticio, calle y número, latitud, longitud, cuenta del portal (solo las que se usan en la demostración)
HOSPITALES = [
    ("Padre Las Casas", "Complejo Asistencial Padre Las Casas", "70.300.101-7", "Camino Aeropuerto Maquehue 194", -38.767397, -72.616366, None),
    ("Lautaro", "Hospital Abraham Godoy Peña de Lautaro", "70.300.102-5", "Diego Barros Arana 820", -38.537174, -72.418315, None),
    ("Victoria", "Hospital de Victoria", "70.300.103-3", "Pedro Dartnell 1141", -38.234385, -72.340603, None),
    ("Angol", "Hospital Dr. Mauricio Heyermann Torres", "70.300.104-1", "General Óscar Bonilla 750", -37.799930, -72.690252, "abastecimiento@hospitalangol.test"),
    ("Nueva Imperial", "Hospital de Nueva Imperial", "70.300.105-K", "Castellón 0115", -38.740557, -72.958233, None),
    ("Carahue", "Hospital de Carahue", "70.300.106-8", "Alcalde Alejandro Floody Buxton 1360", -38.710368, -73.140622, None),
    ("Villarrica", "Hospital de Villarrica", "70.300.107-6", "Saturnino Epulef 2105", -39.295290, -72.211799, "abastecimiento@hospitalvillarrica.test"),
    ("Pucón", "Hospital San Francisco de Pucón", "70.300.108-4", "Uruguay 325", -39.278844, -71.974235, "abastecimiento@hospitalpucon.test"),
    ("Loncoche", "Hospital de Loncoche", "70.300.109-2", "José Miguel Carrera 330", -39.370965, -72.625955, None),
]
# número de OC, RUT del cliente, producto y cantidad. Todos quedan «En preparación»: listos para armar un viaje.
PEDIDOS = [
    ("OC-REG-001", "70.300.104-1", "POL-ENT-10K", 4),      # corredor norte (refrigerados)
    ("OC-REG-002", "70.300.103-3", "VAC-MOL-5K", 3),
    ("OC-REG-003", "70.300.102-5", "POL-TRU-8K", 3),
    ("OC-REG-004", "70.300.107-6", "VAC-POS-5K", 3),       # corredor de los lagos (refrigerados)
    ("OC-REG-005", "70.300.108-4", "EMB-JAM-3K", 4),
    ("OC-REG-006", "70.300.105-K", "LAC-QUE-5K", 2),       # corredor de la costa (refrigerados)
    ("OC-REG-007", "70.300.106-8", "POL-ENT-10K", 3),
    ("OC-REG-008", "70.300.109-2", "PAP-FRI-10K", 2),      # congelados: exige un camión de otro rango
]
# viajes con varias paradas que conviene tener calculados antes de la demostración (los de una parada ya se calculan por dirección)
CORREDORES = [("70.300.102-5", "70.300.103-3", "70.300.104-1"), ("70.300.107-6", "70.300.108-4"), ("70.300.105-K", "70.300.106-8")]


def sembrar(region, tipo_b2b, clave_para):
    """Crea lo que falte. `clave_para(usuario)` es la misma regla de claves de las demás cuentas de demostración. Quedan sin vendedor, como las
    cuentas del equipo: la cartera de cada vendedor es parte de lo que se muestra en RN-09 y no cambia."""
    Usuario = get_user_model()
    for comuna_nombre, nombre, rut, calle, lat, lon, usuario in HOSPITALES:
        comuna, _ = Comuna.objects.get_or_create(region=region, nombre=comuna_nombre)
        correo = usuario or f"abastecimiento.{rut[7:10]}@hospitales.test"
        cliente = Cliente.objects.filter(rut=rut).first()
        if cliente is None:
            cuenta = None
            if usuario:
                cuenta, nueva = Usuario.objects.get_or_create(username=usuario, defaults=dict(email=usuario))
                if nueva:
                    cuenta.set_password(clave_para(usuario))
                    cuenta.save()
            cliente = Cliente.objects.create(rut=rut, usuario=cuenta, tipo_cliente=tipo_b2b, nombre=nombre, email=correo)
        if not cliente.direccion_set.exists():
            Direccion.objects.create(cliente=cliente, calle_numero=calle, comuna=comuna, es_principal=True, lat=lat, long=lon)
    return _pedidos()


def _pedidos():
    """Devuelve los que no se pudieron crear, con el motivo. Sin stock en una base ya usada no se crea el pedido: no es razón para no arrancar."""
    omitidos = []
    for oc, rut, sku, cantidad in PEDIDOS:
        if Orden.objects.filter(numero_oc=oc).exists():
            continue
        cliente = Cliente.objects.get(rut=rut)
        try:
            with transaction.atomic():
                pedidos.agregar(cliente, Producto.objects.get(sku=sku).pk, cantidad)
                pedidos.avanzar(pedidos.avanzar(pedidos.generar_orden(cliente, cliente.direccion_set.first().pk, oc)))
        except pedidos.ErrorDeNegocio as e:
            omitidos.append(f"{oc}: {' '.join(e.mensajes)}")
    return omitidos


def corredores():
    """Paradas [(direccion_id, lat, long)...] de cada corredor, para precalcular su ruta."""
    principales = {d.cliente.rut: d for d in Direccion.objects.filter(cliente__rut__in=[h[2] for h in HOSPITALES], es_principal=True).select_related("cliente")}
    return [[(principales[r].pk, principales[r].lat, principales[r].long) for r in corredor]
            for corredor in CORREDORES if all(r in principales for r in corredor)]
