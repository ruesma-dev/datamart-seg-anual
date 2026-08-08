# tests/test_f005_grants.py
"""
F-005 · Permisos del rol de solo lectura y barridos de seguridad
(R11, R14-R18, R21, R40).

Sin red ni BBDD: `build_readonly_grant_statements` es una función pura y el
paso del pipeline se prueba con un cliente Postgres de mentira.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import main
from etl_sigrid.application.orchestrator import Orchestrator
from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements

REPO_ROOT = Path(__file__).resolve().parents[1]

ESQUEMAS_CONSUMO = ("mart", "cierre", "compras", "maestro", "retenciones")
ESQUEMAS_INTERNOS = ("raw", "stg", "aux", "_meta")


# ---------------------------------------------------------------------------
# R14 · el rol de solo lectura recibe permisos exactamente sobre lo configurado
# ---------------------------------------------------------------------------

def test_f005_r14_grants_solo_sobre_los_esquemas_configurados() -> None:
    """
    Se conceden USAGE y SELECT sobre los esquemas que se pasan, y sobre ningún
    otro. La lista es un parámetro (PG_CONSUMPTION_SCHEMAS) precisamente porque
    su alcance es una decisión de negocio, no del código.

    DESVIACIÓN respecto a la spec: R14 exigía que NUNCA se concediera nada
    sobre raw, stg, aux, _meta ni public. El humano decidió el 2026-08-08 que
    de momento el MCP lee todo y que se revisará en F-006. Lo que el código
    garantiza, por tanto, es que no se concede nada fuera de la lista recibida.
    """
    sentencias = build_readonly_grant_statements(
        "mcp_sigrid_dm_ro", "sigrid_dm_etl", ESQUEMAS_CONSUMO
    )

    for esquema in ESQUEMAS_CONSUMO:
        assert f'GRANT USAGE ON SCHEMA "{esquema}" TO "mcp_sigrid_dm_ro"' in sentencias
        assert (
            f'GRANT SELECT ON ALL TABLES IN SCHEMA "{esquema}" TO "mcp_sigrid_dm_ro"'
            in sentencias
        )

    # Nada sobre los esquemas que no se han pedido.
    texto = "\n".join(sentencias)
    for interno in (*ESQUEMAS_INTERNOS, "public"):
        assert f'"{interno}"' not in texto

    # Y ni una sola sentencia de escritura: esto es un rol de solo lectura.
    for prohibido in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALL PRIVILEGES"):
        assert prohibido not in texto

    # El rol es siempre el destinatario, nunca aparece sin citar.
    assert all("mcp_sigrid_dm_ro" in s for s in sentencias)


def test_f005_r14_la_lista_ampliada_incluye_los_esquemas_internos() -> None:
    """
    Decisión del humano de 2026-08-08: el MCP lee todo de momento. Con la lista
    por defecto de PG_CONSUMPTION_SCHEMAS, los esquemas internos también entran.
    """
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    esquemas = [s.strip() for s in DEFAULT_CONSUMPTION_SCHEMAS.split(",")]
    for esquema in (*ESQUEMAS_CONSUMO, *ESQUEMAS_INTERNOS):
        assert esquema in esquemas

    sentencias = build_readonly_grant_statements("mcp_ro", "sigrid_dm_etl", esquemas)
    texto = "\n".join(sentencias)
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA "raw" TO "mcp_ro"' in texto
    assert 'GRANT SELECT ON ALL TABLES IN SCHEMA "_meta" TO "mcp_ro"' in texto


def test_f005_r14_identificadores_citados() -> None:
    """
    Los identificadores van citados: `_meta` empieza por guion bajo y un nombre
    de rol sin citar sería además una vía de inyección.
    """
    sentencias = build_readonly_grant_statements("rol raro", "dueño", ["_meta"])
    assert all('"_meta"' in s or "DATABASE" in s for s in sentencias)
    assert all('"rol raro"' in s for s in sentencias)


# ---------------------------------------------------------------------------
# R15 · privilegios por defecto para los objetos que aún no existen
# ---------------------------------------------------------------------------

def test_f005_r15_grants_incluyen_default_privileges() -> None:
    """
    ALTER DEFAULT PRIVILEGES FOR ROLE <propietario>: las vistas se recrean en
    cada ejecución, y sin esto nacerían ilegibles hasta el siguiente
    apply-grants.
    """
    sentencias = build_readonly_grant_statements(
        "mcp_sigrid_dm_ro", "sigrid_dm_etl", ESQUEMAS_CONSUMO
    )

    for esquema in ESQUEMAS_CONSUMO:
        esperada = (
            'ALTER DEFAULT PRIVILEGES FOR ROLE "sigrid_dm_etl" '
            f'IN SCHEMA "{esquema}" GRANT SELECT ON TABLES TO "mcp_sigrid_dm_ro"'
        )
        assert esperada in sentencias

    # Sin propietario configurado (desarrollo local) la regla aplica al rol de
    # la sesión: se omite FOR ROLE en vez de generar SQL inválido.
    locales = build_readonly_grant_statements("mcp_ro", "", ["mart"])
    assert 'ALTER DEFAULT PRIVILEGES IN SCHEMA "mart" GRANT SELECT ON TABLES TO "mcp_ro"' in locales
    assert not any("FOR ROLE" in s for s in locales)


def test_f005_r15_grant_connect_sobre_la_base_propia() -> None:
    """El GRANT CONNECT se emite sobre sigrid_dm y sobre ninguna otra base."""
    sentencias = build_readonly_grant_statements(
        "mcp_sigrid_dm_ro", "sigrid_dm_etl", ["mart"], database="sigrid_dm"
    )
    assert 'GRANT CONNECT ON DATABASE "sigrid_dm" TO "mcp_sigrid_dm_ro"' in sentencias
    assert sum(1 for s in sentencias if "ON DATABASE" in s) == 1


# ---------------------------------------------------------------------------
# R11 · nada de lo que el ETL ejecuta toca las otras bases del servidor
# ---------------------------------------------------------------------------

# El servidor psql-albaranes-rs9k2 aloja además dos bases en producción.
#
# OJO con el barrido: «albaranes» y «partes» son también vocabulario de negocio
# de Sigrid (compras.factura_lineas tiene una columna albaran_linea_id), así que
# buscar la palabra suelta da falsos positivos. Lo que hay que prohibir es la
# REFERENCIA A LA BASE: nombrarla en un DATABASE/dbname/\c, o abrir un camino
# entre bases con dblink o postgres_fdw.
BASES_AJENAS = ("albaranes", "partes")

PATRONES_BASE_AJENA = tuple(
    rf"""(?:\bDATABASE\s+|\bdbname\s*=\s*|\\c(?:onnect)?\s+)"?{base}"?\b"""
    for base in BASES_AJENAS
)

PATRONES_PROHIBIDOS = (
    r"\bALTER\s+SYSTEM\b",
    r"\bDROP\s+DATABASE\b",
    r"\bALTER\s+ROLE\b[^;]*\bSUPERUSER\b",
    r"\bCREATE\s+ROLE\b[^;]*\bSUPERUSER\b",
    # Los dos únicos mecanismos que permiten leer otra base desde esta.
    r"\bdblink\b",
    r"\bpostgres_fdw\b",
    r"\bIMPORT\s+FOREIGN\s+SCHEMA\b",
    r"\bCREATE\s+SERVER\b",
)


def _sql_del_etl() -> list[Path]:
    return sorted(REPO_ROOT.glob("etl_sigrid/**/*.sql"))


def test_f005_r11_barrido_estatico_sql_no_toca_otras_bases() -> None:
    """
    Barrido estático: ni el SQL del ETL, ni el de provisión, ni las sentencias
    que genera `build_readonly_grant_statements` nombran `albaranes` o `partes`
    ni contienen sentencias de ámbito de servidor.
    """
    ficheros = _sql_del_etl() + sorted(REPO_ROOT.glob("infra/sql/*.sql"))
    assert ficheros, "el barrido no encontró ningún .sql: revisa las rutas"

    for fichero in ficheros:
        texto = fichero.read_text(encoding="utf-8")
        sin_comentarios = re.sub(r"--[^\n]*", "", texto)

        for patron in PATRONES_BASE_AJENA:
            assert not re.search(patron, sin_comentarios, re.IGNORECASE), (
                f"{fichero} referencia una base ajena ({patron})"
            )

        for patron in PATRONES_PROHIBIDOS:
            assert not re.search(patron, sin_comentarios, re.IGNORECASE), (
                f"{fichero} contiene el patrón prohibido {patron}"
            )

        # CREATE DATABASE solo se admite en el script de provisión que el
        # humano ejecuta a mano; el ETL nunca lo lleva en un .sql.
        if fichero.name != "01_create_database.sql":
            assert not re.search(r"\bCREATE\s+DATABASE\b", sin_comentarios, re.IGNORECASE), (
                f"{fichero} contiene CREATE DATABASE"
            )

    # Y lo mismo para el SQL que se genera en tiempo de ejecución.
    generadas = "\n".join(
        build_readonly_grant_statements(
            "mcp_sigrid_dm_ro",
            "sigrid_dm_etl",
            ["mart", "cierre", "compras", "maestro", "retenciones", "raw", "stg", "aux", "_meta"],
            database="sigrid_dm",
        )
    )
    for base in BASES_AJENAS:
        assert base not in generadas.lower(), (
            "aquí sí vale la palabra suelta: las sentencias generadas solo "
            "nombran sigrid_dm y sus esquemas"
        )
    for patron in (*PATRONES_PROHIBIDOS, *PATRONES_BASE_AJENA, r"\bCREATE\s+DATABASE\b"):
        assert not re.search(patron, generadas, re.IGNORECASE)


# ---------------------------------------------------------------------------
# R16, R17, R18 · el paso del pipeline que reaplica los permisos
# ---------------------------------------------------------------------------

class _ClienteFalso:
    """Cliente Postgres de mentira: apunta qué se le pide y no abre nada."""

    def __init__(self, rol_existe: bool = True) -> None:
        self.rol_existe = rol_existe
        self.llamadas: list[str] = []
        self.grants: list[tuple[str, str, list[str]]] = []

    def role_exists(self, role: str) -> bool:
        self.llamadas.append(f"role_exists({role})")
        return self.rol_existe

    def apply_readonly_grants(
        self, readonly_role: str, owner_role: str, schemas: object
    ) -> list[str]:
        esquemas = list(schemas)  # type: ignore[call-overload]
        self.llamadas.append("apply_readonly_grants")
        self.grants.append((readonly_role, owner_role, esquemas))
        return build_readonly_grant_statements(readonly_role, owner_role, esquemas)


def _settings_falso(**postgres: object) -> SimpleNamespace:
    """Lo mínimo de Settings que mira el step."""
    base: dict[str, object] = {
        "readonly_role": "mcp_sigrid_dm_ro",
        "set_role": "sigrid_dm_etl",
        "consumption_schema_list": ["mart", "cierre"],
    }
    base.update(postgres)
    return SimpleNamespace(postgres=SimpleNamespace(**base))


def test_f005_r16_run_all_incluye_el_paso_de_grants() -> None:
    """
    `run-all` compone apply_grants, y el orquestador lo ordena DESPUÉS de
    build_mart: reaplicar permisos antes de recrear las vistas no serviría de
    nada.
    """
    steps = main.build_pipeline_steps(_settings_falso(), full_refresh=False)

    nombres = [s.name for s in steps]
    assert "apply_grants" in nombres

    paso = next(s for s in steps if s.name == "apply_grants")
    assert isinstance(paso, ApplyGrantsStep)
    assert paso.depends_on == ["build_mart"]
    assert paso.stage == "grants"

    orden = [s.name for s in Orchestrator(steps)._topological_sort()]
    assert orden.index("apply_grants") > orden.index("build_mart")
    assert orden[-1] == "apply_grants"


def test_f005_r17_sin_rol_configurado_el_paso_es_noop() -> None:
    """Sin PG_READONLY_ROLE el paso termina en SUCCESS sin ejecutar nada."""
    cliente = _ClienteFalso()
    paso = ApplyGrantsStep(_settings_falso(readonly_role=""), client=cliente)

    resultado = paso.run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.rows_processed == 0
    assert cliente.llamadas == [], "ni siquiera se preguntó al servidor"


def test_f005_r18_rol_inexistente_avisa_y_no_falla() -> None:
    """
    Un rol configurado pero inexistente no puede tumbar la carga nocturna: se
    avisa y el paso termina en SUCCESS.
    """
    cliente = _ClienteFalso(rol_existe=False)
    paso = ApplyGrantsStep(_settings_falso(), client=cliente)

    resultado = paso.run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.rows_processed == 0
    assert cliente.llamadas == ["role_exists(mcp_sigrid_dm_ro)"]
    assert "no existe" in (resultado.metadata.get("motivo") or "")


def test_f005_r16_el_paso_aplica_los_grants_con_el_propietario_correcto() -> None:
    """El camino normal: se aplican los permisos de los esquemas configurados."""
    cliente = _ClienteFalso()
    paso = ApplyGrantsStep(_settings_falso(), client=cliente)

    resultado = paso.run()

    assert resultado.status == StepStatus.SUCCESS
    assert resultado.rows_processed > 0
    rol, propietario, esquemas = cliente.grants[0]
    assert rol == "mcp_sigrid_dm_ro"
    # El propietario es el rol de grupo: los privilegios por defecto van por
    # rol creador, y quien crea los objetos es sigrid_dm_etl vía SET ROLE.
    assert propietario == "sigrid_dm_etl"
    assert esquemas == ["mart", "cierre"]


# ---------------------------------------------------------------------------
# R21, R40 · ni una contraseña en el repositorio
# ---------------------------------------------------------------------------

# Ficheros que F-005 añade o modifica y que podrían llevar un secreto dentro.
FICHEROS_VIGILADOS = (
    ".env.example",
    "requirements.txt",
    "infra/00_vars.ps1",
    "infra/15_provision_db.ps1",
    "infra/sql/01_create_database.sql",
    "infra/sql/02_roles.sql",
    "infra/sql/03_diagnostico.sql",
    "docs/runbook_postgres_azure.md",
    "docs/ARCHITECTURE.md",
)

# Asignaciones con valor a la derecha. Lo que se busca NO es la palabra
# 'password' —aparece por todas partes de forma legítima— sino que alguien haya
# escrito un valor detrás.
PATRONES_SECRETO = (
    # PG_PASSWORD=algo (se admite vacío y se admiten referencias tipo $VAR)
    r"PG_PASSWORD\s*=\s*(?!\s*$)(?![#\$%<])\S+",
    # password=algo dentro de una cadena de conexión
    r"\bpassword\s*=\s*(?![#\$%<'\"]|\*)\S+",
    # PASSWORD 'literal' en SQL (lo legítimo es PASSWORD :'variable')
    r"\bPASSWORD\s+'[^']+'",
    # Cadenas con pinta de clave generada: 24+ caracteres de base64
    r"[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])",
)


def test_f005_r21_barrido_de_secretos_en_el_arbol() -> None:
    """
    Ninguno de los ficheros que toca F-005 contiene una contraseña.

    La contraseña del rol del MCP la genera el humano, vive en Key Vault y no
    entra en el repositorio, ni en specs/, ni en progress/, ni en un log.
    """
    for relativo in FICHEROS_VIGILADOS:
        fichero = REPO_ROOT / relativo
        assert fichero.exists(), f"falta {relativo}"
        texto = fichero.read_text(encoding="utf-8-sig")

        for patron in PATRONES_SECRETO:
            encontrado = re.search(patron, texto)
            assert encontrado is None, (
                f"{relativo} parece contener un secreto: {encontrado.group(0)!r} "
                f"(patrón {patron})"
            )


def test_f005_r40_ni_env_example_ni_infra_contienen_secretos() -> None:
    """
    `.env.example` documenta las variables nuevas con valor vacío, y los
    scripts de provisión reciben las contraseñas por variable, nunca literal.
    """
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    for variable in (
        "PG_SSLMODE",
        "PG_AUTH_MODE",
        "PG_AUTO_CREATE_DB",
        "PG_SET_ROLE",
        "PG_READONLY_ROLE",
        "PG_CONSUMPTION_SCHEMAS",
    ):
        assert variable in env_example, f"{variable} no está documentada"

    # PG_PASSWORD sigue existiendo, y sigue vacía.
    assert re.search(r"^PG_PASSWORD=\s*$", env_example, re.MULTILINE)

    # El SQL de roles recibe las contraseñas por variable de psql.
    roles = (REPO_ROOT / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    assert ":'app_pwd'" in roles
    assert ":'mcp_pwd'" in roles

    # Y el .env real jamás se versiona.
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env$", gitignore, re.MULTILINE)
