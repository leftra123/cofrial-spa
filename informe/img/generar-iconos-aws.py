"""Íconos oficiales de AWS (librería aws4 de draw.io) como PNG sueltos, para usarlos en tablas del informe.

    python3 informe/img/generar-iconos-aws.py
"""
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DRAWIO = "/Applications/draw.io.app/Contents/MacOS/draw.io"
PTS = "points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];"
SERV = "sketch=0;" + PTS + "outlineConnect=0;fontColor=#232F3E;fillColor={c};strokeColor=#ffffff;dashed=0;html=1;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{n};"
RECU = "sketch=0;" + PTS + "outlineConnect=0;fontColor=#232F3E;fillColor={c};strokeColor=none;dashed=0;html=1;aspect=fixed;shape=mxgraph.aws4.{n};"
ICONOS = {
    "ec2": SERV.format(c="#ED7100", n="ec2"),
    "rds": SERV.format(c="#C925D1", n="rds"),
    "igw": RECU.format(c="#8C4FFF", n="internet_gateway"),
    "vpc": RECU.format(c="#8C4FFF", n="vpc_virtual_private_cloud_vpc"),
    "usuarios": RECU.format(c="#232F3D", n="users"),
    "servidor": RECU.format(c="#232F3D", n="traditional_server"),
}


def main():
    destino = RAIZ / "informe/img/iconos"
    destino.mkdir(exist_ok=True)
    for nombre, estilo in ICONOS.items():
        xml = ('<mxfile><diagram id="i" name="i"><mxGraphModel dx="200" dy="200" grid="0" page="1" pageWidth="120" pageHeight="120"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
               f'<mxCell id="n" value="" style="{estilo}" vertex="1" parent="1"><mxGeometry x="10" y="10" width="78" height="78" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>')
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "i.drawio"
            f.write_text(xml, encoding="utf-8")
            subprocess.run([DRAWIO, "-x", "-f", "png", "-s", "2", "-b", "4", "-t", "-o", str(destino / f"{nombre}.png"), str(f)], check=True, capture_output=True)
        print(f"  {nombre}.png")


if __name__ == "__main__":
    main()
