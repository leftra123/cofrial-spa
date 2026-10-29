"""Cuentas de demostración y la clave propia de cada una.

Cada cuenta tiene una clave distinta que se deriva de DEMO_PASSWORD (o ADMIN_PASSWORD para las administradoras) y del nombre de
usuario. No hay que guardar una variable por cuenta: la web la aplica al arrancar (cargar_demo) y la hoja para entregar se calcula
desde el mismo .env, sin entrar a la máquina. Este archivo no usa Django para poder ejecutarse solo:

    python3 web/clientes/cuentas_demo.py --env .env --url http://localhost:8000 --salida hoja-cuentas.md
    python3 web/clientes/cuentas_demo.py --env aws/.estado/secretos.env --url http://IP --salida aws/.estado/hoja-cuentas.md

La hoja trae claves reales: no se sube a git (hoja-cuentas*.md está en .gitignore) ni se pega en el chat o en Trello.
"""
import argparse
import hashlib
import hmac
import os
import sys

ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"      # sin 0/o, 1/l/i: se dicta y se copia sin confusiones

# usuario, perfil, qué muestra. El orden es el de la hoja.
CUENTAS = [
    ("ana@correo.test", "Cliente particular (B2C)", "Precio público, carrito, Mis pedidos, Soporte con IA"),
    ("abastecimiento@hospital.test", "Cliente institucional (B2B)", "Precio institucional, orden de compra"),
    ("felipe@cofrial.cl", "Cliente institucional (B2B)", "Segunda cuenta de empresa para comprar en la demostración"),
    ("sergio@cofrial.cl", "Cliente particular (B2C)", "Segunda cuenta particular para comprar en la demostración"),
    ("vendedora@cofrial.cl", "Vendedora (cartera: Hospital)", "CRM, embudo, ficha del cliente, solicitudes de empresas"),
    ("vendedor2@cofrial.cl", "Vendedor (cartera: Supermercados del Sur)", "No ve la cartera de la otra vendedora"),
    ("gerencia@cofrial.cl", "Gerencia", "Lee todo el CRM y el panel de ventas; no modifica"),
    ("despacho@cofrial.cl", "Despachador", "Flota en vivo, alertas de frío y despachos"),
    ("admin@cofrial.cl", "Administrador", "Todo, incluida la administración de Django"),
    ("eric@cofrial.cl", "Administrador (equipo)", "Cuenta de Eric para operar la demostración"),
]
USUARIOS = [c[0] for c in CUENTAS]
ADMINISTRADORES = ("admin@cofrial.cl", "eric@cofrial.cl")


def clave_de(usuario, base):
    """Clave de 12 caracteres en tres grupos (p. ej. «k7mq-2xfp-9ra3»), siempre la misma para el mismo usuario y la misma base."""
    n = int.from_bytes(hmac.new(base.encode(), usuario.lower().encode(), hashlib.sha256).digest(), "big")
    letras = []
    for _ in range(12):
        n, r = divmod(n, len(ALFABETO))
        letras.append(ALFABETO[r])
    return "-".join("".join(letras[i:i + 4]) for i in (0, 4, 8))


def base_de(usuario, clave_demo, clave_admin=None):
    """La base de la que sale la clave: ADMIN_PASSWORD para las administradoras (si está definida), DEMO_PASSWORD para el resto."""
    return (clave_admin or clave_demo) if usuario in ADMINISTRADORES else clave_demo


def claves(clave_demo, clave_admin=None):
    return {u: clave_de(u, base_de(u, clave_demo, clave_admin)) for u in USUARIOS}


def hoja(clave_demo, clave_admin=None, url="http://IP"):
    """Hoja en Markdown para entregar al profesor: cuentas, claves y cómo crear o recuperar una cuenta."""
    c = claves(clave_demo, clave_admin)
    filas = "\n".join(f"| `{u}` | {perfil} | `{c[u]}` | {que} |" for u, perfil, que in CUENTAS)
    return f"""# Cofrial SpA: cuentas de prueba

Dirección: {url}

| Usuario | Perfil | Clave | Qué muestra |
|---|---|---|---|
{filas}

## Crear una cuenta propia
- **Particular:** {url}/cuenta/registro/ (queda lista para comprar de inmediato).
- **Empresa:** {url}/cuenta/registro/empresa/ (queda pendiente hasta que ventas la apruebe en el CRM, en «Solicitudes»;
  se puede aprobar entrando como `vendedora@cofrial.cl`).

## Si se olvida la clave
En {url}/cuenta/entrar/, «¿Olvidaste tu clave?»: llega un enlace de un solo uso al correo de la cuenta. Las cuentas de esta
tabla usan correos ficticios (.test y @cofrial.cl) y no reciben correo; para probar la recuperación, crear una cuenta con un
correo real. Cada persona puede cambiar su clave en «Cambiar mi clave»; una clave cambiada no se vuelve a pisar.
"""


def leer_env(ruta):
    valores = {}
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                valores[k.strip()] = v.strip().strip("'\"")
    return valores


def main(argv=None):
    p = argparse.ArgumentParser(description="Genera la hoja de cuentas de prueba con la clave de cada una.")
    p.add_argument("--env", help="archivo .env de donde leer DEMO_PASSWORD y ADMIN_PASSWORD (si no, se usan las variables de entorno)")
    p.add_argument("--url", default="http://IP", help="dirección de la aplicación que aparece en la hoja")
    p.add_argument("--salida", help="archivo donde escribir la hoja (si no, se muestra en pantalla)")
    a = p.parse_args(argv)
    fuente = leer_env(a.env) if a.env else os.environ
    if not fuente.get("DEMO_PASSWORD"):
        sys.exit("Falta DEMO_PASSWORD (en el .env indicado o en las variables de entorno).")
    texto = hoja(fuente["DEMO_PASSWORD"], fuente.get("ADMIN_PASSWORD"), a.url.rstrip("/"))
    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as f:
            f.write(texto)
        os.chmod(a.salida, 0o600)
        print(f"Hoja escrita en {a.salida} (contiene claves: no subirla a git ni compartirla por chat).")
    else:
        print(texto)


if __name__ == "__main__":
    main()
