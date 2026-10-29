# tests/test_f150_albaranes.py
"""
F-150 · Los albaranes pendientes de facturar NETOS por proveedor (N11, R33-R35)
y la parte de coste proporcional de la cartera (N12, R36).

Lo que suma `compras.v_pbi_albaranes_sin_facturar` (solo líneas > 0: 56,9 M EUR
en las 21 obras el 29-10) no es lo que queda por facturar: 48,2 de esos millones
ya están SOBREFACTURADOS al mismo proveedor en otras líneas (pendiente < 0). Lo
real es el NETO por (obra, proveedor), con suelo 0 (8,76 M EUR). Para fecharlo
(H20, H27) se supone FIFO: lo sobrefacturado compensa primero las entregas más
antiguas.

Primero el dominio (`neto_fifo`, el oráculo); después el SQL leído como texto
(literales = dominio, patrón de F-135): ni red ni BBDD.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import neto_fifo

D = Decimal


# ===========================================================================
# R33 · neto_fifo: lo sobrefacturado compensa primero lo más antiguo
# ===========================================================================


def test_f150_r33_todo_positivo_queda_entero() -> None:
    assert neto_fifo([D("100.00"), D("50.00")]) == [D("100.00"), D("50.00")]


def test_f150_r33_todo_negativo_da_ceros() -> None:
    """Sobrefacturado sin nada que compensar: el residuo no es caja (suelo 0)."""
    assert neto_fifo([D("-100.00"), D("-5.00")]) == [D("0"), D("0")]


def test_f150_r33_los_negativos_cubren_justo_lo_positivo() -> None:
    assert neto_fifo([D("100.00"), D("-60.00"), D("50.00"), D("-90.00")]) == [
        D("0"), D("0"), D("0"), D("0"),
    ]


def test_f150_r33_los_negativos_sobran() -> None:
    assert neto_fifo([D("100.00"), D("-500.00"), D("50.00")]) == [D("0"), D("0"), D("0")]


def test_f150_r33_los_negativos_faltan_y_compensan_primero_lo_antiguo() -> None:
    # N = 130: compensa entera la primera (100) y 30 de la segunda (50 -> 20); la
    # cuarta, intacta. FIFO, no LIFO (LIFO dejaría 60 en la primera y 0 en las demás).
    assert neto_fifo([D("100.00"), D("50.00"), D("-130.00"), D("40.00")]) == [
        D("0"), D("20.00"), D("0"), D("40.00"),
    ]


def test_f150_r33_el_orden_manda_no_el_tamano() -> None:
    """Con los mismos importes en otro orden, el resto cae en la otra línea."""
    assert neto_fifo([D("10"), D("90"), D("-50")]) == [D("0"), D("50"), D("0")]
    assert neto_fifo([D("90"), D("10"), D("-50")]) == [D("40"), D("10"), D("0")]


def test_f150_r33_la_posicion_del_negativo_no_importa() -> None:
    """Σ |negativos| es del (obra, proveedor) entero: un abono de hoy compensa
    la entrega de hace un año (FIFO sobre las POSITIVAS)."""
    assert neto_fifo([D("-30"), D("100"), D("20")]) == [D("0"), D("70"), D("20")]
    assert neto_fifo([D("100"), D("20"), D("-30")]) == [D("70"), D("20"), D("0")]


def test_f150_r33_none_y_cero_dan_cero_y_no_compensan() -> None:
    assert neto_fifo([None, D("100"), D("0"), None, D("-40")]) == [
        D("0"), D("60"), D("0"), D("0"), D("0"),
    ]


def test_f150_r33_lista_vacia() -> None:
    assert neto_fifo([]) == []


def test_f150_r33_al_centimo() -> None:
    assert neto_fifo([D("0.01"), D("0.02"), D("-0.02")]) == [D("0"), D("0.01"), D("0")]
    assert neto_fifo([D("1234.56"), D("-1234.55")]) == [D("0.01"), D("0")]


@pytest.mark.parametrize("importes", [
    [D("100"), D("-30"), D("20.55"), D("-0.01"), D("7.45")],
    [D("-5"), D("-5"), D("3"), D("4")],
    [D("12.34"), None, D("-12.34"), D("0.66")],
    [D("1"), D("2"), D("3"), D("-10")],
    [D("0.01")] * 7 + [D("-0.03")],
])
def test_f150_r33_suma_es_max_cero_y_cada_resto_entre_cero_y_su_linea(importes) -> None:
    restos = neto_fifo(importes)
    assert len(restos) == len(importes)
    total = sum((x for x in importes if x is not None), D(0))
    assert sum(restos, D(0)) == max(D(0), total)
    for x, r in zip(importes, restos):
        tope = x if x is not None and x > 0 else D(0)
        assert D(0) <= r <= tope


def test_f150_r33_no_modifica_la_entrada() -> None:
    importes = [D("10"), D("-5")]
    neto_fifo(importes)
    assert importes == [D("10"), D("-5")]


def test_f150_r33_los_literales_del_sql() -> None:
    """`AC` = ALBARAN y `PROF` = PROFORMA (`compras.fn_tipo_documento`); NOTA (`NTC`)
    no lleva pendiente en las 21 obras. El umbral es el de `R-ALBARAN-ABSURDO`."""
    assert dom.SERIES_ALBARAN_PENDIENTE == ("AC", "PROF")
    assert dom.UMBRAL_IMPORTE_ABSURDO == 1e8


# ===========================================================================
# El SQL, leído como texto (R34, R35): literales = dominio
# ===========================================================================

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_SETUP = DIR_SQL / "tesoreria" / "00_setup.sql"
RUTA_ALBARANES = DIR_SQL / "tesoreria" / "09_albaranes_pendientes.sql"
RUTA_DEVENGO = DIR_SQL / "tesoreria" / "07_devengo_pendiente.sql"
RUTA_COMPRAS = DIR_SQL / "compras" / "01_documentos.sql"

#: Las columnas de la tabla nueva, en su orden (design.md §5.7).
COLUMNAS_ALBARANES = (
    "obra_id", "empresa_id", "clave_obra", "proveedor_id", "contrato_id", "mes_albaran",
    "importe_pendiente_bruto", "importe_sobrefacturado", "importe_compensado",
    "importe_pendiente_neto", "meses_antiguedad", "tras_cierre",
)


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


def _sin_comment_on(ruta: Path) -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(ruta))


def _caso_pendiente(texto: str) -> str:
    """El `CASE ... END` que acaba en `AS importe_pendiente_facturar`."""
    fin = texto.index("END AS importe_pendiente_facturar")
    inicio = texto.rindex("CASE WHEN COALESCE(l.can, 0) = 0", 0, fin)
    return texto[inicio:fin + len("END")]


def test_f150_r34_setup_crea_la_tabla_con_sus_columnas_y_tipos() -> None:
    texto = _ejecutable(RUTA_SETUP)
    m = re.search(r"CREATE TABLE IF NOT EXISTS tesoreria\.albaranes_pendientes_neto \((.*?)\);",
                  texto)
    assert m, "falta la tabla en 00_setup.sql"
    columnas = [c.strip().split(" ")[0] for c in re.split(r",(?![^()]*\))", m.group(1))]
    assert tuple(columnas) == COLUMNAS_ALBARANES
    for importe in COLUMNAS_ALBARANES[6:10]:
        assert re.search(rf"{importe} +NUMERIC\(18,2\) +NOT NULL", m.group(1)), importe
    assert re.search(r"mes_albaran +DATE", m.group(1))
    assert re.search(r"meses_antiguedad +INTEGER", m.group(1))
    assert re.search(r"tras_cierre +BOOLEAN +NOT NULL", m.group(1))


def test_f150_r34_setup_la_clave_con_nulls_not_distinct() -> None:
    """Sin proveedor, sin contrato o sin mes son claves válidas: `NULLS NOT
    DISTINCT` (precedente `retenciones.saldo_contable`)."""
    assert ("CREATE UNIQUE INDEX IF NOT EXISTS uq_tes_albaranes_pendientes_neto ON "
            "tesoreria.albaranes_pendientes_neto (obra_id, proveedor_id, contrato_id, "
            "mes_albaran) NULLS NOT DISTINCT;") in _ejecutable(RUTA_SETUP)


def test_f150_r34_la_formula_del_pendiente_es_la_de_compras_letra_a_letra() -> None:
    """Riesgo 7 del diseño: la fórmula vive en dos sitios y este test los ata."""
    assert _caso_pendiente(_ejecutable(RUTA_ALBARANES)) == _caso_pendiente(
        _ejecutable(RUTA_COMPRAS)
    )


def test_f150_r34_lee_raw_y_no_compras() -> None:
    """`compras` se construye DESPUÉS de `tesoreria`: leerla daría el pendiente
    de la víspera."""
    texto = _sin_comment_on(RUTA_ALBARANES)
    assert not re.search(r"\bcompras\.", texto)
    assert ("FROM raw.dcapro l JOIN raw.dca a ON a.ide = l.docide "
            "JOIN raw.con c ON c.ide = a.ide") in texto


def test_f150_r34_las_series_del_dominio() -> None:
    lista = ", ".join(f"'{s}'" for s in dom.SERIES_ALBARAN_PENDIENTE)
    assert f"tesoreria.fn_serie(c.cod) IN ({lista})" in _sin_comment_on(RUTA_ALBARANES)


def test_f150_r34_el_umbral_de_r_albaran_absurdo() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    assert float("1e8") == dom.UMBRAL_IMPORTE_ABSURDO
    assert "abs(x.tot) < 1e8" in texto
    assert "abs(x.pendiente) < 1e8" in texto
    assert "x.pendiente <> 0" in texto


def test_f150_r34_el_universo_son_las_obras_de_coste_del_corte() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    assert "FROM tesoreria.devengo_corte_obra k WHERE k.concepto = 'COSTE'" in texto
    assert "JOIN _alb_obra o ON o.obra_id = NULLIF(l.obride, 0)" in texto


def test_f150_r34_proveedor_contrato_y_fecha() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    assert "NULLIF(a.entide, 0) AS proveedor_id" in texto
    assert ("COALESCE(NULLIF(a.ctride, 0), CASE WHEN l.docoritip = 44 THEN "
            "NULLIF(l.docoriide, 0) END) AS contrato_id") in texto
    assert "tesoreria.fn_fecha(c.fec) AS fecha" in texto


def test_f150_r34_la_ventana_fifo_es_la_del_dominio() -> None:
    """`neto_fifo`: N = Σ |negativos| del (obra, proveedor), 0 sin proveedor; a
    cada positiva, min(p, máx(0, N − positivas anteriores)), en orden (fecha,
    línea)."""
    texto = _sin_comment_on(RUTA_ALBARANES)
    assert ("CASE WHEN x.proveedor_id IS NULL THEN 0 ELSE SUM(GREATEST(-x.pendiente, 0)) "
            "OVER (PARTITION BY x.obra_id, x.proveedor_id) END AS a_compensar") in texto
    assert ("SUM(GREATEST(x.pendiente, 0)) OVER (PARTITION BY x.obra_id, x.proveedor_id "
            "ORDER BY x.fecha NULLS FIRST, x.linea_id) AS acumulado") in texto
    assert ("CASE WHEN y.pendiente > 0 THEN LEAST(y.pendiente, GREATEST(0, y.a_compensar - "
            "(y.acumulado - y.pendiente))) ELSE 0 END AS compensado") in texto
    assert "GREATEST(y.pendiente, 0) AS bruto" in texto
    assert "GREATEST(-y.pendiente, 0) AS sobrefacturado" in texto


def test_f150_r34_el_insert_agrupa_por_la_clave_y_fecha_la_antiguedad() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    m = re.search(r"INSERT INTO tesoreria\.albaranes_pendientes_neto \((.*?)\) (SELECT .*?);",
                  texto)
    assert m, "falta el INSERT"
    assert tuple(c.strip() for c in m.group(1).split(",")) == COLUMNAS_ALBARANES
    select = m.group(2)
    assert "date_trunc('month', f.fecha)::DATE AS mes_albaran" in select
    assert "SUM(f.bruto - f.compensado) AS importe_pendiente_neto" in select
    assert ("(date_part('year', age(date_trunc('month', CURRENT_DATE), "
            "date_trunc('month', f.fecha))) * 12 + date_part('month', age(date_trunc('month', "
            "CURRENT_DATE), date_trunc('month', f.fecha))))::INTEGER AS meses_antiguedad") in select
    assert ("COALESCE(o.mes_ultimo_cierre IS NULL OR date_trunc('month', f.fecha)::DATE > "
            "o.mes_ultimo_cierre, FALSE) AS tras_cierre") in select
    assert "HAVING SUM(f.bruto) > 0 OR SUM(f.sobrefacturado) > 0" in select
    assert texto.index("TRUNCATE tesoreria.albaranes_pendientes_neto;") < texto.index(
        "INSERT INTO tesoreria.albaranes_pendientes_neto")


def test_f150_r35_la_guarda_va_despues_del_insert_y_cuenta() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    guarda = texto[texto.index("INSERT INTO tesoreria.albaranes_pendientes_neto"):]
    assert "RAISE EXCEPTION 'albaranes_pendientes: %" in guarda
    assert ("p.neto <> CASE WHEN p.proveedor_id IS NULL THEN p.bruto "
            "ELSE GREATEST(0, p.bruto - p.sobrefacturado) END") in guarda
    assert "f.compensado < 0 OR f.compensado > f.bruto" in guarda


def test_f150_r35_la_guarda_de_entrada_antes_de_nada() -> None:
    texto = _sin_comment_on(RUTA_ALBARANES)
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    for fuente in ("raw.dca", "raw.dcapro", "raw.con", "tesoreria.devengo_corte_obra"):
        assert f"to_regclass('{fuente}') IS NULL" in entrada
    assert "TRUNCATE" not in entrada


def test_f150_r34_comment_con_el_que_y_la_clave() -> None:
    m = re.search(r"COMMENT ON TABLE tesoreria\.albaranes_pendientes_neto IS '(.*?)';",
                  _ejecutable(RUTA_ALBARANES))
    assert m, "sin COMMENT"
    assert m.group(1).startswith("F-150.")
    assert "Clave: obra_id, proveedor_id, contrato_id, mes_albaran" in m.group(1)


def test_f150_r34_sin_drop_ni_grants() -> None:
    texto = _ejecutable(RUTA_ALBARANES).upper().replace("ON COMMIT DROP AS", "")
    assert "DROP " not in texto
    assert not re.search(r"\b(GRANT|REVOKE)\b", texto)


@pytest.mark.parametrize("columna", COLUMNAS_ALBARANES)
def test_f150_r34_ninguna_columna_es_de_caja(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna)


def test_f150_r34_el_sub_paso_va_al_final() -> None:
    from etl_sigrid.application.steps import build_tesoreria_step as paso

    ultimo = paso.SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file, ultimo.target_schema, ultimo.target_table) == (
        "albaranes_pendientes", "09_albaranes_pendientes.sql", "tesoreria",
        "albaranes_pendientes_neto",
    )


# ===========================================================================
# R36 · la parte de coste proporcional (CP) de la cartera de la obra (N12)
# ===========================================================================

COLUMNAS_CP = ("cartera_viva_coste_proporcional", "cartera_emitida_tras_cierre_coste_proporcional")


def _devengo() -> str:
    return _sin_comment_on(RUTA_DEVENGO)


def test_f150_r36_setup_las_dos_columnas_con_alter() -> None:
    texto = _ejecutable(RUTA_SETUP)
    for columna in COLUMNAS_CP:
        assert (f"ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS {columna} "
                "NUMERIC(18,2);") in texto


@pytest.mark.parametrize("columna", COLUMNAS_CP)
def test_f150_r36_ninguna_columna_cp_es_de_caja(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna)


def test_f150_r36_la_cuota_cp_por_las_partidas_de_la_factura() -> None:
    """Mismo criterio que el devengo: la categoría de la partida de cada línea de
    la factura del efecto; los importes de `raw.dcfpro` (double precision en
    Azure) se castean antes de sumar."""
    texto = _devengo()
    assert ("COALESCE(SUM(l.tot::NUMERIC(18, 2)) FILTER (WHERE dp.categoria = 'CP') / "
            "NULLIF(SUM(l.tot::NUMERIC(18, 2)), 0), 0) AS cuota_cp") in texto
    # La vista de partidas, MATERIALIZED (205 s sin ello, 10 s con ello, 29-10).
    assert ("WITH dp AS MATERIALIZED ( SELECT partida_id, categoria FROM "
            "mart.v_pbi_dim_partida )") in texto
    assert "FROM raw.dcfpro l LEFT JOIN dp ON dp.partida_id = NULLIF(l.paride, 0)" in texto
    assert re.findall(r"\bl\.tot\b(?!::NUMERIC\(18, 2\))", texto) == [], "tot de dcfpro sin cast"


def test_f150_r36_la_cartera_cp_con_los_mismos_filter_y_solo_en_coste() -> None:
    texto = _devengo()
    assert ("SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE e.estado_tesoreria = "
            "'PREVISTO' AND NOT e.previsto_antiguo) AS cartera_viva_cp") in texto
    assert ("SUM(e.importe * COALESCE(q.cuota_cp, 0)) FILTER (WHERE v.mes_ultimo_cierre IS NULL "
            "OR date_trunc('month', e.fecha_emision)::DATE > v.mes_ultimo_cierre) "
            "AS cartera_emitida_tras_cierre_cp") in texto
    assert "LEFT JOIN _dev_cuota_cp q ON q.documento_id = e.documento_id" in texto
    for columna, origen in zip(COLUMNAS_CP, ("cartera_viva_cp", "cartera_emitida_tras_cierre_cp")):
        assert (f"CASE WHEN v.concepto = 'COSTE' THEN ROUND(COALESCE(c.{origen}, 0), 2) END "
                f"AS {columna}") in texto


def test_f150_r36_la_guarda_de_entrada_exige_dcfpro() -> None:
    texto = _devengo()
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    assert "to_regclass('raw.dcfpro') IS NULL" in entrada


def test_f150_r36_el_comment_del_corte_dice_cp() -> None:
    m = re.search(r"COMMENT ON TABLE tesoreria\.devengo_corte_obra IS '(.*?)';",
                  _ejecutable(RUTA_DEVENGO))
    assert m
    assert "coste proporcional" in m.group(1) and "CP" in m.group(1)
