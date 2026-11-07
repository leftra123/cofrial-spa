"""Formularios del administrador. Las claves usan PasswordInput (nunca devuelve el valor al volver a pintar el formulario)."""
from django import forms
from django.contrib.auth import get_user_model

from clientes import cuentas, rut as rutlib
from clientes.models import Comuna, Vendedor

CLASES_CLIENTE = ("cliente-b2b", "cliente-b2c")


class ClaveMixin(forms.Form):
    clave = forms.CharField(label="Clave", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                            help_text="Al menos 8 caracteres y que no sea una clave común.")
    clave2 = forms.CharField(label="Repite la clave", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def verificar_clave(self, usuario=None):
        d = self.cleaned_data
        if d.get("clave") and d.get("clave2") and d["clave"] != d["clave2"]:
            self.add_error("clave2", "Las claves no coinciden.")
        elif d.get("clave"):
            try:
                cuentas.validar_clave(d["clave"], usuario)
            except cuentas.ErrorCuenta as e:
                self.add_error("clave", str(e).removeprefix("Clave no válida: "))

    def marcar_errores(self):
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs["aria-invalid"] = "true"


class CuentaNuevaForm(ClaveMixin):
    usuario = forms.CharField(label="Usuario (correo)", max_length=150, help_text="Con este correo ingresa la persona. Se guarda en minúsculas.",
                              widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "none"}))
    rol = forms.ChoiceField(label="Rol", choices=cuentas.ROLES)
    nombre = forms.CharField(label="Nombre de la persona o empresa", max_length=120, required=False,
                             help_text="Obligatorio para clientes y vendedores.")
    rut = forms.CharField(label="RUT del cliente", max_length=12, required=False, help_text="Con o sin puntos, con dígito verificador.")
    direccion = forms.CharField(label="Dirección de entrega", max_length=150, required=False)
    comuna = forms.ModelChoiceField(label="Comuna", queryset=Comuna.objects.none(), required=False, empty_label=None)
    vendedor = forms.ModelChoiceField(label="Vendedor asignado", queryset=Vendedor.objects.none(), required=False, empty_label="Sin vendedor",
                                      help_text="Cartera del cliente institucional (B2B).")
    field_order = ["usuario", "rol", "nombre", "rut", "direccion", "comuna", "vendedor", "clave", "clave2"]

    def __init__(self, *args, tipo=None, **kwargs):
        """Con `tipo` (un rol de cuentas.ROLES, ya validado por la vista) el rol queda fijo y el formulario pide solo los campos de ese tipo."""
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        self.fields["comuna"].queryset = Comuna.objects.order_by("nombre")
        self.fields["vendedor"].queryset = Vendedor.objects.filter(activo=True).select_related("usuario").order_by("nombre")
        if not self.is_bound:
            self.initial.setdefault("comuna", Comuna.objects.filter(nombre="Temuco").values_list("pk", flat=True).first())
        if tipo:
            self.fields["rol"].widget = forms.HiddenInput()
            self.initial["rol"] = tipo
            self.fields["nombre"].label = "Nombre de la empresa" if tipo == "cliente-b2b" else "Nombre completo" if tipo == "cliente-b2c" else "Nombre"
            if tipo not in CLASES_CLIENTE:
                for campo in ("rut", "direccion", "comuna", "vendedor"):
                    del self.fields[campo]
            elif tipo != "cliente-b2b":
                del self.fields["vendedor"]

    def clean_usuario(self):
        return self.cleaned_data["usuario"].strip().lower()

    def clean_rut(self):
        valor = self.cleaned_data["rut"].strip()
        if valor and not rutlib.es_valido(valor):
            raise forms.ValidationError("El RUT no es válido; revisa el dígito verificador.")
        return rutlib.formatear(valor) if valor else ""

    def clean(self):
        d = super().clean()
        rol = d.get("rol")
        usuario = d.get("usuario")
        if rol in CLASES_CLIENTE:
            for campo, texto in (("nombre", "Indica el nombre."), ("rut", "Indica el RUT."), ("direccion", "Indica la dirección de entrega."),
                                 ("comuna", "Elige la comuna.")):
                if not d.get(campo) and campo not in self.errors:
                    self.add_error(campo, texto)
        elif rol == "vendedor" and not d.get("nombre") and "nombre" not in self.errors:
            self.add_error("nombre", "Indica el nombre del vendedor.")
        if self.errors:                                           # los datos sueltos fallaron: no tiene sentido seguir con el resto
            self.verificar_clave()
            return d
        try:
            self.datos = cuentas.preparar(usuario, rol, nombre=d.get("nombre", ""), rut=d.get("rut") or None, direccion=d.get("direccion") or None,
                                          comuna=d["comuna"].nombre if d.get("comuna") else "Temuco",
                                          vendedor=d["vendedor"].usuario.username if rol == "cliente-b2b" and d.get("vendedor") else None)
        except cuentas.ErrorCuenta as e:
            self.add_error(e.campo if e.campo in self.fields else None, str(e))
        self.verificar_clave(get_user_model()(username=usuario, email=usuario if "@" in (usuario or "") else ""))
        return d

    def guardar(self):
        return cuentas.crear(self.datos, self.cleaned_data["clave"])

    def is_valid(self):
        valido = super().is_valid()
        self.marcar_errores()
        return valido


class ClaveNuevaForm(ClaveMixin):
    """Clave nueva para una cuenta que ya existe."""
    clave = forms.CharField(label="Clave nueva", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                            help_text="Al menos 8 caracteres y que no sea una clave común.")
    clave2 = forms.CharField(label="Repite la clave nueva", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, usuario, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

    def clean(self):
        d = super().clean()
        self.verificar_clave(self.usuario)
        return d

    def is_valid(self):
        valido = super().is_valid()
        self.marcar_errores()
        return valido

    def guardar(self):
        self.usuario.set_password(self.cleaned_data["clave"])
        self.usuario.save(update_fields=["password"])


class ClienteCuentaForm(ClaveMixin):
    """Cuenta del portal para un cliente que ya existe: solo el usuario y la clave; el RUT, el nombre y las direcciones son los del cliente."""
    usuario = forms.CharField(label="Usuario (correo)", max_length=150, help_text="Con este correo ingresa el cliente. Se guarda en minúsculas.",
                              widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "none"}))
    field_order = ["usuario", "clave", "clave2"]

    def clean_usuario(self):
        return self.cleaned_data["usuario"].strip().lower()

    def clean(self):
        d = super().clean()
        usuario = d.get("usuario")
        if usuario and "usuario" not in self.errors:
            try:
                cuentas.validar_nombre_libre(usuario)
            except cuentas.ErrorCuenta as e:
                self.add_error("usuario", str(e))
        self.verificar_clave(get_user_model()(username=usuario or "", email=usuario if "@" in (usuario or "") else ""))
        return d

    def guardar(self, cliente):
        return cuentas.crear_para_cliente(cliente, self.cleaned_data["usuario"], self.cleaned_data["clave"])

    def is_valid(self):
        valido = super().is_valid()
        self.marcar_errores()
        return valido
