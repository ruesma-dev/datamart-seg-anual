# tests/test_f015_rigor.py
"""F-015 · Niveles de rigor (R11, R14, R15, R16, R17, R19).

Sin red y sin BBDD: se leen ficheros del repositorio y estructuras en memoria.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.rigor import (
    PUERTAS,
    cargar_rigor,
    exige,
    nivel_de_feature,
    supervivientes_maximos,
    timeout_mutacion,
    umbral_cobertura,
    validar_features,
)

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RIGOR = RAIZ / "harness" / "rigor.json"


@pytest.fixture
def rigor() -> dict:
    return cargar_rigor(RUTA_RIGOR)


# --- R11: el umbral vive en rigor.json, no cableado -------------------------


def test_f015_r11_umbral_solo_en_rigor_json(rigor: dict) -> None:
    umbral = umbral_cobertura(rigor)

    assert isinstance(umbral, int)
    assert 0 < umbral <= 100
    # Está en el fichero de configuración, no en el código.
    crudo = json.loads(RUTA_RIGOR.read_text(encoding="utf-8"))
    assert crudo["cobertura"]["umbral_lineas_cambiadas"] == umbral

    # Y no hay valor por defecto escondido en el código: si falta, se para.
    with pytest.raises(ValueError, match="umbral_lineas_cambiadas"):
        umbral_cobertura({"cobertura": {}})


def test_f015_r11_el_umbral_no_esta_en_el_codigo_del_arnes(rigor: dict) -> None:
    umbral = str(umbral_cobertura(rigor))
    modulos = sorted((RAIZ / "harness").glob("*.py"))

    assert modulos, "el arnés debe tener herramientas en harness/"
    for modulo in modulos:
        texto = modulo.read_text(encoding="utf-8")
        assert f"= {umbral}" not in texto, modulo.name


def test_f015_r11_configuracion_invalida_se_rechaza(tmp_path: Path) -> None:
    roto = tmp_path / "rigor.json"
    roto.write_text('{"nivel_por_defecto": "inexistente"}', encoding="utf-8")

    with pytest.raises(ValueError):
        cargar_rigor(roto)


def test_f015_r11_timeout_de_mutacion_tambien_es_configuracion(rigor: dict) -> None:
    assert timeout_mutacion(rigor) > 0


# --- R15: resolución del nivel ----------------------------------------------


def test_f015_r15_sin_rigor_declarado_se_aplica_el_mas_exigente(rigor: dict) -> None:
    por_defecto = rigor["nivel_por_defecto"]

    # No declarar nivel NO es la vía fácil: cae en el más exigente.
    assert nivel_de_feature({"id": "F-042"}, rigor) == por_defecto
    assert nivel_de_feature({"id": "F-042", "rigor": None}, rigor) == por_defecto
    # Un valor inválido tampoco relaja nada.
    assert nivel_de_feature({"id": "F-042", "rigor": "flojito"}, rigor) == por_defecto
    # Y el más exigente exige las tres puertas.
    for puerta in PUERTAS:
        assert exige(por_defecto, puerta, rigor) is True
    assert supervivientes_maximos(por_defecto, rigor) == 0


def test_f015_r15_cada_nivel_declara_lo_que_exige(rigor: dict) -> None:
    assert nivel_de_feature({"id": "F-008", "rigor": "documental"}, rigor) == "documental"

    # Una feature documental no puede requerir mutación (R14).
    assert exige("documental", "mutacion", rigor) is False
    assert exige("documental", "cobertura", rigor) is False
    assert exige("documental", "fase_red", rigor) is False

    # El nivel estándar sí, pero admite supervivientes documentados.
    for puerta in PUERTAS:
        assert exige("estandar", puerta, rigor) is True
    assert supervivientes_maximos("estandar", rigor) is None


def test_f015_r15_puerta_desconocida_se_considera_exigida(rigor: dict) -> None:
    assert exige("documental", "puerta_que_no_existe", rigor) is True


def test_f015_r15_validacion_detecta_niveles_invalidos(rigor: dict) -> None:
    features = [
        {"id": "F-001", "rigor": "estandar"},
        {"id": "F-002"},  # sin declarar: legítimo, se aplica el más exigente
        {"id": "F-003", "rigor": "flojito"},
        {"id": "F-004", "rigor": 7},
    ]

    errores = validar_features(features, rigor)

    assert len(errores) == 2
    assert any("F-003" in e and "flojito" in e for e in errores)
    assert any("F-004" in e for e in errores)


def test_f015_r15_las_features_del_repositorio_declaran_niveles_validos(
    rigor: dict,
) -> None:
    datos = json.loads((RAIZ / "harness" / "features.json").read_text(encoding="utf-8"))

    assert validar_features(datos["features"], rigor) == []
