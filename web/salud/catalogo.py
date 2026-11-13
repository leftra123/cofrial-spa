"""Qué se vigila y cómo se agrupa en la página. Una sola lista: el comando, la página y las pruebas leen de aquí.

`cada` = cada cuántos segundos se revisa (lo que cuesta cuota o sale a internet se revisa menos seguido).
`modo` del grupo: «peor» = el grupo está tan mal como su peor componente; «respaldo» = los componentes se reemplazan entre sí
(Gemini y Groq): con uno caído el grupo está degradado y solo está caído cuando caen todos."""
INTERNO, EXTERNO = 60, 300

GRUPOS = [
    {"id": "web", "nombre": "Aplicación web", "modo": "peor",
     "descripcion": "Tienda, CRM, flota y torre de control.",
     "componentes": [("web", "Sitio web (este servidor)", INTERNO), ("publico", "Dirección pública (balanceador)", INTERNO)]},
    {"id": "datos", "nombre": "Base de datos", "modo": "peor",
     "descripcion": "PostgreSQL (RDS en AWS): pedidos, clientes y telemetría.",
     "componentes": [("base", "PostgreSQL", INTERNO)]},
    {"id": "ia", "nombre": "Asistente de IA", "modo": "respaldo",
     "descripcion": "Asistente de la tienda y clasificación de requerimientos. Gemini es el principal y Groq el respaldo.",
     "componentes": [("gemini", "Gemini (principal)", EXTERNO), ("groq", "Groq (respaldo)", EXTERNO)]},
    {"id": "pagos", "nombre": "Pagos", "modo": "peor",
     "descripcion": "Cobro con tarjeta de los clientes B2C.",
     "componentes": [("mercadopago", "Mercado Pago", EXTERNO)]},
    {"id": "iot", "nombre": "Simulación IoT", "modo": "peor",
     "descripcion": "Camiones simulados que insertan telemetría en la base.",
     "componentes": [("iot", "Lecturas de telemetría", INTERNO)]},
    {"id": "bi", "nombre": "Panel BI", "modo": "peor",
     "descripcion": "Grafana: ventas por canal y alertas de ruptura de frío.",
     "componentes": [("grafana", "Grafana", INTERNO)]},
]

NOMBRES = {clave: nombre for g in GRUPOS for clave, nombre, _ in g["componentes"]}
CADA = {clave: cada for g in GRUPOS for clave, _, cada in g["componentes"]}
