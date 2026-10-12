"""Control del servicio systemd del servidor de juego.

`systemctl` puede tardar varios segundos (o colgarse), así que todas las
llamadas llevan `timeout`. Se usan rutas absolutas para no depender del `PATH`
del proceso web, que es controlable por quien lo ejecuta.
"""
import os
import subprocess

# Rutas absolutas: el PATH de un servicio systemd puede ser distinto al de una
# terminal, y no queremos que dependa de él.
SUDO = "/usr/bin/sudo"
SYSTEMCTL = "/usr/bin/systemctl"

SERVICE_NAME = os.environ.get(
    "ASSETOSERVER_SERVICE_NAME",
    "assettoserver"
)

# Segundos máximos por comando: `systemctl start` puede tardar bastante con un
# servidor de juego, pero nunca indefinidamente.
COMMAND_TIMEOUT = int(
    os.environ.get(
        "ASSETOSERVER_COMMAND_TIMEOUT",
        "20"
    )
)


def _run(action: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [SUDO, SYSTEMCTL, action, SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"systemctl {action} tardó más de "
            f"{COMMAND_TIMEOUT}s y se canceló."
        ) from error


def _check_result(result: subprocess.CompletedProcess, action: str):
    """Lanza RuntimeError si systemctl falla (p. ej. sin regla sudoers)."""
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"systemctl {action} falló (código {result.returncode}): {detail}"
        )


# `systemctl is-active` usa el código de salida para decir EN QUÉ ESTÁ el
# servicio, no si la consulta funcionó:
#   0 = active, 3 = inactive/failed (el servicio existe y está parado).
# Sin esto, un servidor simplemente apagado salía como error 502 en el panel.
IS_ACTIVE_INACTIVE = 3


def status() -> bool:
    """Estado real del servicio.

    Lanza RuntimeError si la consulta falla de verdad (p. ej. sudo denegado),
    para no informar "inactivo" cuando en realidad nunca se pudo comprobar.
    """
    result = _run("is-active")

    if result.returncode not in (0, IS_ACTIVE_INACTIVE):
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"systemctl is-active falló (código {result.returncode}): {detail}"
        )

    return result.stdout.strip() == "active"


def start():
    result = _run("start")
    _check_result(result, "start")


def stop():
    result = _run("stop")
    _check_result(result, "stop")


def restart():
    result = _run("restart")
    _check_result(result, "restart")