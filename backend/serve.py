"""Arranque del servidor, compartido por producción (`run.py`) y desarrollo
(`dev.py`).

Ambos scripts llamaban a `uvicorn.run` con la misma lista de argumentos, y solo
cambiaban el prefijo de las variables de entorno y el `reload`. Aquí vive esa
llamada una sola vez.
"""
import os

import uvicorn

APP = "backend.main:app"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "9094"


def serve(prefix: str, reload: bool):
    """Levanta el panel.

    `prefix` elige el juego de variables: `ASSETO_` en producción (el que lee
    la unidad systemd) y `ASSETO_DEV_` en desarrollo.
    """
    host = os.environ.get(f"{prefix}HOST", DEFAULT_HOST)
    port = int(os.environ.get(f"{prefix}PORT", DEFAULT_PORT))

    uvicorn.run(APP, host=host, port=port, reload=reload)