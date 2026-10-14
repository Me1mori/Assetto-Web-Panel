"""Pruebas del servicio de inscritos (`entry_list.ini`).

Verifica que:
- La lista se lee agrupada por modelo, solo con MODEL/SKIN.
- GUID, DRIVERNAME y TEAM NUNCA se exponen.
- La escritura conserva los datos de jugadores en disco.
- Los modelos/skins disponibles salen de `content/cars`.
"""
import pytest

from backend.services import entry_service

ENTRY = """[CAR_0]
MODEL=bmw_z4_gt3
SKIN=04_blu_white_27
SPECTATOR_MODE=0
DRIVERNAME=Piloto Uno
TEAM=Equipo A
GUID=76561199999999999
BALLAST=0
AI=auto

[CAR_1]
MODEL=bmw_z4_gt3
SKIN='07 white red'
SPECTATOR_MODE=0
DRIVERNAME=
TEAM=
GUID=
BALLAST=10
AI=fixed
"""


@pytest.fixture
def entry_file(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    ini = cfg_dir / "entry_list.ini"
    ini.write_text(ENTRY, encoding="utf-8")

    cars_dir = tmp_path / "content" / "cars" / "bmw_z4_gt3" / "skins"
    (cars_dir / "04_blu_white_27").mkdir(parents=True)
    (cars_dir / "07 white red").mkdir(parents=True)

    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))
    return ini


def test_lee_coches_con_modelo_y_skin(entry_file):
    result = entry_service.get_entry_list()

    assert result["total"] == 2
    assert result["cars"][0] == {
        "index": 0,
        "model": "bmw_z4_gt3",
        "skin": "04_blu_white_27",
    }
    # El SKIN entrecomillado se devuelve sin comillas.
    assert result["cars"][1]["skin"] == "07 white red"


def test_datos_de_jugadores_nunca_se_exponen(entry_file):
    result = entry_service.get_entry_list()

    assert "76561199999999999" not in str(result)
    assert "Piloto Uno" not in str(result)
    assert "Equipo A" not in str(result)
    for car in result["cars"]:
        assert set(car) == {"index", "model", "skin"}


def test_resumen_agrupado_por_modelo(entry_file):
    result = entry_service.get_entry_list()

    assert result["models"] == [
        {
            "model": "bmw_z4_gt3",
            "count": 2,
            "skins": ["04_blu_white_27", "07 white red"],
        }
    ]


def test_sin_archivo_devuelve_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    assert "error" in entry_service.get_entry_list()


def test_escribe_modelo_y_skin_y_conserva_jugadores(entry_file):
    result = entry_service.write_entry_list(
        [
            {"model": "bmw_z4_gt3", "skin": "04_blu_white_27"},
            {"model": "bmw_z4_gt3", "skin": "07 white red"},
        ]
    )

    assert result["total"] == 2
    text = entry_file.read_text(encoding="utf-8")
    # Los datos de la plaza 0 siguen en disco aunque no se expongan.
    assert "DRIVERNAME=Piloto Uno" in text
    assert "GUID=76561199999999999" in text
    assert "BALLAST=10" in text
    # El SKIN con espacios se guarda entrecomillado (formato AC).
    assert "SKIN='07 white red'" in text


def test_rechaza_modelo_no_instalado(entry_file):
    with pytest.raises(ValueError, match="no instalado"):
        entry_service.write_entry_list([{"model": "otro", "skin": "auto"}])


def test_rechaza_skin_no_instalada(entry_file):
    with pytest.raises(ValueError, match="no instalada"):
        entry_service.write_entry_list(
            [{"model": "bmw_z4_gt3", "skin": "no-existe"}]
        )


def test_acepta_skin_auto(entry_file):
    result = entry_service.write_entry_list(
        [{"model": "bmw_z4_gt3", "skin": "auto"}]
    )

    assert result["cars"][0]["skin"] == "auto"


def test_rechaza_rutas(entry_file):
    with pytest.raises(ValueError, match="rutas"):
        entry_service.write_entry_list(
            [{"model": "../fuera", "skin": "auto"}]
        )


def test_disponibles_listan_skins(entry_file):
    assert entry_service.get_available_cars() == [
        {
            "model": "bmw_z4_gt3",
            "skins": ["04_blu_white_27", "07 white red"],
        }
    ]


def test_ruta_entry_list(panel, entry_file):
    response = panel.get("/api/server/entry-list")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert "Piloto Uno" not in str(data)


def test_ruta_entry_list_sin_archivo_es_404(panel, tmp_path, monkeypatch):
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    response = panel.get("/api/server/entry-list")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_ruta_put_entry_list(panel, entry_file):
    response = panel.put(
        "/api/server/entry-list",
        json={"cars": [{"model": "bmw_z4_gt3", "skin": "auto"}]},
    )

    assert response.status_code == 200
    assert response.json()["cars"][0]["skin"] == "auto"


def test_ruta_put_entry_list_invalido_es_422(panel, entry_file):
    response = panel.put(
        "/api/server/entry-list",
        json={"cars": [{"model": "otro", "skin": "auto"}]},
    )

    assert response.status_code == 422


def test_ruta_put_entry_list_origen_externo_bloqueado(panel, entry_file):
    response = panel.put(
        "/api/server/entry-list",
        json={"cars": [{"model": "bmw_z4_gt3", "skin": "auto"}]},
        headers={"Origin": "https://sitio-malicioso.example"},
    )

    assert response.status_code == 403
    assert entry_service.get_entry_list()["total"] == 2


def test_rutas_nuevas_son_lecturas_publicas(panel, entry_file):
    for ruta in ("/api/server/tracks", "/api/server/available-cars"):
        response = panel.get(
            ruta, headers={"Origin": "https://sitio-malicioso.example"}
        )
        assert response.status_code == 200


def test_ruta_tracks_lista_pistas(panel, tmp_path, monkeypatch):
    (tmp_path / "content" / "tracks" / "spa").mkdir(parents=True)
    monkeypatch.setenv("ASSETOSERVER_FOLDER", str(tmp_path))

    response = panel.get("/api/server/tracks")

    assert response.json() == {"tracks": [{"name": "spa", "label": "spa"}]}
