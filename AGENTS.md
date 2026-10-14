# AssettoServer — Panel de control

Panel web para encender, apagar y reiniciar un servidor dedicado de Assetto Corsa,
y consultar sus registros en tiempo real.

- **Backend:** FastAPI (Python) en `backend/`.
- **Frontend:** Astro 5 (estático) en `frontend/`, compilado a `frontend/dist`.

> **Memoria local:** rutas de esta máquina y estado cambiante en
> [`MEMORY.md`](./MEMORY.md) (no se versiona).

## Ejecución

```bash
# Backend
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env

# Frontend
cd frontend && npm install && npm run build && cd ..

# Producción (sin recarga, 127.0.0.1)
.venv/bin/python run.py

# Desarrollo (recarga automática)
.venv/bin/python dev.py
# En otra terminal:
cd frontend && npm run dev
```

## Configuración

Todo por variables de entorno (ver `.env.example`). Las esenciales:

| Variable | Para qué |
| --- | --- |
| `ASSETOSERVER_FOLDER` | Carpeta principal del servidor (`logs/`, `cfg/`, …) |
| `ASSETOSERVER_SERVICE_NAME` | Unidad systemd a controlar |
| `ASSETO_HOST` / `ASSETO_PORT` | Interfaz y puerto (producción) |
| `ASSETO_DEV_HOST` / `ASSETO_DEV_PORT` | Interfaz y puerto (desarrollo) |
| `ASTRO_API_TARGET` | Backend al que reenvía Astro en dev |
| `ASSETO_ALLOWED_ORIGINS` | Orígenes extra admitidos en los POST (CSRF) |
| `ASSETO_ENV_FILE` | Ruta del `.env` (por defecto `.env`) |

**No hay variables de credenciales** — el panel no tiene acceso que configurar.

## Convenciones

- Textos de UI y comentarios en español (es-mx).
- Prefijo de API: `/api/server/{status,logs,config,weather-presets,entry-list,tracks,available-cars,start,stop,restart}`. No hay más rutas.
- **Los inscritos contienen datos personales** (`GUID`, `DRIVERNAME`, `TEAM`).
  `entry_service` solo expone `MODEL`/`SKIN` + conteo: nunca devolverlos en crudo.
- **Prohibido gestionar usuarios o contraseñas.** No se añaden cuentas, registro,
  roles, sesiones, cookies, tokens ni HTTP Basic (`ASSETO_BASIC_*`, `auth.py`,
  `Authorization`, `401`). Solo una insistencia explícita del usuario puede reabrir el tema.
- **Los logs contienen datos personales** (Steam ID, IPs, chat). `log_service`
  los redacta antes de exponerlos: nunca devolverlos en crudo.
- **Las contraseñas del juego nunca se exponen.** `config_service` omite
  `PASSWORD` y `ADMIN_PASSWORD` de `server_cfg.ini` y solo informa si existen
  (`*_SET`).
- **Protección:** los tres POST y los PUT de `/config` y `/entry-list`
  comprueban el `Origin` (CSRF) antes de tocar `systemctl`, `server_cfg.ini` o
  `entry_list.ini`. Las lecturas
  (`/status`, `/logs`, `/config`, `/entry-list`, `/tracks`, `/available-cars`)
  no se comprueban.
- `backend/tests/test_api_sin_acceso.py` es la red de seguridad: falla si alguien
  reintroduce `401`, `WWW-Authenticate`, `auth.py` o rutas `/api/auth/*`.
- Iconos: SVG en `frontend/src/components/Icon.astro` (no emojis). Acepta `class`.
- Bitácora de desarrollo: `private/MEMORY.md` (no se versiona). Cada cambio o
  mejora se anota ahí primero; el mensaje del commit se redacta en base a lo
  anotado.
- `backend/paths.py` define `DIST_DIR`. No usar `Path("frontend/dist")` en otros módulos.
- Tests: `.venv/bin/pytest`. Fixtures en `backend/tests/conftest.py`.
- Lint: `.venv/bin/ruff check .`
- Sistema: los endpoints de control usan `systemctl` (requiere regla sudoers).
  Ver [`backend/services/README.md`](./backend/services/README.md).
