from django.urls import path

from . import vistas

urlpatterns = [
    path("", vistas.panel, name="torre"),
    path("pulso/", vistas.pulso, name="torre_pulso"),
]
