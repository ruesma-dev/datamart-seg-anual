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
