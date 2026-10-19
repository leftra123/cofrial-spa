from django.db import connection
from django.http import JsonResponse


def health(request):
    """Comprueba que la app responde y que la BD (local o RDS) es alcanzable."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db = "ok"
    except Exception as exc:
        db = f"error: {exc.__class__.__name__}"
    return JsonResponse({"app": "ok", "db": db}, status=200 if db == "ok" else 503)
