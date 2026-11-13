# Despliegue en AWS Academy (Hito 2, dimensión 1)

Guía para levantar el ecosistema en el Learner Lab: **EC2 web** (aplicación + Grafana), **EC2 IoT** dedicada (camiones simulados) y **RDS PostgreSQL**. Los tres archivos de este directorio se probaron en local con la base como contenedor aparte, la aplicación en modo producción (`gunicorn`, `DEBUG=0`), el simulador en Docker y Grafana, contra una base vacía: migraciones, datos de demostración, telemetría en vivo y las 12 consultas del tablero respondieron sin errores. **La parte de AWS en sí (VPC, RDS, EC2) no se ejecutó**: requiere las credenciales del Learner Lab de cada integrante, que no se comparten.

## Arquitectura (resumen; el diagrama completo está en `informe/04a-diagrama-arquitectura.md`)

| Recurso | Dónde | Qué corre |
|---|---|---|
| Application Load Balancer (`cofrial-alb`) | Subredes públicas de las zonas A y B | Único punto de entrada: 80 (redirige a 443 con certificado de confianza) y 443; chequeo `/salud/` (pasa a `/health`, que prueba la base, con `endurecer.sh salud`; las instalaciones nuevas ya nacen con él); afinidad por cookie |
| EC2 web ×2 (`t3.small`) | Una por zona (`cofrial-ec2-web` primaria, `cofrial-ec2-web-b` secundaria) | `aws/docker-compose.web.yml`: Django (puerto 80, solo desde el ALB), Grafana (solo red interna, se abre en `/bi/`) y los servicios `podador` y `despachador` (solo en la primaria; este último apagado salvo `DESPACHO_AUTO=1`) |
| EC2 IoT (`t3.micro`) | Subred pública o privada con salida | `aws/docker-compose.iot.yml`: 5 contenedores que simulan 50 camiones (10 cada uno) |
| RDS PostgreSQL 16 (`db.t3.micro`) | Subred privada, **Multi-AZ** (réplica síncrona en la otra zona); las instalaciones nuevas nacen con protección contra borrado y respaldos de 7 días | Base `cofrial` |

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

## Endurecimiento (11-nov-2026)

Decisiones y trade-offs: `docs/decisiones.md` («Endurecimiento de la infraestructura y la aplicación»).

**Estado (12-nov-2026).** Lo de la aplicación y los contenedores está en el código y probado en local; llega a AWS con el próximo `recrear-web`/`recrear-iot`, que aún no se hace. En AWS se aplicaron el 12-nov, con vista previa y confirmación de cada comando, la base, los security groups, el descarte de cabeceras, las alarmas y el dominio propio con certificado de ACM. Verificado después de cada paso: `https://www.cofrialspa.shop/salud/bd/` 200, el 80 redirige con 301, las dos web sanas en el balanceador y la IP directa de una web ya no responde. `endurecer.sh revisar` deja una sola falta: el chequeo en `/health`, que espera el código nuevo.

| Qué | Dónde quedó | Estado |
|---|---|---|
| Política de contenido (CSP), cookies `Secure`/`HttpOnly`/`SameSite`, HSTS configurable, respeto de `X-Forwarded-Proto` | `web/cofrial/settings.py`, `web/cofrial/csp.py` | En el código; llega a AWS con el próximo `recrear-web` |
| `/health` (200 solo si la aplicación alcanza la base) | `web/cofrial/urls.py` | En el código; el balanceador sigue chequeando `/salud/` hasta desplegar el código y aplicar el paso `salud` |
| Límites de memoria y CPU, y rotación de registros en todos los contenedores | `aws/docker-compose.web.yml`, `aws/docker-compose.iot.yml` | En el código; llega con `recrear-web` y `recrear-iot` |
| Base: protección contra borrado, respaldos de 7 días, etiquetas en snapshots | `aws/endurecer.sh rds` (y `provision.sh` para instalaciones nuevas) | **Aplicado** (12-nov). Además ya era Multi-AZ y privada; etiquetas `Proyecto` y `Entorno` |
| Security groups: base solo desde web e IoT; web solo desde el balanceador | `aws/endurecer.sh sg` | **Aplicado** (12-nov): se quitaron de `cofrial-sg-web` el 80 y el 443 abiertos a internet; queda el 80 solo desde `cofrial-sg-alb`. La base ya aceptaba solo web e IoT |
| TLS 1.2/1.3, redirección 301 y descarte de cabeceras inválidas en el balanceador | `aws/endurecer.sh https` | **Aplicado** (12-nov): descarte de cabeceras; TLS 1.2/1.3 y 301 ya estaban |
| Alarmas de CloudWatch | `aws/endurecer.sh alarmas` | **Aplicado** (12-nov): 8 alarmas, sin aviso por correo (se ven en la consola de CloudWatch) |
| Copia de las claves en SSM Parameter Store | `aws/endurecer.sh secretos-subir` | Preparado, sin aplicar (0 parámetros en SSM); falta comprobar que el laboratorio lo permita |

**Cómo se aplica.** `aws/endurecer.sh` no recrea nada. Cada paso muestra los comandos exactos y **no ejecuta ninguno**; con `--aplicar` los ejecuta de a uno y pregunta antes de cada uno. Si las claves de la instalación están en otro checkout, se le indica con `COFRIAL_ESTADO=/ruta/a/aws/.estado` (lo mismo vale para `provision.sh`, que ahora se detiene si la base existe y no encuentra sus claves, en vez de generar otras).

```bash
bash aws/endurecer.sh revisar              # solo lectura: qué cumple y qué falta
bash aws/endurecer.sh rds                  # vista previa; con --aplicar, sin corte
bash aws/endurecer.sh rds-multiaz          # solo si revisar dice que no es Multi-AZ: 10-20 min, posible corte breve al final
bash aws/endurecer.sh https
bash aws/endurecer.sh alarmas              # ALARMA_EMAIL=correo@dominio para recibir avisos (hay que confirmar la suscripción)
```

Orden para lo que depende del código nuevo:
1. Fusionar la rama en `main` (las EC2 clonan `main`) y `bash aws/provision.sh recrear-web` (rodante; ~8 min por web) y `recrear-iot`.
2. `bash aws/endurecer.sh salud --aplicar`: comprueba seis veces que `/health` responde 200 por el balanceador y recién entonces cambia el chequeo. Deja impreso el comando para volver a `/salud/`.
3. `bash aws/endurecer.sh sg --aplicar`: quita de la base y del nodo IoT las reglas que sobren. Cierra el acceso directo a las web solo si el balanceador tiene destinos sanos y el dominio ya apunta a él; si no, se detiene y lo dice (`CORTAR_DOMINIO=1` lo fuerza).
4. Con las web cerradas y certificado de confianza, otro `recrear-web` deja a Django en modo HTTPS (`DJANGO_HTTPS=1`: cookies `Secure` y HSTS de un día). Mientras el 80 de las web siga abierto a internet ese modo queda apagado a propósito: con cookies `Secure` nadie podría iniciar sesión por la dirección vieja.
5. `bash aws/endurecer.sh alarmas --aplicar` otra vez: las alarmas de CPU van atadas al ID de cada EC2, que cambia al recrearla.

Después de cada paso: `bash aws/endurecer.sh revisar`, `curl -sI http://DNS-ALB/health` (301 a https), `curl -sk https://DNS-ALB/health` (200) y `python3 aws/verificar.py https://DOMINIO --infra`.

**Dominio y certificado (12-nov-2026).** El sitio se publica en `https://www.cofrialspa.shop`, un dominio propio en GoDaddy: `www` es un CNAME al DNS del balanceador. El 443 usa un certificado de ACM para `www.cofrialspa.shop` validado por DNS (CNAME de validación en GoDaddy), que ACM renueva solo; vence el 29-may-2027. Es el certificado principal del oyente. El de `cofrialspa.webhop.me` (Let's Encrypt importado, sin renovación automática) se quitó del oyente y se borró de ACM, y el nombre de No-IP se dio de baja. La raíz `cofrialspa.shop` se resuelve con el reenvío de GoDaddy hacia `https://www.cofrialspa.shop`. Al 12-nov ese reenvío aún responde 404: la dirección que se muestra es la de `www`. Sin dominio, `provision.sh` genera un certificado autofirmado y lo importa: el navegador muestra «La conexión no es privada» (`NET::ERR_CERT_AUTHORITY_INVALID`) y hay que aceptar la excepción a mano; por eso en ese caso el 80 no redirige y no se anuncia HSTS. Lo mismo se ve hoy al abrir por HTTPS el nombre DNS del balanceador, porque el certificado es del dominio (`NET::ERR_CERT_COMMON_NAME_INVALID`).

**Cifrado en reposo.** `provision.sh` no pide cifrado al crear la base y RDS no permite activarlo sobre una instancia existente: hay que restaurarla desde una copia cifrada. No se hace desde los scripts; el procedimiento, si el equipo lo decide, es:
1. Detener los escritores (EC2 IoT y las dos web) para no perder lo que se escriba entre la copia y el cambio.
2. `aws rds create-db-snapshot --db-instance-identifier cofrial-db --db-snapshot-identifier cofrial-pre-cifrado` y esperar a que termine.
3. `aws rds copy-db-snapshot --source-db-snapshot-identifier cofrial-pre-cifrado --target-db-snapshot-identifier cofrial-cifrado --kms-key-id alias/aws/rds` (la copia es la que queda cifrada).
4. `aws rds restore-db-instance-from-db-snapshot --db-instance-identifier cofrial-db-cifrada --db-snapshot-identifier cofrial-cifrado` con el mismo grupo de subredes, `cofrial-sg-rds`, `--multi-az`, `--no-publicly-accessible`, `--deletion-protection` y `--copy-tags-to-snapshot`; después, `modify-db-instance --backup-retention-period 7`.
5. Renombrar: la actual a `cofrial-db-vieja` y la nueva a `cofrial-db` (`modify-db-instance --new-db-instance-identifier`). El endpoint lleva el identificador, así que el de la nueva queda igual al actual y el `.env` de las EC2 no cambia.
6. Encender web e IoT, verificar, y borrar la vieja solo cuando todo funcione (quitándole antes la protección contra borrado).

Son 30 a 45 minutos con el sitio detenido y sin vuelta atrás rápida si el laboratorio rechaza la clave de KMS. No conviene hacerlo en la víspera de la defensa.

**Pruebas sin AWS.** `bash aws/test_endurecer.sh` ejecuta el script contra un `aws` falso con estado y consultas JMESPath reales (necesita el módulo `jmespath` de Python; sin él se omite): la vista previa no cambia nada, cada paso hace solo lo suyo, las web no se cierran si el balanceador no sirve o el dominio no apunta a él, y ninguna clave sale por pantalla. No valida los permisos del laboratorio.

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

- [ ] `http://IP-WEB/salud/` responde `{"estado": "ok"}` y, con el código del 11-nov, también `/health` (este prueba la base).
- [ ] Entrar con `abastecimiento@hospital.test` (B2B) y con `ana@correo.test` (B2C): precios distintos en el catálogo, carrito y orden generada.
- [ ] En el CRM (`vendedora@cofrial.cl`) aparece el pedido web y el embudo.
- [ ] `docker compose -f aws/docker-compose.iot.yml logs -f` muestra una inserción cada 5 s por camión (50 camiones, en 5 contenedores); en `/flota/` las tarjetas cambian solas.
- [ ] `http://IP-WEB/bi/`, con sesión de gerencia o administración, muestra el tablero con ventas por canal, alertas y mapa; `:3000` no responde.
- [ ] IA: `docker compose -f aws/docker-compose.web.yml exec web python manage.py probar_ia` responde «IA operativa». Enviar una consulta desde **Soporte** y verla clasificada en `/crm/requerimientos/`.
- [ ] IA: `... exec web python manage.py evaluar_ia` da más de 85 % (meta del informe).
- [ ] Plan B: probar también la demo con `GEMINI_API_KEY` vacía; el sistema sigue funcionando y deja el requerimiento «sin clasificar».

## Verificación automática

`python3 aws/verificar.py` recorre la instalación y dice qué falla (cuentas, precios B2B y B2C, permisos por rol, telemetría fresca con los seis campos, consultas del tablero, ventas en ambos canales y requerimiento sin clasificar para la demostración); con `--ia` envía además un reclamo de prueba, con `--compra-ensayo` hace la compra de ensayo B2B y B2C (pedidos reales; no repite si hay una vigente de 7 días) y con `--defensa` exige que las cinco filas D1 a D5 de la Torre queden «verificado» y que `/torre/pulso/` responda rápido. Prueba además las 13 cuentas (con la clave única si está en `secretos.env` como `CLAVE_UNICA_DEMO`), el rechazo de un envío sin token CSRF (y, con `--nombre=https://dominio`, el ingreso por ese nombre) y que «Mi pedido llegó tibio» siga sin clasificar (si no: `manage.py restablecer_demo_ia` en la web). Solo usa la biblioteca estándar de Python y no crea datos salvo con `--ia` y `--compra-ensayo`. Se ejecuta tras cada `provision.sh`, `recrear-web` o `encender`, y antes de la defensa. Con `--infra` (obligatorio en `--defensa`) lee además de AWS, solo lectura y con la AWS CLI, el balanceador, las dos web por zona y RDS Multi-AZ. Sus pruebas sin red: `python3 aws/test_verificar.py`.
