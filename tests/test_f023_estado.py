# tests/test_f023_estado.py
"""F-023 · El estado anterior al criterio único se migra al cargar (R11, R12, R31, R32).

Decisión B+ del humano (2026-11-06): `VERSION_ESTADO` no sube. Un estado sin
`"criterio"` es heredado: `--incremental` lo migra EN MEMORIA —cada `muerto`
que no compila pasa a `indeterminado`, sin correr la suite— y el fichero solo
lo reescribe una campaña fiable. Un seguro cubre lo que la migración no ve: si
un muerto de la muestra de control vuelve indeterminado, se mide entero.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    DELTA_SOLO_TESTS,
    DELTA_VIGENTE,
    INDETERMINADO,
    MUERTO,
    InformeMutacion,
    Mutante,
    PlanIncremental,
    decidir_incremental,
    migrar_estado,
    plan_incremental,
)

FUENTE = "# app.py\ndef bandera():\n    return True\n"
VALIDO = Mutante("app.py", 3, 11, "return True", "return False", "booleano", 4, "False")
ROTO = Mutante("app.py", 3, 4, "return True", "(return True", "roto", 0, "(")


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(raiz: Path, mensaje: str) -> str:
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", mensaje)
    return _git(raiz, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    (raiz / "app.py").write_text(FUENTE, encoding="utf-8", newline="")
    _commit(raiz, "base")
    return raiz


def _entrada(m: Mutante, veredicto: str) -> dict:
    return {"fichero": m.fichero, "linea": m.linea, "col": m.col, "operador": m.operador,
            "original": m.original, "mutado": m.mutado, "veredicto": veredicto}


def _heredado(sha: str = "abc", **extra) -> dict:
    """Estado escrito por un arnés anterior a F-023: sin `criterio`."""
    return {"version": 1, "fiable": True, "feature": "F-999", "sha": sha, "nivel": None,
            "regla": None, "semilla": None, "generados": 2, "candidatos": None,
            "evaluados": [_entrada(VALIDO, MUERTO), _entrada(ROTO, MUERTO)], **extra}


def _alcance() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/x"),
                   lineas={"app.py": {3}})


# --- R12 · migrar_estado ------------------------------------------------------


def test_f023_r12_el_muerto_que_no_compila_pasa_a_indeterminado(repo: Path) -> None:
    estado = _heredado()

    migrado, cuantos = migrar_estado(estado, [VALIDO, ROTO], str(repo))

    assert cuantos == 1
    veredictos = {e["operador"]: e["veredicto"] for e in migrado["evaluados"]}
    assert veredictos == {"booleano": MUERTO, "roto": INDETERMINADO}
    assert estado["evaluados"][1]["veredicto"] == MUERTO, "es una COPIA: no muta la entrada"


def test_f023_r12_con_criterio_no_se_compila_nada(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mutacion, "compila", lambda *a: pytest.fail("no debía compilar"))
    estado = _heredado(criterio=mutacion.CRITERIO_ESTADO)

    migrado, cuantos = migrar_estado(estado, [VALIDO, ROTO], str(repo))

    assert (migrado, cuantos) == (estado, 0)


def test_f023_r12_migrar_dos_veces_es_migrar_una(repo: Path) -> None:
    una, _ = migrar_estado(_heredado(), [VALIDO, ROTO], str(repo))

    dos, cuantos = migrar_estado(una, [VALIDO, ROTO], str(repo))

    assert dos == una
    assert cuantos == 0


def test_f023_r12_el_plan_reevalua_el_migrado_sin_correr_la_suite(repo: Path) -> None:
    migrado, _ = migrar_estado(_heredado(), [VALIDO, ROTO], str(repo))

    plan = plan_incremental(migrado, None, None, None, [VALIDO, ROTO], (0.1, 1))

    assert isinstance(plan, PlanIncremental), plan
    assert plan.reevaluar == [ROTO]
    assert plan.control == [VALIDO]


def test_f023_r12_un_veredicto_desconocido_se_rechaza() -> None:
    estado = _heredado(criterio=mutacion.CRITERIO_ESTADO)
    estado["evaluados"][0]["veredicto"] = "medio_muerto"

    motivo = plan_incremental(estado, None, None, None, [VALIDO, ROTO], (0.1, 1))

    assert isinstance(motivo, str)
    assert "sin veredicto" in motivo


# --- R32 · heredado + vigente = plan corto, sin escribir al cargar ------------


def _vigente(repo: Path, monkeypatch: pytest.MonkeyPatch, estado_extra: dict) -> tuple:
    sha = _git(repo, "rev-parse", "HEAD")
    (repo / "progress").mkdir()
    (repo / "progress" / "notas.md").write_text("papeleo\n", encoding="utf-8")
    _commit(repo, "papeleo")
    monkeypatch.setattr(mutacion, "mutantes_del_alcance", lambda *a, **k: [VALIDO, ROTO])
    ruta = repo / "progress" / "mutacion_F-999.json"
    ruta.write_text(json.dumps(_heredado(sha, **estado_extra)), encoding="utf-8")
    antes = ruta.read_bytes()
    decision = decidir_incremental(mutacion.leer_estado(ruta), str(repo), _alcance(),
                                   None, None, None)
    assert ruta.read_bytes() == antes, "cargar no reescribe el estado"
    return decision


def test_f023_r32_heredado_y_vigente_ejecuta_el_plan_corto(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, plan, motivo = _vigente(repo, monkeypatch, {})

    assert decision == DELTA_SOLO_TESTS
    assert plan is not None and ROTO in plan.reevaluar
    assert "estado anterior a F-023: 1 muerto(s) no compilan" in motivo


def test_f023_r32_con_criterio_y_vigente_sigue_vigente(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, plan, _ = _vigente(repo, monkeypatch, {"criterio": mutacion.CRITERIO_ESTADO})

    assert decision == DELTA_VIGENTE
    assert plan is None


# --- R31 · el seguro del control ---------------------------------------------


def test_f023_r31_un_control_que_vuelve_indeterminado_obliga_a_medir_entero(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = PlanIncremental(desde="abc", reevaluar=[], control=[VALIDO], reutilizados=[ROTO],
                           generados=2, candidatos=2, limite=None)
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: _alcance())
    monkeypatch.setattr(mutacion, "decidir_incremental",
                        lambda *a, **k: (DELTA_SOLO_TESTS, plan, ""))
    llamadas: list[object] = []

    def campania(alcance, ejecutor, **opciones):
        llamadas.append(opciones.get("mutantes"))
        informe = InformeMutacion(feature="F-999", alcance=alcance, generados=2,
                                  mutantes_evaluados=[VALIDO, ROTO], muertos=1)
        if opciones.get("mutantes") is not None:
            informe.indeterminados = [VALIDO]
        else:
            informe.supervivientes = []
        return informe

    monkeypatch.setattr(mutacion, "ejecutar_campania", campania)

    mutacion.main(["--feature", "F-999", "--raiz", str(repo), "--workers", "1",
                   "--incremental", "--salida", str(repo / "progress" / "m.md")],
                  ejecutor=object())

    assert llamadas == [[VALIDO], None], "tras el aviso se mide entero"
    assert "muestra de control" in capsys.readouterr().out
