"""Simulador IoT de un camión frigorífico de Cofrial.

Cada contenedor simula un camión: lee de la base de datos el rango de temperatura que le corresponde y,
cada INTERVALO_SEG segundos, inserta una lectura en la tabla telemetria con los campos que exige la pauta:
camion_id, temp_camara, lat, long, combustible_pct y alerta_ruptura_frio.
La alerta es verdadera cuando la temperatura sale del rango del camión. De vez en cuando se simula una
ruptura de frío (falla del equipo) que sube la temperatura hasta que se "repara".

Posición: sin viaje, el camión patrulla una ruta circular. Con un despacho en curso (salida registrada y sin llegada) en la
tabla despacho, parte desde donde está hacia las direcciones de entrega de sus pedidos (el más cercano primero), se detiene
unas lecturas en cada parada intermedia y queda estacionado en la última, listo para marcar el despacho como entregado.
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
# Velocidad y factor de calles COMPARTIDOS con la web: la hora de llegada que muestra la tienda se calcula con los mismos valores
# (variables VELOCIDAD_MEDIA_KMH y FACTOR_CALLES), así el camión llega cuando la pantalla dijo. VELOCIDAD_KMH queda solo por compatibilidad.
VELOCIDAD_MEDIA_KMH = float(os.environ.get("VELOCIDAD_MEDIA_KMH") or os.environ.get("VELOCIDAD_KMH") or "50")
FACTOR_CALLES = float(os.environ.get("FACTOR_CALLES", "1.3"))      # la ruta por calles es más larga que la línea recta que recorre el simulador
DETENCION_LECTURAS = int(os.environ.get("DETENCION_LECTURAS", "6"))   # lecturas detenido en cada parada intermedia
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


def km_entre(a, b):
    """Distancia en km sobre la esfera (haversine) entre dos puntos (lat, long)."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def ordenar_paradas(origen, paradas):
    """Vecino más cercano: de la posición actual a la parada más próxima, y desde ahí a la siguiente más próxima."""
    pendientes, orden, actual = list(paradas), [], origen
    while pendientes:
        siguiente = min(pendientes, key=lambda p: km_entre(actual, p))
        pendientes.remove(siguiente)
        orden.append(siguiente)
        actual = siguiente
    return orden


def paradas_del_viaje(con):
    """(despacho_id, direcciones) del viaje en curso del camión; las direcciones sin ubicar o de pedidos ya cerrados no cuentan."""
    fila = con.execute("SELECT despacho_id FROM despacho WHERE camion_id = %s AND salida_en IS NOT NULL AND llegada_en IS NULL "
                       "ORDER BY salida_en LIMIT 1", (CAMION_ID,)).fetchone()
    if not fila:
        return None, []
    paradas = con.execute(
        'SELECT DISTINCT d.lat, d."long" FROM orden o JOIN direccion d USING (direccion_id) JOIN estado_orden e USING (estado_orden_id) '
        'WHERE o.despacho_id = %s AND NOT e.es_final AND d.lat IS NOT NULL AND d."long" IS NOT NULL', (fila[0],)).fetchall()
    return fila[0], [(float(la), float(lo)) for la, lo in paradas]


class Camion:
    def __init__(self, tmin, tmax):
        self.tmin, self.tmax = tmin, tmax
        self.objetivo = (tmin + tmax) / 2
        self.temp = self.objetivo
        self.combustible = random.randint(60, 100)
        self.tramo = (sum(map(ord, CAMION_ID)) % len(RUTA))     # próximo punto de la patrulla
        self.pos = RUTA[self.tramo]
        self.tramo = (self.tramo + 1) % len(RUTA)
        self.despacho = None            # viaje en curso: id, paradas por visitar y lecturas que faltan de detención
        self.paradas = []
        self.detenido = 0
        self.ruptura_restante = 0

    def asignar(self, despacho_id, paradas):
        """Sincroniza con el viaje activo de la base: al aparecer uno nuevo ordena sus paradas desde la posición actual."""
        if despacho_id != self.despacho:
            self.despacho, self.detenido = despacho_id, 0
            self.paradas = ordenar_paradas(self.pos, paradas)
            if despacho_id:
                log.info("Viaje %s: %d parada(s)", despacho_id, len(self.paradas))
            else:
                log.info("Sin viaje: patrulla")
        elif despacho_id:
            vigentes = set(paradas)
            self.paradas = [p for p in self.paradas if p in vigentes]    # un pedido entregado o cancelado deja de ser parada

    def posicion(self):
        if self.detenido > 0:
            self.detenido -= 1
            return self.pos
        if self.despacho is not None:
            if not self.paradas:
                return self.pos                                   # estacionado en la última entrega
            destino = self.paradas[0]
        else:
            destino = RUTA[self.tramo]
        paso_km = VELOCIDAD_MEDIA_KMH * INTERVALO / 3600 / FACTOR_CALLES     # en línea recta; por calles equivale a VELOCIDAD_MEDIA_KMH
        faltan = km_entre(self.pos, destino)
        if faltan <= paso_km:
            self.pos = destino
            if self.despacho is None:
                self.tramo = (self.tramo + 1) % len(RUTA)
            else:
                self.paradas.pop(0)
                if self.paradas:                                  # la última parada no se espera: queda estacionado
                    self.detenido = DETENCION_LECTURAS
        else:
            f = paso_km / faltan
            self.pos = (self.pos[0] + (destino[0] - self.pos[0]) * f, self.pos[1] + (destino[1] - self.pos[1]) * f)
        return self.pos

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
        try:
            camion.asignar(*paradas_del_viaje(con))
        except psycopg.Error as e:
            log.error("No se pudo leer el viaje (%s); sigo con el último conocido", str(e).strip().splitlines()[0])
            con = conectar()
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
