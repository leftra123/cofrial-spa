from django.contrib import admin

from .models import Categoria, ListaPrecio, PrecioProducto, Producto, RangoTemperatura


class PrecioInline(admin.TabularInline):
    model = PrecioProducto
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "nombre", "categoria", "unidad_medida", "stock_disponible", "activo")
    list_filter = ("categoria", "activo")
    search_fields = ("sku", "nombre")
    inlines = [PrecioInline]


admin.site.register([RangoTemperatura, Categoria, ListaPrecio])
