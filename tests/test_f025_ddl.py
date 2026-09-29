# tests/test_f025_ddl.py
"""
F-025 · El DDL de `_meta.obra_build` y `_meta.v_frescura_obra` (T9, R14, R15).

Se lee el fichero como texto: es una puerta **offline**, del mismo tipo que la
de F-024 sobre este mismo `00_meta.sql`. Contrastarlo contra el catálogo real es
`python main.py check-diccionario`, que necesita conexión y lo lanza el humano.

Lo que se protege:

* **Ningún `DROP`.** Este fichero lo ejecuta el bootstrap en la primera conexión
  de *cada* proceso. Un `DROP TABLE` aquí borraría de qué noche viene cada obra
  cada vez que alguien lanza `python main.py status`, y esa tabla no se
  reconstruye a posteriori: es la única memoria de la frescura por obra.
* **`construido_at` no se mueve al congelar.** Es la mitad del contrato de R14;
  la otra mitad la vigila `tests/test_f025_sql.py` sobre el `UPDATE`.
* **La comparación de firmas tolera nulos.** Sin eso, la vista diría «no
  divergente» para todas las obras nuevas... o peor, `NULL`, que en un `WHERE`
  se comporta como falso y esconde la denuncia.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RUTA = Path("etl_sigrid/infrastructure/postgres/sql/ddl/00_meta.sql")


def ddl() -> str:
    return RUTA.read_text(encoding="utf-8")


def bloque_f025() -> str:
    """Solo lo que añade esta feature, para no medir el DDL de F-024."""
    texto = ddl()
    return texto[texto.index("F-025 · La ventana de negocio") :]


def sin_comentarios(texto: str) -> str:
    """El SQL sin sus líneas de comentario.

    Hace falta porque los comentarios de este fichero **hablan de** los `DROP`
    que no hay, y un barrido ingenuo sobre el texto entero se dispararía con la
    frase que precisamente explica por qué no están.
    """
    utiles = [
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    ]
    return chr(10).join(utiles)


# ---------------------------------------------------------------------------
# Los dos objetos existen y son idempotentes
# ---------------------------------------------------------------------------


def test_f025_r14_el_ddl_crea_la_tabla_obra_build() -> None:
    assert re.search(
        r"CREATE TABLE IF NOT EXISTS\s+_meta\.obra_build", ddl()
    ), "sin la tabla no hay registro de qué noche viene cada obra"


def test_f025_r14_el_ddl_crea_la_vista_de_frescura_por_obra() -> None:
    assert re.search(r"CREATE OR REPLACE VIEW\s+_meta\.v_frescura_obra", ddl())


def test_f025_r15_el_fichero_no_contiene_NINGUN_drop() -> None:  # noqa: N802
    """**El test más importante de este fichero.** Lo ejecuta el bootstrap en la
    primera conexión de CADA proceso: un `DROP` aquí borraría la memoria de la
    frescura por obra cada vez que alguien lanza `python main.py status`."""
    assert not re.search(r"\bDROP\b", sin_comentarios(ddl()), re.IGNORECASE)


def test_f025_r15_todo_lo_nuevo_es_idempotente() -> None:
    """`IF NOT EXISTS` en la tabla y en los tres índices, `OR REPLACE` en la
    vista, `ADD COLUMN IF NOT EXISTS` en las migraciones."""
    nuevo = bloque_f025()

    creaciones = re.findall(r"CREATE (?:TABLE|INDEX|OR REPLACE VIEW)[^\n]*", nuevo)
    assert creaciones, "el bloque de F-025 no crea nada"

    for creacion in creaciones:
        assert "IF NOT EXISTS" in creacion or "OR REPLACE" in creacion, creacion

    for alter in re.findall(r"ALTER TABLE[^\n]*", nuevo):
        assert "IF NOT EXISTS" in alter, alter


# ---------------------------------------------------------------------------
# Las columnas que sostienen el contrato
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "columna",
    [
        "obra_id",
        "codigo_obra",
        "firma_origen",
        "firma_actual",
        "firma_actual_at",
        "sello_sql",
        "batch_id",
        "construido_at",
        "filas",
        "congelada",
        "motivo",
        "detalle",
    ],
)
def test_f025_r14_la_tabla_declara_sus_columnas(columna: str) -> None:
    assert re.search(rf"^\s+{columna}\s+\w", bloque_f025(), re.MULTILINE)


def test_f025_r14_una_fila_por_obra_garantizada_por_el_motor() -> None:
    """`obra_id` es PRIMARY KEY, y de ahí que los upserts puedan llevar
    `ON CONFLICT (obra_id)`. Sin la clave, la segunda noche duplicaría filas y
    «la última construcción de esta obra» dejaría de estar definida."""
    assert re.search(r"obra_id\s+BIGINT\s+PRIMARY KEY", bloque_f025())


def test_f025_r14_las_marcas_de_tiempo_van_SIN_zona() -> None:  # noqa: N802
    """Todo `_meta` se escribe con `datetime.utcnow()` y se guarda como
    `TIMESTAMP`. Un `TIMESTAMPTZ` suelto aquí desalinearía esta tabla del resto
    del esquema y de la aritmética de la vista."""
    for columna in ("firma_actual_at", "construido_at"):
        assert re.search(rf"{columna}\s+TIMESTAMP\s", bloque_f025())
    assert "TIMESTAMPTZ" not in bloque_f025()


def test_f025_r14_las_DOS_firmas_son_columnas_distintas() -> None:  # noqa: N802
    """Con una sola, la ingesta pisaría cada noche la firma de referencia y
    comparar «de qué es el dato» contra «qué hay en el origen» no diría nada."""
    nuevo = bloque_f025()

    assert re.search(r"^\s+firma_origen\s+TEXT", nuevo, re.MULTILINE)
    assert re.search(r"^\s+firma_actual\s+TEXT", nuevo, re.MULTILINE)


# ---------------------------------------------------------------------------
# La vista: la respuesta consultable a «¿de cuándo es este dato?»
# ---------------------------------------------------------------------------


def test_f025_r14_la_vista_publica_la_antiguedad_de_cada_obra() -> None:
    vista = bloque_f025()[bloque_f025().index("CREATE OR REPLACE VIEW") :]

    for columna in (
        "construido_at",
        "horas_desde_construccion",
        "congelada",
        "motivo",
        "firma_divergente",
    ):
        assert columna in vista


def test_f025_r14_la_antiguedad_se_mide_en_UTC() -> None:  # noqa: N802
    """Los `TIMESTAMP` se escriben con `utcnow()` y sin zona: restarles un
    `now()` local daría el desfase horario de España como antigüedad, y en
    verano son DOS HORAS. Es la misma línea que lleva `_meta.v_frescura`."""
    assert "now() AT TIME ZONE 'UTC'" in bloque_f025()


def test_f025_r16_la_divergencia_de_firma_TOLERA_nulos() -> None:  # noqa: N802
    """**La trampa de tres valores de SQL.** `a <> b` con cualquiera a `NULL`
    devuelve `NULL`, no `FALSE`, y en un `WHERE` eso descarta la fila: la
    denuncia se perdería en silencio. Los dos `IS NOT NULL` delante lo evitan.

    Y con una firma a nulo la respuesta correcta es FALSE: no se sabe, y «no se
    sabe» no es «cambió». Esa obra entra ya por R18."""
    vista = bloque_f025()

    assert "b.firma_origen IS NOT NULL" in vista
    assert "b.firma_actual IS NOT NULL" in vista
    assert "b.firma_origen <> b.firma_actual" in vista


def test_f025_r14_la_vista_muestra_TODAS_las_obras_registradas() -> None:  # noqa: N802
    """Sin `WHERE`: una obra congelada, una sin construir y una recién hecha
    tienen que salir las tres. Filtrar aquí escondería justo lo que se busca."""
    vista = bloque_f025()[bloque_f025().index("CREATE OR REPLACE VIEW") :]

    assert "FROM _meta.obra_build b;" in vista
    assert "WHERE" not in vista


# ---------------------------------------------------------------------------
# Que el DDL diga POR QUÉ, no solo QUÉ
# ---------------------------------------------------------------------------


def test_f025_r14_el_ddl_explica_por_que_hay_dos_firmas() -> None:
    """Quien lea esta tabla dentro de un año verá dos columnas casi iguales. Si
    el fichero no explica la diferencia, alguien fusionará las dos y romperá la
    denuncia sin darse cuenta."""
    nuevo = bloque_f025().lower()

    assert "no es redundancia" in nuevo or "columnas distintas" in nuevo
    assert "pisaria" in nuevo or "pisaría" in nuevo


def test_f025_r14_el_ddl_advierte_de_que_construido_at_no_se_mueve() -> None:
    """Es la mitad del contrato de R14 que un DDL puede documentar; la otra
    mitad la vigila `tests/test_f025_sql.py` sobre el `UPDATE`."""
    nuevo = bloque_f025().lower()

    assert "conserva la fecha de su ultima construccion" in " ".join(nuevo.split())
