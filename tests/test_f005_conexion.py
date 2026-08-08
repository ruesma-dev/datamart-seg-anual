# tests/test_f005_conexion.py
"""
F-005 · Tests de conexión y autenticación contra Postgres (R1-R11, R41).

Ninguno toca red ni BBDD: la configuración se construye en memoria, psycopg se
sustituye por dobles que registran las sentencias, y la credencial de Entra es
un objeto falso.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# R41 · la descripción de la feature en el arnés ya no dice "aprovisionar"
# ---------------------------------------------------------------------------

def test_f005_r41_descripcion_de_la_feature_actualizada() -> None:
    """
    F-005 no aprovisiona ningún Flexible Server: crea la base sigrid_dm dentro
    del servidor que ya existe. La descripción del arnés debe decir eso.
    """
    features = json.loads((REPO_ROOT / "harness" / "features.json").read_text(encoding="utf-8"))
    f005 = next(f for f in features["features"] if f["id"] == "F-005")
    descripcion = f005["description"]

    assert "Aprovisionar" not in descripcion
    assert "sigrid_dm" in descripcion
    assert "psql-albaranes-rs9k2" in descripcion
