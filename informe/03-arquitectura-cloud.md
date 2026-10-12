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
- [ ] Sesiones limitadas en tiempo: las instancias se detienen al cerrar el lab → backend como servicio que arranque solo.
- [ ] La IP pública cambia al reiniciar si no se usa Elastic IP.
- [ ] Permisos IAM restringidos (se usa el rol que entrega el lab).
- [ ] Presupuesto de créditos limitado → instancias pequeñas.

## Notas del equipo
