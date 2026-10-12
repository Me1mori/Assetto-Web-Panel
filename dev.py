"""Arranque en desarrollo, con recarga automática al guardar.

Para exponerlo a otro dispositivo de la red (p. ej. probar desde el portátil)
usar `ASSETO_DEV_HOST=0.0.0.0` — solo en desarrollo.

Variables: `ASSETO_DEV_HOST` y `ASSETO_DEV_PORT`.
"""
from backend.serve import serve

if __name__ == "__main__":
    serve("ASSETO_DEV_", reload=True)