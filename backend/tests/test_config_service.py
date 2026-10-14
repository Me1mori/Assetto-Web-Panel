"""Pruebas del servicio de configuración (server_cfg.ini).

Verifica que:
- El archivo INI se lee y parsea correctamente.
- Las contraseñas NUNCA se exponen (ni siquiera como marcador).
- La API devuelve la configuración y da 404 si falta el archivo.
- La variable de entorno ASSETOSERVER_FOLDER funciona.
"""
import pytest

from backend.services import config_service


@pytest.fixture
def ini_file(tmp_path, monkeypatch):
    """Crea un server_cfg.ini temporal con datos de prueba."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    ini = cfg_dir / "server_cfg.ini"

    content = """[SERVER]
NAME=Servidor de Prueba
CARS=*
TRACK=imola
SUN_ANGLE=-65
ADMIN_PASSWORD=secreto123
PASSWORD=password123

[PRACTICE]
NAME=Practice
TIME=600

[WEATHER_0]
GRAPHICS=sunny
BASE_TEMPERATURE_AMBIENT=25
"""
    ini.write_text(content, encoding="utf-8")

    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))
    return ini


def test_read_config_parsea_secciones(ini_file):
    """El servicio lee y parsea las secciones del INI."""
    config = config_service.read_config()

    assert "SERVER" in config
    assert "PRACTICE" in config
    assert "WEATHER_0" in config


def test_read_config_valores_correctos(ini_file):
    """Los valores del INI se leen correctamente."""
    config = config_service.read_config()

    assert config["SERVER"]["NAME"] == "Servidor de Prueba"
    assert config["SERVER"]["TRACK"] == "imola"
    assert config["SERVER"]["SUN_ANGLE"] == "-65"
    assert config["PRACTICE"]["TIME"] == "600"
    assert config["WEATHER_0"]["GRAPHICS"] == "sunny"


def test_contraseñas_nunca_se_exponen(ini_file):
    """Ni PASSWORD ni ADMIN_PASSWORD aparecen en la respuesta."""
    config = config_service.read_config()

    assert "PASSWORD" not in config["SERVER"]
    assert "ADMIN_PASSWORD" not in config["SERVER"]
    assert "secreto123" not in str(config)
    assert "password123" not in str(config)


def test_contraseñas_solo_informan_si_existen(ini_file):
    """Se devuelve *_SET como booleano, sin el valor."""
    config = config_service.read_config()

    assert config["SERVER"]["PASSWORD_SET"] is True
    assert config["SERVER"]["ADMIN_PASSWORD_SET"] is True


def test_contraseña_vacia_es_falsa(tmp_path, monkeypatch):
    """Una contraseña vacía se informa como no configurada."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "server_cfg.ini").write_text(
        "[SERVER]\nNAME=X\nPASSWORD=\n", encoding="utf-8"
    )
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    config = config_service.read_config()

    assert "PASSWORD" not in config["SERVER"]
    assert config["SERVER"]["PASSWORD_SET"] is False


def test_archivo_no_existe_devuelve_error(tmp_path, monkeypatch):
    """Si no existe el archivo, devuelve un error descriptivo."""
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    config = config_service.read_config()

    assert "error" in config


def test_ruta_config_devuelve_configuracion(panel, ini_file):
    """La API devuelve la configuración del servidor."""
    response = panel.get("/api/server/config")

    assert response.status_code == 200
    data = response.json()

    assert "SERVER" in data
    assert "PRACTICE" in data
    assert data["SERVER"]["NAME"] == "Servidor de Prueba"


def test_ruta_config_no_expone_contraseñas(panel, ini_file):
    """La API NUNCA expone las contraseñas."""
    response = panel.get("/api/server/config")

    assert response.status_code == 200
    data = response.json()

    assert "PASSWORD" not in data["SERVER"]
    assert "ADMIN_PASSWORD" not in data["SERVER"]
    assert "secreto123" not in str(data)
    assert "password123" not in str(data)


def test_ruta_config_sin_archivo_es_404(panel, tmp_path, monkeypatch):
    """Sin server_cfg.ini la API responde 404 con detalle."""
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    response = panel.get("/api/server/config")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_ruta_config_es_lectura_publica(panel, ini_file):
    """GET /config no pide Origin: es lectura, como /status y /logs."""
    response = panel.get(
        "/api/server/config",
        headers={"Origin": "https://sitio-malicioso.example"},
    )

    assert response.status_code == 200


# ── Edición (PUT) ────────────────────────────────────────────────────────
def test_put_actualiza_valores(ini_file):
    """write_config cambia el valor y conserva el resto."""
    config_service.write_config({"SERVER": {"TRACK": "spa"}})

    config = config_service.read_config()

    assert config["SERVER"]["TRACK"] == "spa"
    assert config["SERVER"]["NAME"] == "Servidor de Prueba"


def test_put_nombre_bloqueado(ini_file):
    """El nombre del servidor no se puede cambiar ni por API."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"NAME": "Otro"}})


def test_ruta_put_nombre_bloqueado(panel, ini_file):
    """PUT del nombre responde 422 y el archivo no cambia."""
    response = panel.put(
        "/api/server/config",
        json={"SERVER": {"NAME": "Otro"}},
    )

    assert response.status_code == 422
    assert config_service.read_config()["SERVER"]["NAME"] == "Servidor de Prueba"


def test_put_rechaza_contraseñas(ini_file):
    """Ni PASSWORD ni ADMIN_PASSWORD son editables."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"PASSWORD": "x"}})

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"ADMIN_PASSWORD": "x"}})


def test_put_rechaza_valor_invalido(ini_file):
    """Un entero fuera de rango o un texto larguísimo no se guarda."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"MAX_CLIENTS": "9999"}})

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"CARS": "x" * 201}})

    # El archivo sigue intacto.
    assert config_service.read_config()["SERVER"]["NAME"] == "Servidor de Prueba"


def test_put_acepta_igual_en_graphics(ini_file):
    """GRAPHICS lleva `=` (p. ej. sol_…_type=8) y debe guardarse."""
    config = config_service.write_config(
        {"WEATHER_0": {"GRAPHICS": "sol_03_scattered_clouds_type=8"}}
    )

    assert config["WEATHER_0"]["GRAPHICS"] == "sol_03_scattered_clouds_type=8"


def test_put_conserva_comentarios_y_claves(ini_file):
    """La escritura no destruye comentarios ni claves desconocidas."""
    ini_file.write_text(
        "; comentario del admin\n[SERVER]\nNAME=Original\nRARO=1\n",
        encoding="utf-8",
    )

    config_service.write_config({"SERVER": {"TRACK": "spa"}})

    text = ini_file.read_text(encoding="utf-8")

    assert "; comentario del admin" in text
    assert "RARO=1" in text
    assert "TRACK=spa" in text


def test_ruta_put_guarda_y_devuelve_config(panel, ini_file):
    """PUT /config guarda y devuelve la configuración nueva."""
    response = panel.put(
        "/api/server/config",
        json={"SERVER": {"SUN_ANGLE": "-65"}},
    )

    assert response.status_code == 200
    assert response.json()["SERVER"]["SUN_ANGLE"] == "-65.0"


def test_ruta_put_invalido_es_422(panel, ini_file):
    """Un valor inválido responde 422 con el motivo."""
    response = panel.put(
        "/api/server/config",
        json={"SERVER": {"MAX_CLIENTS": "9999"}},
    )

    assert response.status_code == 422
    assert "MAX_CLIENTS" in response.json()["detail"]


def test_ruta_put_origen_externo_bloqueado(panel, ini_file):
    """El PUT comprueba Origin (CSRF) y no toca el archivo."""
    response = panel.put(
        "/api/server/config",
        json={"SERVER": {"NAME": "Atacante"}},
        headers={"Origin": "https://sitio-malicioso.example"},
    )

    assert response.status_code == 403
    assert config_service.read_config()["SERVER"]["NAME"] == "Servidor de Prueba"


def test_ruta_put_sin_archivo_es_404(panel, tmp_path, monkeypatch):
    """Sin server_cfg.ini el PUT responde 404."""
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    response = panel.put("/api/server/config", json={"SERVER": {"TRACK": "spa"}})

    assert response.status_code == 404


def test_put_acepta_todos_los_campos_del_ini_real(ini_file):
    """Cada campo del server_cfg.ini de ejemplo tiene dónde caer."""
    cambios = {
        "SERVER": {
            "SUN_ANGLE": "-208",
            "SLEEP_TIME": "1",
            "CLIENT_SEND_INTERVAL_HZ": "18",
            "SEND_BUFFER_SIZE": "0",
            "RECV_BUFFER_SIZE": "0",
            "RACE_OVER_TIME": "180",
            "KICK_QUORUM": "85",
            "VOTING_QUORUM": "80",
            "VOTE_DURATION": "20",
            "BLACKLIST_MODE": "1",
            "LEGAL_TYRES": "SV",
            "ALLOWED_TYRES_OUT": "999",
            "PENALTIES": "0",
        },
        "WEATHER_0": {
            "VARIATION_AMBIENT": "0",
            "WIND_VARIATION_DIRECTION": "0",
        },
        "WEATHER_1": {
            "BASE_TEMPERATURE_AMBIENT": "15",
            "WIND_BASE_SPEED_MIN": "0",
        },
    }

    config = config_service.write_config(cambios)

    assert config["SERVER"]["SUN_ANGLE"] == "-208.0"
    assert config["SERVER"]["KICK_QUORUM"] == "85"
    assert config["SERVER"]["LEGAL_TYRES"] == "SV"
    assert config["WEATHER_1"]["BASE_TEMPERATURE_AMBIENT"] == "15"


def test_put_rechaza_sun_angle_fuera_de_rango(ini_file):
    """SUN_ANGLE solo cubre las 00:00–23:59 (-208 a 176)."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"SUN_ANGLE": "200"}})


def test_borrar_tramo_renumera(ini_file):
    """Borrar WEATHER_0 deja el otro como WEATHER_0."""
    (ini_file.parent / "server_cfg.ini").write_text(
        ini_file.read_text(encoding="utf-8")
        + "\n[WEATHER_1]\nGRAPHICS=rain\nBASE_TEMPERATURE_AMBIENT=15\n",
        encoding="utf-8",
    )

    config = config_service.write_config({"WEATHER_0": None})

    assert "WEATHER_1" not in config
    assert config["WEATHER_0"]["GRAPHICS"] == "rain"
    assert "WEATHER_0" in ini_file.read_text(encoding="utf-8")


def test_borrar_ultimo_tramo_rechazado(ini_file):
    """Debe quedar al menos un tramo de clima."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"WEATHER_0": None})


def test_borrar_seccion_no_clima_rechazado(ini_file):
    """Solo se pueden borrar tramos [WEATHER_N]."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": None})

    with _pytest.raises(ValueError):
        config_service.write_config({"RACE": None})


def test_borrar_y_editar_a_la_vez_rechazado(ini_file):
    """Borrado y edición van en peticiones separadas."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config(
            {"WEATHER_0": None, "SERVER": {"NAME": "X"}}
        )


def test_agregar_tramo_nuevo(ini_file):
    """WEATHER_1 se añade al final con sus claves."""
    config = config_service.write_config(
        {
            "WEATHER_1": {
                "GRAPHICS": "rain_type=8",
                "BASE_TEMPERATURE_AMBIENT": "15",
            }
        }
    )

    assert config["WEATHER_1"]["GRAPHICS"] == "rain_type=8"
    assert "[WEATHER_1]" in ini_file.read_text(encoding="utf-8")


def test_agregar_tramo_con_hueco_rechazado(ini_file):
    """Sin WEATHER_1 no se puede crear WEATHER_2."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"WEATHER_2": {"GRAPHICS": "x"}})


def test_ruta_delete_tramo(panel, ini_file):
    """PUT con null borra el tramo y devuelve la config nueva."""
    ini_file.write_text(
        ini_file.read_text(encoding="utf-8")
        + "\n[WEATHER_1]\nGRAPHICS=rain\n",
        encoding="utf-8",
    )

    response = panel.put("/api/server/config", json={"WEATHER_1": None})

    assert response.status_code == 200
    assert "WEATHER_1" not in response.json()


def test_ruta_presets(panel, ini_file):
    """GET /weather-presets lista nombre y etiqueta en español."""
    clima = ini_file.parent.parent / "content" / "weather"
    (clima / "sol_03_scattered_clouds").mkdir(parents=True)
    (clima / "6_mid_clouds").mkdir()
    (clima / "mi_pista").mkdir()
    (clima / "readme_weather.txt").write_text("x", encoding="utf-8")

    response = panel.get("/api/server/weather-presets")

    assert response.status_code == 200
    assert response.json() == {
        "presets": [
            {"name": "6_mid_clouds", "label": "Medio nublado"},
            {"name": "mi_pista", "label": "mi_pista"},
            {"name": "sol_03_scattered_clouds", "label": "Nubes dispersas"},
        ]
    }


def test_ruta_presets_sin_carpeta(panel, tmp_path, monkeypatch):
    """Sin content/weather la lista llega vacía, no 404."""
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    response = panel.get("/api/server/weather-presets")

    assert response.status_code == 200
    assert response.json() == {"presets": []}


def test_agregar_dos_tramos_en_una_peticion(ini_file):
    """Dos tramos nuevos contiguos se guardan juntos (el panel los acumula)."""
    config = config_service.write_config(
        {
            "WEATHER_1": {"GRAPHICS": "rain"},
            "WEATHER_2": {"GRAPHICS": "sunny"},
        }
    )

    assert config["WEATHER_1"]["GRAPHICS"] == "rain"
    assert config["WEATHER_2"]["GRAPHICS"] == "sunny"


def test_agregar_dos_tramos_con_hueco_rechazado(ini_file):
    """WEATHER_1 + WEATHER_3 sin WEATHER_2 sigue siendo hueco."""
    import pytest as _pytest

    with _pytest.raises(ValueError, match="secuencia"):
        config_service.write_config(
            {
                "WEATHER_1": {"GRAPHICS": "rain"},
                "WEATHER_3": {"GRAPHICS": "sunny"},
            }
        )


def test_valor_none_no_se_guarda_como_texto(ini_file):
    """Un campo en null no acaba escrito como la cadena "None"."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        config_service.write_config({"SERVER": {"TRACK": None}})

    assert config_service.read_config()["SERVER"]["TRACK"] == "imola"
