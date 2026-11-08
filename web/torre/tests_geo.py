"""Contornos de la macrozona sur para el mapa de la Torre de control."""
import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RUTA = Path(settings.BASE_DIR) / "static" / "geo" / "macrozona_sur.geojson"
TEMUCO = (-38.7359, -72.5904)
VALDIVIA = (-39.8142, -73.2459)


def _anillos(geometria):
    if geometria["type"] == "Polygon":
        return [geometria["coordinates"]]
    return geometria["coordinates"]


def _punto_en_anillo(lat, lon, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i]
        xj, yj = anillo[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _contiene(geometria, lat, lon):
    for poligono in _anillos(geometria):
        if _punto_en_anillo(lat, lon, poligono[0]) and not any(
            _punto_en_anillo(lat, lon, hueco) for hueco in poligono[1:]
        ):
            return True
    return False


class ContornosMacrozonaTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.datos = json.loads(RUTA.read_text(encoding="utf-8"))
        cls.por_nombre = {f["properties"]["nombre"]: f for f in cls.datos["features"]}

    def test_cuatro_regiones(self):
        self.assertEqual(set(self.por_nombre), {"Biobío", "La Araucanía", "Los Ríos", "Los Lagos"})

    def test_solo_araucania_es_principal(self):
        principales = [n for n, f in self.por_nombre.items() if f["properties"]["principal"] is True]
        self.assertEqual(principales, ["La Araucanía"])

    def test_peso(self):
        self.assertLess(RUTA.stat().st_size, 200 * 1024)

    def test_atribucion_osm(self):
        self.assertIn("OpenStreetMap", self.datos["attribution"])

    def test_temuco_dentro_de_araucania(self):
        self.assertTrue(_contiene(self.por_nombre["La Araucanía"]["geometry"], *TEMUCO))

    def test_valdivia_fuera_de_araucania(self):
        self.assertFalse(_contiene(self.por_nombre["La Araucanía"]["geometry"], *VALDIVIA))
        self.assertTrue(_contiene(self.por_nombre["Los Ríos"]["geometry"], *VALDIVIA))
