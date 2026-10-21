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
import subprocess
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
        "codigo_documento": "dcon.cod",
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
        "LEFT JOIN raw.con dcon ON dcon.ide = d.ide",
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


# --- R22 · los permisos por esquema la protegen sin tocar nada ----------------------

ESQUEMA = "compras_restringida"


def test_f128_r22_defectos_de_settings():
    from config.settings import (
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_TOTAL_VETOED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
        PostgresSettings,
    )

    assert ESQUEMA in DEFAULT_VETOED_SCHEMAS.split(","), "vetada al estándar"
    assert ESQUEMA in DEFAULT_RESTRICTED_SCHEMAS.split(","), "concedida al autorizado"
    assert ESQUEMA not in DEFAULT_TOTAL_VETOED_SCHEMAS.split(","), "el total SÍ la lee"
    assert ESQUEMA not in DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS.split(","), (
        "el perfil restringido (F-141) NO la lee"
    )
    pg = PostgresSettings(_env_file=None)
    assert ESQUEMA in pg.vetoed_schema_list
    assert ESQUEMA in pg.restricted_schema_list
    assert ESQUEMA not in pg.total_vetoed_schema_list
    assert ESQUEMA not in pg.perfil_restringido_schema_list


def test_f128_r22_grants_y_roles_no_nombran_la_tabla():
    """Los permisos van POR ESQUEMA: ni `grants.py` ni `02_roles.sql` tienen
    que saber que la tabla existe."""
    for ruta in (
        RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "grants.py",
        RAIZ / "infra" / "sql" / "02_roles.sql",
        RAIZ / "config" / "settings.py",
    ):
        assert "documento_cuenta_bancaria" not in _texto(ruta), ruta.name


def test_f128_r22_las_guardas_del_perfil_restringido_la_cubren():
    """F-141: el perfil restringido no ve `compras_restringida` (esquema
    ajeno), ninguna vista nueva de F-128 en sus esquemas lee un esquema ajeno
    y ningún objeto nuevo cae en el patrón vigilado por nombre."""
    from config.settings import DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS
    from etl_sigrid.infrastructure.postgres.grants import (
        PATRON_VIGILADO_RESTRINGIDO,
        esquemas_ajenos,
    )

    suyos = DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS.split(",")
    assert ESQUEMA in esquemas_ajenos(["compras", "retenciones", ESQUEMA], suyos)
    nuevos = [
        "compras.factura_recargos", "compras.albaran_recargos", TABLA,
        "retenciones.retencion_factura", "retenciones.v_cuadre_factura_obra",
    ]
    assert not [o for o in nuevos if re.search(PATRON_VIGILADO_RESTRINGIDO, o)]
    # Que la única vista nueva (`v_cuadre_factura_obra`) lea solo `retenciones`
    # —y por tanto no sea una filtración para `filtraciones_restringido`— lo
    # fija `test_f128_sql.py::test_f128_r18_r22_la_vista_lee_solo_retenciones`.


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def test_f128_r22_ficheros_de_permisos_sin_cambios_respecto_a_main():
    """Lo que F-128 no tocó. Antes del merge, `main...HEAD`; DESPUÉS, el diff del propio
    merge de F-128 contra su primer padre: si no, cualquier feature posterior que cambie
    estos ficheros con motivo (F-146 los cambia) pondría este test en rojo. Mismo patrón
    que los tests de versión del diccionario (F-141/F-144/F-145)."""
    ficheros = ("config/settings.py", "etl_sigrid/infrastructure/postgres/grants.py",
                "infra/sql/02_roles.sql")
    merge = _git("log", "main", "--merges", "--format=%H", "--grep=^Merge F-128")
    merge = (merge or "").split()
    if merge:
        salida = _git("diff", "--name-only", f"{merge[0]}^1", merge[0], "--", *ficheros)
    else:
        salida = _git("diff", "--name-only", "main...HEAD", "--", *ficheros)
    if salida is None:
        pytest.skip("sin git o sin rama main: la comprobación la hace el texto de arriba")
    assert salida.strip() == ""


# --- R23 · ningún valor con forma de cuenta en el repositorio ----------------------

#: País + 2 dígitos + 16 o más dígitos (con o sin espacios cada cuatro), o 20
#: dígitos seguidos (CCC).
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?\d){16,}")
_CCC = re.compile(r"(?<!\d)\d{20}(?!\d)")


def cuentas_en(texto: str) -> list[str]:
    """Las cadenas con forma de IBAN o de CCC de un texto (sin devolverlas
    enteras: solo su posición, para no repetir un valor real en el informe)."""
    return [f"posición {m.start()}" for m in (*_IBAN.finditer(texto), *_CCC.finditer(texto))]


def test_f128_r23_positivo_fabricado():
    # Fabricados en tiempo de ejecución para que el propio fichero no contenga
    # ninguna cadena con forma de cuenta.
    iban = "XX" + "00" + "1" * 16
    iban_espacios = "XX00" + " 1111" * 5
    ccc = "0" * 20
    assert cuentas_en(f"cuenta {iban} fin")
    assert cuentas_en(f"cuenta {iban_espacios} fin")
    assert cuentas_en(f"ccc {ccc};")
    assert not cuentas_en("importe 17.706 y 9.939 documentos; 2026-10-17")
    assert not cuentas_en("0" * 19)


def test_f128_r23_barrido_de_los_ficheros_de_la_feature():
    salida = _git("diff", "--name-only", "main...HEAD")
    if salida is None:
        pytest.skip("sin git o sin rama main: no se sabe qué ficheros son de F-128")
    malos = []
    for nombre in salida.split():
        ruta = RAIZ / nombre
        if not ruta.is_file():
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if cuentas_en(texto):
            malos.append(nombre)
    assert malos == []
