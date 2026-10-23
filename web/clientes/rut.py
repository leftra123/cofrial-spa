"""RUT chileno: validación del dígito verificador (módulo 11) y formato con puntos y guion."""
import re


def limpiar(rut):
    return re.sub(r"[^0-9kK]", "", rut or "").upper()


def digito_verificador(cuerpo):
    suma, factor = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return "0" if resto == 11 else "K" if resto == 10 else str(resto)


def es_valido(rut):
    r = limpiar(rut)
    return len(r) >= 8 and r[:-1].isdigit() and digito_verificador(r[:-1]) == r[-1]


def formatear(rut):
    r = limpiar(rut)
    cuerpo, dv = r[:-1], r[-1]
    return f"{int(cuerpo):,}".replace(",", ".") + "-" + dv
