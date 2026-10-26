"""Regenera la topología vigente PNG y draw.io con una fuente común."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("generar-figuras-vigentes.py")))["arquitectura"]()
