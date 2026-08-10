# tests/test_f003_pg_entra_auth.py
"""
F-003 · Acceso a PostgreSQL sin contraseña (R12-R14).

**Estos tests VERIFICAN, no estrenan.** La decisión abierta DA-1 del diseño
(§9) se resolvió así: F-005 ya implementó `PG_AUTH_MODE=entra`
(`etl_sigrid/infrastructure/azure/entra_token.py` y
`etl_sigrid/infrastructure/postgres/conninfo.py`), de modo que F-003 no duplica
ese código: comprueba que cumple lo que R12-R14 exigen del despliegue.

Lo que añaden sobre los tests de F-005, que es la razón de que existan:

- R12 exige `sslmode=require` en la misma cadena que lleva el token; F-005 lo
  probaba por separado (modo TLS por un lado, token por otro).
- R13 exige que el modo `password` **no importe** `azure-identity`. F-005
  probaba que el comportamiento no cambia, no que el paquete no se toque.
- R14 exige que el fallo de token no filtre un token ya obtenido.

Sin red, sin BBDD y sin `azure-identity` instalado: la credencial es un doble.
"""

from __future__ import annotations

import ast
import builtins
import time
from pathlib import Path

import pytest

from config.settings import PostgresSettings
from etl_sigrid.infrastructure.azure import entra_token
from etl_sigrid.infrastructure.azure.entra_token import EntraTokenProvider
from etl_sigrid.infrastructure.postgres import conninfo

REPO_ROOT = Path(__file__).resolve().parents[1]

AZURE_HOST = "psql-albaranes-rs9k2.postgres.database.azure.com"

# Un valor que se reconoce de un vistazo si se cuela en un mensaje de error.
TOKEN_FALSO = "eyJhbGciOiJSUzI1NiJ9.TOKEN-QUE-NO-DEBE-APARECER.firma"


def _pg(**kwargs: object) -> PostgresSettings:
    """Configuración hermética: el `.env` del puesto no puede alterar el resultado."""
    base: dict[str, object] = {
        "host": AZURE_HOST,
        "port": 5432,
        "db": "sigrid_dm",
        "user": "sigrid_dm_app",
        "password": "",
        "sslmode": "",
        "auth_mode": "password",
    }
    base.update(kwargs)
    return PostgresSettings(_env_file=None, **base)  # type: ignore[arg-type]


class _TokenFalso:
    def __init__(self, token: str, expires_on: float) -> None:
        self.token = token
        self.expires_on = expires_on


class _CredencialFalsa:
    """Devuelve un token fijo sin tocar la red."""

    def __init__(self, token: str = TOKEN_FALSO, ttl_s: float = 3600.0) -> None:
        self.token = token
        self.ttl_s = ttl_s
        self.llamadas = 0

    def get_token(self, *scopes: str) -> _TokenFalso:
        self.llamadas += 1
        return _TokenFalso(self.token, time.time() + self.ttl_s)


class _CredencialQueCaduca:
    """Da un token a punto de caducar y revienta al renovarlo."""

    def __init__(self) -> None:
        self.llamadas = 0

    def get_token(self, *scopes: str) -> _TokenFalso:
        self.llamadas += 1
        if self.llamadas == 1:
            return _TokenFalso(TOKEN_FALSO, time.time() + 10.0)
        raise OSError("ManagedIdentityCredential authentication unavailable")


# ---------------------------------------------------------------------------
# R12 · token de Entra como contraseña, sobre TLS obligatorio
# ---------------------------------------------------------------------------


def test_f003_r12_conninfo_entra_usa_token_y_sslmode_require(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    En el job no hay contraseña: la cadena de conexión lleva el token de Entra
    y viaja cifrada. Las dos cosas, en la misma cadena.
    """
    credencial = _CredencialFalsa()
    monkeypatch.setattr(
        entra_token,
        "get_default_token_provider",
        lambda: EntraTokenProvider(credential=credencial),
    )

    pg = _pg(auth_mode="entra", password="CONTRASENA-QUE-NO-DEBE-VIAJAR")
    dsn = conninfo.make_conninfo_provider(pg)()

    assert TOKEN_FALSO in dsn, "la contraseña de la conexión debe ser el token"
    assert "CONTRASENA-QUE-NO-DEBE-VIAJAR" not in dsn
    assert "sslmode=require" in dsn, "un token en claro por la red sería peor que nada"
    assert credencial.llamadas == 1


# ---------------------------------------------------------------------------
# R13 · el modo por defecto no toca Entra ni azure-identity
# ---------------------------------------------------------------------------


def test_f003_r13_modo_password_no_toca_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    El desarrollo local sigue funcionando en una máquina sin `azure-identity`
    instalado y sin sesión de Azure: ni se importa el paquete ni se pide token.
    """
    importar_real = builtins.__import__

    def _importar(nombre: str, *args: object, **kwargs: object) -> object:
        if nombre.startswith("azure"):
            raise AssertionError(f"el modo 'password' ha importado {nombre}")
        return importar_real(nombre, *args, **kwargs)  # type: ignore[arg-type]

    def _sin_proveedor() -> EntraTokenProvider:
        raise AssertionError("el modo 'password' ha pedido un token de Entra")

    monkeypatch.setattr(builtins, "__import__", _importar)
    monkeypatch.setattr(entra_token, "get_default_token_provider", _sin_proveedor)

    pg = _pg(host="localhost", user="postgres", password="local")
    dsn = conninfo.make_conninfo_provider(pg)()

    assert "password=local" in dsn
    assert "sslmode=prefer" in dsn


def test_f003_r13_azure_identity_no_se_importa_al_cargar_la_configuracion() -> None:
    """
    El import de `azure-identity` está DENTRO de la función que lo necesita.

    Si subiera al nivel de módulo, arrancar el ETL en un puesto sin el paquete
    reventaría, y ese es el camino que recorre todo el mundo cada día.
    """
    for relativo in (
        "config/settings.py",
        "etl_sigrid/infrastructure/postgres/conninfo.py",
        "etl_sigrid/infrastructure/azure/entra_token.py",
    ):
        arbol = ast.parse((REPO_ROOT / relativo).read_text(encoding="utf-8"))
        for nodo in arbol.body:  # solo el nivel superior del módulo
            nombres: list[str] = []
            if isinstance(nodo, ast.Import):
                nombres = [alias.name for alias in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            assert not any(n.startswith("azure") for n in nombres), (
                f"{relativo} importa azure-identity al cargar el módulo"
            )


# ---------------------------------------------------------------------------
# R14 · si el token falla, se aborta sin filtrarlo
# ---------------------------------------------------------------------------


def test_f003_r14_fallo_de_token_aborta_sin_filtrar_el_token() -> None:
    """
    El caso real del job: el primer token se obtiene, la carga dura dos horas y
    la renovación falla. El error debe decir qué pasa y qué hacer, y no llevar
    dentro el token que sí se llegó a obtener.
    """
    credencial = _CredencialQueCaduca()
    proveedor = EntraTokenProvider(credential=credencial, margin_s=300)

    assert proveedor.get_token() == TOKEN_FALSO

    with pytest.raises(RuntimeError) as exc:
        proveedor.get_token()  # el cacheado ya está dentro del margen: se renueva

    mensaje = str(exc.value)
    assert TOKEN_FALSO not in mensaje, "el mensaje de error filtra el token"
    assert "TOKEN-QUE-NO-DEBE-APARECER" not in mensaje
    assert "PG_AUTH_MODE" in mensaje, "el error debe identificar la causa"
    assert credencial.llamadas == 2
