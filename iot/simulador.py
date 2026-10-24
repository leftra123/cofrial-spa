"""Simulador IoT de la flota de Cofrial.

Un proceso simula un grupo de camiones (por defecto CAM-01 a CAM-10; con PRIMER_CAMION y NUM_CAMIONES se elige otro grupo,
y con CAMION_ID, uno solo). Lee de la base de datos el rango de temperatura de cada camión y, cada INTERVALO_SEG segundos,
inserta una lectura por camión en la tabla telemetria con los campos que exige la pauta:
camion_id, temp_camara, lat, long, combustible_pct y alerta_ruptura_frio.
La alerta es verdadera cuando la temperatura sale del rango del camión. La mayoría de la flota funciona bien; de vez en
cuando un camión sufre una ruptura de frío (falla del equipo) que sube su temperatura hasta que se "repara".

Recorridos (líneas rectas entre puntos, con el tiempo acelerado para que se vean en una demostración):
  - urbano: vueltas alrededor de la base (INACAP Temuco) dentro de unos 7 km;
  - regional: viaje de ida y vuelta entre la base y una ciudad lejana de La Araucanía (hasta ~100 km).
"""
import logging
import math
import os
import random
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("simulador")

INTERVALO = float(os.environ.get("INTERVALO_SEG", "5"))
PROB_RUPTURA = float(os.environ.get("PROB_RUPTURA", "0.001"))     # por lectura y camión: la flota casi siempre está sana
VELOCIDAD_X = float(os.environ.get("VELOCIDAD_X", "1"))           # multiplica los kilómetros que avanza cada camión por lectura
if os.environ.get("CAMION_ID"):
    IDS = [os.environ["CAMION_ID"]]
else:
    _primero, _cantidad = int(os.environ.get("PRIMER_CAMION", "1")), int(os.environ.get("NUM_CAMIONES", "10"))
    IDS = [f"CAM-{n:02d}" for n in range(_primero, _primero + _cantidad)]

# Base de la flota (referencia: INACAP Temuco). Debe coincidir con BASE_LOGISTICA en web/cofrial/settings.py
BASE = (-38.7330, -72.6040)
# Ciudades de destino de los viajes regionales (lat, long aproximadas)
DESTINOS = [("Lautaro", -38.5300, -72.4330), ("Nueva Imperial", -38.7440, -72.9500), ("Villarrica", -39.2850, -72.2270),
            ("Pucón", -39.2720, -71.9770), ("Loncoche", -39.3700, -72.6310), ("Victoria", -38.2330, -72.3350),
            ("Freire", -38.9500, -72.6200), ("Gorbea", -39.1000, -72.6700), ("Carahue", -38.7100, -73.1600),
            ("Cunco", -38.9250, -72.0300), ("Vilcún", -38.6700, -72.2300), ("Traiguén", -38.2500, -72.6700),
            ("Angol", -37.8000, -72.7100), ("Curacautín", -38.4400, -71.8900)]
KM_LAT, KM_LON = 111.0, 111.0 * math.cos(math.radians(BASE[0]))
KM_LECTURA_URBANO, KM_LECTURA_REGIONAL = 0.15, 0.6


def conectar():
    dsn = (f"host={os.environ['DB_HOST']} port={os.environ.get('DB_PORT', '5432')} dbname={os.environ['DB_NAME']} "
           f"user={os.environ['DB_USER']} password={os.environ['DB_PASSWORD']} connect_timeout=5 "
           f"sslmode={os.environ.get('DB_SSLMODE', 'prefer')}")
    while True:
        try:
            con = psycopg.connect(dsn, autocommit=True)
            log.info("Conectado a la base de datos")
            return con
        except psycopg.OperationalError as e:
            log.warning("Base no disponible (%s); reintento en 5 s", str(e).strip().splitlines()[-1])
            time.sleep(5)


def km(a, b):
    return math.hypot((b[0] - a[0]) * KM_LAT, (b[1] - a[1]) * KM_LON)


class Camion:
    def __init__(self, camion_id, tmin, tmax):
        self.id = camion_id
        self.tmin, self.tmax = tmin, tmax
        self.objetivo = (tmin + tmax) / 2
        self.temp = self.objetivo
        azar = random.Random(camion_id)                          # el recorrido de cada camión es siempre el mismo
        n = int(camion_id.split("-")[-1]) if camion_id.split("-")[-1].isdigit() else 0
        self.regional = n > 3 and azar.random() < 0.35           # CAM-01 a CAM-03 reparten en Temuco (despachos de demostración)
        if self.regional:
            self.destino = azar.choice(DESTINOS)[1:]
            self.puntos = [BASE, self.destino]
            self.paso_km = KM_LECTURA_REGIONAL * azar.uniform(0.8, 1.2)
        else:
            vertices = azar.randint(5, 7)
            angulos = sorted(azar.uniform(0, 2 * math.pi) for _ in range(vertices))
            radios = [azar.uniform(1.5, 7.0) for _ in range(vertices)]
            self.puntos = [(BASE[0] + r * math.sin(a) / KM_LAT, BASE[1] + r * math.cos(a) / KM_LON) for a, r in zip(angulos, radios)]
            self.paso_km = KM_LECTURA_URBANO * azar.uniform(0.8, 1.2)
        self.paso_km *= VELOCIDAD_X
        self.tramo = azar.randrange(len(self.puntos))
        self.avance = azar.random()
        self.combustible = random.randint(60, 100)
        self.ruptura_restante = 0

    def siguiente(self, tramo):
        return 1 - tramo if self.regional else (tramo + 1) % len(self.puntos)

    def posicion(self):
        a, b = self.puntos[self.tramo], self.puntos[self.siguiente(self.tramo)]
        self.avance += self.paso_km / max(km(a, b), 0.1)
        if self.avance >= 1:
            self.avance, self.tramo = 0.0, self.siguiente(self.tramo)
            a, b = self.puntos[self.tramo], self.puntos[self.siguiente(self.tramo)]
        return a[0] + (b[0] - a[0]) * self.avance, a[1] + (b[1] - a[1]) * self.avance

    def paso(self):
        if self.ruptura_restante == 0 and random.random() < PROB_RUPTURA:
            self.ruptura_restante = random.randint(6, 14)
            log.warning("Falla de frío simulada en %s durante %d lecturas", self.id, self.ruptura_restante)
        if self.ruptura_restante > 0:
            self.ruptura_restante -= 1
            self.temp += random.uniform(0.6, 1.4)                 # sube sin control
        else:
            self.temp += (self.objetivo - self.temp) * 0.4 + random.uniform(-0.2, 0.2)   # vuelve al objetivo
        self.combustible = max(0, self.combustible - (1 if random.random() < 0.15 else 0))
        if self.combustible < 15:
            self.combustible = 95                                  # recarga
        lat, lon = self.posicion()
        temp = round(self.temp, 1)
        alerta = temp > self.tmax or temp < self.tmin
        return temp, round(lat, 6), round(lon, 6), self.combustible, alerta


def rangos_de(con, ids):
    filas = con.execute(
        "SELECT c.camion_id, r.temp_min_c, r.temp_max_c FROM camion c JOIN rango_temperatura r USING (rango_temperatura_id) WHERE c.camion_id = ANY(%s)",
        (ids,)).fetchall()
    return {f[0]: (float(f[1]), float(f[2])) for f in filas}


def main():
    con = conectar()
    flota, lecturas_hechas = {}, 0
    log.info("Grupo de %d camiones (%s a %s), intervalo %.0f s, probabilidad de ruptura %.4f", len(IDS), IDS[0], IDS[-1], INTERVALO, PROB_RUPTURA)
    while True:
        inicio = time.monotonic()
        try:
            if len(flota) < len(IDS) and (not flota or lecturas_hechas % 12 == 0):      # los que aún no existen en la base se reintentan cada minuto
                for cid, (tmin, tmax) in rangos_de(con, [i for i in IDS if i not in flota]).items():
                    flota[cid] = Camion(cid, tmin, tmax)
                if len(flota) < len(IDS):
                    log.warning("Faltan %d camiones en la base (se reintenta); activos: %d", len(IDS) - len(flota), len(flota))
            filas = []
            for c in flota.values():
                temp, lat, lon, comb, alerta = c.paso()
                filas.append((c.id, temp, lat, lon, comb, alerta))
            if filas:
                with con.transaction():
                    con.cursor().executemany(
                        'INSERT INTO telemetria (camion_id, temp_camara, lat, "long", combustible_pct, alerta_ruptura_frio, registrado_en) '
                        "VALUES (%s, %s, %s, %s, %s, %s, now())", filas)
                lecturas_hechas += 1
                if lecturas_hechas % 12 == 1:
                    log.info("%d lecturas insertadas; camiones en alerta: %d", len(filas), sum(1 for f in filas if f[5]))
            else:
                lecturas_hechas += 1
        except psycopg.Error as e:
            log.error("No se pudo insertar (%s); reconecto", str(e).strip().splitlines()[0])
            con = conectar()
        time.sleep(max(0.5, INTERVALO - (time.monotonic() - inicio)))


if __name__ == "__main__":
    main()
