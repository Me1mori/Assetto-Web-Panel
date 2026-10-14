"""Lectura y edición de los coches (`entry_list.ini`).

La lista de inscritos vive en `cfg/entry_list.ini`, con una sección
`[CAR_N]` por plaza. Cada sección trae `MODEL` y `SKIN` (lo único editable
desde la web) junto a datos de jugadores (`GUID`, `DRIVERNAME`, `TEAM`) que
**nunca** salen de aquí: son identificadores personales, igual que el Steam ID
de los logs (ver `log_service`).

Lo que expone `get_entry_list()` por coche es solo `{index, model, skin}`,
más un resumen agrupado por modelo `{model, count, skins}`. El resto de claves
(`SPECTATOR_MODE`, `BALLAST`, `AI`, …) se conservan en disco pero no se
devuelven ni se aceptan por API.
"""
import configparser
import re
from pathlib import Path

# Claves con datos de jugadores: jamás se devuelven ni se aceptan.
SECRET_KEYS = frozenset({"GUID", "DRIVERNAME", "TEAM"})

CAR_SECTION = re.compile(r"^CAR_(\d+)$")

# Coches y pistas disponibles en `content/`. Si la carpeta no existe (tests),
# la validación de existencia se omite y solo se comprueba el formato.
MAX_CARS = 128
NAME_LEN = 120


def get_server_folder() -> Path:
    """Carpeta principal, igual que en `config_service` (por llamada)."""
    from backend.services import config_service

    return config_service.get_server_folder()


def get_entry_file() -> Path:
    """Ruta a `cfg/entry_list.ini`."""
    return get_server_folder() / "cfg" / "entry_list.ini"


def _strip_quotes(value: str) -> str:
    """Quita las comillas que Assetto pone a los SKIN con espacios."""
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _quote_skin(skin: str) -> str:
    """Entrecomilla el SKIN si lleva espacios o comillas (formato AC)."""
    if not skin or skin == "auto":
        return skin
    if re.search(r"[\s\"']", skin):
        inner = skin.replace("'", "")
        return f"'{inner}'"
    return skin


def _parse_entry(text: str) -> tuple:
    """Parsea el INI a `{indice: {clave: valor}}` + comentarios de cabecera."""
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read_string(text if text.endswith("\n") else text + "\n")

    cars: dict = {}
    for section in parser.sections():
        match = CAR_SECTION.match(section)
        if not match:
            continue
        cars[int(match.group(1))] = dict(parser.items(section))

    header: list = []
    for line in text.splitlines():
        if line.strip().startswith("["):
            break
        header.append(line)
    return cars, header


def get_entry_list() -> dict:
    """Coches inscritos, sin datos de jugadores.

    Devuelve `{"cars": [{index, model, skin}], "total": N, "models": [...]}`.
    Si falta el archivo, `{"error": ...}` (la API lo convierte en 404).
    """
    entry_file = get_entry_file()
    if not entry_file.is_file():
        return {"error": f"No se encontró {entry_file}"}

    try:
        text = entry_file.read_text(encoding="utf-8")
    except OSError as error:
        return {"error": f"No se pudo leer {entry_file}: {error}"}

    cars, _ = _parse_entry(text)
    result = []
    for index in sorted(cars):
        values = cars[index]
        result.append(
            {
                "index": index,
                "model": (values.get("MODEL") or "").strip(),
                "skin": _strip_quotes(values.get("SKIN") or ""),
            }
        )

    groups: dict = {}
    for car in result:
        group = groups.setdefault(
            car["model"], {"model": car["model"], "count": 0, "skins": []}
        )
        group["count"] += 1
        if car["skin"] not in group["skins"]:
            group["skins"].append(car["skin"])

    return {
        "cars": result,
        "total": len(result),
        "models": sorted(groups.values(), key=lambda g: g["model"]),
    }


def get_available_cars() -> list:
    """Modelos instalados en `content/cars` con sus skins.

    Lista de `{model, skins}` ordenada. Vacío si la carpeta no existe: el
    formulario usa texto libre. `auto` siempre vale como skin (aleatoria).
    """
    folder = get_server_folder() / "content" / "cars"
    try:
        models = sorted(
            entry.name
            for entry in folder.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []

    available = []
    for model in models:
        skins_dir = folder / model / "skins"
        try:
            skins = sorted(
                entry.name
                for entry in skins_dir.iterdir()
                if entry.is_dir() and not entry.name.startswith(".")
            )
        except OSError:
            skins = []
        available.append({"model": model, "skins": skins})
    return available


def get_tracks() -> list:
    """Pistas instaladas en `content/tracks`, ordenadas por nombre."""
    folder = get_server_folder() / "content" / "tracks"
    try:
        names = sorted(
            entry.name
            for entry in folder.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []
    return [{"name": name, "label": name} for name in names]


def _clean_name(value, campo: str) -> str:
    if value is None:
        raise ValueError(f"Coche: {campo} no puede estar vacío.")
    text = str(value).strip().replace("\r", "").replace("\n", "")
    if not text or len(text) > NAME_LEN:
        raise ValueError(f"Coche: {campo} entre 1 y {NAME_LEN} caracteres.")
    if "/" in text or "\\" in text or text in (".", "..") or ".." in text:
        raise ValueError(f"Coche: {campo} no admite rutas.")
    return text


def validate_entry_cars(cars) -> list:
    """Valida la lista completa de `[{model, skin}]`. Devuelve limpia."""
    if not isinstance(cars, list) or not cars:
        raise ValueError("Sin coches que guardar.")
    if len(cars) > MAX_CARS:
        raise ValueError(f"Máximo {MAX_CARS} coches.")

    available = {item["model"]: item["skins"] for item in get_available_cars()}

    clean = []
    for position, car in enumerate(cars):
        if not isinstance(car, dict):
            raise ValueError(f"Coche {position}: formato inválido.")
        model = _clean_name(car.get("model"), "MODEL")
        skin = _clean_name(car.get("skin"), "SKIN")
        if available:
            if model not in available:
                raise ValueError(f"Coche {position}: modelo no instalado.")
            if skin != "auto" and skin not in available[model]:
                raise ValueError(
                    f"Coche {position}: skin no instalada para ese modelo."
                )
        clean.append({"model": model, "skin": skin})
    return clean


def write_entry_list(cars) -> dict:
    """Reemplaza `MODEL`/`SKIN` de todas las plazas y devuelve la lista nueva.

    Las demás claves por plaza (`GUID`, `DRIVERNAME`, `TEAM`, `BALLAST`,
    `AI`, …) se conservan cuando la plaza ya existía; las plazas nuevas usan
    los valores por defecto del juego. Escritura atómica (temporal + renombre).
    """
    clean = validate_entry_cars(cars)
    entry_file = get_entry_file()

    if not entry_file.is_file():
        raise FileNotFoundError(f"No se encontró {entry_file}")

    try:
        text = entry_file.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(f"No se pudo leer {entry_file}: {error}") from error

    previous, header = _parse_entry(text)

    output: list = []
    for line in header:
        output.append(line)

    for index, car in enumerate(clean):
        old = previous.get(index, {})
        output.append(f"[CAR_{index}]")
        output.append(f"MODEL={car['model']}")
        output.append(f"SKIN={_quote_skin(car['skin'])}")
        output.append(f"SPECTATOR_MODE={old.get('SPECTATOR_MODE', '0')}")
        # Los datos de jugadores se conservan en disco pero nunca se exponen
        # ni se aceptan por API: aquí solo se copian los que ya había.
        output.append(f"DRIVERNAME={old.get('DRIVERNAME', '')}")
        output.append(f"TEAM={old.get('TEAM', '')}")
        output.append(f"GUID={old.get('GUID', '')}")
        output.append(f"BALLAST={old.get('BALLAST', '0')}")
        output.append(f"AI={old.get('AI', 'auto')}")

    tmp = entry_file.with_suffix(".ini.tmp")
    try:
        tmp.write_text("\n".join(output) + "\n", encoding="utf-8")
        tmp.replace(entry_file)
    except OSError as error:
        raise OSError(f"No se pudo escribir {entry_file}: {error}") from error

    return get_entry_list()


def get_entry_file_path() -> Path:
    """Ruta del archivo (para tests y mensajes de error)."""
    return get_entry_file()
