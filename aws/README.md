# Despliegue en AWS Academy (Hito 2, dimensión 1)

Guía para levantar el ecosistema en el Learner Lab: **EC2 web** (aplicación + Grafana), **EC2 IoT** dedicada (camiones simulados) y **RDS PostgreSQL**. Los tres archivos de este directorio se probaron en local con la base como contenedor aparte, la aplicación en modo producción (`gunicorn`, `DEBUG=0`), el simulador en Docker y Grafana, contra una base vacía: migraciones, datos de demostración, telemetría en vivo y las 12 consultas del tablero respondieron sin errores. **La parte de AWS en sí (VPC, RDS, EC2) no se ejecutó**: requiere las credenciales del Learner Lab de cada integrante, que no se comparten.

## Arquitectura (resumen; el diagrama completo está en `informe/04a-diagrama-arquitectura.md`)

| Recurso | Dónde | Qué corre |
|---|---|---|
| Application Load Balancer (`cofrial-alb`) | Subredes públicas de las zonas A y B | Único punto de entrada: 80 (redirige a 443 con certificado de confianza) y 443; chequeo `/salud/`; afinidad por cookie |
| EC2 web ×2 (`t3.small`) | Una por zona (`cofrial-ec2-web` primaria, `cofrial-ec2-web-b` secundaria) | `aws/docker-compose.web.yml`: Django (puerto 80, solo desde el ALB), Grafana (solo red interna, se abre en `/bi/`) y los servicios `podador` y `despachador` (solo en la primaria; este último apagado salvo `DESPACHO_AUTO=1`) |
| EC2 IoT (`t3.micro`) | Subred pública o privada con salida | `aws/docker-compose.iot.yml`: 5 contenedores que simulan 50 camiones (10 cada uno) |
| RDS PostgreSQL 16 (`db.t3.micro`) | Subred privada, **Multi-AZ** (réplica síncrona en la otra zona) | Base `cofrial` |

## Opción rápida: script de aprovisionamiento

`aws/provision.sh` crea todo lo de abajo (VPC, subredes, Security Groups encadenados, RDS, las dos EC2 con IP elástica y los contenedores arrancando solos). Genera las contraseñas al azar y las guarda en `aws/.estado/` (ignorado por git). **Está escrito pero no se ha ejecutado contra AWS**; se probó el flujo y los scripts de arranque con un reemplazo del comando `aws`, que no valida la semántica real de AWS. Ejecútalo la primera vez leyendo cada mensaje.

```bash
# 1. Learner Lab > AWS Details > AWS CLI: copiar las tres variables y exportarlas
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
export GEMINI_API_KEY=...        # opcional aquí; también se puede agregar después (ver «Activar la IA»)
bash aws/provision.sh            # ~10 minutos (RDS es lo más lento)
bash aws/provision.sh destruir   # borra todo al terminar
```

Supone: región `us-east-1`, repositorio público (las EC2 lo clonan solas), parámetro público de SSM para la AMI de Ubuntu 24.04 y que el laboratorio permite crear VPC, RDS y EC2 (no crea roles de IAM). Si algo de esto no se cumple, usa los pasos manuales de más abajo. Las claves quedan también en el user-data de la EC2: aceptable para un laboratorio, no para producción (allí iría Secrets Manager).

## Alta disponibilidad (balanceador, dos web, RDS Multi-AZ)

Requisito de la revisión técnica del 8-nov-2026. Diseño y trade-offs: `docs/decisiones.md` («Alta disponibilidad…») e `informe/03-arquitectura-cloud.md` (decisión 6). `provision.sh` lo arma todo; la prueba sin AWS es `bash aws/test_provision_ha.sh`.

**Sobre una instalación que ya existe (una web, RDS en una zona).** No recrear la base: se convierte.
1. `bash aws/provision.sh`: crea la subred B, el ALB, la web secundaria y convierte la RDS a Multi-AZ (10-20 min; corte breve al final). La web vieja queda registrada en el ALB con su configuración anterior.
2. `bash aws/provision.sh recrear-web`: rodante; recrea la web A con la configuración nueva (proxy de confianza, orígenes del ALB) y, cuando el ALB la da por sana, la B.
3. Probar por el DNS del ALB: `bash aws/provision.sh estado` (destinos `healthy` y RDS `True`) y `python3 aws/verificar.py`.
4. Apuntar el dominio al DNS del ALB y, cuando abra por el nombre, `bash aws/provision.sh cerrar-acceso-directo` (cierra el 80/443 abiertos a internet en `sg-web`; desde entonces solo entra el ALB).

**HTTPS.** Con `CERT_ARN=arn:aws:acm:...` (o `cert.pem`, `cert.key` y `cert-cadena.pem` en `aws/.estado/`, que el script importa a ACM) el 80 redirige al 443 y Django activa cookies seguras y HSTS. Sin certificado se genera uno autofirmado: el 443 abre con aviso y el 80 sigue sirviendo. Para reutilizar el certificado de Let's Encrypt del Caddy manual, copiar de su volumen `certificates/acme-v02.api.letsencrypt.org-directory/<dominio>/` el `.key` y el `.crt` (hoja en `cert.pem`, el resto en `cert-cadena.pem`). Importar un certificado a ACM exige permisos que el laboratorio puede negar: en ese caso el script avisa y deja solo el 80.

**Demostración de la caída (evaluador).**
- Web: apagar una EC2 web desde la consola; `curl http://DNS-ALB/salud/` sigue en 200 (el ALB la saca en ~30 s). `bash aws/provision.sh estado` muestra el destino caído.
- Base: `aws rds reboot-db-instance --db-instance-identifier cofrial-db --force-failover`; la zona activa (`AvailabilityZone`) cambia y el endpoint es el mismo. Hacerlo con calma: corta las conexiones 1-2 minutos y la web las retoma sola.

**Límites.** Una EC2 IoT (el requisito fue web y base de datos); los contadores de intentos son por instancia (el ALB mantiene a cada visitante en una); Learner Lab puede no admitir Multi-AZ (el script avisa). Cada web ocupa 2 vCPU: con el ALB y la RDS de respaldo consume más créditos que antes.

## Activar la IA (clave gratuita de Gemini)

1. En https://aistudio.google.com/apikey crear una clave (cuenta Google, plan gratuito, sin tarjeta). **No la pegues en el chat ni en el repositorio.**
2. Local: ponerla en `.env` como `GEMINI_API_KEY=...`. En AWS, en la EC2 web:
   ```bash
   cd /opt/cofrial && nano .env        # completar GEMINI_API_KEY y, si hace falta, GEMINI_MODELS
   docker compose -f aws/docker-compose.web.yml --env-file .env up -d
   ```
3. Verificar con la API real: `docker compose -f aws/docker-compose.web.yml exec web python manage.py probar_ia` debe responder «IA operativa». Si dice que no respondió, el mensaje trae la causa (clave, modelo no disponible o límite de uso). Los modelos se cambian con `GEMINI_MODELS` (lista separada por coma, en orden de preferencia).
4. Medir el acierto (meta del informe: más de 85 %): `... exec web python manage.py evaluar_ia`.

## Pasos manuales

1. **Red.** VPC con una subred pública y dos privadas (RDS exige un grupo de subredes con dos zonas), Internet Gateway y tabla de ruteo de la subred pública.
2. **Security Groups encadenados** (no abrir RDS a internet):
   - `sg-web`: entrada 80 desde internet; 22 solo desde tu IP. El 3000 de Grafana no se abre (`provision.sh` lo cierra si una instalación previa lo tenía).
   - `sg-iot`: sin entradas públicas; 22 solo desde tu IP.
   - `sg-rds`: entrada 5432 **únicamente desde `sg-web` y `sg-iot`**.
3. **RDS.** PostgreSQL 16, Single-AZ, sin acceso público, base inicial `cofrial`, usuario `cofrial`. Anota el endpoint.
4. **EC2 web y EC2 IoT.** Ubuntu 24.04, mismo VPC, con `LabInstanceProfile` si el laboratorio lo ofrece. Asigna una **IP elástica** a la web (sin ella, la IP cambia al reiniciar el laboratorio).
5. **En cada EC2** (por SSH):
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER && newgrp docker
   git clone https://github.com/leftra123/cofrial-spa.git && cd cofrial-spa
   cp aws/.env.aws.example .env && nano .env      # endpoint de RDS, claves y, en la web, DJANGO_CSRF_ORIGINS
   ```
6. **Arrancar primero la web** (crea las tablas y los camiones en RDS) y después el IoT:
   ```bash
   # EC2 web
   docker compose -f aws/docker-compose.web.yml --env-file .env up -d --build
   # EC2 IoT (cuando la web ya haya terminado de migrar: docker compose ... logs web)
   docker compose -f aws/docker-compose.iot.yml --env-file .env up -d --build
   ```
7. **Verificar** (ver la lista de abajo) y ensayar apagar y encender el laboratorio.

## Datos de demostración y reinicios
`cargar_demo` corre con `--solo-primera-vez`: si RDS ya tiene productos no toca nada, para que un reinicio del lab no deshaga lo editado en `/operacion/`. Si el repositorio trae datos nuevos que RDS aún no tiene (por ejemplo el reparto regional), agregar `FORZAR_CARGA_DEMO=1` a `aws/.estado/secretos.env` y ejecutar `recrear-web`. La variable queda en la EC2 y actúa en cada arranque, así que después hay que quitarla de `secretos.env` y ejecutar `recrear-web` otra vez; mientras esté activa, lo borrado en el panel vuelve. Hacerlo antes de editar datos: si la carga choca con algo editado, el sitio igual parte, pero la carga no se aplica y el motivo sale en el registro.

## Reglas del Learner Lab que importan

- Al cerrar la sesión (4 horas) AWS detiene las EC2 y la base. En la primera prueba real (22-oct) la base y las EC2 estaban de nuevo encendidas al iniciar la sesión siguiente, pero no hay garantía documentada; `bash aws/provision.sh estado` lo muestra y `bash aws/provision.sh encender` arranca lo que esté apagado (primero RDS, luego las EC2, y espera a que la aplicación responda). La IP elástica no cambia y `restart: unless-stopped` hace que los contenedores vuelvan solos una vez encendida la EC2. `bash aws/provision.sh estado` muestra cómo están.
- Con el ALB la dirección estable es su DNS (no cambia mientras exista); las EC2 web ya no necesitan IP elástica. Si cambia el dominio o el DNS, actualiza `DJANGO_CSRF_ORIGINS` en el `.env` de **cada** web y ejecuta `docker compose ... up -d`; sin eso los formularios responden 403.
- `DB_SSLMODE=require` es obligatorio contra RDS. Grafana solo admite `require`, `verify-ca`, `verify-full` o `disable` (no `prefer`).
- Imágenes desde un Mac con chip Apple: construir en la EC2 (como indica el paso 6) evita el problema de arquitectura.

## Lista de verificación antes de la demo

- [ ] `http://IP-WEB/salud/` responde `{"estado": "ok"}`.
- [ ] Entrar con `abastecimiento@hospital.test` (B2B) y con `ana@correo.test` (B2C): precios distintos en el catálogo, carrito y orden generada.
- [ ] En el CRM (`vendedora@cofrial.cl`) aparece el pedido web y el embudo.
- [ ] `docker compose -f aws/docker-compose.iot.yml logs -f` muestra una inserción cada 5 s por camión (50 camiones, en 5 contenedores); en `/flota/` las tarjetas cambian solas.
- [ ] `http://IP-WEB/bi/`, con sesión de gerencia o administración, muestra el tablero con ventas por canal, alertas y mapa; `:3000` no responde.
- [ ] IA: `docker compose -f aws/docker-compose.web.yml exec web python manage.py probar_ia` responde «IA operativa». Enviar una consulta desde **Soporte** y verla clasificada en `/crm/requerimientos/`.
- [ ] IA: `... exec web python manage.py evaluar_ia` da más de 85 % (meta del informe).
- [ ] Plan B: probar también la demo con `GEMINI_API_KEY` vacía; el sistema sigue funcionando y deja el requerimiento «sin clasificar».

## Verificación automática

`python3 aws/verificar.py` recorre la instalación y dice qué falla (cuentas, precios B2B y B2C, permisos por rol, telemetría fresca con los seis campos, consultas del tablero, ventas en ambos canales y requerimiento sin clasificar para la demostración); con `--ia` envía además un reclamo de prueba. Solo usa la biblioteca estándar de Python y no crea datos salvo con `--ia`. Se ejecuta tras cada `provision.sh`, `recrear-web` o `encender`, y antes de la defensa.
