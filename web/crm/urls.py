from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="crm"),
    path("embudo/", views.embudo, name="crm_embudo"),
    path("prospectos/nuevo/", views.prospecto_nuevo, name="crm_prospecto_nuevo"),
    path("prospectos/<int:pk>/", views.prospecto_detalle, name="crm_prospecto"),
    path("prospectos/<int:pk>/mover/", views.prospecto_mover, name="crm_prospecto_mover"),
    path("prospectos/<int:pk>/interaccion/", views.prospecto_interaccion, name="crm_prospecto_interaccion"),
    path("clientes/", views.clientes, name="crm_clientes"),
    path("clientes/<int:pk>/", views.cliente_ficha, name="crm_cliente"),
    path("clientes/<int:pk>/interaccion/", views.cliente_interaccion, name="crm_cliente_interaccion"),
    path("clientes/<int:pk>/pedido/", views.cliente_pedido, name="crm_cliente_pedido"),
    path("requerimientos/", views.requerimientos, name="crm_requerimientos"),
    path("requerimientos/<int:pk>/ia/", views.requerimiento_ia, name="crm_requerimiento_ia"),
    path("requerimientos/<int:pk>/clasificar/", views.requerimiento_clasificar, name="crm_requerimiento_clasificar"),
    path("ia/", views.ia_panel, name="crm_ia"),
    path("demanda/", views.demanda, name="crm_demanda"),
    path("alertas/", views.alertas, name="crm_alertas"),
]
