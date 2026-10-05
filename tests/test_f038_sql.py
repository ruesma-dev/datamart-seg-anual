# tests/test_f038_sql.py
"""
F-038 · El comparativo de ofertas, comprobado sobre el TEXTO del SQL.

`sql/compras/00_setup.sql` y `sql/compras/08_comparativos.sql` construyen
tablas en un Postgres **compartido con producción**, así que aquí no se
ejecutan: se leen. Mismo criterio que `tests/test_f084_sql.py` y
`tests/test_f080_sql.py`.

LO QUE ESTE FICHERO DEFIENDE:

- R11: los literales de la regla de ficticias —CIF falsos, patrones de familia
  en su orden, exclusiones, normalización— y los umbrales del atípico son
  **los mismos** que `etl_sigrid/domain/comparativos.py`. Si alguien cambia
  uno de los dos lados, este test se pone rojo.
- Los vetos medidos: el proveedor NO sale de `comprv.prvide` (18 %), el
  importe NO es `dco.totdoc` (lleva IVA), el contrato NO sale de `ctr.comide`
  (56 %), y ninguna columna se llama `importe` a secas.
- La guarda R21 (dos contratos en un comparativo = el build falla) y las
  columnas de design §4, en su orden.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain.comparativos import (
    CIF_FALSOS,
    EXCLUSIONES,
    FACTOR_ATIPICO,
    MINIMO_ATIPICO,
    NO_ALFANUMERICO,
    ORIGENES_ANTERIORES_ABC,
    ORIGENES_ESTUDIOS,
    PATRON_DTO,
    PATRONES_FAMILIA,
    TILDES_DESTINO,
    TILDES_ORIGEN,
    TOLERANCIA_ABS,
    TOLERANCIA_REL,
    base_regla,
)
from tests._texto import normalizado

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
)
RUTA_SETUP = DIRECTORIO_SQL / "00_setup.sql"
RUTA_COMPARATIVOS = DIRECTORIO_SQL / "08_comparativos.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """Quita las líneas de comentario y la cola `-- ...` de las de código."""
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return "\n".join(lineas)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _funcion(nombre: str) -> str:
    """El cuerpo compactado de una función de `00_setup.sql`."""
    texto = _compacto(_texto(RUTA_SETUP))
    marca = f"CREATE OR REPLACE FUNCTION {nombre}("
    assert texto.count(marca) == 1, (
        f"`{nombre}` tiene que estar definida exactamente UNA vez en "
        "`compras/00_setup.sql`"
    )
    inicio = texto.index(marca)
    return texto[inicio : texto.index("$$;", texto.index("AS $$", inicio))]


# ===========================================================================
# T2 · setup: las dos funciones y sus literales (R11)
# ===========================================================================


def test_f038_r11_setup_normalizar_nombre_usa_los_literales_del_dominio() -> None:
    cuerpo = _funcion("compras.fn_normalizar_nombre")
    esperado = (
        "btrim(regexp_replace(translate(upper(COALESCE(p_texto, '')), "
        f"'{TILDES_ORIGEN}', '{TILDES_DESTINO}'), '{NO_ALFANUMERICO}', ' ', 'g'))"
    )
    assert esperado in cuerpo, (
        "`compras.fn_normalizar_nombre` no es la normalización del dominio: "
        f"se esperaba «{esperado}» y el cuerpo es «{cuerpo}»"
    )
    assert "IMMUTABLE" in cuerpo


def test_f038_r11_setup_familia_ficticia_es_immutable_y_normaliza_igual() -> None:
    cuerpo = _funcion("compras.fn_familia_ficticia")
    assert "IMMUTABLE" in cuerpo
    assert "compras.fn_normalizar_nombre(p_nombre) AS n" in cuerpo, (
        "la familia se decide sobre el nombre NORMALIZADO por la misma función"
    )
    assert "upper(btrim(COALESCE(p_cif, ''))) AS c" in cuerpo, (
        "el CIF se compara recortado y en mayúsculas, como en el dominio"
    )


def test_f038_r11_literales_patrones_de_familia_en_su_orden() -> None:
    cuerpo = _funcion("compras.fn_familia_ficticia")
    pares = re.findall(r"WHEN x\.n ~ '([^']*)' THEN '([A-Z_0-9]+)'", cuerpo)
    assert tuple(pares) == tuple((p, f) for f, p in PATRONES_FAMILIA), (
        "los patrones del SQL no son los del dominio o no van en su orden "
        f"(R9, R11): SQL {pares}"
    )


def test_f038_r11_literales_cif_falsos() -> None:
    cuerpo = _funcion("compras.fn_familia_ficticia")
    respaldo = re.findall(r"WHEN x\.c = '([A-Z0-9]+)' THEN '([A-Z_]+)'", cuerpo)
    assert dict(respaldo) == CIF_FALSOS and len(respaldo) == len(CIF_FALSOS)
    lista = re.search(r"x\.c NOT IN \(([^)]*)\)", cuerpo)
    assert lista is not None, "falta la condición de CIF real (no vacío y no falso)"
    assert sorted(re.findall(r"'([^']*)'", lista.group(1))) == sorted(CIF_FALSOS)
    assert re.search(r"WHEN x\.c <> '' AND x\.c NOT IN", cuerpo), (
        "con CIF real la oferta es REAL: la primera rama tiene que exigir CIF "
        "no vacío y no falso (R8)"
    )


def test_f038_r11_literales_exclusiones() -> None:
    cuerpo = _funcion("compras.fn_familia_ficticia")
    excluidas = re.findall(r"WHEN strpos\(x\.n, '([^']*)'\) > 0 THEN NULL", cuerpo)
    assert tuple(excluidas) == EXCLUSIONES, (
        f"las exclusiones del SQL ({excluidas}) no son las del dominio (R10)"
    )


def test_f038_r9_setup_el_orden_de_las_ramas_es_el_del_dominio() -> None:
    """CIF real → excluido → familias → respaldo por CIF falso."""
    cuerpo = _funcion("compras.fn_familia_ficticia")
    cif_real = cuerpo.index("x.c NOT IN")
    exclusion = cuerpo.index("strpos(x.n,")
    primera_familia = cuerpo.index("WHEN x.n ~")
    respaldo = cuerpo.index("WHEN x.c = ")
    assert cif_real < exclusion < primera_familia < respaldo
    assert " ELSE " not in cuerpo, "sin familia ni CIF falso, NULL: la oferta es real"


def test_f038_setup_no_toca_lo_existente() -> None:
    """Las funciones de siempre siguen ahí, una vez cada una (design §2)."""
    texto = _sin_comentarios(_texto(RUTA_SETUP))
    for funcion in (
        "compras.fn_sigrid_date",
        "compras.fn_serie",
        "compras.fn_estado_documento",
        "compras.fn_tipo_documento",
    ):
        assert texto.count(f"CREATE OR REPLACE FUNCTION {funcion}(") == 1, funcion


# ===========================================================================
# T3 · 08_comparativos.sql, parte 1: guarda y comparativo_ofertas
# ===========================================================================

#: Las columnas de `compras.comparativo_ofertas`, EN SU ORDEN (design §4).
COLUMNAS_OFERTAS = (
    "oferta_id",
    "invitacion_id",
    "comparativo_id",
    "posicion",
    "codigo_oferta",
    "fecha_oferta",
    "proveedor_id",
    "proveedor_codigo",
    "proveedor_nombre",
    "proveedor_cif",
    "es_ficticia",
    "familia_ficticia",
    "estado_id",
    "estado_codigo",
    "estado",
    "es_ganadora",
    "importe_ofertado_documento",
    "importe_ofertado_lineas",
    "n_lineas",
)


def _ejecutable_08() -> str:
    return _compacto(_texto(RUTA_COMPARATIVOS))


def _bloque(tabla: str) -> str:
    texto = _ejecutable_08()
    inicio = texto.index(f"DROP TABLE IF EXISTS compras.{tabla} CASCADE")
    fin = texto.index(f"ALTER TABLE compras.{tabla} ADD PRIMARY KEY")
    return texto[inicio:fin]


def _proyeccion(tabla: str, primera: str, desde: str) -> str:
    """El SELECT final del bloque: de su primera columna al FROM principal."""
    bloque = _bloque(tabla)
    inicio = bloque.index(primera)
    return bloque[inicio : bloque.index(desde, inicio)]


def _columnas(proyeccion: str) -> list[str]:
    return re.findall(r"\bAS ([a-z_]+)\b", proyeccion)


def _proyeccion_ofertas() -> str:
    return _proyeccion(
        "comparativo_ofertas", "SELECT d.ide AS oferta_id", "FROM raw.comprv p"
    )


def test_f038_ofertas_r2_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_ofertas())) == COLUMNAS_OFERTAS


def test_f038_ofertas_r2_grano_una_fila_por_oferta_incluidas_las_ficticias() -> None:
    texto = _ejecutable_08()
    assert "ALTER TABLE compras.comparativo_ofertas ADD PRIMARY KEY (oferta_id)" in texto
    bloque = _bloque("comparativo_ofertas")
    assert "FROM raw.comprv p JOIN raw.dco d ON d.ide = p.docide" in bloque
    assert "JOIN raw.con c ON c.ide = d.ide" in bloque
    principal = bloque[bloque.index("FROM raw.comprv p") :]
    sin_subconsultas = re.sub(r"\((?:[^()]|\([^()]*\))*\)", "()", principal)
    assert " WHERE " not in sin_subconsultas, (
        "un WHERE en el FROM principal cambia el grano: R2 publica TODAS las "
        "ofertas, incluidas las ficticias"
    )


def test_f038_ofertas_r3_proveedor_de_dco_entide() -> None:
    proyeccion = _proyeccion_ofertas()
    for esperado in (
        "NULLIF(d.entide, 0) AS proveedor_id",
        "NULLIF(TRIM(d.entcod), '') AS proveedor_codigo",
        "NULLIF(TRIM(d.entres), '') AS proveedor_nombre",
        "NULLIF(TRIM(d.entcif), '') AS proveedor_cif",
    ):
        assert esperado in proyeccion, esperado


def test_f038_prvide_r3_el_sql_no_lee_comprv_prvide() -> None:
    """`comprv.prvide` está informado en el 18 %: quien una por ahí pierde
    el 82 % de las ofertas (F-072, medido en origen)."""
    assert "prvide" not in _ejecutable_08().lower()


def test_f038_totdoc_r12_el_sql_no_lee_dco_totdoc() -> None:
    """`dco.totdoc` lleva IVA (R-COMPRAS-SIN-IVA): el importe es `totbas`."""
    assert "totdoc" not in _ejecutable_08().lower()


def test_f038_ofertas_r8_marca_la_ficticia_con_la_funcion_del_dominio() -> None:
    bloque = _bloque("comparativo_ofertas")
    assert "compras.fn_familia_ficticia(d.entcif, d.entres)" in bloque
    proyeccion = _proyeccion_ofertas()
    assert "ff.familia IS NOT NULL AS es_ficticia" in proyeccion
    assert "ff.familia AS familia_ficticia" in proyeccion


def test_f038_ofertas_r4_estado_tip_12_por_la_pareja() -> None:
    bloque = _bloque("comparativo_ofertas")
    assert (
        "LEFT JOIN LATERAL compras.fn_estado_documento(12, c.est) est ON TRUE"
        in bloque
    )
    assert "c.est AS estado_id" in _proyeccion_ofertas()


def test_f038_ofertas_r15_la_ganadora_es_la_aceptada_definitivamente() -> None:
    assert "COALESCE(c.est = 6, FALSE) AS es_ganadora" in _proyeccion_ofertas()


def test_f038_ofertas_r12_importes_documento_sin_iva_y_lineas() -> None:
    proyeccion = _proyeccion_ofertas()
    assert "d.totbas::NUMERIC(18, 2) AS importe_ofertado_documento" in proyeccion
    assert "li.importe_lineas AS importe_ofertado_lineas" in proyeccion
    bloque = _bloque("comparativo_ofertas")
    lineas = re.search(r"LEFT JOIN \( ?(SELECT .*?) ?\) li ON li\.docide = d\.ide", bloque)
    assert lineas is not None, "faltan las líneas agregadas de `raw.dcopro`"
    sub = lineas.group(1)
    assert "FROM raw.dcopro lp WHERE lp.comlinide > 0 GROUP BY lp.docide" in sub, (
        "solo cuentan las líneas de oferta de una línea del comparativo"
    )
    assert "SUM(lp.tot)::NUMERIC(18, 2) AS importe_lineas" in sub


def test_f038_ofertas_indices() -> None:
    texto = _ejecutable_08()
    for columna in ("comparativo_id", "proveedor_id", "familia_ficticia"):
        assert re.search(
            rf"CREATE INDEX \w+ ON compras\.comparativo_ofertas \({columna}\)", texto
        ), columna


def test_f038_guarda_r21_dos_contratos_rompen_el_build() -> None:
    """Un comparativo con dos `ctride` distintos > 0 hace fallar el build.

    Hoy 0 (medido el 2026-10-04): es una guarda, no un `MIN` silencioso que
    elija uno de los dos contratos sin decirlo.
    """
    texto = _ejecutable_08()
    assert texto.index("DO $$") < texto.index("CREATE TABLE"), (
        "la guarda va LO PRIMERO: si falla, no se ha tirado ninguna tabla"
    )
    guarda = texto[texto.index("DO $$") : texto.index("END $$;")]
    assert "FROM raw.comlin l WHERE l.ctride > 0 GROUP BY l.comide" in guarda
    assert "HAVING count(DISTINCT l.ctride) > 1" in guarda
    assert "IF v_casos > 0 THEN RAISE EXCEPTION" in guarda


def test_f038_guarda_cabecera_dice_que_construye_y_de_que_lee() -> None:
    texto = _texto(RUTA_COMPARATIVOS)
    assert texto.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/08_comparativos.sql"
    )
    cabecera = texto[: texto.index("DO $$")]
    for nombre in ("compras.comparativo_ofertas", "compras.comparativos", "raw.comprv"):
        assert nombre in cabecera, nombre



# ===========================================================================
# T4 · 08_comparativos.sql, parte 2: compras.comparativos
# ===========================================================================

#: Las columnas de `compras.comparativos`, EN SU ORDEN (design §4).
COLUMNAS_COMPARATIVOS = (
    "comparativo_id",
    "codigo_comparativo",
    "nombre_comparativo",
    "fecha_alta",
    "obra_id",
    "codigo_obra",
    "nombre_obra",
    "empresa_id",
    "clave_obra",
    "actividad_id",
    "actividad",
    "estado_id",
    "estado_codigo",
    "estado",
    "contrato_id",
    "codigo_contrato",
    "fecha_contrato",
    "n_ofertas",
    "n_ofertas_reales",
    "n_ofertas_reales_con_importe",
    "n_ofertas_ganadoras",
    "oferta_ganadora_id",
    "proveedor_ganador_id",
    "proveedor_ganador_nombre",
    "importe_ofertado_documento_ganadora",
    "importe_ofertado_lineas_ganadora",
    "importe_adjudicado_lineas",
    "adjudicado_atipico",
    "importe_contratado",
    "oferta_real_minima",
    "oferta_real_maxima",
    "ahorro_concurso",
    "n_firmas",
    "n_firmas_pendientes",
    "fecha_aprobacion",
    "aprobado_por",
)

#: Lo que `com` trae VACÍO en origen (R5): siete fechas y cinco campos.
CAMPOS_VACIOS_DE_COM = (
    "fecent", "feclim", "fecsum", "feccon", "fecinirec", "fecfinrec", "fecdiv",
    "ppoide", "prmide", "pexide", "tipsub", "horlim",
)


def _proyeccion_comparativos() -> str:
    return _proyeccion(
        "comparativos", "SELECT m.ide AS comparativo_id", "FROM raw.com m"
    )


def _cte(nombre: str) -> str:
    """El cuerpo de una CTE del bloque de `compras.comparativos`."""
    bloque = _bloque("comparativos")
    inicio = bloque.index(f" {nombre} AS (")
    profundidad = 0
    for i in range(bloque.index("(", inicio), len(bloque)):
        profundidad += {"(": 1, ")": -1}.get(bloque[i], 0)
        if profundidad == 0:
            return bloque[inicio : i + 1]
    raise AssertionError(f"CTE {nombre} sin cerrar")


def test_f038_r1_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_comparativos())) == COLUMNAS_COMPARATIVOS


def test_f038_r1_grano_una_fila_por_comparativo() -> None:
    texto = _ejecutable_08()
    assert "ALTER TABLE compras.comparativos ADD PRIMARY KEY (comparativo_id)" in texto
    bloque = _bloque("comparativos")
    desde = "FROM raw.com m JOIN raw.con c ON c.ide = m.ide"
    principal = bloque[bloque.index(desde) + len(desde) :]
    sin_subconsultas = re.sub(r"\((?:[^()]|\([^()]*\))*\)", "()", principal)
    assert " WHERE " not in sin_subconsultas
    assert " JOIN " not in sin_subconsultas.replace("LEFT JOIN", ""), (
        "después de `raw.con` todo es LEFT JOIN: ningún comparativo se pierde"
    )


def test_f038_r1_indices() -> None:
    texto = _ejecutable_08()
    for columna in ("obra_id", "contrato_id", "actividad_id", "estado_id"):
        assert re.search(
            rf"CREATE INDEX \w+ ON compras\.comparativos \({columna}\)", texto
        ), columna


def test_f038_r4_estado_tip_46_por_la_pareja() -> None:
    bloque = _bloque("comparativos")
    assert (
        "LEFT JOIN LATERAL compras.fn_estado_documento(46, c.est) est ON TRUE" in bloque
    )
    assert "c.est AS estado_id" in _proyeccion_comparativos()
    assert "raw.conest" not in _ejecutable_08(), (
        "ninguna traducción une solo por estado: se usa la función (R4)"
    )


def test_f038_r5_fecha_alta_de_con_y_nada_de_los_campos_vacios_de_com() -> None:
    assert "compras.fn_sigrid_date(c.fec) AS fecha_alta" in _proyeccion_comparativos()
    ejecutable = _ejecutable_08().lower()
    for campo in CAMPOS_VACIOS_DE_COM:
        assert not re.search(rf"\b{campo}\b", ejecutable), campo


def test_f038_r6_actividad_de_auxpronat() -> None:
    bloque = _bloque("comparativos")
    assert "LEFT JOIN raw.auxpronat a ON a.ide = NULLIF(m.natide, 0)" in bloque
    proyeccion = _proyeccion_comparativos()
    assert "NULLIF(m.natide, 0) AS actividad_id" in proyeccion
    assert "a.res AS actividad" in proyeccion


def test_f038_r7_obra_con_empresa_y_clave() -> None:
    bloque = _bloque("comparativos")
    assert "LEFT JOIN raw.con ob ON ob.ide = NULLIF(m.obride, 0)" in bloque
    assert (
        "LEFT JOIN maestro.v_obra_fichas fo ON fo.obra_id = NULLIF(m.obride, 0)"
        in bloque
    )
    proyeccion = _proyeccion_comparativos()
    for esperado in (
        "NULLIF(m.obride, 0) AS obra_id",
        "ob.cod AS codigo_obra",
        "ob.res AS nombre_obra",
        "fo.empresa_id AS empresa_id",
        "fo.clave_obra AS clave_obra",
    ):
        assert esperado in proyeccion, esperado


def test_f038_r14_ninguna_columna_se_llama_importe_a_secas() -> None:
    columnas = _columnas(_proyeccion_comparativos()) + _columnas(_proyeccion_ofertas())
    assert "importe" not in columnas
    assert not re.search(r"\bAS importe\b", _ejecutable_08())


def test_f038_r13_las_cuatro_magnitudes_con_su_nombre() -> None:
    proyeccion = _proyeccion_comparativos()
    for esperado in (
        "g.importe_ofertado_documento AS importe_ofertado_documento_ganadora",
        "g.importe_ofertado_lineas AS importe_ofertado_lineas_ganadora",
        "li.importe_adjudicado_lineas AS importe_adjudicado_lineas",
        "ct.importe_contratado AS importe_contratado",
    ):
        assert esperado in proyeccion, esperado
    lineas = _cte("lineas")
    assert (
        "SUM(COALESCE(l.can, 0) * COALESCE(l.pre, 0))::NUMERIC(18, 2) "
        "AS importe_adjudicado_lineas" in lineas
    )
    contratado = _cte("contratado")
    assert "FROM compras.contrato_lineas cl GROUP BY cl.contrato_id" in contratado
    assert "SUM(cl.importe)::NUMERIC(18, 2) AS importe_contratado" in contratado
    assert "LEFT JOIN contratado ct ON ct.contrato_id = li.contrato_id" in _bloque(
        "comparativos"
    )


def test_f038_r15_ganadora_solo_si_es_unica() -> None:
    ofertas = _cte("ofertas")
    assert "count(*) FILTER (WHERE o.es_ganadora) AS n_ofertas_ganadoras" in ofertas
    ganadora = _cte("ganadora")
    assert "a.n_ofertas_ganadoras = 1" in ganadora, (
        "con dos ganadoras no se elige una: ganadora e importes a NULL (R15)"
    )
    assert "WHERE o.es_ganadora" in ganadora
    assert "LEFT JOIN ganadora g ON g.comparativo_id = m.ide" in _bloque("comparativos")
    proyeccion = _proyeccion_comparativos()
    assert "g.oferta_id AS oferta_ganadora_id" in proyeccion
    assert "g.proveedor_id AS proveedor_ganador_id" in proyeccion
    assert "g.proveedor_nombre AS proveedor_ganador_nombre" in proyeccion


def test_f038_r16_atipico_con_los_umbrales_del_dominio() -> None:
    proyeccion = _proyeccion_comparativos()
    esperado = (
        "CASE WHEN oft.mayor_oferta > 0 THEN "
        f"li.importe_adjudicado_lineas > {FACTOR_ATIPICO} * oft.mayor_oferta "
        f"AND li.importe_adjudicado_lineas > {int(MINIMO_ATIPICO)} "
        "END AS adjudicado_atipico"
    )
    assert esperado in proyeccion, (
        "el atípico no lleva los umbrales del dominio (R16): "
        f"se esperaba «{esperado}»"
    )
    assert "MAX(o.importe_ofertado_documento) AS mayor_oferta" in _cte("ofertas"), (
        "la mayor oferta para el atípico es la de TODAS las ofertas"
    )


def test_f038_r18_recuentos_de_ofertas() -> None:
    ofertas = _cte("ofertas")
    for esperado in (
        "count(*) AS n_ofertas",
        "count(*) FILTER (WHERE NOT o.es_ficticia) AS n_ofertas_reales",
        "count(*) FILTER (WHERE NOT o.es_ficticia AND "
        "o.importe_ofertado_documento > 0) AS n_ofertas_reales_con_importe",
    ):
        assert esperado in ofertas, esperado
    assert "LEFT JOIN ofertas oft ON oft.comparativo_id = m.ide" in _bloque(
        "comparativos"
    )
    proyeccion = _proyeccion_comparativos()
    for columna in (
        "n_ofertas", "n_ofertas_reales", "n_ofertas_reales_con_importe",
        "n_ofertas_ganadoras",
    ):
        assert f"COALESCE(oft.{columna}, 0) AS {columna}" in proyeccion, columna


def test_f038_r19_ahorro_solo_con_ofertas_reales_con_importe() -> None:
    ofertas = _cte("ofertas")
    filtro = "FILTER (WHERE NOT o.es_ficticia AND o.importe_ofertado_documento > 0)"
    assert f"MIN(o.importe_ofertado_documento) {filtro} AS minima_real" in ofertas
    assert f"MAX(o.importe_ofertado_documento) {filtro} AS maxima_real" in ofertas
    proyeccion = _proyeccion_comparativos()
    condicion = "CASE WHEN oft.n_ofertas_reales_con_importe >= 2 THEN"
    assert f"{condicion} oft.minima_real END AS oferta_real_minima" in proyeccion
    assert f"{condicion} oft.maxima_real END AS oferta_real_maxima" in proyeccion
    assert (
        f"{condicion} oft.maxima_real - oft.minima_real END AS ahorro_concurso"
        in proyeccion
    )


def test_f038_r20_contrato_por_comlin_ctride() -> None:
    lineas = _cte("lineas")
    assert "MAX(NULLIF(l.ctride, 0)) AS contrato_id" in lineas
    assert "FROM raw.comlin l GROUP BY l.comide" in lineas
    bloque = _bloque("comparativos")
    assert "LEFT JOIN lineas li ON li.comparativo_id = m.ide" in bloque
    assert "LEFT JOIN raw.con cc ON cc.ide = li.contrato_id" in bloque
    proyeccion = _proyeccion_comparativos()
    assert "li.contrato_id AS contrato_id" in proyeccion
    assert "cc.cod AS codigo_contrato" in proyeccion
    assert "compras.fn_sigrid_date(cc.fec) AS fecha_contrato" in proyeccion
    ejecutable = _ejecutable_08()
    assert "ctr.comide" not in ejecutable and "raw.ctr " not in ejecutable, (
        "el enlace es `comlin.ctride` (18.633 comparativos), no la cabecera "
        "del contrato (56 %) (R20)"
    )


def test_f038_r23_firmas_y_fecha_de_aprobacion() -> None:
    firmas = _cte("firmas")
    for esperado in (
        "count(*) AS n_firmas",
        "count(*) FILTER (WHERE f.fir = 0) AS n_firmas_pendientes",
        "bool_or(f.estfin = fc.est) AS estado_es_final",
        "FROM raw.confir f JOIN raw.com fm ON fm.ide = f.conide "
        "JOIN raw.con fc ON fc.ide = f.conide",
    ):
        assert esperado in firmas, esperado
    ultima = _cte("ultima_firma")
    assert "SELECT DISTINCT ON (f.conide)" in ultima
    assert "WHERE f.fir <> 0" in ultima, "la última FIRMADA: las pendientes no cuentan"
    assert "ORDER BY f.conide, f.fec DESC NULLS LAST, f.hor DESC NULLS LAST, f.ide DESC" in ultima
    proyeccion = _proyeccion_comparativos()
    bloque = _bloque("comparativos")
    assert "LEFT JOIN firmas fi ON fi.comparativo_id = m.ide" in bloque
    assert "LEFT JOIN ultima_firma uf ON uf.comparativo_id = m.ide" in bloque
    assert "COALESCE(fi.n_firmas, 0) AS n_firmas" in proyeccion
    assert "COALESCE(fi.n_firmas_pendientes, 0) AS n_firmas_pendientes" in proyeccion
    assert (
        "CASE WHEN fi.estado_es_final THEN uf.fecha END AS fecha_aprobacion"
        in proyeccion
    )
    assert (
        "CASE WHEN fi.estado_es_final THEN uf.usuario END AS aprobado_por"
        in proyeccion
    )


@pytest.mark.parametrize(
    ("tabla", "proyeccion", "alias_definidos"),
    [
        (
            "comparativo_ofertas",
            "_proyeccion_ofertas",
            {"compras", "p", "d", "c", "li", "ff", "est"},
        ),
        (
            "comparativos",
            "_proyeccion_comparativos",
            {"compras", "m", "c", "ob", "fo", "a", "est", "oft", "g", "li", "cc",
             "ct", "fi", "uf"},
        ),
    ],
)
def test_f038_la_proyeccion_solo_usa_alias_del_from(
    tabla: str, proyeccion: str, alias_definidos: set[str]
) -> None:
    """Un alias mal escrito no rompe ningún test de texto, pero sí el build."""
    usados = set(re.findall(r"\b([a-z]+)\.[a-z_]+", globals()[proyeccion]()))
    assert usados <= alias_definidos, usados - alias_definidos
    bloque = _bloque(tabla)
    for alias in alias_definidos - {"compras"}:
        definido = (
            rf"(?:FROM|JOIN) (?:LATERAL )?[a-z_.]+(?:\([^()]*\))? {alias} (?:ON|JOIN|LEFT|CROSS)"
            rf"|\) {alias} (?:ON|LEFT|CROSS)"
        )
        assert re.search(definido, bloque), f"alias `{alias}` sin definir en el FROM"



# ===========================================================================
# FASE 2 · T12 · `compras.fn_porcentaje_dto` (R27)
# ===========================================================================


def test_f038_r27_dto_la_funcion_usa_el_patron_del_dominio() -> None:
    """El patrón del SQL ES `PATRON_DTO`: si cambia un lado, esto se pone rojo."""
    cuerpo = _funcion("compras.fn_porcentaje_dto")
    assert "compras.fn_porcentaje_dto(t TEXT) RETURNS NUMERIC" in cuerpo
    assert f"WHEN t ~ '{PATRON_DTO}' THEN" in cuerpo, (
        f"el patrón del SQL no es el del dominio («{PATRON_DTO}»): {cuerpo}"
    )
    assert "replace(replace(t, '%', ''), ',', '.')::NUMERIC" in cuerpo


def test_f038_r27_dto_sin_exception_ni_cero_ni_else() -> None:
    """Lo que no casa es NULL: sin `EXCEPTION` (el patrón garantiza el cast),
    sin `ELSE` (un cero mentiría) e `IMMUTABLE`."""
    cuerpo = _funcion("compras.fn_porcentaje_dto")
    assert "IMMUTABLE" in cuerpo
    assert "EXCEPTION" not in cuerpo.upper()
    assert " ELSE " not in cuerpo
    assert "COALESCE" not in cuerpo.upper()



# ===========================================================================
# FASE 2 · T13 · 09_comparativos_detalle.sql: las líneas de los dos lados y la
# base del objetivo en el descompuesto (R25, R26, R29, R30, R32)
# ===========================================================================

RUTA_DETALLE = DIRECTORIO_SQL / "09_comparativos_detalle.sql"

#: Las columnas de `compras.comparativo_lineas`, EN SU ORDEN (design §5).
COLUMNAS_LINEAS = (
    "linea_id",
    "comparativo_id",
    "numero_linea",
    "posicion",
    "contrato_id",
    "linea_necesidad_id",
    "partida_id",
    "linea_oferta_ganadora_id",
    "cantidad",
    "precio",
    "importe_adjudicado",
)

#: Las columnas de `compras.comparativo_oferta_lineas`, EN SU ORDEN (design §5).
COLUMNAS_OFERTA_LINEAS = (
    "linea_oferta_id",
    "oferta_id",
    "comparativo_id",
    "comparativo_linea_id",
    "producto_id",
    "descripcion",
    "unidad_medida",
    "cantidad",
    "precio",
    "importe_ofertado_linea",
    "descuento_texto",
    "porcentaje_descuento",
    "es_ficticia",
    "familia_ficticia",
    "base_regla",
    "precio_base",
    "origen_base",
    "casa_base",
)


def _ejecutable_09() -> str:
    return _compacto(_texto(RUTA_DETALLE))


def _bloque_09(tabla: str) -> str:
    texto = _ejecutable_09()
    inicio = texto.index(f"DROP TABLE IF EXISTS compras.{tabla} CASCADE")
    fin = texto.index(f"ALTER TABLE compras.{tabla} ADD PRIMARY KEY")
    return texto[inicio:fin]


def _cte_09(tabla: str, nombre: str) -> str:
    """El cuerpo de una CTE del bloque de `compras.<tabla>` en `09`."""
    bloque = _bloque_09(tabla)
    inicio = bloque.index(f" {nombre} AS (")
    profundidad = 0
    for i in range(bloque.index("(", inicio), len(bloque)):
        profundidad += {"(": 1, ")": -1}.get(bloque[i], 0)
        if profundidad == 0:
            return bloque[inicio : i + 1]
    raise AssertionError(f"CTE {nombre} sin cerrar")


def _proyeccion_09(tabla: str, primera: str, desde: str) -> str:
    """El SELECT FINAL del bloque: la ÚLTIMA aparición de su primera columna
    (las CTE de delante pueden empezar igual)."""
    bloque = _bloque_09(tabla)
    inicio = bloque.rindex(primera)
    return bloque[inicio : bloque.index(desde, inicio)]


def _proyeccion_lineas() -> str:
    return _proyeccion_09(
        "comparativo_lineas", "SELECT l.ide AS linea_id", "FROM raw.comlin l"
    )


def _proyeccion_oferta_lineas() -> str:
    return _proyeccion_09(
        "comparativo_oferta_lineas",
        "SELECT lo.linea_oferta_id AS linea_oferta_id",
        "FROM lineas_oferta lo",
    )


def _obra_abc() -> str:
    texto = _ejecutable_09()
    inicio = texto.index("CREATE TEMP TABLE _f038_obra_abc")
    return texto[inicio : texto.index(";", inicio)]


def test_f038_lineas_cabecera_dice_que_construye_de_que_lee_y_el_desfase() -> None:
    texto = _texto(RUTA_DETALLE)
    assert texto.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/09_comparativos_detalle.sql"
    )
    cabecera = normalizado(texto[: texto.index("DROP TABLE")])
    for nombre in (
        "compras.comparativo_lineas", "compras.comparativo_oferta_lineas",
        "compras.comparativo_objetivo", "compras.comparativo_firmas",
        "descompuestos.lineas", "build_descompuestos", "NOCHE ANTERIOR",
    ):
        assert nombre in cabecera, nombre


# --- R25 · compras.comparativo_lineas ---------------------------------------


def test_f038_r25_lineas_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_lineas())) == COLUMNAS_LINEAS


def test_f038_r25_lineas_grano_una_fila_por_comlin_y_partida_de_su_necesidad() -> None:
    texto = _ejecutable_09()
    assert "ALTER TABLE compras.comparativo_lineas ADD PRIMARY KEY (linea_id)" in texto
    bloque = _bloque_09("comparativo_lineas")
    desde = "FROM raw.comlin l LEFT JOIN raw.dncpro n ON n.ide = NULLIF(l.dncproide, 0);"
    assert desde in bloque, "una fila por `raw.comlin`; la partida, por LEFT JOIN"
    proyeccion = _proyeccion_lineas()
    for esperado in (
        "l.comide AS comparativo_id",
        "l.numlin AS numero_linea",
        "l.pos AS posicion",
        "NULLIF(l.ctride, 0) AS contrato_id",
        "NULLIF(l.dncproide, 0) AS linea_necesidad_id",
        "NULLIF(n.paride, 0) AS partida_id",
        "NULLIF(l.dcoproide, 0) AS linea_oferta_ganadora_id",
        "COALESCE(l.can, 0)::NUMERIC(20, 6) AS cantidad",
        "COALESCE(l.pre, 0)::NUMERIC(20, 6) AS precio",
        "(COALESCE(l.can, 0) * COALESCE(l.pre, 0))::NUMERIC(18, 2) AS importe_adjudicado",
    ):
        assert esperado in proyeccion, esperado


def test_f038_r25_lineas_indices() -> None:
    texto = _ejecutable_09()
    for columna in ("comparativo_id", "contrato_id", "partida_id"):
        assert re.search(
            rf"CREATE INDEX \w+ ON compras\.comparativo_lineas \({columna}\)", texto
        ), columna


# --- R26, R27 · compras.comparativo_oferta_lineas ---------------------------


def test_f038_r26_oferta_lineas_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_oferta_lineas())) == COLUMNAS_OFERTA_LINEAS


def test_f038_r26_oferta_lineas_grano_lineas_de_comparativo_de_ofertas_de_r2() -> None:
    texto = _ejecutable_09()
    assert (
        "ALTER TABLE compras.comparativo_oferta_lineas ADD PRIMARY KEY (linea_oferta_id)"
        in texto
    )
    lineas = _cte_09("comparativo_oferta_lineas", "lineas_oferta")
    assert (
        "FROM raw.dcopro lp JOIN compras.comparativo_ofertas o ON o.oferta_id = lp.docide "
        "WHERE lp.comlinide > 0" in lineas
    ), "solo las líneas que responden a una línea del comparativo, de ofertas de R2"
    for esperado in (
        "lp.ide AS linea_oferta_id",
        "o.oferta_id AS oferta_id",
        "o.comparativo_id AS comparativo_id",
        "lp.comlinide AS comparativo_linea_id",
        "NULLIF(lp.proide, 0) AS producto_id",
        "lp.res AS descripcion",
        "lp.unimed AS unidad_medida",
        "COALESCE(lp.can, 0)::NUMERIC(20, 6) AS cantidad",
        "COALESCE(lp.pre, 0)::NUMERIC(20, 6) AS precio",
        "lp.tot::NUMERIC(18, 2) AS importe_ofertado_linea",
        "o.es_ficticia AS es_ficticia",
        "o.familia_ficticia AS familia_ficticia",
    ):
        assert esperado in lineas, esperado


def test_f038_r27_lineas_el_dto_literal_y_su_porcentaje_por_la_funcion() -> None:
    lineas = _cte_09("comparativo_oferta_lineas", "lineas_oferta")
    assert "lp.dto AS descuento_texto" in lineas
    assert "compras.fn_porcentaje_dto(lp.dto) AS porcentaje_descuento" in lineas
    assert "replace(" not in _ejecutable_09(), (
        "el porcentaje se convierte en UNA función (R27), no en línea"
    )


def test_f038_r26_oferta_lineas_indices() -> None:
    texto = _ejecutable_09()
    for columna in ("oferta_id", "comparativo_linea_id"):
        assert re.search(
            rf"CREATE INDEX \w+ ON compras\.comparativo_oferta_lineas \({columna}\)",
            texto,
        ), columna


# --- R29, R30 · la base del objetivo en el descompuesto (D4) ----------------


def test_f038_r29_base_primera_abc_de_la_obra_por_es_primera_abc() -> None:
    abc = _obra_abc()
    assert "ON COMMIT DROP" in abc, "temporal: vive lo que la transacción del fichero"
    assert (
        "SELECT d.obra_id, MIN(d.fase_num) AS fase_abc FROM descompuestos.lineas d "
        "WHERE d.es_primera_abc GROUP BY d.obra_id" in abc
    )
    texto = _ejecutable_09()
    assert texto.index("CREATE TEMP TABLE _f038_obra_abc") < texto.index(
        "CREATE TABLE compras.comparativo_oferta_lineas"
    )


def test_f038_r29_base_solo_lineas_objetivo_con_porcentaje_y_su_regla() -> None:
    objetivo = _cte_09("comparativo_oferta_lineas", "objetivo")
    assert (
        "WHERE lo.familia_ficticia = 'OBJETIVO' AND lo.porcentaje_descuento IS NOT NULL"
        in objetivo
    )
    regla = (
        f"CASE WHEN ab.fase_abc IS NOT NULL THEN '{base_regla(True)}' "
        f"ELSE '{base_regla(False)}' END AS base_regla"
    )
    assert regla in objetivo, f"la regla no es la del dominio: «{regla}»"


def test_f038_r29_base_obra_del_comparativo_y_partida_de_su_linea() -> None:
    objetivo = _cte_09("comparativo_oferta_lineas", "objetivo")
    for esperado in (
        "LEFT JOIN compras.comparativo_lineas cl ON cl.linea_id = lo.comparativo_linea_id",
        "LEFT JOIN compras.comparativos cm ON cm.comparativo_id = lo.comparativo_id",
        "LEFT JOIN _f038_obra_abc ab ON ab.obra_id = cm.obra_id",
        "cm.obra_id AS obra_id",
        "cl.partida_id AS partida_id",
        "cl.linea_necesidad_id AS dncpro_id",
    ):
        assert esperado in objetivo, esperado
    candidatas = _cte_09("comparativo_oferta_lineas", "candidatas")
    assert (
        "JOIN descompuestos.lineas d ON d.obra_id = ob.obra_id "
        "AND d.partida_id = ob.partida_id" in candidatas
    )


def test_f038_r29_base_casa_con_la_tolerancia_del_dominio() -> None:
    candidatas = _cte_09("comparativo_oferta_lineas", "candidatas")
    esperado = (
        "COALESCE(abs(ob.precio - d.precio * (1 - ob.pct / 100)) <= "
        f"{TOLERANCIA_ABS} + {TOLERANCIA_REL} * abs(ob.precio), FALSE) AS casa"
    )
    assert esperado in candidatas, f"«casa» no es la del dominio: «{esperado}»"


def test_f038_r30_base_nunca_una_version_posterior_a_la_abc() -> None:
    """D4: con ABC, la ABC y lo ANTERIOR; sin ABC, solo Estudios. Nunca más."""
    candidatas = _cte_09("comparativo_oferta_lineas", "candidatas")
    anteriores = ", ".join(f"'{o}'" for o in ORIGENES_ANTERIORES_ABC)
    estudios = ", ".join(f"'{o}'" for o in ORIGENES_ESTUDIOS)
    assert (
        "WHERE (ob.fase_abc IS NOT NULL AND (d.es_primera_abc OR d.origen IN "
        f"({anteriores})) AND d.fase_num <= ob.fase_abc) "
        f"OR (ob.fase_abc IS NULL AND d.origen IN ({estudios}))" in candidatas
    )
    ejecutable = _ejecutable_09()
    for posterior in ("'MASTER_PLANIF_JO'", "'PLANIF_JO'", "es_vigente", "es_ultima"):
        assert posterior not in ejecutable, posterior
    assert not re.search(r"fase_num (>|>=) ", ejecutable), "nunca una posterior"


def test_f038_r29_base_el_elemento_por_dncpro_y_si_no_el_que_casa() -> None:
    candidatas = _cte_09("comparativo_oferta_lineas", "candidatas")
    assert "COALESCE(d.dncpro_id = ob.dncpro_id, FALSE) AS por_dncpro" in candidatas
    elemento = _cte_09("comparativo_oferta_lineas", "elemento")
    assert "SELECT DISTINCT ON (c.linea_oferta_id, c.origen, c.fase_num)" in elemento
    assert "WHERE c.por_dncpro OR c.casa" in elemento
    assert (
        "ORDER BY c.linea_oferta_id, c.origen, c.fase_num, c.por_dncpro DESC, "
        "c.casa DESC, c.orden" in elemento
    ), "el de igual dncpro_id manda; si no lo hay, el que case"


def test_f038_r30_base_d4_la_abc_si_casa_si_no_la_anterior_mas_reciente() -> None:
    elegida = _cte_09("comparativo_oferta_lineas", "elegida")
    assert "SELECT DISTINCT ON (e.linea_oferta_id)" in elegida
    assert "WHERE e.casa OR e.es_primera_abc OR ob.fase_abc IS NULL" in elegida, (
        "si ninguna casa, la de la REGLA (la ABC o Estudios), nunca otra anterior"
    )
    assert (
        "ORDER BY e.linea_oferta_id, e.casa DESC, e.fase_num DESC, e.origen" in elegida
    ), "entre las que casan, la de mayor fase: la ABC y si no la anterior más reciente"


def test_f038_r30_base_columnas_precio_origen_y_casa() -> None:
    proyeccion = _proyeccion_oferta_lineas()
    for esperado in (
        "ob.base_regla AS base_regla",
        "el.precio AS precio_base",
        "CASE WHEN el.es_primera_abc THEN 'ABC' ELSE el.origen END || ' v' || "
        "el.fase_num AS origen_base",
        "CASE WHEN el.casa THEN TRUE WHEN cd.linea_oferta_id IS NOT NULL THEN FALSE "
        "END AS casa_base",
    ):
        assert esperado in proyeccion, esperado
    bloque = _bloque_09("comparativo_oferta_lineas")
    for union in (
        "LEFT JOIN objetivo ob ON ob.linea_oferta_id = lo.linea_oferta_id",
        "LEFT JOIN elegida el ON el.linea_oferta_id = lo.linea_oferta_id",
        "LEFT JOIN con_descompuesto cd ON cd.linea_oferta_id = lo.linea_oferta_id",
    ):
        assert union in bloque, union
    assert "SELECT DISTINCT c.linea_oferta_id FROM candidatas c" in _cte_09(
        "comparativo_oferta_lineas", "con_descompuesto"
    ), "sin descompuesto en su partida, `casa_base` NULL (R30)"


def test_f038_r32_lineas_el_detalle_no_cuenta_ofertantes_minima_ni_ahorro() -> None:
    """Ofertantes, mínima y ahorro viven en `compras.comparativos` (08), con
    las ficticias fuera; el detalle no los recalcula sin ese filtro."""
    columnas = set(_columnas(_ejecutable_09()))
    for prohibida in (
        "n_ofertas", "n_ofertas_reales", "oferta_real_minima", "oferta_real_maxima",
        "ahorro_concurso", "minima_real", "maxima_real",
    ):
        assert prohibida not in columnas, prohibida
    assert "MIN(" not in _ejecutable_09().replace("MIN(d.fase_num)", "")
    lineas = _cte_09("comparativo_oferta_lineas", "lineas_oferta")
    assert "o.es_ficticia AS es_ficticia" in lineas, (
        "cada línea lleva si su oferta es ficticia, para poder filtrarla"
    )


def test_f038_r14_lineas_ninguna_columna_se_llama_importe_a_secas() -> None:
    assert not re.search(r"\bAS importe\b", _ejecutable_09())


@pytest.mark.parametrize(
    ("tabla", "proyeccion", "alias_definidos"),
    [
        ("comparativo_lineas", "_proyeccion_lineas", {"l", "n"}),
        ("comparativo_oferta_lineas", "_proyeccion_oferta_lineas", {"lo", "ob", "el", "cd"}),
    ],
)
def test_f038_lineas_la_proyeccion_de_09_solo_usa_alias_del_from(
    tabla: str, proyeccion: str, alias_definidos: set[str]
) -> None:
    """Un alias mal escrito no rompe ningún test de texto, pero sí el build."""
    usados = set(re.findall(r"\b([a-z]+)\.[a-z_]+", globals()[proyeccion]()))
    assert usados <= alias_definidos, usados - alias_definidos
    bloque = _bloque_09(tabla)
    final = bloque[bloque.rindex("FROM "):]
    for alias in alias_definidos:
        assert re.search(rf"(?:FROM|JOIN) [a-z_.]+ {alias}\b", final), (
            f"alias `{alias}` sin definir en el FROM final"
        )


# ===========================================================================
# FASE 2 · T14 · compras.comparativo_objetivo (R31)
# ===========================================================================

#: Las columnas de `compras.comparativo_objetivo`, EN SU ORDEN (design §5).
COLUMNAS_OBJETIVO = (
    "comparativo_id",
    "oferta_objetivo_id",
    "n_ofertas_objetivo",
    "importe_objetivo",
    "porcentaje_objetivo",
    "base_regla",
    "pct_importe_casa_base",
)


def _proyeccion_objetivo() -> str:
    return _proyeccion_09(
        "comparativo_objetivo", "SELECT ob.comparativo_id AS comparativo_id",
        "FROM objetivas ob",
    )


def test_f038_r31_objetivo_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_objetivo())) == COLUMNAS_OBJETIVO


def test_f038_r31_objetivo_grano_un_comparativo_con_oferta_objetivo() -> None:
    texto = _ejecutable_09()
    assert (
        "ALTER TABLE compras.comparativo_objetivo ADD PRIMARY KEY (comparativo_id)"
        in texto
    )
    objetivas = _cte_09("comparativo_objetivo", "objetivas")
    assert (
        "FROM compras.comparativo_ofertas o WHERE o.familia_ficticia = 'OBJETIVO'"
        in objetivas
    )
    assert "count(*) OVER (PARTITION BY o.comparativo_id) AS n_ofertas_objetivo" in objetivas
    bloque = _bloque_09("comparativo_objetivo")
    assert bloque.rstrip().endswith("WHERE ob.orden = 1;"), (
        "UNA fila por comparativo: la oferta objetivo elegida"
    )


def test_f038_r31_objetivo_la_mas_reciente_por_fecha_y_luego_ide() -> None:
    objetivas = _cte_09("comparativo_objetivo", "objetivas")
    assert (
        "row_number() OVER (PARTITION BY o.comparativo_id ORDER BY "
        "o.fecha_oferta DESC NULLS LAST, o.oferta_id DESC) AS orden" in objetivas
    ), "la OBJETIVO más reciente (`con.fec`) y, a igual fecha, la de mayor ide"


def test_f038_r31_objetivo_importe_y_porcentaje_solo_si_es_unico() -> None:
    proyeccion = _proyeccion_objetivo()
    assert "ob.oferta_id AS oferta_objetivo_id" in proyeccion
    assert "ob.n_ofertas_objetivo AS n_ofertas_objetivo" in proyeccion
    assert "ob.importe_ofertado_documento AS importe_objetivo" in proyeccion, (
        "el importe del objetivo es su DOCUMENTO, sin IVA (`dco.totbas`)"
    )
    assert (
        "CASE WHEN cp.n_porcentajes = 1 THEN cp.porcentaje END AS porcentaje_objetivo"
        in proyeccion
    )
    con_porcentaje = _cte_09("comparativo_objetivo", "con_porcentaje")
    for esperado in (
        "count(DISTINCT l.porcentaje_descuento) AS n_porcentajes",
        "MAX(l.porcentaje_descuento) AS porcentaje",
        "FROM compras.comparativo_oferta_lineas l WHERE l.familia_ficticia = 'OBJETIVO' "
        "AND l.porcentaje_descuento IS NOT NULL GROUP BY l.oferta_id",
    ):
        assert esperado in con_porcentaje, esperado


def test_f038_r31_objetivo_regla_de_la_obra_y_parte_del_importe_que_casa() -> None:
    proyeccion = _proyeccion_objetivo()
    regla = (
        f"CASE WHEN ab.fase_abc IS NOT NULL THEN '{base_regla(True)}' "
        f"ELSE '{base_regla(False)}' END AS base_regla"
    )
    assert regla in proyeccion, "la misma regla que las líneas, la del dominio"
    assert (
        "ROUND(100 * cp.importe_casa_base / NULLIF(cp.importe_con_porcentaje, 0), 2) "
        "AS pct_importe_casa_base" in proyeccion
    )
    con_porcentaje = _cte_09("comparativo_objetivo", "con_porcentaje")
    assert "SUM(l.importe_ofertado_linea) AS importe_con_porcentaje" in con_porcentaje
    assert (
        "COALESCE(SUM(l.importe_ofertado_linea) FILTER (WHERE l.casa_base), 0) "
        "AS importe_casa_base" in con_porcentaje
    )
    bloque = _bloque_09("comparativo_objetivo")
    for union in (
        "LEFT JOIN con_porcentaje cp ON cp.oferta_id = ob.oferta_id",
        "LEFT JOIN compras.comparativos cm ON cm.comparativo_id = ob.comparativo_id",
        "LEFT JOIN _f038_obra_abc ab ON ab.obra_id = cm.obra_id",
    ):
        assert union in bloque, union
    texto = _ejecutable_09()
    assert texto.index("CREATE TABLE compras.comparativo_oferta_lineas") < texto.index(
        "CREATE TABLE compras.comparativo_objetivo"
    ), "el objetivo agrega las líneas: va detrás de ellas"


def test_f038_r31_objetivo_la_proyeccion_solo_usa_alias_del_from() -> None:
    usados = set(re.findall(r"\b([a-z]+)\.[a-z_]+", _proyeccion_objetivo()))
    assert usados <= {"ob", "cp", "ab"}, usados


# ===========================================================================
# FASE 2 · T15 · compras.comparativo_firmas (R33, D3)
# ===========================================================================

#: Las columnas de `compras.comparativo_firmas`, EN SU ORDEN (design §5).
COLUMNAS_FIRMAS = (
    "firma_id",
    "comparativo_id",
    "circuito",
    "escalon",
    "usuario",
    "fecha",
    "hora",
    "pendiente",
    "firma_digital_valida",
    "estado_final_id",
)


def _proyeccion_firmas() -> str:
    return _proyeccion_09(
        "comparativo_firmas", "SELECT f.ide AS firma_id", "FROM raw.confir f"
    )


def test_f038_r33_firmas_columnas_en_su_orden() -> None:
    assert tuple(_columnas(_proyeccion_firmas())) == COLUMNAS_FIRMAS


def test_f038_r33_firmas_grano_una_fila_por_confir_de_un_comparativo() -> None:
    texto = _ejecutable_09()
    assert "ALTER TABLE compras.comparativo_firmas ADD PRIMARY KEY (firma_id)" in texto
    bloque = _bloque_09("comparativo_firmas")
    assert "FROM raw.confir f JOIN raw.com m ON m.ide = f.conide;" in bloque, (
        "solo las firmas de un comparativo (`conide` en `raw.com`), todas"
    )


def test_f038_r33_firmas_circuito_escalon_usuario_y_estado_de_la_firma() -> None:
    proyeccion = _proyeccion_firmas()
    for esperado in (
        "f.conide AS comparativo_id",
        "f.cod AS circuito",
        "f.rol AS escalon",
        "f.usu AS usuario",
        "compras.fn_sigrid_date(f.fec) AS fecha",
        "f.hor AS hora",
        # Las mismas definiciones que `n_firmas_pendientes` de 08 (R23)
        "COALESCE(f.fir = 0, FALSE) AS pendiente",
        "COALESCE(f.firok = 1, FALSE) AS firma_digital_valida",
        "f.estfin AS estado_final_id",
    ):
        assert esperado in proyeccion, esperado
    usados = set(re.findall(r"\b([a-z]+)\.[a-z_]+", proyeccion))
    assert usados <= {"f", "compras"}, usados


def test_f038_r33_firmas_indices() -> None:
    texto = _ejecutable_09()
    for columna in ("comparativo_id", "usuario"):
        assert re.search(
            rf"CREATE INDEX \w+ ON compras\.comparativo_firmas \({columna}\)", texto
        ), columna
