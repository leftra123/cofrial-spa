"""El «antes» de la Torre: lo que el caso describe y el equipo reconstruye. Nada de esto sale de la base ni son datos de Cofrial."""

# Un día de coordinación por llamadas y WhatsApp personales (hora, canal, texto), con voces genéricas: se pierde un pedido y una ruptura de frío pasa inadvertida.
REGISTRO = [
    ("07:40", "Llamada, Ventas", "El hospital pide 40 cajas. Lo anoto en un papel y lo paso a la planilla después."),
    ("08:25", "WhatsApp, Bodega", "¿Quién tiene el pedido del hospital? En la planilla no aparece."),
    ("10:10", "WhatsApp, Chofer CAM-12", "Voy saliendo. El termómetro marca raro; lo reviso a la vuelta."),
    ("12:50", "Llamada, Cliente", "Mi pedido no ha llegado. ¿En qué camión viene? Nadie sabe decirme."),
    ("15:30", "WhatsApp, Chofer CAM-12", "Entregué en la feria. La carga venía blanda, pero la recibieron igual."),
    ("18:15", "Planilla, Administración", "Se cierra el día: falta un pedido y nadie anotó la temperatura del CAM-12."),
]

# Tablas 5 y 6 de informe/01-diagnostico.md. Los 15 min de coordinación por viaje son un supuesto nuevo del equipo.
SUPUESTOS = {
    "merma_bajo_mm": 13.5,
    "merma_base_mm": 22.5,
    "merma_alto_mm": 36,
    "viajes_semana": 300,
    "min_coordinacion": 15,
    "horas_semana": 75,
}
