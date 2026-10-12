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

> Fuente: guías de universidades que usan el Learner Lab (no la documentación oficial de AWS), por lo que **deben verificarse en nuestro propio laboratorio** antes de citarlas en el informe.

- [ ] **Regiones:** solo us-east-1 y us-west-2. El prototipo usa us-east-1.
- [ ] **Sesión de 4 horas:** al terminar, los recursos se conservan pero las máquinas se detienen (confirmar comportamiento de EC2 y RDS). El backend debe arrancar solo al encender la EC2 (gunicorn con systemd o `docker compose` con reinicio automático).
- [ ] **IP pública:** cambia al reiniciar si no se usa una IP elástica.
- [ ] **EC2:** solo tamaños nano a large, máximo 9 instancias por región y 32 vCPU en ejecución. El prototipo usa `t3.small` (2 GB): alcanza para el backend con Grafana y Docker; una `t3.micro` (1 GB) quedaría justa.
- [ ] **RDS:** confirmar qué tipos de instancia permite el laboratorio antes de fijar `db.t3.micro`.
- [ ] **Permisos IAM:** se usa el rol `LabRole` que entrega el laboratorio; no se pueden crear roles propios.
- [ ] **Presupuesto de créditos limitado:** instancias pequeñas y apagarlas al terminar de trabajar.
- [ ] **HTTPS:** sin dominio propio no se puede emitir un certificado, así que el prototipo expone HTTP (puerto 80). Si se consigue un dominio, se agrega el 443 y se actualiza el diagrama.
- [ ] **Ensayo de despliegue:** probar el arranque completo tras reiniciar el laboratorio antes de la demo del Hito 2, porque los fallos de arranque son lo que más riesgo tiene en vivo.

## Notas del equipo
