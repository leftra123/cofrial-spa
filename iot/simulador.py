"""Simulador IoT de un camión frigorífico de Cofrial.

Cada contenedor simula un camión: lee de la base de datos el rango de temperatura que le corresponde y,
cada INTERVALO_SEG segundos, inserta una lectura en la tabla telemetria con los campos que exige la pauta:
camion_id, temp_camara, lat, long, combustible_pct y alerta_ruptura_frio.
La alerta es verdadera cuando la temperatura sale del rango del camión. De vez en cuando se simula una
ruptura de frío (falla del equipo) que sube la temperatura hasta que se "repara".
"""
import logging
import math
import os
import random
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("simulador")

CAMION_ID = os.environ["CAMION_ID"]
INTERVALO = float(os.environ.get("INTERVALO_SEG", "5"))
PROB_RUPTURA = float(os.environ.get("PROB_RUPTURA", "0.01"))   # por lectura
# Ruta circular alrededor de Temuco (lat, long); cada camión parte en un punto distinto
RUTA = [(-38.7359, -72.5904), (-38.7290, -72.6120), (-38.7480, -72.6300), (-38.7650, -72.6050),
        (-38.7700, -72.5700), (-38.7550, -72.5450), (-38.7380, -72.5550)]


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


def rango_del_camion(con):
    while True:
        fila = con.execute(
            "SELECT r.temp_min_c, r.temp_max_c FROM camion c JOIN rango_temperatura r USING (rango_temperatura_id) WHERE c.camion_id = %s",
            (CAMION_ID,)).fetchone()
        if fila:
            return float(fila[0]), float(fila[1])
        log.warning("El camión %s aún no existe en la base; reintento en 5 s", CAMION_ID)
        time.sleep(5)


class Camion:
    def __init__(self, tmin, tmax):
        self.tmin, self.tmax = tmin, tmax
        self.objetivo = (tmin + tmax) / 2
        self.temp = self.objetivo
        self.combustible = random.randint(60, 100)
        self.tramo = (sum(map(ord, CAMION_ID)) % len(RUTA))
        self.avance = 0.0
        self.ruptura_restante = 0

    def posicion(self):
        a, b = RUTA[self.tramo], RUTA[(self.tramo + 1) % len(RUTA)]
        self.avance += 0.05
        if self.avance >= 1:
            self.avance, self.tramo = 0.0, (self.tramo + 1) % len(RUTA)
        return a[0] + (b[0] - a[0]) * self.avance, a[1] + (b[1] - a[1]) * self.avance

    def paso(self):
        if self.ruptura_restante == 0 and random.random() < PROB_RUPTURA:
            self.ruptura_restante = random.randint(6, 14)
            log.warning("Falla de frío simulada en %s durante %d lecturas", CAMION_ID, self.ruptura_restante)
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


def main():
    con = conectar()
    tmin, tmax = rango_del_camion(con)
    log.info("Camión %s: rango crítico fuera de %.1f a %.1f °C, intervalo %.0f s", CAMION_ID, tmin, tmax, INTERVALO)
    camion = Camion(tmin, tmax)
    while True:
        temp, lat, lon, comb, alerta = camion.paso()
        try:
            con.execute(
                'INSERT INTO telemetria (camion_id, temp_camara, lat, "long", combustible_pct, alerta_ruptura_frio, registrado_en) '
                "VALUES (%s, %s, %s, %s, %s, %s, now())", (CAMION_ID, temp, lat, lon, comb, alerta))
            log.info("%s temp=%.1f lat=%.4f long=%.4f comb=%d%% alerta=%s", CAMION_ID, temp, lat, lon, comb, alerta)
        except psycopg.Error as e:
            log.error("No se pudo insertar (%s); reconecto", str(e).strip().splitlines()[0])
            con = conectar()
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
