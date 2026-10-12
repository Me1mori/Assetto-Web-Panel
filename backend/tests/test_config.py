"""Pruebas de la carga del archivo .env."""
import os
from pathlib import Path

from backend import config


def test_parse_basico():
    values = config.parse_env("A=1\nB=dos\n")

    assert values == {"A": "1", "B": "dos"}


def test_ignora_comentarios_y_vacias():
    texto = (
        "# comentario\n"
        "\n"
        "   \n"
        "A=1  # esto NO es comentario, es valor\n"
    )

    assert config.parse_env(texto) == {"A": "1  # esto NO es comentario, es valor"}


def test_comentario_en_linea_vacia_no_parte_el_texto():
    assert config.parse_env("A=1 # nota")["A"] == "1 # nota"


def test_quita_comillas():
    texto = 'A="con espacios"\nB=\'otro valor\'\n'

    assert config.parse_env(texto) == {
        "A": "con espacios",
        "B": "otro valor"
    }


def test_admite_export():
    assert config.parse_env("export A=1\n") == {"A": "1"}


def test_valores_con_igual_se_conservan():
    """Un valor puede contener '=': solo se parte el primero."""
    assert config.parse_env("TOKEN=a=b=c\n")["TOKEN"] == "a=b=c"


def test_ignora_lineas_sin_igual():
    assert config.parse_env("esto no es una variable\nA=1\n") == {"A": "1"}


def test_carga_en_entorno(tmp_path, monkeypatch):
    archivo = tmp_path / ".env"
    archivo.write_text("ASSETO_TEST_VAR=hola\n", encoding="utf-8")

    monkeypatch.delenv("ASSETO_TEST_VAR", raising=False)

    assert config.load_env_file(archivo) is True

    assert os.environ["ASSETO_TEST_VAR"] == "hola"


def test_entorno_gana_sobre_el_archivo(tmp_path, monkeypatch):
    """Si systemd ya exportó la variable, el .env no la pisa."""
    archivo = tmp_path / ".env"
    archivo.write_text("ASSETO_TEST_VAR=del-archivo\n", encoding="utf-8")

    monkeypatch.setenv("ASSETO_TEST_VAR", "del-entorno")

    config.load_env_file(archivo)

    assert os.environ["ASSETO_TEST_VAR"] == "del-entorno"


def test_archivo_inexistente_no_falla(tmp_path):
    assert config.load_env_file(tmp_path / "no-existe.env") is False


def test_valor_con_espacios_y_hash(tmp_path, monkeypatch):
    """Un valor con # y espacios debe llegar intacto al entorno.

    Aquí se(parsea) como si fuera una contraseña porque es el caso que más
    dolía (un `#` mal citado se comía el resto de la línea), pero este panel
    no guarda ninguna.
    """
    archivo = tmp_path / ".env"
    archivo.write_text(
        'ASSETO_TEST_VALOR=clave #con hash\n',
        encoding="utf-8"
    )

    monkeypatch.delenv("ASSETO_TEST_VALOR", raising=False)
    config.load_env_file(archivo)

    assert os.environ["ASSETO_TEST_VALOR"] == "clave #con hash"


def test_env_file_por_defecto_es_en_la_raiz():
    assert config.ENV_FILE == Path(".env")