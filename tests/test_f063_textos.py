# tests/test_f063_textos.py
"""F-063: lo que el payload dice (y no trae) sobre `harness/rigor.local.json`."""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _texto(relativa: str) -> str:
    return (RAIZ / relativa).read_text(encoding="utf-8")


def _seccion(texto: str, titulo: str) -> str:
    inicio = texto.index(titulo)
    fin = texto.find("\n## ", inicio + len(titulo))
    seccion = texto[inicio:] if fin == -1 else texto[inicio:fin]
    # En una sola línea y sin negritas: el ajuste de línea no cuenta.
    return " ".join(seccion.replace("**", "").split())


def test_f063_r2_el_payload_no_trae_capa_local() -> None:
    """Si la trajera, el modo `instalar` la crearía en el proyecto de destino."""
    assert not (RAIZ / "harness" / "rigor.local.json").exists()
    assert list(RAIZ.rglob("rigor.local.json")) == []


def test_f063_r23_checkpoints_niveles_de_rigor_nombra_la_capa_y_el_ok() -> None:
    seccion = _seccion(_texto("CHECKPOINTS.md"), "## Niveles de rigor")

    assert "harness/rigor.local.json" in seccion
    assert "OK explícito del humano" in seccion


def test_f063_r23_reviewer_exige_el_ok_si_el_diff_toca_la_capa() -> None:
    seccion = _seccion(_texto(".claude/agents/reviewer.md"),
                       "## Validación contra el nivel de rigor")

    assert "harness/rigor.local.json" in seccion
    assert "OK explícito del humano" in seccion
    assert "CHANGES_REQUESTED" in seccion
    assert "CAPA LOCAL DE RIGOR" in seccion


def test_f063_doc_de_rigor_json_apunta_a_la_capa_local() -> None:
    doc = json.loads(_texto("harness/rigor.json"))["$doc"]

    assert "harness/rigor.local.json" in doc
    assert "clave a clave" in doc
