# Backend Cofrial SpA (Django)

Proyecto `config` + app `core`: `/health/` (app y conexión a la BD) y `/catalogo/` (productos con precio según perfil, `?perfil=b2b` o `b2c`).

## Correr en local
```bash
cp .env.example .env            # en la raíz del repo; completar credenciales
createdb cofrial                # PostgreSQL local
psql cofrial -f informe/modelo/esquema.sql
psql cofrial -f informe/modelo/datos_prueba.sql
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver      # http://localhost:8000/catalogo/  (y /health/)
```

El esquema de datos vive en `informe/modelo/esquema.sql` (generado por `modelo.py`); los modelos de `core/models.py` son `managed=False` (leen las tablas existentes, sin migrarlas).
En AWS, `DB_HOST` apunta al endpoint de Amazon RDS.
