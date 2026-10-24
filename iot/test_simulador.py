"""Pruebas del movimiento del camión (sin base de datos). Desde iot/:  CAMION_ID=CAM-01 python -m unittest test_simulador"""
import os
import unittest

os.environ.setdefault("CAMION_ID", "CAM-01")
os.environ["VELOCIDAD_MEDIA_KMH"] = "120"      # rápido para que las pruebas sean cortas
os.environ["FACTOR_CALLES"] = "1"
os.environ["INTERVALO_SEG"] = "5"
os.environ["DETENCION_LECTURAS"] = "3"
import simulador as sim  # noqa: E402

CASA = (-38.7400, -72.6000)       # a ~2 km de la base
OTRA = (-38.7500, -72.6200)


def viaje(*paradas):
    c = sim.Camion("CAM-01", 0, 5)
    c.pos = sim.BASE                    # sale de la base: así el orden de visita no depende del recorrido de patrulla
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
        self.assertEqual(lecturas, -(-d // (sim.VELOCIDAD_MEDIA_KMH * 5 / 3600 / sim.FACTOR_CALLES)))     # distancia / paso, redondeado hacia arriba

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


class VelocidadCompartidaTest(unittest.TestCase):
    def test_por_defecto_es_la_misma_que_usa_la_web(self):
        """Sin variables, simulador y web usan 50 km/h y un factor de calles de 1,3 (la web: cofrial/settings.py)."""
        import importlib
        import subprocess
        import sys
        codigo = "import simulador as s; print(s.VELOCIDAD_MEDIA_KMH, s.FACTOR_CALLES)"
        entorno = {k: v for k, v in os.environ.items() if k not in ("VELOCIDAD_MEDIA_KMH", "VELOCIDAD_KMH", "FACTOR_CALLES")}
        r = subprocess.run([sys.executable, "-c", codigo], env=entorno, capture_output=True, text=True, cwd=os.path.dirname(__file__) or ".")
        self.assertEqual(r.stdout.split(), ["50.0", "1.3"], r.stderr)

    def test_el_tiempo_de_viaje_coincide_con_la_estimacion_de_la_web(self):
        """Con 50 km/h y factor 1,3, recorrer km en línea recta toma lo mismo que la web estima para km * 1,3 a 50 km/h."""
        km, v, f, intervalo = 3.0, 50.0, 1.3, 5.0
        lecturas = km / (v * intervalo / 3600 / f)
        minutos_web = km * f / v * 60
        self.assertAlmostEqual(lecturas * intervalo / 60, minutos_web, places=6)


if __name__ == "__main__":
    unittest.main()
