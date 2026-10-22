# 3. Memoria y decisiones de arquitectura cloud (trade-offs)

> Rúbrica H1-D2 (Logrado): justificar **con trade-offs** VPC, subredes, seguridad, cómputo (EC2) y persistencia (RDS), coherentes con el caso.
> Las decisiones se registran primero en `docs/decisiones.md` y se resumen aquí.

## Componentes obligatorios
- **EC2** para el backend (persistente) y **EC2 dedicada** para el simulador IoT con Docker.
- **RDS** como base de datos relacional.

## Decisiones a justificar

> Estado: borrador de redacción, pendiente de validación del equipo. Los números marcados como estimación son supuestos explícitos (intervalo de telemetría de 5 segundos, 50 camiones).

**Tabla 1**
*Resumen de decisiones de arquitectura y su trade-off principal*

| Tema | Opción elegida | Alternativa descartada | Trade-off principal |
|---|---|---|---|
| Red | VPC propia con subredes públicas (web e IoT) y privadas (datos) | Todo en subred pública o VPC por defecto | Más pasos de configuración a cambio de que la base de datos no tenga ruta desde internet |
| Seguridad | Security Groups encadenados por referencia | Abrir el puerto 5432 a internet o a un rango de IP | Más grupos que mantener a cambio de admitir solo a las instancias exactas, aunque se reemplacen |
| Cómputo | EC2 con Docker Compose | Lambda o Elastic Beanstalk | Administrar el sistema operativo por cuenta del equipo a cambio de control visible y proceso persistente |
| Base de datos | RDS PostgreSQL | PostgreSQL instalado en EC2 | Menos control del servidor a cambio de respaldos y parches gestionados |
| IoT | EC2 dedicada con Docker | Simulador en la misma EC2 del backend | Una instancia más de créditos a cambio de aislar la carga de telemetría de la web |
| Disponibilidad | Single-AZ en el prototipo, Multi-AZ en producción | Multi-AZ desde el inicio | Riesgo de caída por zona a cambio de costo cero y compatibilidad con el Learner Lab |
| Respaldos | Respaldos automáticos de RDS más un snapshot manual antes de cualquier borrado | Respaldos manuales periódicos | Costo de almacenamiento a cambio de eliminar la dependencia de una persona |

*Nota.* Elaboración propia.

### 1. Red: VPC propia con subredes públicas y privadas

**Decisión.** VPC `10.0.0.0/16` en us-east-1 con una subred pública para la web (`10.0.1.0/24`), otra pública para el nodo IoT (`10.0.2.0/24`) y dos privadas para datos (`10.0.11.0/24` y `10.0.12.0/24`, en zonas distintas). Un Internet Gateway sirve a las dos públicas; las privadas solo tienen ruta local.

**Qué se gana.** La base de datos no tiene dirección pública ni ruta hacia internet. Es el punto que más pesa en Cofrial: sus clientes son hospitales y supermercados, y los datos de pedidos y de cadena de frío son su activo. Dejarlos en una subred pública habría repetido, en la nube, el defecto de la bodega: un único punto expuesto.

**Qué se cede.** Más piezas que configurar (subredes, tablas de ruteo, grupo de subredes de RDS) para un equipo de dos personas. Además, el grupo de subredes de RDS exige dos zonas de disponibilidad, así que existe una subred privada de reserva (`10.0.12.0/24`) que no aloja nada en el prototipo.

**Por qué sin NAT Gateway.** Las subredes privadas solo contienen RDS, que no necesita salir a internet. Un NAT Gateway tiene costo por hora y consumiría créditos del laboratorio sin aportar nada aquí.

**Por qué el nodo IoT va en subred pública.** Necesita descargar imágenes de Docker y paquetes, y sin NAT esa salida requiere IP pública. El riesgo se controla con un Security Group sin entradas públicas. En producción el nodo iría en subred privada con salida controlada.

**Por qué dos subredes públicas separadas.** La separación efectiva la dan los Security Groups, no la subred. Se separan igualmente para que, en producción, la telemetría pueda tener su propia tabla de ruteo y una lista de control de acceso (NACL) sin rediseñar la red.

### 2. Seguridad: Security Groups encadenados

**Decisión.** Tres grupos: `sg-web` (80 público; 22 y 3000 solo desde la IP del equipo), `sg-iot` (sin entradas públicas) y `sg-rds`, que acepta el puerto 5432 únicamente desde `sg-web` y `sg-iot`, referenciados por grupo y no por rango de direcciones.

**Qué se gana.** Una regla por rango de IP (por ejemplo, toda la subred `10.0.1.0/24`) dejaría pasar a cualquier máquina que se cree allí; la regla por grupo admite solo a las instancias que pertenecen a `sg-web` o `sg-iot`, aunque cambien o se reemplacen. Es el mínimo privilegio posible entre capas y evita la tentación de abrir el puerto "para que funcione" cuando se reconstruye una instancia.

**Qué se cede.** Hay que mantener tres grupos y entender cómo se referencian entre sí. También se acepta una limitación del laboratorio: no se pueden crear roles IAM propios, por lo que todo corre con `LabRole`, con permisos más amplios de lo que correspondería. En producción cada servicio tendría su rol con permisos mínimos.

**Administración remota.** El perfil `LabInstanceProfile` permite entrar a las instancias por Session Manager desde el navegador. Esa vía elimina la necesidad de abrir el puerto 22. Queda como mejora a evaluar: cerrar el 22 y administrar solo por Session Manager.

**Secretos.** La clave de la API de IA y las credenciales de la base de datos van en variables de entorno o en Secrets Manager (disponible en el laboratorio), nunca en el repositorio.

**Riesgo aceptado: HTTP.** Sin dominio propio no se puede emitir un certificado, así que el prototipo atiende por HTTP. Las credenciales de inicio de sesión viajarían sin cifrar. Es aceptable para una demostración con datos ficticios y debe declararse en la defensa. En producción: dominio, certificado y balanceador con HTTPS.

### 3. Cómputo: EC2 con Docker Compose

**Decisión.** Una EC2 `t3.small` para la web y el backend (una aplicación Django servida con gunicorn detrás de nginx) y Grafana en un contenedor de la misma instancia, todo orquestado con Docker Compose y reinicio automático.

**Alternativas.** Lambda no ofrece un backend persistente y obliga a rediseñar la aplicación en funciones. Elastic Beanstalk crea EC2 por debajo, pero oculta justamente la red y la seguridad que la rúbrica pide justificar, y en el Learner Lab hay que ajustar a mano el rol de servicio y el perfil de instancia para que funcione.

**Qué se gana.** Control visible de cada capa, un proceso persistente conectado a RDS y un entorno idéntico al que se probará localmente, porque Docker empaqueta la aplicación.

**Qué se cede.** Parches del sistema operativo, supervisión del proceso y escalado quedan a cargo del equipo. Mitigación: contenedores con reinicio automático, de modo que los servicios vuelvan solos cuando el laboratorio apague y encienda la instancia. Para producción el camino natural es Auto Scaling con un balanceador, servicios que el laboratorio sí ofrece.

**Tamaño.** `t3.small` (2 GB) alcanza para la aplicación y Grafana; una `t3.micro` (1 GB) quedaría justa con ambos.

### 4. Base de datos: RDS PostgreSQL

**Decisión.** RDS PostgreSQL `db.t3.micro` en subred privada.

**Qué se gana.** El primer dolor del caso es un servidor único sin respaldos. RDS entrega respaldos automáticos, recuperación a un punto en el tiempo, parches gestionados y un servicio que sobrevive aunque falle la EC2. Instalar PostgreSQL en una EC2 habría trasladado el mismo problema a la nube: respaldos a mano.

**Qué se cede.** No hay acceso al sistema operativo del servidor y los parámetros se ajustan por grupos de parámetros. Además cuesta más que autogestionarla y hereda las restricciones del laboratorio: tamaños nano a medium, disco de hasta 100 GB, sin Multi-AZ y sin monitoreo mejorado.

**Por qué PostgreSQL y no MySQL.** Ambos cumplen la pauta y puntúan casi igual en la evaluación ponderada. PostgreSQL gana por su manejo de fechas y coordenadas, útil para la telemetría, y porque Grafana y Django lo soportan de forma nativa.

**Riesgo: telemetría y transacciones en la misma base.** Con 50 camiones reportando cada 5 segundos se insertan unas 10 filas por segundo, cerca de 864 000 al día (estimación). Si se deja correr durante semanas, la tabla de telemetría crece mucho más que las de pedidos y compite con ellas. Mitigación: índices por camión y fecha, una política de retención (por ejemplo, conservar el detalle por 7 días y agregar por hora) y, en producción, separar la telemetría en una base de series de tiempo.

### 5. IoT: nodo EC2 dedicado con Docker

**Decisión.** Una EC2 aparte donde Docker Compose levanta un contenedor por camión (o por grupo de camiones), cada uno insertando telemetría en RDS.

**Qué se gana.** Aislamiento de fallas y de carga: 50 contenedores generando datos no compiten por CPU y memoria con la web durante la demostración. Además `sg-iot` puede ser mucho más restrictivo que `sg-web`. La pauta exige este nodo dedicado.

**Qué se cede.** Una instancia más que consume créditos (aporta 2 vCPU de los 32 permitidos) y otra máquina que levantar tras cada reinicio del laboratorio.

**Limitación del prototipo.** Los camiones reales no insertarían directamente en la base de datos: lo harían a través de un gateway o un protocolo de mensajería (por ejemplo MQTT) con una API de ingesta que valide y limite el tráfico. Insertar directo acopla el dispositivo a la base. Se acepta porque la pauta pide la inyección automatizada a la BD y el nodo simula justamente el borde.

### 6. Disponibilidad: Single-AZ en el prototipo

**Decisión.** Todo en una sola zona de disponibilidad.

**Por qué.** El Learner Lab no soporta Multi-AZ en RDS, y aunque lo soportara duplicaría el costo en créditos. Es una restricción del entorno, no una omisión de diseño.

**Qué se cede.** Una caída de la zona deja sin servicio al sistema completo. Cofrial hoy tiene un punto único de falla en el servidor de la bodega; el prototipo mejora los respaldos y la recuperación, pero no la alta disponibilidad, y así debe decirse en la defensa.

**Mitigación.** Los datos quedan protegidos por los respaldos de RDS, y la aplicación se reconstruye en minutos con Docker Compose en una instancia nueva. En producción: Multi-AZ para RDS y dos instancias web detrás de un balanceador.

### 7. Respaldos: automáticos y no manuales

**Decisión.** Respaldos automáticos de RDS, con un snapshot manual antes de borrar la instancia o al terminar el trabajo del día.

**Por qué.** La causa raíz del dolor original no es la falta de un disco de respaldo, sino que depende de que alguien se acuerde. Los respaldos automáticos eliminan esa dependencia y permiten volver a un instante concreto.

**Qué se cede y cómo se mitiga.** Los respaldos automáticos se eliminan junto con la instancia, salvo que se pida retenerlos, mientras que los snapshots manuales no se ven afectados (Amazon Web Services, s.f.); por eso se toma uno antes de cualquier borrado. Tampoco hay copia en otra región; en producción se agregaría una copia entre regiones.

### Limitaciones declaradas del prototipo

**Tabla 2**
*Limitaciones del prototipo frente a un entorno de producción*

| Limitación | Causa | Mitigación en el prototipo | En producción |
|---|---|---|---|
| Sin alta disponibilidad | Single-AZ; el laboratorio no permite Multi-AZ en RDS | Respaldos y reconstrucción con Docker Compose | Multi-AZ y balanceador |
| Tráfico sin cifrar | Sin dominio no hay certificado | Datos ficticios y declararlo en la defensa | Dominio, certificado y HTTPS |
| Permisos amplios | Solo se puede usar `LabRole` | Security Groups estrictos | Un rol por servicio con permisos mínimos |
| Nodo IoT en subred pública | Sin NAT para ahorrar créditos | `sg-iot` sin entradas | Subred privada con salida controlada |
| Telemetría y pedidos en la misma base | Una sola instancia RDS | Índices y retención de datos | Base de series de tiempo separada |
| Inserción directa a la base | La pauta pide inyección automatizada a la BD | Credenciales fuera del repositorio | Gateway o MQTT y API de ingesta |

*Nota.* Elaboración propia.

## Restricciones de AWS Academy (Learner Lab) a mencionar

Las restricciones siguientes provienen del documento técnico de AWS para el Learner Lab (Amazon Web Services, 2021), que advierte que pueden cambiar. Los puntos que ese documento no cubre se confirman en el laboratorio del equipo.

- **Regiones:** solo us-east-1 y us-west-2. El prototipo usa us-east-1.
- **EC2:** tamaños nano a large, solo instancias On-Demand, máximo 9 instancias y 32 vCPU en ejecución por región, AMIs de Linux o Windows entregadas por Amazon, discos EBS de hasta 100 GB. El prototipo usa `t3.small` (2 GB): alcanza para el backend con Grafana y Docker; una `t3.micro` (1 GB) quedaría justa.
- **RDS:** tamaños nano a medium (entra `db.t3.micro`), motores Aurora, MySQL, PostgreSQL y MariaDB, disco de hasta 100 GB gp2. **Multi-AZ no está soportado**: el prototipo queda Single-AZ y la subred de reserva en la segunda zona solo cumple el requisito del DB subnet group. El monitoreo mejorado tampoco está soportado.
- **Fin de sesión:** al terminar, las instancias en ejecución pueden quedar detenidas y hay que volver a encenderlas. Sin IP elástica, la IP pública cambia en cada arranque. Un RDS detenido por siete días se reinicia solo y consume créditos. El backend debe arrancar solo (systemd o `docker compose` con reinicio automático).
- **IAM:** no se pueden crear usuarios, grupos ni roles (salvo los vinculados a servicios); se usa el rol `LabRole` y el perfil `LabInstanceProfile`, que además permite entrar a la EC2 por la terminal del navegador (Session Manager).
- **Servicios disponibles:** VPC, EC2, RDS, ECR, S3, CloudWatch, Secrets Manager, Elastic Load Balancing y Elastic Beanstalk, entre otros.
- **Presupuesto de créditos limitado:** instancias pequeñas y apagarlas (EC2 y RDS) al terminar de trabajar.
- **HTTPS:** sin dominio propio no se puede emitir un certificado, así que el prototipo expone HTTP (puerto 80). Si se consigue un dominio, se agrega el 443 y se actualiza el diagrama.
- **Por confirmar en el laboratorio:** la duración de la sesión y el monto de créditos, que ese documento no indica.
- **Ensayo previo:** probar el arranque completo tras reiniciar el laboratorio antes de la demostración del Hito 2, porque los fallos de arranque son lo que más riesgo tiene en vivo.

## Despliegue realizado en AWS Academy (22 de octubre de 2026)

El diseño anterior se construyó en el Learner Lab con el script `aws/provision.sh`, que crea la red, la base de datos y las dos instancias de forma repetible. La **Tabla 3** contrasta lo diseñado con lo desplegado. El prototipo cumple lo que exige la pauta, pero se apartó del diseño en los puntos que se indican; todos son limitaciones declaradas y ninguno compromete un requisito de la pauta.

**Tabla 3**
*Diseño frente a lo desplegado en AWS Academy*

| Aspecto | Diseño | Desplegado | Motivo o consecuencia |
|---|---|---|---|
| Subredes | Dos públicas (web `10.0.1.0/24` e IoT `10.0.2.0/24`) y dos privadas (`10.0.11.0/24` y `10.0.12.0/24`) | Una pública (`10.0.1.0/24`) compartida por web e IoT y dos privadas (`10.0.2.0/24` y `10.0.3.0/24`) | Se simplificó el script; la separación efectiva entre web e IoT la siguen dando los Security Groups, como anticipa el diseño |
| Acceso al tablero de Grafana | Puerto 3000 solo desde la IP del equipo | Puerto 3000 abierto a internet con visor anónimo de solo lectura | Permite mostrar el tablero en la defensa sin cuenta; editar exige la clave de administrador. Exposición mayor que la diseñada |
| Servidor de la aplicación | Gunicorn detrás de nginx | Gunicorn directo en el puerto 80, con los archivos estáticos servidos por WhiteNoise | Una pieza menos que mantener; sin la capa de nginx ante peticiones lentas o malformadas |
| Respaldos de RDS | Automáticos más un snapshot manual antes de cualquier borrado | Retención automática de un día; el borrado con `provision.sh destruir` no toma snapshot final | Mínimo para el laboratorio; la base no se podría recuperar tras destruirla |
| Administración remota | Session Manager con `LabInstanceProfile`, sin abrir el puerto 22 | SSH con llave y puerto 22 abierto solo a la IP del equipo, sin perfil de instancia | El script no asocia el perfil; el SSH de la instancia web recreada llegó a rechazar conexiones |
| Cifrado hacia la base | No especificado | `sslmode=require` desde la aplicación y el simulador | RDS moderno exige conexiones cifradas |
| Seguridad entre capas | Tres Security Groups encadenados por referencia | Igual | Sin diferencias |
| Cómputo y base | EC2 `t3.small` con Docker Compose y RDS `db.t3.micro` Single-AZ en subred privada | Igual; el nodo IoT usa `t3.micro` | Sin diferencias de fondo |
| HTTPS | Solo HTTP, riesgo aceptado | Igual | Sin dominio no hay certificado |

*Nota.* Elaboración propia. Verificado el 22-oct-2026 sobre la instalación en AWS.

**Verificación del despliegue.** Sobre la instalación en AWS se comprobó que: (a) una compra como cliente institucional y otra como cliente público generan órdenes en RDS y aparecen en el CRM; (b) los contenedores de la instancia dedicada insertan telemetría con los seis campos exigidos y la pantalla de flota se actualiza cada cinco segundos; (c) las doce consultas del tablero responden con datos reales y cruzan ventas por canal con alertas de frío; y (d) la clasificación con IA funciona con la API real. La primera ejecución del script no presentó errores. En el proceso se detectó que el terminal integrado del laboratorio usa un rol sin permisos para crear recursos y que debe emplearse el rol del usuario del laboratorio, y que algunos parámetros públicos de SSM están bloqueados, por lo que el script obtiene la imagen de Ubuntu del catálogo del propietario.

**Limitaciones que persisten.** Las instancias se detienen al cerrar la sesión del laboratorio y las claves de acceso caducan; los contenedores y la IP elástica sobreviven a ese reinicio. La instancia web no es redundante y la base es Single-AZ, por lo que una falla de zona dejaría el servicio caído.

## Notas del equipo
