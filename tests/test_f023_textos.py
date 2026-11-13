# tests/test_f023_textos.py
"""F-023 · Las reglas que no son código, escritas donde se leen (R25, R28, R29).

- C4 bis dice, SIEMPRE, que todo superviviente se reproduce a mano antes de
  arreglarlo y que, si serie y paralelo discrepan, vale la serie; el
  implementer remite ahí (una norma, un sitio).
- C4 bis dice qué hace el reviewer con un `indeterminado`.
- La guía del taller avisa del cambio de criterio en la entrada de la 1.9.0.
- `rigor.json` documenta la clave opcional sin declararla.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from harness.rigor import ESQUEMA_LOCAL

RAIZ = Path(__file__).resolve().parents[1]
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
IMPLEMENTER = RAIZ / ".claude" / "agents" / "implementer.md"
RIGOR = RAIZ / "harness" / "rigor.json"
GUIA = RAIZ.parent / "GUIA_INSTALACION.md"

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="la guía es del taller, no del proyecto",
)


def _plano(ruta: Path) -> str:
    """El texto con los saltos de línea y los espacios repetidos colapsados."""
    return re.sub(r"\s+", " ", ruta.read_text(encoding="utf-8"))


def _c4_bis() -> str:
    texto = _plano(CHECKPOINTS)
    inicio = texto.index("## C4 bis")
    return texto[inicio:texto.index("## C4 ter", inicio)]


def test_f023_r25_regla_reproducir_a_mano_y_vale_la_serie() -> None:
    bloque = _c4_bis()

    assert "se reproduce a mano antes de arreglarlo" in bloque
    assert "si serie y paralelo del mismo SHA discrepan, vale la serie" in bloque


def test_f023_r25_regla_el_implementer_remite_a_c4_bis() -> None:
    texto = _plano(IMPLEMENTER)

    assert "reproduce a mano" in texto
    assert "C4 bis" in texto
    assert "vale la serie" not in texto, "la norma vive en un solo sitio: C4 bis"


def test_f023_r7_los_indeterminados_no_bloquean_y_el_reviewer_los_menciona() -> None:
    bloque = _c4_bis()

    assert "Un `indeterminado` no es un muerto ni bloquea" in bloque
    assert "el reviewer lo menciona" in bloque


@es_el_taller
def test_f023_r28_la_guia_avisa_del_cambio_de_criterio() -> None:
    texto = _plano(GUIA)
    inicio = texto.index("### El veredicto del motor es verdad")
    entrada = texto[inicio:].replace("**", "")
    minusculas = entrada.lower()

    assert "la cifra de muertos puede bajar" in minusculas
    assert "el primer `--incremental` no mide entero" in minusculas
    assert "F-026" in entrada
    assert "ficheros_no_versionados" in entrada
    assert "rigor.local.json" in entrada


def test_f023_r29_rigor_documenta_la_clave_sin_declararla() -> None:
    datos = json.loads(RIGOR.read_text(encoding="utf-8"))

    assert "ficheros_no_versionados" in datos["mutacion"]["$doc"]
    assert "ficheros_no_versionados" not in datos["mutacion"]
    assert "ficheros_no_versionados" in ESQUEMA_LOCAL["mutacion"]
