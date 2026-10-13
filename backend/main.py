import os

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.paths import DIST_DIR
from backend.routes.api import router as api_router
from backend.routes.pages import router as pages_router

app = FastAPI()

# Cabeceras Host permitidas. Vacío = sin restricción (valor por defecto para
# no romper despliegues); en producción conviene fijar ASSETO_ALLOWED_HOSTS.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ASSETO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

if ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=ALLOWED_HOSTS
    )

# Cabeceras de seguridad básicas. El panel sirve HTML propio y expone rutas
# que mueven el servidor de juego, así que interesa que nadie lo incruste en un
# iframe ni que un navegador "adivine" el tipo de contenido de la respuesta.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    # El panel no carga nada externo: se bloquea cualquier CDN, fuente o
    # imagen de terceros que alguien pudiera colar en una futura plantilla.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), interest-cohort=()"
    )
    return response


app.include_router(pages_router)
app.include_router(api_router)


# Recursos generados por Astro (CSS con hash, favicon, etc.).
# `check_dir=False` permite arrancar el servidor antes del primer build.
app.mount(
    "/_astro",
    StaticFiles(directory=DIST_DIR / "_astro", check_dir=False),
    name="astro-assets"
)
app.mount(
    "/assets",
    StaticFiles(directory=DIST_DIR / "assets", check_dir=False),
    name="assets"
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception(request: Request, exc: StarletteHTTPException):

    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        # Página 404 de Astro; mientras no exista, respuesta de texto.
        # Las rutas /api/* siempre responden JSON para que el frontend
        # pueda leer el `detail` (p. ej. falta server_cfg.ini).
        not_found = DIST_DIR / "404.html"
        if not_found.is_file():
            return FileResponse(not_found, status_code=404)

        return PlainTextResponse(
            "404 — Ejecuta `npm run build` dentro de frontend/.",
            status_code=404
        )

    # El resto (403 por CSRF, 502 por systemctl…) con el JSON estándar de
    # FastAPI. Antes se relanzaba la excepción aquí, y eso convertía todos
    # esos errores en un 500 sin cuerpo: el frontend nunca recibía el `detail`
    # que necesita para explicar qué pasó.
    return await http_exception_handler(request, exc)
