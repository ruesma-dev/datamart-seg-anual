# tests/test_f150_diccionario.py
"""
F-150 · Diccionario y documentación de la receta (R2-R6, R15, R32).

Sin red ni base: leen los YAML del diccionario y los Markdown del árbol.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_CONVENTIONS = RAIZ / "docs" / "CONVENTIONS.md"
RUTA_ARCHITECTURE = RAIZ / "docs" / "ARCHITECTURE.md"
RUTA_CLAUDE = RAIZ / "CLAUDE.md"


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


# ===========================================================================
# R6 · la excepción acotada de D1 en las convenciones y la arquitectura
# ===========================================================================


def test_f150_r6_conventions_recoge_la_excepcion_acotada() -> None:
    texto = _texto(RUTA_CONVENTIONS)
    tramo = texto[texto.index("Excepción acotada (F-150, D1)"):]
    tramo = tramo[: tramo.index("## Tests")]
    assert "tesoreria.hipotesis_caja" in tramo
    assert "config/hipotesis_caja.yaml" in tramo, "los valores siguen en el YAML"
    assert "objetos del datamart" in tramo
    assert "PASOS_RECETA" in tramo and "paso_receta" in tramo


def test_f150_r6_architecture_describe_la_receta() -> None:
    texto = _texto(RUTA_ARCHITECTURE)
    tramo = texto[texto.index("**La receta de la caja (F-150"):]
    tramo = tramo[: tramo.index("**`descompuestos` (F-097")]
    for clave in ("D1", "PASOS_RECETA", "paso_receta", "coeficiente_venta", "MEDIA_OBRA",
                  "raw.dvf", "raw.iva", "include_columns", "80 tablas", "stg.presupuesto"):
        assert clave in tramo, clave


def test_f150_r32_docs_dicen_27_hipotesis() -> None:
    assert "las 27 (H01-H27 desde F-150)" in _texto(RUTA_ARCHITECTURE)
    claude = _texto(RUTA_CLAUDE)
    assert "las 27 hipótesis de `config/hipotesis_caja.yaml`" in claude
    assert "las 23 hipótesis" not in claude
    assert "**la receta**" in claude and "paso_receta" in claude
