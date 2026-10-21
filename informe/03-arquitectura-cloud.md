# 3. Memoria de decisiones de arquitectura cloud (trade-offs)

Rúbrica H1-D2 (Logrado): justificar **con trade-offs** VPC, subredes, seguridad, cómputo (EC2) y persistencia (RDS), coherentes con el caso.

## Componentes obligatorios según pauta

- **EC2** para el backend (persistente) y **EC2 dedicada** para el simulador IoT con Docker.
- **RDS** como base de datos relacional.
- **VPC, subredes, Security Groups** para arquitectura de red segura.

## Decisiones clave y sus trade-offs

### 1. Arquitectura de red: VPC con subredes segregadas

| Tema | Opción elegida | Alternativa descartada | Trade-off |
|---|---|---|---|
| Red virtual | VPC con subredes públicas (web/API) y privadas (RDS, datos) | Todo en subred pública | Seguridad vs. complejidad. VPC cuesta lo mismo en AWS pero es más complejo de configurar |
| Aislamiento de BD | RDS en subred privada, accesible solo desde EC2 | RDS con acceso público a internet | BD vulnerable a ataques, pero más fácil para debugging. Lo privado es correcto. |
| Internet Gateway | Un IGW para la subred pública (web sale a internet) | NAT Gateway (costo adicional) | El IGW es suficiente; NAT sería para EC2 privadas que necesiten salir. Aquí no es necesario. |

**Conclusión:** VPC con subredes segregadas es la arquitectura estándar. Responde al dolor de "servidor único sin redundancia"; aquí hay separación clara de capas.

---

### 2. Cómputo: EC2 como backend

| Tema | Opción elegida | Alternativa descartada | Trade-off |
|---|---|---|---|
| Servicio de cómputo | Amazon EC2 (IaaS) | AWS Lambda (serverless), Elastic Beanstalk (PaaS) | EC2 obliga a gestionar la instancia, pero deja visible la configuración de red y seguridad que la pauta exige justificar. Lambda no es un "backend persistente". |
| Tipo de instancia | t3.medium (2 vCPU, 4 GB RAM) | t3.small o t3.large | t3.medium es suficiente para un prototipo con Django (gunicorn) + Grafana. Es la "sweet spot" en el Learner Lab. |
| Persistencia | Servicio de respaldo automático (EBS snapshots) | Datos solo en volumen raíz | Snapshots permiten recuperarse de fallos de hardware. Responde al dolor del servidor sin respaldo. |
| Número de instancias | Dos EC2: una para web/API/CRM, otra para IoT/Docker | Una sola para todo | Segregar IoT permite escalar el simulador sin afectar la web. Docker en una máquina dedicada es más limpio. |

**Conclusión:** EC2 t3.medium con subredes y EBS snapshots responde a los requisitos de la pauta y es viable en el Learner Lab.

---

### 3. Base de datos relacional: RDS PostgreSQL

| Tema | Opción elegida | Alternativa descartada | Trade-off |
|---|---|---|---|
| Servicio de BD | Amazon RDS (managed) | PostgreSQL instalado en EC2, DynamoDB (NoSQL) | RDS es managed: AWS maneja respaldos, parcheo de SO, failover. Si fuera en EC2, tendríamos que hacerlo. DynamoDB no es relacional (el MER exige SQL). |
| Motor SQL | PostgreSQL | MySQL | PostgreSQL tiene mejor soporte para datos geográficos (PostGIS, aunque aquí no lo usemos) y series de tiempo (useful para telemetría). Ambos funcionan en RDS. |
| Respaldos | Snapshots automáticos diarios + retención 7 días | Respaldos manuales, o no hacer respaldos | Automático responde a la pauta: "respaldos automatizados". Manual es lo que falla hoy. |
| Subnet group | RDS en subred privada (sin acceso público) | RDS accesible desde internet | Privada es más seguro. Solo EC2 en subred pública puede conectar. |

**Conclusión:** RDS PostgreSQL con snapshots automáticos reemplaza el servidor on-premises vulnerable. Es el equivalente managed en la nube.

---

### 4. Seguridad: Security Groups (firewall de VPC)

| Componente | Regla | Justificación |
|---|---|---|
| SG para EC2 web | Entrada: TCP 80 (HTTP), 443 (HTTPS) desde internet (0.0.0.0/0) | Los clientes (B2B/B2C) acceden al e-commerce desde internet |
| | Entrada: TCP 22 (SSH) desde IP del equipo de desarrollo | Administración remota de la instancia |
| | Salida: TCP 5432 (PostgreSQL) hacia SG de RDS | EC2 se conecta a la BD |
| SG para RDS | Entrada: TCP 5432 (PostgreSQL) solo desde SG de EC2 | La BD solo acepta conexiones de EC2, no de internet |
| | Salida: ninguna (BD no inicia conexiones) | RDS es reactivo |
| SG para EC2 IoT | Entrada: ninguna (simulador solo envía) | Los contenedores solo inyectan datos a RDS |
| | Salida: TCP 5432 (PostgreSQL) hacia SG de RDS | Envía telemetría a la BD |

**Conclusión:** SGs en "principio de menor privilegio": cada componente solo accede a lo que necesita.

---

### 5. Restricciones de AWS Academy (Learner Lab)

La pauta implícitamente usa AWS Academy. El Lab tiene:
- **Créditos limitados:** típicamente $100 USD por 36 horas. Instancias pequeñas, apagarlas cuando termines.
- **Sesiones limitadas:** el lab se cierra después de un tiempo, y la sesión se reinicia.
- **Permisos IAM limitados:** no puedes crear ciertos recursos avanzados (CloudFront, WAF, etc.).
- **IPs públicas:** si usas una IP pública directa, se reasigna al reiniciar. **Solución:** usar Elastic IP (costo mínimo) o actualizar la URL en `.env`.

**Implicaciones:**
1. **Backend persistente:** los servicios (Django con gunicorn, Grafana) deben arrancar automáticamente al reiniciar. Usar `systemd` o Docker `restart: always`.
2. **Datos persistentes:** RDS existe en una BD independiente de la instancia. Los datos persisten.
3. **Plan B para la defensa:** guardar un script que levante todo en < 10 minutos por si el Lab se reinicia durante la demo.

---

## Resumen de la topología

```
Internet
  |
  +-- IGW (Internet Gateway)
       |
   +---+---+
   |       |
 Web(80)  HTTPS(443)
   |
   +-- EC2 web (t3.medium)
       | Backend Django (gunicorn)
       | CRM + E-commerce
       | API REST
       |
       +-- SG web (entrada: 80, 443, 22; salida: 5432 a RDS)
           |
           +-- TCP 5432 →
                       |
                    RDS PostgreSQL (privada)
                    Subredes privadas
                    SG RDS (entrada: 5432 desde EC2 únicamente)
                       |
                       Tablas: clientes, productos, órdenes, CRM, telemetría

EC2 IoT (t3.medium) ← Docker compose (5 contenedores simulando 50 camiones)
|
+-- SG IoT (salida: 5432 a RDS)
    |
    TCP 5432 → RDS (telemetría)
```

---

## Ventajas de esta arquitectura frente al problema original

| Dolor original | Cómo lo resuelve | Evidencia en el Hito 2 |
|---|---|---|
| Servidor único sin respaldo | RDS con snapshots automáticos | BD intacta aunque EC2 falle |
| Silos de datos (Excel + contabilidad) | Una sola BD RDS | Todas las apps leen de RDS |
| Sin trazabilidad de camiones | EC2 IoT envia telemetría a RDS cada 5 s | Dashboard actualizado en vivo |
| Pedidos por WhatsApp | E-commerce web + CRM vinculados a RDS | Orden automática, visible en CRM |
| Cascada de fallos | SGs segregan, RDS privada | No hay acceso directo a la BD desde internet |

Nota. Elaboración propia.

---

## Siguiente fase: escalabilidad

Si Cofrial escalara (más camiones, más clientes), esta arquitectura permite:
- **Multi-AZ para RDS:** replicación en otra zona de disponibilidad (0 downtime).
- **Auto Scaling para EC2:** levantar más instancias si tráfico sube.
- **CDN (CloudFront):** distribuir archivos estáticos (CSS, JS, imágenes).
- **Load Balancer:** distribuir carga entre múltiples EC2.

Ahora no es necesario, pero el diseño lo permite.

Nota. Elaboración propia.
