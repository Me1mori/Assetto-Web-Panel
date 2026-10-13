from fastapi import APIRouter, HTTPException, Request

from backend.security import check_same_origin
from backend.services import config_service, log_service, server_service

router = APIRouter(
    prefix="/api/server",
    tags=["Server"]
)

# Ninguna ruta pide credenciales. Este panel es una herramienta para encender y
# apagar **tu** servidor, no una web con cuentas: no hay usuarios, contraseñas,
# sesiones ni cookies, y no se añaden.
#
# Lo único que se comprueba es el `Origin` de los POST, para que otra web no
# pueda disparar el apagado desde el navegador de un visitante (CSRF). El
# razonamiento completo está en AGENTS.md y en el README.
#
# Estas rutas se declaran con `def` (síncronas) y no con `async def`: las
# llamadas a `systemctl` y la lectura de logs son bloqueantes, y ejecutarlas
# dentro del event loop dejaría toda la API colgada mientras tanto. FastAPI
# las ejecuta en un hilo aparte automáticamente.


def _upstream(action, name=None):
    """Ejecuta una llamada a systemctl y traduce su fallo a 502.

    `systemctl` falla por motivos que el frontend debe poder explicar (sudo
    denegado, unidad inexistente, comando colgado), así que el detalle real
    viaja en el cuerpo del 502 en vez de un 500 sin mensaje.
    """
    try:
        return action()
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        ) from error


@router.get("/status")
def server_status():
    return _upstream(server_service.status)


@router.get("/logs")
def server_logs():
    return log_service.parse_logs()


@router.get("/config")
def server_config():
    config = config_service.get_config()
    if "error" in config:
        raise HTTPException(status_code=404, detail=config["error"])
    return config


@router.get("/weather-presets")
def weather_presets():
    return {"presets": config_service.get_weather_presets()}


@router.put("/config")
def server_config_update(request: Request, updates: dict):
    check_same_origin(request)
    try:
        return _upstream(lambda: config_service.write_config(updates))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/start")
def server_start(request: Request):
    check_same_origin(request)
    return _control(server_service.start, "start")


@router.post("/stop")
def server_stop(request: Request):
    check_same_origin(request)
    return _control(server_service.stop, "stop")


@router.post("/restart")
def server_restart(request: Request):
    check_same_origin(request)
    return _control(server_service.restart, "restart")


def _control(action, name):
    """Ejecuta la acción de control y confirma al frontend que salió bien."""
    _upstream(action)

    return {
        "success": True,
        "action": name
    }