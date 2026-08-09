# tests/test_f015_cobertura.py
"""F-015 · Puerta de cobertura de las líneas cambiadas (R10, R12, R13).

Se cruza un JSON de `coverage` de mentira con un alcance de mentira: aquí no
se ejecuta coverage de verdad, ni pytest, ni se abre conexión alguna.
"""

from __future__ import annotations

import json
import re
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


def test_f015_r10_init_llama_a_la_puerta_de_cobertura() -> None:
    guion = (RAIZ / "harness" / "init.sh").read_text(encoding="utf-8")

    assert "harness.cobertura" in guion
    # Y la medición se hace de verdad, no se da por buena.
    assert "coverage run" in guion
    assert "coverage json" in guion


def test_f015_r11_init_sh_sin_umbral_cableado() -> None:
    guion = (RAIZ / "harness" / "init.sh").read_text(encoding="utf-8")
    umbral = json.loads(RUTA_RIGOR.read_text(encoding="utf-8"))["cobertura"][
        "umbral_lineas_cambiadas"
    ]

    # El número del umbral no aparece por ninguna parte del guion...
    assert str(umbral) not in guion
    # ...ni ningún otro porcentaje cableado...
    assert not re.search(r"\d+\s*%", guion)
    # ...y el guion apunta al fichero donde sí vive.
    assert "harness/rigor.json" in guion


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


def test_f015_r13_init_explica_como_instalar_la_medicion() -> None:
    guion = (RAIZ / "harness" / "init.sh").read_text(encoding="utf-8")

    assert "coverage" in guion
    assert "requirements-dev.txt" in guion


def test_f015_r13_la_disponibilidad_de_la_medicion_se_consulta_de_verdad() -> None:
    assert isinstance(cobertura.hay_coverage(), bool)


def test_f015_r12_la_rama_actual_se_lee_de_git() -> None:
    # git local, de solo lectura: ni red ni BBDD.
    assert cobertura.rama_actual(str(RAIZ)) != ""


def test_f015_r13_configuracion_de_rigor_ilegible_es_ko(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch)
    argumentos_rotos = argumentos(entorno)
    argumentos_rotos[1] = str(entorno["tmp"] / "no_existe.json")

    codigo = cobertura.main(argumentos_rotos)

    assert codigo == 1
    assert "PUERTA COBERTURA" in capsys.readouterr().err


def test_f015_r13_cobertura_json_corrupto_es_ko(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch)
    entorno["cov"].write_text("{no soy json", encoding="utf-8")

    codigo = cobertura.main(argumentos(entorno))

    assert codigo == 1
    assert "JSON" in capsys.readouterr().err


def test_f015_r12_alcance_irresoluble_es_na_con_motivo(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(cobertura, "rama_actual", lambda *a, **k: "feature/F-042-x")

    def no_hay_alcance(*args: object, **kwargs: object) -> None:
        raise SystemExit("ni rama ni merge")

    monkeypatch.setattr(cobertura, "alcance_de_feature", no_hay_alcance)

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "N/A" in salida and "ni rama ni merge" in salida


def test_f015_r12_lineas_cambiadas_sin_sentencias_es_na(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch, lineas={"modulo_x.py": {3}})  # solo comentarios

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "N/A" in salida and "ejecutables" in salida


def test_f015_r10_fichero_ni_medido_ni_existente_se_ignora(tmp_path: Path) -> None:
    assert cobertura_lineas_cambiadas(
        {"files": {}}, {"borrado.py": {1, 2}}, raiz=str(tmp_path)
    ) == (0, 0)


def test_f015_r10_fuente_que_no_compila_no_tiene_lineas_ejecutables() -> None:
    assert lineas_ejecutables("def f(:\n") == set()


def test_f015_r13_sin_fichero_de_cobertura_ko_si_aplica(
    entorno: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    preparar(monkeypatch)
    entorno["cov"].unlink()

    codigo = cobertura.main(argumentos(entorno))

    salida = capsys.readouterr()
    assert codigo == 1
    assert "requirements-dev.txt" in salida.out + salida.err
