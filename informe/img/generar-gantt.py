"""Carta Gantt del proyecto, generada desde la tabla de cronograma de informe/07-metodologia-cronograma.md.

Se dibuja como HTML y se captura con Google Chrome sin interfaz:

    python3 informe/img/generar-gantt.py
"""
import re
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MESES = {"oct": 10, "nov": 11}
COLOR = {"Eric": "#4a6fa5", "Sergio": "#2e8b57", "Ambos": "#b8860b"}
INICIO, FIN = date(2026, 10, 12), date(2026, 11, 13)
DIA, ETIQ, FILA = 24, 400, 28


def leer_cronograma():
    texto = (RAIZ / "informe/07-metodologia-cronograma.md").read_text(encoding="utf-8")
    bloque = texto[texto.index("## Cronograma"):texto.index("## Equipo y matriz RACI")]
    filas = []
    for linea in bloque.splitlines():
        c = [x.strip() for x in linea.strip().strip("|").split("|")]
        if len(c) == 5 and re.match(r"^\d+-(oct|nov)$", c[2]):
            f = lambda s: date(2026, MESES[s.split("-")[1]], int(s.split("-")[0]))
            filas.append((c[0], c[1], f(c[2]), f(c[3])))
    return filas


def html(filas):
    dias = (FIN - INICIO).days + 1
    ancho = dias * DIA
    cab = ""
    for i in range(dias):
        d = INICIO + timedelta(days=i)
        fin_sem = d.weekday() >= 5
        cab += f'<div class="d{" fs" if fin_sem else ""}" style="left:{i * DIA}px">{d.day}</div>'
    meses = (f'<div class="m" style="left:0;width:{(date(2026, 11, 1) - INICIO).days * DIA}px">Octubre 2026</div>'
             f'<div class="m" style="left:{(date(2026, 11, 1) - INICIO).days * DIA}px;width:{(FIN - date(2026, 11, 1)).days * DIA + DIA}px">Noviembre 2026</div>')
    fondo = "".join(f'<div class="fs-col" style="left:{i * DIA}px"></div>' for i in range(dias) if (INICIO + timedelta(days=i)).weekday() >= 5)
    filas_html = ""
    for k, (act, resp, ini, fin) in enumerate(filas):
        x = (ini - INICIO).days * DIA
        w = ((fin - ini).days + 1) * DIA
        filas_html += (f'<div class="et" style="top:{k * FILA}px">{act}</div>'
                       f'<div class="b" style="left:{x}px;top:{k * FILA + 5}px;width:{w}px;background:{COLOR[resp]}"></div>')
    hitos = ""
    for f, t in ((date(2026, 11, 4), "Hito 1 · 4-nov"), (date(2026, 11, 12), "Hito 2 · 12-nov")):
        x = (f - INICIO).days * DIA + DIA // 2
        hitos += f'<div class="h" style="left:{x}px;height:{len(filas) * FILA}px"></div><div class="ht" style="left:{x - 50}px">{t}</div>'
    leyenda = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in COLOR.items())
    alto_graf = len(filas) * FILA
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font-family:"Times New Roman",serif;color:#222}}
.w{{position:relative;width:{ETIQ + ancho + 20}px;padding:16px 10px 10px}}
.cab{{position:relative;height:44px;margin-left:{ETIQ}px;width:{ancho}px}}
.m{{position:absolute;top:0;height:20px;text-align:center;font-weight:bold;font-size:13px;border-bottom:1px solid #999}}
.d{{position:absolute;top:24px;width:{DIA}px;text-align:center;font-size:11px}}.fs{{color:#999}}
.g{{position:relative;margin-left:{ETIQ}px;width:{ancho}px;height:{alto_graf}px;border-top:1px solid #999;border-bottom:1px solid #999}}
.fs-col{{position:absolute;top:0;bottom:0;width:{DIA}px;background:#f3f4f6}}
.et{{position:absolute;left:-{ETIQ}px;width:{ETIQ - 10}px;height:{FILA}px;line-height:{FILA}px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}}
.b{{position:absolute;height:{FILA - 10}px;border-radius:2px}}
.h{{position:absolute;top:0;width:0;border-left:2px dashed #c0392b}}.ht{{position:absolute;top:{alto_graf + 4}px;width:100px;text-align:center;font-size:11px;font-weight:bold;color:#c0392b}}
.ley{{margin:30px 0 0 {ETIQ}px;font-size:12px;display:flex;gap:22px}}.ley i{{display:inline-block;width:14px;height:10px;margin-right:6px}}
</style><div class="w"><div class="cab">{meses}{cab}</div><div class="g">{fondo}{filas_html}{hitos}</div><div class="ley">{leyenda}</div></div>"""


def main():
    filas = leer_cronograma()
    ancho = ETIQ + (FIN - INICIO).days * DIA + DIA + 40
    alto = len(filas) * FILA + 150
    destino = RAIZ / "informe/img/gantt.png"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "g.html"
        f.write_text(html(filas), encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={ancho},{alto}",
                        "--force-device-scale-factor=2", f"--screenshot={destino}", f"file://{f}"], check=True, capture_output=True)
    print(f"{len(filas)} actividades -> {destino.name}")


if __name__ == "__main__":
    main()
