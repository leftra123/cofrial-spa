# 3. Memoria y decisiones de arquitectura cloud (trade-offs)

> Rúbrica H1-D2 (Logrado): justificar **con trade-offs** VPC, subredes, seguridad, cómputo (EC2) y persistencia (RDS), coherentes con el caso.
> Las decisiones se registran primero en `docs/decisiones.md` y se resumen aquí.

## Componentes obligatorios
- **EC2** para el backend (persistente) y **EC2 dedicada** para el simulador IoT con Docker.
- **RDS** como base de datos relacional.

## Decisiones a justificar
| Tema | Opción elegida | Alternativa descartada | Por qué (trade-off) |
|---|---|---|---|
| Red | VPC propia con subred pública (web) y privadas (RDS) | Todo en subred pública | _pendiente_ |
| Seguridad | Security Groups encadenados (RDS solo acepta desde EC2) | Abrir el puerto de la BD a internet | _pendiente_ |
| Cómputo | EC2 | Lambda/Beanstalk (no exigidos, limitaciones del Learner Lab) | _pendiente_ |
| BD | RDS (motor: ver decisiones) | BD instalada en EC2 | _pendiente_ |
| IoT | Nodo EC2 aparte con Docker | Simulador en la misma EC2 del backend | _pendiente_ |
| Disponibilidad | Single-AZ en el prototipo, Multi-AZ en producción | — | Costo vs. resiliencia |
| Respaldos | Respaldos automáticos de RDS | Respaldos manuales | Responde al dolor del servidor sin respaldo |

## Restricciones de AWS Academy (Learner Lab) a mencionar

> Fuente: documento de AWS "AWS Academy Learner Lab – Foundation Services" (copia alojada por una universidad, © 2021; el propio documento advierte que las restricciones pueden cambiar). Los puntos marcados como pendientes se verifican en nuestro laboratorio y en la guía del estudiante del curso antes de citarlos en la entrega.

- [x] **Regiones:** solo us-east-1 y us-west-2. El prototipo usa us-east-1.
- [x] **EC2:** tamaños nano a large, solo instancias On-Demand, máximo 9 instancias y 32 vCPU en ejecución por región, AMIs de Linux o Windows entregadas por Amazon, discos EBS de hasta 100 GB. El prototipo usa `t3.small` (2 GB): alcanza para el backend con Grafana y Docker; una `t3.micro` (1 GB) quedaría justa.
- [x] **RDS:** tamaños nano a medium (entra `db.t3.micro`), motores Aurora, MySQL, PostgreSQL y MariaDB, disco de hasta 100 GB gp2. **Multi-AZ no está soportado**: el prototipo queda Single-AZ y la subred de reserva en la segunda zona solo cumple el requisito del DB subnet group. El monitoreo mejorado tampoco está soportado.
- [x] **Fin de sesión:** al terminar, las instancias en ejecución pueden quedar detenidas y hay que volver a encenderlas. Sin IP elástica, la IP pública cambia en cada arranque. Un RDS detenido por siete días se reinicia solo y consume créditos. El backend debe arrancar solo (systemd o `docker compose` con reinicio automático).
- [x] **IAM:** no se pueden crear usuarios, grupos ni roles (salvo los vinculados a servicios); se usa el rol `LabRole` y el perfil `LabInstanceProfile`, que además permite entrar a la EC2 por la terminal del navegador (Session Manager).
- [x] **Servicios disponibles:** VPC, EC2, RDS, ECR, S3, CloudWatch, Secrets Manager, Elastic Load Balancing y Elastic Beanstalk, entre otros.
- [x] **Presupuesto de créditos limitado:** instancias pequeñas y apagarlas (EC2 y RDS) al terminar de trabajar.
- [x] **HTTPS:** sin dominio propio no se puede emitir un certificado, así que el prototipo expone HTTP (puerto 80). Si se consigue un dominio, se agrega el 443 y se actualiza el diagrama.
- [ ] **Pendiente:** duración exacta de la sesión (4 horas según otras guías) y monto de créditos, que no figuran en ese documento: leerlos en la guía del estudiante del curso.
- [ ] **Pendiente:** ensayar el arranque completo tras reiniciar el laboratorio antes de la demo del Hito 2, porque los fallos de arranque son lo que más riesgo tiene en vivo.

## Notas del equipo
