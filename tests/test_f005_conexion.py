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

import psycopg
import pytest
from psycopg.sql import Composable

from config.settings import PostgresSettings
from etl_sigrid.infrastructure.azure import entra_token
from etl_sigrid.infrastructure.azure.entra_token import EntraTokenProvider
from etl_sigrid.infrastructure.postgres import conninfo
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client_from

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
# R7, R9, R10 · comportamiento del cliente al abrir sesión
# ---------------------------------------------------------------------------

class _CursorFalso:
    """Cursor que apunta lo que se ejecuta y devuelve lo que se le diga."""

    def __init__(self, conn: _ConexionFalsa) -> None:
        self._conn = conn

    def __enter__(self) -> _CursorFalso:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, query: object, params: object = None) -> None:
        # psycopg compone las sentencias con identificadores citados; se
        # renderizan igual que las mandaría al servidor.
        if isinstance(query, Composable):
            self._conn.sentencias.append(query.as_string(None))
        else:
            self._conn.sentencias.append(str(query))

    def fetchone(self) -> tuple[object, ...] | None:
        return self._conn.fetchone_devuelve

    def fetchall(self) -> list[tuple[object, ...]]:
        return []


class _ConexionFalsa:
    """Doble de psycopg.Connection: no habla con nada."""

    def __init__(self, dsn: str, autocommit: bool = False) -> None:
        self.dsn = dsn
        self.autocommit = autocommit
        self.sentencias: list[str] = []
        self.cerrada = False
        self.fetchone_devuelve: tuple[object, ...] | None = (1,)

    def cursor(self) -> _CursorFalso:
        return _CursorFalso(self)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self.cerrada = True


class _Psycopg:
    """Registro de todas las conexiones abiertas durante un test."""

    def __init__(self, fallo_en: str | None = None) -> None:
        self.conexiones: list[_ConexionFalsa] = []
        self._fallo_en = fallo_en

    def connect(self, dsn: str, autocommit: bool = False) -> _ConexionFalsa:
        if self._fallo_en and self._fallo_en in dsn:
            raise psycopg.OperationalError('database "sigrid_dm" does not exist')
        conn = _ConexionFalsa(dsn, autocommit=autocommit)
        self.conexiones.append(conn)
        return conn

    @property
    def dsns(self) -> list[str]:
        return [c.dsn for c in self.conexiones]

    @property
    def sentencias(self) -> list[str]:
        return [s for c in self.conexiones for s in c.sentencias]


def _instalar_psycopg_falso(
    monkeypatch: pytest.MonkeyPatch, fallo_en: str | None = None
) -> _Psycopg:
    doble = _Psycopg(fallo_en=fallo_en)
    monkeypatch.setattr(psycopg, "connect", doble.connect)
    return doble


def test_f005_r7_set_role_es_la_primera_sentencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Con PG_SET_ROLE configurado, cada sesión empieza con SET ROLE. Si no fuera
    la primera sentencia, los objetos creados antes tendrían otro propietario.
    """
    doble = _instalar_psycopg_falso(monkeypatch)
    cliente = build_postgres_client_from(
        _pg(host=AZURE_HOST, set_role="sigrid_dm_etl", auto_create_db=False)
    )

    with cliente.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")

    for conexion in doble.conexiones:
        assert conexion.sentencias, "toda sesión ejecuta algo"
        assert conexion.sentencias[0] == 'SET ROLE "sigrid_dm_etl"'

    # Sin rol configurado (desarrollo local) no se emite ningún SET ROLE.
    doble_local = _instalar_psycopg_falso(monkeypatch)
    cliente_local = build_postgres_client_from(_pg(set_role=""))
    with cliente_local.connection():
        pass
    assert not any("SET ROLE" in s for s in doble_local.sentencias)


def test_f005_r9_sin_autocreate_no_toca_la_base_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Con PG_AUTO_CREATE_DB=false no se abre conexión contra la base admin ni se
    ejecuta CREATE DATABASE. Es la salvaguarda contra el servidor compartido:
    albaranes y partes viven ahí.
    """
    doble = _instalar_psycopg_falso(monkeypatch)
    cliente = build_postgres_client_from(
        _pg(host=AZURE_HOST, auto_create_db=False, admin_db="postgres")
    )

    with cliente.connection():
        pass

    assert all("dbname=postgres" not in dsn for dsn in doble.dsns)
    assert all("CREATE DATABASE" not in s.upper() for s in doble.sentencias)
    assert all("pg_database" not in s for s in doble.sentencias)

    # Contraste: con auto_create_db=True sí se consulta la base admin.
    doble_auto = _instalar_psycopg_falso(monkeypatch)
    build_postgres_client_from(_pg(auto_create_db=True)).connection().__enter__()
    assert any("dbname=postgres" in dsn for dsn in doble_auto.dsns)


def test_f005_r10_base_ausente_mensaje_remite_al_runbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Si la base no existe y no se puede autocrear, el error dice qué ejecutar,
    no intenta crearla, y no filtra la contraseña.
    """
    doble = _instalar_psycopg_falso(monkeypatch, fallo_en="dbname=sigrid_dm")
    cliente = build_postgres_client_from(
        _pg(host=AZURE_HOST, auto_create_db=False, password="ESTA-NO-DEBE-VIAJAR")
    )

    with pytest.raises(RuntimeError) as exc, cliente.connection():
        pass

    mensaje = str(exc.value)
    assert "infra/sql/01_create_database.sql" in mensaje
    assert "docs/runbook_postgres_azure.md" in mensaje
    assert "ESTA-NO-DEBE-VIAJAR" not in mensaje
    assert "password=***" in mensaje
    assert not doble.conexiones, "no se abrió ninguna conexión útil, ni a la admin"


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
