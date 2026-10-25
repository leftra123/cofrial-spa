"""Simulador IoT de la flota de Cofrial.

Un proceso simula un grupo de camiones (por defecto CAM-01 a CAM-10; con PRIMER_CAMION y NUM_CAMIONES se elige otro grupo,
y con CAMION_ID, uno solo). Lee de la base de datos el rango de temperatura de cada camión y, cada INTERVALO_SEG segundos,
inserta una lectura por camión en la tabla telemetria con los campos que exige la pauta:
camion_id, temp_camara, lat, long, combustible_pct y alerta_ruptura_frio.
La alerta es verdadera cuando la temperatura sale del rango del camión. La mayoría de la flota funciona bien; de vez en
cuando un camión sufre una ruptura de frío (falla del equipo) que sube su temperatura hasta que se "repara".

Ciclo de un camión:
  - SIN despacho queda GUARDADO en la base (un puesto fijo junto al frigorífico), detenido, con su telemetría cada INTERVALO_SEG.
  - Con un despacho en curso (salida registrada y sin regreso) recorre la polilínea por calles que el servidor calculó y guardó
    en despacho.ruta_geojson (base -> paradas -> base); si el despacho no la tiene, recorre rectas entre las direcciones.
  - Al llegar a cada dirección los pedidos de esa dirección que iban «Despachada» pasan a «Camión en la puerta» y empieza a correr
    el plazo del cliente (fase en_la_puerta); se queda DETENCION_LECTURAS lecturas y sigue.
  - Al llegar a la última parada registra despacho.llegada_en; luego vuelve a la base por la ruta de regreso (fase volviendo)
    y al llegar registra despacho.regreso_en: recién entonces el camión queda libre.
  - El simulador también da por entregados («confirmada automáticamente») los pedidos cuyo camión lleva más de
    CONFIRMACION_AUTO_SEG en la puerta sin respuesta del cliente. Es una sentencia condicional sobre el estado: repetirla, o que
    corra en varios contenedores o tras un reinicio, no cambia nada; el plazo está en la base (orden.puerta_en), no en memoria.
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
# Velocidad y factor de calles COMPARTIDOS con la web: la hora de llegada que muestra la tienda se calcula con los mismos valores
# (variables VELOCIDAD_MEDIA_KMH y FACTOR_CALLES), así el camión llega cuando la pantalla dijo. VELOCIDAD_KMH queda solo por compatibilidad.
VELOCIDAD_MEDIA_KMH = float(os.environ.get("VELOCIDAD_MEDIA_KMH") or os.environ.get("VELOCIDAD_KMH") or "50")
FACTOR_CALLES = float(os.environ.get("FACTOR_CALLES", "1.3"))      # solo para rectas: la ruta por calles es más larga que la línea recta
DETENCION_LECTURAS = int(os.environ.get("DETENCION_LECTURAS", "6"))   # lecturas detenido en cada dirección de entrega
CONFIRMACION_AUTO_SEG = int(os.environ.get("CONFIRMACION_AUTO_SEG") or 120)
if os.environ.get("CAMION_ID"):
    IDS = [os.environ["CAMION_ID"]]
else:
    _primero, _cantidad = int(os.environ.get("PRIMER_CAMION", "1")), int(os.environ.get("NUM_CAMIONES", "10"))
    IDS = [f"CAM-{n:02d}" for n in range(_primero, _primero + _cantidad)]

# Base de la flota (referencia: INACAP Temuco). Debe coincidir con BASE_LOGISTICA en web/cofrial/settings.py
BASE = (-38.7330, -72.6040)


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
    """Vecino más cercano sobre [(direccion_id, lat, long)] (solo para despachos sin ruta guardada)."""
    pendientes, orden, actual = list(paradas), [], origen
    while pendientes:
        siguiente = min(pendientes, key=lambda p: km_entre(actual, (p[1], p[2])))
        pendientes.remove(siguiente)
        orden.append(siguiente)
        actual = (siguiente[1], siguiente[2])
    return orden


def viajes_en_curso(con, ids):
    """{camion_id: viaje} de los despachos con salida y sin regreso. viaje = {despacho_id, llego (ya llegó a la última parada),
    ruta (dict guardado o None), paradas (direcciones por visitar, solo si no hay ruta)}."""
    viajes = {}
    for camion_id, despacho_id, llego, ruta in con.execute(
            "SELECT camion_id, despacho_id, llegada_en IS NOT NULL, ruta_geojson FROM despacho "
            "WHERE camion_id = ANY(%s) AND salida_en IS NOT NULL AND regreso_en IS NULL ORDER BY salida_en DESC", (ids,)).fetchall():
        viajes[camion_id] = {"despacho_id": despacho_id, "llego": llego, "ruta": ruta, "paradas": []}     # si hubiera dos abiertos, gana el más antiguo
    sin_ruta = {v["despacho_id"]: v for v in viajes.values() if not v["ruta"]}
    if sin_ruta:
        for despacho_id, did, lat, lon in con.execute(
                'SELECT DISTINCT o.despacho_id, d.direccion_id, d.lat, d."long" FROM orden o JOIN direccion d USING (direccion_id) '
                "JOIN estado_orden e USING (estado_orden_id) WHERE o.despacho_id = ANY(%s) AND e.nombre = 'Despachada' "
                'AND d.lat IS NOT NULL AND d."long" IS NOT NULL', (list(sin_ruta),)).fetchall():
            sin_ruta[despacho_id]["paradas"].append((did, float(lat), float(lon)))
    return viajes


class Camion:
    def __init__(self, camion_id, tmin, tmax):
        self.id = camion_id
        self.tmin, self.tmax = tmin, tmax
        self.objetivo = (tmin + tmax) / 2
        self.temp = self.objetivo
        azar = random.Random(camion_id)                          # cada camión tiene siempre el mismo puesto en la base (a pocos metros del resto)
        self.casa = (BASE[0] + azar.uniform(-0.0003, 0.0003), BASE[1] + azar.uniform(-0.0003, 0.0003))
        self.pos = self.casa
        self.combustible = random.randint(60, 100)
        self.ruptura_restante = 0
        self.despacho = None            # viaje en curso
        self.camino = []                # [(lat, long)...] que está recorriendo; vacío = guardado en la base
        self.i = 0                      # índice del próximo vértice del camino
        self.marcas = {}                # {índice del camino: [direccion_id...]} de las direcciones de entrega
        self.ultima_marca = -1          # índice de la última parada
        self.paso_km = 0.0
        self.detenido = 0
        self.al_reanudar = None         # fase que se informa al terminar la detención
        self.fase = None
        self.eventos = []               # lo que el proceso debe escribir en la base: ("puerta", despacho, direccion), ("llegada", d), ("fase", d, f), ("regreso", d)

    @property
    def en_base(self):
        return self.despacho is None and not self.camino

    def _paso_para(self, aproximada):
        return VELOCIDAD_MEDIA_KMH * INTERVALO / 3600 / (FACTOR_CALLES if aproximada else 1)

    def _volver(self):
        """Regreso directo a la base desde donde está (sin ruta guardada para ese tramo)."""
        self.camino, self.i, self.marcas, self.ultima_marca = [self.pos, self.casa], 1, {}, -1
        self.paso_km = self._paso_para(True)

    def asignar(self, viaje):
        """Sincroniza con el despacho de la base: al aparecer uno nuevo arma su camino; si desaparece, vuelve a la base."""
        if viaje is None:
            if self.despacho is not None:                        # el viaje se cerró desde afuera: vuelve a su puesto
                log.info("%s sin viaje: vuelve a la base", self.id)
                self.despacho, self.fase, self.detenido, self.al_reanudar = None, None, 0, None
                self._volver()
            return
        if viaje["despacho_id"] != self.despacho:
            self.despacho, self.detenido, self.al_reanudar, self.eventos = viaje["despacho_id"], 0, None, []
            ruta = viaje["ruta"]
            if viaje["llego"]:                                    # reinicio a mitad de la vuelta: solo termina de volver
                self._volver()
                self.fase = "volviendo"
            elif ruta and ruta.get("puntos"):
                puntos = [tuple(p) for p in ruta["puntos"]]
                desfase = 0
                if km_entre(self.pos, puntos[0]) > 0.2:           # no parte de la base: primero llega al comienzo de la ruta
                    puntos, desfase = [self.pos] + puntos, 1
                self.camino, self.i, self.marcas, self.paso_km = puntos, 1, {}, self._paso_para(bool(ruta.get("aproximada")))
                for p in ruta.get("paradas", []):
                    self.marcas.setdefault(p["indice"] + desfase, []).append(p["direccion_id"])
                self.fase = "en_ruta"
            else:                                                 # sin ruta guardada: rectas entre las direcciones y de vuelta a la base
                orden = ordenar_paradas(self.pos, viaje["paradas"])
                self.camino = [self.pos] + [(p[1], p[2]) for p in orden] + [self.casa]
                self.i, self.marcas, self.paso_km = 1, {k + 1: [p[0]] for k, p in enumerate(orden)}, self._paso_para(True)
                self.fase = "en_ruta"
            self.ultima_marca = max(self.marcas) if self.marcas else -1
            log.info("%s, viaje %s: %d parada(s)", self.id, self.despacho, len(self.marcas))
            if not self.marcas and self.fase == "en_ruta":        # nada que entregar: llega y vuelve
                self.eventos.append(("llegada", self.despacho))
                self.fase = "volviendo"
                self.eventos.append(("fase", self.despacho, "volviendo"))
        elif viaje["llego"] and self.fase != "volviendo":          # corrección manual: se dio el viaje por llegado, el camión regresa
            self.fase, self.detenido, self.al_reanudar = "volviendo", 0, None
            self._volver()

    def posicion(self):
        if self.detenido > 0:
            self.detenido -= 1
            if self.detenido == 0 and self.al_reanudar:
                self.fase = self.al_reanudar
                self.eventos.append(("fase", self.despacho, self.fase))
                self.al_reanudar = None
            return self.pos
        if not self.camino:
            return self.pos                                       # guardado en la base
        paso = self.paso_km
        while paso > 0 and self.i < len(self.camino):
            destino = self.camino[self.i]
            faltan = km_entre(self.pos, destino)
            if faltan > paso:
                f = paso / faltan
                self.pos = (self.pos[0] + (destino[0] - self.pos[0]) * f, self.pos[1] + (destino[1] - self.pos[1]) * f)
                break
            self.pos, paso = destino, paso - faltan
            indice, self.i = self.i, self.i + 1
            if indice in self.marcas:                              # llegó a una dirección de entrega
                for did in self.marcas.pop(indice):
                    self.eventos.append(("puerta", self.despacho, did))
                self.fase = "en_la_puerta"
                self.eventos.append(("fase", self.despacho, self.fase))
                self.detenido = DETENCION_LECTURAS
                if indice == self.ultima_marca:                    # última parada: queda registrada la llegada y luego vuelve
                    self.eventos.append(("llegada", self.despacho))
                    self.al_reanudar = "volviendo"
                else:
                    self.al_reanudar = "en_ruta"
                if self.detenido == 0:                             # sin detención configurada
                    self.fase = self.al_reanudar
                    self.eventos.append(("fase", self.despacho, self.fase))
                    self.al_reanudar = None
                break
        if self.i >= len(self.camino):                             # llegó al final del camino: de vuelta en la base
            if self.despacho is not None:
                self.eventos.append(("regreso", self.despacho))
                log.info("%s de vuelta en la base (viaje %s)", self.id, self.despacho)
            self.despacho, self.camino, self.marcas, self.fase = None, [], {}, None
            self.pos = self.casa
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


def aplicar_eventos(con, camion):
    """Escribe en la base lo que le pasó al camión en esta lectura. Cada sentencia es condicional sobre el estado actual, así que
    repetirla no cambia nada."""
    for ev in camion.eventos:
        if ev[0] == "puerta":
            con.execute(
                "UPDATE orden SET estado_orden_id = (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Camión en la puerta'), puerta_en = now() "
                "WHERE despacho_id = %s AND direccion_id = %s AND estado_orden_id = (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Despachada')",
                (ev[1], ev[2]))
        elif ev[0] == "llegada":
            con.execute("UPDATE despacho SET llegada_en = now(), fase = 'en_la_puerta' WHERE despacho_id = %s AND llegada_en IS NULL", (ev[1],))
        elif ev[0] == "fase":
            con.execute("UPDATE despacho SET fase = %s WHERE despacho_id = %s AND regreso_en IS NULL", (ev[2], ev[1]))
        elif ev[0] == "regreso":
            con.execute("UPDATE despacho SET llegada_en = COALESCE(llegada_en, now()), regreso_en = now() WHERE despacho_id = %s AND regreso_en IS NULL", (ev[1],))
    camion.eventos = []


def confirmar_vencidas(con):
    """Da por entregados los pedidos con el camión en la puerta sin respuesta pasado el plazo (misma regla que la web)."""
    return con.execute(
        "UPDATE orden SET estado_orden_id = (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Entregada'), "
        "entrega_resuelta_en = now(), entrega_automatica = true "
        "WHERE estado_orden_id = (SELECT estado_orden_id FROM estado_orden WHERE nombre = 'Camión en la puerta') "
        "AND puerta_en <= now() - make_interval(secs => %s)", (CONFIRMACION_AUTO_SEG,)).rowcount


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
                c.asignar(viajes.get(c.id))
                temp, lat, lon, comb, alerta = c.paso()
                filas.append((c.id, temp, lat, lon, comb, alerta))
                aplicar_eventos(con, c)
            confirmadas = confirmar_vencidas(con)
            if confirmadas:
                log.info("%d pedido(s) dados por entregados al vencer el plazo de confirmación", confirmadas)
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
