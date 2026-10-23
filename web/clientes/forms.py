from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from . import rut as rutlib
from .models import Cliente, Comuna, Direccion, TipoCliente


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
            raise forms.ValidationError("Ya existe una cuenta con ese correo. Ingresa desde «Ingresar».")
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
    def guardar(self):
        d = self.cleaned_data
        u = get_user_model().objects.create_user(d["email"], email=d["email"], password=d["clave"])
        c = Cliente.objects.create(usuario=u, tipo_cliente=TipoCliente.objects.get(codigo="B2C"), rut=d["rut"],
                                   nombre=d["nombre"], email=d["email"], telefono=d["telefono"])
        Direccion.objects.create(cliente=c, calle_numero=d["direccion"], comuna=d["comuna"], es_principal=True)
        return u
