"""Crea (si no existe) el usuario de solo lectura que usa Grafana, con permiso solo para consultar."""
import os

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Crea el rol de solo lectura del tablero de BI (grafana_ro)."

    def handle(self, *args, **opciones):
        clave = os.environ.get("GRAFANA_DB_PASSWORD")
        if not clave:
            self.stdout.write("GRAFANA_DB_PASSWORD no está definida: se omite la creación del usuario del tablero.")
            return
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro'")
            existe = c.fetchone() is not None
            c.execute(f"{'ALTER' if existe else 'CREATE'} ROLE grafana_ro LOGIN PASSWORD %s", [clave])
            c.execute("SELECT current_database()")
            bd = c.fetchone()[0]
            c.execute(f'GRANT CONNECT ON DATABASE "{bd}" TO grafana_ro')
            c.execute("GRANT USAGE ON SCHEMA public TO grafana_ro")
            c.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_ro")
            c.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_ro")
        self.stdout.write(self.style.SUCCESS("Usuario de solo lectura del tablero listo."))
