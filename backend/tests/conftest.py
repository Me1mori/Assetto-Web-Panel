"""Fixtures compartidas por las pruebas de la API.

Estaban duplicadas en `test_api.py` y en `test_api_sin_acceso.py`: un mismo
cliente del panel y un mismo `systemctl` falso, escritos dos veces.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import server_service


@pytest.fixture
def panel():
    """Cliente del panel. Sin credenciales ni variables que configurar."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def systemctl(monkeypatch):
    """Sustituye `systemctl` para no tocar el servicio real en los tests.

    Devuelve la lista de acciones invocadas.
    """
    calls = []

    class Result:
        def __init__(self, action):
            self.stdout = "active" if action == "is-active" else ""
            self.stderr = ""
            self.returncode = 0

    def fake_run(action):
        calls.append(action)
        return Result(action)

    monkeypatch.setattr(server_service, "_run", fake_run)

    return calls