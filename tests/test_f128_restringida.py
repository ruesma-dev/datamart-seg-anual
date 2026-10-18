# tests/test_f128_restringida.py
"""F-128 · R20-R23: la cuenta bancaria del proveedor, SOLO en `compras_restringida`.

D4-B (humano, 2026-10-17): la cuenta que lleva cada factura o albarán
(`ban`, `bancue`, `bandig`, `banban`, `bansuc`) se publica en
`compras_restringida.documento_cuenta_bancaria`, que solo lee el perfil total
del MCP. Estos tests fijan que no se escapa: ni otro fichero SQL la publica, ni
otro objeto la lee, ni cambian los permisos por esquema que la protegen, ni
entra en el repositorio un valor con forma de cuenta. Sin red ni BBDD.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etl_sigrid.domain import cabecera_compra as cc

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DOCUMENTOS = DIR_SQL / "compras" / "01_documentos.sql"
TABLA = "compras_restringida.documento_cuenta_bancaria"
INICIO = "-- >>> F-128 CUENTA BANCARIA (inicio)"
FIN = "-- <<< F-128 CUENTA BANCARIA (fin)"

COLUMNAS = [
    "documento_id", "tipo_documento", "codigo_documento", "fecha_documento",
    "proveedor_id", "proveedor_nombre", "banco_id", "banco", "sucursal_id",
    "sucursal", "digitos_control", "numero_cuenta", "cuenta_bancaria",
]


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _bloque() -> str:
    """La sección CUENTA BANCARIA de `01_documentos.sql`, entre sus marcas."""
    texto = _texto(DOCUMENTOS)
    assert INICIO in texto and FIN in texto, "faltan las marcas de la sección"
    return texto[texto.index(INICIO): texto.index(FIN) + len(FIN)]


def _fuera_del_bloque(ruta: Path) -> str:
    texto = _texto(ruta)
    if ruta == DOCUMENTOS and INICIO in texto:
        texto = texto[: texto.index(INICIO)] + texto[texto.index(FIN) + len(FIN):]
    return _sin_comentarios(texto)


def _sentencia() -> str:
    limpio = _sin_comentarios(_bloque())
    m = re.search(rf"CREATE TABLE {re.escape(TABLA)} AS\b(.*?);", limpio, re.S)
    assert m, "no está el CREATE TABLE"
    return m.group(1)


def _partir(texto: str) -> list[str]:
    partes, nivel, actual = [], 0, []
    for ch in texto:
        nivel += (ch == "(") - (ch == ")")
        if ch == "," and nivel == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(ch)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def _select_externo(sentencia: str) -> tuple[str, str]:
    """(CTE, SELECT de primer nivel) de `WITH ... AS (...) SELECT ...`."""
    nivel = 0
    for i, ch in enumerate(sentencia):
        nivel += (ch == "(") - (ch == ")")
        if nivel == 0 and sentencia.startswith("SELECT", i):
            return sentencia[:i], sentencia[i:]
    raise AssertionError("sin SELECT de primer nivel")


def _proyeccion() -> dict[str, str]:
    _, select = _select_externo(_sentencia())
    cuerpo = select[len("SELECT"): select.index("FROM doc d")]
    salida = {}
    for parte in _partir(cuerpo):
        m = re.search(r"^(.*)\bAS\s+(\w+)$", parte, re.S)
        assert m, parte
        salida[m.group(2)] = " ".join(m.group(1).split())
    return salida


# --- R20 · la tabla -------------------------------------------------------------

def test_f128_r20_columnas_en_orden():
    assert list(_proyeccion()) == COLUMNAS


def test_f128_r20_expresiones():
    p = _proyeccion()
    esperadas = {
        "documento_id": "d.ide",
        "tipo_documento": "d.tipo",
        "codigo_documento": "c.cod",
        "fecha_documento": "compras.fn_sigrid_date(d.fecdoc)",
        "proveedor_id": "NULLIF(d.entide, 0)",
        "proveedor_nombre": "prv.res",
        "banco_id": "NULLIF(d.banban, 0)",
        "banco": "bb.res",
        "sucursal_id": "NULLIF(d.bansuc, 0)",
        "sucursal": "bs.res",
        "digitos_control": "NULLIF(btrim(d.bandig), '')",
        "numero_cuenta": "NULLIF(btrim(d.bancue), '')",
        "cuenta_bancaria": "btrim(d.ban)",
    }
    assert p == esperadas


def test_f128_r20_universo_ban_informado_en_las_dos_ramas():
    cte, _ = _select_externo(_sentencia())
    plano = " ".join(cte.split())
    assert "FROM raw.dcf f WHERE NULLIF(btrim(f.ban), '') IS NOT NULL" in plano
    assert "FROM raw.dca a WHERE NULLIF(btrim(a.ban), '') IS NOT NULL" in plano
    assert "'FACTURA'" in plano and "'ALBARAN'" in plano
    assert "UNION ALL" in plano


def test_f128_r20_lee_solo_raw_y_sin_bantipide():
    s = _sentencia()
    origenes = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+\.\w+)", s))
    assert origenes == {"raw.dcf", "raw.dca", "raw.con", "raw.auxban"}
    assert "bantipide" not in s and "banide" not in s
    plano = " ".join(s.split())
    for join in (
        "LEFT JOIN raw.con c ON c.ide = d.ide",
        "LEFT JOIN raw.con prv ON prv.ide = NULLIF(d.entide, 0)",
        "LEFT JOIN raw.auxban bb ON bb.ide = NULLIF(d.banban, 0)",
        "LEFT JOIN raw.auxban bs ON bs.ide = NULLIF(d.bansuc, 0)",
    ):
        assert join in plano, join
    # Sin WHERE en el SELECT externo: el universo lo fija la CTE.
    _, select = _select_externo(s)
    assert " WHERE " not in " ".join(select.split())


def test_f128_r20_pk_indice_y_comment():
    bloque = _bloque()
    assert f"DROP TABLE IF EXISTS {TABLA} CASCADE;" in bloque
    assert re.search(rf"ALTER TABLE {re.escape(TABLA)} ADD PRIMARY KEY \(documento_id\);", bloque)
    assert re.search(rf"CREATE INDEX \w+ ON {re.escape(TABLA)} \(proveedor_id\);", bloque)
    m = re.search(rf"COMMENT ON TABLE {re.escape(TABLA)} IS\s*'(.*?)';", bloque, re.S)
    assert m and m.group(1).startswith("ACCESO RESTRINGIDO")


def test_f128_r20_es_la_ultima_seccion_del_fichero():
    texto = _texto(DOCUMENTOS)
    resto = _sin_comentarios(texto[texto.index(FIN) + len(FIN):])
    assert resto.strip() == ""
    creates = re.findall(r"CREATE TABLE (\w+\.\w+)", _sin_comentarios(texto))
    assert creates[-1] == TABLA


def test_f128_r20_inventario_igual_al_sql():
    """Lo que la tabla lee de cada rama es lo que el inventario le asigna."""
    cte, _ = _select_externo(_sentencia())
    ramas = cte.split("UNION ALL")
    assert len(ramas) == 2
    destino = TABLA
    for rama, alias, tabla in ((ramas[0], "f", "dcf"), (ramas[1], "a", "dca")):
        leidas = set(re.findall(rf"(?<![\w.]){alias}\.(\w+)", rama))
        assert leidas == cc.columnas_origen(cc.INVENTARIOS[tabla], destino), tabla


# --- R21 · nadie más la publica ni la lee -----------------------------------------

def infracciones(texto: str, nombre: str) -> list[str]:
    """Lo que un SQL (sin comentarios) hace mal con la cuenta del proveedor."""
    salida = []
    if re.search(r"(?<![\w])\w+\.(ban|bancue|bandig)\b", texto):
        salida.append(f"{nombre}: publica `ban`/`bancue`/`bandig` fuera de {TABLA}")
    for alias in re.findall(r"\braw\.dca\s+(?:AS\s+)?(\w+)", texto, re.I):
        if re.search(rf"(?<![\w.]){alias}\.(banban|bansuc)\b", texto):
            salida.append(f"{nombre}: publica `dca.banban`/`bansuc` fuera de {TABLA}")
    for m in re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:VIEW|TABLE)\s+(\w+)\.(\w+)", texto, re.I):
        fin = texto.find(";", m.end())
        cuerpo = texto[m.end(): fin if fin >= 0 else None]
        if TABLA in cuerpo and m.group(1) != "compras_restringida":
            salida.append(f"{nombre}: {m.group(1)}.{m.group(2)} lee {TABLA}")
    return salida


def test_f128_r21_barrido_de_todo_el_sql():
    malos = []
    for ruta in sorted(DIR_SQL.rglob("*.sql")):
        malos += infracciones(_fuera_del_bloque(ruta), ruta.relative_to(RAIZ).as_posix())
    assert malos == []


@pytest.mark.parametrize(
    "fabricado",
    [
        "CREATE TABLE compras.x AS SELECT f.ban AS cuenta FROM raw.dcf f;",
        "CREATE VIEW compras.y AS SELECT p.bancue FROM raw.pag p;",
        "CREATE TABLE compras.z AS SELECT d.bandig FROM raw.dcf d;",
        "CREATE TABLE compras.w AS SELECT a.banban AS banco FROM raw.dca a;",
        "CREATE TABLE compras.v AS SELECT x.bansuc FROM raw.dca AS x;",
        f"CREATE VIEW compras.u AS SELECT * FROM {TABLA};",
        f"CREATE TABLE retenciones.t AS SELECT 1 FROM {TABLA} c;",
    ],
)
def test_f128_r21_positivo_fabricado(fabricado):
    errores = infracciones(fabricado, "fabricado.sql")
    assert errores and "fabricado.sql" in errores[0]


def test_f128_r21_lo_permitido_no_salta():
    """El banco y la sucursal de la FACTURA en `v_facturas_pago` (F-080) y los
    de los efectos de `tesoreria` no son la cuenta: no saltan."""
    permitido = (
        "CREATE VIEW compras.v_facturas_pago AS SELECT bb.res FROM compras.facturas fa "
        "JOIN raw.dcf f ON f.ide = fa.factura_id "
        "LEFT JOIN raw.auxban bb ON bb.ide = NULLIF(f.banban, 0);"
        f"CREATE TABLE compras_restringida.otra AS SELECT * FROM {TABLA};"
    )
    assert infracciones(permitido, "permitido.sql") == []
