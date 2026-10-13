"""Lectura de los logs del servidor de Assetto Corsa.

Devuelve las líneas de la última ejecución, ya recortadas y redactadas. El
panel solo muestra esas líneas, así que no se extrae nada más del log.

⚠️ Estos logs contienen datos personales: identificadores de Steam, IPs
públicas y mensajes de chat. Todo lo que sale de aquí pasa primero por
`redact()`, de modo que la API nunca los expone en crudo.
"""
import os
import re
from datetime import datetime
from pathlib import Path

# Ruta de los logs de AssettoServer.
# En producción la define ASSETOSERVER_FOLDER (systemd / entorno).
# Sin esa variable se usa "logs" relativo a la raíz del repo, para que el
# proyecto sea portable y no lleve rutas personales dentro.
LOG_FOLDER = Path(
    os.environ.get("ASSETOSERVER_FOLDER") or "."
).expanduser() / "logs"

# Tope para que la respuesta no crezca sin límite durante una sesión larga.
MAX_LOG_LINES = int(
    os.environ.get("ASSETOSERVER_MAX_LOG_LINES", "500")
)

# ===================== Redacción de datos personales ======================
# SteamID64: 17 dígitos que empiezan por 7656
# (rango real 76561197960265728 - 76561198788406271).
STEAM_ID = re.compile(r"\b7656\d{13}\b")
# IPv4 con puerto opcional.
IP_ADDRESS = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b")
# Línea de chat: "CHAT: Jugador (12): mensaje".
CHAT_LINE = re.compile(r"^(?P<head>CHAT:\s*[^:]*:)\s*(?P<msg>.*)$")

STEAM_PLACEHOLDER = "7656…id"
IP_PLACEHOLDER = "ip.oculta"


def redact(message):
    """Quita datos personales de una línea de log.

    Sustituye el Steam ID, la IP y el texto del chat por marcadores neutros.
    """
    if not message:
        return message

    match = CHAT_LINE.match(message)
    if match:
        message = f"{match.group('head')} [mensaje oculto]"

    message = STEAM_ID.sub(STEAM_PLACEHOLDER, message)

    # Se conserva el puerto porque no es dato personal y ayuda a diagnosticar.
    return IP_ADDRESS.sub(
        lambda m: f"{IP_PLACEHOLDER}{m.group(1) or ''}",
        message
    )


# ========================== Lectura del archivo ==============================
def get_current_log_file():
    today = datetime.now().strftime("%Y%m%d")
    return LOG_FOLDER / f"log-{today}.txt"


# Caché del archivo parseado, indexada por (ruta, mtime, tamaño).
# Evita volver a leer y parsear el archivo entero en cada consulta cuando el
# servidor no ha escrito nada nuevo.
_cache = {
    "key": None,
    "lines": ()
}


def _file_key(file: Path):
    """Identifica la versión del archivo en disco, o None si no existe."""
    try:
        stat = file.stat()
    except OSError:
        return None

    return (str(file), stat.st_mtime_ns, stat.st_size)


def read_current_log():
    file = get_current_log_file()
    key = _file_key(file)

    if key is None:
        _cache["key"] = None
        _cache["lines"] = ()
        return []

    if key == _cache["key"]:
        return list(_cache["lines"])

    with file.open(
        encoding="utf-8",
        errors="ignore"
    ) as f:
        lines = f.readlines()

    _cache["key"] = key
    _cache["lines"] = lines

    return lines


# ========================== Buscar última ejecución ==========================
# Línea de arranque real del servidor, por ejemplo:
#   2026-10-12 01:23:47.416 +01:00 [INF] AssettoServer 0.0.54+51737e2c2e
# Se ancla a esa forma exacta: buscar la palabra "AssettoServer" suelta
# también encontraba las líneas de un stack trace de .NET y hacía que
# `parse_logs()` devolviera la lista de logs vacía.
SERVER_BANNER = re.compile(
    r"AssettoServer\s+\d+\.\d+\.\d+\+[0-9a-fA-F]+"
)


def find_last_server_start(lines):
    start_index = 0

    for index, line in enumerate(lines):
        if SERVER_BANNER.search(line):
            start_index = index

    return lines[start_index:]


# ========================== Parser principal =================================
def parse_logs():
    """Líneas de la última ejecución del servidor, ya redactadas.

    Devuelve solo los registros que el panel muestra. Lo que no se expone no se
    parsea: aquí no se extraen sesión, pista, coches, jugadores ni vueltas
    porque la interfaz no los usa, y en esas líneas es donde aparecen los datos
    personales.
    """
    lines = read_current_log()

    if not lines:
        return empty_state()

    logs = []
    for line in find_last_server_start(lines):
        parsed = parse_log_line(line)

        if parsed:
            logs.append(parsed)

    # Se recorta al final para que una sesión larga no produzca una respuesta
    # enorme ni mantenga listas sin límite en memoria.
    return {"logs": logs[-MAX_LOG_LINES:]}


# ========================== Estado inicial ===================================
def empty_state():
    return {"logs": []}


# ========================== Parse línea base =================================
LOG_PATTERN = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>[\d:.]+).*?"
    r"\[(?P<level>\w+)\]\s+"
    r"(?P<message>.*)"
)


def parse_log_line(line):
    match = LOG_PATTERN.match(line)

    if not match:
        return None

    return {
        "time": match.group("time"),
        "level": match.group("level"),
        "message": redact(match.group("message").strip())
    }
