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

import pytest

from config.settings import PostgresSettings

REPO_ROOT = Path(__file__).resolve().parents[1]

AZURE_HOST = "psql-albaranes-rs9k2.postgres.database.azure.com"


def _pg(**kwargs: object) -> PostgresSettings:
    """
    PostgresSettings hermético: `_env_file=None` evita que el .env del puesto
    donde corran los tests cambie el resultado.
    """
    base: dict[str, object] = {
        "host": "localhost",
        "port": 5432,
        "db": "sigrid_dm",
        "user": "postgres",
        "password": "",
        "admin_db": "postgres",
        "sslmode": "",
        "auth_mode": "password",
        "auto_create_db": True,
        "set_role": "",
        "readonly_role": "",
    }
    base.update(kwargs)
    return PostgresSettings(_env_file=None, **base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R1 · el modo TLS se configura, y por defecto depende del host
# ---------------------------------------------------------------------------

def test_f005_r1_sslmode_por_defecto_segun_host() -> None:
    """Vacío contra Azure = require; vacío en local = prefer; y lo explícito manda."""
    assert _pg(host=AZURE_HOST).effective_sslmode == "require"
    assert _pg(host="localhost").effective_sslmode == "prefer"

    # Un valor explícito se respeta (aquí uno más estricto que el defecto).
    assert _pg(host=AZURE_HOST, sslmode="verify-full").effective_sslmode == "verify-full"
    assert _pg(host="localhost", sslmode="disable").effective_sslmode == "disable"

    # El sufijo se reconoce sin importar mayúsculas ni espacios sobrantes.
    assert _pg(host=AZURE_HOST.upper()).effective_sslmode == "require"


# ---------------------------------------------------------------------------
# R2 · TLS débil contra un host de Azure aborta al construir la configuración
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("modo_debil", ["disable", "allow", "prefer"])
def test_f005_r2_sslmode_debil_contra_azure_aborta(modo_debil: str) -> None:
    """
    Contra un servidor de Azure con endpoint público no se conecta en claro:
    se aborta con un mensaje que nombra la variable y el valor exigido.
    """
    with pytest.raises(Exception) as exc:
        _pg(host=AZURE_HOST, sslmode=modo_debil)

    mensaje = str(exc.value)
    assert "PG_SSLMODE" in mensaje
    assert "require" in mensaje

    # El mismo valor contra un host local es perfectamente legítimo.
    assert _pg(host="localhost", sslmode=modo_debil).effective_sslmode == modo_debil


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
