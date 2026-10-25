# tests/test_f140_sql.py
"""
F-140 · El SQL de los ingredientes de caja en `sql/tesoreria/` (R4-R18).

Se lee el SQL como texto: ni red ni BBDD. El SQL no llama al dominio, pero
lleva sus mismos literales (patrón de F-135), y aquí se comparan.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom

RAIZ = Path(__file__).resolve().parents[1]
DIR_TESORERIA = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
RUTA_SETUP = DIR_TESORERIA / "00_setup.sql"
RUTA_PLAZOS = DIR_TESORERIA / "04_plazos_forma_pago.sql"
RUTA_COMPRA = DIR_TESORERIA / "05_condiciones_contrato_compra.sql"
RUTA_CLIENTE = DIR_TESORERIA / "06_condiciones_contrato_cliente.sql"
RUTA_DEVENGO = DIR_TESORERIA / "07_devengo_pendiente.sql"
RUTA_HIPOTESIS_OBRA = DIR_TESORERIA / "08_hipotesis_caja_obra.sql"

#: Los ficheros NUEVOS de F-140 (el 00 se amplía).
NUEVOS = (RUTA_PLAZOS, RUTA_COMPRA, RUTA_CLIENTE, RUTA_DEVENGO, RUTA_HIPOTESIS_OBRA)

#: Las ocho tablas nuevas y su clave primaria (design.md §4.1).
TABLAS_NUEVAS: dict[str, str] = {
    "tesoreria.hipotesis_caja": "codigo",
    "tesoreria.hipotesis_caja_manual": "clave_obra, codigo",
    "tesoreria.hipotesis_caja_obra": "obra_id, codigo",
    "tesoreria.condiciones_contrato_compra": "contrato_id",
    "tesoreria.condiciones_contrato_cliente": "contrato_cliente_id",
    "tesoreria.devengo_pendiente_partida": "obra_id, partida_id, concepto",
    "tesoreria.devengo_pendiente_obra_mes": "obra_id, anio_mes, concepto, categoria",
    "tesoreria.devengo_corte_obra": "obra_id, concepto",
}

#: Las columnas de la fórmula, las de R9, que repiten las condiciones (R10, R11).
COLUMNAS_FORMULA = (
    "plazo_formula", "dias_vencimientos", "num_vencimientos", "dias_retencion",
    "formula_reconocida",
)


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return "\n".join(lineas)


def _ejecutable(ruta: Path) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(_sql(ruta)))


def _sin_comment_on(ruta: Path) -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(ruta))


def _cuerpo_tabla(tabla: str) -> str:
    m = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);", _ejecutable(RUTA_SETUP)
    )
    assert m, f"falta el CREATE TABLE IF NOT EXISTS de {tabla}"
    return m.group(1)


def _columnas(tabla: str) -> list[str]:
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", _cuerpo_tabla(tabla)):
        nombre = trozo.strip().split(" ")[0]
        if nombre and nombre.upper() != "PRIMARY":
            columnas.append(nombre)
    return columnas


def _cuerpo_funcion(nombre: str) -> str:
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(nombre)}\(.*?\$\$(.*?)\$\$;",
        _sql(RUTA_SETUP), re.S,
    )
    assert m, f"no encuentro {nombre}"
    return re.sub(r"\s+", " ", m.group(1))


FUNCIONES = ("tesoreria.fn_plazo_reconocido", "tesoreria.fn_plazo_dias",
             "tesoreria.fn_plazo_dias_retencion")


# ===========================================================================
# 00 · las funciones de la fórmula (R7, R8)
# ===========================================================================

@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f140_r8_setup_las_funciones_llevan_los_literales_del_dominio(funcion: str) -> None:
    cuerpo = _cuerpo_funcion(funcion)
    separador = "'" + dom.SEPARADOR_TOKENS + "'"
    assert f"regexp_split_to_array(btrim(f), {separador})" in cuerpo
    regex = {
        "tesoreria.fn_plazo_reconocido": (dom.REGEX_TOKEN_DIAS, dom.REGEX_TOKEN_RETENCION),
        "tesoreria.fn_plazo_dias": (dom.REGEX_TOKEN_DIAS,),
        "tesoreria.fn_plazo_dias_retencion": (dom.REGEX_TOKEN_RETENCION,),
    }[funcion]
    for literal in regex:
        assert f"'{literal}'" in cuerpo
    # ningún otro regex: lo que el SQL reconoce es lo que reconoce el dominio
    assert set(re.findall(r"~ '([^']*)'", cuerpo)) == set(regex)


@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f140_r8_setup_las_funciones_son_immutable_sobre_text(funcion: str) -> None:
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(funcion)}\(f TEXT\)\s+RETURNS (\S+)\s+"
        rf"LANGUAGE sql IMMUTABLE AS",
        _sql(RUTA_SETUP),
    )
    assert m, funcion


def test_f140_r8_setup_los_tipos_que_devuelven() -> None:
    texto = re.sub(r"\s+", " ", _sql(RUTA_SETUP))
    assert "FUNCTION tesoreria.fn_plazo_reconocido(f TEXT) RETURNS BOOLEAN" in texto
    assert "FUNCTION tesoreria.fn_plazo_dias(f TEXT) RETURNS INT[]" in texto
    assert "FUNCTION tesoreria.fn_plazo_dias_retencion(f TEXT) RETURNS INT" in texto


def test_f140_r8_setup_reconocido_falla_cerrado() -> None:
    """Vacía o NULL, un token ajeno o dos `NR`: no reconocida (los casos de R8)."""
    cuerpo = _cuerpo_funcion("tesoreria.fn_plazo_reconocido")
    assert "f IS NOT NULL" in cuerpo
    assert "btrim(f) <> ''" in cuerpo
    assert f"t !~ '{dom.REGEX_TOKEN_DIAS}' AND t !~ '{dom.REGEX_TOKEN_RETENCION}'" in cuerpo
    assert f"WHERE t ~ '{dom.REGEX_TOKEN_RETENCION}') <= 1" in cuerpo


def test_f140_r8_setup_dias_y_retencion_solo_si_se_reconoce() -> None:
    dias = _cuerpo_funcion("tesoreria.fn_plazo_dias")
    assert "WHEN tesoreria.fn_plazo_reconocido(f)" in dias
    assert f"WHERE u.t ~ '{dom.REGEX_TOKEN_DIAS}' ORDER BY u.n" in dias, "en el orden escrito"
    assert "ELSE '{}'::INT[]" in dias, "no reconocida: sin días, como el dominio"
    retencion = _cuerpo_funcion("tesoreria.fn_plazo_dias_retencion")
    assert "WHEN tesoreria.fn_plazo_reconocido(f)" in retencion
    assert "left(t, -1)::INT" in retencion
    assert "ELSE" not in retencion, "no reconocida: NULL"


# ===========================================================================
# 00 · las ocho tablas (R4, R5, R10-R15, R16)
# ===========================================================================

@pytest.mark.parametrize(("tabla", "clave"), TABLAS_NUEVAS.items())
def test_f140_setup_cada_tabla_nueva_con_su_clave_primaria(tabla: str, clave: str) -> None:
    cuerpo = _cuerpo_tabla(tabla)
    if "," in clave:
        assert f"PRIMARY KEY ({clave})" in cuerpo, tabla
    else:
        assert re.search(rf"\b{clave} \w+(\(\d+\))? PRIMARY KEY", cuerpo), tabla


@pytest.mark.parametrize("tabla", TABLAS_NUEVAS)
def test_f140_setup_las_tablas_con_obra_se_buscan_por_obra(tabla: str) -> None:
    columnas = _columnas(tabla)
    if "obra_id" not in columnas:
        return
    clave = TABLAS_NUEVAS[tabla]
    indice = re.search(
        rf"CREATE INDEX IF NOT EXISTS \w+ ON {re.escape(tabla)} \(obra_id\);",
        _ejecutable(RUTA_SETUP),
    )
    assert clave.startswith("obra_id") or indice, f"{tabla}: índice por obra"


@pytest.mark.parametrize("tabla", TABLAS_NUEVAS)
def test_f140_r16_setup_ninguna_columna_de_caja(tabla: str) -> None:
    for columna in _columnas(tabla):
        assert not dom.es_columna_de_caja(columna), f"{tabla}.{columna}"


def test_f140_setup_no_dropea_ni_concede() -> None:
    ejecutable = _ejecutable(RUTA_SETUP).upper()
    assert "DROP TABLE" not in ejecutable and "DROP VIEW" not in ejecutable
    assert not re.search(r"\b(GRANT|REVOKE)\b", ejecutable)


def test_f140_setup_las_condiciones_repiten_las_columnas_de_la_formula() -> None:
    for tabla in ("tesoreria.condiciones_contrato_compra",
                  "tesoreria.condiciones_contrato_cliente"):
        columnas = _columnas(tabla)
        assert [c for c in columnas if c in COLUMNAS_FORMULA] == list(COLUMNAS_FORMULA), tabla


def test_f140_setup_los_valores_de_hipotesis_son_jsonb() -> None:
    """Un DIAS, un PORCENTAJE, una OPCION y un MAPA_DIAS en la misma columna."""
    for tabla, columna in (("tesoreria.hipotesis_caja", "valor_defecto"),
                           ("tesoreria.hipotesis_caja_manual", "valor"),
                           ("tesoreria.hipotesis_caja_obra", "valor")):
        assert re.search(rf"\b{columna} JSONB NOT NULL", _cuerpo_tabla(tabla)), tabla


def test_f140_setup_el_catalogo_tiene_los_campos_de_r1() -> None:
    assert _columnas("tesoreria.hipotesis_caja") == [
        "codigo", "sentido", "descripcion", "unidad", "valor_defecto", "opciones",
        "fuente_defecto", "ingrediente", "validado", "fecha_validacion", "admite_obra",
    ]
    assert _columnas("tesoreria.hipotesis_caja_manual") == [
        "clave_obra", "codigo", "valor", "motivo", "fecha",
    ]


def test_f140_r5_setup_las_columnas_de_la_hipotesis_por_obra() -> None:
    assert _columnas("tesoreria.hipotesis_caja_obra") == [
        "obra_id", "empresa_id", "clave_obra", "codigo", "valor", "nivel", "fuente", "motivo",
    ]


# ===========================================================================
# 04 · las formas de pago y de cobro (R9)
# ===========================================================================

COLUMNAS_PLAZOS = [
    "sentido", "forma_id", "codigo", "nombre", "medio_id", "medio", *COLUMNAS_FORMULA,
    "fecha_baja",
]


def _alias_del_select(texto: str) -> list[str]:
    """Los alias `AS x` del SELECT exterior, en orden, hasta su primer FROM."""
    m = re.search(r"SELECT (.*?) FROM ", texto)
    assert m
    return re.findall(r" AS (\w+)(?=,|$)", m.group(1))


def _ramas_plazos() -> list[str]:
    compacto = _sin_comment_on(RUTA_PLAZOS)
    ramas = compacto.split("UNION ALL")
    assert len(ramas) == 2, "un UNION ALL de PAGO y COBRO"
    return ramas


def test_f140_r9_es_una_vista_que_se_reemplaza() -> None:
    assert "CREATE OR REPLACE VIEW tesoreria.plazos_forma_pago AS" in _ejecutable(RUTA_PLAZOS)
    assert "TABLE" not in _sin_comment_on(RUTA_PLAZOS).upper()


@pytest.mark.parametrize("rama", [0, 1])
def test_f140_r9_las_columnas_de_cada_rama(rama: int) -> None:
    assert _alias_del_select(_ramas_plazos()[rama]) == COLUMNAS_PLAZOS


@pytest.mark.parametrize(
    ("rama", "sentido", "forma", "medio"),
    [(0, "PAGO", "raw.auxpag", "raw.auxefp"), (1, "COBRO", "raw.auxcob", "raw.auxefc")],
)
def test_f140_r9_cada_sentido_con_su_catalogo(rama, sentido, forma, medio) -> None:
    texto = _ramas_plazos()[rama]
    assert f"'{sentido}'" in texto
    assert f"FROM {forma} f LEFT JOIN {medio} m ON m.ide = NULLIF(f.efeide, 0)" in texto
    assert "WHERE" not in texto, "sin filtro: las de baja se publican con su fecha"


@pytest.mark.parametrize("rama", [0, 1])
def test_f140_r9_la_formula_verbatim_y_leida_con_las_funciones(rama: int) -> None:
    texto = _ramas_plazos()[rama]
    assert "f.formul AS plazo_formula" in texto
    assert "tesoreria.fn_plazo_dias(f.formul) AS dias_vencimientos" in texto
    assert "cardinality(tesoreria.fn_plazo_dias(f.formul)) AS num_vencimientos" in texto
    assert "tesoreria.fn_plazo_dias_retencion(f.formul) AS dias_retencion" in texto
    assert "tesoreria.fn_plazo_reconocido(f.formul) AS formula_reconocida" in texto
    assert "tesoreria.fn_fecha(f.fecbaj) AS fecha_baja" in texto


# ===========================================================================
# 05 · las condiciones del contrato de compra (R10)
# ===========================================================================

def _insert(ruta: Path, tabla: str) -> tuple[list[str], str]:
    """Las columnas del INSERT y el SELECT que lo llena."""
    compacto = _sin_comment_on(ruta)
    m = re.search(rf"INSERT INTO {re.escape(tabla)} \((.*?)\) (SELECT .*?);", compacto)
    assert m, f"falta el INSERT de {tabla}"
    return [c.strip() for c in m.group(1).split(",")], m.group(2)


@pytest.mark.parametrize(
    ("ruta", "tabla"),
    [(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra"),
     (RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")],
    ids=["compra", "cliente"],
)
def test_f140_r10_r11_truncate_e_insert_en_el_orden_del_setup(ruta, tabla) -> None:
    compacto = _ejecutable(ruta)
    assert compacto.index(f"TRUNCATE {tabla};") < compacto.index(f"INSERT INTO {tabla} (")
    columnas, select = _insert(ruta, tabla)
    assert columnas == _columnas(tabla)
    assert _alias_del_select(select) == columnas, "cada expresión con el alias de su columna"
    sin_comentarios = _sin_comment_on(ruta).upper()
    assert "CREATE" not in sin_comentarios and "DROP" not in sin_comentarios


def test_f140_r10_sin_terceros_empleados() -> None:
    """R10: un tercero empleado (`con.tip = 43`) no se publica (medido: 0)."""
    _cols, select = _insert(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra")
    assert "LEFT JOIN raw.con t ON t.ide = NULLIF(c.entide, 0)" in select
    assert select.endswith("WHERE t.tip IS DISTINCT FROM 43")


def test_f140_r10_la_garantia_por_clase_4_y_5() -> None:
    """D8-A: clase 4 o 5 de `ctrrec.reccla` (criterio de F-128), la de menor `pos`."""
    _cols, select = _insert(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra")
    assert "WHERE r.docide = c.ide AND r.reccla IN (4, 5) ORDER BY r.pos, r.ide LIMIT 1" in select
    assert "ROUND((r.valpor * 100)::NUMERIC, 4) AS porcentaje" in select
    assert "'RET%'" not in select, "no el criterio por código de F-067"


def test_f140_r10_la_forma_de_pago_y_los_dias_del_proveedor() -> None:
    _cols, select = _insert(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra")
    assert "LEFT JOIN raw.auxpag f ON f.ide = NULLIF(c.pagide, 0)" in select
    assert "LEFT JOIN raw.prv prv ON prv.ide = NULLIF(c.entide, 0)" in select
    assert "NULLIF(btrim(prv.pagdia), '') AS proveedor_dias_fijos_pago" in select
    assert "NULLIF(btrim(prv.pagmes), '') AS proveedor_meses_sin_pago" in select
    for expresion in ("f.formul AS plazo_formula",
                      "tesoreria.fn_plazo_reconocido(f.formul) AS formula_reconocida"):
        assert expresion in select


def test_f140_r10_importes_base_e_iva_tal_cual() -> None:
    _cols, select = _insert(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra")
    assert "c.totbas::NUMERIC(18, 2) AS importe_base" in select
    assert "c.totiva::NUMERIC(18, 2) AS importe_iva" in select


def test_f140_r10_el_estado_con_el_tipo_del_contrato() -> None:
    _cols, select = _insert(RUTA_COMPRA, "tesoreria.condiciones_contrato_compra")
    assert "LEFT JOIN raw.conest ce ON ce.tip = 44 AND ce.est = con.est" in select


# ===========================================================================
# 06 · las condiciones del contrato con el cliente (R11)
# ===========================================================================

def test_f140_r11_desde_obrctr_con_la_forma_de_cobro() -> None:
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert "FROM raw.obrctr o" in select
    assert "LEFT JOIN raw.auxcob f ON f.ide = NULLIF(o.pagide, 0)" in select
    assert "LEFT JOIN raw.auxefc m ON m.ide = NULLIF(f.efeide, 0)" in select
    assert "WHERE" not in select, "todos los contratos con el cliente"


def test_f140_r11_la_retencion_coegar_y_si_no_la_de_retide() -> None:
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert (
        "CASE WHEN COALESCE(o.coegar, 0) <> 0 THEN ROUND(o.coegar::NUMERIC, 4) "
        "WHEN r.ide IS NOT NULL THEN ROUND((r.valpor * 100)::NUMERIC, 4) END "
        "AS retencion_porcentaje" in select
    )
    assert (
        "CASE WHEN COALESCE(o.coegar, 0) <> 0 THEN 'COEGAR' "
        "WHEN r.ide IS NOT NULL THEN 'RECARGO' END AS retencion_fuente" in select
    )
    assert "LEFT JOIN raw.rec r ON r.ide = NULLIF(o.retide, 0)" in select


def test_f140_r11_plazos_a_cero_son_nulos_y_la_fecha_tal_cual() -> None:
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert "NULLIF(o.plaret, 0) AS plazo_retencion_meses" in select
    assert "NULLIF(o.plagar, 0) AS plazo_garantia_meses" in select
    assert "tesoreria.fn_fecha(o.fecinigar) AS fecha_inicio_garantia" in select


# ===========================================================================
# R6, R16, R18 · lo que el SQL nuevo NO hace
# ===========================================================================

@pytest.mark.parametrize("ruta", NUEVOS, ids=lambda r: r.name)
def test_f140_r16_sin_aritmetica_de_fechas(ruta: Path) -> None:
    """Sumar un plazo a una fecha es convertir a caja: no se hace en el ETL."""
    texto = _sin_comment_on(ruta).lower()
    for prohibido in ("interval", "make_interval", "date_add", "+ f.", "+ dias"):
        assert prohibido not in texto, f"{ruta.name}: {prohibido}"


@pytest.mark.parametrize("ruta", NUEVOS, ids=lambda r: r.name)
def test_f140_r6_ningun_valor_de_hipotesis_se_aplica(ruta: Path) -> None:
    """Solo `08` lee las hipótesis, y no hace cuentas con ellas."""
    texto = _sin_comment_on(ruta)
    if ruta == RUTA_HIPOTESIS_OBRA:
        sin_conteos = re.sub(r"count\(\*\)|SELECT \*", "", texto, flags=re.IGNORECASE)
        assert not re.search(r"[*/]|\s[+-]\s", sin_conteos), "08 no hace aritmética"
    else:
        assert "hipotesis" not in texto.lower(), f"{ruta.name} no lee hipótesis"


@pytest.mark.parametrize("ruta", NUEVOS, ids=lambda r: r.name)
@pytest.mark.parametrize(
    "prohibido",
    [r"raw\.pag\b", r"raw\.cob\b", r"tesoreria_restringida", r"raw\.emp\b",
     r"raw\.hmores\b", r"\bpersonal\."],
)
def test_f140_r18_lo_de_personal_no_se_lee(ruta: Path, prohibido: str) -> None:
    assert not re.search(prohibido, _sin_comment_on(ruta)), f"{ruta.name}: {prohibido}"


@pytest.mark.parametrize("ruta", NUEVOS, ids=lambda r: r.name)
def test_f140_sin_grants_ni_drop(ruta: Path) -> None:
    ejecutable = _ejecutable(ruta).upper()
    assert not re.search(r"\b(GRANT|REVOKE)\b", ejecutable)
    assert "DROP " not in ejecutable


@pytest.mark.parametrize("ruta", NUEVOS, ids=lambda r: r.name)
def test_f140_la_cabecera_dice_su_ruta_lo_que_lee_y_lo_que_escribe(ruta: Path) -> None:
    texto = _sql(ruta)
    assert texto.startswith(f"-- etl_sigrid/infrastructure/postgres/sql/tesoreria/{ruta.name}")
    assert "-- Lee de:" in texto and "-- Escribe en:" in texto


# ===========================================================================
# R17 · la cascada de obra de los efectos (D10-A)
# ===========================================================================

from etl_sigrid.domain import tesoreria as dom_tes  # noqa: E402

RUTA_COMPLETO = DIR_TESORERIA / "01_efectos_completo.sql"
RUTA_GENERAL = DIR_TESORERIA / "02_efectos_general.sql"


def _rama_efectos(nombre: str) -> str:
    ramas = _sin_comment_on(RUTA_COMPLETO).split("UNION ALL")
    assert len(ramas) == 2
    return ramas[0] if nombre == "PAGO" else ramas[1]


def test_f140_r17_las_dos_carteras_ganan_obra_via_al_final() -> None:
    compacto = _ejecutable(RUTA_SETUP)
    for tabla in ("tesoreria_restringida.efectos", "tesoreria.efectos"):
        assert f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS obra_via VARCHAR(16);" in compacto
    assert "obra_via" not in _cuerpo_tabla_efectos("tesoreria.efectos"), (
        "va con ALTER, como F-101: al final en una base nueva y en la de hoy"
    )


def _cuerpo_tabla_efectos(tabla: str) -> str:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);",
                  _ejecutable(RUTA_SETUP))
    assert m
    return m.group(1)


def test_f140_r17_los_insert_terminan_en_obra_via() -> None:
    for ruta, tabla in ((RUTA_COMPLETO, "tesoreria_restringida.efectos"),
                        (RUTA_GENERAL, "tesoreria.efectos")):
        m = re.search(rf"INSERT INTO {re.escape(tabla)} \((.*?)\)", _ejecutable(ruta))
        assert m
        assert [c.strip() for c in m.group(1).split(",")][-1] == "obra_via", ruta.name
    assert _sin_comment_on(RUTA_COMPLETO).rstrip().split("FROM marcados m")[0].rstrip().endswith(
        "m.obra_via"
    )
    general = _sin_comment_on(RUTA_GENERAL)
    assert "r.previsto_antiguo, r.obra_via FROM tesoreria_restringida.efectos r" in general


def test_f140_r17_el_case_lleva_las_vias_del_dominio_en_su_orden() -> None:
    pago = _rama_efectos("PAGO")
    assert (
        "CASE WHEN oc.obra_id IS NOT NULL THEN oc.obra_id "
        "WHEN f.obra_cabecera IS NOT NULL THEN f.obra_cabecera "
        "WHEN ol.obra_id IS NOT NULL THEN ol.obra_id END AS obra_id"
    ) in pago
    via = re.search(r"CASE WHEN oc\.obra_id IS NOT NULL THEN '(\w+)' "
                    r"WHEN f\.obra_cabecera IS NOT NULL THEN '(\w+)' "
                    r"WHEN ol\.obra_id IS NOT NULL THEN '(\w+)' END AS obra_via", pago)
    assert via, "la vía de la cascada"
    assert via.groups() == dom_tes.VIAS_EN_ORDEN[1:]


def test_f140_r17_el_centro_manda_y_sin_obra_corta_la_cascada() -> None:
    pago = _rama_efectos("PAGO")
    assert (
        "LEFT JOIN obra_documento od ON od.documento_id = NULLIF(p.conide, 0) "
        "AND COALESCE(p.cenide, 0) = 0"
    ) in pago, "solo sin centro se mira el documento"
    assert "COALESCE(cc.obra_id, od.obra_id) AS obra_id" in pago
    assert (
        f"CASE WHEN cc.obra_id IS NOT NULL THEN '{dom_tes.VIA_CENTRO}' ELSE od.obra_via END "
        "AS obra_via"
    ) in pago


def test_f140_r17_los_cobros_solo_por_el_centro() -> None:
    """Sin documento de venta (F-040) no hay cascada en los cobros."""
    cobro = _rama_efectos("COBRO")
    assert "cc.obra_id AS obra_id" in cobro
    assert f"CASE WHEN cc.obra_id IS NOT NULL THEN '{dom_tes.VIA_CENTRO}' END AS obra_via" in cobro
    assert "obra_documento" not in cobro


def test_f140_r17_solo_obras_de_verdad_y_un_conjunto_de_varias_no_decide() -> None:
    pago = _rama_efectos("PAGO")
    assert pago.count("JOIN raw.obr ") == 3, "contrato, cabecera y líneas: obras de raw.obr"
    assert pago.count("CASE WHEN count(DISTINCT ob.ide) = 1 THEN min(ob.ide) END AS obra_id") == 2
    assert "AND COALESCE(p.cenide, 0) = 0" in pago.split("efectos AS (")[0]
    assert "OR k.ide = l.docoriide" in pago, "contratos de la cabecera y de las líneas"
