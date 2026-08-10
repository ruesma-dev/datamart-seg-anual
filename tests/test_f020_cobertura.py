# tests/test_f020_cobertura.py
"""F-020 · Puerta de cobertura agregada de un monorepo (R13, R14, R2).

Los `coverage.json` son fixtures inventados y el alcance se inyecta: aquí no se
ejecuta coverage de verdad, ni pytest, ni git, ni se abre conexión alguna.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import cobertura
from harness.alcance import Alcance
from harness.cobertura import fusionar_coberturas

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RIGOR = RAIZ / "harness" / "rigor.json"

FEATURES = {
    "features": [
        {
            "id": "F-042",
            "title": "Feature de prueba",
            "status": "in_progress",
            "sdd": True,
            "rigor": "estandar",
            "branch": "feature/F-042-x",
        }
    ]
}

DECLARACION = {
    "servicios": [
        {"nombre": "email", "ruta": "services/email", "lenguaje": "python"},
        {"nombre": "web", "ruta": "services/web", "lenguaje": "otro"},
    ]
}

#: La raíz mide 2 de 3 líneas; el servicio, 3 de 3. Agregado: 5 de 6 = 83,3 %.
COBERTURA_RAIZ = {
    "files": {"harness/util.py": {"executed_lines": [1, 2], "missing_lines": [3]}}
}
COBERTURA_EMAIL = {
    "files": {"app/flujo.py": {"executed_lines": [1, 2, 3], "missing_lines": []}}
}
ALCANCE = {"harness/util.py": {1, 2, 3}, "services/email/app/flujo.py": {1, 2, 3}}


def escribir(ruta: Path, datos: dict) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


@pytest.fixture
def monorepo(tmp_path: Path) -> dict:
    """Monorepo de mentira: dos servicios, coverage de la raíz y del servicio."""
    escribir(tmp_path / "harness" / "servicios.json", DECLARACION)
    (tmp_path / "services" / "email").mkdir(parents=True)
    (tmp_path / "services" / "web").mkdir(parents=True)
    escribir(tmp_path / "coverage.json", COBERTURA_RAIZ)
    escribir(tmp_path / "services" / "email" / "coverage.json", COBERTURA_EMAIL)
    features = escribir(tmp_path / "features.json", FEATURES)
    return {"tmp": tmp_path, "features": features}


def argumentos(entorno: dict) -> list[str]:
    return [
        "--config",
        str(RUTA_RIGOR),
        "--features",
        str(entorno["features"]),
        "--cov",
        str(entorno["tmp"] / "coverage.json"),
        "--raiz",
        str(entorno["tmp"]),
    ]


def preparar(
    monkeypatch: pytest.MonkeyPatch, lineas: dict[str, set[int]] | None = None
) -> None:
    monkeypatch.setattr(cobertura, "rama_actual", lambda *a, **k: "feature/F-042-x")
    monkeypatch.setattr(cobertura, "hay_coverage", lambda: True)
    alcance = Alcance(
        feature="F-042",
        origen="rama",
        ref_diff=("base", "feature/F-042-x"),
        lineas=dict(ALCANCE) if lineas is None else lineas,
    )
    monkeypatch.setattr(cobertura, "alcance_de_feature", lambda *a, **k: alcance)


# --- R13: fusión de los informes de cada servicio ---------------------------


def test_f020_r13_fusion_reprefija_rutas_de_servicio() -> None:
    fusionado = fusionar_coberturas(
        COBERTURA_RAIZ, [("services/email", COBERTURA_EMAIL)]
    )

    assert sorted(fusionado["files"]) == [
        "harness/util.py",
        "services/email/app/flujo.py",
    ]
    assert fusionado["files"]["services/email/app/flujo.py"]["executed_lines"] == [
        1,
        2,
        3,
    ]
    # El original no se toca: la fusión es una función pura.
    assert list(COBERTURA_EMAIL["files"]) == ["app/flujo.py"]


def test_f020_r13_fusion_sin_cobertura_de_raiz_y_con_separadores_de_windows() -> None:
    servicio = {"files": {"app\\flujo.py": {"executed_lines": [1], "missing_lines": []}}}

    fusionado = fusionar_coberturas(None, [("services\\email\\", servicio)])

    assert list(fusionado["files"]) == ["services/email/app/flujo.py"]


def test_f020_r13_porcentaje_agregado_contra_umbral_unico(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    salida = capsys.readouterr()
    assert codigo == 0, salida.err
    # 5 de 6 líneas: el porcentaje es UNO solo, no uno por servicio.
    assert "83.3% de 6 líneas cambiadas cubiertas (5/6" in salida.out


def test_f020_r13_un_servicio_en_rojo_hunde_el_agregado(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    escribir(
        monorepo["tmp"] / "services" / "email" / "coverage.json",
        {"files": {"app/flujo.py": {"executed_lines": [1], "missing_lines": [2, 3]}}},
    )
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    salida = capsys.readouterr()
    assert codigo == 1
    assert "50.0%" in salida.err


def test_f020_r13_declaracion_rota_tumba_la_puerta(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (monorepo["tmp"] / "harness" / "servicios.json").write_text("{roto", encoding="utf-8")
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    assert codigo == 1
    assert "no es JSON válido" in capsys.readouterr().err


# --- R14: lo que nadie mide cuenta como no cubierto -------------------------


def test_f020_r14_fichero_sin_medir_cuenta_como_no_cubierto(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Un módulo de un servicio que no aparece en NINGÚN coverage.json: o el
    # servicio no tiene suite, o ningún test lo importa. No sale gratis.
    modulo = monorepo["tmp"] / "services" / "email" / "app" / "sin_medir.py"
    modulo.parent.mkdir(parents=True, exist_ok=True)
    modulo.write_text("import os\n\n\ndef f(a):\n    return a + 1\n", encoding="utf-8")
    preparar(
        monkeypatch,
        lineas={**ALCANCE, "services/email/app/sin_medir.py": {1, 2, 3, 4, 5}},
    )

    codigo = cobertura.main(argumentos(monorepo))

    salida = capsys.readouterr()
    assert codigo == 1
    # 5 cubiertas de 9: las 3 líneas ejecutables del módulo sin medir suman al
    # denominador y a nadie al numerador.
    assert "(5/9" in salida.err


# --- R2: sin declaración, el camino de siempre ------------------------------


def test_f020_r2_cobertura_sin_servicios_camino_actual(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (monorepo["tmp"] / "harness" / "servicios.json").unlink()
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    salida = capsys.readouterr()
    # Sin declaración solo cuenta el coverage.json de la raíz: 2 de 3 = 66,7 %,
    # y el fichero del servicio no se mide (ni existe en disco).
    assert codigo == 1
    assert "(2/3" in salida.err


def test_f020_r2_sin_servicios_y_sin_coverage_json_pide_instalarlo(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (monorepo["tmp"] / "harness" / "servicios.json").unlink()
    (monorepo["tmp"] / "coverage.json").unlink()
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    assert codigo == 1
    assert cobertura.MENSAJE_INSTALACION in capsys.readouterr().err


def test_f020_r2_monorepo_sin_ninguna_medicion_pide_instalarlo(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (monorepo["tmp"] / "coverage.json").unlink()
    (monorepo["tmp"] / "services" / "email" / "coverage.json").unlink()
    preparar(monkeypatch)

    codigo = cobertura.main(argumentos(monorepo))

    assert codigo == 1
    assert cobertura.MENSAJE_INSTALACION in capsys.readouterr().err


def test_f020_r2_solo_mide_el_servicio_si_la_raiz_no_tiene_informe(
    monorepo: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (monorepo["tmp"] / "coverage.json").unlink()
    preparar(monkeypatch, lineas={"services/email/app/flujo.py": {1, 2, 3}})

    codigo = cobertura.main(argumentos(monorepo))

    assert codigo == 0
    assert "100.0%" in capsys.readouterr().out
