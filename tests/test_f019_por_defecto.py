# tests/test_f019_por_defecto.py
"""F-019 · Pasada 2 (opción «b», humano 2026-11-10): selección APAGADA por defecto (R19).

Tras medir en T15 que la selección no ahorraba en la suite del payload, la
campaña juzga por defecto como la 1.9.0. Se enciende con `--con-seleccion` o
con la clave OPCIONAL `mutacion.seleccion_de_tests: true` (ausente = false); la
orden manda sobre la clave, y `--sin-seleccion` la apaga cuando la clave la
enciende. El comando de la cabecera y «Cómo se juzgó» lo dicen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import mutacion, rigor
from harness.alcance import Alcance
from harness.mutacion import (
    InformeMutacion,
    _analizar_argumentos,
    comando_de,
    escribir_informe,
    resolver_seleccion,
)
from harness.rigor import CapaLocalInvalida, seleccion_de_tests, validar_capa_local

RIGOR_PAYLOAD = Path(__file__).resolve().parents[1] / "harness" / "rigor.json"


def _con_clave(valor: object) -> dict:
    datos = json.loads(RIGOR_PAYLOAD.read_text(encoding="utf-8"))
    datos["mutacion"]["seleccion_de_tests"] = valor
    return datos


# --- R19 · la clave opcional ----------------------------------------------------


def test_f019_r19_ausente_es_false_y_el_rigor_de_la_1_9_0_sigue_valido() -> None:
    datos = json.loads(RIGOR_PAYLOAD.read_text(encoding="utf-8"))

    assert "seleccion_de_tests" not in datos["mutacion"], "no se declara: el defecto es false"
    rigor._validar_configuracion(datos, "rigor.json")
    assert seleccion_de_tests(datos) is False
    assert seleccion_de_tests({}) is False


@pytest.mark.parametrize("valor", [True, False])
def test_f019_r19_la_clave_booleana_vale(valor: bool) -> None:
    datos = _con_clave(valor)

    rigor._validar_configuracion(datos, "rigor.json")
    assert seleccion_de_tests(datos) is valor


@pytest.mark.parametrize("valor", ["true", 1, None])
def test_f019_r19_la_clave_no_booleana_se_rechaza(valor: object) -> None:
    with pytest.raises(ValueError, match="seleccion_de_tests"):
        rigor._validar_configuracion(_con_clave(valor), "rigor.json")


def test_f019_r19_la_capa_local_admite_la_clave(tmp_path: Path) -> None:
    validar_capa_local({"mutacion": {"seleccion_de_tests": True}}, tmp_path / "l.json")
    with pytest.raises(CapaLocalInvalida, match="seleccion_de_tests"):
        validar_capa_local({"mutacion": {"seleccion_de_tests": "si"}}, tmp_path / "l.json")


def test_f019_r19_el_doc_de_rigor_explica_la_clave_y_la_base_por_workers() -> None:
    doc = json.loads(RIGOR_PAYLOAD.read_text(encoding="utf-8"))["mutacion"]["$doc"]

    assert "seleccion_de_tests" in doc and "--con-seleccion" in doc
    assert "suelo*5*W" in doc
    assert "suelo*5." not in doc


# --- R19 · la orden manda sobre la clave ---------------------------------------


@pytest.mark.parametrize(
    ("con", "sin", "configurada", "esperada"),
    [
        (False, False, False, False),
        (False, False, True, True),
        (True, False, False, True),
        (True, False, True, True),
        (False, True, True, False),
        (False, True, False, False),
    ],
)
def test_f019_r19_resolver_seleccion(con: bool, sin: bool, configurada: bool, esperada: bool) -> None:
    assert resolver_seleccion(con, sin, configurada) is esperada


def test_f019_r19_las_dos_opciones_a_la_vez_no_valen(capsys: pytest.CaptureFixture[str]) -> None:
    assert _analizar_argumentos(["--feature", "F-019"]).con_seleccion is False
    with pytest.raises(SystemExit):
        _analizar_argumentos(["--feature", "F-019", "--con-seleccion", "--sin-seleccion"])


# --- R19 · el comando de la cabecera reproduce el modo -------------------------


def _informe(**campos: object) -> InformeMutacion:
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"), lineas={})
    informe = InformeMutacion(feature="F-019", alcance=alcance, workers=2)
    for clave, valor in campos.items():
        setattr(informe, clave, valor)
    return informe


@pytest.mark.parametrize(
    ("seleccion", "por_rigor", "cola"),
    [
        ("activa", False, " --workers 2 --con-seleccion"),
        ("degradada", False, " --workers 2 --con-seleccion"),
        ("activa", True, " --workers 2 --con-seleccion"),
        ("desactivada", False, " --workers 2"),
        ("desactivada", True, " --workers 2 --sin-seleccion"),
        (None, False, " --workers 2"),
    ],
)
def test_f019_r19_comando_de(seleccion: str | None, por_rigor: bool, cola: str) -> None:
    assert comando_de(_informe(seleccion=seleccion, seleccion_por_rigor=por_rigor)).endswith(
        f"--feature F-019{cola}"
    )


# --- R19 · «Cómo se juzgó» con la selección apagada ----------------------------


def test_f019_r19_apagada_por_defecto_lo_dice_y_dice_como_encenderla(tmp_path: Path) -> None:
    salida = tmp_path / "informe.md"
    escribir_informe(_informe(seleccion="desactivada"), salida)
    texto = salida.read_text(encoding="utf-8")

    assert "## Cómo se juzgó" in texto
    seccion = texto.split("## Cómo se juzgó", 1)[1].split("\n## ", 1)[0]
    assert "suite entera" in seccion and "1.9.0" in seccion
    assert "por defecto" in seccion
    assert "`--con-seleccion`" in seccion and "`mutacion.seleccion_de_tests: true`" in seccion
    assert "PODADO" not in seccion, "sin selección no hay nada que explicar de la poda"
    assert "| Selección de tests | desactivada (por defecto)" in texto


def test_f019_r19_apagada_por_la_orden_frente_a_la_clave(tmp_path: Path) -> None:
    salida = tmp_path / "informe.md"
    escribir_informe(_informe(seleccion="desactivada", seleccion_por_rigor=True), salida)
    texto = salida.read_text(encoding="utf-8")

    assert "| Selección de tests | desactivada (`--sin-seleccion`, la clave la encendía)" in texto


# --- R19 · el CLI -------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    llamadas: list[dict] = []
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"),
                      lineas={"harness/mutacion.py": {1}})

    def _campania(alc: Alcance, *_a: object, **kwargs: object) -> InformeMutacion:
        llamadas.append(dict(kwargs))
        informe = InformeMutacion(feature=alc.feature, alcance=alc, generados=1)
        informe.seleccion = "activa" if kwargs["seleccion"] else "desactivada"
        return informe

    monkeypatch.setattr("harness.mutacion.alcance_de_feature", lambda *_a, **_k: alcance)
    monkeypatch.setattr("harness.mutacion.ejecutar_campania", _campania)
    monkeypatch.setattr("harness.mutacion_paralela.ejecutar_campania_paralela", _campania)
    return llamadas


@pytest.mark.parametrize("workers", ["1", "2"])
@pytest.mark.parametrize(
    ("configurada", "opcion", "esperada", "cola"),
    [
        (False, [], False, ""),
        (False, ["--con-seleccion"], True, " --con-seleccion"),
        (True, [], True, " --con-seleccion"),
        (True, ["--sin-seleccion"], False, " --sin-seleccion"),
    ],
)
def test_f019_r19_el_cli_resuelve_y_pasa_la_seleccion(
    cli: list[dict], monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    capsys: pytest.CaptureFixture[str], workers: str, configurada: bool,
    opcion: list[str], esperada: bool, cola: str,
) -> None:
    monkeypatch.setattr(mutacion, "_seleccion_configurada", lambda: configurada)

    mutacion.main(["--feature", "F-019", "--workers", workers, *opcion,
                   "--salida", str(tmp_path / "a.md")])

    assert [k["seleccion"] for k in cli] == [esperada]
    cabecera = (tmp_path / "a.md").read_text(encoding="utf-8").splitlines()[3]
    assert cabecera.split("`")[1] == f"python -m harness.mutacion --feature F-019{cola}", cabecera
    salida = capsys.readouterr().out
    assert ("Selección de tests: activa" in salida) is esperada
    assert ("Selección de tests: DESACTIVADA" in salida) is not esperada
