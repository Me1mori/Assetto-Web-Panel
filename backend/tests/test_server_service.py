"""Pruebas del control del servicio systemd."""
import subprocess

import pytest

from backend.services import server_service


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_commands_use_absolute_paths(monkeypatch):
    """No debe depender del PATH, que es controlable."""
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Result(stdout="active")

    monkeypatch.setattr(subprocess, "run", fake_run)

    server_service.status()

    assert captured["args"][:2] == [
        server_service.SUDO,
        server_service.SYSTEMCTL
    ]
    assert captured["args"][0].startswith("/")
    assert captured["args"][1].startswith("/")


def test_run_has_timeout(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    server_service.start()

    assert captured["timeout"] == server_service.COMMAND_TIMEOUT
    assert captured["timeout"] > 0


def test_status_false_when_inactive(monkeypatch):
    """Un servidor apagado NO es un error.

    `systemctl is-active` responde `inactive` con código 3: la consulta
    funcionó y el servicio está parado. Antes eso acababa en un 502 que
    enseñaba "systemctl is-active falló (código 3): inactive".
    """
    monkeypatch.setattr(
        server_service,
        "_run",
        lambda a: Result("inactive\n", returncode=3)
    )

    assert server_service.status() is False


def test_status_true_when_active(monkeypatch):
    monkeypatch.setattr(server_service, "_run", lambda a: Result("active\n"))

    assert server_service.status() is True


def test_status_raises_on_error(monkeypatch):
    """No debe informar 'inactivo' cuando en realidad no pudo comprobar."""
    monkeypatch.setattr(
        server_service,
        "_run",
        lambda a: Result(stderr="sudo: denied", returncode=1)
    )

    with pytest.raises(RuntimeError, match="denied"):
        server_service.status()


def test_status_raises_when_unit_does_not_exist(monkeypatch):
    """Si la unidad no existe, sí es un fallo real que hay que reportar."""
    monkeypatch.setattr(
        server_service,
        "_run",
        lambda a: Result(
            stderr="Unit no-existe.service could not be found.",
            returncode=5
        )
    )

    with pytest.raises(RuntimeError, match="could not be found"):
        server_service.status()


def test_timeout_is_reported(monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="systemctl", timeout=20)

    monkeypatch.setattr(subprocess, "run", boom)

    with pytest.raises(RuntimeError, match="tardó más de"):
        server_service.start()


def test_start_stop_restart_actions(monkeypatch):
    calls = []
    monkeypatch.setattr(
        server_service, "_run", lambda a: calls.append(a) or Result()
    )

    server_service.start()
    server_service.stop()
    server_service.restart()

    assert calls == ["start", "stop", "restart"]