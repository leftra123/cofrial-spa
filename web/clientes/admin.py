from django.contrib import admin

from .models import AceptacionLegal, Cliente, Comuna, Direccion, Region, SegmentoCliente, TipoCliente, Vendedor


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "tipo_cliente", "vendedor", "email")
    list_filter = ("tipo_cliente", "segmento", "vendedor")
    search_fields = ("nombre", "rut", "email")
    inlines = [DireccionInline]


admin.site.register([Region, Comuna, TipoCliente, Vendedor, SegmentoCliente])


@admin.register(AceptacionLegal)
class AceptacionLegalAdmin(admin.ModelAdmin):
    """Constancia del consentimiento: se consulta, no se edita ni se borra desde el panel."""
    list_display = ("usuario", "version", "aceptado_en", "ip")
    search_fields = ("usuario__username",)
    readonly_fields = ("usuario", "version", "aceptado_en", "ip")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
