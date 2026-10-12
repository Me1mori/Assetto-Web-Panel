"""Carga del archivo `.env` (sin dependencias externas).

Solo define variables que **no** estén ya en el entorno: lo que exporta
systemd o la terminal siempre gana sobre el archivo. Si el archivo no existe
no pasa nada, así que el proyecto sigue arrancando sin él.
"""
import os
from pathlib import Path

ENV_FILE = Path(
    os.environ.get("ASSETO_ENV_FILE", ".env")
).expanduser()


def parse_env(text: str) -> dict:
    """Extraye pares clave=valor de un archivo .env sencillo.

    Admite comentarios con `#` al inicio de línea, `export` opcional y
    valores entre comillas simples o dobles.
    """
    values = {}

    for raw in text.splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line[len("export "):].strip()

        key, _, value = line.partition("=")
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if key.strip():
            values[key.strip()] = value

    return values


def load_env_file(path: Path | None = None) -> bool:
    """Carga el `.env` en `os.environ`. Devuelve si lo leyó."""
    path = path or ENV_FILE

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    for key, value in parse_env(text).items():
        os.environ.setdefault(key, value)

    return True