"""Arranque en producción.

Sin recarga automática y escuchando solo en localhost por defecto: el panel
debe quedar detrás de un proxy inverso (túnel, nginx, Caddy…), nunca expuesto
directo a la red. Para desarrollo usar `dev.py`.

Variables: `ASSETO_HOST` y `ASSETO_PORT`.
"""
from backend.serve import serve

if __name__ == "__main__":
    serve("ASSETO_", reload=False)