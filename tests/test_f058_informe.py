# tests/test_f058_informe.py
"""F-058 · R9–R13: lo que el informe y el CLI dicen de la regla de muestreo.

Informes construidos a mano y CLI con la campaña sustituida por un espía: ni
suite real ni red. La configuración de rigor se inyecta, nunca se lee la del
proyecto.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    InformeMutacion,
    Mutante,
    escribir_informe,
    lineas_comparables,
)
from harness.rigor import ReglaMuestreo

ALCANCE = Alcance(feature="F-990", origen="ficheros", ref_diff=("", ""),
                  lineas={"app/a.py": {1, 2, 3}})
CRITICO = ReglaMuestreo(por_linea=True, fraccion=0.6, suelo=100, techo=300, origen="nivel")
FIJO = ReglaMuestreo(por_linea=True, fraccion=None, suelo=None, techo=20, origen="nivel")
ORDEN = ReglaMuestreo(por_linea=False, fraccion=None, suelo=None, techo=30, origen="orden")


def _mutantes(cuantos: int) -> list[Mutante]:
    return [Mutante("app/a.py", i, 0, "x == 1", "x != 1", "comparacion")
            for i in range(1, cuantos + 1)]


def _texto(tmp_path: Path, evaluados: int = 120, supervivientes: int = 0,
           **campos) -> str:
    elegidos = _mutantes(evaluados)
    informe = InformeMutacion(
        feature="F-990", alcance=ALCANCE, mutantes_evaluados=elegidos,
        supervivientes=elegidos[:supervivientes],
        muertos=evaluados - supervivientes, **campos,
    )
    ruta = tmp_path / "informe.md"
    escribir_informe(informe, ruta)
    return ruta.read_text(encoding="utf-8")


# --- R9 -----------------------------------------------------------------------


def test_f058_r9_declara_la_reduccion_por_linea(tmp_path: Path) -> None:
    texto = _texto(tmp_path, generados=290, candidatos=200, regla=CRITICO,
                   muestreado=True, max_mutantes=120, semilla=20261030, nivel="critico")

    assert ("| Un mutante por línea | sí — 290 generados → 200 candidatos, uno por "
            "línea |") in texto


def test_f058_r9_sin_reduccion_lo_dice(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=30, generados=90, candidatos=90, regla=ORDEN,
                   muestreado=True, max_mutantes=30, semilla=1, nivel="critico")

    assert "| Un mutante por línea | no |" in texto


def test_f058_r9_sin_regla_no_hay_fila_nueva(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=20, generados=61, muestreado=True,
                   max_mutantes=20, semilla=20260820, nivel="estandar")

    assert "Un mutante por línea" not in texto
    assert ("| Muestreo | sí — 20 de 61 mutantes, semilla `20260820`, nivel "
            "`estandar` |") in texto


# --- R10, R11 -----------------------------------------------------------------


def test_f058_r10_muestreo_proporcional_con_su_motivo(tmp_path: Path) -> None:
    texto = _texto(tmp_path, generados=290, candidatos=200, regla=CRITICO,
                   muestreado=True, max_mutantes=120, semilla=20261030, nivel="critico")

    assert ("| Muestreo | sí — 120 de 200 candidatos, semilla `20261030`, nivel "
            "`critico`; tope: 60 % de 200 candidatos, acotado a [100, 300] |") in texto


def test_f058_r10_tope_fijo_del_nivel(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=20, generados=80, candidatos=50, regla=FIJO,
                   muestreado=True, max_mutantes=20, semilla=20260820, nivel="estandar")

    assert ("| Muestreo | sí — 20 de 50 candidatos, semilla `20260820`, nivel "
            "`estandar`; tope: tope fijo del nivel `estandar` |") in texto


def test_f058_r10_tope_fijado_a_mano(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=30, generados=90, candidatos=90, regla=ORDEN,
                   muestreado=True, max_mutantes=30, semilla=1, nivel="critico")

    assert "; tope: fijado a mano con `--max-mutantes` |" in texto


def test_f058_r10_el_motivo_sin_suelo_ni_techo(tmp_path: Path) -> None:
    regla = ReglaMuestreo(por_linea=False, fraccion=0.25, suelo=None, techo=None,
                          origen="nivel")

    assert regla.motivo(400) == "25 % de 400 candidatos, acotado a [0, sin techo]"


def test_f058_r11_completa_porque_cabe_en_el_tope(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=30, generados=70, candidatos=30, regla=CRITICO,
                   muestreado=False, max_mutantes=100, semilla=20261030, nivel="critico")

    assert ("| Muestreo | no: campaña completa (30 candidatos ≤ tope 100 del nivel "
            "`critico`) |") in texto


def test_f058_r11_completa_sin_tope_es_el_texto_de_hoy(tmp_path: Path) -> None:
    sin_tope = ReglaMuestreo(por_linea=True, fraccion=None, suelo=None, techo=None,
                             origen="orden")
    texto = _texto(tmp_path, evaluados=30, generados=70, candidatos=30, regla=sin_tope,
                   muestreado=False, max_mutantes=None, semilla=1, nivel="critico")

    assert "| Muestreo | no: campaña completa |" in texto


def test_f058_r10_r11_las_filas_nuevas_son_comparables(tmp_path: Path) -> None:
    texto = _texto(tmp_path, generados=290, candidatos=200, regla=CRITICO,
                   muestreado=True, max_mutantes=120, semilla=20261030, nivel="critico")
    comparables = "\n".join(lineas_comparables(texto))

    assert "| Un mutante por línea |" in comparables
    assert "| Muestreo | sí — 120 de 200 candidatos" in comparables


# --- R12 ----------------------------------------------------------------------

COTA_20 = "0 supervivientes en 20 → tasa real < 3/20 (15.0 %) al 95 % (regla del tres)"


def test_f058_r12_cero_supervivientes_en_muestra_da_la_cota(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=20, generados=80, candidatos=50, regla=FIJO,
                   muestreado=True, max_mutantes=20, semilla=1, nivel="estandar")

    supervivientes = texto.split("## Supervivientes", 1)[1]
    assert COTA_20 in supervivientes


def test_f058_r12_la_cota_usa_los_evaluados(tmp_path: Path) -> None:
    texto = _texto(tmp_path, generados=290, candidatos=200, regla=CRITICO,
                   muestreado=True, max_mutantes=120, semilla=1, nivel="critico")

    assert "0 supervivientes en 120 → tasa real < 3/120 (2.5 %) al 95 %" in texto


def test_f058_r12_sin_muestreo_no_hay_cota(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=20, generados=20, candidatos=20, regla=FIJO,
                   muestreado=False, max_mutantes=20, semilla=1, nivel="estandar")

    assert "regla del tres" not in texto


def test_f058_r12_con_supervivientes_no_hay_cota(tmp_path: Path) -> None:
    texto = _texto(tmp_path, evaluados=20, supervivientes=1, generados=80,
                   candidatos=50, regla=FIJO, muestreado=True, max_mutantes=20,
                   semilla=1, nivel="estandar")

    assert "regla del tres" not in texto


# --- R13: el CLI anuncia la regla antes de generar ---------------------------

RIGOR = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": False,
                     "un_mutante_por_linea": True, "max_mutantes": 13, "semilla": 4242},
        "critico": {"fase_red": True, "cobertura": True, "mutacion": True,
                    "un_mutante_por_linea": True, "fraccion_mutantes": 0.6,
                    "min_mutantes": 100, "max_mutantes": 300, "semilla": 20261030},
        "documental": {"fase_red": False, "cobertura": False, "mutacion": False},
    },
}


def _cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nivel: str,
         capturado: dict, *extra: str) -> int:
    (tmp_path / "harness").mkdir(exist_ok=True)
    (tmp_path / "harness" / "rigor.json").write_text(json.dumps(RIGOR), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ficha = {"id": "F-990", "rigor": nivel}
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [ficha])
    alcance = Alcance(feature="F-990", origen="rama", ref_diff=("dev", "feature/x"),
                      lineas={"app/a.py": {1}})
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)

    def espia(alcance, ejecutor, **kwargs):
        capturado.update(kwargs)
        return InformeMutacion(feature=alcance.feature, alcance=alcance)

    monkeypatch.setattr(mutacion, "ejecutar_campania", espia)
    return mutacion.main(["--feature", "F-990", "--raiz", str(tmp_path),
                          "--salida", str(tmp_path / "informe.md"), *extra],
                         ejecutor=object())


def test_f058_r13_el_cli_anuncia_la_regla_proporcional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capturado: dict = {}
    _cli(tmp_path, monkeypatch, "critico", capturado)

    assert capturado["regla"] == CRITICO and capturado["semilla"] == 20261030
    salida = capsys.readouterr().out
    assert ("Regla de muestreo (nivel critico): uno por línea sí; 60 % de los "
            "candidatos, suelo 100, techo 300; semilla 20261030.") in salida
    # El techo no es lo que se evalúa: la línea de tope fijo no se imprime.
    assert "Muestreo: hasta" not in salida


def test_f058_r13_el_cli_anuncia_el_tope_fijo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capturado: dict = {}
    _cli(tmp_path, monkeypatch, "estandar", capturado)

    salida = capsys.readouterr().out
    assert ("Regla de muestreo (nivel estandar): uno por línea sí; tope fijo 13; "
            "semilla 4242.") in salida
    assert capturado["regla"] == FIJO.__class__(True, None, None, 13, "nivel")
    # La línea de antes sigue: R27, nada de lo que se imprimía desaparece.
    assert "Muestreo: hasta 13 mutantes, semilla 4242" in salida


def test_f058_r13_r7_el_cli_con_tope_a_mano(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capturado: dict = {}
    _cli(tmp_path, monkeypatch, "critico", capturado, "--max-mutantes", "30")

    assert capturado["regla"] == ReglaMuestreo(True, None, None, 30, "orden")
    assert ("Regla de muestreo (nivel critico): uno por línea sí; tope fijado a mano "
            "30; semilla 20261030.") in capsys.readouterr().out


def test_f058_r13_r7_el_cli_sin_tope_a_mano(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capturado: dict = {}
    _cli(tmp_path, monkeypatch, "critico", capturado, "--max-mutantes", "0")

    assert capturado["regla"] == ReglaMuestreo(True, None, None, None, "orden")
    salida = capsys.readouterr().out
    assert "uno por línea sí; sin tope; semilla 20261030." in salida
    assert "Muestreo:" not in salida


def test_f058_r13_sin_regla_no_se_anuncia_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    capturado: dict = {}
    _cli(tmp_path, monkeypatch, "documental", capturado)

    assert capturado["regla"] is None
    assert "Regla de muestreo" not in capsys.readouterr().out
