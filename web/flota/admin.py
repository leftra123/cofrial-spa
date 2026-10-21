from django.contrib import admin

from .models import Camion, Despacho, Telemetria


@admin.register(Telemetria)
class TelemetriaAdmin(admin.ModelAdmin):
    list_display = ("camion", "temp_camara", "lat", "long", "combustible_pct", "alerta_ruptura_frio", "registrado_en")
    list_filter = ("camion", "alerta_ruptura_frio")
    date_hierarchy = "registrado_en"


admin.site.register([Camion, Despacho])
