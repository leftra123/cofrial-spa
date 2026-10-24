"""Simulador IoT de la flota de Cofrial.

Un proceso simula un grupo de camiones (por defecto CAM-01 a CAM-10; con PRIMER_CAMION y NUM_CAMIONES se elige otro grupo,
y con CAMION_ID, uno solo). Lee de la base de datos el rango de temperatura de cada camión y, cada INTERVALO_SEG segundos,
inserta una lectura por camión en la tabla telemetria con los campos que exige la pauta:
camion_id, temp_camara, lat, long, combustible_pct y alerta_ruptura_frio.
La alerta es verdadera cuando la temperatura sale del rango del camión. La mayoría de la flota funciona bien; de vez en
cuando un camión sufre una ruptura de frío (falla del equipo) que sube su temperatura hasta que se "repara".

Sin viaje, recorridos (líneas rectas entre puntos, con el tiempo acelerado para que se vean en una demostración):
  - urbano: vueltas alrededor de la base (INACAP Temuco) dentro de unos 7 km;
  - regional: viaje de ida y vuelta entre la base y una ciudad lejana de La Araucanía (hasta ~100 km).

Con un despacho en curso (salida registrada y sin llegada) en la tabla despacho, el camión parte desde donde está hacia las
direcciones de entrega de sus pedidos (el más cercano primero), se detiene unas lecturas en cada parada intermedia y queda
estacionado en la última, listo para marcar el despacho como entregado.
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
# Velocidad en viaje de entrega. 120 km/h hace que un reparto de pocos km termine en un par de minutos (modo demostración);
# con 30 km/h coincide con la velocidad urbana que usa la web para estimar la llegada.
VELOCIDAD_KMH = float(os.environ.get("VELOCIDAD_KMH", "120"))
DETENCION_LECTURAS = int(os.environ.get("DETENCION_LECTURAS", "6"))   # lecturas detenido en cada parada intermedia
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


def viajes_en_curso(con, ids):
    """{camion_id: (despacho_id, direcciones)} de los viajes en curso (salida registrada y sin llegada); las direcciones sin
    ubicar o de pedidos ya cerrados no cuentan."""
    viajes = {}
    for camion_id, despacho_id in con.execute(
            "SELECT camion_id, despacho_id FROM despacho WHERE camion_id = ANY(%s) AND salida_en IS NOT NULL AND llegada_en IS NULL "
            "ORDER BY salida_en DESC", (ids,)).fetchall():
        viajes[camion_id] = (despacho_id, [])                    # si hubiera dos abiertos, gana el más antiguo
    if viajes:
        por_despacho = {v[0]: v[1] for v in viajes.values()}
        for despacho_id, lat, lon in con.execute(
                'SELECT DISTINCT o.despacho_id, d.lat, d."long" FROM orden o JOIN direccion d USING (direccion_id) '
                "JOIN estado_orden e USING (estado_orden_id) WHERE o.despacho_id = ANY(%s) AND NOT e.es_final "
                'AND d.lat IS NOT NULL AND d."long" IS NOT NULL', (list(por_despacho),)).fetchall():
            por_despacho[despacho_id].append((float(lat), float(lon)))
    return viajes


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
        a, b = self.puntos[self.tramo], self.puntos[self.siguiente(self.tramo)]
        self.pos = (a[0] + (b[0] - a[0]) * self.avance, a[1] + (b[1] - a[1]) * self.avance)   # parte en algún punto del recorrido
        self.tramo = self.siguiente(self.tramo)                  # punto del recorrido al que se dirige
        self.despacho = None            # viaje en curso: id, paradas por visitar y lecturas que faltan de detención
        self.paradas = []
        self.detenido = 0

    def siguiente(self, tramo):
        return 1 - tramo if self.regional else (tramo + 1) % len(self.puntos)

    def asignar(self, despacho_id, paradas):
        """Sincroniza con el viaje activo de la base: al aparecer uno nuevo ordena sus paradas desde la posición actual."""
        if despacho_id != self.despacho:
            self.despacho, self.detenido = despacho_id, 0
            self.paradas = ordenar_paradas(self.pos, paradas)
            if despacho_id:
                log.info("%s, viaje %s: %d parada(s)", self.id, despacho_id, len(self.paradas))
            else:
                log.info("%s sin viaje: vuelve a su recorrido", self.id)
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
            destino, paso_km = self.paradas[0], VELOCIDAD_KMH * INTERVALO / 3600
        else:
            destino, paso_km = self.puntos[self.tramo], self.paso_km
        faltan = km_entre(self.pos, destino)
        if faltan <= paso_km:
            self.pos = destino
            if self.despacho is None:
                self.tramo = self.siguiente(self.tramo)
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
            viajes = viajes_en_curso(con, list(flota))
            filas = []
            for c in flota.values():
                c.asignar(*viajes.get(c.id, (None, [])))
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
