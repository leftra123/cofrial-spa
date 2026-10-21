from django.urls import path

from . import views

urlpatterns = [path("", views.listado, name="catalogo")]
