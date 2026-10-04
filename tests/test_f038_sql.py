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
    PATRONES_FAMILIA,
    TILDES_DESTINO,
    TILDES_ORIGEN,
)

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
