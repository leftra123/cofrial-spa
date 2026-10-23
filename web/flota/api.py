"""API JSON de solo lectura (Django REST Framework). La usa la pantalla de flota para refrescarse sin recargar."""
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from crm import servicios as crm
from pedidos import servicios as pedidos

from .servicios import estado_flota


class PuedeVerFlota(BasePermission):
    """Mismos roles que la pantalla /flota/."""
    message = "Tu cuenta no tiene acceso a la flota."

    def has_permission(self, request, view):
        return crm.rol(request.user) in ("admin", "gerencia", "despachador")


class LecturaSerializer(serializers.Serializer):
    temp_camara = serializers.FloatField()
    lat = serializers.FloatField()
    long = serializers.FloatField()
    combustible_pct = serializers.IntegerField()
    alerta_ruptura_frio = serializers.BooleanField()
    registrado_en = serializers.DateTimeField()


class CamionSerializer(serializers.Serializer):
    camion_id = serializers.CharField(source="camion.camion_id")
    patente = serializers.CharField(source="camion.patente")
    capacidad_kg = serializers.IntegerField(source="camion.capacidad_kg")
    rango_temperatura = serializers.CharField(source="camion.rango_temperatura.nombre")
    activo = serializers.BooleanField(source="camion.activo")
    en_ruta = serializers.SerializerMethodField()
    alerta = serializers.BooleanField()
    combustible_bajo = serializers.BooleanField()
    ultima_lectura = LecturaSerializer(source="lectura", allow_null=True)

    def get_en_ruta(self, obj):
        return obj["viaje"] is not None


class FlotaAPI(APIView):
    permission_classes = [PuedeVerFlota]

    def get(self, request):
        tarjetas, resumen = estado_flota()
        return Response({"resumen": resumen, "camiones": CamionSerializer(tarjetas, many=True).data})


class PedidosAPI(APIView):
    """Órdenes del cliente autenticado (B2B o B2C), para que su propio sistema las consulte."""

    def get(self, request):
        cliente = pedidos.cliente_de(request.user)
        if cliente is None:
            return Response({"detail": "Tu cuenta no está asociada a un cliente."}, status=403)
        datos = [{"orden_id": o.orden_id, "estado": o.estado_orden.nombre, "creada_en": o.creada_en,
                  "numero_oc": o.numero_oc, "total_clp": pedidos.total_orden(o)}
                 for o in pedidos.ordenes_de(cliente)]
        return Response({"cliente": cliente.nombre, "ordenes": datos})


class SeguimientoAPI(APIView):
    """Posición y temperatura del camión de una orden del propio cliente; la pantalla de la orden la consulta cada 5 s."""

    def get(self, request, orden_id):
        cliente = pedidos.cliente_de(request.user)
        if cliente is None:
            return Response({"detail": "Tu cuenta no está asociada a un cliente."}, status=403)
        orden = pedidos.ordenes_de(cliente).filter(pk=orden_id).first()
        if orden is None:
            return Response({"detail": "Orden no encontrada."}, status=404)       # ajena e inexistente se ven igual
        return Response({"orden_id": orden.orden_id, "estado": orden.estado_orden.nombre,
                         "seguimiento": pedidos.seguimiento(orden)})
