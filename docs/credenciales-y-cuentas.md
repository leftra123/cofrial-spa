# Credenciales y cuentas: cómo se crean, dónde viven y cómo se cambian

> Regla de oro: **las claves de la infraestructura (AWS, base de datos, Grafana, Django y las APIs de IA) no van a GitHub, Trello, el chat ni una captura de pantalla.** Para leer una, usar el panel Terminal. **Excepción deliberada del prototipo académico:** las cuentas de demostración usan correos simples (`@cofrial.cl` para el personal) y una clave fácil, y se documentan en el Anexo B del informe, porque solo las usa el equipo y quienes evalúan, con datos ficticios.

## 1. Mapa de credenciales

| Credencial | Qué es | Dónde vive | Cómo se crea o se renueva |
|---|---|---|---|
| **AWS (Learner Lab)** | Llaves temporales de la sesión del laboratorio; caducan a las 4 horas | `~/.aws/credentials` (computador de quien opera) | AWS Academy, Learner Lab, **Start Lab**; esperar el círculo verde; AWS Details, AWS CLI, **Show**; copiar el bloque que empieza con `[default]` y ejecutar `pbpaste > ~/.aws/credentials`. Verificar con `aws ec2 describe-addresses --query 'Addresses[0].PublicIp' --output text` (debe devolver la IP). |
| **Claves generadas** (base, Grafana, Django, cuentas de demostración) | `DB_PASSWORD`, `GRAFANA_DB_PASSWORD`, `GRAFANA_PASSWORD`, `DJANGO_SECRET_KEY`, `DEMO_PASSWORD` | `aws/.estado/secretos.env` (ignorado por git) | Las genera sola la primera vez `bash aws/provision.sh` (20 caracteres al azar). Para leer una: `grep '^DEMO_PASSWORD=' aws/.estado/secretos.env \| cut -d= -f2-` en el **panel Terminal**. |
| **Gemini** | Clave de la IA principal | `GEMINI_API_KEY` en `secretos.env` | https://aistudio.google.com/apikey con la **cuenta institucional**; sin tarjeta. |
| **Groq** | Clave de la IA de respaldo | `GROQ_API_KEY` en `secretos.env` | https://console.groq.com, crear una API key; sin tarjeta. |
| **Llave SSH** | `cofrial-key.pem`, para entrar a las EC2 | `aws/.estado/` | La crea el script. (En la EC2 web recreada el SSH hoy rechaza conexiones; no es necesaria para operar.) |

**Cambiar cualquier clave de `secretos.env`:** editar el archivo con el editor (no con capturas ni pegándola en un chat), guardar, y ejecutar `bash aws/provision.sh recrear-web` (la web queda sin servicio unos 8 minutos). Excepciones:
- **`DB_PASSWORD` no se cambia así**: la clave real vive en RDS; cambiar solo el archivo deja la aplicación sin acceso a la base. Cambiarla exige modificar RDS y el archivo a la vez.
- **Si alguna clave de IA se filtró, revocarla primero** en su consola (AI Studio o Groq) y crear una nueva.

## 2. Cuentas de acceso a la aplicación

Hay dos formas. En AWS se usa la primera porque no requiere entrar a la máquina.

### A. Desde la web de administración (`/admin/`), sin comandos
Entrar a `http://IP/admin/` como `admin`.

| Quiero crear | Pasos |
|---|---|
| **Vendedor** | Usuarios, Agregar (usuario y clave; marcar **Es staff**); en Grupos elegir **vendedores**. Luego Vendedores, Agregar: elegir ese usuario y poner el nombre. |
| **Gerencia** | Usuarios, Agregar con **Es staff**; Grupos: **gerencia**. |
| **Despachador** | Usuarios, Agregar con **Es staff**; Grupos: **despachadores**. |
| **Cliente (B2B o B2C)** | Usuarios, Agregar (sin Es staff). Luego Clientes, Agregar: elegir el usuario, el tipo (B2B o B2C), RUT, nombre y correo, y el vendedor si es B2B; en la parte de abajo, agregar su **dirección** (marcar «es principal»). |
| **Administrador** | Solo por comando (sección B): un administrador tiene todos los permisos. |

Para cambiar la clave de alguien: Usuarios, abrir el usuario, enlace «este formulario» junto a la clave.

### B. Con comandos (en un computador con el proyecto, o dentro del contenedor)
Se ejecutan desde la carpeta `web/`. En AWS exigen entrar a la EC2 (`docker compose -f aws/docker-compose.web.yml --env-file .env exec web python manage.py ...`), hoy no disponible por SSH.

```bash
# Vendedor
python manage.py crear_cuenta jefa@cofrial.test --rol vendedor --nombre "Camila Soto"
# Gerencia, despachador o administrador
python manage.py crear_cuenta gerencia2@cofrial.test --rol gerencia
python manage.py crear_cuenta sergio --rol admin
# Cliente institucional (B2B), con vendedor asignado
python manage.py crear_cuenta compras@hotel.test --rol cliente-b2b --nombre "Hotel Villarrica" \
    --rut 76.111.222-3 --direccion "Av. Pedro de Valdivia 100" --comuna Temuco --vendedor vendedora@cofrial.cl
# Cliente público (B2C)
python manage.py crear_cuenta ana2@correo.test --rol cliente-b2c --nombre "Ana Díaz" --rut 11.222.333-4 --direccion "Calle 1 123"
```

La clave se **pide por teclado** (dos veces) y se valida (largo mínimo y no una clave común). Los errores son claros: usuario o RUT repetido, comuna inexistente (lista las que existen), vendedor inexistente. Si algo falla no queda nada creado a medias. Para cambiar la clave de una cuenta existente: `python manage.py changepassword usuario`.

## 3. Cuentas de demostración y su clave

Las crea `cargar_demo` (ver `docs/guia-pruebas-aws.md`). Si existían con los nombres anteriores, las renombra sin perder sus datos.

| Cuenta | Rol |
|---|---|
| `eric@cofrial.cl` | Administrador (Eric): despacha en la demostración |
| `felipe@cofrial.cl` | Cliente institucional B2B (Felipe Henríquez) |
| `sergio@cofrial.cl` | Cliente particular B2C (Sergio Vásquez) |
| `admin@cofrial.cl` | Administrador |
| `gerencia@cofrial.cl` | Gerencia |
| `vendedora@cofrial.cl` | Vendedora (María Paz Soto) |
| `vendedor2@cofrial.cl` | Vendedor (Pedro Núñez) |
| `despacho@cofrial.cl` | Despachador |
| `abastecimiento@hospital.test` | Cliente institucional B2B (Hospital Regional de Temuco) |
| `ana@correo.test` | Cliente particular B2C (Ana Pérez) |

Todas comparten `DEMO_PASSWORD`; en AWS vale `123456` (con `DEMO_CLAVE_DEBIL=1`). *Supermercados del Sur* es un cliente del CRM **sin cuenta de acceso**. Los clientes particulares nuevos se registran solos en `/cuenta/registro/`.

**Rotar la clave de demostración** (por ejemplo, tras compartirla por error):
1. Editar `DEMO_PASSWORD` en `aws/.estado/secretos.env` (mínimo 8 caracteres, no una clave común).
2. `bash aws/provision.sh recrear-web`. El contenedor web ejecuta `cambiar_clave_demo` en cada arranque y actualiza **solo** esas siete cuentas. Cualquier cuenta que se haya creado a mano conserva su clave.
3. En local: `DEMO_PASSWORD=la-nueva python manage.py cambiar_clave_demo`.

## 4. Consola web de AWS

La consola sirve para mirar y encender cosas, pero **cada región muestra solo lo suyo**. La instalación está en **N. Virginia (`us-east-1`)**: arriba a la derecha, el selector de región debe decir **«Este de EE. UU. (Norte de Virginia)»**. Si dice São Paulo u otra, EC2 y RDS aparecerán vacíos. Desde ahí se ven las instancias `cofrial-ec2-web` y `cofrial-ec2-iot`, la base `cofrial-db` y la IP elástica; también sirve para encender lo que haya quedado apagado.
