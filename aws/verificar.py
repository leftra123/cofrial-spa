#!/usr/bin/env python3
"""Verificación de punta a punta de la instalación de Cofrial en AWS. Solo lee (no crea datos) salvo con --ia.

    python3 aws/verificar.py                 # usa la IP de aws/.estado/ip.txt o la variable COFRIAL_URL
    python3 aws/verificar.py http://IP       # o una dirección explícita
    python3 aws/verificar.py --ia            # además envía un reclamo de prueba por Soporte y comprueba la clasificación

Las claves se toman de DEMO_PASSWORD, ADMIN_PASSWORD y GRAFANA_VISOR_PASSWORD (variables o aws/.estado/secretos.env); no se imprimen.
Solo usa la biblioteca estándar de Python (sin instalar nada). Sale con código 0 si todo pasó y 1 si algo falló.
"""
import base64
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
ADMINISTRADORES = ("admin@cofrial.cl", "eric@cofrial.cl")


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

    def token(self, ruta):
        _, html, _ = self.pedir(ruta)
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        return m.group(1) if m else ""

    def entrar(self, usuario):
        t = self.token("/cuenta/entrar/")
        st, html, url = self.pedir("/cuenta/entrar/", {"csrfmiddlewaretoken": t, "username": usuario, "password": CLAVE_ADMIN if usuario in ADMINISTRADORES else CLAVE, "next": "/"})
        return st == 200 and "/cuenta/salir/" in html          # el formulario de salida solo aparece con sesión iniciada

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


def consulta_grafana(sql):
    sql = sql.replace("$camion", "'CAM-01'")           # variable del selector de camiones del tablero: aquí se prueba con uno
    cuerpo = json.dumps({"queries": [{"refId": "A", "datasource": {"uid": "cofrial-pg"}, "rawSql": sql, "format": "table"}],
                         "from": "now-24h", "to": "now"}).encode()
    cabeceras = {"Content-Type": "application/json"}
    clave = os.environ.get("GRAFANA_VISOR_PASSWORD") or leer_estado("GRAFANA_VISOR_PASSWORD")
    if clave:                                          # Grafana ya no admite acceso anónimo: se consulta con la cuenta visor
        cabeceras["Authorization"] = "Basic " + base64.b64encode(f"visor:{clave}".encode()).decode()
    pedido = urllib.request.Request(f"http://{HOST}:3000/api/ds/query", data=cuerpo, headers=cabeceras)
    try:
        return json.loads(urllib.request.urlopen(pedido, timeout=30).read())["results"]["A"]
    except urllib.error.HTTPError as e:
        return json.loads(e.read())["results"]["A"]


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
        print("\nHay cuentas que no entran: revisar las claves (DEMO_PASSWORD, ADMIN_PASSWORD o la que se cambió desde la cuenta).")

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

    titulo("5. Tablero de BI (Grafana)")
    gb = Sesion()
    st, cuerpo, _ = gb.pedir("/api/health", base=f"http://{HOST}:3000")
    if chk(st == 200 and re.search(r'"database":\s*"ok"', cuerpo), "Grafana responde y llega a la base", f"HTTP {st}"):
        try:
            tablero = json.load(open(os.path.join(RAIZ, "grafana", "dashboards", "cofrial.json")))
            malas, n = [], 0
            for p in tablero["panels"]:
                for t in p.get("targets", []):
                    n += 1
                    if consulta_grafana(t["rawSql"]).get("error"):
                        malas.append(p["title"])
            chk(not malas, f"Las {n} consultas del tablero responden", "fallan: " + ", ".join(sorted(set(malas))))
            r = consulta_grafana("SELECT o.canal AS canal FROM v_orden o JOIN estado_orden e ON e.estado_orden_id = o.estado_orden_id "
                                 "WHERE e.nombre <> 'Cancelada' GROUP BY 1")
            v = r["frames"][0]["data"]["values"] if r.get("frames") else []
            canales = sorted(set(v[0])) if v else []
            if {"B2B", "B2C"} <= set(canales):
                marca("ok", "Hay ventas en ambos canales (B2B y B2C)")
            else:
                marca("aviso", "Solo hay ventas en: " + (", ".join(canales) or "ningún canal") + ". Antes de la demo, hacer una compra en el canal que falte.")
        except (OSError, KeyError, ValueError) as e:
            marca("aviso", "No pude revisar las consultas del tablero", str(e)[:80])

    titulo("6. CRM e IA")
    if sesiones["vendedora"]:
        st, html, _ = sesiones["vendedora"].pedir("/crm/requerimientos/")
        sin = html.count("sin clasificar")
        if sin:
            marca("ok", f"Hay {sin} requerimiento(s) sin clasificar con el botón \"Clasificar con IA\" (listo para la demo en vivo)")
        else:
            marca("aviso", "No queda ningún requerimiento sin clasificar: la demostración en vivo de la IA necesita uno")
    if sesiones["vendedora"]:
        st, html, _ = sesiones["vendedora"].pedir("/crm/ia/")
        chk(st == 200 and "Panel de IA" in html and "Probar la IA ahora" in html, "El CRM tiene el panel de IA (estado y prueba en vivo)", f"HTTP {st}")
    if "--ia" in sys.argv and sesiones["ana"]:
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
