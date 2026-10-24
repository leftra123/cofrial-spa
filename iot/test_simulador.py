"""Pruebas del movimiento del camión (sin base de datos). Desde iot/:  CAMION_ID=CAM-01 python -m unittest test_simulador"""
import os
import unittest

os.environ.setdefault("CAMION_ID", "CAM-01")
os.environ["VELOCIDAD_KMH"] = "120"
os.environ["INTERVALO_SEG"] = "5"
os.environ["DETENCION_LECTURAS"] = "3"
import simulador as sim  # noqa: E402

CASA = (-38.7400, -72.6000)       # a ~2 km de la base
OTRA = (-38.7500, -72.6200)


def viaje(*paradas):
    c = sim.Camion(0, 5)
    c.asignar(1, list(paradas))
    return c


class MovimientoTest(unittest.TestCase):
    def test_llega_a_la_direccion_y_se_queda(self):
        c = viaje(CASA)
        for _ in range(200):
            c.posicion()
        self.assertEqual(c.pos, CASA)
        self.assertLess(sim.km_entre(c.posicion(), CASA), 0.001)     # estacionado: sigue ahí en las lecturas siguientes

    def test_se_acerca_sin_pasarse(self):
        c = viaje(CASA)
        previa = sim.km_entre(c.pos, CASA)
        for _ in range(500):
            lat, lon = c.posicion()
            ahora = sim.km_entre((lat, lon), CASA)
            self.assertLessEqual(ahora, previa + 1e-9)
            previa = ahora

    def test_demora_razonable(self):
        c = viaje(CASA)
        d = sim.km_entre(c.pos, CASA)
        lecturas = 0
        while c.pos != CASA:
            c.posicion()
            lecturas += 1
        self.assertEqual(lecturas, -(-d // (120 * 5 / 3600)))        # distancia / paso, redondeado hacia arriba

    def test_orden_vecino_mas_cercano_y_detencion_intermedia(self):
        c = viaje(OTRA, CASA)                                        # CASA queda más cerca de la posición inicial
        self.assertEqual(c.paradas, sim.ordenar_paradas(c.pos, [OTRA, CASA]))
        visitadas, quieto = [], 0
        for _ in range(400):
            antes = c.pos
            c.posicion()
            if c.pos == antes and c.pos in (CASA, OTRA) and c.paradas:
                quieto += 1
            if c.pos in (CASA, OTRA) and (not visitadas or visitadas[-1] != c.pos):
                visitadas.append(c.pos)
        self.assertEqual(visitadas[-1], OTRA)
        self.assertEqual(len(visitadas), 2)
        self.assertEqual(quieto, 3)                                  # DETENCION_LECTURAS en la parada intermedia

    def test_viaje_terminado_vuelve_a_patrullar(self):
        c = viaje(CASA)
        for _ in range(200):
            c.posicion()
        c.asignar(None, [])
        antes = c.pos
        c.posicion()
        self.assertNotEqual(c.pos, antes)

    def test_pedido_cerrado_deja_de_ser_parada(self):
        c = viaje(CASA, OTRA)
        c.asignar(1, [OTRA])
        self.assertEqual(c.paradas, [OTRA])

    def test_telemetria_conserva_los_campos_de_la_pauta(self):
        c = viaje(CASA)
        temp, lat, lon, comb, alerta = c.paso()
        self.assertIsInstance(temp, float)
        self.assertIsInstance(comb, int)
        self.assertIsInstance(alerta, bool)
        self.assertLess(abs(lat - c.pos[0]), 1e-5)


if __name__ == "__main__":
    unittest.main()
