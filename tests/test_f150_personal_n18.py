# tests/test_f150_personal_n18.py
"""
F-150 · N18 (quinta tanda, 31-10): el personal pendiente se paga en DOS tramos,
el NETO el último día del mes de su devengo y el IRPF + la Seguridad Social el
último día del mes SIGUIENTE (R53-R61; corrige la decisión (f) de N16).

La parte de IRPF + SS sale de la CONTABILIDAD de la empresa (abonos NORMAL de
12 meses de 4652000000 Nóminas Pdtes de Pago, 4751000000 H.P. Acree. Reten.
Trabajo y 4760000000 Seguridad Social Acreedora, leídos de `raw.apu`): medido
el 31-10, empresa 1, 0,4419. Se publica solo la CUOTA (las cuentas son CR,
`R-PERFILES`): `tesoreria.reparto_pago_personal` no lleva importes.

Primero el dominio (el oráculo); después el SQL de `07` y `10` leído como
texto (literales = dominio, patrón de F-135): ni red ni BBDD.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom

D = Decimal


# ===========================================================================
# R53 · cuota_irpf_ss: (irpf + ss) / (neto + irpf + ss), a 6 decimales
# ===========================================================================


def test_f150_r53_la_cuota_medida_de_la_empresa_1() -> None:
    """12 meses oct-25..sep-26 (miles de EUR): 7.715,3 / 2.143,0 / 3.966,1."""
    assert dom.cuota_irpf_ss(D("7715.3"), D("2143.0"), D("3966.1")) == D("0.441907")


def test_f150_r53_redondea_a_seis_decimales_la_mitad_lejos_del_cero() -> None:
    assert dom.cuota_irpf_ss(D("2"), D("1"), D("0")) == D("0.333333")
    assert dom.cuota_irpf_ss(D("1"), D("1"), D("1")) == D("0.666667")
    # 1 / 2.000.000 = 0,0000005 exacto: sube (ROUND de PostgreSQL), no al par.
    assert dom.cuota_irpf_ss(D("1999999"), D("1"), D("0")) == D("0.000001")


def test_f150_r53_sin_irpf_ni_ss_la_cuota_es_cero() -> None:
    assert dom.cuota_irpf_ss(D("100"), D("0"), D("0")) == D("0.000000")


@pytest.mark.parametrize(
    ("neto", "irpf", "ss"),
    [
        (D("0"), D("10"), D("10")),       # sin neto: no hay nómina que partir
        (D("-5"), D("10"), D("10")),      # neto negativo (anulaciones)
        (None, D("10"), D("10")),
        (D("100"), D("-60"), D("-50")),   # IRPF + SS < -neto: cociente > 1
        (D("100"), D("-50"), D("-50")),   # denominador 0: no se divide
        (D("100"), D("-10"), D("0")),     # cuota negativa
        (D("100"), None, D("10")),
        (D("100"), D("10"), None),
    ],
)
def test_f150_r53_fuera_de_rango_o_sin_neto_devuelve_none(neto, irpf, ss) -> None:
    assert dom.cuota_irpf_ss(neto, irpf, ss) is None


def test_f150_r53_los_extremos_del_rango_valen() -> None:
    assert dom.cuota_irpf_ss(D("100"), D("0"), D("0")) == D("0")
    # neto > 0 diminuto frente a irpf + ss: 0,999999..., redondea a 1 y vale.
    assert dom.cuota_irpf_ss(D("0.0000001"), D("100"), D("0")) == D("1")


# ===========================================================================
# R54 · reparto_pago_personal: (cuota, fuente, motivo)
# ===========================================================================

NETO, IRPF, SS = D("7715.3"), D("2143.0"), D("3966.1")


def test_f150_r54_las_constantes() -> None:
    assert dom.CUENTAS_NOMINA == {"NETO": "4652000000", "IRPF": "4751000000", "SS": "4760000000"}
    assert dom.MESES_VENTANA_NOMINA == 12
    assert dom.MESES_MAX_SIN_NOMINA == 3
    assert dom.MIN_PERSONAS_REPARTO == 10
    assert dom.FUENTES_REPARTO_PERSONAL == ("CONTABILIDAD", "CONTABILIDAD_PARCIAL", "DEFECTO")
    assert dom.MOTIVOS_REPARTO_PERSONAL == (
        "SIN_NOMINA_RECIENTE", "POCAS_PERSONAS", "CUOTA_FUERA_DE_RANGO")


def test_f150_r54_doce_meses_es_contabilidad() -> None:
    assert dom.reparto_pago_personal(12, 273, NETO, IRPF, SS) == (D("0.441907"), "CONTABILIDAD", None)


@pytest.mark.parametrize("meses", [1, 6, 11])
def test_f150_r54_de_uno_a_once_meses_es_parcial_y_se_aplica(meses: int) -> None:
    assert dom.reparto_pago_personal(meses, 273, NETO, IRPF, SS) == (
        D("0.441907"), "CONTABILIDAD_PARCIAL", None)


def test_f150_r54_sin_nomina_reciente_es_defecto_cero() -> None:
    """Sin abono en 4652000000 en los 3 meses anteriores al build no hay
    ventana: 0 meses. Defecto = N16: todo a fin del mes de devengo."""
    assert dom.reparto_pago_personal(0, 273, None, None, None) == (
        D("0"), "DEFECTO", "SIN_NOMINA_RECIENTE")
    assert dom.reparto_pago_personal(0, 273, NETO, IRPF, SS) == (
        D("0"), "DEFECTO", "SIN_NOMINA_RECIENTE")


def test_f150_r54_nueve_personas_es_defecto_diez_no() -> None:
    """Con menos de 10 personas la cuota delataría el IRPF de alguien."""
    assert dom.reparto_pago_personal(12, 9, NETO, IRPF, SS) == (D("0"), "DEFECTO", "POCAS_PERSONAS")
    assert dom.reparto_pago_personal(12, 0, NETO, IRPF, SS) == (D("0"), "DEFECTO", "POCAS_PERSONAS")
    assert dom.reparto_pago_personal(12, 10, NETO, IRPF, SS)[1] == "CONTABILIDAD"


def test_f150_r54_cuota_fuera_de_rango_es_defecto() -> None:
    assert dom.reparto_pago_personal(12, 273, D("0"), IRPF, SS) == (
        D("0"), "DEFECTO", "CUOTA_FUERA_DE_RANGO")
    assert dom.reparto_pago_personal(5, 273, D("100"), D("-60"), D("-50")) == (
        D("0"), "DEFECTO", "CUOTA_FUERA_DE_RANGO")


def test_f150_r54_el_orden_de_los_motivos() -> None:
    """Sin nómina manda sobre pocas personas, y pocas personas sobre el rango."""
    assert dom.reparto_pago_personal(0, 3, D("0"), D("1"), D("1"))[2] == "SIN_NOMINA_RECIENTE"
    assert dom.reparto_pago_personal(12, 3, D("0"), D("1"), D("1"))[2] == "POCAS_PERSONAS"


def test_f150_r54_fuente_y_motivo_siempre_del_catalogo() -> None:
    for meses, personas, n in [(12, 273, NETO), (3, 50, NETO), (0, 50, NETO), (12, 2, NETO),
                               (12, 50, D("-1"))]:
        cuota, fuente, motivo = dom.reparto_pago_personal(meses, personas, n, IRPF, SS)
        assert fuente in dom.FUENTES_REPARTO_PERSONAL
        assert (motivo is None) == (fuente != "DEFECTO")
        assert motivo is None or motivo in dom.MOTIVOS_REPARTO_PERSONAL
        assert D("0") <= cuota <= D("1")


# ===========================================================================
# R55 · partir_personal: irpf_ss al céntimo y el neto, la resta
# ===========================================================================


def test_f150_r55_la_0686_de_noviembre() -> None:
    """0,2104 M EUR de personal en 2026-11 con 0,441907."""
    neto, irpf_ss = dom.partir_personal(D("210400.00"), D("0.441907"))
    assert irpf_ss == D("92977.23")
    assert neto == D("117422.77")


def test_f150_r55_redondeo_al_centimo_la_mitad_lejos_del_cero() -> None:
    assert dom.partir_personal(D("0.01"), D("0.5")) == (D("0.00"), D("0.01"))
    assert dom.partir_personal(D("-0.01"), D("0.5")) == (D("0.00"), D("-0.01"))
    assert dom.partir_personal(D("100.00"), D("0.333333")) == (D("66.67"), D("33.33"))


@pytest.mark.parametrize("importe", [D("0"), D("0.00"), D("-123.45"), D("0.03"), D("999999.99")])
@pytest.mark.parametrize("cuota", [D("0"), D("0.441907"), D("0.5"), D("1"), D("0.000001")])
def test_f150_r55_la_suma_es_exacta_al_centimo(importe: Decimal, cuota: Decimal) -> None:
    neto, irpf_ss = dom.partir_personal(importe, cuota)
    assert neto + irpf_ss == importe
    assert irpf_ss == irpf_ss.quantize(D("0.01"))


def test_f150_r55_cuota_cero_es_todo_neto_y_uno_todo_al_mes_siguiente() -> None:
    assert dom.partir_personal(D("500.00"), D("0")) == (D("500.00"), D("0.00"))
    assert dom.partir_personal(D("500.00"), D("1")) == (D("0.00"), D("500.00"))


# ===========================================================================
# El SQL de `07` y `10`, leído como texto (R56-R61): literales = dominio
# ===========================================================================

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_SETUP = DIR_SQL / "tesoreria" / "00_setup.sql"
RUTA_DEVENGO = DIR_SQL / "tesoreria" / "07_devengo_pendiente.sql"
RUTA_SALDO = DIR_SQL / "tesoreria" / "10_saldo_partida.sql"
RUTA_MAYOR = DIR_SQL / "contabilidad" / "02_mayor.sql"

#: R56: ninguna columna de la tabla de cuotas puede ser un importe de nómina.
PATRON_IMPORTE = r"importe|debe|haber|saldo|total|eur"

COLUMNAS_REPARTO = [
    "empresa_id", "mes_desde", "mes_hasta", "meses_con_nomina", "personas_con_partes",
    "cuota_neto", "cuota_irpf_ss", "fuente", "motivo", "fecha_calculo",
]


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _ejecutable(ruta: Path) -> str:
    lineas = []
    for linea in _sql(ruta).splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return re.sub(r"\s+", " ", "\n".join(lineas))


def _sin_comment(ruta: Path) -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(ruta))


def _insert(ruta: Path, tabla: str) -> tuple[list[str], str]:
    m = re.search(rf"INSERT INTO {re.escape(tabla)} \((.*?)\) (SELECT .*?);", _sin_comment(ruta))
    assert m, f"falta el INSERT de {tabla}"
    return [c.strip() for c in m.group(1).split(",")], m.group(2)


def _cuerpo_tabla(tabla: str) -> str:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);",
                  _ejecutable(RUTA_SETUP))
    assert m, f"falta el CREATE TABLE de {tabla}"
    return m.group(1)


def _sentencia(texto: str, inicio: str) -> str:
    i = texto.index(inicio)
    return texto[i: texto.index(";", i)]


# ---------------------------------------------------------------------------
# R56 · la tabla de cuotas: una fila por empresa y ningún importe
# ---------------------------------------------------------------------------


def test_f150_r56_la_tabla_y_su_clave() -> None:
    cuerpo = _cuerpo_tabla("tesoreria.reparto_pago_personal")
    columnas = [t.strip().split(" ")[0] for t in re.split(r",(?![^()]*\))", cuerpo)]
    assert columnas == COLUMNAS_REPARTO
    assert re.search(r"\bempresa_id INTEGER PRIMARY KEY", cuerpo)
    assert "cuota_irpf_ss NUMERIC(12,6) NOT NULL" in cuerpo


@pytest.mark.parametrize("columna", COLUMNAS_REPARTO)
def test_f150_r56_ninguna_columna_es_un_importe(columna: str) -> None:
    assert not re.search(PATRON_IMPORTE, columna), columna
    assert not dom.es_columna_de_caja(columna), columna


def test_f150_r56_el_insert_no_publica_ninguna_suma() -> None:
    """Las columnas del INSERT son las del setup, y su SELECT exterior solo
    expone cuotas, meses, recuentos y la fuente: ni un alias de importe."""
    columnas, select = _insert(RUTA_DEVENGO, "tesoreria.reparto_pago_personal")
    assert columnas == COLUMNAS_REPARTO
    exterior = re.search(r"SELECT (.*?) FROM ", select).group(1)
    assert re.findall(r" AS (\w+)(?=,|$)", exterior) == COLUMNAS_REPARTO
    assert "SUM(" not in exterior and "haber" not in exterior


def test_f150_r56_la_cuota_neto_es_el_complemento() -> None:
    _cols, select = _insert(RUTA_DEVENGO, "tesoreria.reparto_pago_personal")
    assert "1 - q.cuota_irpf_ss AS cuota_neto" in select


def test_f150_r56_las_sumas_viven_solo_en_temporales() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    assert "CREATE TEMP TABLE _dev_nomina ON COMMIT DROP AS" in texto
    assert "CREATE TEMP TABLE _dev_personas ON COMMIT DROP AS" in texto
    # `raw.apu` solo se lee en la guarda de entrada y en `_dev_nomina`.
    usos = re.findall(r"FROM raw\.apu\b", texto)
    nomina = _sentencia(texto, "CREATE TEMP TABLE _dev_nomina")
    assert len(usos) == 2 and "FROM raw.apu a" in nomina


def test_f150_r56_el_comment_dice_que_no_lleva_importes() -> None:
    m = re.search(r"COMMENT ON TABLE tesoreria\.reparto_pago_personal IS '(.*?)';",
                  _ejecutable(RUTA_DEVENGO))
    assert m
    assert "R-PERFILES" in m.group(1) and "sin importes" in m.group(1).lower()


# ---------------------------------------------------------------------------
# R57 · las cuentas, la clase NORMAL y la ventana: los literales del dominio
# ---------------------------------------------------------------------------


def _clase_mayor() -> str:
    m = re.search(r"(CASE WHEN a\.cla = 3 .*? ELSE 'NORMAL' END)", _ejecutable(RUTA_MAYOR))
    assert m, "02_mayor.sql sin su clase"
    return m.group(1)


def test_f150_r57_la_clase_normal_es_la_de_02_mayor() -> None:
    nomina = _sentencia(_sin_comment(RUTA_DEVENGO), "CREATE TEMP TABLE _dev_nomina")
    assert f"{_clase_mayor()} = 'NORMAL'" in nomina


def test_f150_r57_las_tres_cuentas_exactas_y_por_su_tipo() -> None:
    nomina = _sentencia(_sin_comment(RUTA_DEVENGO), "CREATE TEMP TABLE _dev_nomina")
    cuentas = ", ".join(f"'{c}'" for c in dom.CUENTAS_NOMINA.values())
    assert f"k.cod IN ({cuentas})" in nomina
    assert "JOIN raw.con k ON k.ide = a.cueide AND k.tip = 17" in nomina
    assert "SUM(COALESCE(a.hab, 0)::NUMERIC(18, 2)) AS haber" in nomina, "hab es double: cast"
    assert "a.deb" not in nomina, "solo el ABONO"


def test_f150_r57_los_meses_de_la_ventana_son_los_del_dominio() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    nomina = _sentencia(texto, "CREATE TEMP TABLE _dev_nomina")
    total = dom.MESES_VENTANA_NOMINA + dom.MESES_MAX_SIN_NOMINA
    assert f"(date_trunc('month', CURRENT_DATE) - INTERVAL '{total} month')::DATE" in nomina
    assert "< date_trunc('month', CURRENT_DATE)::DATE" in nomina, "solo meses anteriores al build"
    ventana = _sentencia(texto, "CREATE TEMP TABLE _dev_ventana")
    assert (f"(date_trunc('month', CURRENT_DATE) - INTERVAL '{dom.MESES_MAX_SIN_NOMINA} month')"
            "::DATE") in ventana
    assert (f"(h.mes_hasta - INTERVAL '{dom.MESES_VENTANA_NOMINA - 1} month')::DATE "
            "AS mes_desde") in ventana
    assert f"n.cuenta = '{dom.CUENTAS_NOMINA['NETO']}' AND n.haber <> 0" in ventana


def test_f150_r57_las_personas_con_el_filtro_del_personal() -> None:
    personas = _sentencia(_sin_comment(RUTA_DEVENGO), "CREATE TEMP TABLE _dev_personas")
    assert "r.cla = 1 AND COALESCE(r.prvide, 0) = 0" in personas
    assert "COUNT(DISTINCT h.reside)" in personas
    assert "JOIN maestro.v_obra_fichas fo ON fo.empresa_id = w.empresa_id" in personas
    assert "BETWEEN w.mes_desde AND w.mes_hasta" in personas


def test_f150_r57_el_sql_lleva_las_reglas_del_dominio() -> None:
    _cols, select = _insert(RUTA_DEVENGO, "tesoreria.reparto_pago_personal")
    assert (f"WHEN b.personas_con_partes < {dom.MIN_PERSONAS_REPARTO} THEN 'POCAS_PERSONAS'"
            in select)
    assert "WHEN b.meses_con_nomina <= 0 THEN 'SIN_NOMINA_RECIENTE'" in select
    assert ("WHEN b.cuota_bruta IS NULL OR b.cuota_bruta < 0 OR b.cuota_bruta > 1 "
            "THEN 'CUOTA_FUERA_DE_RANGO'") in select
    assert (f"WHEN c.meses_con_nomina >= {dom.MESES_VENTANA_NOMINA} THEN 'CONTABILIDAD' "
            "ELSE 'CONTABILIDAD_PARCIAL'") in select
    assert ("CASE WHEN a.neto > 0 THEN ROUND((a.irpf + a.ss) / NULLIF(a.neto + a.irpf + a.ss, 0), "
            "6) END AS cuota_bruta") in select
    for clave in ("NETO", "IRPF", "SS"):
        assert f"n.cuenta = '{dom.CUENTAS_NOMINA[clave]}'" in select, clave
    for literal in dom.FUENTES_REPARTO_PERSONAL + dom.MOTIVOS_REPARTO_PERSONAL:
        assert f"'{literal}'" in select, literal


def test_f150_r56_solo_las_empresas_del_devengo_de_coste() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    ventana = _sentencia(texto, "CREATE TEMP TABLE _dev_ventana")
    assert ("SELECT DISTINCT empresa_id FROM _dev_version WHERE concepto = 'COSTE' "
            "AND empresa_id IS NOT NULL") in ventana
    nomina = _sentencia(texto, "CREATE TEMP TABLE _dev_nomina")
    assert "k.emp IN (SELECT empresa_id FROM _dev_version WHERE concepto = 'COSTE')" in nomina


# ---------------------------------------------------------------------------
# R58 · el personal del mes en dos tramos y el corte
# ---------------------------------------------------------------------------


def test_f150_r58_la_obra_mes_parte_el_personal_por_la_cuota_de_su_empresa() -> None:
    columnas, select = _insert(RUTA_DEVENGO, "tesoreria.devengo_pendiente_obra_mes")
    assert columnas[-3:] == ["importe_pendiente_personal", "importe_personal_neto",
                             "importe_personal_irpf_ss"]
    irpf_ss = "ROUND(COALESCE(x.importe_personal, 0) * COALESCE(rp.cuota_irpf_ss, 0), 2)"
    assert (f"CASE WHEN x.concepto = 'COSTE' THEN {irpf_ss} END AS importe_personal_irpf_ss"
            in select)
    assert (f"CASE WHEN x.concepto = 'COSTE' THEN COALESCE(x.importe_personal, 0) - {irpf_ss} END "
            "AS importe_personal_neto") in select
    assert ("LEFT JOIN tesoreria.reparto_pago_personal rp ON rp.empresa_id = v.empresa_id"
            in select)


def test_f150_r58_la_guarda_mira_los_dos_tramos_fila_a_fila() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    assert ("WHERE concepto = 'COSTE' AND importe_personal_neto + importe_personal_irpf_ss "
            "IS DISTINCT FROM importe_pendiente_personal") in texto
    assert "no cuadra en sus dos tramos" in texto
    # La guarda va antes del corte: si falla, la transaccion entera vuelve atras.
    i_guarda = texto.index("no cuadra en sus dos tramos")
    assert i_guarda < texto.index("INSERT INTO tesoreria.devengo_corte_obra (")


def test_f150_r58_el_corte_publica_la_parte_irpf_ss() -> None:
    columnas, select = _insert(RUTA_DEVENGO, "tesoreria.devengo_corte_obra")
    assert columnas[-1] == "pendiente_personal_irpf_ss"
    assert ("CASE WHEN v.concepto = 'COSTE' THEN COALESCE(pi.pendiente_personal_irpf_ss, 0) END "
            "AS pendiente_personal_irpf_ss") in select
    assert ("SELECT obra_id, SUM(importe_personal_irpf_ss) AS pendiente_personal_irpf_ss "
            "FROM tesoreria.devengo_pendiente_obra_mes WHERE concepto = 'COSTE' GROUP BY obra_id"
            ) in select


def test_f150_r58_el_reparto_se_publica_antes_que_la_obra_mes() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    i_reparto = texto.index("INSERT INTO tesoreria.reparto_pago_personal (")
    assert texto.index("TRUNCATE tesoreria.reparto_pago_personal;") < i_reparto
    assert i_reparto < texto.index("INSERT INTO tesoreria.devengo_pendiente_obra_mes (")
    # y despues de la guarda de D6: no vacia nada antes de las guardas.
    assert texto.index("partidas de venta con pendiente y sin coeficiente") < texto.index(
        "TRUNCATE tesoreria.reparto_pago_personal;")


# ---------------------------------------------------------------------------
# R61 · la guarda de entrada: sin apuntes o sin cuentas, falla
# ---------------------------------------------------------------------------


def test_f150_r61_la_guarda_de_entrada_de_la_nomina() -> None:
    texto = _sin_comment(RUTA_DEVENGO)
    primera_temporal = texto.index("CREATE TEMP TABLE")
    entrada = texto[:primera_temporal]
    assert "to_regclass('raw.apu') IS NULL" in entrada
    assert "IF NOT EXISTS (SELECT 1 FROM raw.apu) THEN" in entrada
    cuentas = ", ".join(f"'{c}'" for c in dom.CUENTAS_NOMINA.values())
    assert (f"IF NOT EXISTS (SELECT 1 FROM raw.con WHERE tip = 17 AND cod IN ({cuentas})) THEN"
            in entrada)
    assert "raw.apu llega vacia" in entrada
    assert primera_temporal < texto.index("TRUNCATE")


# ---------------------------------------------------------------------------
# R59 · el saldo de partida: el IRPF + SS de los partes del último cierre
# ---------------------------------------------------------------------------


def test_f150_r59_la_columna_con_alter_y_al_final_del_insert() -> None:
    assert ("ALTER TABLE tesoreria.saldo_partida_obra ADD COLUMN IF NOT EXISTS "
            "personal_irpf_ss_pendiente NUMERIC(18,2);") in _ejecutable(RUTA_SETUP)
    columnas, select = _insert(RUTA_SALDO, "tesoreria.saldo_partida_obra")
    assert columnas[-1] == "personal_irpf_ss_pendiente"
    assert re.findall(r" AS (\w+)(?=,|$)", re.search(r"SELECT (.*?) FROM ", select).group(1))[-1] \
        == "personal_irpf_ss_pendiente"


def test_f150_r59_los_partes_del_ultimo_cierre_con_el_mismo_filtro() -> None:
    personal = _sentencia(_sin_comment(RUTA_SALDO), "CREATE TEMP TABLE _sal_personal")
    assert ("SUM(COALESCE(h.tot, 0)::NUMERIC(18, 2)) FILTER (WHERE date_trunc('month', "
            "tesoreria.fn_fecha(h.fec))::DATE = o.mes_ultimo_cierre) AS personal_partes_ultimo_cierre"
            ) in personal
    # el mismo WHERE que `personal_coste_partes`: una sola lectura de los partes
    assert personal.count("FROM raw.hmores h") == 1


def test_f150_r59_la_condicion_de_fecha_y_la_cuota_de_su_empresa() -> None:
    _cols, select = _insert(RUTA_SALDO, "tesoreria.saldo_partida_obra")
    assert ("CASE WHEN o.mes_ultimo_cierre IS NULL THEN NULL "
            "WHEN (o.mes_ultimo_cierre + INTERVAL '2 month' - INTERVAL '1 day')::DATE >= CURRENT_DATE "
            "THEN ROUND(COALESCE(p.personal_partes_ultimo_cierre, 0) * COALESCE(rp.cuota_irpf_ss, 0), 2) "
            "ELSE 0 END AS personal_irpf_ss_pendiente") in select
    assert "LEFT JOIN tesoreria.reparto_pago_personal rp ON rp.empresa_id = o.empresa_id" in select
    # fecha_corte es CURRENT_DATE: la condición compara con la misma fecha.
    assert "CURRENT_DATE AS fecha_corte" in select


def test_f150_r59_la_guarda_de_entrada_exige_el_reparto() -> None:
    texto = _sin_comment(RUTA_SALDO)
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    assert "to_regclass('tesoreria.reparto_pago_personal') IS NULL" in entrada


def _fin_mes_siguiente(mes_cierre: date) -> date:
    """`(mes_ultimo_cierre + INTERVAL '2 month' - INTERVAL '1 day')::DATE`."""
    anio, mes = divmod(mes_cierre.month + 1, 12)
    primero_dos_meses = date(mes_cierre.year + anio, mes + 1, 1)
    return primero_dos_meses - timedelta(days=1)


@pytest.mark.parametrize(
    ("cierre", "corte", "pendiente"),
    [
        (date(2026, 10, 1), date(2026, 10, 31), True),    # 16 obras: vence el 30-11
        (date(2026, 9, 1), date(2026, 10, 31), True),     # 2 obras: vence el 31-10, no antes
        (date(2026, 9, 1), date(2026, 11, 1), False),     # ya pagado
        (date(2026, 8, 1), date(2026, 10, 31), False),
        (date(2026, 11, 1), date(2026, 12, 31), True),    # vence el 31-12
        (date(2026, 12, 1), date(2027, 1, 31), True),     # cruza el año
        (date(2026, 12, 1), date(2027, 2, 1), False),
        (date(2027, 1, 1), date(2027, 2, 28), True),      # febrero no bisiesto
    ],
)
def test_f150_r59_la_condicion_de_fecha(cierre: date, corte: date, pendiente: bool) -> None:
    """Pendiente SI el último día del mes siguiente al cierre NO es anterior al corte."""
    assert (_fin_mes_siguiente(cierre) >= corte) is pendiente
