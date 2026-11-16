# tests/test_f026_textos.py
"""F-026 · Las reglas que no son código, escritas donde se leen (R22, R23, R27).

- `reviewer.md` extiende la prueba de control del cero al fichero sin
  mutantes y no deja pasar una declaración en `PENDIENTE`; C4 bis no cambia.
- `docs/PROPUESTAS.md` marca P-2 como aplicada por F-026, sin borrarla.
- La guía del taller avisa de lo que cambia al actualizar.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
REVIEWER = RAIZ / ".claude" / "agents" / "reviewer.md"
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
PROPUESTAS = RAIZ / "docs" / "PROPUESTAS.md"
GUIA = RAIZ.parent / "GUIA_INSTALACION.md"

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="la guía es del taller, no del proyecto",
)


def _plano(ruta: Path) -> str:
    """El texto con los saltos de línea y los espacios repetidos colapsados."""
    return re.sub(r"\s+", " ", ruta.read_text(encoding="utf-8")).replace("**", "")


def test_f026_r22_el_reviewer_extiende_la_prueba_del_cero_al_fichero() -> None:
    texto = _plano(REVIEWER)

    assert (
        "Si la campaña declara cero mutantes, en total o en un fichero de la "
        "sección «Ficheros sin mutantes»"
    ) in texto
    assert "ignorando la exclusión de alcance" in texto


def test_f026_r22_el_reviewer_no_deja_una_declaracion_pendiente() -> None:
    texto = _plano(REVIEWER)

    assert (
        "ningún superviviente con su análisis en `PENDIENTE` ni ningún fichero sin "
        "mutantes con su declaración en `PENDIENTE`"
    ) in texto


def test_f026_r22_c4_bis_no_lleva_la_regla() -> None:
    assert "Ficheros sin mutantes" not in CHECKPOINTS.read_text(encoding="utf-8")


@es_el_taller
def test_f026_r23_p2_aplicada_por_f026_sin_borrar_la_entrada() -> None:
    texto = _plano(PROPUESTAS)
    inicio = texto.index("## P-2")
    entrada = texto[inicio:texto.index("## P-3", inicio) if "## P-3" in texto else None]

    assert re.search(r"Aplicada el \d{4}-\d{2}-\d{2} por F-026", entrada)
    assert "format_spec" in entrada, "la entrada original se conserva"


@es_el_taller
def test_f026_r27_la_guia_avisa_de_lo_que_cambia_al_actualizar() -> None:
    texto = _plano(GUIA)
    inicio = texto.index("### Lo que el mutador no veía")
    entrada = texto[inicio:]
    minusculas = entrada.lower()

    assert "deja de ser comparable" in minusculas
    assert "el primer `--incremental` mide entero" in minusculas
    assert "Ficheros sin mutantes" in entrada
    assert re.search(r"\d\.\d{3} → \d\.\d{3} mutantes", entrada), "cifras de R26"


@es_el_taller
def test_f026_r27_la_entrada_de_la_guia_cabe_en_veinte_lineas() -> None:
    lineas = GUIA.read_text(encoding="utf-8").split("\n")
    inicio = next(i for i, linea in enumerate(lineas) if "### Lo que el mutador no veía" in linea)
    fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].startswith("#")),
               len(lineas))

    assert len([linea for linea in lineas[inicio:fin] if linea.strip()]) <= 20
