# tests/test_f118_coeficientes.py
"""
F-118 · Fallo 2 (D6): la venta final del cierre SIN coeficientes, y la otra
aparte (R39-R44).

Correo de Juan Romero del 2026-09-29: el cierre de agosto de 12 obras daba una
venta final y un beneficio final inflados porque `final_master` sumaba
`importe_oficial` (el `impcoe` de Sigrid, con los coeficientes del contrato)
mientras el ejecutado y el coste van sin ellos. Decisión del humano (D6): cierre,
beneficio y análisis SIN coeficientes; la venta CON coeficientes (lo que se
factura) se publica ADEMÁS, en columnas propias, y nunca se mezcla con la otra.

Aserciones sobre el TEXTO del SQL de `cierre`, sin conexión.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pytest

from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG

SQL = DIRECTORIO_SQL_STG.parent


@lru_cache(maxsize=None)
def _leer(relativo: str) -> str:
    texto = (SQL / relativo).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return "\n".join(
        "" if linea.lstrip().startswith("--") else linea.split("--", 1)[0]
        for linea in texto.splitlines()
    )


def _entre(texto: str, inicio: str, fin: str) -> str:
    desde = texto.index(inicio)
    return texto[desde : texto.index(fin, desde)]


def _ramas(cte: str) -> list[str]:
    """Las ramas del UNION ALL de una CTE de `02_build_fact.sql`."""
    build = _leer("cierre/02_build_fact.sql")
    cuerpo = re.search(rf"\n{cte} AS \((.*?)\n\),", build, re.DOTALL).group(1)
    return cuerpo.split("UNION ALL")


def _rama_venta(cte: str) -> str:
    ramas = [r for r in _ramas(cte) if "'VENTA'" in r]
    assert len(ramas) == 1, cte
    return ramas[0]


# ---------------------------------------------------------------------------
# R39 · la venta final sin coeficientes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cte", ("final_master", "final_fase0"))
def test_f118_r39_fact_la_venta_final_suma_importe_sin_coeficientes(cte: str) -> None:
    rama = _rama_venta(cte)
    assert "SUM(pres.importe)::NUMERIC(18,2) AS final_importe" in rama, rama
    assert "importe_oficial) AS final_importe," not in rama
    assert not re.search(r"SUM\(pres\.importe_oficial\)[^\n]*AS final_importe\b(?!_)", rama)


def test_f118_r39_fact_el_coste_sigue_sin_coeficientes() -> None:
    for cte in ("final_master", "final_fase0"):
        for rama in _ramas(cte):
            if "'VENTA'" in rama:
                continue
            assert "importe_oficial" not in rama, rama


# ---------------------------------------------------------------------------
# R41 + D10 · la venta con coeficientes, aparte y solo del master
# ---------------------------------------------------------------------------


def test_f118_r41_ddl_final_importe_con_coeficientes() -> None:
    ddl = _entre(
        _leer("cierre/01_ddl_fact.sql"), "CREATE TABLE cierre.fact_cierre_mensual (", ");"
    )
    assert re.search(r"final_importe_con_coeficientes\s+NUMERIC\(18,2\)\s+NULL", ddl), ddl


def test_f118_r41_fact_la_con_coeficientes_sale_de_importe_oficial_del_master() -> None:
    rama = _rama_venta("final_master")
    assert (
        "SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe_con_coeficientes"
        in rama
    ), rama


def test_f118_r41_fact_el_coste_no_tiene_venta_con_coeficientes() -> None:
    for rama in _ramas("final_master"):
        if "'VENTA'" not in rama:
            assert "NULL::NUMERIC(18,2)" in rama, rama


def test_f118_d10_fact_el_respaldo_de_fase_0_no_publica_con_coeficientes() -> None:
    """D10: la venta real no guarda coeficientes; copiar la sin coeficientes
    diría que las dos son iguales. Con fuente `fase_0` o `sin_dato`, NULL."""
    assert "importe_oficial" not in "".join(_ramas("final_fase0"))
    build = _leer("cierre/02_build_fact.sql")
    combinado = _entre(build, "combinado AS (", "con_grupo AS (")
    assert re.search(
        r"fm\.final_importe_con_coeficientes\s*,", combinado
    ), combinado
    assert "ff.final_importe_con_coeficientes" not in build


def test_f118_r41_fact_el_insert_escribe_la_columna() -> None:
    build = _leer("cierre/02_build_fact.sql")
    insert = _entre(build, "INSERT INTO cierre.fact_cierre_mensual (", ")")
    assert "final_importe_con_coeficientes" in insert
    final = build[build.rindex("SELECT") :]
    assert "final_importe_con_coeficientes" in final


# ---------------------------------------------------------------------------
# R43 · ninguna columna con coeficientes entra en un cálculo
# ---------------------------------------------------------------------------

_OPERADOR = re.compile(r"[-+*/]|SUM\(|ROUND\(|COALESCE\(")


@pytest.mark.parametrize(
    "relativo",
    ("cierre/02_build_fact.sql", "cierre/03_views.sql", "cierre/05_views_cabecera.sql"),
)
def test_f118_r43_ninguna_columna_con_coeficientes_se_opera(relativo: str) -> None:
    """Ni beneficio, ni pendiente, ni %, ni restas con el ejecutado o el coste.

    Cada línea que nombra una columna con coeficientes es una columna pasada
    tal cual (o su origen, `SUM(pres.importe_oficial)` en `final_master`). Lo
    compruebo línea a línea: una suma o una resta en la misma línea es mezclar.
    """
    for linea in _leer(relativo).splitlines():
        if "con_coeficientes" not in linea:
            continue
        if "SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe_con_coeficientes" in linea:
            continue
        # Fuera los literales de texto (COMMENT ON ... 'F-118') y los casts.
        limpia = re.sub(r"'[^']*'", "''", re.sub(r"::NUMERIC\(18,2\)", "", linea))
        assert not _OPERADOR.search(limpia), f"{relativo}: {linea.strip()}"


def test_f118_r43_el_resumen_no_mete_la_con_coeficientes_en_gastos_ni_beneficio() -> None:
    vistas = _leer("cierre/03_views.sql")
    for cte, fin in (("gastos AS (", "beneficio AS ("), ("beneficio AS (", "venta_por_mes AS (")):
        cuerpo = _entre(vistas, cte, fin)
        assert "NULL::NUMERIC(18,2) AS final_importe_con_coeficientes" in cuerpo, cte
    venta = _entre(vistas, "venta_por_mes AS (", "aprobado_por_obra AS (")
    assert "con_coeficientes" not in venta


def test_f118_r43_los_porcentajes_no_usan_la_con_coeficientes() -> None:
    vistas = _leer("cierre/03_views.sql")
    final = vistas[vistas.rindex("SELECT") :]
    bloques = re.findall(r"\n    CASE.*?END\s+AS \w+_pct", final, re.DOTALL)
    assert len(bloques) == 6, len(bloques)
    for bloque in bloques:
        assert "con_coeficientes" not in bloque


# ---------------------------------------------------------------------------
# R42 · el resumen y la cabecera la publican (D11)
# ---------------------------------------------------------------------------


def test_f118_r42_el_resumen_publica_la_columna() -> None:
    vistas = _leer("cierre/03_views.sql")
    final = vistas[vistas.rindex("SELECT") :]
    assert "t.final_importe_con_coeficientes" in final
    base = _entre(vistas, "base AS (", "gastos AS (")
    assert "final_importe_con_coeficientes" in base


@pytest.mark.parametrize(
    "columna",
    (
        "presupuesto_inicial_venta_con_coeficientes",
        "presupuesto_vigente_venta_con_coeficientes",
    ),
)
def test_f118_r42_la_cabecera_publica_el_presupuesto_con_coeficientes(columna: str) -> None:
    cabecera = _leer("cierre/05_views_cabecera.sql")
    assert re.search(rf"\b{columna}\b", cabecera[cabecera.rindex("SELECT") :]), columna
    meses = _entre(cabecera, "venta_meses AS (", "venta_inicial AS (")
    assert "final_importe_con_coeficientes" in meses


def test_f118_r42_los_modificados_siguen_sin_coeficientes() -> None:
    cabecera = _leer("cierre/05_views_cabecera.sql")
    modificados = re.search(
        r"\(COALESCE\(vv\.presupuesto_vigente_venta, 0\)\s*- COALESCE\(vi\.presupuesto_inicial_venta, 0\)\)"
        r"::NUMERIC\(18,2\) AS modificados_aprobados",
        cabecera,
    )
    assert modificados, "modificados_aprobados tiene que seguir restando las dos SIN coeficientes"


# ---------------------------------------------------------------------------
# R44 · no se inventa nada: stg.presupuesto.importe_oficial no cambia
# ---------------------------------------------------------------------------


def test_f118_r44_importe_oficial_se_calcula_igual_que_hoy() -> None:
    presupuesto = _leer("stg/06_presupuesto.sql")
    assert re.search(
        r"NULLIF\(pp\.impcoe::NUMERIC\(18,2\), 0\)", presupuesto
    ), "importe_oficial = COALESCE(NULLIF(impcoe, 0), importe), como antes"
