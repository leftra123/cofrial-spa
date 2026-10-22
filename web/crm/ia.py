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
import time
import urllib.error
import urllib.request

log = logging.getLogger("crm.ia")


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
    pedido = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", **cabeceras})
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
            ultimo_modelo = modelo
            return texto
        except ErrorIA as e:
            errores.append(f"{modelo}: {e}")
    raise ErrorIA("; ".join(errores))


def _groq(prompt, plazo_total):
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        raise ErrorIA("GROQ_API_KEY no está definida")
    datos = _post("https://api.groq.com/openai/v1/chat/completions",
                  {"model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), "temperature": 0,
                   "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]},
                  {"Authorization": f"Bearer {clave}"}, plazo_total)
    try:
        return datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ErrorIA("Groq respondió sin texto")


def _llamar(prompt):
    """Gemini primero; si falla, Groq. El presupuesto de tiempo es uno solo para todos los intentos."""
    inicio, errores = time.monotonic(), []
    for proveedor in (_gemini, _groq):
        restante = _presupuesto() - (time.monotonic() - inicio)
        if restante < 1:
            errores.append("sin tiempo")
            break
        try:
            return proveedor(prompt, restante)
        except ErrorIA as e:
            errores.append(f"{proveedor.__name__}: {e}")
    raise ErrorIA("; ".join(errores))


def clasificar(asunto, descripcion, categorias):
    """Devuelve (nombre_de_categoria, confianza). Lanza ErrorIA si no hay una respuesta utilizable."""
    texto = _llamar(_prompt(asunto, descripcion, categorias))
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
