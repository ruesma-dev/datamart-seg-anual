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


# --- utilidades de lectura de una sentencia --------------------------------------

def _sentencia(sql: str, nombre: str, clase: str = "TABLE") -> str:
    """El texto, sin comentarios, de `CREATE <clase> <nombre> AS ... ;`."""
    limpio = _sin_comentarios(sql)
    m = re.search(rf"CREATE {clase} {re.escape(nombre)} AS\b(.*?);", limpio, re.S)
    assert m, f"no está CREATE {clase} {nombre}"
    return m.group(1)


def _partir(texto: str) -> list[str]:
    """Parte por las comas de primer nivel (fuera de paréntesis)."""
    partes, nivel, actual = [], 0, []
    for ch in texto:
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        if ch == "," and nivel == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(ch)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def _proyeccion(sentencia: str, desde: str, inicio: str = "SELECT") -> list[tuple[str, str]]:
    """[(expresión, alias)] entre el `inicio` y el `FROM <desde>` de primer nivel."""
    i = sentencia.index(inicio) + len(inicio)
    j = sentencia.index(f"FROM {desde}", i)
    salida = []
    for parte in _partir(sentencia[i:j]):
        m = re.search(r"^(.*)\bAS\s+([a-z_0-9]+)$", parte, re.S)
        assert m, f"columna sin alias: {parte!r}"
        salida.append((" ".join(m.group(1).split()), m.group(2)))
    return salida


def _columnas(sentencia: str, desde: str, inicio: str = "SELECT") -> list[str]:
    return [a for _, a in _proyeccion(sentencia, desde, inicio)]


def _expresion(sentencia: str, desde: str, alias: str, inicio: str = "SELECT") -> str:
    for expr, a in _proyeccion(sentencia, desde, inicio):
        if a == alias:
            return expr
    raise AssertionError(f"no está la columna {alias}")


# --- R12-R13 · los recargos de cada documento -------------------------------------

COLUMNAS_RECARGOS = [
    "recargo_id", "{doc}_id", "posicion", "concepto_id", "codigo_concepto", "concepto",
    "clase_recargo", "es_retencion_garantia", "base", "porcentaje", "cuota",
    "cuota_iva", "valor_fijo", "cuenta_id", "cuenta_contable",
]

RECARGOS = [
    ("compras.factura_recargos", "factura", "raw.dcfrec r", "raw.dcf f", "f"),
    ("compras.albaran_recargos", "albaran", "raw.dcarec r", "raw.dca a", "a"),
]


@pytest.mark.parametrize(("tabla", "doc", "desde", "cabecera", "alias"), RECARGOS)
def test_f128_r12_r13_recargos_columnas_y_origen(tabla, doc, desde, cabecera, alias):
    s = _sentencia(_texto(DOCUMENTOS), tabla)
    assert _columnas(s, desde) == [c.format(doc=doc) for c in COLUMNAS_RECARGOS]
    assert _expresion(s, desde, "recargo_id") == "r.ide"
    assert _expresion(s, desde, f"{doc}_id") == "r.docide"
    assert _expresion(s, desde, "posicion") == "r.pos"
    assert _expresion(s, desde, "concepto_id") == "NULLIF(r.recide, 0)"
    assert _expresion(s, desde, "codigo_concepto") == "x.cod"
    assert _expresion(s, desde, "concepto") == "x.res"
    assert _expresion(s, desde, "clase_recargo") == "compras.fn_clase_recargo(r.reccla)"
    assert (
        _expresion(s, desde, "es_retencion_garantia")
        == "compras.fn_es_retencion_garantia(r.reccla)"
    )
    assert _expresion(s, desde, "porcentaje") == "ROUND((r.valpor * 100)::NUMERIC, 4)"
    assert _expresion(s, desde, "base") == "COALESCE(r.bas, 0)::NUMERIC(18, 2)"
    assert _expresion(s, desde, "cuota") == "COALESCE(r.cuo, 0)::NUMERIC(18, 2)"
    assert _expresion(s, desde, "cuota_iva") == "COALESCE(r.ivacuo, 0)::NUMERIC(18, 2)"
    assert _expresion(s, desde, "valor_fijo") == "COALESCE(r.valfij <> 0, FALSE)"
    assert _expresion(s, desde, "cuenta_id") == "NULLIF(r.cueide, 0)"
    assert _expresion(s, desde, "cuenta_contable") == "cue.cod"
    resto = " ".join(s[s.index(f"FROM {desde}"):].split())
    assert "LEFT JOIN raw.con x ON x.ide = r.recide" in resto
    assert "LEFT JOIN raw.con cue ON cue.ide = NULLIF(r.cueide, 0)" in resto
    assert (
        f"WHERE EXISTS (SELECT 1 FROM {cabecera} WHERE {alias}.ide = r.docide)" in resto
    )
    # Solo LEFT JOIN: ningún recargo se pierde por un concepto sin ficha.
    assert not re.search(r"(?<!LEFT )JOIN raw", resto)


@pytest.mark.parametrize(("tabla", "doc", "desde", "cabecera", "alias"), RECARGOS)
def test_f128_r12_r13_recargos_pk_indices_y_drop(tabla, doc, desde, cabecera, alias):
    sql = _texto(DOCUMENTOS)
    assert f"DROP TABLE IF EXISTS {tabla} CASCADE;" in sql
    assert re.search(rf"ALTER TABLE {re.escape(tabla)} ADD PRIMARY KEY \(recargo_id\);", sql)
    assert re.search(rf"CREATE INDEX \w+ ON {re.escape(tabla)} \({doc}_id\);", sql)
    assert re.search(
        rf"CREATE INDEX \w+ ON {re.escape(tabla)} \(es_retencion_garantia\);", sql
    )


def test_f128_r12_r13_recargos_antes_que_los_documentos():
    """Los recargos se construyen ANTES que albaranes y facturas, que los agregan."""
    sql = _sin_comentarios(_texto(DOCUMENTOS))
    alb = sql.index("CREATE TABLE compras.albaranes AS")
    fac = sql.index("CREATE TABLE compras.facturas AS")
    for tabla, *_ in RECARGOS:
        assert sql.index(f"CREATE TABLE {tabla} AS") < min(alb, fac)


def test_f128_r12_cabecera_del_fichero_explica_f128():
    cabecera = _texto(DOCUMENTOS).split("-- CONTRATOS")[0]
    assert "F-128" in cabecera
    for frase in ("totdoc", "totpag", "D2-B", "RETESP", "compras_restringida"):
        assert frase in cabecera, frase
