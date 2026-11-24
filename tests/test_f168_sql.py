# tests/test_f168_sql.py
"""
F-168 · El SQL del texto largo, leído sin base de datos.

- `stg/11_texto_largo.sql`: las funciones de limpieza e identidad, con los
  literales del dominio (R5-R8).
- `stg/12_partida_texto.sql`: el texto de la partida, sin filtro de ámbito
  (R9, R10, R23).
- `compras/16_textos_linea.sql`: las cinco fuentes del flujo, el catálogo
  deduplicado y la vista (R12-R17, R23).
- `compras/07_texto.sql`: el memo de comparativos y ofertas (R18).
- Los sub-pasos nuevos en `build_stg` y `build_compras`.

Lo que hace el SQL de verdad lo prueba `tests/test_f168_sandbox.py` contra un
Postgres de usar y tirar.
"""

from __future__ import annotations

import re
from pathlib import Path

from etl_sigrid.domain import texto_largo as tl

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
TEXTO_LARGO = DIR_SQL / "stg" / "11_texto_largo.sql"
PARTIDA_TEXTO = DIR_SQL / "stg" / "12_partida_texto.sql"
STEP_STG = RAIZ / "etl_sigrid" / "application" / "steps" / "build_stg_step.py"


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _compacto(ruta: Path) -> str:
    return " ".join(_sin_comentarios(_crudo(ruta)).split())


# ---------------------------------------------------------------------------
# R5 · R6 · R7 · R8 · las funciones de stg/11
# ---------------------------------------------------------------------------


def test_f168_r7_cabecera_con_la_ruta() -> None:
    for ruta in (TEXTO_LARGO, PARTIDA_TEXTO):
        primera = _crudo(ruta).splitlines()[0]
        assert primera == f"-- {ruta.relative_to(RAIZ).as_posix()}"


def test_f168_r7_el_sql_usa_los_literales_del_dominio() -> None:
    sql = _sin_comentarios(_crudo(TEXTO_LARGO))
    assert f"'{tl.PATRON_CONTROL}'" in sql, "el patrón de control es el del dominio"
    # Todo número de 4 o más cifras del fichero es el tope del dominio.
    numeros = set(re.findall(r"\b\d{4,}\b", sql))
    assert numeros == {str(tl.TOPE_CARACTERES)}, numeros
    extremos = "E'" + tl.EXTREMOS.replace("\t", "\\t").replace("\n", "\\n") + "'"
    assert sql.count(extremos) == 2, "btrim de los extremos antes y después del corte"


def test_f168_r5_el_orden_de_la_limpieza() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    esperado = (
        "SELECT NULLIF( btrim( left( btrim( regexp_replace( "
        "replace(replace(t, E'\\r\\n', E'\\n'), E'\\r', E'\\n'), "
        f"'{tl.PATRON_CONTROL}', '', 'g' ), E' \\t\\n' ), {tl.TOPE_CARACTERES} ), "
        "E' \\t\\n' ), '' )"
    )
    assert esperado in cuerpo


def test_f168_r6_texto_id_es_md5_uuid() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert "CREATE OR REPLACE FUNCTION stg.fn_texto_id(t TEXT) RETURNS UUID" in cuerpo
    assert "SELECT md5(t)::uuid" in cuerpo


def test_f168_r8_recortado_es_mayor_o_igual_que_el_tope() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert "CREATE OR REPLACE FUNCTION stg.fn_texto_recortado(t TEXT) RETURNS BOOLEAN" in cuerpo
    assert f"SELECT COALESCE(char_length(t) >= {tl.TOPE_CARACTERES}, FALSE)" in cuerpo


def test_f168_r5_funciones_inmutables_y_solo_funciones() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert cuerpo.count("IMMUTABLE PARALLEL SAFE") == 3
    for prohibido in ("CREATE TABLE", "DROP TABLE", "INSERT", "DELETE", "TRUNCATE"):
        assert prohibido not in cuerpo, f"stg/11 entra en el sello: solo funciones ({prohibido})"


# ---------------------------------------------------------------------------
# R9 · R10 · R23 · stg.partida_texto
# ---------------------------------------------------------------------------


def test_f168_r9_partida_texto_columnas_y_clave() -> None:
    cuerpo = _compacto(PARTIDA_TEXTO)
    for columna in ("partida_id", "obra_id", "codigo_partida", "descripcion_corta", "texto",
                    "texto_id", "bytes", "recortado"):
        assert re.search(rf"AS {columna}\b", cuerpo), columna
    assert "ALTER TABLE stg.partida_texto ADD PRIMARY KEY (partida_id);" in cuerpo
    assert "FROM raw.obrparpar o" in cuerpo
    assert "LEFT JOIN stg.partidas p ON p.partida_id = o.ide" in cuerpo
    assert "stg.fn_texto_largo(o.tex)" in cuerpo
    assert "stg.fn_texto_recortado(o.tex) AS recortado" in cuerpo
    assert "WHERE l.texto IS NOT NULL" in cuerpo


def test_f168_r10_sin_filtro_de_ambito_fase_ni_tipo() -> None:
    compacto = _compacto(PARTIDA_TEXTO)
    inicio = compacto.index("CREATE TABLE stg.partida_texto AS")
    cuerpo = compacto[inicio:compacto.index(";", inicio)]
    for vetado in ("amb", "fas", "tip", "tipdes", "obrparpre", "ambito_id", "fase_num"):
        assert not re.search(rf"\b{vetado}\b", cuerpo), (
            f"stg.partida_texto no filtra por {vetado} (R10)"
        )
    assert cuerpo.count("WHERE") == 1, "un solo filtro: el de texto no nulo"


def test_f168_r23_drop_y_create_en_un_solo_fichero_sin_commit() -> None:
    cuerpo = _compacto(PARTIDA_TEXTO)
    assert cuerpo.index("DROP TABLE IF EXISTS stg.partida_texto") < cuerpo.index(
        "CREATE TABLE stg.partida_texto AS"
    )
    for vetado in ("COMMIT", "BEGIN;", "ROLLBACK"):
        assert vetado not in cuerpo, "una sola transacción: la de execute_sql_file (R23)"


# ---------------------------------------------------------------------------
# Los sub-pasos de build_stg
# ---------------------------------------------------------------------------


def _sub_pasos_stg() -> list[tuple[str, str]]:
    return re.findall(r'_SubStep\(\s*"(\w+)",\s*"([\w.]*)"', _crudo(STEP_STG))


def test_f168_los_sub_pasos_de_stg_van_detras_de_master_versiones() -> None:
    pasos = _sub_pasos_stg()
    assert pasos[-3:] == [
        ("build_master_versiones", "10_master_versiones.sql"),
        ("texto_largo", "11_texto_largo.sql"),
        ("build_partida_texto", "12_partida_texto.sql"),
    ]
    bloque = re.search(r'_SubStep\(\s*"build_partida_texto".*?\)', _crudo(STEP_STG), re.S)
    assert bloque and '"stg"' in bloque.group(0) and '"partida_texto"' in bloque.group(0)
    for marca in ("acotado", "por_tramos", "es_plan_ventana"):
        assert marca not in bloque.group(0), f"{marca}: se ejecuta entero"


def test_f168_fuera_del_sello_de_stg_y_de_la_ventana() -> None:
    from etl_sigrid.application.steps.build_stg_step import FICHEROS_DEL_SELLO
    from etl_sigrid.infrastructure.postgres.postgres_client import TABLAS_ACOTADAS

    assert "11_texto_largo.sql" not in FICHEROS_DEL_SELLO
    assert "12_partida_texto.sql" not in FICHEROS_DEL_SELLO
    assert "partida_texto" not in TABLAS_ACOTADAS


def test_f168_el_preflight_exige_tex_en_obrparpar() -> None:
    texto = _crudo(STEP_STG)
    linea = re.search(r'\("raw", "obrparpar"\):\s*\[[^\]]*\]', texto)
    assert linea and '"tex"' in linea.group(0)


# ---------------------------------------------------------------------------
# R12 · R13 · R14 · R15 · R16 · R17 · R23 · compras/16_textos_linea.sql
# ---------------------------------------------------------------------------

TEXTOS_LINEA = DIR_SQL / "compras" / "16_textos_linea.sql"

#: Las cinco fuentes: tipo de línea, tabla, columna del documento y de dónde
#: sale la obra (R13).
FUENTES = {
    "NECESIDAD": ("raw.dncpro", "dncide"),
    "OFERTA": ("raw.dcopro", "docide"),
    "CONTRATO": ("raw.ctrpro", "docide"),
    "ALBARAN": ("raw.dcapro", "docide"),
    "FACTURA": ("raw.dcfpro", "docide"),
}


def _rama(tipo: str) -> str:
    """El SELECT de la rama `tipo` dentro del UNION ALL de las fuentes."""
    compacto = _compacto(TEXTOS_LINEA)
    inicio = compacto.index(f"'{tipo}'::TEXT AS tipo_linea")
    fin = compacto.find("UNION ALL", inicio)
    return compacto[inicio: fin if fin > 0 else compacto.index(")", compacto.index("FROM", inicio))]


def test_f168_r12_cabecera_y_tres_objetos() -> None:
    assert _crudo(TEXTOS_LINEA).splitlines()[0] == (
        "-- etl_sigrid/infrastructure/postgres/sql/compras/16_textos_linea.sql"
    )
    cuerpo = _compacto(TEXTOS_LINEA)
    for objeto in ("CREATE TABLE compras.linea_texto AS", "CREATE TABLE compras.textos AS",
                   "CREATE OR REPLACE VIEW compras.v_linea_texto AS"):
        assert objeto in cuerpo, objeto
    assert "ALTER TABLE compras.linea_texto ADD PRIMARY KEY (tipo_linea, linea_id);" in cuerpo
    assert "ALTER TABLE compras.textos ADD PRIMARY KEY (texto_id);" in cuerpo


def test_f168_r13_las_cinco_fuentes_y_sus_enlaces() -> None:
    for tipo, (tabla, documento) in FUENTES.items():
        rama = _rama(tipo)
        assert f"FROM {tabla} " in rama + " ", f"{tipo} lee {tabla}"
        assert f".{documento}::BIGINT AS documento_id" in rama, f"{tipo}: documento por {documento}"
        assert ".paride::BIGINT AS partida_id" in rama, f"{tipo}: partida por paride"
        if tipo == "NECESIDAD":
            assert "NULL::BIGINT AS linea_necesidad_id" in rama
            assert "d.obride::BIGINT AS obra_id" in rama and "LEFT JOIN raw.dnc d" in rama
        else:
            assert ".dncproide::BIGINT AS linea_necesidad_id" in rama
            assert ".obride::BIGINT AS obra_id" in rama


def test_f168_r13_cero_es_nulo() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    for columna in ("documento_id", "obra_id", "partida_id", "linea_necesidad_id"):
        assert f"NULLIF(f.{columna}, 0) AS {columna}" in cuerpo, columna


def test_f168_r13_no_se_compara_por_linoriide() -> None:
    assert "linoriide" not in _sin_comentarios(_crudo(TEXTOS_LINEA)), (
        "linoriide no dice a qué tabla apunta (M3): se compara por paride y dncproide"
    )


def test_f168_r12_solo_texto_limpio_no_nulo_y_tope_del_dominio() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    assert "stg.fn_texto_largo(c.tex)" in cuerpo
    assert "stg.fn_texto_id(x.texto) AS texto_id" in cuerpo
    assert "stg.fn_texto_recortado(c.tex) AS recortado" in cuerpo
    assert "WHERE x.texto IS NOT NULL" in cuerpo
    assert not re.search(r"\b\d{4,}\b", cuerpo), "el tope vive en el dominio y en stg/11"


def test_f168_r14_igualdades_con_case_y_nulo() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    assert ("CASE WHEN pt.texto_id IS NULL THEN NULL ELSE f.texto_id = pt.texto_id END "
            "AS igual_a_partida") in cuerpo
    assert ("CASE WHEN f.tipo_linea = 'NECESIDAD' OR nec.texto_id IS NULL THEN NULL "
            "ELSE f.texto_id = nec.texto_id END AS igual_a_necesidad") in cuerpo
    assert "LEFT JOIN stg.partida_texto pt ON pt.partida_id = f.partida_id" in cuerpo
    assert ("LEFT JOIN _f168_fuentes nec ON nec.tipo_linea = 'NECESIDAD' "
            "AND nec.linea_id = f.linea_necesidad_id") in cuerpo


def test_f168_r15_textos_deduplicado_de_las_mismas_fuentes() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    bloque = cuerpo[cuerpo.index("CREATE TABLE compras.textos AS"):]
    bloque = bloque[: bloque.index(";")]
    assert "SELECT DISTINCT ON (f.texto_id)" in bloque
    assert "FROM _f168_fuentes f" in bloque
    assert "ORDER BY f.texto_id, f.recortado DESC" in bloque, "recortado si alguna línea lo está"


def test_f168_r15_linea_texto_no_guarda_el_texto() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    bloque = cuerpo[cuerpo.index("CREATE TABLE compras.linea_texto AS"):]
    proyeccion = bloque[: bloque.index(" FROM ")]
    assert "AS texto " not in proyeccion + " " and "f.texto AS" not in proyeccion


def test_f168_r16_la_vista_une_por_texto_id() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    bloque = cuerpo[cuerpo.index("CREATE OR REPLACE VIEW compras.v_linea_texto AS"):]
    bloque = bloque[: bloque.index(";")]
    assert "FROM compras.linea_texto l JOIN compras.textos t ON t.texto_id = l.texto_id" in bloque
    assert "t.texto AS texto" in bloque


def test_f168_r23_un_solo_fichero_sin_commit() -> None:
    cuerpo = _compacto(TEXTOS_LINEA)
    # `ON COMMIT DROP` de la temporal no es un COMMIT: lo es la sentencia suelta.
    for vetado in (r"(?<!ON )\bCOMMIT\b", r"\bBEGIN\s*;", r"\bROLLBACK\b"):
        assert not re.search(vetado, cuerpo), vetado
    assert "CREATE TEMP TABLE _f168_fuentes ON COMMIT DROP AS" in cuerpo


def test_f168_el_sub_paso_de_compras_es_el_ultimo_y_cuenta_linea_texto() -> None:
    from etl_sigrid.application.steps.build_compras_step import SUB_PASOS

    ultimo = SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file) == ("textos_linea", "16_textos_linea.sql")
    assert (ultimo.target_schema, ultimo.target_table) == ("compras", "linea_texto")


# ---------------------------------------------------------------------------
# R18 · el memo de comparativos (46) y ofertas (12) en compras/07
# ---------------------------------------------------------------------------

TEXTO_DOC = DIR_SQL / "compras" / "07_texto.sql"


def test_f168_r18_el_memo_entra_tambien_de_ofertas_y_comparativos() -> None:
    cuerpo = _compacto(TEXTO_DOC)
    assert "WHERE c.tip IN (12, 15, 44, 46)" in cuerpo
    assert "c.tip IN (15, 44)" not in cuerpo


def test_f168_r18_misma_regla_de_partir_para_todos() -> None:
    """Los comentarios salen de `documento_texto` sin volver a filtrar por tipo:
    la regla de partir es la misma para ofertas y comparativos."""
    cuerpo = _compacto(TEXTO_DOC)
    comentarios = cuerpo.split("CREATE TABLE compras.documento_comentarios AS", 1)[1]
    assert "FROM compras.documento_texto t" in comentarios
    assert "c.tip" not in comentarios and ".tipo_documento" not in comentarios


def test_f168_r18_el_tipo_de_oferta_y_comparativo_tiene_nombre() -> None:
    """`fn_tipo_documento` no conoce el 12 ni el 46 (darían OTRO): se nombran
    en `07`, sin tocar la función que comparten las demás tablas."""
    cuerpo = _compacto(TEXTO_DOC)
    assert ("CASE c.tip WHEN 12 THEN 'OFERTA' WHEN 46 THEN 'COMPARATIVO' "
            "ELSE compras.fn_tipo_documento(c.tip, compras.fn_serie(c.cod)) END") in cuerpo


def test_f168_r18_la_ficha_declara_los_cuatro_tipos() -> None:
    import yaml

    fichas = yaml.safe_load((RAIZ / "config" / "diccionario" / "compras.yaml")
                            .read_text(encoding="utf-8"))["objetos"]
    columnas = fichas["documento_texto"]["columnas"]
    assert columnas["tipo_documento_codigo"]["valores"] == [12, 15, 44, 46]
    assert {"OFERTA", "COMPARATIVO"} <= set(columnas["tipo_documento"]["valores"])


# ---------------------------------------------------------------------------
# R17 · del comparativo al texto, sin tablas intermedias
# ---------------------------------------------------------------------------

COMPARATIVOS_DETALLE = DIR_SQL / "compras" / "09_comparativos_detalle.sql"


def test_f168_r17_las_claves_del_comparativo_son_las_de_linea_texto() -> None:
    """`comparativo_lineas.linea_necesidad_id` es `dncpro.ide` y
    `comparativo_oferta_lineas.linea_oferta_id` es `dcopro.ide`: las mismas que
    `linea_texto.linea_id` en NECESIDAD y en OFERTA. Basta (`tipo_linea`, `linea_id`)."""
    detalle = _compacto(COMPARATIVOS_DETALLE)
    assert "NULLIF(l.dncproide, 0) AS linea_necesidad_id" in detalle
    assert "lp.ide AS linea_oferta_id" in detalle and "FROM raw.dcopro lp" in detalle
    necesidad, oferta = _rama("NECESIDAD"), _rama("OFERTA")
    assert "n.ide::BIGINT AS linea_id" in necesidad and "FROM raw.dncpro n" in necesidad
    assert "o.ide::BIGINT AS linea_id" in oferta and "FROM raw.dcopro o" in oferta
