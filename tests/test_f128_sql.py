# tests/test_f128_sql.py
"""F-128 · el SQL de la cabecera, los recargos y el cuadre de retenciones.

Sobre el TEXTO del SQL: no se ejecuta (el Postgres es compartido y los tests
de humo no tocan BBDD). Lo que aquí se fija es lo que el SQL promete y que un
cambio descuidado rompería sin que el build lo note: el orden de las columnas
de dos tablas vivas, la expresión de cada importe, la agregación previa que
protege el grano y que las funciones llevan el mismo `CASE` que el dominio.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etl_sigrid.domain import cabecera_compra as cc

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
SETUP_COMPRAS = SQL / "compras" / "00_setup.sql"
DOCUMENTOS = SQL / "compras" / "01_documentos.sql"
SETUP_RETENCIONES = SQL / "retenciones" / "00_setup.sql"
CUADRE = SQL / "retenciones" / "07_cuadre_factura.sql"


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _funcion(sql: str, nombre: str) -> tuple[str, str, str]:
    """(parámetros, cabecera, cuerpo) de `CREATE OR REPLACE FUNCTION <nombre>`."""
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(nombre)}\s*\(([^)]*)\)(.*?)\$\$(.*?)\$\$",
        sql,
        re.S,
    )
    assert m, f"no está la función {nombre}"
    return m.group(1).strip(), m.group(2), m.group(3)


# --- R14 · las funciones de `compras` llevan el CASE del dominio ----------------

def test_f128_r14_fn_clase_recargo_es_el_dominio():
    params, cabecera, cuerpo = _funcion(_texto(SETUP_COMPRAS), "compras.fn_clase_recargo")
    assert params == "reccla INT"
    assert "RETURNS TEXT" in cabecera
    assert "IMMUTABLE" in cabecera and "LANGUAGE sql" in cabecera
    pares = {int(n): lit for n, lit in re.findall(r"WHEN (\d+) THEN '([A-Z_]+)'", cuerpo)}
    assert pares == cc.CLASES_RECARGO
    assert re.search(r"ELSE 'OTRA'", cuerpo)


def test_f128_r14_fn_es_retencion_garantia_es_d2b():
    sql = _texto(SETUP_COMPRAS)
    params, cabecera, cuerpo = _funcion(sql, "compras.fn_es_retencion_garantia")
    # UN parámetro (D2-B): no recibe el código del concepto.
    assert params == "reccla INT"
    assert "RETURNS BOOLEAN" in cabecera and "IMMUTABLE" in cabecera
    m = re.search(r"COALESCE\(reccla IN \(([\d, ]+)\), FALSE\)", cuerpo)
    assert m, cuerpo
    assert {int(x) for x in m.group(1).split(",")} == set(cc.CLASES_GARANTIA)
    comentario = re.search(
        r"COMMENT ON FUNCTION compras\.fn_es_retencion_garantia\(INT\) IS\s*'(.*?)';",
        sql,
        re.S,
    )
    assert comentario and "RETESP" in comentario.group(1)


def test_f128_r14_casos_del_dominio_reproducidos_por_el_case():
    """El CASE leído del SQL, aplicado a mano, da lo mismo que el dominio."""
    _, _, cuerpo = _funcion(_texto(SETUP_COMPRAS), "compras.fn_clase_recargo")
    pares = {int(n): lit for n, lit in re.findall(r"WHEN (\d+) THEN '([A-Z_]+)'", cuerpo)}
    for reccla in (None, -1, 0, 1, 2, 3, 4, 5, 6):
        assert pares.get(reccla, "OTRA") == cc.clase_recargo(reccla)
