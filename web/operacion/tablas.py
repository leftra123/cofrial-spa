"""Registro del panel común: qué tablas edita el administrador en /operacion/datos/ y con qué límites.
Las vistas (datos.py) no saben de ninguna tabla en particular: todo lo propio de cada una está aquí."""
from dataclasses import dataclass, field
from typing import Callable

from django import forms
from django.core.validators import RegexValidator
from django.db.models import Q
from django.forms import modelform_factory

from catalogo.models import Categoria, ListaPrecio, RangoTemperatura
from clientes import rut as rutlib
from clientes.models import Cliente, Comuna, Direccion, Region, TipoCliente, Vendedor
from crm.models import CategoriaRequerimiento, EtapaPipeline, Prospecto, Requerimiento
from flota.models import Camion
from pedidos.models import EstadoOrden, Orden

ETAPAS_FIJAS = {"Contactado", "Propuesta enviada"}                               # crm/servicios.py las compara por nombre
CATEGORIAS_FIJAS = {"Reclamo por temperatura", "Problema en la entrega"}          # el código y el simulador las buscan por nombre


@dataclass
class Tabla:
    slug: str
    titulo: str
    grupo: str
    icono: str
    modelo: type
    columnas: list                          # [(encabezado, atributo con puntos o función)]
    busqueda: tuple
    campos: tuple
    crear: bool = True
    editar: bool = True
    borrar: bool = True
    ayuda: str = ""
    validar: Callable | None = None         # validar(form, objeto): agrega errores al formulario; objeto aún tiene los datos guardados
    protegida: Callable | None = None       # protegida(objeto) -> motivo que impide borrar, o ""
    bloqueada: Callable | None = None       # bloqueada(objeto) -> motivo que impide editar, o ""
    al_guardar: Callable | None = None      # al_guardar(form, objeto): ajustes justo antes de guardar
    solo_al_crear: tuple = ()               # campos que se fijan al crear y después no cambian
    ajustar: Callable | None = None         # ajustar(form): retoques del formulario (validadores, opciones, ayudas)
    orden: tuple = ()
    relacionados: tuple = field(default_factory=tuple)


ETIQUETAS = {
    "sku": "SKU", "descripcion": "Descripción", "categoria": "Categoría", "unidad_medida": "Unidad de medida", "rango_temperatura": "Rango de temperatura",
    "temp_min_c": "Temperatura mínima (°C)", "temp_max_c": "Temperatura máxima (°C)", "camion_id": "Código", "capacidad_kg": "Capacidad (kg)",
    "lista_precio": "Lista de precios", "dias_credito": "Días de crédito", "rut": "RUT", "email": "Correo", "telefono": "Teléfono", "region": "Región",
    "calle_numero": "Calle y número", "es_principal": "Dirección principal", "nombre_contacto": "Nombre del contacto", "monto_estimado_clp": "Monto estimado (CLP)",
    "orden_etapa": "Orden en el embudo", "es_final": "Etapa final", "es_ganada": "Etapa ganada",
}


def en_espanol(form):
    """Etiquetas legibles y el texto de «sin elegir», que Django 6.1 trae solo en inglés."""
    for nombre, campo in form.fields.items():
        if nombre in ETIQUETAS:
            campo.label = ETIQUETAS[nombre]
        if getattr(campo, "empty_label", None) is not None:
            campo.empty_label = "Elige una opción"
        elif isinstance(campo, forms.TypedChoiceField) and campo.choices and campo.choices[0][0] == "":
            campo.choices = [("", "Elige una opción"), *campo.choices[1:]]


def formulario_de(tabla):
    """ModelForm de la tabla. Un campo deshabilitado ignora lo que venga en el POST, así que el límite no depende de la pantalla."""
    base = modelform_factory(tabla.modelo, fields=tabla.campos)

    class Formulario(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            existe = not self.instance._state.adding
            self.motivo_bloqueo = tabla.bloqueada(self.instance) if existe and tabla.bloqueada else ""
            for nombre, campo in self.fields.items():
                if self.motivo_bloqueo or (existe and nombre in tabla.solo_al_crear):
                    campo.disabled = True
            if tabla.ajustar:
                tabla.ajustar(self)
            en_espanol(self)

        def clean(self):
            datos = super().clean()
            if self.motivo_bloqueo:
                self.add_error(None, self.motivo_bloqueo)
            elif tabla.validar:
                tabla.validar(self, self.instance)
            return datos

    return Formulario


def _ajustar_camion(form):
    form.fields["camion_id"].validators.append(RegexValidator(r"^[A-Z0-9-]+$", "Usa mayúsculas, números y guiones, por ejemplo CAM-51."))


def _etapa_necesaria(etapa):
    """Motivo por el que la etapa no puede dejar de existir tal como está, o «». crm/servicios.py exige una ganada y una final perdida."""
    if etapa.nombre in ETAPAS_FIJAS:
        return f"el sistema usa la etapa «{etapa.nombre}» por su nombre."
    otras = EtapaPipeline.objects.exclude(pk=etapa.pk)
    if etapa.es_ganada and not otras.filter(es_ganada=True).exists():
        return "es la única etapa ganada."
    if etapa.es_final and not etapa.es_ganada and not otras.filter(es_final=True, es_ganada=False).exists():
        return "es la única etapa final perdida."
    return ""


def _validar_etapa(form, etapa):
    d = form.cleaned_data
    if d.get("es_ganada") and not d.get("es_final"):
        form.add_error("es_final", "Una etapa ganada también debe ser final.")
    if etapa._state.adding:
        return
    if etapa.nombre in ETAPAS_FIJAS and (d.get("nombre") != etapa.nombre or d.get("es_final") or d.get("es_ganada")):
        form.add_error("nombre", f"«{etapa.nombre}» es fija: el sistema la usa por su nombre y debe seguir abierta.")
    otras = EtapaPipeline.objects.exclude(pk=etapa.pk)
    if etapa.es_ganada and not d.get("es_ganada") and not otras.filter(es_ganada=True).exists():
        form.add_error("es_ganada", "Debe quedar al menos una etapa ganada.")
    perdida = etapa.es_final and not etapa.es_ganada
    if perdida and not (d.get("es_final") and not d.get("es_ganada")) and not otras.filter(es_final=True, es_ganada=False).exists():
        form.add_error("es_final", "Debe quedar al menos una etapa final perdida.")


def _validar_categoria_requerimiento(form, categoria):
    if categoria.nombre in CATEGORIAS_FIJAS and form.cleaned_data.get("nombre") != categoria.nombre:
        form.add_error("nombre", f"«{categoria.nombre}» es fija: el sistema la busca por su nombre.")


def _categoria_requerimiento_protegida(categoria):
    """Borrarla dejaría sus requerimientos «clasificados» sin categoría (la clave foránea es SET_NULL), sin avisar a nadie."""
    if categoria.nombre in CATEGORIAS_FIJAS:
        return f"el sistema busca «{categoria.nombre}» por su nombre."
    if Requerimiento.objects.filter(Q(categoria_requerimiento=categoria) | Q(categoria_ia=categoria)).exists():
        return "tiene requerimientos clasificados con ella. Reclasifícalos primero en el CRM."
    return ""


def _validar_rango(form, rango):
    d = form.cleaned_data
    if d.get("temp_min_c") is not None and d.get("temp_max_c") is not None and d["temp_min_c"] >= d["temp_max_c"]:
        form.add_error("temp_max_c", "La temperatura máxima debe ser mayor que la mínima.")


def _validar_camion(form, camion):
    if form.cleaned_data.get("capacidad_kg") is not None and form.cleaned_data["capacidad_kg"] <= 0:
        form.add_error("capacidad_kg", "La capacidad debe ser mayor que cero.")


def _validar_prospecto(form, prospecto):
    d = form.cleaned_data
    if "email" in d and "telefono" in d and not d["email"] and not d["telefono"]:
        form.add_error("email", "Indica un correo o un teléfono de contacto.")
    if d.get("monto_estimado_clp") is not None and d["monto_estimado_clp"] < 0:
        form.add_error("monto_estimado_clp", "El monto no puede ser negativo.")


def _vendedores_activos(form):
    """En la lista solo vendedores activos, más el que la fila ya tiene para no perderlo al guardar."""
    actual = getattr(form.instance, "vendedor_id", None)
    form.fields["vendedor"].queryset = Vendedor.objects.filter(Q(activo=True) | Q(pk=actual)).order_by("nombre")


def _es_solicitud(cliente):
    return cliente.tipo_cliente.codigo == "B2B" and cliente.vendedor_id is None and cliente.usuario_id is not None and not cliente.usuario.is_active


def _cliente_bloqueado(cliente):
    return "Esta empresa espera aprobación: se aprueba o se rechaza en CRM, Solicitudes." if _es_solicitud(cliente) else ""


def _validar_cliente(form, cliente):
    d = form.cleaned_data
    if d.get("rut") and "rut" in form.changed_data:                     # los RUT ya guardados no se revalidan: algunos de la demostración son ficticios
        if rutlib.es_valido(d["rut"]):
            d["rut"] = rutlib.formatear(d["rut"])                     # antes de revisar duplicados: el mismo RUT escrito de otra forma es el mismo
        else:
            form.add_error("rut", "El RUT no es válido: revisa el dígito verificador.")
    if "vendedor" in d and d["vendedor"] is None and cliente.tipo_cliente.codigo == "B2B" and cliente.usuario_id and not cliente.usuario.is_active:
        form.add_error("vendedor", "Sin vendedor esta cuenta inactiva pasaría a ser una solicitud pendiente, y al rechazarla se borraría el cliente.")


def _direccion_bloqueada(direccion):
    if Orden.objects.filter(direccion=direccion, estado_orden__es_final=False).exists():
        return "Esta dirección tiene órdenes en curso: no se edita hasta que terminen. Si el cliente cambió de lugar, agrega otra en su ficha del CRM."
    return ""


def _validar_direccion(form, direccion):
    if direccion.es_principal and not form.cleaned_data.get("es_principal"):
        form.add_error("es_principal", "Para cambiarla, marca como principal otra dirección del cliente.")


def _al_guardar_direccion(form, direccion):
    if {"calle_numero", "comuna"} & set(form.changed_data):
        direccion.lat = direccion.long = None                        # las coordenadas eran del lugar anterior: se vuelven a ubicar
    if direccion.es_principal:
        Direccion.objects.filter(cliente_id=direccion.cliente_id, es_principal=True).exclude(pk=direccion.pk).update(es_principal=False)


def _direccion_protegida(direccion):
    return "es la dirección principal del cliente: primero marca otra." if direccion.es_principal else ""


AVISO_SIMULADOR = "El simulador solo mueve de CAM-01 a CAM-50: un camión con otro código aparece en la flota, pero sin telemetría."

_LISTA = [
    Tabla("categorias", "Categorías", "Catálogo", "categorias", Categoria,
          [("Nombre", "nombre"), ("Rango de temperatura", "rango_temperatura.nombre")], ("nombre",), ("nombre", "rango_temperatura"),
          orden=("nombre",), relacionados=("rango_temperatura",)),
    Tabla("rangos", "Rangos de temperatura", "Catálogo", "alerta-frio", RangoTemperatura,
          [("Nombre", "nombre"), ("Mínima °C", "temp_min_c"), ("Máxima °C", "temp_max_c")], ("nombre",), ("nombre", "temp_min_c", "temp_max_c"),
          solo_al_crear=("nombre",), validar=_validar_rango, orden=("nombre",), ayuda="El nombre no cambia después de crearlo: la flota lo compara con el de cada categoría."),
    Tabla("listas", "Listas de precio", "Catálogo", "cobranza", ListaPrecio, [("Nombre", "nombre")], ("nombre",), ("nombre",), orden=("nombre",),
          ayuda="Borrar una lista borra también sus precios. Los precios se editan en cada producto."),
    Tabla("camiones", "Camiones", "Flota", "camion", Camion,
          [("Código", "camion_id"), ("Patente", "patente"), ("Capacidad kg", "capacidad_kg"), ("Rango", "rango_temperatura.nombre"), ("Activo", "activo")],
          ("camion_id", "patente"), ("camion_id", "patente", "capacidad_kg", "rango_temperatura", "activo"),
          solo_al_crear=("camion_id",), ajustar=_ajustar_camion, validar=_validar_camion, ayuda=AVISO_SIMULADOR, orden=("camion_id",), relacionados=("rango_temperatura",)),
    Tabla("tipos-cliente", "Tipos de cliente", "Clientes", "clientes", TipoCliente,
          [("Código", "codigo"), ("Nombre", "nombre"), ("Lista de precios", "lista_precio.nombre"), ("Días de crédito", "dias_credito")],
          ("codigo", "nombre"), ("lista_precio", "dias_credito"), crear=False, borrar=False, orden=("codigo",), relacionados=("lista_precio",),
          ayuda="B2B y B2C son fijos: el sistema los usa por su código. Aquí se ajusta su lista de precios y sus días de crédito."),
    Tabla("clientes", "Clientes", "Clientes", "clientes", Cliente,
          [("Nombre", "nombre"), ("RUT", "rut"), ("Tipo", "tipo_cliente.codigo"), ("Vendedor", "vendedor.nombre"), ("Correo", "email")],
          ("nombre", "rut", "email"), ("nombre", "rut", "email", "telefono", "giro", "vendedor"), crear=False, borrar=False,
          validar=_validar_cliente, bloqueada=_cliente_bloqueado, ajustar=_vendedores_activos, orden=("nombre",), relacionados=("tipo_cliente", "vendedor", "usuario"),
          ayuda="Los clientes nacen en Usuarios, en el registro o al ganar un prospecto. Aquí se corrigen sus datos y se reasigna su vendedor."),
    Tabla("direcciones", "Direcciones", "Clientes", "territorio", Direccion,
          [("Calle y número", "calle_numero"), ("Comuna", "comuna.nombre"), ("Cliente", "cliente.nombre"), ("Principal", "es_principal")],
          ("calle_numero", "cliente__nombre", "comuna__nombre"), ("calle_numero", "comuna", "referencia", "es_principal"), crear=False,
          validar=_validar_direccion, bloqueada=_direccion_bloqueada, al_guardar=_al_guardar_direccion, protegida=_direccion_protegida,
          orden=("cliente__nombre", "calle_numero"), relacionados=("cliente", "comuna"),
          ayuda="Las direcciones nuevas se agregan en la ficha del cliente, en el CRM. Al cambiar la calle o la comuna se vuelven a ubicar en el mapa."),
    Tabla("vendedores", "Vendedores", "Clientes", "ventas", Vendedor,
          [("Nombre", "nombre"), ("Usuario", "usuario.username"), ("Teléfono", "telefono"), ("Activo", "activo")], ("nombre", "usuario__username"),
          ("nombre", "telefono"), crear=False, borrar=False, orden=("nombre",), relacionados=("usuario",),
          ayuda="Se crean, activan y desactivan en Usuarios. Para reasignar su cartera, edita cada cliente o prospecto."),
    Tabla("regiones", "Regiones", "Territorio", "territorio", Region, [("Nombre", "nombre")], ("nombre",), ("nombre",), orden=("nombre",)),
    Tabla("comunas", "Comunas", "Territorio", "territorio", Comuna, [("Nombre", "nombre"), ("Región", "region.nombre")], ("nombre", "region__nombre"),
          ("region", "nombre"), orden=("nombre",), relacionados=("region",)),
    Tabla("prospectos", "Prospectos", "CRM", "embudo", Prospecto,
          [("Contacto", "nombre_contacto"), ("Empresa", "empresa"), ("Etapa", "etapa.nombre"), ("Vendedor", "vendedor.nombre"), ("Monto estimado", "monto_estimado_clp")],
          ("nombre_contacto", "empresa"), ("nombre_contacto", "empresa", "email", "telefono", "origen", "monto_estimado_clp", "vendedor"), crear=False, borrar=False,
          ajustar=_vendedores_activos, validar=_validar_prospecto, orden=("nombre_contacto",), relacionados=("etapa", "vendedor"),
          ayuda="Se crean y cambian de etapa en el embudo del CRM, que aplica las reglas de cada paso."),
    Tabla("etapas", "Etapas del embudo", "CRM", "etapas", EtapaPipeline,
          [("Orden", "orden_etapa"), ("Nombre", "nombre"), ("Final", "es_final"), ("Ganada", "es_ganada")], ("nombre",),
          ("nombre", "orden_etapa", "es_final", "es_ganada"), validar=_validar_etapa, protegida=_etapa_necesaria, orden=("orden_etapa",),
          ayuda="«Contactado» y «Propuesta enviada» son fijas, y siempre debe quedar una etapa ganada y una final perdida."),
    Tabla("categorias-requerimiento", "Categorías de requerimiento", "CRM", "requerimientos", CategoriaRequerimiento, [("Nombre", "nombre")], ("nombre",), ("nombre",),
          validar=_validar_categoria_requerimiento, protegida=_categoria_requerimiento_protegida, orden=("nombre",),
          ayuda="«Reclamo por temperatura» y «Problema en la entrega» son fijas: el sistema las busca por su nombre."),
    Tabla("estados-orden", "Estados de orden", "Pedidos", "estados", EstadoOrden,
          [("Orden", "orden_flujo"), ("Nombre", "nombre"), ("Final", "es_final")], ("nombre",), ("nombre",), crear=False, editar=False, borrar=False,
          orden=("orden_flujo",), ayuda="Solo lectura: el sistema y el simulador buscan estos estados por su nombre."),
]

TABLAS = {t.slug: t for t in _LISTA}
GRUPOS = ("Catálogo", "Flota", "Clientes", "Territorio", "CRM", "Pedidos")
