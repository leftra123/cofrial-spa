# Backend Cofrial SpA (Django)

Proyecto `config` + app `core`: `/health/` (app y conexión a la BD) y `/catalogo/` (productos con precio según perfil, `?perfil=b2b` o `b2c`), `/carrito/` y `/orden/<id>/`.

**Compra:** elige un cliente en «Comprar como… (demo)» (sustituto temporal del login), agrega productos y confirma. La orden se genera con estado «Recibida» y el stock se descuenta en la misma transacción, con los productos bloqueados (`core/servicios.py`, reglas RN-01 a RN-06 de `informe/04c`). Si una línea no tiene stock suficiente no se guarda nada. B2B debe indicar su n.º de orden de compra.

## Correr en local
```bash
cp .env.example .env            # en la raíz del repo; completar credenciales
createdb cofrial                # PostgreSQL local
psql cofrial -f informe/modelo/esquema.sql
psql cofrial -f informe/modelo/datos_prueba.sql
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate         # crea solo las tablas de sesiones y admin de Django
python manage.py runserver      # http://localhost:8000/catalogo/  (y /health/)
```

El esquema de datos vive en `informe/modelo/esquema.sql` (generado por `modelo.py`); los modelos de `core/models.py` son `managed=False` (leen las tablas existentes, sin migrarlas).
En AWS, `DB_HOST` apunta al endpoint de Amazon RDS.
