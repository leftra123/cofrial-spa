from django.contrib import admin

from . import servicios
from .models import CategoriaRequerimiento, EtapaPipeline, Interaccion, Prospecto, Requerimiento


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = ("nombre_contacto", "empresa", "etapa", "vendedor", "monto_estimado_clp", "origen")
    list_filter = ("etapa", "vendedor", "origen")
    search_fields = ("nombre_contacto", "empresa")


@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = ("asunto", "cliente", "categoria_requerimiento", "clasificado_por", "confianza_ia", "estado", "creado_en")
    list_filter = ("estado", "categoria_requerimiento")
    search_fields = ("asunto", "descripcion")
    actions = ["clasificar_con_ia"]

    @admin.display(description="Clasificado por")
    def clasificado_por(self, r):
        if r.categoria_requerimiento_id and r.confianza_ia is not None:
            return "IA"
        if r.categoria_requerimiento_id:
            return "Manual"
        return "IA dudó" if r.confianza_ia is not None else "Nadie aún"

    @admin.action(description="Clasificar con IA los requerimientos seleccionados")
    def clasificar_con_ia(self, request, queryset):
        clasificados = dudosos = 0
        for r in queryset:
            servicios.clasificar_con_ia(r)
            if r.estado == "clasificado":
                clasificados += 1
            else:
                dudosos += 1
        self.message_user(request, f"IA: {clasificados} clasificado(s); {dudosos} quedaron sin clasificar (la IA dudó o no estuvo disponible).")


admin.site.register([EtapaPipeline, Interaccion, CategoriaRequerimiento])
