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

Escenarios: en cada ciclo el proceso lee de la tabla escenario_simulador los escenarios vigentes de sus camiones (la web los valida y los
escribe; ver web/flota/escenarios.py). Cambian el comportamiento del camión, no las lecturas: estas se siguen insertando aquí.
  - falla_frio: al llegar al avance pedido la temperatura sube duracion_lecturas lecturas; la alerta sale de la misma regla de siempre.
    Esas lecturas van marcadas forzada, para que la limpieza de la demostración las pueda borrar.
  - entrega_perfecta: sin rupturas al azar y el cliente confirma en cada parada.
  - cliente_no_recibe: en la parada pedida el pedido queda «Entrega no concretada» y se crea el requerimiento para ventas.
Sin escenario vigente no cambia nada. Si la tabla aún no existe (la EC2 IoT se actualizó antes que la web), se sigue como si no hubiera escenarios.

Tiempo acelerado: en cada ciclo el proceso lee de ajuste_simulador el multiplicador que pidió un administrador en /demo/ (1, 5, 20 o 60), sin
recrear contenedores. Multiplica solo los km que el camión avanza por lectura. Lo demás sigue igual: se inserta una lectura cada INTERVALO_SEG con
los mismos campos, la detención en la puerta dura las mismas lecturas y el plazo del cliente sigue en segundos reales (lo responde una persona).
Un camión rápido no se salta paradas: el avance de cada lectura termina en la primera parada que encuentra.
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
ESPERA_RESPUESTA_LECTURAS = int(os.environ.get("ESPERA_RESPUESTA_LECTURAS", "3"))   # en un escenario, lecturas que el cliente tarda en responder en la puerta
TOPE_SOBRE_RANGO_C = 12.0                                                           # una falla de escenario no sube más que esto sobre el máximo del camión
TIPOS_ESCENARIO = ("falla_frio", "entrega_perfecta", "cliente_no_recibe")
MULTIPLICADORES = (1, 5, 20, 60)                                                    # los mismos de web/flota/tiempo.py y de la restricción de la tabla
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


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def escenario_de_fila(fila):
    """Fila de escenario_simulador -> diccionario. La web y las restricciones de la tabla ya validaron; igual se ignora un tipo desconocido y se acotan los números."""
    escenario_id, camion_id, despacho_id, tipo, momento, duracion, subida, direccion_id, motivo = fila
    if tipo not in TIPOS_ESCENARIO:
        log.warning("Escenario %s con tipo desconocido: se ignora", escenario_id)
        return None
    return {"id": escenario_id, "camion_id": camion_id, "despacho_id": despacho_id, "tipo": tipo, "momento_pct": _acotar(momento or 50, 5, 95),
            "duracion_lecturas": _acotar(duracion or 12, 6, 36), "subida_c": _acotar(subida or 1.0, 1.0, 2.0), "direccion_id": direccion_id, "motivo": motivo or ""}


_sin_tabla_avisado = False


def escenarios_vigentes(con, ids):
    """{camion_id: escenario} de los viajes abiertos. Una consulta por ciclo. Un problema de esquema no puede detener la telemetría."""
    global _sin_tabla_avisado
    try:
        filas = con.execute(
            "SELECT e.escenario_id, d.camion_id, e.despacho_id, e.tipo, e.momento_pct, e.duracion_lecturas, e.subida_c, e.direccion_id, e.motivo_no_recibe "
            "FROM escenario_simulador e JOIN despacho d USING (despacho_id) "
            "WHERE d.camion_id = ANY(%s) AND e.estado IN ('pendiente', 'en_curso') AND d.regreso_en IS NULL", (ids,)).fetchall()
    except psycopg.ProgrammingError as e:
        if not _sin_tabla_avisado:
            log.warning("Sin escenarios (%s); el simulador sigue normal", str(e).strip().splitlines()[0])
            _sin_tabla_avisado = True
        return {}
    escenarios = {}
    for fila in filas:
        esc = escenario_de_fila(fila)
        if esc:
            escenarios[esc["camion_id"]] = esc
    return escenarios


_sin_ajuste_avisado = False


def multiplicador_vigente(con):
    """Cuántas veces más rápido avanzan los camiones. Sin fila, sin tabla o con un valor desconocido, 1: un ajuste nunca detiene la telemetría."""
    global _sin_ajuste_avisado
    try:
        fila = con.execute("SELECT multiplicador_tiempo FROM ajuste_simulador WHERE ajuste_id = 1").fetchone()
    except psycopg.ProgrammingError as e:
        if not _sin_ajuste_avisado:
            log.warning("Sin ajuste de tiempo (%s); el simulador sigue a 1×", str(e).strip().splitlines()[0])
            _sin_ajuste_avisado = True
        return 1
    return fila[0] if fila and fila[0] in MULTIPLICADORES else 1


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
        self.paso_km = 0.0              # km por lectura a velocidad normal
        self.multiplicador = 1          # tiempo acelerado: lo fija el ciclo principal con lo que lee de la base
        self.detenido = 0
        self.al_reanudar = None         # fase que se informa al terminar la detención
        self.fase = None
        self.eventos = []               # lo que el proceso debe escribir en la base: ("puerta", despacho, direccion), ("llegada", d), ("fase", d, f), ("regreso", d)
        self.escenario = None           # escenario vigente de este camión (None: comportamiento normal)
        self.respuestas = []            # [[lecturas que faltan, direccion_id]...] clientes de un escenario por responder en la puerta
        self.lectura_forzada = False    # la última lectura es parte de una falla de escenario

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
        elif viaje["llego"] and self.fase != "volviendo" and self.al_reanudar != "volviendo":      # corrección manual: se dio el viaje por llegado, el camión regresa
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
        paso = self.paso_km * self.multiplicador                   # lo que sobre al llegar a una parada se descarta: nunca se pasa de largo
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

    def progreso_pct(self):
        """Avance del camión hacia la última parada, medido en km sobre el camino (los vértices de la ruta no están a la misma distancia)."""
        if self.ultima_marca < 1 or self.i > self.ultima_marca:
            return 100.0
        tramos = [km_entre(a, b) for a, b in zip(self.camino, self.camino[1:self.ultima_marca + 1])]
        total = sum(tramos)
        if total == 0:
            return 100.0
        return 100 * (sum(tramos[:self.i - 1]) + km_entre(self.camino[self.i - 1], self.pos)) / total

    def aplicar_escenario(self, esc):
        """Sincroniza con el escenario de la base. Si desapareció (cancelado, limpiado o terminado) se suelta y sigue el comportamiento normal."""
        if esc is not None and esc["despacho_id"] != self.despacho:
            esc = None
        if esc is None:
            if self.escenario is not None:
                if self.escenario.get("disparada"):
                    self.ruptura_restante = 0                      # una falla cancelada a medias se corta: la temperatura vuelve sola al objetivo
                self.escenario, self.respuestas = None, []
            return
        if self.escenario is not None and self.escenario["id"] == esc["id"]:
            return
        self.escenario, self.respuestas = {**esc, "disparada": False, "terminado": False}, []
        log.info("%s, viaje %s: escenario %s (%s)", self.id, self.despacho, esc["id"], esc["tipo"])
        if esc["tipo"] == "entrega_perfecta":
            self.ruptura_restante = 0
            self.eventos.append(("escenario", esc["id"], "en_curso"))

    def _terminar_escenario(self):
        self.escenario["terminado"] = True
        self.eventos.append(("escenario", self.escenario["id"], "terminado"))

    def _disparar_falla(self):
        esc = self.escenario
        if esc is None or esc["tipo"] != "falla_frio" or esc["disparada"] or esc["terminado"]:
            return
        if self.fase == "volviendo":                               # el viaje se dio por llegado antes del avance pedido: ya no hay carga que dañar
            self._terminar_escenario()
        elif self.progreso_pct() >= esc["momento_pct"]:
            esc["disparada"], self.ruptura_restante = True, esc["duracion_lecturas"]
            self.eventos.append(("escenario", esc["id"], "en_curso"))
            log.warning("Escenario %s: falla de frío en %s durante %d lecturas", esc["id"], self.id, self.ruptura_restante)

    def _despues_de_leer(self, alerta):
        """Efectos del escenario que dependen de lo que pasó en esta lectura. Sin escenario no hace nada."""
        esc = self.escenario
        self.lectura_forzada = bool(esc and esc.get("disparada") and not esc["terminado"])
        if esc is None or esc["terminado"]:
            return
        if esc["tipo"] == "falla_frio":
            if esc["disparada"] and self.ruptura_restante == 0 and not alerta:        # volvió al rango: esta última lectura normal cierra la falla
                self._terminar_escenario()
            return
        for ev in list(self.eventos):
            if ev[0] == "puerta" and (esc["tipo"] == "entrega_perfecta" or ev[2] == esc["direccion_id"]):
                self.respuestas.append([ESPERA_RESPUESTA_LECTURAS, ev[2]])
                if esc["tipo"] == "cliente_no_recibe":
                    self.eventos.append(("escenario", esc["id"], "en_curso"))
        for respuesta in self.respuestas:
            respuesta[0] -= 1
            if respuesta[0] <= 0:
                if esc["tipo"] == "entrega_perfecta":
                    self.eventos.append(("recibe", esc["despacho_id"], respuesta[1]))
                else:
                    self.eventos.append(("no_recibe", esc["despacho_id"], respuesta[1], esc["motivo"]))
                    self._terminar_escenario()
        self.respuestas = [r for r in self.respuestas if r[0] > 0]

    def paso(self):
        esc = self.escenario
        self._disparar_falla()
        falla = bool(esc and esc.get("disparada") and not esc["terminado"] and self.ruptura_restante > 0)
        protegido = bool(esc and esc["tipo"] == "entrega_perfecta")
        if self.ruptura_restante == 0 and not protegido and random.random() < PROB_RUPTURA:
            self.ruptura_restante = random.randint(6, 14)
            log.warning("Falla de frío simulada en %s durante %d lecturas", self.id, self.ruptura_restante)
        if self.ruptura_restante > 0:
            self.ruptura_restante -= 1
            if falla:
                self.temp = min(self.temp + esc["subida_c"] * random.uniform(0.85, 1.15), self.tmax + TOPE_SOBRE_RANGO_C)
            else:
                self.temp += random.uniform(0.6, 1.4)             # sube sin control
        else:
            self.temp += (self.objetivo - self.temp) * 0.4 + random.uniform(-0.2, 0.2)   # vuelve al objetivo
        self.combustible = max(0, self.combustible - (1 if random.random() < 0.15 else 0))
        if self.combustible < 15:
            self.combustible = 95                                  # recarga
        lat, lon = self.posicion()
        temp = round(self.temp, 1)
        alerta = temp > self.tmax or temp < self.tmin
        self._despues_de_leer(alerta)
        return temp, round(lat, 6), round(lon, 6), self.combustible, alerta


ESTADO_ORDEN = "(SELECT estado_orden_id FROM estado_orden WHERE nombre = '{}')"
# Misma regla que pedidos.servicios.resolver_entrega. El texto y los ids entran siempre como parámetros, nunca dentro de la sentencia.
SQL_RECIBE = (f"UPDATE orden SET estado_orden_id = {ESTADO_ORDEN.format('Entregada')}, entrega_resuelta_en = now(), entrega_automatica = false "
              f"WHERE despacho_id = %s AND direccion_id = %s AND estado_orden_id = {ESTADO_ORDEN.format('Camión en la puerta')}")
SQL_NO_RECIBE = (f"WITH marcadas AS (UPDATE orden SET estado_orden_id = {ESTADO_ORDEN.format('Entrega no concretada')}, entrega_resuelta_en = now(), "
                 f"entrega_automatica = false, entrega_motivo = %(motivo)s WHERE despacho_id = %(despacho)s AND direccion_id = %(direccion)s "
                 f"AND estado_orden_id = {ESTADO_ORDEN.format('Camión en la puerta')} RETURNING orden_id, direccion_id) "
                 "INSERT INTO requerimiento (cliente_id, orden_id, asunto, descripcion, categoria_requerimiento_id, estado, clasificado_manual, creado_en) "
                 "SELECT d.cliente_id, m.orden_id, 'Entrega no concretada del pedido N.º ' || m.orden_id, %(motivo)s, c.categoria_requerimiento_id, "
                 "CASE WHEN c.categoria_requerimiento_id IS NULL THEN 'sin_clasificar' ELSE 'clasificado' END, false, now() "
                 "FROM marcadas m JOIN direccion d USING (direccion_id) "
                 "LEFT JOIN categoria_requerimiento c ON c.nombre = 'Problema en la entrega'")
SQL_ESCENARIO = ("UPDATE escenario_simulador SET estado = %(estado)s, iniciado_en = COALESCE(iniciado_en, now()), "
                 "terminado_en = CASE WHEN %(fin)s THEN now() END "
                 "WHERE escenario_id = %(id)s AND estado IN ('pendiente', 'en_curso')")


def aplicar_evento_de_escenario(con, ev):
    """Un error de esquema en un evento de escenario se registra y no detiene la telemetría (el resto de los errores los maneja el ciclo principal)."""
    try:
        if ev[0] == "recibe":
            con.execute(SQL_RECIBE, (ev[1], ev[2]))
        elif ev[0] == "no_recibe":
            with con.transaction():
                con.execute(SQL_NO_RECIBE, {"motivo": ev[3], "despacho": ev[1], "direccion": ev[2]})
        else:
            con.execute(SQL_ESCENARIO, {"estado": ev[2], "fin": ev[2] == "terminado", "id": ev[1]})
    except (psycopg.ProgrammingError, psycopg.IntegrityError) as e:
        log.error("Evento de escenario %s sin aplicar: %s", ev[0], str(e).strip().splitlines()[0])


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
        elif ev[0] in ("recibe", "no_recibe", "escenario"):
            aplicar_evento_de_escenario(con, ev)
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
    flota, lecturas_hechas, multiplicador_anterior = {}, 0, 1
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
            escenarios = escenarios_vigentes(con, list(flota))
            multiplicador = multiplicador_vigente(con)
            if multiplicador != multiplicador_anterior:
                log.info("Tiempo de la simulación: %d×", multiplicador)
                multiplicador_anterior = multiplicador
            filas = []
            for c in flota.values():
                c.multiplicador = multiplicador
                c.asignar(viajes.get(c.id))
                c.aplicar_escenario(escenarios.get(c.id))
                temp, lat, lon, comb, alerta = c.paso()
                filas.append((c.id, temp, lat, lon, comb, alerta, c.lectura_forzada))
                aplicar_eventos(con, c)
            confirmadas = confirmar_vencidas(con)
            if confirmadas:
                log.info("%d pedido(s) dados por entregados al vencer el plazo de confirmación", confirmadas)
            if filas:
                with con.transaction():
                    con.cursor().executemany(
                        'INSERT INTO telemetria (camion_id, temp_camara, lat, "long", combustible_pct, alerta_ruptura_frio, forzada, registrado_en) '
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, now())", filas)
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
