# Diagrama de arquitectura cloud

## Topología implementada

La Figura 1 representa la configuración vigente de `aws/provision.sh` y los compose de AWS. El equipo consultor reemplazó el dibujo inicial de cuatro subredes por una topología con una subred pública compartida y dos privadas. La región por defecto es us-east-1; las zonas se seleccionan al ejecutar el script.

**Figura 1**
*Arquitectura cloud implementada para el prototipo Cofrial SpA*

![Topología implementada de Cofrial](img/arquitectura-cloud.drawio.png)

Nota. Elaboración propia. Las líneas indican acceso web, consultas SQL cifradas y llamadas a servicios externos. La segunda subred privada pertenece al DB subnet group; no aloja una réplica activa.

## Elementos y flujos

**Tabla 1**
*Elementos de la topología implementada*

| Elemento | Configuración | Función |
|---|---|---|
| Región | us-east-1 por defecto | Entorno del laboratorio académico |
| VPC | 10.0.0.0/16 | Comunicación privada común |
| Subred pública | 10.0.1.0/24, zona A | EC2 web t3.small y EC2 IoT t3.micro; salida por IGW |
| Subred privada A | 10.0.2.0/24, zona A | Integrante del grupo de subredes de RDS |
| Subred privada B | 10.0.3.0/24, zona B | Segundo integrante del grupo; sin réplica Multi-AZ |
| RDS | PostgreSQL 16, db.t3.micro, 20 GB, Single-AZ, sin acceso público | Pedidos, CRM y telemetría |
| sg-web | 80 y 3000 públicos; 22 desde la IP del equipo | Portal y Grafana; administración SSH |
| sg-iot | 22 desde la IP del equipo | Administración; sin servicio público IoT |
| sg-rds | 5432 desde sg-web y sg-iot | Acceso SQL de aplicación, BI y simulador |
| API de IA externa | Gemini y Groq | Clasificación y asistente de tienda |
| Mapas externos | OpenStreetMap, Nominatim y OSRM | Teselas, ubicación de direcciones y rutas |

Nota. Elaboración propia. Zona A y zona B identifican las zonas seleccionadas por el script; no fijan letras de disponibilidad.

El cliente compra por el portal; Django persiste las órdenes y el CRM las consulta sin duplicarlas. El nodo IoT inserta lecturas y Grafana consulta RDS con una cuenta de solo lectura. Las llamadas a IA salen desde la aplicación; el navegador obtiene teselas y rutas según la pantalla. La protección de RDS depende de su acceso privado y de las referencias entre Security Groups, aunque las EC2 compartan subred.

La topología no incluye Nginx, balanceador, NAT Gateway, réplica Multi-AZ, Secrets Manager ni Session Manager porque esos componentes no están configurados en el despliegue actual. Sus alternativas de evolución se justifican en `03-arquitectura-cloud.md`.
