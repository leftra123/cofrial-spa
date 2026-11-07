"""El cliente ve solo su tramo: del camión a su parada. Nunca la ruta completa del viaje ni la parada de otro cliente."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model

from catalogo.models import Producto
from flota import rutas, servicios as flota
from flota.models import Telemetria
from pedidos import servicios as s

from .tests_entrega import CLAVE, EntregaBase


def calle_falsa(puntos):
    """Sustituye a OSRM: una polilínea «por calles» con 6 vértices intermedios entre cada par de puntos (pasa exacto por cada parada)."""
    linea = []
    for (a, b), (c, d) in zip(puntos, puntos[1:]):
        linea += [[a + (c - a) * k / 7, b + (d - b) * k / 7] for k in range(7)]
    return linea + [list(puntos[-1])]


def redondeado(p):
    return (round(p[0], 6), round(p[1], 6))


def puntos_de(respuesta):
    """Todas las coordenadas de la respuesta (línea y parada), para buscar una ajena en cualquier parte."""
    return {redondeado(p) for p in respuesta["puntos"]} | {redondeado((respuesta["parada"]["lat"], respuesta["parada"]["long"]))}


class ViajeDeDosClientesBase(EntregaBase):
    """Ayudas para armar un viaje con dos clientes (la usan las pruebas de ruta y de itinerario)."""

    def viaje_de_dos_clientes(self, osrm=None):
        """Ana (B2C) y el hospital (B2B) en el mismo camión. Devuelve (despacho, [(cliente, orden, parada)]) en el orden en que el viaje los visita."""
        usuarios, pedidos = get_user_model().objects, []
        for username in ("ana@correo.test", "abastecimiento@hospital.test"):
            cliente = s.cliente_de(usuarios.get(username=username))
            s.agregar(cliente, Producto.objects.get(sku="VAC-LOM-5K").pk, 1)
            pedidos.append((cliente, s.generar_ordenes(cliente, cliente.direccion_set.first().pk)[0]))
        camion = next(c for c in flota.camiones_libres() if c.rango_temperatura.nombre == flota.rangos_de(pedidos[0][1])[0])
        with patch.object(rutas, "_pedir_osrm", osrm or (lambda puntos: None)):
            despacho = flota.despachar(camion.camion_id, [o.pk for _, o in pedidos])
        despacho.refresh_from_db()
        marcas = despacho.ruta_geojson["paradas"]
        self.assertEqual(len(marcas), 2, "el viaje debe llevar a los dos clientes")
        por_direccion = {m["direccion_id"]: (m["lat"], m["long"]) for m in marcas}
        orden_de_visita = [m["direccion_id"] for m in marcas]
        pedidos.sort(key=lambda par: orden_de_visita.index(par[1].direccion_id))
        return despacho, [(c, o, por_direccion[o.direccion_id]) for c, o in pedidos]

    def poner_camion(self, despacho, posicion):
        Telemetria.objects.create(camion=despacho.camion, temp_camara=2.0, lat=posicion[0], long=posicion[1], combustible_pct=80, alerta_ruptura_frio=False)

    def pedir_ruta(self, cliente, orden):
        self.client.logout()
        self.assertTrue(self.client.login(username=cliente.usuario.username, password=CLAVE))
        r = self.client.get(f"/api/pedidos/{orden.pk}/ruta/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    @staticmethod
    def punto_medio(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)



class RutaSoloDelClienteTests(ViajeDeDosClientesBase):
    def test_con_dos_clientes_nadie_recibe_la_parada_ni_los_puntos_del_otro(self):
        """El caso de la prueba en vivo: un viaje con 2 paradas. Con la línea recta de respaldo, la polilínea completa lleva ambas paradas."""
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.assertEqual(sum(1 for pt in despacho.ruta_geojson["puntos"] if redondeado(pt) in (redondeado(p1), redondeado(p2))), 2)    # base->p1->p2->base: la completa trae las dos paradas
        self.poner_camion(despacho, (settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"]))
        r1, r2 = self.pedir_ruta(c1, o1), self.pedir_ruta(c2, o2)
        self.assertNotIn(redondeado(p2), puntos_de(r1))                       # quien recibe primero no ve la parada del segundo
        self.assertNotIn(redondeado(p1), puntos_de(r2))                       # y el segundo no ve la del primero, aunque el camión pase antes por ahí
        self.assertEqual(redondeado((r1["parada"]["lat"], r1["parada"]["long"])), redondeado(p1))
        self.assertEqual(redondeado((r2["parada"]["lat"], r2["parada"]["long"])), redondeado(p2))
        for r in (r1, r2):
            self.assertEqual(redondeado(r["puntos"][-1]), redondeado((r["parada"]["lat"], r["parada"]["long"])))     # la línea termina en la parada propia
            self.assertNotIn("paradas", r)                                    # no hay lista de paradas del viaje

    def test_la_respuesta_nunca_es_la_polilinea_completa(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes(calle_falsa)
        completa = despacho.ruta_geojson["puntos"]
        self.poner_camion(despacho, self.punto_medio((settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"]), p1))
        for c, o in ((c1, o1), (c2, o2)):
            self.assertLess(len(self.pedir_ruta(c, o)["puntos"]), len(completa))

    def test_el_primero_recibe_el_tramo_por_calles_hasta_su_parada_y_el_segundo_una_recta(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes(calle_falsa)
        camion = self.punto_medio((settings.BASE_LOGISTICA["lat"], settings.BASE_LOGISTICA["long"]), p1)
        self.poner_camion(despacho, camion)
        r1, r2 = self.pedir_ruta(c1, o1), self.pedir_ruta(c2, o2)
        self.assertFalse(r1["aproximada"])
        self.assertGreater(len(r1["puntos"]), 2)                              # sigue las calles hasta su parada
        self.assertEqual(redondeado(r1["puntos"][0]), redondeado(camion))     # y parte de donde está el camión
        self.assertNotIn(redondeado(p2), puntos_de(r1))
        # el segundo debe esperar a que el camión pase por la casa del primero: un trazo por calles delataría esa parada, así que es recto y aproximado
        self.assertTrue(r2["aproximada"])
        self.assertEqual([redondeado(p) for p in r2["puntos"]], [redondeado(camion), redondeado(p2)])
        self.assertNotIn(redondeado(p1), puntos_de(r2))

    def test_pasada_la_primera_parada_el_segundo_recibe_el_tramo_por_calles_sin_lo_anterior(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes(calle_falsa)
        camion = self.punto_medio(p1, p2)
        self.poner_camion(despacho, camion)
        r2 = self.pedir_ruta(c2, o2)
        self.assertFalse(r2["aproximada"])
        self.assertGreater(len(r2["puntos"]), 2)
        self.assertEqual(redondeado(r2["puntos"][0]), redondeado(camion))
        self.assertEqual(redondeado(r2["puntos"][-1]), redondeado(p2))
        self.assertNotIn(redondeado(p1), puntos_de(r2))                       # lo ya recorrido (y la casa del primero) no viaja
        self.assertLess(len(r2["puntos"]), len(despacho.ruta_geojson["puntos"]) / 2)

    def test_un_cliente_no_pide_la_ruta_de_la_orden_de_otro(self):
        despacho, ((c1, o1, p1), (c2, o2, p2)) = self.viaje_de_dos_clientes()
        self.poner_camion(despacho, p1)
        self.client.logout()
        self.assertTrue(self.client.login(username=c1.usuario.username, password=CLAVE))
        self.assertEqual(self.client.get(f"/api/pedidos/{o2.pk}/ruta/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/pedidos/{o1.pk}/ruta/").status_code, 200)
