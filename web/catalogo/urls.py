from django.urls import path

from . import views

urlpatterns = [
    path("", views.listado, name="catalogo"),
    path("<int:producto_id>/", views.detalle, name="producto"),
]
