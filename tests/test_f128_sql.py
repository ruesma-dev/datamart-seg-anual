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


# --- R15-R19 · el cuadre de la retención de garantía por factura -----------------

COLUMNAS_RETENCION_FACTURA = [
    "factura_id", "codigo_factura", "fecha_alta", "fecha_factura", "proveedor_id",
    "proveedor_nombre", "obra_id", "empresa_id", "codigo_obra", "clave_obra",
    "nombre_obra", "retencion_factura", "retencion_contable", "diferencia_contable",
    "efectos_generados", "efectos_vivos", "diferencia_efectos", "categoria_contable",
    "categoria_efectos",
]

COLUMNAS_CUADRE_OBRA = [
    "proveedor_id", "proveedor_nombre", "obra_id", "empresa_id", "codigo_obra",
    "clave_obra", "nombre_obra", "retencion_facturas", "altas_contables", "diferencia",
    "num_facturas", "num_facturas_descuadre", "categoria",
]


def _select_externo(sentencia: str) -> tuple[str, str]:
    """(CTE, SELECT de primer nivel) de `WITH ... SELECT ...`."""
    nivel = 0
    for i, ch in enumerate(sentencia):
        nivel += (ch == "(") - (ch == ")")
        if nivel == 0 and sentencia.startswith("SELECT", i) and i > 0:
            return sentencia[:i], sentencia[i:]
    raise AssertionError("sin SELECT de primer nivel")


def _retencion_factura() -> tuple[str, str]:
    return _select_externo(_sentencia(_texto(CUADRE), "retenciones.retencion_factura"))


def _cuadre_obra() -> tuple[str, str]:
    return _select_externo(
        _sentencia(_texto(CUADRE), "retenciones.v_cuadre_factura_obra", "VIEW")
    )


def _cte(cte: str, nombre: str) -> str:
    """El cuerpo de la CTE `nombre AS ( ... )`, en una línea."""
    m = re.search(rf"\b{nombre} AS \(", cte)
    assert m, f"no está la CTE {nombre}"
    nivel, i = 1, m.end()
    while nivel:
        nivel += (cte[i] == "(") - (cte[i] == ")")
        i += 1
    return " ".join(cte[m.end(): i - 1].split())


def test_f128_r19_funcion_copiada_de_compras():
    _, cab_c, cuerpo_c = _funcion(_texto(SETUP_COMPRAS), "compras.fn_es_retencion_garantia")
    params, cab_r, cuerpo_r = _funcion(
        _texto(SETUP_RETENCIONES), "retenciones.fn_es_retencion_garantia"
    )
    assert params == "reccla INT"
    assert " ".join(cuerpo_r.split()) == " ".join(cuerpo_c.split())
    assert " ".join(cab_r.split()) == " ".join(cab_c.split())
    assert re.search(
        r"COMMENT ON FUNCTION retenciones\.fn_es_retencion_garantia\(INT\) IS",
        _texto(SETUP_RETENCIONES),
    )


def test_f128_r15_retencion_factura_columnas():
    _, select = _retencion_factura()
    assert _columnas(select, "universo u") == COLUMNAS_RETENCION_FACTURA


def test_f128_r15_lee_solo_raw_y_retenciones():
    texto = _sin_comentarios(_texto(CUADRE))
    sin_literales = re.sub(r"'[^']*'", "''", texto)
    origenes = set(re.findall(r"(?<!DISTINCT )\b(?:FROM|JOIN)\s+(\w+)\.\w+", sin_literales))
    assert origenes == {"raw", "retenciones"}, origenes
    leidas = set(re.findall(r"(?<!DISTINCT )\b(?:FROM|JOIN)\s+(\w+\.\w+)", sin_literales))
    assert leidas == {
        "raw.dcfrec", "raw.dcf", "raw.con", "retenciones.apuntes_contables",
        "retenciones.movimientos", "retenciones.saldo_contable",
        "retenciones.retencion_factura",
    }, leidas
    assert "compras." not in sin_literales


def test_f128_r15_universo_y_garantia_agregada_antes_de_unir():
    cte, select = _retencion_factura()
    garantia = _cte(cte, "garantia")
    assert "FROM raw.dcfrec r" in garantia
    assert "WHERE retenciones.fn_es_retencion_garantia(r.reccla)" in garantia
    assert "GROUP BY r.docide" in garantia
    universo = _cte(cte, "universo")
    assert "FROM garantia WHERE ABS(retencion) >= 0.01" in universo
    assert "UNION SELECT documento_id FROM contable" in universo
    resto = _tras_el_from(select, "universo u")
    assert "JOIN raw.dcf f ON f.ide = u.factura_id" in resto
    assert "JOIN raw.con c ON c.ide = f.ide" in resto
    assert "LEFT JOIN raw.con ob ON ob.ide = NULLIF(f.obride, 0)" in resto
    assert " WHERE " not in f" {_nivel_cero(resto)} "


def test_f128_r16_lados_del_cuadre():
    cte, select = _retencion_factura()
    contable = _cte(cte, "contable")
    assert "FROM retenciones.apuntes_contables" in contable
    assert "clase IN ('ALTA', 'BAJA')" in contable
    assert "documento_id IS NOT NULL" in contable and "GROUP BY documento_id" in contable
    efectos = _cte(cte, "efectos")
    assert "FROM retenciones.movimientos" in efectos
    assert "sentido = 'PROVEEDOR'" in efectos
    assert "FILTER (WHERE estado <> 'BAJA' OR estado_sigrid = 14) AS generados" in efectos
    assert "FILTER (WHERE estado = 'VIVA') AS vivos" in efectos
    e = {a: x for x, a in _proyeccion(select, "universo u")}
    assert e["retencion_factura"] == "COALESCE(g.retencion, 0)::NUMERIC(18, 2)"
    assert e["retencion_contable"] == "ct.importe::NUMERIC(18, 2)"
    assert e["diferencia_contable"] == "(COALESCE(g.retencion, 0) - ct.importe)::NUMERIC(18, 2)"
    assert e["efectos_generados"] == "e.generados::NUMERIC(18, 2)"
    assert e["efectos_vivos"] == "e.vivos::NUMERIC(18, 2)"
    assert e["diferencia_efectos"] == "(COALESCE(g.retencion, 0) - e.generados)::NUMERIC(18, 2)"
    assert e["obra_id"] == "NULLIF(f.obride, 0)"
    assert e["empresa_id"] == "ob.emp"
    assert e["clave_obra"] == "ob.emp::text || '-' || ob.cod"


def _literales_case(expr: str) -> list[str]:
    return re.findall(r"(?:THEN|ELSE) '([A-Z_]+)'", expr)


def test_f128_r17_categorias_en_orden():
    _, select = _retencion_factura()
    e = {a: x for x, a in _proyeccion(select, "universo u")}
    contable = e["categoria_contable"]
    assert _literales_case(contable) == ["SOLO_CONTABLE", "SIN_APUNTE", "CUADRA", "DIFIERE"]
    assert "WHEN ABS(COALESCE(g.retencion, 0)) < 0.01 THEN 'SOLO_CONTABLE'" in contable
    assert "WHEN ct.importe IS NULL THEN 'SIN_APUNTE'" in contable
    assert "WHEN ABS(COALESCE(g.retencion, 0) - ct.importe) < 0.01 THEN 'CUADRA'" in contable
    efectos = e["categoria_efectos"]
    assert _literales_case(efectos) == ["SIN_EFECTOS", "CUADRA", "DIFIERE"]
    assert "WHEN e.generados IS NULL THEN 'SIN_EFECTOS'" in efectos
    assert "WHEN ABS(COALESCE(g.retencion, 0) - e.generados) < 0.01 THEN 'CUADRA'" in efectos


def test_f128_r15_pk_indices_y_comment():
    sql = _texto(CUADRE)
    assert "DROP TABLE IF EXISTS retenciones.retencion_factura CASCADE;" in sql
    assert "ALTER TABLE retenciones.retencion_factura ADD PRIMARY KEY (factura_id);" in sql
    assert re.search(r"CREATE INDEX \w+ ON retenciones\.retencion_factura \(proveedor_id\);", sql)
    assert re.search(r"CREATE INDEX \w+ ON retenciones\.retencion_factura \(obra_id\);", sql)
    assert "COMMENT ON TABLE retenciones.retencion_factura IS" in sql
    assert "DROP VIEW IF EXISTS retenciones.v_cuadre_factura_obra CASCADE;" in sql
    assert "COMMENT ON VIEW retenciones.v_cuadre_factura_obra IS" in sql


def test_f128_r18_cuadre_por_proveedor_y_obra():
    cte, select = _cuadre_obra()
    assert _columnas(select, "x") == COLUMNAS_CUADRE_OBRA
    plano = " ".join(cte.split())
    assert "FROM retenciones.retencion_factura" in plano
    assert "GROUP BY proveedor_id, obra_id" in plano
    assert (
        "FULL JOIN retenciones.saldo_contable c ON c.proveedor_id = f.proveedor_id "
        "AND c.obra_id IS NOT DISTINCT FROM f.obra_id"
    ) in plano
    assert (
        "COUNT(*) FILTER (WHERE categoria_contable <> 'CUADRA') AS num_facturas_descuadre"
        in plano
    )
    assert "COALESCE(c.altas, 0)::NUMERIC(18, 2) AS altas_contables" in plano
    e = {a: x for x, a in _proyeccion(select, "x")}
    assert _literales_case(e["categoria"]) == [
        "CUADRA", "SOLO_FACTURAS", "SOLO_CONTABILIDAD", "FACTURAS_MAYOR", "CONTABILIDAD_MAYOR",
    ]
    assert (
        "WHEN ABS(x.retencion_facturas - x.altas_contables) < 1 THEN 'CUADRA'" in e["categoria"]
    )
    assert e["diferencia"] == "(x.retencion_facturas - x.altas_contables)::NUMERIC(18, 2)"
    resto = _tras_el_from(select, "x")
    assert resto.endswith(
        "WHERE ABS(x.retencion_facturas) >= 1 OR ABS(x.altas_contables) >= 1"
    ), resto


def test_f128_r18_r22_la_vista_lee_solo_retenciones():
    """Para `filtraciones_restringido` (F-141): la única vista nueva no alcanza
    ningún esquema ajeno al perfil restringido."""
    cuerpo = _sentencia(_texto(CUADRE), "retenciones.v_cuadre_factura_obra", "VIEW")
    leidos = set(re.findall(r"(?<!DISTINCT )\b(?:FROM|JOIN)\s+(\w+)\.\w+", cuerpo))
    assert leidos == {"retenciones"}, leidos


# --- R24 · los pasos ETL --------------------------------------------------------

def test_f128_r24_cuadre_factura_es_el_ultimo_sub_paso_de_retenciones():
    from etl_sigrid.application.steps import build_retenciones_step as paso

    ultimo = paso.SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file, ultimo.target_schema, ultimo.target_table) == (
        "cuadre_factura", "07_cuadre_factura.sql", "retenciones", "retencion_factura"
    )
    assert "07_cuadre_factura.sql" in (paso.__doc__ or "")
    assert (SQL / "retenciones" / ultimo.sql_file).is_file()


def test_f128_r24_compras_sin_sub_paso_nuevo():
    """Los recargos y la cuenta bancaria los deja `01_documentos.sql`, sin sub-paso
    nuevo: `documentos` sigue contando `contratos`."""
    from etl_sigrid.application.steps import build_compras_step as paso

    ficheros = [s.sql_file for s in paso.SUB_PASOS]
    assert ficheros.count("01_documentos.sql") == 1
    documentos = next(s for s in paso.SUB_PASOS if s.name == "documentos")
    assert (documentos.target_schema, documentos.target_table) == ("compras", "contratos")


def test_f128_r24_docstring_de_build_retenciones_en_main():
    import main

    assert "07_cuadre_factura.sql" in (main.build_retenciones.callback.__doc__ or "")
