"""Pruebas del movimiento del camión (sin base de datos). Desde iot/:  CAMION_ID=CAM-01 python -m unittest test_simulador"""
import os
import unittest

os.environ.setdefault("CAMION_ID", "CAM-01")
os.environ["VELOCIDAD_MEDIA_KMH"] = "120"      # rápido para que las pruebas sean cortas
os.environ["FACTOR_CALLES"] = "1"
os.environ["INTERVALO_SEG"] = "5"
os.environ["DETENCION_LECTURAS"] = "3"
os.environ["PROB_RUPTURA"] = "0"               # una ruptura al azar en 400 lecturas tumbaba las pruebas de los escenarios una de cada tres veces
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


def falla(momento=50, duracion=8, subida=1.0, despacho=1, id_=9):
    return {"id": id_, "camion_id": "CAM-01", "despacho_id": despacho, "tipo": "falla_frio", "momento_pct": momento, "duracion_lecturas": duracion,
            "subida_c": subida, "direccion_id": None, "motivo": ""}


def otro(tipo, direccion=None, motivo="", despacho=1, id_=9):
    return {"id": id_, "camion_id": "CAM-01", "despacho_id": despacho, "tipo": tipo, "momento_pct": 50, "duracion_lecturas": 12, "subida_c": 1.0,
            "direccion_id": direccion, "motivo": motivo}


def leer(c, esc, lecturas=400):
    """Corre el camión como el ciclo principal, con el escenario tal como lo devolvería la base. Devuelve (lecturas, eventos)."""
    salida, eventos = [], []
    for _ in range(lecturas):
        c.aplicar_escenario(esc)
        lectura = c.paso()
        salida.append((c.progreso_pct(), lectura, c.lectura_forzada))
        eventos += c.eventos
        if any(e[0] == "escenario" and e[2] == "terminado" for e in c.eventos):
            esc = None                                                      # la base ya no lo devuelve como vigente
        c.eventos = []
    return salida, eventos


class SinEscenarioTest(unittest.TestCase):
    def test_sin_escenario_las_lecturas_son_identicas_a_las_de_siempre(self):
        """Mismo azar, con y sin el paso de sincronizar escenarios: mismas lecturas y mismos eventos."""
        import random

        def correr_viaje(sincronizar):
            random.seed(7)
            c = camion()
            c.combustible = 80
            c.asignar(viaje(ruta(CASA)))
            lecturas, eventos = [], []
            for _ in range(300):
                if sincronizar:
                    c.aplicar_escenario(None)
                lecturas.append(c.paso())
                eventos += c.eventos
                c.eventos = []
            return lecturas, eventos, c.lectura_forzada
        self.assertEqual(correr_viaje(True), correr_viaje(False))

    def test_la_ruptura_al_azar_sigue_igual_y_no_se_marca_forzada(self):
        c = camion()
        original, sim.PROB_RUPTURA = sim.PROB_RUPTURA, 1.0
        try:
            c.paso()
        finally:
            sim.PROB_RUPTURA = original
        self.assertGreater(c.ruptura_restante, 0)
        self.assertFalse(c.lectura_forzada)

    def test_un_escenario_de_otro_viaje_no_afecta_al_camion(self):
        c = camion()
        c.asignar(viaje(ruta(CASA), despacho=1))
        c.aplicar_escenario(falla(momento=5, despacho=2))
        self.assertIsNone(c.escenario)


class FallaDeFrioTest(unittest.TestCase):
    def test_parte_en_el_avance_pedido_y_salta_la_alerta_con_la_regla_de_siempre(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        lecturas, eventos = leer(c, falla(momento=50))
        primera = next(i for i, l in enumerate(lecturas) if l[2])
        self.assertGreaterEqual(lecturas[primera - 1][0], 45)                # justo antes iba cerca del 50 %
        self.assertLess(lecturas[primera - 2][0], 50)                        # y aún no lo pasaba
        self.assertFalse(any(l[1][4] for l in lecturas[:primera]))           # sin alerta antes de la falla
        self.assertTrue(any(l[1][4] for l in lecturas[primera:]))
        self.assertIn(("escenario", 9, "en_curso"), eventos)
        self.assertIn(("escenario", 9, "terminado"), eventos)

    def test_todas_las_lecturas_con_alerta_quedan_marcadas_y_la_ultima_marcada_es_normal(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        lecturas, _ = leer(c, falla(momento=5))
        marcadas = [l for l in lecturas if l[2]]
        self.assertTrue(all(l[2] for l in lecturas if l[1][4]))
        self.assertFalse(marcadas[-1][1][4])                                 # la lectura que cierra la falla ya está en rango
        self.assertFalse(lecturas[-1][2])

    def test_la_lectura_conserva_los_campos_de_siempre(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        c.aplicar_escenario(falla(momento=5))
        for _ in range(30):
            temp, lat, lon, comb, alerta = c.paso()
        self.assertIsInstance(temp, float)
        self.assertIsInstance(comb, int)
        self.assertIsInstance(alerta, bool)

    def test_la_temperatura_no_pasa_del_tope(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        lecturas, _ = leer(c, falla(momento=5, duracion=36, subida=2.0))
        self.assertLessEqual(max(l[1][0] for l in lecturas), c.tmax + sim.TOPE_SOBRE_RANGO_C)

    def test_cancelarla_a_medias_la_corta_y_el_camion_se_recupera(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        leer(c, falla(momento=5, duracion=36), lecturas=4)
        self.assertGreater(c.ruptura_restante, 0)
        lecturas, eventos = leer(c, None, lecturas=30)
        self.assertEqual(c.ruptura_restante, 0)
        self.assertIsNone(c.escenario)
        self.assertFalse(lecturas[-1][1][4])
        self.assertFalse(any(l[2] for l in lecturas))
        self.assertFalse([e for e in eventos if e[0] == "escenario"])

    def test_si_el_viaje_se_dio_por_llegado_no_dispara(self):
        c = camion()
        c.asignar(viaje(ruta(CASA)))
        c.asignar(viaje(ruta(CASA), llego=True))
        lecturas, eventos = leer(c, falla(momento=50), lecturas=3)
        self.assertIn(("escenario", 9, "terminado"), eventos)
        self.assertFalse(any(l[2] for l in lecturas))

    def test_el_avance_se_mide_en_km_y_no_en_vertices(self):
        c = camion()
        cerca = (sim.BASE[0] - 0.0001, sim.BASE[1])                         # un vértice casi encima de la base: 1 de 2 vértices, pero poco camino
        c.asignar(viaje(ruta(CASA, intermedios=[cerca])))
        c.posicion()
        self.assertLess(c.progreso_pct(), 30)                                # por vértices ya iría en más del 50 %

    def test_con_los_parametros_minimos_igual_salta_la_alerta_en_el_rango_mas_ancho(self):
        for _ in range(50):
            c = sim.Camion("CAM-01", -25, -18)                               # Congelado: 7 °C de ancho
            c.asignar(viaje(ruta(CASA)))
            lecturas, _ = leer(c, falla(momento=5, duracion=6, subida=1.0), lecturas=40)
            self.assertTrue(any(l[1][4] for l in lecturas))


class EntregaPerfectaTest(unittest.TestCase):
    def test_no_hay_rupturas_y_cada_cliente_confirma(self):
        c = camion()
        c.ruptura_restante = 5                                              # una ruptura al azar en curso se repara
        c.asignar(viaje(ruta(CASA, OTRA)))
        original, sim.PROB_RUPTURA = sim.PROB_RUPTURA, 1.0                  # ni con la probabilidad al máximo
        lecturas, eventos = [], []
        try:
            while c.despacho is not None:
                nuevas, nuevos = leer(c, otro("entrega_perfecta"), lecturas=1)
                lecturas += nuevas
                eventos += nuevos
        finally:
            sim.PROB_RUPTURA = original
        self.assertFalse(any(l[1][4] for l in lecturas))
        self.assertEqual([e for e in eventos if e[0] == "recibe"], [("recibe", 1, 100), ("recibe", 1, 101)])
        self.assertLess(eventos.index(("puerta", 1, 100)), eventos.index(("recibe", 1, 100)))
        self.assertFalse(any(l[2] for l in lecturas))


class ClienteNoRecibeTest(unittest.TestCase):
    def test_solo_la_parada_pedida_y_despues_de_llegar_a_la_puerta(self):
        c = camion()
        c.asignar(viaje(ruta(CASA, OTRA)))
        _, eventos = leer(c, otro("cliente_no_recibe", direccion=101, motivo="No había nadie."))
        self.assertEqual([e for e in eventos if e[0] == "no_recibe"], [("no_recibe", 1, 101, "No había nadie.")])
        self.assertLess(eventos.index(("puerta", 1, 101)), eventos.index(("no_recibe", 1, 101, "No había nadie.")))
        self.assertFalse([e for e in eventos if e[0] == "recibe"])
        self.assertIn(("escenario", 9, "terminado"), eventos)
        self.assertEqual(sum(1 for e in eventos if e[0] == "regreso"), 1)   # el camión termina su viaje igual

    def test_responde_antes_del_plazo_de_confirmacion_automatica(self):
        self.assertLess(sim.ESPERA_RESPUESTA_LECTURAS * sim.INTERVALO, sim.CONFIRMACION_AUTO_SEG)


class FilaDeEscenarioTest(unittest.TestCase):
    def test_ignora_un_tipo_desconocido(self):
        self.assertIsNone(sim.escenario_de_fila((1, "CAM-01", 1, "DROP TABLE orden", 50, 12, 1.0, None, "")))

    def test_acota_numeros_aunque_vengan_mal_de_la_base(self):
        e = sim.escenario_de_fila((1, "CAM-01", 1, "falla_frio", 500, 9000, 99.0, None, ""))
        self.assertEqual((e["momento_pct"], e["duracion_lecturas"], e["subida_c"]), (95, 36, 2.0))


class ConexionFalsa:
    """Registra lo que se envía a la base; `error` simula un problema de esquema."""

    def __init__(self, error=None, filas=()):
        self.error, self.filas, self.sentencias = error, filas, []

    def execute(self, sql, parametros=None):
        self.sentencias.append((sql, parametros))
        if self.error:
            raise self.error
        return self

    def fetchall(self):
        return list(self.filas)

    def transaction(self):
        import contextlib
        return contextlib.nullcontext()


class BaseDeDatosTest(unittest.TestCase):
    def test_si_la_tabla_no_existe_sigue_sin_escenarios(self):
        self.assertEqual(sim.escenarios_vigentes(ConexionFalsa(error=sim.psycopg.errors.UndefinedTable("no existe")), ["CAM-01"]), {})

    def test_una_caida_de_conexion_no_se_esconde(self):
        with self.assertRaises(sim.psycopg.OperationalError):
            sim.escenarios_vigentes(ConexionFalsa(error=sim.psycopg.OperationalError("caída")), ["CAM-01"])

    def test_el_motivo_viaja_como_parametro_y_no_dentro_de_la_sentencia(self):
        con, c = ConexionFalsa(), camion()
        malicioso = "'; DROP TABLE orden; --"
        c.eventos = [("no_recibe", 1, 100, malicioso)]
        sim.aplicar_eventos(con, c)
        sql, parametros = con.sentencias[0]
        self.assertNotIn(malicioso, sql)
        self.assertEqual(parametros["motivo"], malicioso)

    def test_un_error_de_esquema_en_un_evento_no_detiene_la_lectura(self):
        c = camion()
        c.eventos = [("escenario", 1, "en_curso")]
        sim.aplicar_eventos(ConexionFalsa(error=sim.psycopg.errors.UndefinedColumn("sin columna")), c)
        self.assertEqual(c.eventos, [])


class TiempoAceleradoTest(unittest.TestCase):
    """El multiplicador cambia cuánto avanza el camión por lectura y nada más."""
    LEJOS = (-37.80, -72.69)                       # Angol, a más de 100 km de la base

    def recorrido(self, *paradas, tramos=40):
        """Ruta con vértices intermedios, como las de OSRM: la marca de cada parada cae en medio de la polilínea."""
        puntos, marcas = [list(sim.BASE)], []
        for k, p in enumerate(paradas):
            a = puntos[-1]
            puntos += [[a[0] + (p[0] - a[0]) * i / tramos, a[1] + (p[1] - a[1]) * i / tramos] for i in range(1, tramos + 1)]
            marcas.append({"direccion_id": 100 + k, "indice": len(puntos) - 1})
        puntos.append(list(sim.BASE))
        return {"puntos": puntos, "paradas": marcas, "aproximada": False, "km": 200}

    def avance(self, multiplicador):
        c = camion()
        c.multiplicador = multiplicador
        c.asignar(viaje(self.recorrido(self.LEJOS)))
        antes = c.pos
        c.posicion()
        return sim.km_entre(antes, c.pos)

    def test_avanza_tantas_veces_mas_como_diga_el_multiplicador(self):
        normal = self.avance(1)
        for m in sim.MULTIPLICADORES:
            self.assertAlmostEqual(self.avance(m) / normal, m, delta=m * 0.02)

    def test_a_60x_no_se_salta_ninguna_parada_aunque_esten_a_menos_de_un_paso(self):
        cerca = (sim.BASE[0] - 0.002, sim.BASE[1])                   # tres paradas a unos 200 m entre sí: a 60× un paso son 10 km
        otra = (sim.BASE[0] - 0.004, sim.BASE[1])
        c = camion()
        c.multiplicador = 60
        c.asignar(viaje(self.recorrido(cerca, otra, self.LEJOS, tramos=4)))
        eventos = correr(c)
        self.assertEqual([e[2] for e in eventos if e[0] == "puerta"], [100, 101, 102])     # todas y en orden
        self.assertLess([e[0] for e in eventos].index("llegada"), [e[0] for e in eventos].index("regreso"))
        self.assertTrue(c.en_base)

    def test_la_detencion_dura_las_mismas_lecturas_que_a_velocidad_normal(self):
        for m in (1, 60):
            c = camion()
            c.multiplicador = m
            c.asignar(viaje(self.recorrido(CASA)))
            lecturas_en_la_puerta = 0
            for _ in range(2000):
                c.posicion()
                lecturas_en_la_puerta += c.detenido > 0
                if c.fase == "volviendo":
                    break
            self.assertEqual(lecturas_en_la_puerta, sim.DETENCION_LECTURAS, m)

    def test_cambiarlo_a_mitad_de_viaje_se_nota_en_la_lectura_siguiente(self):
        c = camion()
        c.asignar(viaje(self.recorrido(self.LEJOS)))
        c.posicion()
        antes = c.pos
        c.posicion()
        normal = sim.km_entre(antes, c.pos)
        c.multiplicador = 20
        antes = c.pos
        c.posicion()
        self.assertAlmostEqual(sim.km_entre(antes, c.pos) / normal, 20, delta=1)

    def test_cada_ciclo_sigue_siendo_una_lectura_con_los_mismos_campos(self):
        c = camion()
        c.multiplicador = 60
        c.asignar(viaje(self.recorrido(self.LEJOS)))
        lectura = c.paso()
        self.assertEqual(len(lectura), 5)                            # temp_camara, lat, long, combustible_pct, alerta_ruptura_frio
        self.assertIsInstance(lectura[0], float)
        self.assertIsInstance(lectura[3], int)
        self.assertIsInstance(lectura[4], bool)

    def test_una_falla_de_frio_dura_las_mismas_lecturas_a_60x(self):
        c = camion()
        c.multiplicador = 60
        c.asignar(viaje(self.recorrido(self.LEJOS)))
        c.aplicar_escenario({"id": 1, "camion_id": "CAM-01", "despacho_id": 1, "tipo": "falla_frio", "momento_pct": 50, "duracion_lecturas": 12, "subida_c": 1.0, "direccion_id": None, "motivo": ""})
        marcadas = 0
        for _ in range(300):
            c.paso()
            marcadas += c.lectura_forzada
        self.assertGreaterEqual(marcadas, 12)
        self.assertTrue(c.escenario["terminado"])


class RegresoDesdeLaUltimaParadaTest(unittest.TestCase):
    """La base avisa `llego` en cuanto el simulador registra la llegada: eso no es una corrección manual."""

    def test_termina_la_detencion_y_vuelve_por_la_ruta_informando_la_fase(self):
        intermedio = (-38.7350, -72.5900)                            # el regreso por calles no es la recta a la base
        c = camion()
        r = ruta(CASA)
        r["puntos"].insert(-1, list(intermedio))
        c.asignar(viaje(r))
        for _ in range(400):
            c.posicion()
            if c.fase == "en_la_puerta":
                break
        camino = list(c.camino)
        c.eventos = []
        lecturas_detenido = 0
        while c.fase == "en_la_puerta":
            c.asignar(viaje(r, llego=True))                          # lo que el ciclo principal lee de la base después de escribir la llegada
            c.posicion()
            lecturas_detenido += 1
        self.assertEqual(lecturas_detenido, sim.DETENCION_LECTURAS)
        self.assertEqual(c.camino, camino)                           # sigue la ruta guardada, no una recta improvisada
        self.assertIn(("fase", 1, "volviendo"), c.eventos)

    def test_una_correccion_manual_en_ruta_sigue_haciendolo_volver(self):
        c = camion()
        c.asignar(viaje(ruta(CASA, OTRA)))
        c.posicion()
        c.asignar(viaje(ruta(CASA, OTRA), llego=True))
        self.assertEqual(c.fase, "volviendo")


class LecturaDelMultiplicadorTest(unittest.TestCase):
    class Conexion:
        def __init__(self, fila=None, error=None):
            self.fila, self.error = fila, error

        def execute(self, sql, *args):
            if self.error:
                raise self.error
            return self

        def fetchone(self):
            return self.fila

    def test_lee_el_valor_de_la_tabla(self):
        self.assertEqual(sim.multiplicador_vigente(self.Conexion((20,))), 20)

    def test_sin_fila_es_tiempo_normal(self):
        self.assertEqual(sim.multiplicador_vigente(self.Conexion(None)), 1)

    def test_un_valor_desconocido_no_se_obedece(self):
        for malo in (0, -5, 7, 1000):
            self.assertEqual(sim.multiplicador_vigente(self.Conexion((malo,))), 1)

    def test_si_la_tabla_no_existe_sigue_a_velocidad_normal(self):
        self.assertEqual(sim.multiplicador_vigente(self.Conexion(error=sim.psycopg.errors.UndefinedTable("no existe"))), 1)

    def test_una_caida_de_conexion_no_se_esconde(self):
        with self.assertRaises(sim.psycopg.OperationalError):
            sim.multiplicador_vigente(self.Conexion(error=sim.psycopg.OperationalError("sin red")))


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
