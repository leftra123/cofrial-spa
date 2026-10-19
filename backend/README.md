# Backend Cofrial SpA (Django)

Scaffold mínimo: proyecto `config` + app `core` con `/health/` (app y conexión a la BD).

## Correr en local
```bash
cp .env.example .env            # en la raíz del repo; completar credenciales
createdb cofrial                # PostgreSQL local
psql cofrial -f informe/modelo/esquema.sql
psql cofrial -f informe/modelo/datos_prueba.sql
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver      # http://localhost:8000/health/
```

El esquema de datos vive en `informe/modelo/esquema.sql` (generado por `modelo.py`); aún no hay modelos Django.
En AWS, `DB_HOST` apunta al endpoint de Amazon RDS.
