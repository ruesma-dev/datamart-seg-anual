# tests/test_f037_sql.py
"""
F-037 · El SQL de `tesoreria` y la vista `compras.vencimientos`, comprobados sobre su TEXTO.

Ninguno de estos ficheros se puede ejecutar aquí: construyen tablas en un
Postgres compartido con producción, y los unit tests no tocan BBDD. Lo que sí
se puede es fijar por escrito lo que el diseño decidió midiendo, de modo que un
refactor que se lleve por delante cualquiera de esas decisiones rompa la suite
y no la nocturna. Mismo criterio que `test_f080_sql.py` y `test_f135_sql.py`.

Las aserciones de SEMÁNTICA del efecto que `test_f080_sql.py` hacía sobre
`compras/05_vencimientos.sql` viven aquí desde F-037 (T5): esa lógica se mudó a
`tesoreria/01_efectos_completo.sql`, y `05` es ya una vista.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import tesoreria as dom

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_TESORERIA = DIRECTORIO_SQL / "tesoreria"
RUTA_SETUP = DIR_TESORERIA / "00_setup.sql"
RUTA_COMPLETO = DIR_TESORERIA / "01_efectos_completo.sql"
RUTA_GENERAL = DIR_TESORERIA / "02_efectos_general.sql"
RUTA_RESTRINGIDOS_MES = DIR_TESORERIA / "03_efectos_restringidos_mes.sql"
RUTA_COMPRAS_SETUP = DIRECTORIO_SQL / "compras" / "00_setup.sql"
RUTA_VENCIMIENTOS = DIRECTORIO_SQL / "compras" / "05_vencimientos.sql"

#: Los ficheros de `tesoreria`, en orden. Lo que vale para todos se comprueba
#: sobre esta tupla.
FICHEROS = (RUTA_SETUP, RUTA_COMPLETO, RUTA_GENERAL, RUTA_RESTRINGIDOS_MES)

#: El orden de columnas de design §4.2 (con `previsto_antiguo`, D11-A).
COLUMNAS_COMPLETO = (
    "efecto_id", "sentido", "empresa_id", "codigo_efecto", "descripcion_efecto",
    "serie_efecto", "documento_id", "codigo_documento", "tipo_documento",
    "es_factura_compra", "tercero_id", "tercero_nombre", "tercero_cif",
    "fecha_emision", "fecha_vencimiento", "fecha_real", "importe", "importe_flujo",
    "estado_tesoreria", "estado_codigo", "estado_sigrid", "efecto_anulado",
    "fecha_anulacion", "medio_pago_id", "medio_pago", "naturaleza_pago_id",
    "naturaleza_pago", "cuenta_contable_id", "cuenta_contable",
    "cuenta_contable_nombre", "banco_id", "banco", "sucursal_id", "sucursal",
    "retencion_id", "centro_coste_id", "obra_id", "codigo_obra", "nombre_obra",
    "remesa_id", "codigo_remesa", "fecha_remesa", "importe_remesa",
    "previsto_antiguo", "restringido", "motivo_restriccion",
)
COLUMNAS_GENERAL = COLUMNAS_COMPLETO[:-2]


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto ejecutable: sin comentarios `--` (de línea o al final de una)."""
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return "\n".join(lineas)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _ejecutable(ruta: Path) -> str:
    return _compacto(_sql(ruta))


def _sin_comment_on(ruta: Path) -> str:
    """El ejecutable sin las sentencias `COMMENT ON ... IS '...';`."""
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(ruta))


def _columnas_de_tabla(ruta: Path, tabla: str) -> list[str]:
    compacto = _ejecutable(ruta)
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);", compacto)
    assert m, f"falta el CREATE TABLE IF NOT EXISTS de {tabla}"
    cuerpo = m.group(1)
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", cuerpo):
        nombre = trozo.strip().split(" ")[0]
        if nombre and nombre.upper() != "PRIMARY":
            columnas.append(nombre)
    return columnas


def _rama(nombre: str) -> str:
    """El texto de una rama del UNION ALL de 01: PAGO o COBRO."""
    compacto = _sin_comment_on(RUTA_COMPLETO)
    ramas = compacto.split("UNION ALL")
    assert len(ramas) == 2, "01 es un UNION ALL de exactamente dos ramas"
    return ramas[0] if nombre == "PAGO" else ramas[1]


# ===========================================================================
# 00 · esquemas, funciones, tablas (R5, R10, R13, R14)
# ===========================================================================

def test_f037_r14_dos_esquemas_y_tres_tablas_que_no_se_dropean() -> None:
    compacto = _ejecutable(RUTA_SETUP)
    assert "CREATE SCHEMA IF NOT EXISTS tesoreria;" in compacto
    assert "CREATE SCHEMA IF NOT EXISTS tesoreria_restringida;" in compacto
    for tabla in (
        "tesoreria_restringida.efectos",
        "tesoreria.efectos",
        "tesoreria.efectos_restringidos_mes",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {tabla} (" in compacto


@pytest.mark.parametrize("ruta", FICHEROS, ids=lambda r: r.name)
def test_f037_r14_ningun_fichero_dropea_una_tabla(ruta: Path) -> None:
    """Un DROP ... CASCADE se llevaría la vista `compras.vencimientos` y los GRANT."""
    ejecutable = _ejecutable(ruta).upper()
    assert "DROP TABLE" not in ejecutable
    assert "DROP SCHEMA" not in ejecutable
    # Solo el setup crea tablas, y siempre con IF NOT EXISTS.
    assert "CREATE TABLE " not in ejecutable.replace("CREATE TABLE IF NOT EXISTS ", "")
    if ruta != RUTA_SETUP:
        assert "CREATE TABLE" not in ejecutable


@pytest.mark.parametrize(
    ("ruta", "tabla"),
    [
        (RUTA_COMPLETO, "tesoreria_restringida.efectos"),
        (RUTA_GENERAL, "tesoreria.efectos"),
        (RUTA_RESTRINGIDOS_MES, "tesoreria.efectos_restringidos_mes"),
    ],
    ids=lambda x: x if isinstance(x, str) else x.name,
)
def test_f037_r14_cada_build_es_truncate_mas_insert(ruta: Path, tabla: str) -> None:
    compacto = _ejecutable(ruta)
    assert f"TRUNCATE {tabla};" in compacto
    assert f"INSERT INTO {tabla} (" in compacto
    assert compacto.index(f"TRUNCATE {tabla};") < compacto.index(f"INSERT INTO {tabla} (")


@pytest.mark.parametrize("ruta", FICHEROS, ids=lambda r: r.name)
def test_f037_r14_sin_grants(ruta: Path) -> None:
    """Los permisos son de `apply_grants` (F-135/F-136), no del build."""
    ejecutable = _ejecutable(ruta).upper()
    assert not re.search(r"\bGRANT\b", ejecutable)
    assert not re.search(r"\bREVOKE\b", ejecutable)
    assert "ALTER DEFAULT PRIVILEGES" not in ejecutable


def test_f037_r5_columnas_de_la_completa_en_su_orden() -> None:
    assert _columnas_de_tabla(RUTA_SETUP, "tesoreria_restringida.efectos") == list(
        COLUMNAS_COMPLETO
    )


def test_f037_r10_columnas_de_la_general_en_el_mismo_orden() -> None:
    assert _columnas_de_tabla(RUTA_SETUP, "tesoreria.efectos") == list(COLUMNAS_GENERAL)


def test_f037_r10_tipos_iguales_en_completa_y_general() -> None:
    compacto = _ejecutable(RUTA_SETUP)
    def cuerpo(t: str) -> str:
        m = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(t)} \((.*?)\);", compacto)
        assert m
        return m.group(1)
    completa = cuerpo("tesoreria_restringida.efectos")
    general = cuerpo("tesoreria.efectos")
    corte = completa.index(", restringido ")
    assert completa[:corte] == general.rstrip()


def test_f037_r5_las_claves_primarias() -> None:
    compacto = _ejecutable(RUTA_SETUP)
    assert compacto.count("efecto_id INTEGER PRIMARY KEY") == 2
    assert "PRIMARY KEY (empresa_id, sentido, anio, mes, estado_tesoreria)" in compacto


@pytest.mark.parametrize(
    "columna",
    ["sentido", "estado_tesoreria", "fecha_vencimiento", "tercero_id", "obra_id",
     "documento_id", "remesa_id"],
)
def test_f037_r14_indices_en_las_dos_carteras(columna: str) -> None:
    compacto = _ejecutable(RUTA_SETUP)
    for tabla in ("tesoreria_restringida.efectos", "tesoreria.efectos"):
        assert re.search(
            rf"CREATE INDEX IF NOT EXISTS \w+ ON {re.escape(tabla)} \({columna}\);", compacto
        ), f"{tabla} necesita índice en {columna}"


def test_f037_r13_la_tabla_de_recuentos_no_tiene_importes() -> None:
    columnas = _columnas_de_tabla(RUTA_SETUP, "tesoreria.efectos_restringidos_mes")
    assert columnas == [
        "empresa_id", "sentido", "anio", "mes", "estado_tesoreria", "num_efectos",
    ]


def _cuerpo_funcion(ruta: Path, firma: str) -> str:
    texto = _sql(ruta)
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(firma)}\((.*?)\)(.*?)(\$\$;|END \$\$;)",
        texto, re.S,
    )
    assert m, f"no encuentro {firma}"
    return re.sub(r"\s+", " ", m.group(1) + m.group(2) + m.group(3)).strip()


@pytest.mark.parametrize(
    ("propia", "original"),
    [
        ("tesoreria.fn_fecha", "compras.fn_sigrid_date"),
        ("tesoreria.fn_serie", "compras.fn_serie"),
    ],
)
def test_f037_funciones_copiadas_de_compras(propia: str, original: str) -> None:
    """R6: la serie es la lógica de `compras.fn_serie`; la fecha, la de siempre."""
    assert _cuerpo_funcion(RUTA_SETUP, propia) == _cuerpo_funcion(RUTA_COMPRAS_SETUP, original)


# ===========================================================================
# 01 · la cartera completa (R2, R5-R9)
# ===========================================================================

def test_f037_r5_una_fila_por_efecto_union_all_de_pag_y_cob() -> None:
    compacto = _sin_comment_on(RUTA_COMPLETO)
    assert compacto.count("UNION ALL") == 1
    assert "FROM raw.pag p" in _rama("PAGO")
    assert "FROM raw.cob p" in _rama("COBRO")
    assert "'PAGO'" in _rama("PAGO") and "'COBRO'" in _rama("COBRO")


def test_f037_r5_sin_where_de_fila() -> None:
    """La cartera es el HECHO entero: ni bajas, ni personal, ni nada se filtra.

    Solo se admite el `WHERE` dentro del `EXISTS` que mira `raw.dcf`.
    """
    sin_exists = re.sub(r"EXISTS \(SELECT 1 FROM raw\.dcf \w+ WHERE [^)]*\)", "", _sin_comment_on(RUTA_COMPLETO))
    assert not re.search(r"\bWHERE\b", sin_exists, re.I)


def test_f037_r5_columnas_del_insert_en_el_orden_del_setup() -> None:
    compacto = _ejecutable(RUTA_COMPLETO)
    m = re.search(r"INSERT INTO tesoreria_restringida\.efectos \((.*?)\)", compacto)
    assert m
    assert [c.strip() for c in m.group(1).split(",")] == list(COLUMNAS_COMPLETO)


@pytest.mark.parametrize("rama", ["PAGO", "COBRO"])
def test_f037_r6_el_efecto_se_lee_de_su_propia_fila_de_con(rama: str) -> None:
    """DA-9 de F-080: el efecto ES un documento; código, estado y baja se LEEN."""
    texto = _rama(rama)
    assert re.search(r"(?<!LEFT )JOIN raw\.con c ON c\.ide = p\.ide", texto)
    for expresion in (
        "c.cod AS codigo_efecto",
        "c.res AS descripcion_efecto",
        "tesoreria.fn_serie(c.cod) AS serie_efecto",
        "c.emp AS empresa_id",
        "c.est AS estado_codigo",
        "(c.fecbaj <> 0) AS efecto_anulado",
        "tesoreria.fn_fecha(c.fecbaj) AS fecha_anulacion",
    ):
        assert expresion in texto, f"{rama}: falta «{expresion}»"


@pytest.mark.parametrize(("rama", "tip"), [("PAGO", 25), ("COBRO", 24)])
def test_f037_r7_el_estado_sigrid_con_el_tip_de_su_sentido(rama: str, tip: int) -> None:
    texto = _rama(rama)
    assert re.search(
        rf"LEFT JOIN raw\.conest ce ON ce\.tip = {tip} AND ce\.est = c\.est", texto
    ), f"{rama}: el estado se traduce con tip = {tip}"
    assert "ce.res AS estado_sigrid" in texto
    otro = 24 if tip == 25 else 25
    assert f"ce.tip = {otro}" not in texto


def test_f037_r7_los_tip_del_sql_son_los_del_dominio() -> None:
    assert f"ce.tip = {dom.TIP_EFECTO_PAGO} " in _rama("PAGO")
    assert f"ce.tip = {dom.TIP_EFECTO_COBRO} " in _rama("COBRO")


@pytest.mark.parametrize("rama", ["PAGO", "COBRO"])
def test_f037_r7_documento_tercero_y_catalogos(rama: str) -> None:
    texto = _rama(rama)
    for expresion in (
        "NULLIF(p.conide, 0) AS documento_id",
        "d.cod AS codigo_documento",
        "d.tip AS tipo_documento",
        "NULLIF(p.entide, 0) AS tercero_id",
        "t.res AS tercero_nombre",
        "tesoreria.fn_fecha(p.fecreaemi) AS fecha_emision",
        "tesoreria.fn_fecha(p.fecven) AS fecha_vencimiento",
        "tesoreria.fn_fecha(p.fecrea) AS fecha_real",
        "COALESCE(p.tot, 0)::NUMERIC(18, 2) AS importe",
        "NULLIF(p.efeide, 0) AS medio_pago_id",
        "ef.res AS medio_pago",
        "NULLIF(p.natide, 0) AS naturaleza_pago_id",
        "na.res AS naturaleza_pago",
        "NULLIF(p.cueide, 0) AS cuenta_contable_id",
        "cue.cod AS cuenta_contable",
        "cue.res AS cuenta_contable_nombre",
        "NULLIF(p.banban, 0) AS banco_id",
        "bb.res AS banco",
        "NULLIF(p.bansuc, 0) AS sucursal_id",
        "bs.res AS sucursal",
        "NULLIF(p.retide, 0) AS retencion_id",
        "NULLIF(p.cenide, 0) AS centro_coste_id",
        "NULLIF(p.remide, 0) AS remesa_id",
        "rc.cod AS codigo_remesa",
        "LEFT JOIN raw.con d ON d.ide = NULLIF(p.conide, 0)",
        "LEFT JOIN raw.con t ON t.ide = NULLIF(p.entide, 0)",
        "LEFT JOIN raw.auxefp ef ON ef.ide = NULLIF(p.efeide, 0)",
        "LEFT JOIN raw.auxnap na ON na.ide = NULLIF(p.natide, 0)",
        "LEFT JOIN raw.con cue ON cue.ide = NULLIF(p.cueide, 0)",
        "LEFT JOIN raw.auxban bb ON bb.ide = NULLIF(p.banban, 0)",
        "LEFT JOIN raw.auxban bs ON bs.ide = NULLIF(p.bansuc, 0)",
    ):
        assert expresion in texto, f"{rama}: falta «{expresion}»"


def test_f037_r7_solo_el_pago_es_factura_de_compra_y_tiene_cif_y_remesa_rpa() -> None:
    pago, cobro = _rama("PAGO"), _rama("COBRO")
    assert re.search(
        r"EXISTS \(SELECT 1 FROM raw\.dcf f WHERE f\.ide = p\.conide\) AS es_factura_compra", pago
    )
    assert "FALSE AS es_factura_compra" in cobro
    assert "LEFT JOIN raw.prv prv ON prv.ide = NULLIF(p.entide, 0)" in pago
    assert "prv.cif AS tercero_cif" in pago
    assert "NULL::VARCHAR(24) AS tercero_cif" in cobro
    assert "raw.prv" not in cobro
    # La remesa de pago, contra `raw.rpa` como en F-080; la de cobro solo tiene
    # código (`raw.rco` no se ingiere).
    assert "LEFT JOIN raw.rpa r ON r.ide = NULLIF(p.remide, 0)" in pago
    assert "LEFT JOIN raw.con rc ON rc.ide = r.ide" in pago
    assert "tesoreria.fn_fecha(r.fecrem) AS fecha_remesa" in pago
    assert "r.imptot::NUMERIC AS importe_remesa" in pago
    assert "LEFT JOIN raw.con rc ON rc.ide = NULLIF(p.remide, 0)" in cobro
    assert "NULL::DATE AS fecha_remesa" in cobro
    assert "NULL::NUMERIC AS importe_remesa" in cobro
    assert "raw.rpa" not in cobro and "raw.rco" not in _sin_comentarios(_sql(RUTA_COMPLETO))


@pytest.mark.parametrize("rama", ["PAGO", "COBRO"])
def test_f037_r8_la_obra_sale_solo_del_centro(rama: str) -> None:
    """D4-A: ni contrato ni líneas (añadirían 6 y 112 efectos)."""
    texto = _rama(rama)
    assert (
        "LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(p.cenide, 0)"
        in texto
    )
    for expresion in ("cc.obra_id AS obra_id", "cc.codigo_obra AS codigo_obra",
                      "cc.nombre_obra AS nombre_obra"):
        assert expresion in texto
    ejecutable = _sin_comentarios(_sql(RUTA_COMPLETO))
    for prohibido in ("compras.contratos", "ctride", "obride", "factura_lineas", "raw.dcfpro"):
        assert prohibido not in ejecutable, f"D4-A: la obra no sale de {prohibido}"


@pytest.mark.parametrize(
    "prohibido",
    ["bancue", "bandig", "p.ban ", "p.ban,", "cpaban", "cpacue", "cpapai", "cpasuc",
     "cpaswi", "cpatip", "cpadiv", "padide", "prpide", "efecto_origen_id"],
)
def test_f037_r9_no_se_publica_la_cuenta_bancaria_ni_enlaces_vacios(prohibido: str) -> None:
    """111.450 pagos traen la cuenta bancaria del tercero: no se publica (R9)."""
    for ruta in FICHEROS:
        assert prohibido not in _sin_comentarios(_sql(ruta)), f"{ruta.name}: {prohibido}"


def _expresion_motivo() -> str:
    m = re.search(
        r"CASE (WHEN e\.naturaleza_pago_id .*?) END AS motivo_restriccion",
        _sin_comment_on(RUTA_COMPLETO),
    )
    assert m, "falta el CASE de motivo_restriccion"
    return m.group(1)


def test_f037_r2_el_case_lleva_los_literales_del_dominio_en_su_orden() -> None:
    """R1/R2: mismo orden de precedencia, la regex de F-135 TAL CUAL, 43 y 306."""
    caso = _expresion_motivo()
    posiciones = [caso.index(f"THEN '{m}'") for m in dom.MOTIVOS_EN_ORDEN]
    assert posiciones == sorted(posiciones), "el orden del CASE es el del dominio"
    assert f"e.cuenta_contable ~ '{dom.REGEX_CUENTA_RESTRINGIDA}' THEN 'CUENTA'" in caso
    assert f"e.tip_tercero = {dom.TIP_TERCERO_EMPLEADO} THEN 'TERCERO_EMPLEADO'" in caso
    assert f"e.tipo_documento = {dom.TIP_DOCUMENTO_NOMINA} THEN 'DOCUMENTO_NOMINA'" in caso
    assert "e.naturaleza_pago_id IS NOT NULL THEN 'NATURALEZA'" in caso
    assert (
        "e.cuenta_contable_id IS NOT NULL AND e.cuenta_contable IS NULL "
        "THEN 'CUENTA_SIN_RESOLVER'" in caso
    )
    assert "ELSE" not in caso, "sin motivo es NULL: visible"


def test_f037_r2_restringido_es_tener_motivo() -> None:
    """Una sola clasificación: `restringido` lee el motivo, no repite el CASE."""
    compacto = _sin_comment_on(RUTA_COMPLETO)
    assert "(m.motivo_restriccion IS NOT NULL) AS restringido" in compacto
    assert compacto.count("THEN 'NATURALEZA'") == 1


def test_f037_r2_el_tercero_trae_su_tip() -> None:
    for rama in ("PAGO", "COBRO"):
        assert "t.tip AS tip_tercero" in _rama(rama)


def test_f037_r3_el_estado_lleva_los_literales_del_dominio() -> None:
    compacto = _sin_comment_on(RUTA_COMPLETO)
    sustituido = ", ".join(str(e) for e in dom.EST_SUSTITUIDO)
    esperado = (
        f"CASE WHEN COALESCE(e.fecbaj_efecto, 0) <> 0 OR e.estado_codigo IN ({sustituido}) "
        f"THEN '{dom.ESTADO_BAJA}' "
        f"WHEN COALESCE(e.fecrea_efecto, 0) <> 0 OR e.estado_codigo = {dom.EST_PAGADO} "
        f"THEN '{dom.ESTADO_REALIZADO}' "
        f"ELSE '{dom.ESTADO_PREVISTO}' END"
    )
    assert f"{esperado} AS estado_tesoreria" in compacto


def test_f037_r4_el_signo_del_flujo() -> None:
    compacto = _sin_comment_on(RUTA_COMPLETO)
    assert (
        f"CASE m.sentido WHEN '{dom.SENTIDO_COBRO}' THEN m.importe "
        f"WHEN '{dom.SENTIDO_PAGO}' THEN -m.importe END AS importe_flujo"
    ) in compacto, "sin ELSE: un sentido desconocido da NULL y la columna NOT NULL lo rechaza"


def test_f037_r25bis_previsto_antiguo_con_los_dos_anios_del_dominio() -> None:
    compacto = _sin_comment_on(RUTA_COMPLETO)
    assert (
        f"(m.estado_tesoreria = '{dom.ESTADO_PREVISTO}' AND COALESCE(m.fecha_vencimiento < "
        f"(CURRENT_DATE - INTERVAL '{dom.ANIOS_PREVISTO_ANTIGUO} years')::DATE, FALSE)) "
        "AS previsto_antiguo"
    ) in compacto, (
        "previsto_antiguo = PREVISTO y vencimiento ANTERIOR (<) al límite; sin "
        "vencimiento, FALSE y no NULL (la columna es NOT NULL)"
    )


@pytest.mark.parametrize("rama", ["PAGO", "COBRO"])
def test_f037_r3_las_fechas_crudas_del_estado_viajan_aparte(rama: str) -> None:
    """El estado mira `fecrea` y `fecbaj` crudos: `fn_fecha` da NULL a una fecha inválida."""
    texto = _rama(rama)
    assert "p.fecrea AS fecrea_efecto" in texto
    assert "c.fecbaj AS fecbaj_efecto" in texto


def test_f037_r5_la_cabecera_cita_lo_que_lee_y_escribe() -> None:
    texto = _sql(RUTA_COMPLETO)
    assert texto.splitlines()[0] == (
        "-- etl_sigrid/infrastructure/postgres/sql/tesoreria/01_efectos_completo.sql"
    )
    for leido in ("raw.pag", "raw.cob", "raw.con", "raw.conest", "raw.dcf",
                  "maestro.centros_coste", "tesoreria_restringida.efectos"):
        assert leido in texto


# ===========================================================================
# 02 · la cartera general (R10, R11, R12)
# ===========================================================================

def test_f037_r10_la_general_es_la_completa_sin_los_restringidos() -> None:
    compacto = _sin_comment_on(RUTA_GENERAL)
    m = re.search(r"INSERT INTO tesoreria\.efectos \((.*?)\)", compacto)
    assert m
    assert [c.strip() for c in m.group(1).split(",")] == list(COLUMNAS_GENERAL)
    assert "FROM tesoreria_restringida.efectos r" in compacto
    assert re.search(r"WHERE NOT r\.restringido;", compacto)
    for prohibida in ("r.restringido,", "r.motivo_restriccion"):
        assert prohibida not in compacto.split("WHERE NOT")[0]


def test_f037_r10_el_select_de_la_general_respeta_el_orden() -> None:
    """Cada columna sale con su nombre, en el orden del setup."""
    compacto = _sin_comment_on(RUTA_GENERAL)
    cuerpo = compacto[compacto.index("SELECT "):compacto.index(" FROM tesoreria_restringida.efectos r")]
    salida = re.findall(r"(?:r\.(\w+)(?:,|$))|(?:AS (\w+)(?:,|$))", cuerpo + ",")
    nombres = [a or b for a, b in salida]
    assert nombres == list(COLUMNAS_GENERAL)


def test_f037_r11_la_remesa_mixta_pierde_su_importe() -> None:
    """Una remesa con algún efecto restringido: su total delataría la nómina (D8)."""
    compacto = _sin_comment_on(RUTA_GENERAL)
    assert (
        "CASE WHEN r.remesa_id IN (SELECT x.remesa_id FROM tesoreria_restringida.efectos x "
        "WHERE x.restringido AND x.remesa_id IS NOT NULL) THEN NULL "
        "ELSE r.importe_remesa END AS importe_remesa"
    ) in compacto


def test_f037_r12_la_guarda_recalcula_el_criterio_desde_raw() -> None:
    """0 filas de la general que cumplan el criterio, recalculado desde `raw`."""
    compacto = _ejecutable(RUTA_GENERAL)
    guarda = compacto[compacto.index("DO $$"):]
    for origen in ("raw.pag", "raw.cob", "raw.con"):
        assert origen in guarda, f"la guarda recalcula desde {origen}"
    assert f"'{dom.REGEX_CUENTA_RESTRINGIDA}'" in guarda
    assert f"= {dom.TIP_TERCERO_EMPLEADO}" in guarda
    assert f"= {dom.TIP_DOCUMENTO_NOMINA}" in guarda
    assert "natide" in guarda
    assert "IS NOT NULL AND cue.cod IS NULL" in guarda, "también la cuenta que no resuelve"
    assert guarda.count("RAISE EXCEPTION") >= 2


def test_f037_r12_la_guarda_cuadra_los_recuentos() -> None:
    compacto = _ejecutable(RUTA_GENERAL)
    guarda = compacto[compacto.index("DO $$"):]
    assert "SELECT count(*) INTO v_general FROM tesoreria.efectos;" in guarda
    assert (
        "SELECT count(*), count(*) FILTER (WHERE restringido) INTO v_completo, v_restringidos "
        "FROM tesoreria_restringida.efectos;"
    ) in guarda
    assert "IF v_general + v_restringidos <> v_completo THEN RAISE EXCEPTION" in guarda
    assert "IF v_personal <> 0 THEN RAISE EXCEPTION" in guarda


def test_f037_r12_la_guarda_va_despues_del_insert() -> None:
    compacto = _ejecutable(RUTA_GENERAL)
    assert compacto.index("INSERT INTO tesoreria.efectos") < compacto.index("DO $$")


# ===========================================================================
# 03 · lo que falta, solo contado (R13, D6)
# ===========================================================================

def test_f037_r13_solo_recuentos_de_los_restringidos() -> None:
    compacto = _sin_comment_on(RUTA_RESTRINGIDOS_MES)
    m = re.search(r"INSERT INTO tesoreria\.efectos_restringidos_mes \((.*?)\)", compacto)
    assert m
    assert [c.strip() for c in m.group(1).split(",")] == [
        "empresa_id", "sentido", "anio", "mes", "estado_tesoreria", "num_efectos",
    ]
    assert "count(*) AS num_efectos" in compacto
    assert "WHERE r.restringido" in compacto
    assert "FROM tesoreria_restringida.efectos r" in compacto


@pytest.mark.parametrize("importe", ["importe", "sum(", "avg(", "max(", "min("])
def test_f037_r13_ningun_importe(importe: str) -> None:
    """D6: el importe por empresa y mes es la nómina neta mensual."""
    assert importe not in _sin_comment_on(RUTA_RESTRINGIDOS_MES).lower()


def test_f037_r13_sin_vencimiento_es_cero_y_no_null() -> None:
    compacto = _sin_comment_on(RUTA_RESTRINGIDOS_MES)
    assert "COALESCE(EXTRACT(YEAR FROM r.fecha_vencimiento)::INT, 0) AS anio" in compacto
    assert "COALESCE(EXTRACT(MONTH FROM r.fecha_vencimiento)::INT, 0) AS mes" in compacto
    assert "COALESCE(r.empresa_id, 0) AS empresa_id" in compacto
    assert "GROUP BY 1, 2, 3, 4, 5" in compacto


# ===========================================================================
# 05 · `compras.vencimientos` pasa a ser vista de la general (R15, R16, D1)
# ===========================================================================

def test_f037_r15_la_vista_publica_la_lista_de_f080() -> None:
    """Mismas columnas, nombres y orden que la tabla de F-080 (lista medida)."""
    from tests.test_f080_sql import COLUMNAS_TABLA_F080, _columnas_de_la_vista

    assert _columnas_de_la_vista() == [c for c, _t in COLUMNAS_TABLA_F080]


def test_f037_r15_los_tipos_de_la_general_son_los_de_f080() -> None:
    """La vista hereda el tipo de `tesoreria.efectos`: tiene que ser el de F-080."""
    from tests.test_f080_sql import COLUMNAS_TABLA_F080

    compacto = _ejecutable(RUTA_SETUP)
    m = re.search(r"CREATE TABLE IF NOT EXISTS tesoreria\.efectos \((.*?)\);", compacto)
    assert m
    tipos = {}
    for trozo in re.split(r",(?![^()]*\))", m.group(1)):
        partes = trozo.strip().split(" ", 1)
        tipos[partes[0]] = partes[1].replace(" NOT NULL", "").replace(" PRIMARY KEY", "").strip()
    traduccion = {
        "INTEGER": "integer", "TEXT": "text", "DATE": "date", "BOOLEAN": "boolean",
        "NUMERIC": "numeric", "NUMERIC(18,2)": "numeric(18,2)",
    }
    def _pg(tipo: str) -> str:
        m_var = re.fullmatch(r"VARCHAR\((\d+)\)", tipo)
        return f"character varying({m_var.group(1)})" if m_var else traduccion[tipo]
    origen = re.search(
        r"CREATE VIEW compras\.vencimientos AS SELECT (.*?) FROM tesoreria\.efectos",
        _ejecutable(RUTA_VENCIMIENTOS),
    ).group(1)
    pares = [t.strip().split(" AS ") for t in origen.split(",")]
    for (columna_general, columna_vista), (esperada, tipo_f080) in zip(
        pares, COLUMNAS_TABLA_F080, strict=True
    ):
        assert columna_vista == esperada
        assert _pg(tipos[columna_general]) == tipo_f080, columna_vista


def test_f037_r15_la_vista_filtra_pago_y_factura_de_compra() -> None:
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "FROM tesoreria.efectos WHERE sentido = 'PAGO' AND es_factura_compra;" in compacto
    assert "tesoreria_restringida" not in compacto, "la vista lee la GENERAL"


def test_f037_r16_borra_tabla_o_vista_segun_relkind() -> None:
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "WHERE n.nspname = 'compras' AND c.relname = 'vencimientos';" in compacto
    assert "IF v_relkind IN ('r', 'p') THEN EXECUTE 'DROP TABLE compras.vencimientos CASCADE';" in compacto
    assert "ELSIF v_relkind = 'v' THEN EXECUTE 'DROP VIEW compras.vencimientos CASCADE';" in compacto
    assert compacto.index("DO $$") < compacto.index("CREATE VIEW compras.vencimientos AS")


def test_f037_r16_sin_indices_ni_tabla_en_05() -> None:
    """Los índices los lleva `tesoreria.efectos`; una vista no los admite."""
    compacto = _ejecutable(RUTA_VENCIMIENTOS)
    assert "CREATE INDEX" not in compacto
    assert "ADD PRIMARY KEY" not in compacto
    assert "CREATE TABLE" not in compacto
    assert "COMMENT ON VIEW compras.vencimientos IS" in compacto


def test_f037_r16_06_sigue_leyendo_la_vista_tal_cual() -> None:
    texto = _sql(DIRECTORIO_SQL / "compras" / "06_pago_factura.sql")
    assert "FROM compras.vencimientos" in texto
    assert "tesoreria" not in texto, "06 no cambia: lee la vista como leía la tabla"


# ===========================================================================
# Trasladadas de `test_f080_sql.py` (T5): la semántica del efecto, ahora en 01
# ===========================================================================

def test_f037_f080_la_cuenta_contable_sale_de_con_y_no_de_cua() -> None:
    """`raw.cua` no tiene `cod` ni `res`: unirse a ella daría una columna vacía."""
    assert "raw.cua" not in _sin_comentarios(_sql(RUTA_COMPLETO))


@pytest.mark.parametrize(
    "crudo", ["fecrea_efecto", "fecbaj_efecto", "tip_tercero"]
)
def test_f037_f080_ninguna_fecha_cruda_se_publica(crudo: str) -> None:
    """Las fechas AAAAMMDD crudas viajan dentro del CTE para el estado, pero no
    se publican: un entero AAAAMMDD se ordena bien y se resta mal (R9 de F-080)."""
    assert crudo not in COLUMNAS_COMPLETO
    compacto = _sin_comment_on(RUTA_COMPLETO)
    insert = re.search(r"INSERT INTO tesoreria_restringida\.efectos \((.*?)\)", compacto).group(1)
    assert crudo not in insert
    final = compacto[compacto.index("FROM marcados m") - 2500:]
    assert f"m.{crudo}" not in final


def test_f037_f080_el_punteo_no_distingue_nada() -> None:
    """`pag.pun` vale 0 en todos los efectos (R10 de F-080)."""
    assert "p.pun" not in _sin_comentarios(_sql(RUTA_COMPLETO))


@pytest.mark.parametrize("derivacion", ["row_number", "lpad", "ordinal_efecto"])
def test_f037_f080_no_se_deriva_el_ordinal_del_efecto(derivacion: str) -> None:
    """DA-8 de F-080: el código del efecto se LEE de `con.cod`."""
    assert derivacion not in _sin_comentarios(_sql(RUTA_COMPLETO)).lower()


def test_f037_f080_la_serie_no_sale_de_con_serie() -> None:
    """`con.serie` vale 0 en todos los efectos (R38 de F-080)."""
    assert "c.serie" not in _ejecutable(RUTA_COMPLETO)


@pytest.mark.parametrize("parseo", ["substring", "left(", "split_part", "regexp_match"])
def test_f037_f080_no_hay_una_segunda_derivacion_de_la_serie(parseo: str) -> None:
    assert parseo not in _sin_comentarios(_sql(RUTA_COMPLETO)).lower()


def test_f037_f080_sin_autojoin_para_adivinar_el_origen() -> None:
    ejecutable = _sin_comentarios(_sql(RUTA_COMPLETO))
    assert not re.search(r"JOIN\s+(compras\.vencimientos|tesoreria\.efectos)", ejecutable, re.I)


def test_f037_f080_la_remesa_de_pago_no_tiene_codigo_en_rpa() -> None:
    """`rpa.cod` no existe: el código de la remesa está en `raw.con` (R41)."""
    assert not re.search(r"\br\.cod\b", _ejecutable(RUTA_COMPLETO))
    assert "rc.cod AS codigo_remesa" in _rama("PAGO")
