# tests/test_f024_meta_y_formato.py
"""
F-024 · Tests del DDL de `_meta` (R2, R13, R16, R17) y de los formatos de
salida (R6, R19, R20).

Los del DDL son ESTÁTICOS: leen `sql/ddl/00_meta.sql` como texto. No validan
SQL —eso lo hacen las verificaciones MANUAL contra BBDD real de R25 y R26—,
pero convierten en rojo inmediato la regresión más probable: que alguien
sustituya la migración idempotente por un `DROP` y se lleve por delante el
histórico de `_meta.etl_runs` en producción, o que renombre una columna que
leen el MCP y Power BI.

Ese fichero lo ejecuta `_bootstrap_schemas_and_meta` en la PRIMERA conexión de
cada proceso. O sea: cada noche, y cada vez que alguien lanza un comando. Por
eso todo lo que hay dentro tiene que ser idempotente, y por eso hay un test
que lo comprueba sentencia a sentencia.

Ninguno abre red ni BBDD.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.postgres.postgres_client import _split_sql_statements

REPO_ROOT = Path(__file__).resolve().parents[1]
RUTA_META = (
    REPO_ROOT
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "ddl" / "00_meta.sql"
)


def sql_meta() -> str:
    return RUTA_META.read_text(encoding="utf-8")


def sentencias() -> list[str]:
    """Las sentencias del fichero, sin comentarios de línea."""
    limpias = []
    for stmt in _split_sql_statements(sql_meta()):
        sin_comentarios = re.sub(r"(?m)^\s*--.*$", "", stmt).strip()
        if sin_comentarios:
            limpias.append(sin_comentarios)
    return limpias


# ---------------------------------------------------------------------------
# R2 · `_meta.etl_runs` conserva el histórico y gana `batch_id`
# ---------------------------------------------------------------------------


def test_f024_r2_ddl_meta_migra_sin_destruir() -> None:
    """La columna se AÑADE. Ni un `DROP`, ni una recreación de la tabla.

    El histórico de `_meta.etl_runs` es el único sitio donde consta cuánto tardó
    cada carga y qué pasó las noches que fallaron. Recrear la tabla para añadir
    una columna lo borraría, en producción, y en silencio.
    """
    texto = sql_meta()

    assert re.search(
        r"ALTER\s+TABLE\s+_meta\.etl_runs\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
        r"batch_id\s+TEXT",
        texto,
        re.IGNORECASE,
    ), "no se añade batch_id de forma idempotente"

    assert re.search(
        r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+\w+\s+ON\s+_meta\.etl_runs\s*\(\s*batch_id",
        texto,
        re.IGNORECASE,
    ), "batch_id no tiene índice idempotente"

    # El histórico se conserva: nada que borre datos ni estructura.
    for prohibido in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert prohibido not in texto.upper(), (
            f"00_meta.sql contiene '{prohibido}': se ejecuta en CADA arranque de "
            f"CADA proceso contra el datamart de producción"
        )

    # Y la tabla se sigue creando solo si no existe.
    assert re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+_meta\.etl_runs", texto, re.IGNORECASE
    )


def test_f024_r2_batch_id_admite_nulos() -> None:
    """`NULL` es el valor del histórico anterior a F-024, y `timings` tiene que
    seguir funcionando sobre él. Un `NOT NULL` sin default rompería el ALTER."""
    texto = sql_meta()
    columna = re.search(
        r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+batch_id\s+TEXT([^;]*)",
        texto,
        re.IGNORECASE,
    )
    assert columna is not None
    assert "NOT NULL" not in columna.group(1).upper()


def test_f024_r2_todas_las_sentencias_del_ddl_son_idempotentes() -> None:
    """Cada sentencia del fichero, una por una.

    No es un test de estilo: `_bootstrap_schemas_and_meta` ejecuta este fichero
    entero en la primera conexión de cada proceso. Una sentencia no idempotente
    aquí es un error en cada ejecución del pipeline a partir de la segunda.
    """
    idempotente = re.compile(
        r"^(CREATE\s+(OR\s+REPLACE\s+)?VIEW|"
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS|"
        r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS|"
        r"ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS)",
        re.IGNORECASE,
    )
    for stmt in sentencias():
        assert idempotente.match(stmt), (
            f"sentencia no idempotente en 00_meta.sql: {stmt[:80]!r}"
        )


def test_f024_r2_el_ddl_no_lleva_bloques_que_el_troceador_no_sabe_partir() -> None:
    """Sin `$$` ni comentarios de bloque: `_split_sql_statements` no los maneja
    y lo dice en su propio docstring."""
    texto = sql_meta()
    assert "$$" not in texto
    assert "/*" not in texto


# ---------------------------------------------------------------------------
# R13 · Vista `_meta.v_raw_state`
# ---------------------------------------------------------------------------


def test_f024_r13_vista_raw_state_definida_en_el_ddl() -> None:
    """Última ingesta por tabla. `CREATE OR REPLACE` porque el fichero se
    ejecuta en cada arranque."""
    texto = sql_meta()

    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_raw_state", texto, re.IGNORECASE
    ), "falta la vista _meta.v_raw_state"

    vista = _cuerpo_de_vista("v_raw_state")

    # Una fila por tabla: la más reciente manda.
    assert re.search(r"DISTINCT\s+ON\s*\(\s*step\s*\)", vista, re.IGNORECASE)
    # Solo las filas de ingesta, y el nombre de la tabla es el sufijo del step.
    assert "ingest_raw." in vista
    assert re.search(r"WHERE\s+step\s+LIKE", vista, re.IGNORECASE)
    # Desempate estable: sin el `id DESC` dos filas del mismo segundo bailan.
    assert re.search(
        r"ORDER\s+BY\s+step\s*,\s*started_at\s+DESC\s*,\s*id\s+DESC", vista, re.IGNORECASE
    )

    for columna in ("tabla", "status", "batch_id", "started_at", "finished_at", "filas"):
        assert re.search(rf"\b{columna}\b", vista), (
            f"v_raw_state no expone la columna '{columna}'"
        )


# ---------------------------------------------------------------------------
# R16 · Vista `_meta.v_frescura`
# ---------------------------------------------------------------------------

#: Las ocho columnas que consumen `check-frescura`, el MCP y Power BI. Se
#: escriben aquí como contrato: renombrar una en el SQL sin actualizar a sus
#: consumidores es exactamente el fallo que este test convierte en rojo.
COLUMNAS_FRESCURA = (
    "paso",
    "ultimo_ok_finished_at",
    "ultimo_ok_batch_id",
    "ultimo_ok_filas",
    "horas_desde_ultimo_ok",
    "ultimo_intento_started_at",
    "ultimo_intento_status",
    "ultimo_intento_error",
)


def test_f024_r16_vista_frescura_columnas_y_or_replace() -> None:
    texto = sql_meta()

    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_frescura", texto, re.IGNORECASE
    ), "falta la vista _meta.v_frescura"

    vista = _cuerpo_de_vista("v_frescura")

    for columna in COLUMNAS_FRESCURA:
        assert re.search(rf"\bAS\s+{columna}\b", vista, re.IGNORECASE), (
            f"v_frescura no expone la columna '{columna}' con ese nombre exacto"
        )


def test_f024_r16_frescura_separa_ultimo_ok_de_ultimo_intento() -> None:
    """No son la misma noticia: un `build_mart` que falló esta noche deja
    `mart` con lo de ayer, y el consumidor tiene que ver las dos cosas.

    Por eso el JOIN es LEFT: un paso que nunca terminó bien sigue apareciendo,
    con `ultimo_ok_*` a nulo. Un INNER JOIN lo escondería, que es justo el
    silencio que esta feature elimina.
    """
    vista = _cuerpo_de_vista("v_frescura")

    assert re.search(r"status\s*=\s*'SUCCESS'", vista, re.IGNORECASE), (
        "el bloque de 'último OK' no filtra por SUCCESS"
    )
    assert re.search(r"LEFT\s+JOIN", vista, re.IGNORECASE), (
        "el JOIN debe ser LEFT: un paso sin ningún OK tiene que seguir saliendo"
    )


def test_f024_r16_frescura_solo_mira_pasos_de_pipeline() -> None:
    """Pasos de nivel de pipeline (`step` sin punto), no sub-pasos ni tramos.

    Sin este filtro, `v_frescura` tendría una fila por cada uno de los 60
    tramos de `build_plan_mensual` y dejaría de ser legible.
    """
    vista = _cuerpo_de_vista("v_frescura")
    assert re.search(r"position\s*\(\s*'\.'\s+IN\s+step\s*\)\s*=\s*0", vista, re.IGNORECASE)


def test_f024_r16_las_horas_se_calculan_en_utc() -> None:
    """`started_at`/`finished_at` son TIMESTAMP sin zona escritos con
    `datetime.utcnow()`. Comparar contra un `now()` local daría el desfase
    horario de España como «antigüedad», y en verano son dos horas."""
    vista = _cuerpo_de_vista("v_frescura")
    assert re.search(r"now\(\)\s+AT\s+TIME\s+ZONE\s+'UTC'", vista, re.IGNORECASE)
    # Segundos a horas.
    assert "3600" in vista


def test_f024_r16_ninguna_vista_de_meta_lee_de_otra_capa() -> None:
    """Cero coste sobre el servidor compartido: las vistas solo tocan `_meta`.

    Si una vista de `_meta` leyera de `raw` o de `mart`, cada refresco de Power
    BI dispararía un escaneo sobre las tablas grandes del servidor que comparten
    `albaranes` y `partes`.
    """
    # Se miran los ORÍGENES (FROM / JOIN), no el texto entero: `ingest_raw.`
    # contiene `raw.` y buscar la subcadena a pelo daría un falso positivo.
    ajenos = {"raw", "stg", "mart", "cierre", "compras", "maestro", "retenciones", "aux"}

    for nombre in ("v_raw_state", "v_frescura"):
        vista = _cuerpo_de_vista(nombre)
        origenes = re.findall(
            r"(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", vista, re.IGNORECASE
        )
        assert origenes, f"{nombre} no lee de ningún sitio: ¿se ha vaciado la vista?"

        for origen in origenes:
            esquema = origen.split(".")[0] if "." in origen else ""
            assert esquema not in ajenos, (
                f"{nombre} lee de '{origen}': las vistas de _meta solo leen de _meta"
            )


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------


def _cuerpo_de_vista(nombre: str) -> str:
    """La sentencia completa que define una vista, sin sus comentarios."""
    for stmt in sentencias():
        if re.search(rf"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.{nombre}\b", stmt, re.I):
            return stmt
    pytest.fail(f"no hay ninguna sentencia que defina _meta.{nombre}")
