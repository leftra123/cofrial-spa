# Despliegue en AWS Academy (Hito 2, dimensión 1)

Guía para levantar el ecosistema en el Learner Lab: **EC2 web** (aplicación + Grafana), **EC2 IoT** dedicada (camiones simulados) y **RDS PostgreSQL**. Los tres archivos de este directorio se probaron en local con la base como contenedor aparte, la aplicación en modo producción (`gunicorn`, `DEBUG=0`), el simulador en Docker y Grafana, contra una base vacía: migraciones, datos de demostración, telemetría en vivo y las 12 consultas del tablero respondieron sin errores. **La parte de AWS en sí (VPC, RDS, EC2) no se ejecutó**: requiere las credenciales del Learner Lab de cada integrante, que no se comparten.

## Arquitectura (resumen; el diagrama completo está en `informe/04a-diagrama-arquitectura.md`)

| Recurso | Dónde | Qué corre |
|---|---|---|
| EC2 web (`t3.small`) | Subred pública, IP elástica | `aws/docker-compose.web.yml`: Django (puerto 80) y Grafana (3000) |
| EC2 IoT (`t3.micro`) | Subred pública o privada con salida | `aws/docker-compose.iot.yml`: 3 contenedores de camiones |
| RDS PostgreSQL 16 (`db.t3.micro`) | Subred privada, Single-AZ | Base `cofrial` |

## Pasos

1. **Red.** VPC con una subred pública y dos privadas (RDS exige un grupo de subredes con dos zonas), Internet Gateway y tabla de ruteo de la subred pública.
2. **Security Groups encadenados** (no abrir RDS a internet):
   - `sg-web`: entrada 80 y 3000 desde internet; 22 solo desde tu IP.
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

## Reglas del Learner Lab que importan

- Al cerrar la sesión las instancias se **detienen** y al reiniciar cambia la IP pública: por eso la IP elástica y `restart: unless-stopped` (los contenedores vuelven solos al encender la EC2).
- Si la EC2 web cambia de IP, actualiza `DJANGO_CSRF_ORIGINS` en su `.env` y ejecuta `docker compose ... up -d`; sin eso los formularios responden 403.
- `DB_SSLMODE=require` es obligatorio contra RDS. Grafana solo admite `require`, `verify-ca`, `verify-full` o `disable` (no `prefer`).
- Imágenes desde un Mac con chip Apple: construir en la EC2 (como indica el paso 6) evita el problema de arquitectura.

## Lista de verificación antes de la demo

- [ ] `http://IP-WEB/salud/` responde `{"estado": "ok"}`.
- [ ] Entrar con `abastecimiento@hospital.test` (B2B) y con `ana@correo.test` (B2C): precios distintos en el catálogo, carrito y orden generada.
- [ ] En el CRM (`vendedora@cofrial.test`) aparece el pedido web y el embudo.
- [ ] `docker compose -f aws/docker-compose.iot.yml logs -f` muestra una inserción cada 5 s por camión; en `/flota/` las tarjetas cambian solas.
- [ ] `http://IP-WEB:3000` muestra el tablero con ventas por canal, alertas y mapa.
- [ ] IA: `docker compose -f aws/docker-compose.web.yml exec web python manage.py probar_ia` responde «IA operativa». Enviar una consulta desde **Soporte** y verla clasificada en `/crm/requerimientos/`.
- [ ] IA: `... exec web python manage.py evaluar_ia` da más de 85 % (meta del informe).
- [ ] Plan B: probar también la demo con `GEMINI_API_KEY` vacía; el sistema sigue funcionando y deja el requerimiento «sin clasificar».
