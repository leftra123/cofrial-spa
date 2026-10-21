from django.contrib import admin

from .models import CategoriaRequerimiento, EtapaPipeline, Interaccion, Prospecto, Requerimiento


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = ("nombre_contacto", "empresa", "etapa", "vendedor", "monto_estimado_clp", "origen")
    list_filter = ("etapa", "vendedor", "origen")
    search_fields = ("nombre_contacto", "empresa")


@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = ("asunto", "cliente", "categoria_requerimiento", "confianza_ia", "estado", "creado_en")
    list_filter = ("estado", "categoria_requerimiento")


admin.site.register([EtapaPipeline, Interaccion, CategoriaRequerimiento])
