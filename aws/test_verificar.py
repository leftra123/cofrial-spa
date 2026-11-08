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
    def test_nombre_sslip_desde_la_ip(self):
        self.assertEqual(v.nombre_sslip("54.82.100.161"), "54-82-100-161.sslip.io")

    def test_nombre_sslip_no_toca_un_nombre_de_host(self):
        self.assertIsNone(v.nombre_sslip("localhost"))
        self.assertIsNone(v.nombre_sslip("54-82-100-161.sslip.io"))

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


if __name__ == "__main__":
    unittest.main(argv=["test_verificar"], verbosity=1)
