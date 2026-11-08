"""Lectura del momento: dos o tres frases redactadas por reglas a partir de los datos de la Torre (sin IA)."""

SIN_LECTURAS_S = 120      # más de 2 minutos sin lecturas reales: el simulador parece detenido


def _pesos(monto):
    if monto >= 1_000_000:
        return "$" + f"{monto / 1_000_000:.1f}".replace(".", ",") + " M"
    return "$" + f"{monto:,}".replace(",", ".")


def redactar(ahora):
    frases = []
    seg = ahora["ultima_lectura_seg"]
    al_dia = seg is not None and seg <= SIN_LECTURAS_S
    if seg is None:
        frases.append("Sin lecturas de los camiones todavía.")
    elif not al_dia:
        frases.append(f"Sin lecturas nuevas hace {max(1, seg // 60)} min: el simulador parece detenido.")

    n = ahora["camiones_en_alerta"]
    if n:
        camiones = "1 camión con ruptura de frío" if n == 1 else f"{n} camiones con ruptura de frío"
        frase = f"{camiones} y {_pesos(ahora['riesgo_actual_clp'])} en pedidos en riesgo."
        if ahora["mas_expuesto"]:
            frase += f" El más expuesto es {ahora['mas_expuesto']}."
        frases.append(frase)
    elif al_dia:                                  # sin lecturas al día no se puede afirmar que no hay novedades
        frases.append("Sin novedades en la cadena de frío.")

    ventas = ahora["ventas_24h"]
    total = ventas["B2B"] + ventas["B2C"]
    if total == 0:
        frases.append("Sin ventas en 24 h.")
    else:
        frases.append(f"Las ventas de 24 h van {round(100 * ventas['B2B'] / total)} % institucional.")

    if ahora["simulacion"]:
        frases.append("Hay una simulación en curso: algunas alertas son de demostración.")
    return frases
