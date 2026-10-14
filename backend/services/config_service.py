"""Lectura de la configuración del servidor (server_cfg.ini).

La carpeta principal del servidor llega por `ASSETOSERVER_FOLDER` y de ahí se
derivan las subcarpetas (`logs/`, `cfg/`, `content/`…).

⚠️ Nunca se exponen contraseñas: las claves `PASSWORD` y `ADMIN_PASSWORD` no
salen de aquí. En su lugar se devuelve `<CLAVE>_SET` (booleano) para indicar
si hay algo configurado, sin revelar el valor.
"""
import configparser
import os
import re
from pathlib import Path

# Claves que jamás se devuelven, en ninguna sección.
SECRET_KEYS = frozenset({"PASSWORD", "ADMIN_PASSWORD"})


def get_server_folder() -> Path:
    """Carpeta principal del servidor, resuelta en cada llamada.

    Se lee aquí (y no solo al importar) para que los tests con `monkeypatch`
    y los cambios de entorno en caliente funcionen.
    """
    return Path(
        os.environ.get("ASSETOSERVER_FOLDER") or "."
    ).expanduser()


def get_config_file() -> Path:
    """Ruta a `cfg/server_cfg.ini` dentro de la carpeta principal."""
    return get_server_folder() / "cfg" / "server_cfg.ini"


# Traducción al español de los presets de content/weather. Los que no estén
# aquí (carpetas personalizadas) se muestran con su nombre original.
PRESET_LABELS: dict = {
    "1_heavy_fog": "Niebla densa",
    "2_light_fog": "Niebla ligera",
    "3_clear": "Despejado",
    "4_mid_clear": "Casi despejado",
    "5_light_clouds": "Pocas nubes",
    "6_mid_clouds": "Medio nublado",
    "7_heavy_clouds": "Muy nublado",
    "sol_00_no_clouds": "Sin nubes",
    "sol_01_clear": "Despejado",
    "sol_02_few_clouds": "Pocas nubes",
    "sol_03_scattered_clouds": "Nubes dispersas",
    "sol_04_windy": "Ventoso",
    "sol_05_broken_clouds": "Nubes fragmentadas",
    "sol_06_overcast": "Cubierto",
    "sol_11_mist": "Neblina",
    "sol_12_fog": "Niebla",
    "sol_21_haze": "Calima",
    "sol_22_dust": "Polvo",
    "sol_23_sand": "Arena",
    "sol_24_smoke": "Humo",
    "sol_31_light_drizzle": "Llovizna ligera",
    "sol_32_drizzle": "Llovizna",
    "sol_33_heavy_drizzle": "Llovizna fuerte",
    "sol_34_light_rain": "Lluvia ligera",
    "sol_35_rain": "Lluvia",
    "sol_36_heavy_rain": "Lluvia fuerte",
    "sol_41_light_thunderstorm": "Tormenta ligera",
    "sol_42_thunderstorm": "Tormenta",
    "sol_43_heavy_thunderstorm": "Tormenta fuerte",
    "sol_44_squalls": "Chubascos",
    "sol_45_tornado": "Tornado",
    "sol_46_hurricane": "Huracán",
    "sol_51_light_snow": "Nieve ligera",
    "sol_52_snow": "Nieve",
    "sol_53_heavy_snow": "Nieve fuerte",
    "sol_54_light_sleet": "Aguanieve ligera",
    "sol_55_sleet": "Aguanieve",
    "sol_56_heavy_sleet": "Aguanieve fuerte",
    "sol_57_hail": "Granizo",
}


def get_weather_presets() -> list:
    """Presets visuales de clima (`content/weather/*`).

    Lista de `{name, label}` ordenada por nombre. `label` traduce al
    español los presets conocidos; los personalizados se muestran tal cual.
    Vacío si la carpeta no existe: el formulario usa texto libre.
    """
    folder = get_server_folder() / "content" / "weather"
    try:
        names = sorted(
            entry.name
            for entry in folder.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []
    return [
        {"name": name, "label": PRESET_LABELS.get(name, name)}
        for name in names
    ]


# Compatibilidad: antes se importaba `CONFIG_FILE` directamente. Se mantiene
# como foto inicial, pero `read_config()` siempre recalcula la ruta.
CONFIG_FILE = get_config_file()
SERVER_FOLDER = get_server_folder()


def read_config() -> dict:
    """Lee y parsea `server_cfg.ini`.

    Devuelve un diccionario `{seccion: {clave: valor}}` con las mayúsculas
    originales. Si falta el archivo, devuelve `{"error": ...}`.
    """
    config_file = get_config_file()

    if not config_file.is_file():
        return {"error": f"No se encontró {config_file}"}

    parser = configparser.ConfigParser()
    parser.optionxform = str  # Preservar mayúsculas en las claves
    parser.read(config_file, encoding="utf-8")

    config: dict = {}
    for section in parser.sections():
        values: dict = {}
        for key, value in parser.items(section):
            if key.upper() in SECRET_KEYS:
                # Solo se informa si hay algo escrito, nunca el valor.
                values[f"{key}_SET"] = bool(value.strip())
                continue
            values[key] = value
        config[section] = values

    return config


def get_config() -> dict:
    """Devuelve la configuración del servidor, sin secretos."""
    return read_config()


# ================== Edición de la configuración =====================
# Solo estas claves se pueden cambiar desde la web. Todo lo demás (puertos,
# direcciones de plugins, y sobre todo PASSWORD / ADMIN_PASSWORD) se ignora.
# Tipos: "str" (texto), "int" (entero), "float" (decimal), "bool01" ("0"/"1").
# Los rangos son (mínimo, máximo) o None si no aplica.
# Reglas comunes a todos los tramos [WEATHER_N]: el validador las aplica a
# cualquier sección que cumpla `WEATHER_\d+`, no solo a 0 y 1.
WEATHER_RULES: dict = {
    "GRAPHICS": ("str", 1, 120),
    "BASE_TEMPERATURE_AMBIENT": ("int", -20, 60),
    "BASE_TEMPERATURE_ROAD": ("int", -20, 80),
    "VARIATION_AMBIENT": ("int", 0, 30),
    "VARIATION_ROAD": ("int", 0, 30),
    "WIND_BASE_SPEED_MIN": ("int", 0, 200),
    "WIND_BASE_SPEED_MAX": ("int", 0, 200),
    "WIND_BASE_DIRECTION": ("int", 0, 360),
    "WIND_VARIATION_DIRECTION": ("int", 0, 360),
}

EDITABLE_FIELDS: dict = {
    "SERVER": {
        # NAME bloqueado: el nombre del servidor no se cambia desde la web.
        "CARS": ("str", 1, 200),
        "TRACK": ("str", 1, 120),
        "CONFIG_TRACK": ("str", 0, 120),
        "AI_LEVEL": ("int", 0, 100),
        "SUN_ANGLE": ("float", -208.0, 176.0),
        "TIME_OF_DAY_MULT": ("float", 0.0, 100.0),
        "PICKUP_MODE_ENABLED": ("bool01", None, None),
        "LOOP_MODE": ("bool01", None, None),
        "REGISTER_TO_LOBBY": ("bool01", None, None),
        "MAX_CLIENTS": ("int", 1, 128),
        "RACE_OVER_TIME": ("int", 0, 3600),
        "SLEEP_TIME": ("int", 0, 100),
        "CLIENT_SEND_INTERVAL_HZ": ("int", 1, 60),
        "SEND_BUFFER_SIZE": ("int", 0, 1048576),
        "RECV_BUFFER_SIZE": ("int", 0, 1048576),
        "KICK_QUORUM": ("int", 0, 100),
        "VOTING_QUORUM": ("int", 0, 100),
        "VOTE_DURATION": ("int", 0, 3600),
        "BLACKLIST_MODE": ("bool01", None, None),
        "LEGAL_TYRES": ("str", 0, 200),
        "FUEL_RATE": ("int", 0, 500),
        "DAMAGE_MULTIPLIER": ("int", 0, 500),
        "TYRE_WEAR_RATE": ("int", 0, 500),
        "PENALTIES": ("bool01", None, None),
        "ALLOWED_TYRES_OUT": ("int", 0, 999),
        "ABS_ALLOWED": ("bool01", None, None),
        "TC_ALLOWED": ("bool01", None, None),
        "STABILITY_ALLOWED": ("bool01", None, None),
        "AUTOCLUTCH_ALLOWED": ("bool01", None, None),
        "TYRE_BLANKETS_ALLOWED": ("bool01", None, None),
        "FORCE_VIRTUAL_MIRROR": ("bool01", None, None),
    },
    "PRACTICE": {
        "NAME": ("str", 1, 64),
        "TIME": ("int", 1, 10080),
        "IS_OPEN": ("bool01", None, None),
        "INFINITE": ("bool01", None, None),
    },
    "RACE": {
        "NAME": ("str", 1, 64),
        "LAPS": ("int", 1, 1000),
        "WAIT_TIME": ("int", 0, 3600),
        "IS_OPEN": ("bool01", None, None),
    },
    "DYNAMIC_TRACK": {
        "SESSION_START": ("int", 0, 100),
        "RANDOMNESS": ("int", 0, 100),
        "SESSION_TRANSFER": ("int", 0, 100),
        "LAP_GAIN": ("int", 0, 1000),
    },
    "WEATHER_0": dict(WEATHER_RULES),
    "WEATHER_1": dict(WEATHER_RULES),
}


def _clean(value) -> str:
    """Normaliza un valor entrante a texto sin saltos de línea."""
    text = str(value).strip().replace("\r", "").replace("\n", "")
    return text


# Solo los tramos de clima se pueden borrar completos (con `null`).
WEATHER_SECTION = re.compile(r"^WEATHER_(\d+)$")


def _weather_rules(section: str):
    """Reglas de un tramo de clima, sea cual sea su número."""
    if WEATHER_SECTION.match(section):
        return WEATHER_RULES
    return None


def validate_updates(updates: dict) -> tuple:
    """Valida `{seccion: {clave: valor}}` contra la lista permitida.

    Devuelve `(limpios, borrados)`: valores ya en texto y tipos comprobados,
    más las secciones a eliminar (las que llegaron como `null`).
    Lanza `ValueError` con mensaje en español si algo no es editable o el
    valor no es válido. No toca el disco.
    """
    if not isinstance(updates, dict) or not updates:
        raise ValueError("Sin cambios que guardar.")

    clean: dict = {}
    deleted: list = []
    for section, fields in updates.items():
        if fields is None:
            if WEATHER_SECTION.match(section) is None:
                raise ValueError(
                    "Solo se pueden borrar tramos de clima."
                )
            deleted.append(section)
            continue

        allowed = EDITABLE_FIELDS.get(section) or _weather_rules(section)
        if allowed is None or not isinstance(fields, dict):
            raise ValueError(f"Sección no editable: {section}.")

        clean_section: dict = {}
        for key, value in fields.items():
            if value is None:
                raise ValueError(f"[{section}] {key}: sin valor.")
            rule = allowed.get(key)
            if rule is None:
                raise ValueError(f"Campo no editable: [{section}] {key}.")

            kind, minimum, maximum = rule
            text = _clean(value)

            if kind == "bool01":
                if text not in ("0", "1"):
                    raise ValueError(f"[{section}] {key}: usa 0 o 1.")
            elif kind == "int":
                try:
                    number = int(text)
                except ValueError:
                    raise ValueError(
                        f"[{section}] {key}: debe ser un número entero."
                    ) from None
                if minimum is not None and number < minimum:
                    raise ValueError(
                        f"[{section}] {key}: mínimo {minimum}."
                    )
                if maximum is not None and number > maximum:
                    raise ValueError(
                        f"[{section}] {key}: máximo {maximum}."
                    )
                text = str(number)
            elif kind == "float":
                try:
                    number = float(text)
                except ValueError:
                    raise ValueError(
                        f"[{section}] {key}: debe ser un número."
                    ) from None
                if minimum is not None and number < minimum:
                    raise ValueError(
                        f"[{section}] {key}: mínimo {minimum}."
                    )
                if maximum is not None and number > maximum:
                    raise ValueError(
                        f"[{section}] {key}: máximo {maximum}."
                    )
                text = str(number)
            else:  # "str"
                if len(text) < minimum or len(text) > maximum:
                    raise ValueError(
                        f"[{section}] {key}: entre {minimum} y "
                        f"{maximum} caracteres."
                    )
                # Sin saltos de línea (ya quitados en _clean): un valor de
                # una sola línea no puede romper el INI, aunque lleve `=`
                # (p. ej. GRAPHICS=6_mid_clouds_type=8).

            clean_section[key] = text

        if clean_section:
            clean[section] = clean_section

    if not clean and not deleted:
        raise ValueError("Sin cambios que guardar.")

    if clean and deleted:
        raise ValueError(
            "Guarda los cambios o borra el tramo, no ambas cosas."
        )

    return clean, deleted


def _is_header(stripped: str) -> bool:
    return stripped.startswith("[") and stripped.endswith("]")


def _header_name(stripped: str) -> str:
    return stripped[1:-1]


def _file_weathers(lines: list) -> list:
    """Tramos [WEATHER_N] del archivo, en orden de aparición."""
    return [
        _header_name(line.strip())
        for line in lines
        if _is_header(line.strip())
        and WEATHER_SECTION.match(_header_name(line.strip()))
    ]


def write_config(updates: dict) -> dict:
    """Guarda cambios validados en `server_cfg.ini` y devuelve la config nueva.

    Reescribe solo las líneas de las claves editadas: comentarios, orden y
    claves desconocidas se conservan. Borrar un tramo (`null`) elimina su
    bloque y renumera los siguientes para mantener la secuencia contigua.
    Agregar un tramo nuevo solo admite el siguiente índice libre.
    La escritura es atómica (temporal + renombrado).
    """
    clean, deleted = validate_updates(updates)
    config_file = get_config_file()

    if not config_file.is_file():
        raise FileNotFoundError(f"No se encontró {config_file}")

    original = config_file.read_text(encoding="utf-8").splitlines()
    present = _file_weathers(original)

    for section in deleted:
        if section not in present:
            raise ValueError(f"No existe la sección [{section}].")

    remaining = [s for s in present if s not in deleted]
    if deleted and not remaining:
        raise ValueError("Debe quedar al menos un tramo de clima.")

    # Nuevo tramo: solo índices contiguos al final (sin huecos). Se aceptan
    # varios a la vez siempre que formen la secuencia siguiente completa.
    new_weathers = sorted(
        (
            int(match.group(1))
            for section, match in (
                (s, WEATHER_SECTION.match(s)) for s in clean
            )
            if match and section not in present
        )
    )
    for position, index in enumerate(new_weathers):
        if index != len(present) + position:
            raise ValueError(
                f"[WEATHER_{index}] no sigue la secuencia: el siguiente es "
                f"[WEATHER_{len(present)}]."
            )

    renumber = {
        old: f"WEATHER_{new}"
        for new, old in enumerate(remaining)
    }

    pending = {s: dict(f) for s, f in clean.items()}
    section = None
    skipping = False
    output: list = []

    for line in original:
        stripped = line.strip()
        if _is_header(stripped):
            # Al cerrar una sección, se añaden las claves que faltaban.
            rest = pending.pop(section, None)
            if rest and section not in deleted:
                for key, value in rest.items():
                    output.append(f"{key}={value}")
            section = _header_name(stripped)
            skipping = section in deleted
            if skipping:
                continue
            if section in renumber and renumber[section] != section:
                line = re.sub(
                    r"\[WEATHER_\d+\]",
                    f"[{renumber[section]}]",
                    line,
                    count=1,
                )
            output.append(line)
            continue

        if skipping:
            continue

        if (
            section in pending
            and stripped
            and not stripped.startswith((";", "#"))
            and "=" in line
        ):
            name = line.split("=", 1)[0].strip()
            if name in pending[section]:
                indent = line[: len(line) - len(line.lstrip())]
                output.append(f"{indent}{name}={pending[section].pop(name)}")
                if not pending[section]:
                    del pending[section]
                continue

        output.append(line)

    # Claves restantes de la última sección, más secciones totalmente nuevas.
    # Se omiten las vacías: ya quedaron escritas en su sitio.
    rest = pending.pop(section, None)
    if rest and not skipping:
        for key, value in rest.items():
            output.append(f"{key}={value}")
    for new_section, fields in pending.items():
        if not fields:
            continue
        output.append(f"[{new_section}]")
        for key, value in fields.items():
            output.append(f"{key}={value}")

    tmp = config_file.with_suffix(".ini.tmp")
    tmp.write_text("\n".join(output) + "\n", encoding="utf-8")
    tmp.replace(config_file)

    return read_config()
