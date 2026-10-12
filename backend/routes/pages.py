from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.paths import DIST_DIR

router = APIRouter()


def page(path: str):
    file = DIST_DIR / path
    if not file.is_file():
        # Aún no se ha construido el frontend: 404 gestionado.
        raise HTTPException(status_code=404)
    return FileResponse(file)


@router.get("/")
async def index():
    return page("index.html")


@router.get("/config")
async def config():
    return page("config/index.html")


@router.get("/menu")
async def menu():
    return page("menu/index.html")
