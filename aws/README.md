# Despliegue en AWS Academy (Hito 2, dimensión 1)

Guía para levantar el ecosistema en el Learner Lab: **EC2 web** (aplicación + Grafana), **EC2 IoT** dedicada (camiones simulados) y **RDS PostgreSQL**. Los tres archivos de este directorio se probaron en local con la base como contenedor aparte, la aplicación en modo producción (`gunicorn`, `DEBUG=0`), el simulador en Docker y Grafana, contra una base vacía: migraciones, datos de demostración, telemetría en vivo y las 12 consultas del tablero respondieron sin errores. **La parte de AWS en sí (VPC, RDS, EC2) no se ejecutó**: requiere las credenciales del Learner Lab de cada integrante, que no se comparten.

## Arquitectura (resumen; el diagrama completo está en `informe/04a-diagrama-arquitectura.md`)

| Recurso | Dónde | Qué corre |
|---|---|---|
| Application Load Balancer (`cofrial-alb`) | Subredes públicas de las zonas A y B | Único punto de entrada: 80 (redirige a 443 con certificado de confianza) y 443; chequeo `/salud/` (pasa a `/health`, que prueba la base, con `endurecer.sh salud`; las instalaciones nuevas ya nacen con él); afinidad por cookie |
| EC2 web ×2 (`t3.small`) | Una por zona (`cofrial-ec2-web` primaria, `cofrial-ec2-web-b` secundaria) | `aws/docker-compose.web.yml`: Django (puerto 80, solo desde el ALB), Grafana (solo red interna, se abre en `/bi/`) y los servicios `podador`, `vigilante` (revisa cada minuto web, base, IoT, Grafana, IA y pagos y alimenta `/salud/`) y `despachador` (solo en la primaria; este último apagado salvo `DESPACHO_AUTO=1`) |
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

**Estado (12-nov-2026).** Lo de la aplicación y los contenedores llegó a AWS el 12-nov con `recrear-web` (rodante: unos 40 s de errores en total, al terminar cada web vieja) y `recrear-iot`. En AWS se aplicaron el 12-nov, con vista previa y confirmación de cada comando, la base, los security groups, el descarte de cabeceras, las alarmas y el dominio propio con certificado de ACM. Verificado después de cada paso: `https://www.cofrialspa.shop/salud/bd/` 200, el 80 redirige con 301, las dos web sanas en el balanceador y la IP directa de una web ya no responde. Después se pasó el chequeo del balanceador a `/health` y se rehicieron las alarmas con los ID nuevos; `endurecer.sh revisar` no deja faltas y `verificar.py --infra` da en verde la alta disponibilidad y D1 a D5.

**Estado (13-nov-2026).** Las dos web ya corren el código nuevo: `https://www.cofrialspa.shop` responde con la política CSP y HSTS de un día, `/health` da 200 y el grupo de destino del balanceador ya chequea en `/health` con las dos instancias sanas; la base sigue en Multi-AZ. Ese día, entre las 11:18 y las 11:25 (hora de Chile), un `recrear-web` rodante dejó las dos web con `main` en `32dd4ba` (PR 87: confirmación del pago con tarjeta y exención de `/health` en la redirección HTTPS); el sitio no se interrumpió y las alarmas de CPU se reaplicaron con los IDs nuevos. Los contenedores del nodo IoT no se revisaron ni se recrearon.

**Despliegue de la parte legal (13-nov-2026, 12:47 a 12:56, hora de Chile).** Otro `recrear-web` rodante dejó las dos web con `main` en `a9f3458` (PR 96: páginas legales, casilla de términos con constancia en `aceptacion_legal` y «Mis datos»); la migración `clientes/0005` corrió al arrancar. Medido cada 2 s contra `/health`: dos cortes de unos 20 s (502 o sin respuesta), uno al terminar cada web vieja, porque `recrear-web` no la saca antes del balanceador. Después: las dos web sanas, `/health` 200, el 80 redirige con 301, `endurecer.sh alarmas --aplicar` rehízo las ocho alarmas con los ID nuevos (todas en OK), `endurecer.sh revisar` sin faltas y `verificar.py --defensa --infra` con 65 correctas y 0 fallas.

**Despliegue de la página de estado (13-nov-2026, 13:22 a 13:31, hora de Chile).** Otro `recrear-web` rodante dejó las dos web con `main` en `bf9ba35` (PR 97: `/salud/` con historial y el servicio `vigilante`, que corre solo en la web primaria; PR 100: README). Antes se corrieron sobre ese `main` las pruebas de `salud`, rutas, legal, seguridad, cuentas y clientes: 208 OK. Medido cada 2 s contra `/health`: dos cortes, de unos 7 s y 17 s, uno por web reemplazada. Después: las dos web sanas, `/salud/` entrega la página al navegador y `{"estado": "ok"}` a `curl`, el 80 redirige con 301, alarmas rehechas con los ID nuevos (la de destinos no sanos saltó por la reconstrucción de la web B y volvió sola a OK), `endurecer.sh revisar` sin faltas y `verificar.py --defensa --infra` con 65 correctas y 0 fallas.

| Qué | Dónde quedó | Estado |
|---|---|---|
| Política de contenido (CSP), cookies `Secure`/`HttpOnly`/`SameSite`, HSTS configurable, respeto de `X-Forwarded-Proto` | `web/cofrial/settings.py`, `web/cofrial/csp.py` | **Aplicado** (12-nov): CSP, cookies `Secure` y HSTS de un día activos (`DJANGO_HTTPS=1`) |
| `/health` (200 solo si la aplicación alcanza la base) | `web/cofrial/urls.py` | **Aplicado** (12-nov): es el chequeo del balanceador |
| Límites de memoria y CPU, y rotación de registros en todos los contenedores | `aws/docker-compose.web.yml`, `aws/docker-compose.iot.yml` | **Aplicado** (12-nov) |
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
5. Las alarmas de CPU van atadas al ID de cada EC2, que cambia al recrearla: `recrear-web` y `recrear-iot` las **reapuntan solos al terminar** (`aws/reaplicar-alarmas-cpu.sh`, solo las que ya existen). Si fallara: `bash aws/endurecer.sh alarmas --aplicar`.

Después de cada paso: `bash aws/endurecer.sh revisar`, `curl -sI http://DNS-ALB/health` (301 a https), `curl -sk https://DNS-ALB/health` (200) y `python3 aws/verificar.py https://DOMINIO --infra`.

**Dominio y certificado (12-nov-2026).** El sitio se publica en `https://www.cofrialspa.shop`, un dominio propio en GoDaddy: `www` es un CNAME al DNS del balanceador. El 443 usa un certificado de ACM para `www.cofrialspa.shop` validado por DNS (CNAME de validación en GoDaddy), que ACM renueva solo; vence el 29-may-2027. Es el certificado principal del oyente. El de `cofrialspa.webhop.me` (Let's Encrypt importado, sin renovación automática) se quitó del oyente y se borró de ACM, y el nombre de No-IP se dio de baja. La raíz `cofrialspa.shop` se resuelve con el reenvío de GoDaddy hacia `https://www.cofrialspa.shop`. Al 13-nov el reenvío (permanente, 301) ya responde por `http://cofrialspa.shop` y, una vez que GoDaddy activó su certificado para el reenvío, también por `https://cofrialspa.shop`. La dirección que se muestra sigue siendo la de `www`. Sin dominio, `provision.sh` genera un certificado autofirmado y lo importa: el navegador muestra «La conexión no es privada» (`NET::ERR_CERT_AUTHORITY_INVALID`) y hay que aceptar la excepción a mano; por eso en ese caso el 80 no redirige y no se anuncia HSTS. Lo mismo se ve hoy al abrir por HTTPS el nombre DNS del balanceador, porque el certificado es del dominio (`NET::ERR_CERT_COMMON_NAME_INVALID`).

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

- Al cerrar la sesión (4 horas) AWS detiene las EC2 y la base. **El propio laboratorio vuelve a encender las EC2 al pulsar Start Lab** (22-oct y 13-nov: CloudTrail registra `StopInstances` y `StartInstances` hechos por el usuario de sistema del laboratorio, y la base quedó `available`), así que normalmente solo faltan las credenciales nuevas; `bash aws/provision.sh estado` lo muestra y `bash aws/provision.sh encender` arranca lo que, si acaso, esté apagado (primero RDS, luego las EC2, y espera a que la aplicación responda). La IP elástica no cambia y `restart: unless-stopped` hace que los contenedores vuelvan solos una vez encendida la EC2. `bash aws/provision.sh estado` muestra cómo están. **Para cada sesión nueva basta `bash aws/activar.sh`** (ver «Activar el laboratorio en cada sesión» más abajo).
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

## Activar el laboratorio en cada sesión

`bash aws/activar.sh` hace en un solo paso lo que antes eran varios: pide las credenciales nuevas, enciende la base y las EC2, espera a que el balanceador vea sanas las dos web y verifica desde fuera (`/health`, `/salud/bd/`, el sitio y la raíz del dominio). Con todo ya encendido solo verifica.

- **Por qué solo hay que encender.** Al cerrar la sesión AWS *detiene* (no termina) las EC2 y la base. Se conservan la red, el balanceador, la IP elástica, el certificado, el DNS, los destinos del balanceador y las alarmas, porque las IDs de las instancias no cambian al detener y encender; los contenedores vuelven solos (`restart: unless-stopped`). Recrear (`recrear-web`) sería un error aquí: cambia las IDs y deja las alarmas de CPU apuntando a instancias que ya no existen.
- **Qué no se puede automatizar: las credenciales.** AWS Academy las crea al pulsar Start Lab y solo se ven en su consola. El script usa las actuales si todavía funcionan; si no, pide copiar el bloque de AWS Details > AWS CLI, lo lee del portapapeles, lo prueba **antes** de reemplazar el archivo, rechaza el rol `runserver` y deja copia de las anteriores en `~/.aws/credentials.antes`. Nunca imprime las claves.
- **Opciones.** `--pegar` fuerza pegar credenciales nuevas; `--solo-verificar` no enciende nada (sirve a mitad de la sesión). Define `COFRIAL_ESTADO` o lo busca en el estado vigente del repositorio.
- **Alarmas desfasadas.** Si las alarmas de CPU apuntan a instancias que ya no existen (alguien recreó las web), `activar.sh` lo avisa y **pregunta si las reapunta** (`--arreglar-alarmas` lo hace sin preguntar). Lo hace `bash aws/reaplicar-alarmas-cpu.sh --aplicar`: solo reapunta alarmas que ya existen (mismos parámetros que `endurecer.sh alarmas`, conservando sus avisos SNS) y no crea ninguna nueva; sin `--aplicar` muestra qué cambiaría. Prueba: `bash aws/test_reaplicar_alarmas.sh` (8 casos).
- **SSH con IP de salida cambiante.** Tu proveedor reparte varias IP de salida y solo algunas están en la lista del puerto 22, así que la conexión a veces falla y a veces no. `--clave-unica` reintenta la prueba de conexión y el comando real (hasta `REINTENTOS_SSH`, 6, con `INTERVALO_SSH` s entre intentos) antes de ofrecer abrir el puerto, y la clave solo se envía por conexiones que llegaron a abrirse. Las IP públicas de la web B y de la IoT cambian en cada arranque (solo la web A tiene IP elástica): las muestra al final.
- **Clave única para todos los usuarios activos (`--clave-unica`).** Para dejar de perder claves entre stacks, copias de `secretos.env` y bases recreadas, `bash aws/activar.sh --clave-unica` (o contestar `s` a la pregunta del final) pide **una clave simple**, sin mostrarla y dos veces, y la pone igual en **todos los usuarios activos** (clientes, equipo y administración; los dados de baja no se tocan).
  - **Cómo viaja.** Por la entrada estándar de `ssh` hasta `manage.py cambiar_clave_demo --clave-stdin --todos-los-activos --permitir-clave-debil` en la web A: nunca en un argumento, en el entorno ni en el historial, y el comando no la imprime. Cada usuario guarda su propio hash.
  - **Huella verificada.** Siempre se conecta con `StrictHostKeyChecking=yes`. La huella sale, en orden, de: (1) la guardada para esa instancia en `$COFRIAL_ESTADO/huellas-ssh/<id>.pub`; (2) la salida de consola de EC2, que AWS imprime **solo la primera vez que arranca la instancia** (tras detener y encender el laboratorio ya no está) y que entonces se guarda; (3) la que responde ahora, **solo si la aceptas** (pregunta, o `--confiar-huella`): se muestra su huella `SHA256` y se guarda para las próximas veces. Esa tercera vía no tiene otra fuente con la que compararla, así que acéptala únicamente desde tu red de siempre. Sin huella ni consentimiento, no se conecta.
  - **Puerto 22.** Las IP permitidas de `cofrial-sg-web` son una lista fija; si la tuya cambió, el script lo dice y ofrece abrir el 22 **solo para tu IP** mientras dura el paso y cerrarlo al terminar (pregunta; `--abrir-ssh` da el consentimiento sin preguntar).
  - **Si no coinciden.** Hay hasta 3 intentos en la misma corrida; cada desajuste dice cuántos caracteres tuvo cada entrada y si alguna trae caracteres no imprimibles (por ejemplo, de pegar), sin mostrar las claves.
  - **Reglas.** Mínimo 4 caracteres y sin espacios. No puede ser igual a `DEMO_PASSWORD` ni a `ADMIN_PASSWORD`: `cargar_demo` devuelve a su clave propia a quien siga con la común y la nueva se perdería.
  - **Advertencia.** Es una clave débil y compartida, también en las cuentas del equipo y de administración de un sitio público. Solo para esta demostración; el límite de 10 claves malas por cuenta (15 min) sigue activo, pero no hay límite por IP.
- **Corrección de `encender` (13-nov-2026).** Su espera final consultaba `http://<balanceador>/salud/` sin seguir redirecciones; desde que el 80 redirige a HTTPS recibía un 301 y daba por caída una aplicación que ya funcionaba. Ahora sigue la redirección (`-L -k`, el certificado es del dominio, no del DNS del balanceador).
- **Prueba.** `bash aws/test_activar.sh` (AWS, `curl` y `pbpaste` falsos: 17 casos, entre ellos bloque incompleto, rol `runserver`, web no sana, alarmas huérfanas y la clave única). No ejercita `encender` sobre máquinas detenidas: el 13-nov, en la primera sesión nueva real, el laboratorio ya había encendido las EC2 y la base, y `activar.sh` solo guardó las credenciales y verificó (el sitio quedó verificado en 2 de 2 web sanas, dominio y raíz en 200).

## Panel de salud (CloudWatch)

`bash aws/panel-salud.sh` crea (o actualiza) el panel **`cofrial-salud`** en CloudWatch: el estado de la aplicación en verde y rojo, **alojado por AWS fuera de las EC2**. `--vista-previa` solo imprime su definición.

- **Por qué fuera de las máquinas.** `/health`, `/salud/` y `/salud/bd/` son respuestas de texto (`{"estado": "ok"}`, o 503 con `sin_base`) que viven en las mismas web que vigilan: si la web cae, no hay nada que responda ni pantalla que se ponga roja, y el panel de Grafana (`/bi/`) tampoco, porque corre en la misma máquina. CloudWatch lee las métricas del balanceador, de la base y de las EC2 y las alarmas, así que sigue mostrando aunque las web estén caídas.
- **Qué muestra.** Un cuadro con las 8 alarmas (verde bien, rojo en alarma, gris sin datos); web sanas y no sanas del balanceador (deben ser 2 y 0); errores 5xx del balanceador y de la aplicación con la línea de la alarma; peticiones y tiempo de respuesta; la CPU más alta y el promedio de las EC2; y CPU, conexiones y espacio libre de la base.
- **Dónde se abre.** Desde la consola de AWS del laboratorio (AWS Academy > AWS > CloudWatch > Paneles > `cofrial-salud`): `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/cofrial-salud`.
- **No depende de las IDs de las EC2**, así que sigue valiendo tras cada `recrear-web`. La CPU se busca por métrica (`MAX`/`AVG` de `SEARCH`) para que las instancias terminadas no llenen la leyenda; por instancia están las alarmas.
- **Lo que no hace.** No avisa por correo: eso lo hacen las alarmas con `ALARMA_EMAIL` (hoy sin definir). Las lagunas de la gráfica son los cierres del laboratorio, cuando no hay datos.
- **Prueba.** `bash aws/test_panel_salud.sh` (AWS falso, 5 casos). Creado y comprobado el 13-nov-2026 contra el laboratorio vivo: se renderizaron las gráficas de 5xx y CPU con datos reales.

