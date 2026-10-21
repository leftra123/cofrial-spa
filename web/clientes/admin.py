from django.contrib import admin

from .models import Cliente, Comuna, Direccion, Region, TipoCliente, Vendedor


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "tipo_cliente", "vendedor", "email")
    list_filter = ("tipo_cliente", "vendedor")
    search_fields = ("nombre", "rut", "email")
    inlines = [DireccionInline]


admin.site.register([Region, Comuna, TipoCliente, Vendedor])
