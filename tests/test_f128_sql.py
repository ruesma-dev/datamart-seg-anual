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


# --- R6-R11 · la cabecera de albaranes y facturas ---------------------------------

def _nivel_cero(texto: str) -> str:
    """El texto sin lo que va entre paréntesis (subconsultas, FILTER, llamadas)."""
    salida, nivel = [], 0
    for ch in texto:
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        elif nivel == 0:
            salida.append(ch)
    return "".join(salida)


def _tras_el_from(sentencia: str, desde: str) -> str:
    return " ".join(sentencia[sentencia.index(f"FROM {desde}"):].split())


IMPORTES = [
    ("importe_bruto", "impbru"),
    ("importe_neto", "impnet"),
    ("importe_descuentos", "impdes"),
    ("importe_recargos", "imprec"),
    ("base_imponible", "totbas"),
    ("cuota_iva", "totiva"),
    ("{total}", "totdoc"),
]

ALBARANES_DE_SIEMPRE = [
    "albaran_id", "codigo_albaran", "serie", "tipo_documento", "descripcion", "fecha",
    "contrato_id", "comparativo_id", "proveedor_id", "proveedor_nombre", "proveedor_cif",
    "referencia_proveedor",
]

IMPORTES_NUEVOS = [
    "importe_bruto", "importe_neto", "importe_descuentos", "importe_recargos",
    "base_imponible", "cuota_iva", "{total}", "importe_retenciones",
    "importe_retencion_garantia", "importe_retencion_fiscal", "total_a_pagar",
]

OBRA_CENTRO = [
    "obra_cabecera_id", "codigo_obra_cabecera", "nombre_obra_cabecera",
    "centro_coste_cabecera_id", "codigo_centro_coste_cabecera",
    "nombre_centro_coste_cabecera",
]

PROVEEDOR = [
    "proveedor_codigo", "proveedor_nombre_documento", "proveedor_tipo_identificacion",
    "proveedor_pais_identificacion",
]

ALBARANES_NUEVAS = (
    [c.format(total="total_documento") for c in IMPORTES_NUEVOS]
    + ["fecha_documento", "forma_pago_id", "forma_pago", "medio_pago_id", "medio_pago",
       "cuenta_contable"]
    + OBRA_CENTRO
    + ["cuenta_analitica_cabecera_id"]
    + PROVEEDOR
    + ["iva_diferido", "fecha_entrega_prevista", "fecha_limite", "facturado_sigrid",
       "fecha_facturacion", "factura_cabecera_id"]
)


def _albaranes() -> str:
    return _sentencia(_texto(DOCUMENTOS), "compras.albaranes")


def test_f128_r10_albaranes_prefijo_intacto_y_nuevas_en_orden():
    columnas = _columnas(_albaranes(), "raw.dca a")
    assert len(ALBARANES_NUEVAS) == 34
    assert columnas == ALBARANES_DE_SIEMPRE + ALBARANES_NUEVAS


def _comprobar_importes(s: str, desde: str, a: str, total: str, recargos: str) -> None:
    for alias, origen in IMPORTES:
        alias = alias.format(total=total)
        assert _expresion(s, desde, alias) == f"COALESCE({a}.{origen}, 0)::NUMERIC(18, 2)"
    assert (
        _expresion(s, desde, "total_a_pagar") == f"COALESCE({a}.totpag, 0)::NUMERIC(18, 2)"
    )
    assert _expresion(s, desde, "importe_retenciones") == (
        f"(COALESCE({a}.totdoc, 0) - COALESCE({a}.totpag, 0))::NUMERIC(18, 2)"
    )
    assert (
        _expresion(s, desde, "importe_retencion_garantia")
        == "COALESCE(rec.garantia, 0)::NUMERIC(18, 2)"
    )
    assert (
        _expresion(s, desde, "importe_retencion_fiscal")
        == "COALESCE(rec.fiscal, 0)::NUMERIC(18, 2)"
    )
    # `tot` NO se publica: es `totpag` en el 100 %.
    assert not re.search(rf"\b{a}\.tot\b", s)
    # R7 · el agregado previo POR DOCUMENTO, antes de unirse (guarda de grano).
    resto = _tras_el_from(s, desde)
    m = re.search(
        r"LEFT JOIN \( SELECT (\w+), SUM\(cuota\) FILTER \(WHERE es_retencion_garantia\) "
        r"AS garantia, SUM\(cuota\) FILTER \(WHERE clase_recargo = 'RETENCION_FISCAL'\) "
        rf"AS fiscal FROM {re.escape(recargos)} GROUP BY (\w+) \) rec ON rec\.(\w+) = {a}\.ide",
        resto.replace("(SELECT", "( SELECT").replace("albaran_id)", "albaran_id )")
        .replace("factura_id)", "factura_id )"),
    )
    assert m, resto
    assert m.group(1) == m.group(2) == m.group(3)


def test_f128_r6_r7_albaranes_importes_y_agregado_previo():
    _comprobar_importes(
        _albaranes(), "raw.dca a", "a", "total_documento", "compras.albaran_recargos"
    )


def _comprobar_cabecera_comun(s: str, desde: str, a: str) -> None:
    """R8: ids con 0 a NULL, nombres de `raw.con`, textos vacíos a NULL, fechas
    con `fn_sigrid_date`, booleanos nunca NULL."""
    esperadas = {
        "obra_cabecera_id": f"NULLIF({a}.obride, 0)",
        "codigo_obra_cabecera": "obr.cod",
        "nombre_obra_cabecera": "obr.res",
        "centro_coste_cabecera_id": f"NULLIF({a}.cenide, 0)",
        "codigo_centro_coste_cabecera": "cen.cod",
        "nombre_centro_coste_cabecera": "cen.res",
        "cuenta_analitica_cabecera_id": f"NULLIF({a}.caaide, 0)",
        "proveedor_codigo": f"NULLIF(btrim({a}.entcod), '')",
        "proveedor_nombre_documento": f"NULLIF(btrim({a}.entres), '')",
        "proveedor_tipo_identificacion": f"NULLIF(btrim({a}.entciftip), '')",
        "proveedor_pais_identificacion": f"NULLIF(btrim({a}.entcifpai), '')",
        "iva_diferido": f"COALESCE({a}.ivadif <> 0, FALSE)",
        "fecha_entrega_prevista": f"compras.fn_sigrid_date({a}.fecent)",
        "fecha_limite": f"compras.fn_sigrid_date({a}.feclim)",
    }
    for alias, expr in esperadas.items():
        assert _expresion(s, desde, alias) == expr, alias
    resto = _tras_el_from(s, desde)
    assert f"LEFT JOIN raw.con obr ON obr.ide = NULLIF({a}.obride, 0)" in resto
    assert f"LEFT JOIN raw.con cen ON cen.ide = NULLIF({a}.cenide, 0)" in resto


def test_f128_r8_albaranes_cabecera():
    _comprobar_cabecera_comun(_albaranes(), "raw.dca a", "a")


def test_f128_r11_albaranes_pago_cuenta_y_facturacion():
    s = _albaranes()
    esperadas = {
        "fecha_documento": "compras.fn_sigrid_date(a.fecdoc)",
        "forma_pago_id": "NULLIF(a.pagide, 0)",
        "forma_pago": "pag.res",
        "medio_pago_id": "NULLIF(a.efeide, 0)",
        "medio_pago": "efp.res",
        "cuenta_contable": "cue.cod",
        "facturado_sigrid": "COALESCE(a.estfac = 1, FALSE)",
        "fecha_facturacion": "compras.fn_sigrid_date(a.fecfac)",
        "factura_cabecera_id": "NULLIF(a.idefac, 0)",
    }
    for alias, expr in esperadas.items():
        assert _expresion(s, "raw.dca a", alias) == expr, alias
    resto = _tras_el_from(s, "raw.dca a")
    assert "LEFT JOIN raw.auxpag pag ON pag.ide = NULLIF(a.pagide, 0)" in resto
    assert "LEFT JOIN raw.auxefp efp ON efp.ide = NULLIF(a.efeide, 0)" in resto
    assert "LEFT JOIN raw.con cue ON cue.ide = NULLIF(a.cueide, 0)" in resto


def _comprobar_grano(s: str, desde: str, a: str) -> None:
    """R9/R11: sin `WHERE` externo y, aparte del `JOIN raw.con con` de siempre,
    solo `LEFT JOIN`."""
    resto = _nivel_cero(_tras_el_from(s, desde))
    assert " WHERE " not in f" {resto} ", resto
    internos = re.findall(r"(?<!LEFT) JOIN (\S+ \S+)", resto)
    assert internos == ["raw.con con"], internos


def test_f128_r11_albaranes_grano_sin_where_externo():
    _comprobar_grano(_albaranes(), "raw.dca a", "a")


def test_f128_r10_albaranes_sin_datos_bancarios():
    assert not re.search(r"\ba\.ban\w*", _albaranes())


FACTURAS_DE_SIEMPRE = [
    "factura_id", "codigo_factura", "serie", "tipo_documento", "descripcion", "fecha",
    "proveedor_id", "proveedor_nombre", "proveedor_cif", "referencia_proveedor",
    "estado_id", "estado_codigo", "estado", "fecha_factura", "fecha_alta",
]

FACTURAS_NUEVAS = (
    [c.format(total="total_factura") for c in IMPORTES_NUEVOS]
    + ["contrato_id"]
    + OBRA_CENTRO
    + ["cuenta_analitica_cabecera_id"]
    + PROVEEDOR
    + ["iva_diferido", "inversion_sujeto_pasivo", "fecha_entrega_prevista", "fecha_limite"]
)


def _facturas() -> str:
    return _sentencia(_texto(DOCUMENTOS), "compras.facturas")


def test_f128_r5_facturas_prefijo_intacto_y_nuevas_en_orden():
    assert len(FACTURAS_NUEVAS) == 27
    assert _columnas(_facturas(), "raw.dcf f") == FACTURAS_DE_SIEMPRE + FACTURAS_NUEVAS


def test_f128_r6_r7_facturas_importes_y_agregado_previo():
    _comprobar_importes(
        _facturas(), "raw.dcf f", "f", "total_factura", "compras.factura_recargos"
    )


def test_f128_r8_facturas_cabecera():
    s = _facturas()
    _comprobar_cabecera_comun(s, "raw.dcf f", "f")
    assert _expresion(s, "raw.dcf f", "contrato_id") == "NULLIF(f.ctride, 0)"
    assert (
        _expresion(s, "raw.dcf f", "inversion_sujeto_pasivo")
        == "COALESCE(f.tipisp <> 0, FALSE)"
    )


def test_f128_r9_facturas_grano_y_joins_tras_el_lateral():
    s = _facturas()
    _comprobar_grano(s, "raw.dcf f", "f")
    resto = _tras_el_from(s, "raw.dcf f")
    lateral = resto.index("LEFT JOIN LATERAL compras.fn_estado_documento(15, con.est) est ON TRUE")
    for nuevo in ("raw.con obr", "raw.con cen", "compras.factura_recargos"):
        assert resto.index(nuevo) > lateral, nuevo
    # El lateral del estado sigue siendo el PRIMERO (lo lee `test_f083_sql`).
    assert resto.index("LATERAL") == lateral + len("LEFT JOIN ")


def _origen_en_sql(sentencia: str, alias: str) -> set[str]:
    return set(re.findall(rf"(?<![\w.]){alias}\.(\w+)", sentencia))


@pytest.mark.parametrize(
    ("tabla", "objeto", "sentencia", "desde", "alias"),
    [
        ("dcf", "compras.facturas", _facturas, "raw.dcf f", "f"),
        ("dca", "compras.albaranes", _albaranes, "raw.dca a", "a"),
    ],
)
def test_f128_r3_inventario_igual_al_sql(tabla, objeto, sentencia, desde, alias):
    """Lo que el SQL lee de la cabecera es EXACTAMENTE lo que el inventario
    declara publicado en ese objeto, y cada ruta es una columna del SQL."""
    s = sentencia()
    inventario = cc.INVENTARIOS[tabla]
    assert _origen_en_sql(s, alias) == cc.columnas_origen(inventario, objeto)
    columnas = _columnas(s, desde)
    assert set(cc.publicadas(inventario, objeto)) <= set(columnas)


def test_f128_r3_v_facturas_pago_rutas_existen():
    """Las rutas a `v_facturas_pago` (F-080, no se toca) son columnas suyas."""
    texto = _sin_comentarios(_texto(SQL / "compras" / "06_pago_factura.sql"))
    for columna in cc.publicadas(cc.INVENTARIO_DCF, "compras.v_facturas_pago"):
        assert re.search(rf"\bAS {columna}\b", texto), columna


@pytest.mark.parametrize("sentencia", [_facturas, _albaranes])
def test_f128_r32_ni_empide_ni_hor_ni_desajuste(sentencia):
    s = sentencia()
    assert not re.search(r"(?<![\w.])[af]\.(empide|hor)\b", s)
    assert not re.search(r"desajuste|diferencia_lineas|lineas_vs_cabecera", s)
