# AssettoServer

Panel web para encender, apagar y reiniciar un servidor dedicado de
[Assetto Corsa](https://assettocorsa.gg/assetto-corsa/), y seguir sus registros en
tiempo real.

## Características

- **Sin login.** No hay usuarios ni contraseñas: abres la página y todo funciona.
- **Control del servidor.** Botones para encender, apagar y reiniciar el servicio.
- **Logs en tiempo real.** Ves los registros del servidor sin conectarte por SSH.
- **Privacidad.** Los logs se redactan automáticamente (Steam ID, IPs, chat) antes
  de mostrarse.

## Requisitos

- Python 3.13+
- Node.js 20+
- Un servidor de Assetto Corsa instalado y configurado como servicio systemd

## Instalación rápida

```bash
# 1. Clona el repositorio y entra
cd Assetto-Web-Panel

# 2. Backend
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 3. Configura las rutas de tu servidor
cp .env.example .env
# Edita .env y ajusta ASSETOSERVER_FOLDER y ASSETOSERVER_SERVICE_NAME

# 4. Frontend
cd frontend && npm install && npm run build && cd ..

# 5. Arranca
.venv/bin/python run.py
```

Abre [http://127.0.0.1:9094](http://127.0.0.1:9094) en tu navegador.

## Desarrollo

```bash
.venv/bin/python dev.py          # Backend con recarga automática
cd frontend && npm run dev       # Frontend con hot-reload
```

Tests y lint:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

## Despliegue con systemd

```bash
sudo sed -e "s|__USER__|$USER|g" -e "s|__REPO__|$PWD|g" \
  backend/services/assetoserver.service \
  | sudo tee /etc/systemd/system/assetoserver.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart assetoserver
```

El servicio del juego y la regla de sudoers están en
[`backend/services/README.md`](./backend/services/README.md).

## Configuración

Ver [`.env.example`](./.env.example). Las variables principales:

| Variable | Para qué |
| --- | --- |
| `ASSETOSERVER_FOLDER` | Carpeta principal del servidor (`logs/`, `cfg/`) |
| `ASSETOSERVER_SERVICE_NAME` | Unidad systemd a controlar |
| `ASSETO_HOST` / `ASSETO_PORT` | Interfaz y puerto del backend |
| `ASSETO_ALLOWED_ORIGINS` | Orígenes extra admitidos en los POST (CSRF) |

## Seguridad

- **Sin autenticación.** Diseñado para uso personal en `127.0.0.1` o detrás de
  un proxy inverso (Cloudflare Access recomendado para acceso externo).
- **Protección CSRF.** Los botones de encender/apagar/reiniciar comprueban que la
  petición viene del mismo sitio.
- **Logs redactados.** Los datos personales (Steam ID, IPs, chat) se eliminan
  antes de mostrarse en el panel.

## Estructura

```
backend/          FastAPI, servicios systemd, tests
frontend/         Astro 5 (se compila a frontend/dist)
backend/services/ Plantillas systemd y documentación
```
