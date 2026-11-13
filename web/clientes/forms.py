from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.safestring import mark_safe

from . import geo, rut as rutlib
from .models import AceptacionLegal, Cliente, Comuna, Direccion, TipoCliente

ACEPTA_ETIQUETA = mark_safe('Leí y acepto los <a href="/legal/terminos/" target="_blank" rel="noopener">términos y condiciones</a> '
                            'y la <a href="/legal/privacidad/" target="_blank" rel="noopener">política de privacidad</a>')


def registrar_aceptacion(usuario, ip=None):
    """Deja constancia de quién aceptó, cuándo, qué versión y desde qué IP (la versión vigente está en cofrial/legal.py)."""
    from cofrial.legal import VERSION
    return AceptacionLegal.objects.create(usuario=usuario, version=VERSION, ip=ip or None)


class RegistroB2CForm(forms.Form):
    """Registro de un cliente particular (perfil B2C): crea la cuenta, el cliente y su dirección principal."""
    nombre = forms.CharField(label="Nombre completo", max_length=120)
    rut = forms.CharField(label="RUT", max_length=12, help_text="Con o sin puntos, con dígito verificador.")
    email = forms.EmailField(label="Correo electrónico", max_length=120)
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=20, required=False)
    direccion = forms.CharField(label="Dirección de entrega", max_length=150)
    comuna = forms.ModelChoiceField(label="Comuna", queryset=Comuna.objects.order_by("nombre"), empty_label=None)
    clave = forms.CharField(label="Clave", widget=forms.PasswordInput, help_text="Al menos 8 caracteres y no una clave común.")
    clave2 = forms.CharField(label="Repite la clave", widget=forms.PasswordInput)
    # La casilla parte sin marcar y es obligatoria: el consentimiento tiene que ser un acto de la persona, no un valor por defecto.
    acepta = forms.BooleanField(label=ACEPTA_ETIQUETA, required=True,
                                error_messages={"required": "Para crear la cuenta tienes que aceptar los términos y la política de privacidad."})
    template_name_p = "clientes/_form_p.html"      # dentro de la app: el renderizador de formularios no mira la carpeta templates del proyecto

    def clean_rut(self):
        valor = self.cleaned_data["rut"]
        if not rutlib.es_valido(valor):
            raise forms.ValidationError("El RUT no es válido; revisa el dígito verificador.")
        valor = rutlib.formatear(valor)
        if Cliente.objects.filter(rut=valor).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese RUT.")
        return valor

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo. Ingresa desde \"Ingresar\".")
        return email

    def clean(self):
        datos = super().clean()
        if datos.get("clave") and datos.get("clave2") and datos["clave"] != datos["clave2"]:
            self.add_error("clave2", "Las claves no coinciden.")
        elif datos.get("clave"):
            try:
                validate_password(datos["clave"])
            except forms.ValidationError as e:
                self.add_error("clave", e)
        return datos

    @transaction.atomic
    def guardar(self, ip=None):
        d = self.cleaned_data
        u = get_user_model().objects.create_user(d["email"], email=d["email"], password=d["clave"])
        registrar_aceptacion(u, ip)
        c = Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2C"), rut=d["rut"],
                                   nombre=d["nombre"], email=d["email"], telefono=d["telefono"])
        dir_ = Direccion.objects.create(cliente=c, calle_numero=d["direccion"], comuna=d["comuna"], es_principal=True)
        self.ubicada = geo.ubicar(dir_)
        return u


class RegistroEmpresaForm(RegistroB2CForm):
    """Solicitud de cuenta de una empresa (perfil B2B). Queda inactiva y sin vendedor hasta que ventas la aprueba en el CRM
    (crm/solicitudes): así la lista de precios institucional y el crédito no se entregan a cualquiera que se registre."""

    giro = forms.CharField(label="Giro", max_length=80, help_text="Actividad económica, tal como va en la factura (p. ej. «Hotelería»).")
    field_order = ["nombre", "rut", "giro", "email", "telefono", "direccion", "comuna", "clave", "clave2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo, etiqueta, ayuda in (("nombre", "Razón social", None), ("rut", "RUT de la empresa", "Con o sin puntos, con dígito verificador."),
                                       ("email", "Correo de compras", "Con este correo se ingresa y llegan los avisos de los pedidos."),
                                       ("telefono", "Teléfono de contacto (opcional)", None), ("direccion", "Dirección de despacho", None)):
            self.fields[campo].label = etiqueta
            if ayuda:
                self.fields[campo].help_text = ayuda

    @transaction.atomic
    def guardar(self, ip=None):
        d = self.cleaned_data
        u = get_user_model().objects.create_user(d["email"], email=d["email"], password=d["clave"], is_active=False)
        registrar_aceptacion(u, ip)
        c = Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2B"), rut=d["rut"], giro=d["giro"],
                                   nombre=d["nombre"], email=d["email"], telefono=d["telefono"])
        dir_ = Direccion.objects.create(cliente=c, calle_numero=d["direccion"], comuna=d["comuna"], es_principal=True)
        self.ubicada = geo.ubicar(dir_)
        return c
