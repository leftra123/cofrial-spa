# Plan de construcción y despliegue en AWS

> **Estado al 22-oct-2026.** Los pasos 1 a 7 de la Tabla 2 se ejecutaron antes de lo planificado y el sistema está desplegado y verificado de punta a punta en AWS Academy. Lo construido y sus diferencias con el diseño están en la Tabla 3 de `03-arquitectura-cloud.md` y en `09-verificacion-pauta.md`. Quedan el guion de la demostración y el ensayo del apagado y encendido del laboratorio.

> Une el diseño con lo que se construirá en el Hito 2. Cada componente del diagrama de arquitectura tiene aquí su criterio de aceptación.

## Qué significa "funcional"

El Hito 2 no se cumple con una versión parcial. Para el equipo, el sistema está funcional cuando todo el ecosistema corre en AWS Academy, conectado entre sí y accesible desde un navegador, sin depender de ningún computador del equipo. Un cliente compra, la orden aparece en el CRM, los camiones envían telemetría, una ruptura de frío se ve en el tablero y la IA clasifica un requerimiento, todo en vivo y en una sola demostración.

## Qué se construye y cómo se comprueba

**Tabla 1**
*Componentes del sistema, dónde corren en AWS y criterio de aceptación*

| Componente | Dónde corre | Criterio de aceptación |
|---|---|---|
| Red y seguridad | VPC `10.0.0.0/16`, cuatro subredes, Internet Gateway y tres Security Groups | RDS no responde desde internet; la EC2 web sí responde en el puerto 80 |
| Base de datos | RDS PostgreSQL en la subred privada, con el esquema de las 25 tablas y datos de prueba | La aplicación y el nodo IoT se conectan; las consultas del tablero devuelven los montos esperados |
| Aplicación web | EC2 web: Django con gunicorn y nginx, en Docker Compose con reinicio automático | Catálogo, carrito y orden funcionan para B2B y B2C; la orden queda en la base de datos |
| CRM | La misma aplicación Django, con el panel de administración y las vistas del vendedor | Un prospecto avanza de etapa; una orden web aparece en la ficha del cliente |
| Simulación IoT | EC2 dedicada: un contenedor Docker por camión, imagen para x86 | Cada contenedor inserta lecturas con los seis campos de la pauta, sin inserciones manuales |
| Tablero de BI | Grafana en Docker, en la EC2 web, leyendo RDS en vivo | Ventas por canal y alertas de frío se actualizan solas cada pocos segundos |
| Inteligencia artificial | Llamada desde la aplicación a la API gratuita de Gemini, con Groq de respaldo | Un requerimiento se clasifica; con la API apagada queda "sin clasificar" y el sistema sigue |

*Nota.* Elaboración propia. Los criterios retoman los de las especificaciones de la sección 5 y la rúbrica del Hito 2 de la pauta (INACAP Sede Temuco, 2026).

## Secuencia de construcción

El orden sigue las dependencias técnicas. Primero se construye y prueba en los computadores del equipo con contenedores iguales a los de AWS, y luego se despliega.

**Tabla 2**
*Secuencia de construcción y despliegue en AWS*

| Paso | Qué se hace | Depende de | Cuándo | Responsable |
|---|---|---|---|---|
| 1 | Prueba temprana en el Learner Lab: red, una EC2 y una RDS con una página de prueba | Acceso al laboratorio | 14 al 18 de octubre | Sergio |
| 2 | Esqueleto de Django con el modelo de datos, probado con PostgreSQL local en Docker | Esquema SQL del informe | 21 al 25 de octubre | Eric |
| 3 | Simulador IoT en contenedores, probado en local contra PostgreSQL | Esquema SQL del informe | 27 de octubre al 1 de noviembre | Sergio |
| 4 | Red, EC2 y RDS definitivas, con el esquema cargado | Paso 1 | 5 y 6 de noviembre | Sergio |
| 5 | E-commerce y CRM desplegados y conectados a RDS | Pasos 2 y 4 | 5 al 9 de noviembre | Eric |
| 6 | Nodo IoT desplegado en su EC2 dedicada | Pasos 3 y 4 | 6 al 9 de noviembre | Sergio |
| 7 | Tablero de Grafana y conexión con la IA | Pasos 5 y 6 | 9 y 10 de noviembre | Sergio y Eric |
| 8 | Pruebas integrales y ensayo del arranque completo | Todo lo anterior | 10 y 11 de noviembre | Ambos |

*Nota.* Elaboración propia a partir del cronograma de la sección 13. Los pasos 2 y 3 se hacen antes del Hito 1 para llegar al despliegue con el código probado.

## Cómo se mantiene funcional en el Learner Lab

El laboratorio apaga las instancias al cerrar la sesión y cambia la IP pública al encenderlas, de modo que "funcional" exige que el sistema vuelva solo. Con esa condición se diseñó el despliegue:

- Los servicios arrancan con la instancia: Docker Compose con política de reinicio y una IP elástica asociada a la EC2 web.
- La base de datos conserva los datos entre sesiones, y se toma un snapshot manual antes de cualquier borrado.
- Existe un guion de arranque escrito, para levantar todo en menos de diez minutos antes de la defensa.
- Las imágenes de Docker se construyen para x86 (`--platform linux/amd64`), porque los computadores del equipo tienen chip Apple y las EC2 del laboratorio no.
- Antes de la defensa se ensaya apagar y volver a encender el laboratorio, para comprobar que nada requiere intervención manual.

## Guion de la demostración

La defensa recorre el sistema de extremo a extremo, en este orden:

1. Un cliente institucional inicia sesión, ve su lista de precios y genera una orden.
2. El vendedor ve la orden en su CRM y avanza un prospecto de etapa.
3. El simulador envía lecturas de los camiones y una de ellas supera el rango de frío.
4. El tablero muestra la alerta junto a las ventas por canal, y la ficha del cliente destaca el pedido afectado.
5. Un cliente envía un reclamo y la IA lo clasifica; se repite con la API apagada para mostrar que el sistema sigue operando.
6. Se muestra el diagrama de arquitectura y se explican las decisiones, apoyadas en la memoria y en las pruebas.

## Notas del equipo
