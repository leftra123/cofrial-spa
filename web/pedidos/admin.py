from django.contrib import admin, messages

from . import servicios

from .models import Carrito, CarritoItem, Documento, EstadoOrden, Orden, OrdenItem, Pago


class OrdenItemInline(admin.TabularInline):
    model = OrdenItem
    extra = 0


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ("orden_id", "direccion", "estado_orden", "despacho", "numero_oc", "creada_en")
    list_filter = ("estado_orden",)
    inlines = [OrdenItemInline]
    actions = ["avanzar_estado", "cancelar_ordenes"]

    @admin.action(description="Avanzar al siguiente estado")
    def avanzar_estado(self, request, queryset):
        for orden in queryset:
            try:
                servicios.avanzar(orden)
            except servicios.ErrorDeNegocio as e:
                self.message_user(request, f"Orden {orden.orden_id}: {e}", messages.ERROR)

    @admin.action(description="Cancelar (vendedor, hasta «En preparación»; repone stock)")
    def cancelar_ordenes(self, request, queryset):
        for orden in queryset:
            try:
                servicios.cancelar(orden, como="vendedor")
            except servicios.ErrorDeNegocio as e:
                self.message_user(request, f"Orden {orden.orden_id}: {e}", messages.ERROR)


class CarritoItemInline(admin.TabularInline):
    model = CarritoItem
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("carrito_id", "cliente", "estado", "creado_en")
    inlines = [CarritoItemInline]


admin.site.register(EstadoOrden)


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "folio", "orden", "monto_clp", "vence_en", "emitido_en")
    list_filter = ("tipo",)
    search_fields = ("folio", "orden__numero_oc")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("pago_id", "documento", "monto_clp", "medio", "referencia", "pagado_en")
    list_filter = ("medio",)
