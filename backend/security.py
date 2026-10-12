"""Protección CSRF de las rutas de control.

El panel enciende y apaga el servidor de juego y no pide credenciales (ver
`backend/routes/api.py`), así que esto es **lo único** que impide que otra web
dispare esas acciones desde el navegador de un visitante.
"""
import os

from fastapi import HTTPException, Request

# Orígenes extra permitidos, separados por comas.
# Vacío = solo se acepta el mismo origen que sirve la página.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ASSETO_ALLOWED_ORIGINS",
        ""
    ).split(",")
    if origin.strip()
]


def request_origin(request: Request) -> str:
    """Origen del propio request (esquema + Host)."""
    return f"{request.url.scheme}://{request.headers.get('host', '')}"


def check_same_origin(request: Request) -> None:
    """Rechaza peticiones que vienen de otra web.

    Un POST sin cabecera `Origin` (curl, tests) no se rechaza: en un navegador
    los POST siempre la envían, así que su presencia delata el intento externo.
    """
    origin = request.headers.get("origin")

    if not origin:
        return

    if origin == request_origin(request) or origin in ALLOWED_ORIGINS:
        return

    raise HTTPException(
        status_code=403,
        detail="Origen no permitido para esta acción."
    )