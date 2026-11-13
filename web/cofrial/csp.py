"""Política de contenido (CSP) propia de una vista. La del sitio está en settings.SECURE_CSP y la pone el middleware de Django."""
from django.conf import settings
from django.views.decorators.csp import csp_override, csp_report_only_override


def politica_propia(config):
    """La vista responde con `config` en lugar de la política del sitio, en el mismo modo que DJANGO_CSP: aplicada, solo informe o apagada."""
    def decorar(vista):
        vista = csp_report_only_override(config if settings.CSP_MODO == "informe" else {})(vista)
        return csp_override(config if settings.CSP_MODO == "1" else {})(vista)
    return decorar
