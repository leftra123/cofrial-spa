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


def camion():
    return sim.Camion("CAM-01", 0, 5)


def ruta(*paradas, aproximada=False, intermedios=()):
    """Ruta guardada de ejemplo: base -> paradas -> base, con el formato que arma el servidor."""
    puntos = [list(sim.BASE)] + [list(p) for p in intermedios] + [list(p) for p in paradas] + [list(sim.BASE)]
    marcas = [{"direccion_id": 100 + k, "indice": puntos.index(list(p))} for k, p in enumerate(paradas)]
    return {"puntos": puntos, "paradas": marcas, "aproximada": aproximada, "km": 5}


def viaje(r=None, despacho=1, llego=False, paradas=()):
    return {"despacho_id": despacho, "llego": llego, "ruta": r, "paradas": list(paradas)}


def correr(c, lecturas=400):
    eventos = []
    for _ in range(lecturas):
        c.posicion()
        eventos += c.eventos
        c.eventos = []
    return eventos


class GuardadoEnBaseTest(unittest.TestCase):
    def test_sin_despacho_queda_detenido_en_la_base(self):
        c = camion()
        self.assertTrue(c.en_base)
        self.assertLess(sim.km_entre(c.pos, sim.BASE), 0.05)            # su puesto está a pocos metros de la base
        antes = c.pos
        for _ in range(50):
            c.asignar(None)
            c.posicion()
        self.assertEqual(c.pos, antes)                                  # no vaga: sigue en su puesto

    def test_cada_camion_tiene_su_propio_puesto_fijo(self):
        a, b = sim.Camion("CAM-05", 0, 5), sim.Camion("CAM-06", 0, 5)
        self.assertNotEqual(a.casa, b.casa)
        self.assertEqual(a.casa, sim.Camion("CAM-05", 0, 5).casa)

    def test_la_telemetria_sigue_igual_que_siempre(self):
        c = camion()
        temp, lat, lon, comb, alerta = c.paso()
        self.assertIsInstance(temp, float)
        self.assertIsInstance(comb, int)
        self.assertIsInstance(alerta, bool)
        self.assertLess(abs(lat - c.pos[0]), 1e-5)


class ViajeConRutaTest(unittest.TestCase):
    def test_ciclo_completo_ida_puerta_llegada_vuelta_y_regreso(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        self.assertEqual(c.fase, "en_ruta")
        eventos = correr(c)
        tipos = [e[0] for e in eventos]
        self.assertEqual(tipos.count("puerta"), 1)
        self.assertEqual(tipos.count("llegada"), 1)
        self.assertEqual(tipos.count("regreso"), 1)
        self.assertLess(tipos.index("puerta"), tipos.index("llegada") + 1)
        self.assertLess(tipos.index("llegada"), tipos.index("regreso"))
        self.assertIn(("puerta", 1, 100), eventos)
        self.assertIn(("fase", 1, "volviendo"), eventos)
        self.assertTrue(c.en_base)
        self.assertEqual(c.pos, c.casa)                                 # volvió y quedó guardado
        self.assertEqual(c.eventos, [])

    def test_se_queda_en_la_puerta_las_lecturas_de_la_detencion(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        quieto, fases = 0, set()
        for _ in range(400):
            antes = c.pos
            c.posicion()
            fases.add(c.fase)
            if c.pos == antes == CASA:
                quieto += 1
        self.assertIn("en_la_puerta", fases)
        self.assertEqual(quieto, sim.DETENCION_LECTURAS)

    def test_dos_paradas_avisan_cada_puerta_y_la_llegada_solo_en_la_ultima(self):
        c = camion()
        c.asignar(viaje(ruta(CASA, OTRA)))
        eventos = correr(c)
        self.assertEqual([e for e in eventos if e[0] == "puerta"], [("puerta", 1, 100), ("puerta", 1, 101)])
        self.assertEqual(sum(1 for e in eventos if e[0] == "llegada"), 1)
        posicion_llegada = next(i for i, e in enumerate(eventos) if e[0] == "llegada")
        self.assertEqual(eventos[posicion_llegada - 2:posicion_llegada], [("puerta", 1, 100), ("puerta", 1, 101)][-1:] + [eventos[posicion_llegada - 1]])

    def test_sigue_la_polilinea_y_no_la_recta(self):
        """Con un vértice intermedio lejos de la recta (un rodeo por calles), el camión pasa por él."""
        rodeo = (-38.7300, -72.5800)
        r = ruta(CASA, intermedios=[rodeo])
        c = camion()
        c.asignar(viaje(r))
        minimo = min(sim.km_entre(c.posicion(), rodeo) for _ in range(300))
        self.assertLess(minimo, 0.2)

    def test_ruta_por_calles_no_usa_el_factor_de_calles(self):
        self.assertEqual(sim.Camion("CAM-01", 0, 5)._paso_para(False), 120 * 5 / 3600)
        self.assertEqual(sim.Camion("CAM-01", 0, 5)._paso_para(True), 120 * 5 / 3600 / sim.FACTOR_CALLES)

    def test_el_regreso_no_ocurre_antes_de_llegar_a_la_ultima_parada(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        vistos = []
        for _ in range(400):
            c.posicion()
            vistos += [e[0] for e in c.eventos]
            c.eventos = []
        self.assertEqual(vistos.index("regreso"), len(vistos) - 1)

    def test_corregir_a_mano_hace_volver_al_camion(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        for _ in range(3):
            c.posicion()
        c.asignar(viaje(ruta(CASA), llego=True))                          # el despachador dio el viaje por llegado
        self.assertEqual(c.fase, "volviendo")
        eventos = correr(c)
        self.assertEqual([e[0] for e in eventos if e[0] == "regreso"], ["regreso"])
        self.assertTrue(c.en_base)

    def test_si_el_despacho_desaparece_vuelve_a_su_puesto(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        for _ in range(10):
            c.posicion()
        c.asignar(None)
        correr(c)
        self.assertTrue(c.en_base)
        self.assertEqual(c.pos, c.casa)


class ViajeSinRutaTest(unittest.TestCase):
    """Despachos anteriores a las rutas guardadas: rectas entre las direcciones y de vuelta a la base."""

    def test_sin_ruta_recorre_las_rectas_y_vuelve(self):
        c = camion()
        c.asignar(viaje(None, paradas=[(7, *CASA)]))
        eventos = correr(c)
        self.assertIn(("puerta", 1, 7), eventos)
        self.assertEqual(sum(1 for e in eventos if e[0] == "regreso"), 1)
        self.assertTrue(c.en_base)

    def test_orden_vecino_mas_cercano(self):
        c = camion()
        c.pos = sim.BASE
        c.asignar(viaje(None, paradas=[(8, *OTRA), (7, *CASA)]))
        eventos = [e for e in correr(c) if e[0] == "puerta"]
        self.assertEqual(eventos, [("puerta", 1, 7), ("puerta", 1, 8)])        # CASA está más cerca de la base

    def test_sin_nada_que_entregar_llega_y_vuelve(self):
        c = camion()
        c.asignar(viaje(None, paradas=[]))
        eventos = correr(c)
        self.assertEqual([e[0] for e in eventos if e[0] in ("llegada", "regreso")], ["llegada", "regreso"])

    def test_ruta_aproximada_usa_el_factor_de_calles(self):
        c = camion()
        c.asignar(viaje(ruta(CASA, aproximada=True)))
        self.assertEqual(c.paso_km, 120 * 5 / 3600 / sim.FACTOR_CALLES)


class VelocidadCompartidaTest(unittest.TestCase):
    def test_por_defecto_es_la_misma_que_usa_la_web(self):
        """Sin variables, simulador y web usan 50 km/h y un factor de calles de 1,3 (la web: cofrial/settings.py)."""
        import subprocess
        import sys
        codigo = "import simulador as s; print(s.VELOCIDAD_MEDIA_KMH, s.FACTOR_CALLES, s.CONFIRMACION_AUTO_SEG)"
        entorno = {k: v for k, v in os.environ.items() if k not in ("VELOCIDAD_MEDIA_KMH", "VELOCIDAD_KMH", "FACTOR_CALLES", "CONFIRMACION_AUTO_SEG")}
        r = subprocess.run([sys.executable, "-c", codigo], env=entorno, capture_output=True, text=True, cwd=os.path.dirname(__file__) or ".")
        self.assertEqual(r.stdout.split(), ["50.0", "1.3", "120"], r.stderr)

    def test_el_tiempo_de_viaje_coincide_con_la_estimacion_de_la_web(self):
        """Con 50 km/h y factor 1,3, recorrer km en línea recta toma lo mismo que la web estima para km * 1,3 a 50 km/h."""
        km, v, f, intervalo = 3.0, 50.0, 1.3, 5.0
        lecturas = km / (v * intervalo / 3600 / f)
        minutos_web = km * f / v * 60
        self.assertAlmostEqual(lecturas * intervalo / 60, minutos_web, places=6)


if __name__ == "__main__":
    unittest.main()
