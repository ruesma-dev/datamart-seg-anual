# tests/test_f164_sql.py
"""
F-164 · El SQL de `postventa.documento_adjuntos` sobre su TEXTO (R9, R11, R4).

Como `tests/test_f156_ingesta_sql.py`: el SQL construye en un Postgres compartido
con producción, así que aquí se lee, no se ejecuta (la ejecución es la sandbox,
`tests/test_f164_sandbox.py`). Lo que defiende:

- R9: la lista abierta y los dos patrones del `CASE` son EXACTAMENTE los del
  dominio (`etl_sigrid/domain/postventa.py`), uno a uno.
- R4: el `CASE` es seguro ante `NULL`: solo abre con `IS TRUE` / `IS FALSE`.
- R11: la columna nueva `familia_documento` va justo detrás de `familia`, con la
  expresión de F-156; el resto de columnas, su orden, la clave y los índices no
  cambian.
"""

from __future__ import annotations

import re
from pathlib import Path

from etl_sigrid.domain import postventa as pv

RAIZ = Path(__file__).resolve().parents[1]
RUTA_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "postventa" / "06_adjuntos.sql"

#: Las columnas publicadas ANTES de F-164 (F-156), en su orden.
COLUMNAS_F156: tuple[str, ...] = (
    "adjunto_id", "familia", "documento_id", "tipo_documento_codigo", "codigo_documento",
    "incidencia_id", "unidad_id", "tarea_id", "grafico_id", "cod_repositorio",
    "empresa_repositorio", "nombre_fichero", "extension", "clase_fichero", "clase_grafico_id",
    "clase_grafico_codigo", "clase_grafico", "descripcion", "fecha_alta", "subido_por", "posicion",
)

#: Lo que lee `abrir_adjunto` de `mcp-bbdd` (F-145/F-034): ni nombre ni tipo cambian.
CONTRATO_ABRIR_ADJUNTO: tuple[str, ...] = (
    "adjunto_id", "familia", "documento_id", "cod_repositorio", "empresa_repositorio",
    "nombre_fichero", "extension", "clase_fichero",
)


def _texto() -> str:
    return RUTA_SQL.read_text(encoding="utf-8")


def _compacto() -> str:
    sin = "\n".join(re.sub(r"--.*$", "", linea) for linea in _texto().splitlines())
    return re.sub(r"\s+", " ", sin).strip()


def _create() -> str:
    sql = _compacto()
    cabecera = "CREATE TABLE postventa.documento_adjuntos AS"
    inicio = sql.index(cabecera)
    return sql[inicio: sql.index(";", inicio)]


def _select_final() -> str:
    create = _create()
    final = create[create.rindex("SELECT "):]
    return final[: final.index(" FROM ")]


def _alias_publicados() -> list[str]:
    return re.findall(r" AS (\w+)", _select_final())


def _case_familia() -> str:
    caso = re.search(
        r"CASE WHEN \(.*?\) IS TRUE AND \(.*?\) IS FALSE THEN b\.familia_documento "
        r"ELSE 'REPARACION' END::TEXT AS familia\b",
        _select_final(),
    )
    assert caso, "falta el CASE de `familia` seguro ante NULL (design §4)"
    return caso.group(0)


# ===========================================================================
# R9 · Los literales del SQL son los del dominio
# ===========================================================================


def test_f164_r9_la_lista_abierta_del_sql_es_la_del_dominio() -> None:
    caso = _case_familia()
    parejas = {
        (int(t), int(c))
        for t, c in re.findall(
            r"b\.tipo_documento_codigo = (\d+) AND b\.clase_grafico_id = (\d+)", caso)
    }
    assert parejas == set(pv.LISTA_ABIERTA)
    assert len(re.findall(r"b\.tipo_documento_codigo = ", caso)) == len(pv.LISTA_ABIERTA)


def test_f164_r9_los_patrones_del_sql_son_los_del_dominio() -> None:
    caso = _case_familia()
    assert re.findall(r"~ '([^']*)'", caso) == [pv.PATRON_SENAL_FIRMA, pv.PATRON_SENAL_CODIGO]
    nombre = "COALESCE(b.nombre_fichero, '')"
    descripcion = "COALESCE(b.descripcion, '')"
    # S2 sobre nombre + espacio + descripción; S3 SOLO sobre el nombre (design §3).
    assert f"upper({nombre} || ' ' || {descripcion}) ~ '{pv.PATRON_SENAL_FIRMA}'" in caso
    assert f"upper({nombre}) ~ '{pv.PATRON_SENAL_CODIGO}'" in caso


#: El orden de las parejas en el SQL (`LISTA_ABIERTA` es un `frozenset`).
ORDEN_SQL: tuple[tuple[int, int], ...] = (
    (pv.TIPO_INCIDENCIA, pv.GRATIPIDE_FOTOS_INCIDENCIA),
    (pv.TIPO_UNIDAD, pv.GRATIPIDE_FICHA_INMUEBLE),
    (pv.TIPO_TAREA, pv.GRATIPIDE_INFORMES),
)


def test_f164_r9_el_case_entero_es_el_del_dominio() -> None:
    """La ESTRUCTURA del `CASE`, no solo sus literales (review H1).

    La sandbox, que lo ejecuta, hace `skip` sin DSN en la puerta y `harness.mutacion`
    no muta SQL: sin este test, abrir los sin clase (`OR TRUE`), apagar S3
    (`AND FALSE`) o cambiar el `OR` de las señales por `AND` dejaba la puerta en verde.
    """
    assert set(ORDEN_SQL) == set(pv.LISTA_ABIERTA)
    lista = " OR ".join(
        f"(b.tipo_documento_codigo = {t} AND b.clase_grafico_id = {c})" for t, c in ORDEN_SQL)
    esperado = (
        f"CASE WHEN ({lista}) IS TRUE AND ("
        f"upper(COALESCE(b.nombre_fichero, '') || ' ' || COALESCE(b.descripcion, '')) "
        f"~ '{pv.PATRON_SENAL_FIRMA}' "
        f"OR upper(COALESCE(b.nombre_fichero, '')) ~ '{pv.PATRON_SENAL_CODIGO}') IS FALSE "
        "THEN b.familia_documento ELSE 'REPARACION' END::TEXT AS familia,"
    )
    assert esperado in _select_final()


def test_f164_r9_ningun_otro_patron_ni_clase_en_el_sql() -> None:
    """El CASE no mira la extensión ni `clase_fichero` (R6) ni otra columna."""
    caso = _case_familia()
    columnas = set(re.findall(r"\bb\.(\w+)", caso))
    assert columnas == {"tipo_documento_codigo", "clase_grafico_id", "nombre_fichero",
                        "descripcion", "familia_documento"}


# ===========================================================================
# R4 · Ningún NULL del SQL abre un fichero
# ===========================================================================


def test_f164_r4_el_case_solo_abre_con_is_true_y_is_false() -> None:
    caso = _case_familia()
    assert caso.count(" IS TRUE") == 1 and caso.count(" IS FALSE") == 1
    assert "ELSE 'REPARACION'" in caso
    # El texto nulo cuenta como vacío: la señal del otro campo sigue valiendo.
    assert caso.count("COALESCE(b.nombre_fichero, '')") == 2
    assert caso.count("COALESCE(b.descripcion, '')") == 1


# ===========================================================================
# R11 · La columna nueva y el contrato con `abrir_adjunto`
# ===========================================================================


def test_f164_r11_familia_documento_es_la_expresion_de_f156() -> None:
    esperado = (
        f"CASE WHEN c.tip = {pv.TIPO_UNIDAD} THEN 'UNIDAD' "
        f"WHEN c.tip = {pv.TIPO_TAREA} THEN 'TAREA' "
        f"WHEN g.gratipide = {pv.GRATIPIDE_REPARACION} THEN 'REPARACION' "
        "ELSE 'INCIDENCIA' END::TEXT AS familia_documento"
    )
    assert esperado in _create()
    assert "b.familia_documento AS familia_documento" in _select_final()


def test_f164_r11_columnas_y_orden() -> None:
    publicadas = _alias_publicados()
    assert publicadas.index("familia_documento") == publicadas.index("familia") + 1
    assert tuple(c for c in publicadas if c != "familia_documento") == COLUMNAS_F156
    assert len(publicadas) == len(set(publicadas)) == len(COLUMNAS_F156) + 1
    for columna in CONTRATO_ABRIR_ADJUNTO:
        assert columna in publicadas, columna


def test_f164_r11_clave_e_indices_sin_cambios() -> None:
    sql = _compacto()
    assert "ALTER TABLE postventa.documento_adjuntos ADD PRIMARY KEY (adjunto_id);" in sql
    indices = re.findall(r"CREATE INDEX (\w+) ON postventa\.documento_adjuntos \((\w+)\)", sql)
    assert indices == [("ix_pv_adjuntos_documento", "documento_id"),
                       ("ix_pv_adjuntos_incidencia", "incidencia_id"),
                       ("ix_pv_adjuntos_unidad", "unidad_id")]
    # Una fila por enlace, como antes: el mismo FROM y los mismos JOIN.
    create = _create()
    assert "FROM raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (47, 707, 708) " \
           "JOIN raw.gra g ON g.ide = r.gra" in create
    assert create.rstrip().endswith("FROM base b")


def test_f164_r11_el_comentario_de_la_tabla_dice_el_criterio() -> None:
    comentario = re.search(r"COMMENT ON TABLE postventa\.documento_adjuntos IS '(.*?)';",
                           _compacto())
    assert comentario
    texto = comentario.group(1)
    for clave in ("F-164", "PV001", "PV006", "PV004", "FIRMA", "codigo", "familia_documento"):
        assert clave in texto, clave


def test_f164_r11_la_cabecera_explica_la_regla() -> None:
    cabecera = _texto().split("DO $$")[0]
    for clave in ("F-164", "LISTA ABIERTA", "familia_documento", "PV001", "PV006", "PV004",
                  "FIRMA", "sin clase"):
        assert clave in cabecera, clave
