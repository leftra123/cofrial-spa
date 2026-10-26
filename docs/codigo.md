# Sistema implementado Cofrial SpA

Estado al 25-oct-2026. La aplicación única está en `web/`; el scaffold `backend/` fue retirado.

| Área | Implementación vigente |
|---|---|
| Web | Django 5.2, plantillas, CSS propio, JavaScript progresivo, DRF y autenticación por sesión |
| Datos | PostgreSQL 16; migraciones Django; diferencias del SQL lógico descritas en informe/04b |
| Comercio | Catálogo por perfil, registro B2C, stock transaccional, compra por rango, OC diferida, historial y soporte con orden propia |
| CRM | Cartera y prospectos, interacciones, avance secuencial, cierre ganado/perdido, pedidos asistidos y bandeja compartida |
| IA | Clasificador Gemini/Groq y chat Groq/Gemini por defecto; configuración independiente, falla controlada y reintento manual |
| Logística | Despacho compatible con el rango, seguimiento y ETA aproximada; cierre manual libera camión |
| IoT | CAM-01 a CAM-50 en cinco contenedores de diez; lecturas cada cinco segundos y movimiento hacia paradas |
| BI | Grafana (login obligatorio: **visor** para mirar, **admin** para editar); usuario SQL `grafana_ro` de solo lectura; refresco cada cinco segundos y cruce ventas-frío |
| AWS | VPC tres subredes, EC2 web y EC2 IoT, RDS privada Single-AZ; infraestructura definida en aws/ |

Para iniciar el entorno local se copia `.env.example` a `.env`, se completan secretos (incluidas `GRAFANA_DB_PASSWORD`, `GRAFANA_PASSWORD` y `GRAFANA_VISOR_PASSWORD`) y se utiliza `docker compose --env-file .env up -d --build`. La aplicación publica en `localhost` con `WEB_PUERTO` (por defecto 8000) y Grafana en `GRAFANA_PUERTO` (por defecto 3000); al abrir Grafana hay que iniciar sesión (no hay modo anónimo). Las pruebas deben usar la contraseña de fixtures exclusivamente dentro del contenedor de pruebas, sin modificar las cuentas de la instalación ordinaria. El montaje del código actual evita ensayar una imagen antigua. Claves en la nube: `docs/credenciales-y-cuentas.md` y `aws/README.md` (sección Grafana).

El registro de AWS del 22 de octubre es histórico. Los cambios posteriores requieren revalidación con `aws/verificar.py` sobre la misma revisión desplegada. Véanse `docs/revision-hito1-2026-10-25.md` y `informe/04e-plan-despliegue.md` para resultados y límites.

## Utilidades locales del equipo

Se conservan las utilidades incorporadas en la carpeta original durante esta revisión:

```bash
cp .env.example .env        # DB_PASSWORD, DEMO_PASSWORD y GRAFANA_* (ver .env.example)
docker compose --env-file .env up -d --build
./scripts/estado-local.sh   # comprobar git, contenedores y URLs
./scripts/logs-local.sh     # seguir web + flota en la terminal
```

La dirección AWS documentada por el equipo es http://54.82.100.161 y Grafana en http://54.82.100.161:3000 (login **visor** con `GRAFANA_VISOR_PASSWORD` en `secretos.env` del operador); puede no responder con el laboratorio detenido. La dirección vigente se consulta con `bash aws/provision.sh estado` o `aws/.estado/ip.txt`. Recorrido de prueba: `docs/guia-pruebas-aws.md`.
