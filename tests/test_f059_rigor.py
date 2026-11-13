# tests/test_f059_rigor.py
"""F-059 · R21–R22: `e2e` como puerta OPCIONAL de un nivel de rigor.

Opcional porque meterla en `PUERTAS` rompería todo `rigor.json` instalado, que
declara solo las tres booleanas de siempre: ausente es «no exigida».
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.rigor import cargar_rigor, exige, informativa

RAIZ = Path(__file__).resolve().parents[1]
PUBLICADO_F058 = Path(__file__).with_name("f058_rigor_publicado.json")

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="harness/rigor.json es del taller, no del proyecto",
)


def _rigor(tmp_path: Path, **nivel: object) -> Path:
    datos = {
        "nivel_por_defecto": "n",
        "cobertura": {"umbral_lineas_cambiadas": 80},
        "niveles": {"n": {"fase_red": True, "cobertura": True, "mutacion": False, **nivel}},
    }
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


# --- R21 ----------------------------------------------------------------------


@pytest.mark.parametrize("valor", [1, "true", None, ["e2e"]])
def test_f059_r21_e2e_declarada_tiene_que_ser_booleana(tmp_path: Path, valor) -> None:
    with pytest.raises(ValueError, match="'e2e'"):
        cargar_rigor(_rigor(tmp_path, e2e=valor))


@pytest.mark.parametrize("valor", [True, False])
def test_f059_r21_e2e_booleana_se_carga_y_se_exige_si_es_true(tmp_path: Path, valor) -> None:
    rigor = cargar_rigor(_rigor(tmp_path, e2e=valor))

    assert exige("n", "e2e", rigor) is valor


def test_f059_r21_e2e_ausente_no_se_exige(tmp_path: Path) -> None:
    rigor = cargar_rigor(_rigor(tmp_path))

    assert exige("n", "e2e", rigor) is False
    assert informativa("n", "e2e", rigor) is False


def test_f059_r21_las_puertas_de_siempre_siguen_exigidas_si_faltan() -> None:
    rigor = {"niveles": {"n": {}}}

    assert exige("n", "mutacion", rigor) is True
    assert exige("desconocido", "e2e", rigor) is True


def test_f059_r21_e2e_admitida_en_informativas(tmp_path: Path) -> None:
    rigor = cargar_rigor(_rigor(tmp_path, informativas=["mutacion", "e2e"]))

    assert informativa("n", "e2e", rigor) is True
    assert exige("n", "e2e", rigor) is False


def test_f059_r21_e2e_no_puede_ser_exigida_e_informativa(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'e2e'"):
        cargar_rigor(_rigor(tmp_path, e2e=True, informativas=["e2e"]))


def test_f059_r21_una_puerta_desconocida_en_informativas_sigue_fallando(tmp_path) -> None:
    with pytest.raises(ValueError, match="informativas"):
        cargar_rigor(_rigor(tmp_path, informativas=["e2e_x"]))


def test_f059_r21_el_rigor_publicado_con_f058_carga_igual() -> None:
    rigor = cargar_rigor(PUBLICADO_F058)

    for nivel in rigor["niveles"]:
        assert exige(nivel, "e2e", rigor) is False
        assert informativa(nivel, "e2e", rigor) is False


# --- R22: el rigor.json del payload ------------------------------------------


@es_el_taller
def test_f059_r22_estandar_y_critico_informan_la_capa() -> None:
    rigor = cargar_rigor(RAIZ / "harness" / "rigor.json")

    for nivel in ("estandar", "critico"):
        assert informativa(nivel, "e2e", rigor), nivel
        assert exige(nivel, "e2e", rigor) is False


@es_el_taller
def test_f059_r22_critico_solo_informa_la_capa_e2e() -> None:
    """F-040 deja de fotografiar `informativas` de critico; esta foto la sustituye."""
    rigor = cargar_rigor(RAIZ / "harness" / "rigor.json")

    assert rigor["niveles"]["critico"]["informativas"] == ["e2e"]
    assert rigor["niveles"]["estandar"]["informativas"] == ["mutacion", "e2e"]


@es_el_taller
def test_f059_r22_documental_y_express_no_cambian() -> None:
    publicado = cargar_rigor(PUBLICADO_F058)
    rigor = cargar_rigor(RAIZ / "harness" / "rigor.json")

    for nivel in ("documental", "express"):
        assert rigor["niveles"][nivel] == publicado["niveles"][nivel], nivel


@es_el_taller
def test_f059_r22_el_doc_dice_que_la_puerta_la_decide_el_piloto() -> None:
    rigor = cargar_rigor(RAIZ / "harness" / "rigor.json")
    doc = " ".join(rigor["$doc"].split())

    assert "e2e" in doc and "F-047" in doc and "informativa" in doc
