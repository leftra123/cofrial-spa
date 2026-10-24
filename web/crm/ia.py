"""Clasificación de requerimientos con IA externa gratuita (RN-14 y CU-09 del informe).

Gemini (free tier) es el proveedor principal y Groq el respaldo. Las claves vienen del entorno
(GEMINI_API_KEY, GROQ_API_KEY) y nunca del código. Solo se usa la biblioteca estándar: sin dependencias nuevas.
Cualquier falla (sin clave, red, tiempo, respuesta inválida) se informa como ErrorIA y el servicio la trata
como «sin clasificar»: un requerimiento nunca se pierde.
"""
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("crm.ia")


_hilo = threading.local()          # modelo que respondió en ESTE hilo (ultimo_modelo es global y con varios hilos se puede cruzar)


def modelo_del_hilo():
    return getattr(_hilo, "modelo", None)


class ErrorIA(Exception):
    """La IA no pudo clasificar; el llamador deja el requerimiento para revisión manual."""


def _presupuesto():
    """Tiempo total (segundos) que se le da a la IA por requerimiento, sumando todos los intentos.
    CU-09 pedía 5 s, pero la latencia medida de Gemini es de 4 a 7 s; con 12 s hay margen y el formulario no se cuelga."""
    return float(os.environ.get("IA_TIMEOUT_SEG", "12"))


def _prompt(asunto, descripcion, categorias):
    lista = "\n".join(f"- {c}" for c in categorias)
    return ("Eres el clasificador de requerimientos de Cofrial SpA, una distribuidora chilena de alimentos "
            "refrigerados y congelados. Clasifica el mensaje de un cliente en UNA de estas categorías:\n"
            f"{lista}\n\n"
            f"Asunto: {asunto}\nMensaje: {descripcion}\n\n"
            'Responde SOLO con JSON: {"categoria": "<nombre exacto de la lista>", "confianza": <número de 0 a 1>}. '
            "La confianza es qué tan seguro estás; usa un valor bajo si el mensaje es ambiguo.")


def _post(url, cuerpo, cabeceras, plazo):
    pedido = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", "User-Agent": "cofrial-crm/1.0", **cabeceras})
    try:
        with urllib.request.urlopen(pedido, timeout=max(1.0, plazo)) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ErrorIA(f"HTTP {e.code}")                      # sin el cuerpo: podría repetir datos de la consulta
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ErrorIA(f"{type(e).__name__}")


# Modelos de Gemini en orden de preferencia (los «lite» son los más livianos). Se pueden cambiar con GEMINI_MODELS
# separados por coma; GEMINI_MODEL (uno solo) sigue funcionando. Si uno está saturado (503) o no existe, se pasa al siguiente.
MODELOS_POR_DEFECTO = "gemini-3.5-flash-lite,gemini-flash-lite-latest,gemini-3.5-flash"
ultimo_modelo = None


def _modelos():
    lista = os.environ.get("GEMINI_MODELS") or os.environ.get("GEMINI_MODEL") or MODELOS_POR_DEFECTO
    return [m.strip() for m in lista.split(",") if m.strip()]


def _texto_de_interaccion(datos):
    """La Interactions API devuelve `steps`; el texto está en los pasos de tipo model_output."""
    partes = [c.get("text", "") for st in datos.get("steps", []) if st.get("type") == "model_output" for c in st.get("content", [])]
    texto = "".join(partes).strip()
    if not texto:
        raise ErrorIA("Gemini respondió sin texto")
    return texto


def _gemini(prompt, plazo_total):
    global ultimo_modelo
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise ErrorIA("GEMINI_API_KEY no está definida")
    inicio, errores = time.monotonic(), []
    for modelo in _modelos():
        restante = plazo_total - (time.monotonic() - inicio)
        if restante < 1:
            errores.append("sin tiempo")
            break
        try:
            datos = _post("https://generativelanguage.googleapis.com/v1beta/interactions",
                          {"model": modelo, "input": prompt, "generation_config": {"thinking_level": "low", "temperature": 0}},
                          {"x-goog-api-key": clave}, restante)
            texto = _texto_de_interaccion(datos)
            ultimo_modelo = _hilo.modelo = "Gemini " + modelo
            return texto
        except ErrorIA as e:
            errores.append(f"{modelo}: {e}")
    raise ErrorIA("; ".join(errores))


# Modelos de Groq en orden de preferencia; configurables con GROQ_MODELS (lista separada por coma) o GROQ_MODEL (uno solo).
GROQ_MODELOS_POR_DEFECTO = "openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.8-27b"


def _modelos_groq():
    lista = os.environ.get("GROQ_MODELS") or os.environ.get("GROQ_MODEL") or GROQ_MODELOS_POR_DEFECTO
    return [m.strip() for m in lista.split(",") if m.strip()]


def _groq(prompt, plazo_total):
    global ultimo_modelo
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        raise ErrorIA("GROQ_API_KEY no está definida")
    inicio, errores = time.monotonic(), []
    for modelo in _modelos_groq():
        restante = plazo_total - (time.monotonic() - inicio)
        if restante < 1:
            errores.append("sin tiempo")
            break
        cuerpo = {"model": modelo, "temperature": 0, "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": prompt}]}
        if "gpt-oss" in modelo or "qwen" in modelo:
            cuerpo["reasoning_effort"] = "low"                   # menos demora: la tarea es clasificar, no razonar
        try:
            datos = _post("https://api.groq.com/openai/v1/chat/completions", cuerpo, {"Authorization": f"Bearer {clave}"}, restante)
            texto = datos["choices"][0]["message"]["content"]
            if not texto or not texto.strip():
                raise ErrorIA("Groq respondió sin texto")
            ultimo_modelo = _hilo.modelo = "Groq " + modelo
            return texto
        except (KeyError, IndexError, TypeError):
            errores.append(f"{modelo}: respuesta sin texto")
        except ErrorIA as e:
            errores.append(f"{modelo}: {e}")
    raise ErrorIA("; ".join(errores))


def _proveedores(orden=None):
    """Orden de los proveedores: IA_PROVEEDORES=groq,gemini lo invierte (Groq responde en ~1 s; Gemini tarda 4 a 7 s). `orden` lo fuerza (lista de nombres)."""
    disponibles = {"gemini": _gemini, "groq": _groq}
    orden = [n.strip().lower() for n in (orden or (os.environ.get("IA_PROVEEDORES") or "gemini,groq").split(","))]
    return [disponibles[n] for n in orden if n in disponibles] or [_gemini, _groq]


# Parte del tiempo restante que puede gastar un proveedor que tiene un respaldo detrás. Sin este tope, un proveedor lento
# (Gemini tarda de 4 a 7 s y a veces se cuelga) agotaba los 12 s y el respaldo nunca llegaba a intentarse.
PARTE_MAXIMA_CON_RESPALDO = 0.65


def _llamar(prompt, plazo=None, orden=None):
    """Prueba los proveedores en orden. Hay un solo presupuesto de tiempo (`plazo`, por defecto el de la clasificación) y se reserva una parte para el respaldo."""
    inicio, errores = time.monotonic(), []
    proveedores = _proveedores(orden)
    for i, proveedor in enumerate(proveedores):
        restante = (plazo or _presupuesto()) - (time.monotonic() - inicio)
        if restante < 1:
            errores.append("sin tiempo")
            break
        tope = restante if i == len(proveedores) - 1 else restante * PARTE_MAXIMA_CON_RESPALDO
        try:
            return proveedor(prompt, tope)
        except ErrorIA as e:
            errores.append(f"{getattr(proveedor, '__name__', 'proveedor')}: {e}")
    raise ErrorIA("; ".join(errores))


def _interpretar(texto, categorias):
    """Del texto del modelo saca (categoría, confianza). Lanza ErrorIA si no se puede interpretar."""
    m = re.search(r"\{.*\}", texto, re.S)                        # tolera texto o ``` alrededor del JSON
    try:
        datos = json.loads(m.group(0))
        nombre = str(datos["categoria"]).strip().lower()
        confianza = max(0.0, min(1.0, float(datos["confianza"])))
    except (AttributeError, ValueError, KeyError, TypeError):
        raise ErrorIA(f"Respuesta no interpretable: {texto[:120]!r}")
    for c in categorias:
        if c.lower() == nombre:
            return c, confianza
    raise ErrorIA(f"Categoría desconocida: {nombre!r}")


def clasificar(asunto, descripcion, categorias):
    """Devuelve (nombre_de_categoria, confianza). Lanza ErrorIA si no hay una respuesta utilizable."""
    return _interpretar(_llamar(_prompt(asunto, descripcion, categorias)), categorias)


def redactar(prompt, plazo=8):
    """Texto libre de la IA (mismos proveedores y respaldo que la clasificación). Lanza ErrorIA si no responde a tiempo."""
    return _llamar(prompt, plazo)


def estado():
    """Configuración visible de la IA para el panel del CRM. Nunca incluye las claves, solo si existen."""
    return {"gemini": bool(os.environ.get("GEMINI_API_KEY")), "groq": bool(os.environ.get("GROQ_API_KEY")),
            "orden": [getattr(f, "__name__", "?").lstrip("_").capitalize() for f in _proveedores()],
            "modelos_gemini": _modelos(), "modelos_groq": _modelos_groq(),
            "presupuesto": _presupuesto(), "parte_con_respaldo": int(PARTE_MAXIMA_CON_RESPALDO * 100)}


def comparar(asunto, descripcion, categorias):
    """Prueba cada proveedor POR SEPARADO con el mismo mensaje, para ver qué recibe y qué responde cada uno.
    Devuelve (prompt, filas); cada fila lleva proveedor, modelo, resultado o error y los segundos que tardó."""
    global ultimo_modelo
    prompt = _prompt(asunto, descripcion, categorias)
    filas = []
    for nombre, proveedor in (("Gemini", _gemini), ("Groq", _groq)):
        fila, ultimo_modelo, inicio = {"proveedor": nombre, "ok": False}, None, time.monotonic()
        try:
            texto = proveedor(prompt, _presupuesto())
            fila["modelo"], fila["respuesta"] = (ultimo_modelo or "").split(" ", 1)[-1], texto.strip()[:300]
            fila["categoria"], fila["confianza"] = _interpretar(texto, categorias)
            fila["ok"] = True
        except ErrorIA as e:
            fila["error"] = str(e)[:300]
        fila["segundos"] = round(time.monotonic() - inicio, 1)
        filas.append(fila)
    return prompt, filas
