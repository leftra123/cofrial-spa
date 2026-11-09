#!/usr/bin/env python3
"""Pruebas de los ayudantes de aws/verificar.py con una sesión simulada (sin red, sin AWS): python3 aws/test_verificar.py"""
import contextlib
import datetime
import importlib.util
import io
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["verificar.py", "http://localhost:1"]          # verificar.py lee la dirección al importarse
_spec = importlib.util.spec_from_file_location("verificar", os.path.join(AQUI, "verificar.py"))
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)

AHORA = datetime.datetime.now(datetime.timezone.utc)


def orden(oid, estado="Recibida", oc="ENSAYO-20261110-1000", dias=0):
    return {"orden_id": oid, "estado": estado, "numero_oc": oc, "creada_en": (AHORA - datetime.timedelta(days=dias)).isoformat()}


class SesionFalsa:
    """Responde como el sitio: lista de pedidos, catálogo, carrito y confirmación; anota cada POST."""
    def __init__(self, ordenes, mp=False, confirma_bien=True):
        self.ordenes, self.mp, self.confirma_bien, self.posts = ordenes, mp, confirma_bien, []

    def json(self, ruta):
        return 200, {"ordenes": self.ordenes}

    def token(self, ruta, base=None):
        return "tok"

    def pedir(self, ruta, datos=None, base=None):
        if datos is not None:
            self.posts.append((ruta, datos))
        if ruta == "/catalogo/":
            return 200, '<article data-sku="VAC-LOM-5K"><input type="hidden" name="producto" value="7">', v.BASE + ruta
        if ruta == "/carrito/" and datos is None:
            marca = 'data-checkout="mp-modal-v4"' if self.mp else ""
            return 200, f'{marca}<select name="direccion" id="d"><option value="42" selected>x</option></select>', v.BASE + ruta
        if ruta == "/carrito/confirmar/":
            return 200, "", v.BASE + ("/pedidos/9/?nueva=1" if self.confirma_bien else "/carrito/")
        return 200, "", v.BASE + ruta


class Ayudantes(unittest.TestCase):
    def test_una_direccion_local_nunca_se_contrasta_con_aws(self):
        for host in ("localhost", "127.0.0.1", "mi-rama.localhost"):
            self.assertTrue(v.es_local(host))
        for host in ("54.82.100.161", "cofrialspa.webhop.me", "cofrial-alb-1.us-east-1.elb.amazonaws.com"):
            self.assertFalse(v.es_local(host))

    def test_nombre_alterno_solo_si_se_pide(self):
        original = sys.argv[:]
        try:
            sys.argv = ["verificar.py", "http://localhost:1"]
            self.assertIsNone(v.nombre_alterno())                          # nunca se adivina un nombre: la clave no se manda a un host que nadie pidió
            sys.argv = ["verificar.py", "http://localhost:1", "--nombre=https://mi.dominio/"]
            self.assertEqual(v.nombre_alterno(), "https://mi.dominio")
        finally:
            sys.argv = original

    def test_fila_del_requerimiento_lee_solo_su_fila(self):
        html = '<tr><td><a><b>Otro</b></a></td><span>sin clasificar</span></tr><tr><td><a><b>Mi pedido llegó tibio</b></a></td><span>clasificado</span></tr>'
        fila = v.fila_del_requerimiento(html, "Mi pedido llegó tibio")
        self.assertIn("clasificado</span>", fila)
        self.assertNotIn("sin clasificar", fila)
        self.assertIsNone(v.fila_del_requerimiento(html, "No existe"))

    def test_pedidos_vigentes_descarta_lo_que_no_es_venta_ni_reciente(self):
        s = SesionFalsa([orden(1), orden(2, estado="Cancelada"), orden(3, estado="Rechazada en recepción"), orden(4, oc="HIS-9"), orden(5, dias=8), orden(6, oc="OC-1")])
        self.assertEqual([o["orden_id"] for o in v.pedidos_vigentes(s, solo_ensayo=False)], [1, 6])
        self.assertEqual([o["orden_id"] for o in v.pedidos_vigentes(s, solo_ensayo=True)], [1])

    def test_exigir_es_aviso_antes_de_la_defensa_y_falla_en_modo_defensa(self):
        for defensa, esperado in ((False, "aviso"), (True, "mal")):
            v.DEFENSA, v.RESULTADOS[:] = defensa, []
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(v.exigir(False, "x"))
            self.assertEqual(v.RESULTADOS[0][0], esperado)
        v.DEFENSA = False


class CompraDeEnsayo(unittest.TestCase):
    def test_no_repite_si_ya_hay_una_vigente(self):
        s = SesionFalsa([orden(1)])
        self.assertEqual(v.comprar_ensayo(s, "B2B")[0], "vigente")
        self.assertEqual(s.posts, [])                                     # no agregó nada al carrito ni confirmó

    def test_b2b_confirma_con_oc_de_ensayo_y_factura(self):
        s = SesionFalsa([orden(5, oc="OC-1")])                            # un pedido real que no es de ensayo no cuenta como vigente en B2B
        estado, _ = v.comprar_ensayo(s, "B2B")
        confirmar = dict(s.posts)["/carrito/confirmar/"]
        self.assertEqual(estado, "creada")
        self.assertTrue(confirmar["numero_oc"].startswith("ENSAYO-"))
        self.assertEqual((confirmar["comprobante"], confirmar["direccion"]), ("factura", "42"))
        self.assertEqual(dict(s.posts)["/carrito/agregar/"]["producto"], "7")

    def test_b2c_confirma_con_boleta_y_sin_oc(self):
        estado, _ = v.comprar_ensayo(s := SesionFalsa([]), "B2C")
        confirmar = dict(s.posts)["/carrito/confirmar/"]
        self.assertEqual(estado, "creada")
        self.assertEqual(confirmar["comprobante"], "boleta")
        self.assertNotIn("numero_oc", confirmar)

    def test_b2c_con_mercado_pago_no_compra_y_deja_el_carrito_vacio(self):
        estado, _ = v.comprar_ensayo(s := SesionFalsa([], mp=True), "B2C")
        self.assertEqual(estado, "mp")
        self.assertNotIn("/carrito/confirmar/", dict(s.posts))
        self.assertEqual(dict(s.posts)["/carrito/actualizar/"]["cantidad"], "0")

    def test_si_la_orden_no_se_genera_es_un_error(self):
        self.assertEqual(v.comprar_ensayo(SesionFalsa([], confirma_bien=False), "B2B")[0], "error")


def infra_ok():
    """Lo que dejaría la rama de alta disponibilidad: ALB en dos zonas, dos web sanas en zonas distintas y RDS Multi-AZ."""
    return {"cli": True, "lb": {"estado": "active", "esquema": "internet-facing", "zonas": ["us-east-1a", "us-east-1b"], "dns": "cofrial-alb-1.us-east-1.elb.amazonaws.com"},
            "puertos": [80, 443],
            "destinos": [{"id": "i-1", "estado": "healthy", "zona": "us-east-1a"}, {"id": "i-2", "estado": "healthy", "zona": "us-east-1b"}],
            "db": {"multi_az": True, "estado": "available", "zona": "us-east-1a", "respaldo": "us-east-1b"}, "sg_web_abierto": []}


def fallan(info):
    return [nombre for ok, nombre, _ in v.juzgar_infra(info) if not ok]


class InfraDeAltaDisponibilidad(unittest.TestCase):
    def test_la_instalacion_de_alta_disponibilidad_pasa_completa(self):
        self.assertEqual(fallan(infra_ok()), [])

    def test_sin_aws_cli_con_credenciales_no_se_puede_comprobar(self):
        self.assertEqual(len(fallan({"cli": False})), 1)

    def test_sin_balanceador_falla(self):
        info = infra_ok(); info["lb"] = None
        self.assertTrue(any("ALB" in n for n in fallan(info)))

    def test_un_balanceador_en_una_sola_zona_falla(self):
        info = infra_ok(); info["lb"]["zonas"] = ["us-east-1a"]
        self.assertTrue(any("dos zonas" in n for n in fallan(info)))

    def test_dos_web_en_la_misma_zona_fallan(self):
        info = infra_ok(); info["destinos"][1]["zona"] = "us-east-1a"
        self.assertTrue(any("zonas distintas" in n for n in fallan(info)))

    def test_una_web_que_no_esta_sana_no_cuenta(self):
        info = infra_ok(); info["destinos"][1]["estado"] = "unhealthy"
        self.assertTrue(any("sanas" in n for n in fallan(info)))

    def test_rds_sin_multi_az_falla(self):
        info = infra_ok(); info["db"]["multi_az"] = False
        self.assertTrue(any("Multi-AZ" in n for n in fallan(info)))

    def test_sin_listener_https_falla(self):
        info = infra_ok(); info["puertos"] = [80]
        self.assertTrue(any("443" in n for n in fallan(info)))

    def test_el_acceso_directo_abierto_a_internet_falla(self):
        info = infra_ok(); info["sg_web_abierto"] = [80, 443]
        self.assertTrue(any("acceso directo" in n for n in fallan(info)))


if __name__ == "__main__":
    unittest.main(argv=["test_verificar"], verbosity=1)
