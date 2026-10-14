"""Red de seguridad: el panel NO tiene acceso de ningún tipo.

Decisión del dueño del proyecto (ver AGENTS.md): encender y apagar el servidor
tiene que funcionar a la primera, sin escribir usuario y contraseña. Por eso
aquí **no** existe HTTP Basic, ni `Authorization`, ni usuarios, sesiones,
cookies o tokens.

Estas pruebas fallan en cuanto alguien reintroduce esa capa:

* un `401` o un `WWW-Authenticate` en cualquier ruta,
* un `backend/auth.py` (o cualquier módulo de autenticación),
* una ruta `/api/auth/*`,
* las variables `ASSETO_BASIC_*` o cualquier otra de credenciales.

No las borres ni las relajes: son lo que mantiene esa decisión.
"""
from pathlib import Path

import pytest

from backend import security

# Raíz del repositorio, para revisar los archivos del proyecto.
ROOT = Path(__file__).resolve().parents[2]

RUTAS = [
    "/api/server/status",
    "/api/server/logs",
    "/api/server/config",
    "/api/server/entry-list",
    "/api/server/tracks",
    "/api/server/available-cars",
    "/api/server/start",
    "/api/server/stop",
    "/api/server/restart",
]

POSTS = [
    "/api/server/start",
    "/api/server/stop",
    "/api/server/restart",
]

# Lo que delata una capa de acceso reintroducida.
PATRONES_PROHIBIDOS = [
    "ASSETO_BASIC_",
    "WWW-Authenticate",
    "HTTPBasic",
    "OAuth2PasswordRequestForm",
    "/api/auth",
    "set_cookie",
    "Set-Cookie",
]


# ── No hay 401 ni desafío de autenticación ──────────────────────────────────
@pytest.mark.parametrize("ruta", RUTAS)
def test_nunca_hay_401_ni_desafio(panel, systemctl, ruta):
    """Ninguna ruta responde 401, en ningún método, aunque se mande basura."""
    metodo = panel.post if ruta.split("/")[-1] in {
        "start", "stop", "restart"
    } else panel.get

    response = metodo(ruta, headers={"Authorization": "Basic Zm9vOmJhcg=="})

    assert response.status_code != 401
    assert "www-authenticate" not in response.headers


@pytest.mark.parametrize("ruta", POSTS)
def test_un_authorization_raro_no_rompe(panel, systemctl, ruta):
    """Una cabecera `Authorization` rara se ignora: no rompe el panel."""
    response = panel.post(ruta, headers={"Authorization": "Bearer algo"})

    assert response.status_code == 200


@pytest.mark.parametrize("ruta", POSTS)
def test_control_works_without_credentials(panel, systemctl, ruta):
    """Encender/apagar/reiniciar funcionan sin escribir nada."""
    response = panel.post(ruta)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert systemctl == [ruta.rsplit("/", 1)[-1]]


# ── No existe el código de autenticación ───────────────────────────────────
def test_no_existe_el_modulo_de_auth():
    """`backend/auth.py` no debe volver (ni otro módulo de acceso)."""
    assert not (ROOT / "backend" / "auth.py").exists()

    modulos = list((ROOT / "backend").rglob("*.py"))

    assert modulos, "no se encuentra ningún módulo del backend"


def test_no_deja_ruta_de_auth(panel, systemctl):
    """No hay rutas de autenticación: ni /api/auth ni /auth."""
    for ruta in ("/api/auth/login", "/api/auth/logout", "/auth", "/login"):
        assert panel.get(ruta).status_code == 404


# ── No quedan variables de credenciales ────────────────────────────────────
def test_no_quedan_las_variables_de_credenciales():
    """`security.py` solo conoce orígenes: ninguna variable de credenciales."""
    fuente = (ROOT / "backend" / "security.py").read_text(encoding="utf-8")

    assert "BASIC" not in fuente
    assert "PASSWORD" not in fuente
    # La configuración real: únicamente el origen permitido.
    assert "ASSETO_ALLOWED_ORIGINS" in fuente


@pytest.mark.parametrize("patron", PATRONES_PROHIBIDOS)
def test_el_backend_no_habla_de_credenciales(patron):
    """Barrido del backend: ninguna huella de una capa de acceso."""
    ofensores = []

    for archivo in (ROOT / "backend").rglob("*.py"):
        # Las pruebas sí mencionan estos términos: son las que los prohíben.
        if "tests" in archivo.parts:
            continue

        if patron in archivo.read_text(encoding="utf-8"):
            ofensores.append(archivo.relative_to(ROOT))

    assert ofensores == []


def test_solo_se_protege_el_origen(monkeypatch):
    """Recordatorio de la decisión: lo único que se comprueba es el Origin."""
    monkeypatch.setattr(security, "ALLOWED_ORIGINS", [])

    assert hasattr(security, "check_same_origin")
    assert not hasattr(security, "verify_credentials")