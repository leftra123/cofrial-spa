#!/usr/bin/env python3
"""Verificación de punta a punta de la instalación de Cofrial en AWS. Solo lee (no crea datos) salvo con --ia y --compra-ensayo.

    python3 aws/verificar.py                 # usa la IP de aws/.estado/ip.txt o la variable COFRIAL_URL
    python3 aws/verificar.py http://IP       # o una dirección explícita
    python3 aws/verificar.py --ia            # además envía un reclamo de prueba por Soporte y comprueba la clasificación
    python3 aws/verificar.py --compra-ensayo # además hace la compra de ensayo B2B y B2C (crea pedidos reales); no repite si ya hay una vigente
    python3 aws/verificar.py --defensa       # modo previo a la defensa: las 5 filas D1 a D5 de la Torre deben quedar «verificado» y /torre/pulso/ rápido

Las claves se toman de DEMO_PASSWORD, ADMIN_PASSWORD y CLAVE_UNICA_DEMO (variables o aws/.estado/secretos.env); no se imprimen.
Cada cuenta entra con la clave única (si se aplicó cambiar_clave_demo --misma), con su clave propia (web/clientes/cuentas_demo.py) o, si no, con la común de antes.
Solo usa la biblioteca estándar de Python (sin instalar nada). Sale con código 0 si todo pasó y 1 si algo falló.
"""
import datetime
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "clientes"))
import cuentas_demo  # noqa: E402  (no usa Django)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(RAIZ, "aws", ".estado")


def leer_estado(nombre):
    try:
        for linea in open(os.path.join(ESTADO, "secretos.env")):
            if linea.startswith(nombre + "="):
                return linea.strip().split("=", 1)[1]
    except OSError:
        pass
    return None


def direccion():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        return args[0].rstrip("/")
    if os.environ.get("COFRIAL_URL"):
        return os.environ["COFRIAL_URL"].rstrip("/")
    try:
        return "http://" + open(os.path.join(ESTADO, "ip.txt")).read().strip()
    except OSError:
        sys.exit("No sé la dirección: pásala como argumento (http://IP) o define COFRIAL_URL.")


BASE = direccion()
HOST = BASE.split("//", 1)[1].split("/")[0].split(":")[0]
CLAVE = os.environ.get("DEMO_PASSWORD") or leer_estado("DEMO_PASSWORD")
CLAVE_ADMIN = os.environ.get("ADMIN_PASSWORD") or leer_estado("ADMIN_PASSWORD") or CLAVE
CLAVE_UNICA = os.environ.get("CLAVE_UNICA_DEMO") or leer_estado("CLAVE_UNICA_DEMO")
DEFENSA = "--defensa" in sys.argv
COMPRA_ENSAYO = "--compra-ensayo" in sys.argv
PULSO_MAX_MS = 3000          # peor caso aceptado de /torre/pulso/ sin caché; la pantalla marca «Sin conexión» a los 8000 ms (ESPERA_MS)
VIGENCIA_ENSAYO_DIAS = 7     # la rúbrica D2/D4 de la Torre mira los últimos 7 días
ADMINISTRADORES = cuentas_demo.ADMINISTRADORES
MODO_CLAVE = ["unica" if os.environ.get("CLAVE_UNICA_DEMO") or leer_estado("CLAVE_UNICA_DEMO") else "propia"]


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Sesion:
    """Un navegador mínimo: cookies, formularios con CSRF y control de redirecciones."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.abre = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def pedir(self, ruta, datos=None, base=None):
        url = (base or BASE) + ruta
        cuerpo = urllib.parse.urlencode(datos).encode() if datos is not None else None
        pedido = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": "cofrial-verificar/1.0", "Referer": url})
        try:
            r = self.abre.open(pedido, timeout=30)
            return r.status, r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), url
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, "", url

    def token(self, ruta, base=None):
        _, html, _ = self.pedir(ruta, base=base)
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        return m.group(1) if m else ""

    def entrar(self, usuario, base=None):
        comun = CLAVE_ADMIN if usuario in ADMINISTRADORES else CLAVE
        opciones = {"propia": cuentas_demo.clave_de(usuario, comun), "comun": comun}    # la común si el despliegue es anterior
        if CLAVE_UNICA:
            opciones["unica"] = CLAVE_UNICA                                         # cambiar_clave_demo --misma: la misma clave en las 13 cuentas
        for modo in sorted(opciones, key=lambda m: m != MODO_CLAVE[0]):            # primero la que ya funcionó: menos intentos fallidos
            t = self.token("/cuenta/entrar/", base)
            st, html, url = self.pedir("/cuenta/entrar/", {"csrfmiddlewaretoken": t, "username": usuario, "password": opciones[modo], "next": "/"}, base=base)
            if st == 200 and "/cuenta/salir/" in html:        # el formulario de salida solo aparece con sesión iniciada
                MODO_CLAVE[0] = modo
                return True
        return False

    def json(self, ruta):
        st, cuerpo, _ = self.pedir(ruta)
        try:
            return st, (json.loads(cuerpo) if st == 200 else None)
        except ValueError:
            return st, None


RESULTADOS = []


def marca(estado, nombre, detalle=""):
    RESULTADOS.append((estado, nombre, detalle))
    simbolo = {"ok": "✓", "mal": "✗", "aviso": "⚠", "info": "·"}[estado]
    print(f"  {simbolo} {nombre}" + (f"  -> {detalle}" if detalle else ""))


def chk(cond, nombre, detalle_mal=""):
    marca("ok" if cond else "mal", nombre, "" if cond else detalle_mal)
    return bool(cond)


def titulo(t):
    print(f"\n{t}")


def precio(html, sku):
    """Precio del producto según el atributo data-precio de su tarjeta en el catálogo."""
    m = re.search(r'data-sku="' + re.escape(sku) + r'"\s+data-precio="(\d+)"', html)
    return m.group(1) if m else None


def consulta_grafana(sesion, sql):
    """Consulta el tablero por /bi/ con la sesión de la aplicación (Grafana no se alcanza de otra forma)."""
    sql = sql.replace("$camion", "'CAM-01'")           # variable del selector de camiones del tablero: aquí se prueba con uno
    cuerpo = json.dumps({"queries": [{"refId": "A", "datasource": {"uid": "cofrial-pg"}, "rawSql": sql, "format": "table"}],
                         "from": "now-24h", "to": "now"}).encode()
    pedido = urllib.request.Request(f"{BASE}/bi/api/ds/query", data=cuerpo, headers={"Content-Type": "application/json", "Origin": BASE})
    try:
        return json.loads(sesion.abre.open(pedido, timeout=30).read())["results"]["A"]
    except urllib.error.HTTPError as e:
        return json.loads(e.read())["results"]["A"]


def exigir(cond, nombre, detalle_mal=""):
    """Falla en modo --defensa; antes de la demo es solo un aviso (todavía puede faltar una venta o una lectura real)."""
    if DEFENSA:
        return chk(cond, nombre, detalle_mal)
    marca("ok" if cond else "aviso", nombre, "" if cond else detalle_mal)
    return bool(cond)


def nombre_sslip(host):
    """54.82.100.161 -> 54-82-100-161.sslip.io (sslip.io devuelve la IP escrita en el nombre); None si el host ya es un nombre."""
    return host.replace(".", "-") + ".sslip.io" if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host) else None


def fila_del_requerimiento(html, asunto):
    """Fila de la lista de requerimientos con ese asunto (o None): para leer su estado sin depender de otras filas."""
    for fila in html.split("<tr>"):
        if f"<b>{asunto}</b>" in fila:
            return fila
    return None


def pedidos_vigentes(sesion, solo_ensayo):
    """Pedidos reales del cliente de la sesión de los últimos días: ni cancelados, ni rechazados enteros, ni del historial HIS-.
    Con solo_ensayo, solo los de OC ENSAYO-. Devuelve None si la API no responde."""
    st, d = sesion.json("/api/pedidos/")
    if st != 200 or not d:
        return None
    desde = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=VIGENCIA_ENSAYO_DIAS)
    vigentes = []
    for o in d["ordenes"]:
        if o["estado"] in ("Cancelada", "Rechazada en recepción") or (o["numero_oc"] or "").startswith("HIS-"):
            continue
        if datetime.datetime.fromisoformat(o["creada_en"].replace("Z", "+00:00")) < desde:
            continue
        if solo_ensayo and not (o["numero_oc"] or "").startswith("ENSAYO-"):
            continue
        vigentes.append(o)
    return vigentes


def comprar_ensayo(sesion, canal, producto="VAC-LOM-5K"):
    """Una compra real por el flujo del sitio (catálogo, carrito, confirmar). Devuelve (estado, detalle): «creada», «vigente», «mp» o «error».
    No repite si ya hay una vigente de los últimos 7 días; el B2C con Mercado Pago activo se paga en el navegador (el script no maneja el Brick)."""
    previas = pedidos_vigentes(sesion, solo_ensayo=(canal == "B2B"))
    if previas is None:
        return "error", "la API de pedidos no responde"
    if previas:
        return "vigente", f"orden {previas[0]['orden_id']} ({previas[0]['numero_oc'] or 'sin OC'}, {previas[0]['estado']})"
    m = re.search(r'data-sku="' + re.escape(producto) + r'".*?name="producto" value="(\d+)"', sesion.pedir("/catalogo/")[1], re.S)
    if not m:
        return "error", f"no encontré {producto} en el catálogo"
    st, _, _ = sesion.pedir("/carrito/agregar/", {"csrfmiddlewaretoken": sesion.token("/carrito/"), "producto": m.group(1), "cantidad": "1", "volver": "/carrito/"})
    st, html, _ = sesion.pedir("/carrito/")
    if 'data-checkout="mp-modal-v4"' in html:
        sesion.pedir("/carrito/actualizar/", {"csrfmiddlewaretoken": sesion.token("/carrito/"), "producto": m.group(1), "cantidad": "0"})     # deja el carrito como estaba
        return "mp", "el carrito de este canal paga con Mercado Pago (sandbox): hacerlo a mano en el navegador"
    d = re.search(r'<select name="direccion"[^>]*>.*?<option value="(\d+)"', html, re.S)
    if not d:
        return "error", "el carrito no ofrece dirección de entrega"
    oc = "ENSAYO-" + datetime.datetime.now().strftime("%Y%m%d-%H%M")
    datos = {"csrfmiddlewaretoken": sesion.token("/carrito/"), "direccion": d.group(1), "recibe": "", "recibe_nuevo": "",
             "comprobante": "factura" if canal == "B2B" else "boleta"}
    if canal == "B2B":
        datos["numero_oc"] = oc
    st, _, url = sesion.pedir("/carrito/confirmar/", datos)
    if "/pedidos/" in url and "nueva=1" in url:
        return "creada", f"{url.split(BASE)[-1]}" + (f" (OC {oc})" if canal == "B2B" else "")
    return "error", f"no se generó la orden (HTTP {st}, terminó en {url.split(BASE)[-1]})"


USUARIOS = {"hospital": "abastecimiento@hospital.test", "ana": "ana@correo.test",
            "vendedora": "vendedora@cofrial.cl", "vendedor2": "vendedor2@cofrial.cl", "gerente": "gerencia@cofrial.cl",
            "despachador": "despacho@cofrial.cl", "admin": "admin@cofrial.cl",
            "felipe": "felipe@cofrial.cl", "sergio": "sergio@cofrial.cl", "eric": "eric@cofrial.cl"}


def main():
    t0 = time.time()
    print(f"Verificando {BASE}")
    if not CLAVE:
        sys.exit("Falta la clave de demostración: define DEMO_PASSWORD o deja aws/.estado/secretos.env.")

    titulo("1. Aplicación y acceso")
    anon = Sesion()
    st, cuerpo = anon.json("/salud/")
    if not chk(st == 200 and cuerpo and cuerpo.get("estado") == "ok", "La aplicación responde (/salud/)", f"HTTP {st}"):
        print("\nLa aplicación no responde: revisar que el laboratorio y las instancias estén encendidos (bash aws/provision.sh encender).")
        sys.exit(1)
    st, html, _ = anon.pedir("/catalogo/")
    chk(st == 200 and "Catálogo" in html, "Catálogo visible sin iniciar sesión", f"HTTP {st}")
    st, html, url = anon.pedir("/crm/")
    chk("/cuenta/entrar/" in url, "El CRM exige iniciar sesión", f"terminó en {url}")

    sesiones = {}
    for clave, usuario in USUARIOS.items():
        s = Sesion()
        sesiones[clave] = s if s.entrar(usuario) else None
        chk(sesiones[clave] is not None, f"Inicio de sesión: {usuario}", "usuario o clave rechazados")
    if not all(sesiones.values()):
        print("\nHay cuentas que no entran: revisar las claves (DEMO_PASSWORD, ADMIN_PASSWORD, CLAVE_UNICA_DEMO o la que se cambió desde la cuenta).")

    otras = [u for u in cuentas_demo.USUARIOS if u not in USUARIOS.values()]       # las que no se usan en las demás pruebas (Angol, Villarrica, Pucón…)
    entran = sum(1 for s in sesiones.values() if s)
    for usuario in otras:
        entran += chk(Sesion().entrar(usuario), f"Inicio de sesión: {usuario}", "usuario o clave rechazados")
    chk(entran == len(cuentas_demo.USUARIOS) == len(USUARIOS) + len(otras), f"Las {len(cuentas_demo.USUARIOS)} cuentas de demostración entran: {entran}/{len(cuentas_demo.USUARIOS)}",
        "revisar las claves: tras recrear la web hay que repetir cambiar_clave_demo --misma")
    st, _, _ = Sesion().pedir("/cuenta/entrar/", {"username": "no-existe@cofrial.test", "password": "x"})      # sin token CSRF
    chk(st == 403, "Un envío del formulario de ingreso sin token CSRF se rechaza (403)", f"HTTP {st}")
    falso = Sesion()
    st, html, _ = falso.pedir("/cuenta/entrar/", {"csrfmiddlewaretoken": falso.token("/cuenta/entrar/"), "username": "no-existe@cofrial.test", "password": "x", "next": "/"})
    chk(st == 200 and "/cuenta/salir/" not in html, "Con token CSRF pero clave falsa el ingreso se rechaza", f"HTTP {st}")
    nombre = nombre_sslip(HOST)
    if nombre:
        base_nombre = "http://" + nombre
        sesion_nombre = Sesion()
        st, cuerpo, _ = sesion_nombre.pedir("/salud/", base=base_nombre)
        chk(st == 200 and '"ok"' in cuerpo, f"El nombre {nombre} responde (/salud/)", f"HTTP {st}: sin respuesta (¿sin internet o sin DNS?)")
        chk(sesion_nombre.entrar("gerencia@cofrial.cl", base=base_nombre), f"Ingreso con formulario y CSRF por {nombre}", "el formulario no entra por el nombre (¿DJANGO_CSRF_ORIGINS?)")

    titulo("2. E-commerce: perfiles B2B y B2C")
    if sesiones["hospital"] and sesiones["ana"]:
        producto = "VAC-LOM-5K"          # Lomo vetado de vacuno 5 kg
        pb = precio(sesiones["hospital"].pedir("/catalogo/")[1], producto)
        pc = precio(sesiones["ana"].pedir("/catalogo/")[1], producto)
        chk(pb and pc and pb != pc, f"El mismo producto tiene precio distinto: B2B ${pb} y B2C ${pc}", "los precios son iguales o no se encontraron")
        st, _, _ = sesiones["ana"].pedir("/pedidos/")
        chk(st == 200, "Cliente B2C ve Mis pedidos", f"HTTP {st}")
        st, d = sesiones["hospital"].json("/api/pedidos/")
        n = len(d["ordenes"]) if d else 0
        chk(st == 200 and n >= 1, f"API de pedidos del Hospital: {n} órdenes", f"HTTP {st}")

    titulo("3. Permisos por rol")
    pruebas = [("ana", "/crm/", 403), ("ana", "/flota/", 403), ("vendedora", "/flota/", 403), ("despachador", "/flota/", 200),
               ("despachador", "/crm/embudo/", 403), ("gerente", "/crm/prospectos/nuevo/", 403), ("vendedora", "/crm/prospectos/nuevo/", 200),
               ("admin", "/flota/", 200), ("ana", "/pedidos/99999/", 404)]
    for quien, ruta, esperado in pruebas:
        if sesiones.get(quien):
            st, html, _ = sesiones[quien].pedir(ruta)
            ok = st == esperado and (esperado not in (403, 404) or "Cofrial" in html)      # el 403/404 debe traer el diseño del sitio
            chk(ok, f"{USUARIOS[quien].split('@')[0]} en {ruta}: HTTP {esperado}", f"HTTP {st}")

    titulo("4. IoT y cadena de frío")
    if sesiones["admin"]:
        st, d = sesiones["admin"].json("/api/flota/")
        n = len(d["camiones"]) if d else 0
        if chk(st == 200 and n >= 50, f"La flota tiene {n} camiones (se esperan 50)", f"HTTP {st}"):
            ahora = datetime.datetime.now(datetime.timezone.utc)
            edades, campos_ok, alertas = [], True, []
            for c in d["camiones"]:
                l = c["ultima_lectura"]
                if not l:
                    campos_ok = False
                    continue
                campos_ok &= all(k in l for k in ("temp_camara", "lat", "long", "combustible_pct", "alerta_ruptura_frio"))
                campos_ok &= isinstance(l["temp_camara"], float) and isinstance(l["combustible_pct"], int) and isinstance(l["alerta_ruptura_frio"], bool)
                ts = datetime.datetime.fromisoformat(l["registrado_en"].replace("Z", "+00:00"))
                edades.append((ahora - ts).total_seconds())
                if c["alerta"]:
                    alertas.append(c["camion_id"])
            chk(campos_ok and len(edades) == n, "Los 6 campos exigidos, con sus tipos, en todos los camiones", "falta alguna lectura o campo")
            chk(edades and max(edades) < 60, f"Telemetría fresca: la lectura más vieja tiene {max(edades):.0f} s" if edades else "Telemetría fresca",
                "el simulador IoT no está insertando (revisar la EC2 de IoT)")
            marca("info", "Camiones con ruptura de frío ahora: " + (", ".join(alertas) if alertas else "ninguno (es aleatorio y poco frecuente)"))
        if sesiones["despachador"]:
            chk("Pedidos afectados" in sesiones["despachador"].pedir("/crm/alertas/")[1], "El despachador ve la pantalla de alertas de frío")

    titulo("5. Tablero de BI (Grafana, solo por /bi/ y con rol)")
    st, _, url = anon.pedir("/bi/")
    chk("/cuenta/entrar/" in url, "Sin sesión, /bi/ lleva a la pantalla de entrar", f"terminó en {url}")
    for clave, quien in (("vendedora", "vendedora"), ("despachador", "despachador"), ("hospital", "cliente B2B")):
        if sesiones[clave]:
            chk(sesiones[clave].pedir("/bi/")[0] == 403, f"/bi/ responde 403 al {quien}", "debería negarse a este rol")
    try:                                                # no basta abrir el socket: algunas redes aceptan cualquier conexión TCP; se pide la salud de Grafana
        r = urllib.request.urlopen(f"http://{HOST}:3000/api/health", timeout=6)
        respondio = r.status == 200 and b"database" in r.read(2000)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        respondio = False
    chk(not respondio, "El puerto 3000 de Grafana no está abierto a internet", "Grafana responde: cerrar la regla del Security Group sg-web")
    for clave, quien in (("gerente", "gerencia"), ("admin", "administrador")):
        if not sesiones[clave]:
            continue
        st, cuerpo, _ = sesiones[clave].pedir("/bi/api/health")
        chk(st == 200 and re.search(r'"database":\s*"ok"', cuerpo), f"El tablero abre por /bi/ para {quien} y llega a la base", f"HTTP {st}")
    if sesiones["gerente"]:
        try:
            tablero = json.load(open(os.path.join(RAIZ, "grafana", "dashboards", "cofrial.json")))
            malas, n = [], 0
            for p in tablero["panels"]:
                for t in p.get("targets", []):
                    n += 1
                    if consulta_grafana(sesiones["gerente"], t["rawSql"]).get("error"):
                        malas.append(p["title"])
            chk(not malas, f"Las {n} consultas del tablero responden", "fallan: " + ", ".join(sorted(set(malas))))
            r = consulta_grafana(sesiones["gerente"], "SELECT o.canal AS canal FROM v_orden o JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id "
                                 "WHERE e.nombre <> 'Cancelada' GROUP BY 1")
            v = r["frames"][0]["data"]["values"] if r.get("frames") else []
            canales = sorted(set(v[0])) if v else []
            if {"B2B", "B2C"} <= set(canales):
                marca("ok", "Hay ventas en ambos canales (B2B y B2C)")
            else:
                marca("aviso", "Solo hay ventas en: " + (", ".join(canales) or "ningún canal") + ". Antes de la demo, hacer una compra en el canal que falte.")
        except (OSError, KeyError, ValueError) as e:
            marca("aviso", "No pude revisar las consultas del tablero", str(e)[:80])

    titulo("6. IA: reclamo de prueba (--ia; D5 de la Torre necesita una clasificación registrada)")
    creo_datos = False
    if "--ia" in sys.argv and sesiones["ana"]:
        creo_datos = True
        t = sesiones["ana"].token("/soporte/")
        t1 = time.time()
        st, html, _ = sesiones["ana"].pedir("/soporte/", {"csrfmiddlewaretoken": t, "asunto": "Verificación automática",
                                                          "descripcion": "La carga llegó con la temperatura muy alta y rechazamos las cajas."})
        seg = time.time() - t1
        m = re.search(r"la derivamos a (?:\"|&quot;)([^\"&]+)(?:\"|&quot;)", html)
        chk(m, f"La IA clasificó el reclamo de prueba como \"{m.group(1)}\" en {seg:.1f} s" if m else "La IA clasificó el reclamo de prueba",
            "quedó sin clasificar: revisar las claves de IA (manage.py probar_ia)")
    elif "--ia" not in sys.argv:
        marca("info", "Prueba de IA omitida (crearía un requerimiento). Para incluirla: python3 aws/verificar.py --ia")

    titulo("7. Compra de ensayo (D2 y D4 exigen un pedido real por canal)")
    if COMPRA_ENSAYO:
        creada = False
        for canal, clave in (("B2B", "hospital"), ("B2C", "ana")):
            if not sesiones[clave]:
                marca("mal", f"Compra de ensayo {canal}", "la cuenta no entró")
                continue
            estado, detalle = comprar_ensayo(sesiones[clave], canal)
            if estado == "mp":
                marca("aviso", f"Compra de ensayo {canal}: {detalle}")
            else:
                chk(estado in ("creada", "vigente"), f"Compra de ensayo {canal}: " + {"creada": "pedido creado", "vigente": "ya hay uno vigente (no se repite)"}.get(estado, "falló") + f" {detalle}" * (estado != "error"), detalle)
            creada |= estado == "creada"
        creo_datos |= creada
    else:
        for canal, clave in (("B2B", "hospital"), ("B2C", "ana")):
            if sesiones[clave]:
                vigentes = pedidos_vigentes(sesiones[clave], solo_ensayo=(canal == "B2B"))
                marca("info", f"Pedidos reales de {canal} en {VIGENCIA_ENSAYO_DIAS} días: " + ("no se pudo leer" if vigentes is None else str(len(vigentes))))
        marca("info", "No se hizo compra de ensayo. Para hacerla (crea pedidos reales y descuenta stock): python3 aws/verificar.py --compra-ensayo")

    if creo_datos:
        time.sleep(6)                     # la Torre calcula el pulso con una caché de 5 s: esperar para que vea lo que se acaba de crear
    titulo("8. Torre de control (gerencia; solo lectura)" + (" · modo --defensa: las cinco filas deben estar verificadas" if DEFENSA else ""))
    if sesiones["gerente"]:
        st, html, _ = sesiones["gerente"].pedir("/torre/")
        chk(st == 200 and "Torre de control" in html, "La Torre de control abre para gerencia (/torre/)", f"HTTP {st}")
        t1 = time.perf_counter()
        st, d = sesiones["gerente"].json("/torre/pulso/")
        tiempos = [round((time.perf_counter() - t1) * 1000)]
        filas = d.get("rubrica") if d else None
        if chk(st == 200 and isinstance(filas, list) and len(filas) == 5, "El pulso trae las 5 filas de la rúbrica", f"HTTP {st}"):
            etiqueta = {"verificado": "ok", "sin_evidencia": "aviso", "no_comprobado": "aviso"}
            for f in filas:       # un estado sin evidencia no es falla antes de la demo: todavía no hay ventas ni lecturas reales
                nombre = f"Rúbrica {f.get('dim')} {f.get('titulo')}: {f.get('estado')}"
                if DEFENSA:
                    chk(f.get("estado") == "verificado", nombre, "; ".join(f.get("evidencia") or [])[:240])
                else:
                    marca(etiqueta.get(f.get("estado"), "aviso"), nombre)
            por_dim = {f.get("dim"): f for f in filas}
            d1, d5 = (por_dim.get("D1") or {}).get("evidencia") or [], (por_dim.get("D5") or {}).get("evidencia") or []
            exigir(any(re.fullmatch(r"Instancia EC2: i-[0-9a-f]{8,17}", e) for e in d1), "D1 muestra el ID de la instancia EC2 (Instancia EC2: i-…)",
                   "sin ID: ¿se recreó la web con provision.sh de main? (escribe INSTANCIA_EC2 en el .env)")
            exigir("IA de pago (ANTHROPIC_API_KEY): no configurada" in d5, "D5 sin clave de IA de pago (ANTHROPIC_API_KEY vacía)",
                   "hay una clave de pago activa: vaciar ANTHROPIC_API_KEY en secretos.env y recrear la web")
            if not DEFENSA:
                marca("info", "Un aviso de la rúbrica no hace fallar este verificador: en el punto de decisión usar --defensa")
        for _ in range(3 if DEFENSA else 0):          # varias lecturas espaciadas más que la caché de 5 s: miden el cálculo, no la caché
            time.sleep(6)
            t1 = time.perf_counter()
            sesiones["gerente"].json("/torre/pulso/")
            tiempos.append(round((time.perf_counter() - t1) * 1000))
        exigir(max(tiempos) < PULSO_MAX_MS, f"/torre/pulso/ responde en {max(tiempos)} ms" + (f" (peor de {len(tiempos)} lecturas sin caché)" if len(tiempos) > 1 else ""),
               f"más de {PULSO_MAX_MS} ms: la pantalla marca «Sin conexión» a los 8000 ms; revisar el tamaño de telemetria y el índice de fecha")
    if sesiones["vendedora"]:
        st, _, _ = sesiones["vendedora"].pedir("/torre/")
        chk(st == 403, "La Torre responde 403 a una vendedora (verían clientes fuera de su cartera)", f"HTTP {st}")

    titulo("9. Requerimiento de la demostración y panel de IA")
    if sesiones["vendedor2"]:
        st, html, _ = sesiones["vendedor2"].pedir("/crm/requerimientos/")      # el reclamo es de Supermercados del Sur, cartera de vendedor2; gerencia mira pero no tiene el botón
        fila = fila_del_requerimiento(html, "Mi pedido llegó tibio")
        chk(fila is not None and "sin clasificar</span>" in fila and "Clasificar con IA" in fila,
            "«Mi pedido llegó tibio» está sin clasificar, con el botón \"Clasificar con IA\" (listo para la demo en vivo)",
            "no existe o ya está clasificado: ejecutar en la EC2 web  docker compose -f aws/docker-compose.web.yml --env-file .env exec -T web python manage.py restablecer_demo_ia")
    if sesiones["vendedora"]:
        st, html, _ = sesiones["vendedora"].pedir("/crm/ia/")
        chk(st == 200 and "Panel de IA" in html and "Probar la IA ahora" in html, "El CRM tiene el panel de IA (estado y prueba en vivo)", f"HTTP {st}")

    malos = [r for r in RESULTADOS if r[0] == "mal"]
    print(f"\nResumen: {sum(1 for r in RESULTADOS if r[0] == 'ok')} correctas, {len(malos)} con falla, "
          f"{sum(1 for r in RESULTADOS if r[0] == 'aviso')} avisos ({time.time() - t0:.0f} s).")
    if malos:
        print("FALLAS:")
        for _, n, d in malos:
            print(f"  - {n}" + (f": {d}" if d else ""))
    sys.exit(1 if malos else 0)


if __name__ == "__main__":
    main()
