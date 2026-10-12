"""Rutas del proyecto, en un solo sitio.

`DIST_DIR` estaba definido a la vez en `main.py` y en `routes/pages.py`, y en
los dos como ruta relativa: si alguien arrancaba el servidor desde otro
directorio, los montajes de estáticos y las páginas apuntaban a sitios
distintos. Se calcula desde la ubicación de este archivo, así que da igual
desde dónde se ejecute.
"""
from pathlib import Path

# backend/ -> raíz del repositorio
ROOT_DIR = Path(__file__).resolve().parents[1]

# Salida estática de Astro (se genera con `npm run build` en frontend/).
DIST_DIR = ROOT_DIR / "frontend/dist"