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
import urllib.error
import urllib.request

log = logging.getLogger("crm.ia")


class ErrorIA(Exception):
    """La IA no pudo clasificar; el llamador deja el requerimiento para revisión manual."""


def _timeout():
    return float(os.environ.get("IA_TIMEOUT_SEG", "5"))      # CU-09: sin respuesta en 5 s -> «sin clasificar»


def _prompt(asunto, descripcion, categorias):
    lista = "\n".join(f"- {c}" for c in categorias)
    return ("Eres el clasificador de requerimientos de Cofrial SpA, una distribuidora chilena de alimentos "
            "refrigerados y congelados. Clasifica el mensaje de un cliente en UNA de estas categorías:\n"
            f"{lista}\n\n"
            f"Asunto: {asunto}\nMensaje: {descripcion}\n\n"
            'Responde SOLO con JSON: {"categoria": "<nombre exacto de la lista>", "confianza": <número de 0 a 1>}. '
            "La confianza es qué tan seguro estás; usa un valor bajo si el mensaje es ambiguo.")


def _post(url, cuerpo, cabeceras):
    pedido = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", **cabeceras})
    try:
        with urllib.request.urlopen(pedido, timeout=_timeout()) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ErrorIA(f"{type(e).__name__}: {e}")


def _gemini(prompt):
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise ErrorIA("GEMINI_API_KEY no está definida")
    modelo = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    datos = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                  {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                  {"x-goog-api-key": clave})
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise ErrorIA("Gemini respondió sin texto")


def _groq(prompt):
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        raise ErrorIA("GROQ_API_KEY no está definida")
    datos = _post("https://api.groq.com/openai/v1/chat/completions",
                  {"model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), "temperature": 0,
                   "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]},
                  {"Authorization": f"Bearer {clave}"})
    try:
        return datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ErrorIA("Groq respondió sin texto")


def _llamar(prompt):
    """Gemini primero; si falla, Groq. Devuelve el texto crudo del modelo."""
    errores = []
    for proveedor in (_gemini, _groq):
        try:
            return proveedor(prompt)
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
