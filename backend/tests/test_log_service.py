"""Pruebas de la lectura de logs.

Incluyen regresiones de fallos reales: el stack trace de .NET que vaciaba la
lista de logs, y la exposición de datos personales.
"""
from datetime import datetime

import pytest

from backend.services import log_service


# ── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture
def log_file(tmp_path, monkeypatch):
    """Apunta LOG_FOLDER a un temporal y devuelve un escritor de líneas."""
    folder = tmp_path / "logs"
    folder.mkdir()
    monkeypatch.setattr(log_service, "LOG_FOLDER", folder)
    log_service._cache["key"] = None
    log_service._cache["lines"] = ()

    def write(*lines):
        today = datetime.now().strftime("%Y%m%d")
        (folder / f"log-{today}.txt").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8"
        )
        # La caché compara (ruta, mtime, tamaño): hay que invalidarla.
        log_service._cache["key"] = None
        log_service._cache["lines"] = ()

    return write


BANNER = (
    "2026-10-12 01:23:47.416 +01:00 [INF] "
    "AssettoServer 0.0.54+51737e2c2e"
)


def line(level, message, time="12:00:00.000"):
    return f"2026-10-12 {time} +01:00 [{level}] {message}"


# ── Redacción de datos personales ───────────────────────────────────────────
def test_redact_steam_id():
    result = log_service.redact(
        "Jugador (76561199999999999 - 203.0.113.42:60379) connecting"
    )

    assert "76561199999999999" not in result
    assert "7656" in result


def test_redact_ip():
    result = log_service.redact("Disconnecting Jugador (203.0.113.42:60379)")

    assert "203.0.113.42" not in result
    # Ni un solo octeto se conserva; el puerto sí, porque no es personal.
    assert result == "Disconnecting Jugador (ip.oculta:60379)"


def test_redact_chat_message():
    result = log_service.redact("CHAT: Jugador (12): \t\t$CSP0:YOqrL2En")

    assert "YOqrL2En" not in result
    assert result.startswith("CHAT: Jugador (12):")


def test_redact_keeps_normal_text():
    assert log_service.redact("Server shutting down") == "Server shutting down"


def test_redact_linea_vacia():
    assert log_service.redact("") == ""
    assert log_service.redact(None) is None


def test_parse_log_line_redacts():
    parsed = log_service.parse_log_line(
        line("INF", "Jugador (76561199999999999) connected")
    )

    assert parsed is not None
    assert "76561199999999999" not in parsed["message"]


def test_parse_log_line_fields():
    parsed = log_service.parse_log_line(line("WRN", "Aviso de prueba"))

    assert parsed == {
        "time": "12:00:00.000",
        "level": "WRN",
        "message": "Aviso de prueba"
    }


def test_log_line_without_pattern():
    assert log_service.parse_log_line("sin fecha ni nivel") is None


# ── Última ejecución ───────────────────────────────────────────────────────
def test_find_last_server_start_ignores_stack_trace():
    """Regresión: un stack trace de .NET con 'AssettoServer' ya no manda."""
    lines = [
        "2026-10-12 00:00:00.000 +01:00 [ERR] AssettoServer crashed",
        "   at AssettoServer.Interop.Run()",
        BANNER,
        line("INF", "después del arranque"),
    ]

    result = log_service.find_last_server_start(lines)

    assert result == [BANNER, line("INF", "después del arranque")]


def test_find_last_server_start_uses_last_banner():
    lines = [BANNER, "algo", BANNER, "otra cosa"]

    result = log_service.find_last_server_start(lines)

    assert result == [BANNER, "otra cosa"]


def test_find_last_server_start_without_banner():
    lines = ["línea cualquiera", "otra línea"]

    assert log_service.find_last_server_start(lines) == lines


# ── parse_logs ─────────────────────────────────────────────────────────────
def test_parse_logs_empty_when_no_file(log_file):
    log_file()  # crea el archivo vacío

    assert log_service.parse_logs() == log_service.empty_state()


def test_parse_logs_only_returns_logs(log_file):
    """La respuesta es solo la lista de líneas que el panel muestra."""
    log_file(BANNER, line("INF", "mensaje"))

    result = log_service.parse_logs()

    assert list(result) == ["logs"]
    assert [log["message"] for log in result["logs"]] == [
        "AssettoServer 0.0.54+51737e2c2e",
        "mensaje"
    ]


def test_parse_logs_ignores_previous_session(log_file):
    log_file(
        line("INF", "Jugador viejo ha conectado"),
        BANNER,
        line("INF", "mensaje nuevo"),
    )

    result = log_service.parse_logs()

    messages = [log["message"] for log in result["logs"]]

    assert "Jugador viejo ha conectado" not in messages
    assert messages[-1] == "mensaje nuevo"


def test_parse_logs_skips_lines_without_header(log_file):
    """Las líneas sueltas (stack traces) se ignoran sin romper la respuesta."""
    log_file(BANNER, "   at AssettoServer.Interop.Run()", line("INF", "uno"))

    result = log_service.parse_logs()

    messages = [log["message"] for log in result["logs"]]

    assert "at AssettoServer.Interop.Run()" not in messages
    assert messages[-1] == "uno"


def test_parse_logs_caps_logs(log_file, monkeypatch):
    monkeypatch.setattr(log_service, "MAX_LOG_LINES", 3)

    log_file(
        BANNER,
        *[line("INF", f"mensaje {i}") for i in range(10)],
    )

    result = log_service.parse_logs()

    assert len(result["logs"]) == 3
    # Se conserva la parte más reciente.
    assert result["logs"][-1]["message"] == "mensaje 9"


def test_parse_logs_redacts_every_line(log_file):
    """Ninguna línea sale con Steam ID ni IP, aunque no tenga cabecera."""
    log_file(
        line("INF", "Jugador (76561199999999999) connecting"),
        "conexión desde 203.0.113.42 sin cabecera",
    )

    crudo = str(log_service.parse_logs())

    assert "76561199999999999" not in crudo
    assert "203.0.113.42" not in crudo


def test_read_current_log_uses_cache(log_file):
    log_file(BANNER)

    first = log_service.read_current_log()
    second = log_service.read_current_log()

    assert first == second
    assert first is not second  # copia, no la lista interna


def test_cache_invalidated_when_file_changes(log_file):
    log_file(BANNER, line("INF", "uno"))
    assert len(log_service.read_current_log()) == 2

    log_file(BANNER, line("INF", "uno"), line("INF", "dos"))
    assert len(log_service.read_current_log()) == 3


def test_read_current_log_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(log_service, "LOG_FOLDER", tmp_path / "no-existe")

    assert log_service.read_current_log() == []