"""Pruebas de las rutas de la API.

El panel **no pide credenciales**: ni usuarios, ni contraseñas, ni sesiones, ni
`Authorization`. Lo que se comprueba aquí es que el CSRF de los POST siga
frenando a otra web y que los fallos de `systemctl` lleguen al frontend con el
detalle real en vez de fingir estado.

Las pruebas de que no queda ningún acceso (ni `401`, ni `WWW-Authenticate`, ni
`/api/auth/*`) están en `test_api_sin_acceso.py`. El cliente del panel y el
`systemctl` falso vienen de `conftest.py`.
"""
import pytest

from backend.services import server_service


# ── Estado ─────────────────────────────────────────────────────────────────
def test_status_ok(panel, systemctl, monkeypatch):
    monkeypatch.setattr(server_service, "status", lambda: True)

    response = panel.get("/api/server/status")

    assert response.status_code == 200
    assert response.json() is True


@pytest.mark.parametrize("endpoint", ["status", "logs"])
def test_get_is_public(panel, systemctl, endpoint):
    """Las lecturas no piden nada: no hay sesión, cookie ni token.

    `systemctl` viene sustituido por la fixture para no tocar el servicio real.
    """
    response = panel.get(f"/api/server/{endpoint}")

    assert response.status_code == 200


def test_status_failure_is_502_with_detail(panel, monkeypatch):
    class Failed:
        stdout = ""
        stderr = "sudo: a password is required"
        returncode = 1

    monkeypatch.setattr(server_service, "_run", lambda action: Failed())

    response = panel.get("/api/server/status")

    assert response.status_code == 502
    assert "password is required" in response.json()["detail"]


def test_status_timeout_is_502(panel, monkeypatch):
    def boom():
        raise RuntimeError("systemctl is-active tardó más de 20s")

    monkeypatch.setattr(server_service, "status", boom)

    response = panel.get("/api/server/status")

    assert response.status_code == 502


# ── CSRF ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("endpoint", ["/start", "/stop", "/restart"])
def test_post_same_origin_allowed(panel, systemctl, endpoint):
    response = panel.post(f"/api/server{endpoint}")

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.parametrize("endpoint", ["/start", "/stop", "/restart"])
def test_post_from_other_origin_blocked(panel, systemctl, endpoint):
    response = panel.post(
        f"/api/server{endpoint}",
        headers={"Origin": "https://sitio-malicioso.example"}
    )

    assert response.status_code == 403
    assert "Origen" in response.json()["detail"]
    # Lo importante: el bloqueo ocurre ANTES de tocar systemctl.
    assert systemctl == []


def test_post_from_allowed_extra_origin(panel, systemctl, monkeypatch):
    """ASSETO_ALLOWED_ORIGINS admite un origen externo (proxy, otro host)."""
    from backend import security
    monkeypatch.setattr(
        security, "ALLOWED_ORIGINS", ["https://panel.ejemplo.com"]
    )

    response = panel.post(
        "/api/server/start",
        headers={"Origin": "https://panel.ejemplo.com"}
    )

    assert response.status_code == 200


def test_origen_no_permitido_no_toca_systemctl(panel, systemctl):
    """Regresión de seguridad: el 403 debe ocurrir ANTES de actuar."""
    response = panel.post(
        "/api/server/stop",
        headers={"Origin": "https://sitio-malioso.example"}
    )

    assert response.status_code == 403
    assert systemctl == []


def test_get_has_no_origin_requirement(panel, systemctl, monkeypatch):
    monkeypatch.setattr(server_service, "status", lambda: True)

    response = panel.get(
        "/api/server/status",
        headers={"Origin": "https://sitio-malicioso.example"}
    )

    # Solo los POST que cambian el estado se protegen.
    assert response.status_code == 200


# ── Control ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("endpoint", ["start", "stop", "restart"])
def test_control_failure_is_502(panel, monkeypatch, endpoint):
    def boom():
        raise RuntimeError("systemctl start falló (código 1): denied")

    monkeypatch.setattr(server_service, endpoint, boom)

    response = panel.post(f"/api/server/{endpoint}")

    assert response.status_code == 502
    assert "denied" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ["start", "stop", "restart"])
def test_control_uses_systemctl(panel, systemctl, endpoint):
    panel.post(f"/api/server/{endpoint}")

    assert systemctl == [endpoint]


# ── Manejo de errores ──────────────────────────────────────────────────────
def test_error_responses_keep_their_detail(panel, monkeypatch):
    """Regresión: el handler de main.py relanzaba los errores != 404.

    Eso convertía cada 502 en un 500 sin cuerpo y el frontend se quedaba sin
    el `detail` que explica el fallo (sudo denegado, systemctl colgado…).
    """
    def boom():
        raise RuntimeError("sudo: a password is required")

    monkeypatch.setattr(server_service, "start", boom)

    response = panel.post("/api/server/start")

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "detail": "sudo: a password is required"
    }


def test_unknown_path_serves_the_404_page(panel):
    response = panel.get("/ruta-que-no-existe")

    assert response.status_code == 404


# ── Cabeceras de seguridad ─────────────────────────────────────────────────
def test_security_headers(panel, systemctl):
    response = panel.get("/api/server/status")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"].startswith("geolocation=()")
    # Nada de recursos de terceros ni scripts incrustados en el HTML.
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]