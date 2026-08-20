# tests/test_f006_publicacion.py
"""
F-006 · La publicación del diccionario en `_meta` (R15, R17-R23).

Esto es **la mitad del contrato con el repositorio `mcp-bbdd`**, y lo único que
este repositorio puede garantizarle: nombres de tabla, de columna y de vista
estables, y una publicación atómica. El otro lado —que el MCP lea `_meta` en vez
de su YAML local— no se puede garantizar desde aquí.

De ahí que estos tests sean tan literales con el DDL: no comprueban que «algo
parecido» exista, comprueban el contrato letra a letra, porque alguien va a
programar contra él sin poder preguntar.

Ningún test de este fichero abre conexión a la base. El `.env` de este puesto
apunta a `psql-albaranes-rs9k2`, compartido con `albaranes` y `partes` en
producción: todo lo que exige una base real queda como verificación
`MANUAL (humano)` y está listado en `progress/impl_F-006.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DDL = RAIZ / "etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql"


def _ddl() -> str:
    return DDL.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", " ", texto)


def _cuerpo_de_la_vista() -> str:
    """Solo el `CREATE OR REPLACE VIEW`, hasta su `;`.

    Sin este recorte, el `COMMENT ON VIEW` que explica el contrato entra en la
    comprobación y la rompe: su texto menciona `JOIN` y `DROP VIEW` justamente
    para advertir de ellos.
    """
    limpio = _sin_comentarios(_ddl())
    inicio = limpio.upper().index("CREATE OR REPLACE VIEW _META.V_DICCIONARIO")
    return limpio[inicio:].split(";")[0]


# ---------------------------------------------------------------------------
# ddl · las tres tablas y la vista
# ---------------------------------------------------------------------------


def test_f006_r17_ddl_el_fichero_existe_y_se_declara() -> None:
    assert DDL.exists()
    assert _ddl().splitlines()[0].strip().startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql"
    )


@pytest.mark.parametrize(
    "tabla",
    ["_meta.diccionario", "_meta.diccionario_reglas", "_meta.diccionario_publicacion"],
)
def test_f006_r17_ddl_crea_las_tres_tablas_de_forma_idempotente(tabla: str) -> None:
    """`CREATE TABLE IF NOT EXISTS`: el DDL se ejecuta en cada publicación."""
    assert re.search(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{re.escape(tabla)}\s*\(",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    ), f"falta el CREATE TABLE IF NOT EXISTS de {tabla}"


def test_f006_r18_ddl_no_hace_drop_de_nada() -> None:
    """LA REGLA QUE NO SE PUEDE ROMPER: un `DROP` se lleva los `GRANT`.

    Es el problema que ya obliga a reaplicar los permisos cada noche. Si estas
    tablas se recrearan, el rol del MCP se quedaría sin lectura sobre ellas
    hasta el `apply-grants` siguiente, es decir, justo cuando más falta hace.
    """
    # Se miran las SENTENCIAS, no el texto: la cabecera y el `COMMENT ON` de la
    # vista mencionan `DROP VIEW` a propósito, para advertir de lo que cuesta.
    sentencias = [s.strip() for s in _sin_comentarios(_ddl()).split(";")]
    verbos = [s.split()[0].upper() for s in sentencias if s.split()]

    assert "DROP" not in verbos
    assert "TRUNCATE" not in verbos, (
        "el vaciado es DELETE dentro de la transacción de publicación, no aquí"
    )


def test_f006_r15_ddl_crea_la_vista_con_create_or_replace() -> None:
    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_diccionario\s+AS",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    )


def test_f006_r15_ddl_los_dos_joins_de_la_vista_son_left() -> None:
    """Los dos son deliberados y por motivos distintos.

    El de `v_frescura`, porque un objeto cuyo paso nunca terminó bien tiene que
    seguir saliendo con la frescura a nulo: esconderlo sería el silencio que
    F-024 eliminó. El de `diccionario_publicacion`, un `LEFT JOIN ... ON TRUE` y
    no un `CROSS JOIN`, porque con la tabla vacía un `CROSS JOIN` devolvería
    CERO filas y la vista mentiría diciendo que no hay diccionario.
    """
    vista = _cuerpo_de_la_vista()

    assert re.search(r"LEFT\s+JOIN\s+_meta\.v_frescura", vista, re.IGNORECASE)
    assert re.search(
        r"LEFT\s+JOIN\s+_meta\.diccionario_publicacion\s+AS\s+p\s+ON\s+TRUE",
        vista,
        re.IGNORECASE,
    )
    assert "CROSS JOIN" not in vista.upper()
    for union in re.finditer(r"(\w+)\s+JOIN\b", vista, re.IGNORECASE):
        assert union.group(1).upper() == "LEFT", f"JOIN no LEFT: {union.group(0)}"


def test_f006_r22_ddl_la_publicacion_es_un_singleton() -> None:
    """`CHECK (id = 1)`: no hay forma de que queden dos versiones publicadas."""
    assert re.search(
        r"id\s+SMALLINT\s+PRIMARY\s+KEY\s+DEFAULT\s+1\s+CHECK\s*\(\s*id\s*=\s*1\s*\)",
        _sin_comentarios(_ddl()),
        re.IGNORECASE,
    )


@pytest.mark.parametrize(
    ("tabla", "columnas"),
    [
        (
            "_meta.diccionario",
            [
                "esquema", "objeto", "tipo", "capa", "consumo_recomendado",
                "motivo_no_consumo", "descripcion", "grano", "clave_negocio",
                "paso_etl", "refresco", "avisos", "n_columnas", "ficha",
            ],
        ),
        (
            "_meta.diccionario_reglas",
            ["codigo", "titulo", "severidad", "ambito", "regla", "motivo", "orden"],
        ),
        (
            "_meta.diccionario_publicacion",
            [
                "id", "version", "hash_fuente", "publicado_en", "batch_id",
                "n_objetos", "n_reglas", "n_columnas", "cobertura_cols",
            ],
        ),
    ],
)
def test_f006_r22_ddl_el_contrato_de_columnas_es_exacto(
    tabla: str, columnas: list[str]
) -> None:
    """`design.md` §4.1 letra a letra: `mcp-bbdd` programa contra esto."""
    from tests.test_f006_fichas import columnas_del_create_table

    reales = columnas_del_create_table(_ddl(), tabla)

    assert reales == columnas, f"{tabla}: {reales}"


def test_f006_r22_ddl_los_tipos_del_contrato_no_se_improvisan() -> None:
    """Los que un cliente necesita conocer para deserializar sin adivinar."""
    limpio = _sin_comentarios(_ddl())

    assert re.search(r"clave_negocio\s+TEXT\[\]", limpio, re.IGNORECASE)
    assert re.search(r"avisos\s+TEXT\[\]", limpio, re.IGNORECASE)
    assert re.search(r"ficha\s+JSONB\s+NOT\s+NULL", limpio, re.IGNORECASE)
    assert re.search(r"cobertura_cols\s+NUMERIC\(5,\s*2\)", limpio, re.IGNORECASE)


def test_f006_r22_ddl_publicado_en_es_timestamp_sin_zona() -> None:
    """Como el resto de `_meta`: UTC sin zona, escrito con `utcnow()`.

    Mezclar aquí un `TIMESTAMPTZ` haría que la fecha del diccionario y la de
    `v_frescura` no fueran comparables, que es justo lo que la vista hace.
    """
    limpio = _sin_comentarios(_ddl())

    assert re.search(r"publicado_en\s+TIMESTAMP\s+NOT\s+NULL", limpio, re.IGNORECASE)
    assert "TIMESTAMPTZ" not in limpio.upper()


def test_f006_r15_ddl_la_vista_expone_significado_y_frescura_de_una_vez() -> None:
    """Es lo que resuelve P15: una sola consulta, semántica y fecha de build."""
    vista = _cuerpo_de_la_vista()

    for columna in (
        "esquema", "objeto", "descripcion", "grano", "clave_negocio", "refresco",
        "avisos", "n_columnas", "ficha", "paso_etl",
        "ultimo_ok_finished_at", "horas_desde_ultimo_ok", "ultimo_intento_status",
        "diccionario_version", "diccionario_publicado_en",
    ):
        assert columna in vista, f"la vista no expone `{columna}`"


def test_f006_r23_ddl_advierte_de_lo_que_cuesta_cambiar_la_vista() -> None:
    """R23: quitar o reordenar columnas exige `DROP VIEW`, y eso se lleva los
    `GRANT`. Quien lo haga tiene que ejecutar `apply-grants` acto seguido, y
    tiene que enterarse leyendo el propio fichero."""
    cabecera = "\n".join(_ddl().splitlines()[:40])

    assert "DROP VIEW" in cabecera
    assert "apply-grants" in cabecera
    assert "CREATE OR REPLACE VIEW" in cabecera
