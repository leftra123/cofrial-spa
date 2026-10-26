"""Regenera la carta Gantt vigente desde el cronograma Markdown (Pillow)."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("generar-figuras-vigentes.py")))["gantt"]()
