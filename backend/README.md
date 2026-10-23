# Backend Cofrial SpA (Django)

Proyecto `config` + app `core`: `/health/` (app y conexión a la BD) y `/catalogo/` (productos con precio según perfil, `?perfil=b2b` o `b2c`), `/entrar/`, `/registro/`, `/carrito/`, `/pedidos/` y `/orden/<id>/`.

**Cuentas:** inicio de sesión sobre la tabla `usuario` (contraseñas con PBKDF2 de Django, límite de 5 intentos fallidos por 15 min, sesión renovada al entrar) y registro de clientes B2C con RUT validado. Los B2B los crea Cofrial. `/pedidos/` lista los pedidos del cliente.

**Cuentas de prueba** (solo desarrollo; las asigna `python manage.py poner_claves_demo`): `abastecimiento@hospital.test` (B2B) y `ana@correo.test` (B2C), contraseña `Cofrial2026!`.

**Compra:** con sesión iniciada, agrega productos y confirma. La orden se genera con estado «Recibida» y el stock se descuenta en la misma transacción, con los productos bloqueados (`core/servicios.py`, reglas RN-01 a RN-06 de `informe/04c`). Si una línea no tiene stock suficiente no se guarda nada. B2B debe indicar su n.º de orden de compra.

## Correr en local

**Opción rápida con Docker** (sin instalar PostgreSQL ni Python; no se probó en esta sesión porque el contenedor de desarrollo no tiene el servicio de Docker):
```bash
docker compose up --build       # desde la raíz del repo; abre http://localhost:8000/catalogo/
docker compose down -v          # para borrar la BD y recargar los datos de prueba
```

**Opción manual:**
```bash
cp .env.example .env            # en la raíz del repo; completar credenciales
createdb cofrial                # PostgreSQL local
psql cofrial -f informe/modelo/esquema.sql
psql cofrial -f informe/modelo/datos_prueba.sql
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate         # crea solo las tablas de sesiones y admin de Django
python manage.py poner_claves_demo   # contraseña de prueba para los usuarios del script de datos
python manage.py runserver      # http://localhost:8000/catalogo/  (y /health/)
```

El esquema de datos vive en `informe/modelo/esquema.sql` (generado por `modelo.py`); los modelos de `core/models.py` son `managed=False` (leen las tablas existentes, sin migrarlas).
En AWS, `DB_HOST` apunta al endpoint de Amazon RDS.
