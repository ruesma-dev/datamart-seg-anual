# tests/test_f015_cobertura.py
"""F-015 · Puerta de cobertura de las líneas cambiadas (R10, R12, R13).

Se cruza un JSON de `coverage` de mentira con un alcance de mentira: aquí no
se ejecuta coverage de verdad, ni pytest, ni se abre conexión alguna.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import cobertura
from harness.alcance import Alcance
from harness.cobertura import cobertura_lineas_cambiadas, lineas_ejecutables

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RIGOR = RAIZ / "harness" / "rigor.json"

COBERTURA_JSON = {
    "files": {
        "modulo_x.py": {"executed_lines": [1, 2, 5], "missing_lines": [7, 9]},
        # coverage escribe separadores del sistema: en Windows, contrabarra.
        "paquete\\modulo_y.py": {"executed_lines": [3], "missing_lines": [4]},
    }
}

FEATURES = {
    "features": [
        {
            "id": "F-042",
            "title": "Feature de prueba",
            "status": "in_progress",
            "sdd": True,
            "rigor": "estandar",
            "branch": "feature/F-042-x",
        },
        {
            "id": "F-043",
            "title": "Feature documental",
            "status": "in_progress",
            "sdd": False,
            "rigor": "documental",
            "branch": "feature/F-043-docs",
        },
    ]
}


@pytest.fixture
def entorno(tmp_path: Path) -> dict:
    """Deja en disco un features.json y un coverage.json de mentira."""
    features = tmp_path / "features.json"
    features.write_text(json.dumps(FEATURES), encoding="utf-8")
    cov = tmp_path / "coverage.json"
    cov.write_text(json.dumps(COBERTURA_JSON), encoding="utf-8")
    return {"features": features, "cov": cov, "tmp": tmp_path}


def argumentos(entorno: dict) -> list[str]:
    return [
        "--config",
        str(RUTA_RIGOR),
        "--features",
        str(entorno["features"]),
        "--cov",
        str(entorno["cov"]),
        "--raiz",
        str(entorno["tmp"]),
    ]


def preparar(
    monkeypatch: pytest.MonkeyPatch,
    rama: str = "feature/F-042-x",
    lineas: dict[str, set[int]] | None = None,
    coverage_disponible: bool = True,
) -> None:
    """Fija la rama actual, el alcance y la disponibilidad de coverage.

    Nada de esto toca git ni depende de qué haya instalado quien ejecuta los
    tests: el objeto de estos casos es la decisión de la puerta.
    """
    monkeypatch.setattr(cobertura, "rama_actual", lambda *a, **k: rama)
    monkeypatch.setattr(cobertura, "hay_coverage", lambda: coverage_disponible)
    alcance = Alcance(
        feature="F-042",
        origen="rama",
        ref_diff=("base", rama),
        lineas={"modulo_x.py": {1, 2, 3, 5, 7}} if lineas is None else lineas,
    )
    monkeypatch.setattr(cobertura, "alcance_de_feature", lambda *a, **k: alcance)


# --- R10: el cálculo --------------------------------------------------------


def test_f015_r10_calculo_de_cobertura_de_lineas_cambiadas() -> None:
    # Ejecutables del fichero: {1,2,5,7,9}. En el alcance: {1,2,5,7}.
    # Cubiertas de esas: {1,2,5}.
    cubiertas, totales = cobertura_lineas_cambiadas(
        COBERTURA_JSON, {"modulo_x.py": {1, 2, 3, 5, 7}}
    )

    assert (cubiertas, totales) == (3, 4)


def test_f015_r10_las_lineas_no_ejecutables_no_cuentan() -> None:
    # La 3 es un comentario o una línea en blanco: ni suma ni resta.
    assert cobertura_lineas_cambiadas(COBERTURA_JSON, {"modulo_x.py": {3}}) == (0, 0)


def test_f015_r10_separadores_de_windows_se_normalizan() -> None:
    assert cobertura_lineas_cambiadas(COBERTURA_JSON, {"paquete/modulo_y.py": {3, 4}}) == (
        1,
        2,
    )


def test_f015_r10_fichero_sin_medir_cuenta_como_no_cubierto(tmp_path: Path) -> None:
    # Un módulo nuevo que ningún test importa NO aparece en el JSON de
    # coverage: no puede salir gratis, cuenta entero como no cubierto.
    (tmp_path / "nuevo.py").write_text(
        "# nuevo.py\nimport os\n\n\ndef f(a):\n    return a + 1\n", encoding="utf-8"
    )

    cubiertas, totales = cobertura_lineas_cambiadas(
        {"files": {}}, {"nuevo.py": {1, 2, 3, 4, 5, 6}}, raiz=str(tmp_path)
    )

    assert cubiertas == 0
    assert totales == 3  # import, def y return


def test_f015_r10_lineas_ejecutables_de_un_fuente() -> None:
    fuente = "# comentario\nimport os\n\n\ndef f():\n    return 1\n"

    assert lineas_ejecutables(fuente) == {2, 5, 6}


def test_f015_r10_exit_1_bajo_el_umbral(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch)  # 3 de 4 = 75 %, por debajo del umbral de 80 %

    codigo = cobertura.main(argumentos(entorno))

    capturado = capsys.readouterr()
    salida = capturado.out + capturado.err
    assert codigo == 1
    assert "75" in salida
    assert "80" in salida


def test_f015_r10_exit_0_sobre_el_umbral(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch, lineas={"modulo_x.py": {1, 2, 5}})  # 3 de 3 = 100 %

    codigo = cobertura.main(argumentos(entorno))

    assert codigo == 0
    assert "100" in capsys.readouterr().out


# --- R12: cuándo la puerta NO aplica ----------------------------------------


def test_f015_r12_sin_diff_la_puerta_es_na_con_motivo(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch, lineas={})

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "N/A" in salida
    assert "producción" in salida or "produccion" in salida


def test_f015_r12_en_dev_o_main_la_puerta_es_na_con_motivo(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    for rama in ("dev", "main"):
        preparar(monkeypatch, rama=rama)

        codigo = cobertura.main(argumentos(entorno))

        salida = capsys.readouterr().out
        assert codigo == 0, rama
        assert "N/A" in salida and rama in salida


def test_f015_r12_nivel_documental_no_exige_cobertura(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch, rama="feature/F-043-docs")

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "N/A" in salida and "documental" in salida


def test_f015_r12_rama_sin_feature_declarada_es_na(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch, rama="feature/F-999-inventada")
    entorno["features"].write_text(json.dumps({"features": []}), encoding="utf-8")

    codigo = cobertura.main(argumentos(entorno))

    assert codigo == 0
    assert "N/A" in capsys.readouterr().out


# --- R13: sin la herramienta instalada --------------------------------------


def test_f015_r13_sin_coverage_ko_si_aplica_aviso_si_no(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # (a) La puerta aplica: no tener la herramienta es un KO, no una excusa.
    preparar(monkeypatch, coverage_disponible=False)
    codigo = cobertura.main(argumentos(entorno))
    salida = capsys.readouterr()
    assert codigo == 1
    assert "requirements-dev.txt" in salida.out + salida.err

    # (b) La puerta no aplica: degrada con aviso.
    preparar(monkeypatch, lineas={}, coverage_disponible=False)
    codigo = cobertura.main(argumentos(entorno))
    assert codigo == 0
    assert "N/A" in capsys.readouterr().out


def test_f015_r13_sin_fichero_de_cobertura_ko_si_aplica(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch)
    entorno["cov"].unlink()

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr()
    assert codigo == 1
    assert "requirements-dev.txt" in salida.out + salida.err
