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
    """Sumar un plazo a una fecha es convertir a caja: no se hace en el ETL.

    `\\binterval\\b`: el tipo, no las columnas `plan_intervalo` de R12.
    """
    texto = _sin_comment_on(ruta).lower()
    for prohibido in (r"\binterval\b", r"make_interval", r"date_add", r"\+ f\.", r"\+ dias"):
        assert not re.search(prohibido, texto), f"{ruta.name}: {prohibido}"


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
    """Las temporales de `07` (`ON COMMIT DROP`) mueren solas: eso no es un DROP."""
    ejecutable = _ejecutable(ruta).upper().replace("ON COMMIT DROP AS", "")
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
        "LEFT JOIN obra_documento od ON od.factura_id = NULLIF(p.conide, 0) "
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


# ===========================================================================
# 07 · el devengo pendiente (R12-R15, D3-A, D5-A, D16-A, D19-A)
# ===========================================================================

TABLAS_DEVENGO = (
    "tesoreria.devengo_pendiente_partida",
    "tesoreria.devengo_pendiente_obra_mes",
    "tesoreria.devengo_corte_obra",
)


def _devengo() -> str:
    return _sin_comment_on(RUTA_DEVENGO)


def _sin_to_regclass(texto: str) -> str:
    """La guarda de entrada nombra sus fuentes sin leerlas."""
    return re.sub(r"to_regclass\('[^']*'\)", "", texto)


@pytest.mark.parametrize("tabla", TABLAS_DEVENGO)
def test_f140_r12_r14_r15_truncate_e_insert_con_las_columnas_del_setup(tabla: str) -> None:
    texto = _devengo()
    assert texto.index(f"TRUNCATE {tabla};") < texto.index(f"INSERT INTO {tabla} (")
    columnas, select = _insert(RUTA_DEVENGO, tabla)
    assert columnas == _columnas(tabla)
    assert _alias_del_select(select) == columnas


def test_f140_r12_r14_r15_el_orden_de_los_tres_insert() -> None:
    texto = _devengo()
    posiciones = [texto.index(f"INSERT INTO {t} (") for t in TABLAS_DEVENGO]
    assert posiciones == sorted(posiciones), "partida, luego obra y mes, luego el corte"


def test_f140_r13_el_unico_acceso_a_stg_filtra_obra_ambito_y_version() -> None:
    texto = _sin_to_regclass(_devengo())
    assert re.findall(r"\bstg\.\w+", texto) == ["stg.plan_mensual"]
    assert (
        "JOIN stg.plan_mensual pm ON pm.obra_id = v.obra_id "
        "AND pm.ambito_id = v.ambito_id AND pm.version = v.version_master"
    ) in texto


@pytest.mark.parametrize(
    "ruta", sorted(DIR_TESORERIA.glob("*.sql")), ids=lambda r: r.name
)
def test_f140_r13_ninguna_lectura_de_plan_mensual_sin_version(ruta: Path) -> None:
    """`R-VERSION-MASTER`: sin la versión, se suman todas las de la obra."""
    texto = _sin_to_regclass(_sin_comment_on(ruta))
    for m in re.finditer(r"stg\.plan_mensual (\w+) ON (.*?)(?= (?:LEFT )?JOIN | WHERE | GROUP BY |\)|;)", texto):
        alias, condicion = m.group(1), m.group(2)
        assert f"{alias}.version = " in condicion, f"{ruta.name}: {m.group(0)}"
        assert f"{alias}.obra_id = " in condicion and f"{alias}.ambito_id = " in condicion
    assert texto.count("stg.plan_mensual") == len(
        re.findall(r"stg\.plan_mensual \w+ ON ", texto)
    ), f"{ruta.name}: toda lectura de plan_mensual va con su ON filtrado"


def test_f140_r13_los_ambitos_master_por_concepto() -> None:
    assert "CASE p.concepto WHEN 'COSTE' THEN 8 WHEN 'VENTA' THEN 11 END AS ambito_id" in _devengo()


def test_f140_r12_lo_ejecutado_son_las_filas_reales_del_intervalo() -> None:
    texto = _devengo()
    assert (
        "JOIN mart.fact_seguimiento_mensual f ON f.obra_id = v.obra_id "
        "AND f.concepto = v.concepto AND f.tipo_dato = 'REAL' "
        "AND f.anio_mes >= v.mes_version AND f.anio_mes <= v.mes_ultimo_cierre"
    ) in texto


def test_f140_r12_la_version_es_la_del_ultimo_mes_pendiente() -> None:
    """D2-A: la de `mart` en el último mes planificado posterior al cierre."""
    texto = _devengo()
    assert (
        "(array_agg(f.version_master ORDER BY f.anio_mes DESC, f.version_master DESC))[1] "
        "AS version_master"
    ) in texto
    assert "f.tipo_dato = 'PLANIFICADO' AND (u.mes_ultimo_cierre IS NULL OR f.anio_mes > u.mes_ultimo_cierre)" in texto
    assert "COUNT(DISTINCT f.version_master) AS num_versiones_pendientes" in texto
    assert "date_trunc('month', t.version_fec_efectiva)::DATE AS mes_version" in texto
    assert "FROM mart.master_versiones_tipadas x" in texto


def test_f140_r12_los_tramos_del_plan_de_la_version() -> None:
    texto = _devengo()
    assert (
        "COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version), 0) "
        "AS plan_desde_version"
    ) in texto
    assert (
        "COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version "
        "AND p.anio_mes <= v.mes_ultimo_cierre), 0) AS plan_intervalo"
    ) in texto
    assert (
        "COALESCE(SUM(p.importe_mes) FILTER (WHERE p.anio_mes >= v.mes_version "
        "AND (v.mes_ultimo_cierre IS NULL OR p.anio_mes > v.mes_ultimo_cierre)), 0) "
        "AS plan_restante"
    ) in texto


def test_f140_r12_pendiente_y_sobre_ejecutado_como_el_dominio() -> None:
    texto = _devengo()
    assert "GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) AS pendiente" in texto
    assert "GREATEST(0, d.ejecutado_intervalo - d.plan_desde_version) AS sobre_ejecutado" in texto


def test_f140_r14_el_reparto_proporcional_con_el_resto_al_ultimo_mes() -> None:
    texto = _devengo()
    assert "ROUND(d.pendiente * pr.importe_mes / d.total_perfil, 2) AS parte" in texto
    assert (
        "ROW_NUMBER() OVER (PARTITION BY pr.obra_id, pr.concepto, pr.partida_id "
        "ORDER BY pr.anio_mes DESC) AS desde_el_final"
    ) in texto
    assert (
        "CASE WHEN r.desde_el_final = 1 THEN r.pendiente - (r.suma_partes - r.parte) "
        "ELSE r.parte END"
    ) in texto


def test_f140_r14_el_perfil_son_los_meses_con_plan_tras_el_cierre() -> None:
    """Como `repartir_pendiente`: meses a cero fuera y suma positiva para repartir."""
    texto = _devengo()
    assert (
        "p.anio_mes >= v.mes_version AND (v.mes_ultimo_cierre IS NULL OR "
        "p.anio_mes > v.mes_ultimo_cierre) AND p.importe_mes <> 0"
    ) in texto
    assert "d.pendiente > 0 AND d.total_perfil > 0" in texto


def test_f140_r14_sin_perfil_todo_al_primer_mes_marcado() -> None:
    texto = _devengo()
    assert "COALESCE(d.total_perfil, 0) <= 0" in texto
    assert "v.primer_mes_pendiente AS anio_mes" in texto
    assert "TRUE AS es_retraso" in texto


def test_f140_r14_la_guarda_de_la_suma_al_centimo() -> None:
    texto = _devengo()
    guarda = texto[texto.index("INSERT INTO tesoreria.devengo_pendiente_obra_mes"):]
    guarda = guarda[guarda.index("DO $$"):guarda.index("END $$;")]
    assert "tesoreria.devengo_pendiente_partida" in guarda
    assert "tesoreria.devengo_pendiente_obra_mes" in guarda
    assert "IS DISTINCT FROM" in guarda and "RAISE EXCEPTION" in guarda
    assert texto.index("DO $$", texto.index("INSERT INTO tesoreria.devengo_pendiente_obra_mes")) < (
        texto.index("INSERT INTO tesoreria.devengo_corte_obra")
    ), "la guarda va antes del corte"


def test_f140_r14_mes_pasado_sin_cierre_contra_el_mes_del_build() -> None:
    assert "x.anio_mes < date_trunc('month', CURRENT_DATE)::DATE AS mes_pasado_sin_cierre" in _devengo()


def test_f140_r15_la_frontera_con_la_cartera_general() -> None:
    """D16-A: la cartera viva del sentido del concepto y lo emitido tras el cierre."""
    texto = _devengo()
    assert "FROM tesoreria.efectos e" in texto
    assert "e.sentido = CASE v.concepto WHEN 'COSTE' THEN 'PAGO' WHEN 'VENTA' THEN 'COBRO' END" in texto
    assert "e.estado_tesoreria = 'PREVISTO' AND NOT e.previsto_antiguo" in texto
    assert (
        "SUM(e.importe) FILTER (WHERE v.mes_ultimo_cierre IS NULL OR "
        "date_trunc('month', e.fecha_emision)::DATE > v.mes_ultimo_cierre)"
    ) in texto


def test_f140_r15_adelantado_retrasado_y_ejecutado_sin_plan() -> None:
    texto = _devengo()
    assert "SUM(GREATEST(0, d.ejecutado_intervalo - d.plan_intervalo)) AS adelantado" in texto
    assert "SUM(GREATEST(0, d.plan_intervalo - d.ejecutado_intervalo)) AS retrasado" in texto
    assert "WHERE NOT EXISTS (SELECT 1 FROM _dev_partida d WHERE d.obra_id = r.obra_id" in texto


def test_f140_r15_el_real_a_origen_suma_los_meses_reales_hasta_el_cierre() -> None:
    texto = _devengo()
    assert (
        "f.tipo_dato = 'REAL' AND f.anio_mes <= v.mes_ultimo_cierre"
    ) in texto


def test_f140_las_guardas_de_entrada_antes_de_vaciar() -> None:
    texto = _devengo()
    primera = texto.index("DO $$")
    assert primera < texto.index("TRUNCATE")
    entrada = texto[primera:texto.index("END $$;")]
    for objeto in ("mart.fact_seguimiento_mensual", "mart.master_versiones_tipadas",
                   "stg.plan_mensual", "tesoreria.efectos"):
        assert f"to_regclass('{objeto}') IS NULL" in entrada, objeto


def test_f140_la_version_sin_fecha_efectiva_tumba_el_paso() -> None:
    """Sin el mes de V no hay intervalo: falla cerrado, no se adivina."""
    texto = _devengo()
    assert "WHERE mes_version IS NULL" in texto
    assert "devengo_pendiente: " in texto


def test_f140_las_tablas_temporales_mueren_con_la_transaccion() -> None:
    texto = _devengo()
    temporales = re.findall(r"CREATE TEMP TABLE (\w+)", texto)
    assert temporales and all(t.startswith("_dev_") for t in temporales)
    assert texto.count("ON COMMIT DROP") == len(temporales)
    assert not re.search(r"CREATE (?!TEMP TABLE)", texto)


# ===========================================================================
# 08 · el valor de cada hipótesis en cada obra (R3, R5, D18-A)
# ===========================================================================

def _hipotesis_obra() -> str:
    return _sin_comment_on(RUTA_HIPOTESIS_OBRA)


def test_f140_r3_la_guarda_de_la_clave_obra_antes_de_vaciar() -> None:
    texto = _hipotesis_obra()
    guarda = texto[texto.index("DO $$"):texto.index("END $$;")]
    assert "FROM tesoreria.hipotesis_caja_manual m" in guarda
    assert (
        "WHERE NOT EXISTS (SELECT 1 FROM maestro.v_obra_fichas fo WHERE fo.clave_obra = m.clave_obra)"
    ) in guarda
    assert "RAISE EXCEPTION 'hipotesis_caja_obra: " in guarda
    assert texto.index("END $$;") < texto.index("TRUNCATE tesoreria.hipotesis_caja_obra;")


def test_f140_r5_truncate_e_insert_con_las_columnas_del_setup() -> None:
    tabla = "tesoreria.hipotesis_caja_obra"
    texto = _hipotesis_obra()
    assert texto.index(f"TRUNCATE {tabla};") < texto.index(f"INSERT INTO {tabla} (")
    columnas, select = _insert(RUTA_HIPOTESIS_OBRA, tabla)
    assert columnas == _columnas(tabla)
    assert _alias_del_select(select) == columnas


def test_f140_r5_el_case_lleva_el_orden_de_resolver_hipotesis() -> None:
    """MANUAL > SIGRID > DEFECTO, con los niveles de `resolver_hipotesis`."""
    texto = _hipotesis_obra()
    assert (
        "CASE WHEN m.valor IS NOT NULL THEN m.valor WHEN s.valor IS NOT NULL THEN s.valor "
        "ELSE h.valor_defecto END AS valor"
    ) in texto
    fuente = re.search(
        r"CASE WHEN m\.valor IS NOT NULL THEN '(\w+)' WHEN s\.valor IS NOT NULL THEN '(\w+)' "
        r"ELSE '(\w+)' END AS fuente", texto,
    )
    assert fuente and fuente.groups() == dom.ORDEN_FUENTES
    nivel = re.search(
        r"CASE WHEN m\.valor IS NOT NULL THEN '(\w+)' WHEN s\.valor IS NOT NULL THEN '(\w+)' "
        r"ELSE '(\w+)' END AS nivel", texto,
    )
    assert nivel
    esperado = tuple(dom.resolver_hipotesis("d", s, m)[1] for m, s in (("m", None), (None, "s"), (None, None)))
    assert nivel.groups() == esperado
    assert set(nivel.groups()) <= set(dom.NIVELES)


def test_f140_r5_el_universo_obras_con_devengo_o_con_valor_manual() -> None:
    texto = _hipotesis_obra()
    assert "fo.obra_id IN (SELECT c.obra_id FROM tesoreria.devengo_corte_obra c)" in texto
    assert "OR fo.clave_obra IN (SELECT x.clave_obra FROM tesoreria.hipotesis_caja_manual x)" in texto
    assert "CROSS JOIN tesoreria.hipotesis_caja h" in texto


def test_f140_r5_p1a_se_publican_las_23_y_la_que_no_admite_obra_va_a_defecto() -> None:
    """P1-a del review (decisión del humano, 2026-10-26): `R-CAJA-HIPOTESIS`
    manda declarar TODAS las hipótesis desde `hipotesis_caja_obra`, así que la
    tabla publica las 23 del catálogo por obra. `admite_obra` ya no filtra
    filas: solo impide que el YAML o Sigrid den valor de obra (H17 = DEFECTO)."""
    from etl_sigrid.infrastructure.config.hipotesis_caja_yaml import cargar_hipotesis_caja

    catalogo = cargar_hipotesis_caja().catalogo
    assert len(catalogo) == 23
    texto = _hipotesis_obra()
    select = texto[texto.index("INSERT INTO tesoreria.hipotesis_caja_obra"):]
    assert "WHERE h.admite_obra" not in select, "ningún filtro deja fuera hipótesis del catálogo"
    assert not re.search(r"\bh\.codigo\s*(=|IN|<>)", select), "ni por código"
    assert (
        "ON m.clave_obra = o.clave_obra AND m.codigo = h.codigo AND h.admite_obra"
    ) in select, "el YAML no da valor de obra a la que no lo admite"
    assert ") s ON s.obra_id = o.obra_id AND s.codigo = h.codigo AND h.admite_obra;" in select
    # Sin manual ni Sigrid, el CASE cae al DEFECTO: lo mismo que dice el dominio.
    assert dom.resolver_hipotesis("d", None, None)[1:] == ("DEFECTO", "DEFECTO")
    assert [h.codigo for h in catalogo if not h.admite_obra] == ["H17"]


def test_f140_r5_d18_sigrid_solo_h09_h10_h11() -> None:
    texto = _hipotesis_obra()
    codigos = re.findall(r"'(H[0-9]{2})'::VARCHAR\(3\) AS codigo", texto)
    assert tuple(codigos) == dom.CODIGOS_SIGRID
    assert texto.count("FROM tesoreria.condiciones_contrato_cliente k") == 3


def test_f140_r5_d18_sigrid_solo_si_el_valor_es_unico() -> None:
    """Todos los contratos de la obra dan valor, y el mismo."""
    texto = _hipotesis_obra()
    assert texto.count(
        "CASE WHEN count(*) = count(c.valor) AND count(DISTINCT c.valor) = 1 "
        "THEN to_jsonb(min(c.valor)) END AS valor"
    ) == 3


def test_f140_r5_d18_de_donde_sale_cada_valor_sigrid() -> None:
    texto = _hipotesis_obra()
    assert (
        "CASE WHEN k.formula_reconocida AND k.num_vencimientos = 1 "
        "THEN k.dias_vencimientos[1] END AS valor"
    ) in texto, "H09: un plazo único; varios vencimientos no son un valor"
    assert "k.retencion_porcentaje AS valor" in texto, "H10"
    assert "COALESCE(k.plazo_retencion_meses, k.plazo_garantia_meses) AS meses" in texto, "H11"
    assert (
        "CASE WHEN x.meses = trunc(x.meses) THEN x.meses::INTEGER END AS valor"
    ) in texto, "H11 en MESES ENTEROS, como exige el catálogo (no `12.00`)"
