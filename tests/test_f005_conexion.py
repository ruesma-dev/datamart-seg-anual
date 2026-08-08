# tests/test_f005_conexion.py
"""
F-005 · Tests de conexión y autenticación contra Postgres (R1-R11, R41).

Ninguno toca red ni BBDD: la configuración se construye en memoria, psycopg se
sustituye por dobles que registran las sentencias, y la credencial de Entra es
un objeto falso.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from config.settings import PostgresSettings
from etl_sigrid.infrastructure.azure import entra_token
from etl_sigrid.infrastructure.azure.entra_token import EntraTokenProvider
from etl_sigrid.infrastructure.postgres import conninfo

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
# R3, R4, R5 · autenticación con token de Entra
# ---------------------------------------------------------------------------

class _TokenFalso:
    """Lo mínimo que devuelve azure.identity: valor y caducidad epoch."""

    def __init__(self, token: str, expires_on: float) -> None:
        self.token = token
        self.expires_on = expires_on


class _CredencialFalsa:
    """Credencial de mentira: cuenta llamadas y no toca la red."""

    def __init__(self, ttl_s: float = 3600.0) -> None:
        self.llamadas = 0
        self.scopes: list[str] = []
        self._ttl_s = ttl_s

    def get_token(self, *scopes: str) -> _TokenFalso:
        self.llamadas += 1
        self.scopes.extend(scopes)
        return _TokenFalso(f"token-{self.llamadas}", time.time() + self._ttl_s)


class _CredencialRota:
    """Credencial que falla como falla una máquina sin identidad configurada."""

    def get_token(self, *scopes: str) -> _TokenFalso:
        raise OSError("no managed identity endpoint found")


def test_f005_r3_entra_usa_token_y_no_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Con PG_AUTH_MODE=entra la contraseña de la cadena de conexión es el token,
    y PG_PASSWORD no se lee en absoluto.
    """
    credencial = _CredencialFalsa()
    monkeypatch.setattr(
        entra_token,
        "get_default_token_provider",
        lambda: EntraTokenProvider(credential=credencial),
    )

    pg = _pg(host=AZURE_HOST, auth_mode="entra", password="ESTA-NO-DEBE-VIAJAR")
    dsn = conninfo.make_conninfo_provider(pg)()

    assert "token-1" in dsn
    assert "ESTA-NO-DEBE-VIAJAR" not in dsn
    # Y se pide para el recurso de Azure Database for PostgreSQL, no para otro.
    assert credencial.scopes == ["https://ossrdbms-aad.database.windows.net/.default"]


def test_f005_r4_token_se_refresca_solo_cerca_de_caducar() -> None:
    """El token cacheado se reutiliza; se pide otro solo si caduca en < margen."""
    credencial = _CredencialFalsa(ttl_s=3600.0)
    provider = EntraTokenProvider(credential=credencial, margin_s=300)

    assert provider.get_token() == "token-1"
    assert provider.get_token() == "token-1"
    assert credencial.llamadas == 1, "un token con una hora de vida no se re-pide"

    # Ahora uno que caduca dentro del margen de 5 minutos: cada uso pide otro.
    credencial_corta = _CredencialFalsa(ttl_s=60.0)
    provider_corto = EntraTokenProvider(credential=credencial_corta, margin_s=300)

    assert provider_corto.get_token() == "token-1"
    assert provider_corto.get_token() == "token-2"
    assert credencial_corta.llamadas == 2


def test_f005_r5_sin_credencial_error_explicito_sin_fallback() -> None:
    """
    Si no hay token, se falla explicando el plan B. Nunca se cae en silencio a
    la contraseña: eso cambiaría el modelo de seguridad sin que nadie lo note.
    """
    provider = EntraTokenProvider(credential=_CredencialRota())

    with pytest.raises(RuntimeError) as exc:
        provider.get_token()

    mensaje = str(exc.value)
    assert "PG_AUTH_MODE=password" in mensaje
    assert "Key Vault" in mensaje

    # Y el fallo se propaga hasta quien construye la cadena de conexión: no se
    # devuelve una cadena con la contraseña dentro.
    pg = _pg(host=AZURE_HOST, auth_mode="entra", password="ESTA-NO-DEBE-VIAJAR")
    proveedor = conninfo.make_conninfo_provider(pg)
    entra_token._default_provider = EntraTokenProvider(credential=_CredencialRota())
    try:
        with pytest.raises(RuntimeError):
            proveedor()
    finally:
        entra_token._default_provider = None


def test_f005_r5_sin_paquete_azure_identity_error_explicito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin el paquete azure-identity instalado, el mensaje es el mismo plan B."""
    import builtins

    importar_real = builtins.__import__

    def _importar(nombre: str, *args: object, **kwargs: object) -> object:
        if nombre.startswith("azure.identity"):
            raise ImportError("No module named 'azure.identity'")
        return importar_real(nombre, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _importar)

    with pytest.raises(RuntimeError) as exc:
        EntraTokenProvider().get_token()

    assert "azure-identity" in str(exc.value)
    assert "PG_AUTH_MODE=password" in str(exc.value)


# ---------------------------------------------------------------------------
# R6 · nada de contraseñas ni tokens en los logs
# ---------------------------------------------------------------------------

def test_f005_r6_safe_dsn_redacta_password_y_token() -> None:
    """`safe_dsn` es lo único que puede registrarse. Redacta el secreto."""
    secreto = "Un4-Cl4ve-Muy-Larga"
    pg = _pg(host=AZURE_HOST, password=secreto)
    dsn = conninfo.build_conninfo(pg, secreto)

    redactado = conninfo.safe_dsn(dsn)

    assert secreto not in redactado
    assert "password=***" in redactado
    # Lo demás sigue siendo legible: si no, el log no sirve para diagnosticar.
    assert f"host={AZURE_HOST}" in redactado
    assert "dbname=sigrid_dm" in redactado
    assert "sslmode=require" in redactado

    # Un token de Entra ocupa el mismo sitio que la contraseña y se redacta igual.
    dsn_token = conninfo.build_conninfo(pg, "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.carga.firma")
    assert "eyJ0eXAi" not in conninfo.safe_dsn(dsn_token)

    # Contraseña con espacios y comillas: make_conninfo la cita, y el redactor
    # tiene que llevarse la cita entera, no media.
    dsn_raro = conninfo.build_conninfo(pg, "clave con espacios y ' comilla")
    assert "espacios" not in conninfo.safe_dsn(dsn_raro)


# ---------------------------------------------------------------------------
# R8 · el modo de hoy (contraseña, host local) no cambia
# ---------------------------------------------------------------------------

def test_f005_r8_modo_password_local_sin_regresion() -> None:
    """
    Un .env local intacto sigue produciendo la misma conexión: mismos host,
    puerto, base, usuario y contraseña, y `sslmode=prefer`, que es el valor
    por defecto de libpq y por tanto no cambia el comportamiento.
    """
    pg = _pg(host="localhost", port=5432, db="sigrid_dm", user="postgres", password="local")

    dsn = pg.conninfo
    assert "host=localhost" in dsn
    assert "port=5432" in dsn
    assert "dbname=sigrid_dm" in dsn
    assert "user=postgres" in dsn
    assert "password=local" in dsn
    assert "sslmode=prefer" in dsn

    admin = pg.admin_conninfo
    assert "dbname=postgres" in admin
    assert "dbname=sigrid_dm" not in admin

    # Y los defectos de los campos nuevos son los del comportamiento actual.
    assert pg.auth_mode == "password"
    assert pg.auto_create_db is True
    assert pg.set_role == ""
    assert pg.readonly_role == ""


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
