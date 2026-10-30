# tests/test_f150_saldo.py
"""
F-150 · El saldo de partida (N14, R38-R40) y el IVA ya recuperado (N15, R43).

La caja de una obra no empieza en cero: lo cobrado menos lo pagado hasta hoy
(CON IVA, efectos REALIZADO) es el PASO 0 de la receta, SALDO. Es opcional (H28)
y los pagarés agrupados (AGR) pierden la obra: H29 elige entre contarlos por
sus ORIGINALES o por el AGR que conserva obra. Primero el catálogo (R39);
después el SQL de `10_saldo_partida.sql`, leído como texto (R38, R43).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import Hipotesis
from etl_sigrid.infrastructure.config import hipotesis_caja_yaml as lector

RAIZ = Path(__file__).resolve().parents[1]
RUTA_YAML = RAIZ / "config" / "hipotesis_caja.yaml"


def _catalogo() -> dict[str, Hipotesis]:
    leido = lector.cargar_hipotesis_caja(RUTA_YAML)
    assert leido.errores == []
    return {h.codigo: h for h in leido.catalogo}


def _texto(h: Hipotesis) -> str:
    return " ".join(f"{h.descripcion} {h.fuente_defecto}".split())


# ===========================================================================
# R39 · el paso SALDO, H28 y H29
# ===========================================================================


def test_f150_r39_saldo_es_el_primer_paso_y_son_ocho() -> None:
    assert dom.PASOS_RECETA[0] == "SALDO"
    assert len(dom.PASOS_RECETA) == 8
    assert dom.PASOS_RECETA[1:] == (
        "DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA", "CARTERA",
    )


def test_f150_r39_h28_el_saldo_de_partida_es_opcional() -> None:
    h = _catalogo()["H28"]
    assert (h.sentido, h.unidad, h.valor_defecto, h.opciones) == (
        "AMBOS", "OPCION", "CON_SALDO", ("CON_SALDO", "SIN_SALDO"),
    )
    assert (h.paso_receta, h.admite_obra, h.validado) == ("SALDO", True, False)
    assert h.ingrediente == "tesoreria.saldo_partida_obra"
    assert "CON IVA" in _texto(h) and "cartera vencida" in _texto(h)


def test_f150_r39_h29_los_agrupados_por_sus_originales() -> None:
    h = _catalogo()["H29"]
    assert (h.sentido, h.unidad, h.valor_defecto, h.opciones) == (
        "PAGO", "OPCION", "ORIGINALES", ("ORIGINALES", "AGR"),
    )
    assert (h.paso_receta, h.admite_obra, h.validado) == ("SALDO", True, False)
    assert h.ingrediente == "tesoreria.saldo_partida_obra"
    texto = _texto(h)
    assert "R-TESORERIA-ESTADO" in texto, "rompe la regla a proposito y se declara"
    assert "1,32" in texto and "0,27" in texto, "lo medido en la 0686"


def test_f150_r39_son_29_en_su_orden() -> None:
    # N15 suma H30 detras.
    assert list(_catalogo())[:29] == [f"H{n:02d}" for n in range(1, 30)]


# ===========================================================================
# R38 · `10_saldo_partida.sql` y su tabla, leídos como texto
# ===========================================================================

import re  # noqa: E402
from functools import cache  # noqa: E402

DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
RUTA_SETUP = DIR_SQL / "00_setup.sql"
RUTA_SALDO = DIR_SQL / "10_saldo_partida.sql"

#: Las columnas de la tabla, en su orden (design.md §5.9; N15 añade las de IVA).
COLUMNAS_SALDO = (
    "obra_id", "empresa_id", "clave_obra", "fecha_corte", "mes_ultimo_cierre",
    "cobrado_realizado", "pagado_realizado_sin_agr", "pagado_agr_con_obra",
    "agrupados_vencidos", "agrupados_pendientes", "cartera_viva_agr_con_obra",
    "pagado_coste_proporcional", "agrupados_vencidos_coste_proporcional",
    "personal_coste_partes",
    # N15 (R43): el IVA de lo pagado y lo cobrado, y cuanto ya volvio segun H30.
    "iva_soportado_pagado", "iva_repercutido_cobrado",
    "iva_soportado_pagado_hasta_4t", "iva_repercutido_cobrado_hasta_4t",
    "iva_soportado_pagado_hasta_4m", "iva_repercutido_cobrado_hasta_4m",
)


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _ejecutable(ruta: Path) -> str:
    lineas = [re.sub(r"\s--\s.*$", "", linea) for linea in _sql(ruta).splitlines()
              if not linea.lstrip().startswith("--")]
    return re.sub(r"\s+", " ", "\n".join(lineas))


def _saldo() -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(RUTA_SALDO))


def _insert() -> tuple[list[str], str]:
    m = re.search(r"INSERT INTO tesoreria\.saldo_partida_obra \((.*?)\) (SELECT .*?);", _saldo())
    assert m, "falta el INSERT"
    return [c.strip() for c in m.group(1).split(",")], m.group(2)


def test_f150_r38_setup_crea_la_tabla_con_sus_columnas() -> None:
    m = re.search(r"CREATE TABLE IF NOT EXISTS tesoreria\.saldo_partida_obra \((.*?)\);",
                  _ejecutable(RUTA_SETUP))
    assert m, "falta la tabla en 00_setup.sql"
    trozos = [c.strip() for c in re.split(r",(?![^()]*\))", m.group(1))]
    columnas = [c.split(" ")[0] for c in trozos if not c.startswith("PRIMARY KEY")]
    assert tuple(columnas[: len(COLUMNAS_SALDO)]) == COLUMNAS_SALDO
    assert "PRIMARY KEY (obra_id)" in m.group(1)
    for importe in COLUMNAS_SALDO[5:]:
        assert re.search(rf"{importe} +NUMERIC\(18,2\) +NOT NULL", m.group(1)), importe


def test_f150_r38_el_insert_en_el_orden_de_la_tabla() -> None:
    columnas, _select = _insert()
    assert tuple(columnas[: len(COLUMNAS_SALDO)]) == COLUMNAS_SALDO
    assert _saldo().index("TRUNCATE tesoreria.saldo_partida_obra;") < _saldo().index(
        "INSERT INTO tesoreria.saldo_partida_obra")


@pytest.mark.parametrize("columna", COLUMNAS_SALDO)
def test_f150_r38_ninguna_columna_es_de_caja(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna)


def test_f150_r38_el_universo_y_la_fecha_de_corte() -> None:
    texto = _saldo()
    assert "FROM tesoreria.devengo_corte_obra k WHERE k.concepto = 'COSTE'" in texto
    assert "CURRENT_DATE AS fecha_corte" in texto


def test_f150_r38_lo_realizado_sin_bajas_y_sin_agr() -> None:
    texto = _saldo()
    assert ("SUM(e.importe) FILTER (WHERE e.sentido = 'COBRO' AND e.estado_tesoreria = "
            "'REALIZADO') AS cobrado_realizado") in texto
    assert ("SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = "
            "'REALIZADO' AND e.serie_efecto IS DISTINCT FROM 'AGR') AS pagado_realizado_sin_agr") in texto
    assert ("SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = "
            "'REALIZADO' AND e.serie_efecto = 'AGR') AS pagado_agr_con_obra") in texto
    assert ("SUM(e.importe) FILTER (WHERE e.sentido = 'PAGO' AND e.estado_tesoreria = "
            "'PREVISTO' AND NOT e.previsto_antiguo AND e.serie_efecto = 'AGR') "
            "AS cartera_viva_agr_con_obra") in texto
    assert "FROM tesoreria.efectos e" in texto and "tesoreria_restringida" not in texto


def test_f150_r38_los_originales_agrupados_rompen_la_baja_a_proposito() -> None:
    """H29 `ORIGINALES`: los efectos de BAJA con `estado_codigo = 14` («Agrupados»)."""
    texto = _saldo()
    original = ("e.sentido = 'PAGO' AND e.estado_tesoreria = 'BAJA' AND "
                "e.estado_codigo = 14")
    assert (f"SUM(e.importe) FILTER (WHERE {original} AND e.fecha_vencimiento < "
            "CURRENT_DATE) AS agrupados_vencidos") in texto
    assert (f"SUM(e.importe) FILTER (WHERE {original} AND e.fecha_vencimiento >= "
            "CURRENT_DATE) AS agrupados_pendientes") in texto


def test_f150_r38_la_cuota_cp_como_en_07() -> None:
    texto = _saldo()
    assert ("COALESCE(SUM(l.tot::NUMERIC(18, 2)) FILTER (WHERE dp.categoria = 'CP') / "
            "NULLIF(SUM(l.tot::NUMERIC(18, 2)), 0), 0) AS cuota_cp") in texto
    assert "WITH dp AS MATERIALIZED ( SELECT partida_id, categoria FROM mart.v_pbi_dim_partida )" in texto
    assert re.findall(r"\bl\.tot\b(?!::NUMERIC\(18, 2\))", texto) == []


def test_f150_r38_el_personal_por_los_partes_hasta_el_cierre() -> None:
    """PERSONA (`res.cla = 1`) interna (sin proveedor), a su precio del parte,
    hasta el ultimo cierre: lo de despues ya es devengo pendiente."""
    texto = _saldo()
    assert "FROM raw.hmores h JOIN raw.res r ON r.ide = h.reside" in texto
    assert "r.cla = 1 AND COALESCE(r.prvide, 0) = 0" in texto
    assert "SUM(COALESCE(h.tot, 0)::NUMERIC(18, 2)) AS personal_coste_partes" in texto
    assert ("date_trunc('month', tesoreria.fn_fecha(h.fec))::DATE <= o.mes_ultimo_cierre"
            in texto)
    assert re.findall(r"\bh\.tot\b(?!, 0\)::NUMERIC\(18, 2\))", texto) == []


def test_f150_r38_la_guarda_de_entrada_antes_de_nada() -> None:
    texto = _saldo()
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    for fuente in ("raw.hmores", "raw.res", "raw.dcfpro", "tesoreria.efectos",
                   "tesoreria.devengo_corte_obra", "mart.v_pbi_dim_partida",
                   "raw.dcf", "raw.dvf"):
        assert f"to_regclass('{fuente}') IS NULL" in entrada, fuente
    assert "TRUNCATE" not in entrada


def test_f150_r38_sin_drop_ni_grants_ni_hipotesis() -> None:
    texto = _ejecutable(RUTA_SALDO).upper().replace("ON COMMIT DROP AS", "")
    assert "DROP " not in texto and not re.search(r"\b(GRANT|REVOKE)\b", texto)
    assert "hipotesis" not in _saldo().lower(), "el SQL no aplica H28 ni H29"


def test_f150_r38_comment_y_cabecera() -> None:
    assert _sql(RUTA_SALDO).startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/tesoreria/10_saldo_partida.sql")
    m = re.search(r"COMMENT ON TABLE tesoreria\.saldo_partida_obra IS '(.*?)';",
                  _ejecutable(RUTA_SALDO))
    assert m and m.group(1).startswith("F-150.") and "Clave: obra_id" in m.group(1)


def test_f150_r38_el_sub_paso_tras_los_albaranes() -> None:
    from etl_sigrid.application.steps import build_tesoreria_step as paso

    nombres = [s.name for s in paso.SUB_PASOS]
    i = nombres.index("saldo_partida")
    assert nombres[i - 1] == "albaranes_pendientes"
    sub = paso.SUB_PASOS[i]
    assert (sub.sql_file, sub.target_schema, sub.target_table) == (
        "10_saldo_partida.sql", "tesoreria", "saldo_partida_obra")


# ===========================================================================
# R43 · el IVA de lo pagado y lo cobrado (N15, T34)
# ===========================================================================


def test_f150_r43_la_fraccion_de_iva_de_cada_factura() -> None:
    """Pago: cuota / total a pagar de `raw.dcf`; cobro: cuota / total de `raw.dvf`.
    Los `double precision` de Sigrid pasan a NUMERIC (lección del 29-10)."""
    texto = _saldo()
    assert ("SELECT f.ide AS documento_id, 'PAGO'::VARCHAR(5) AS sentido, "
            "f.totiva::NUMERIC(18, 2) / NULLIF(f.totpag::NUMERIC(18, 2), 0) AS fraccion_iva "
            "FROM raw.dcf f") in texto
    assert ("SELECT v.ide AS documento_id, 'COBRO'::VARCHAR(5) AS sentido, "
            "v.totiva::NUMERIC(18, 2) / NULLIF(v.totdoc::NUMERIC(18, 2), 0) AS fraccion_iva "
            "FROM raw.dvf v") in texto
    assert ("LEFT JOIN _sal_iva_doc d ON d.documento_id = e.documento_id "
            "AND d.sentido = e.sentido") in texto


PAGADO = ("e.sentido = 'PAGO' AND (e.estado_tesoreria = 'REALIZADO' AND e.serie_efecto IS DISTINCT "
          "FROM 'AGR' OR e.estado_tesoreria = 'BAJA' AND e.estado_codigo = 14 AND "
          "e.fecha_vencimiento < CURRENT_DATE)")
COBRADO = "e.sentido = 'COBRO' AND e.estado_tesoreria = 'REALIZADO'"
HASTA_4T = "e.fecha_movimiento < date_trunc('year', CURRENT_DATE)::DATE"
HASTA_4M = ("(date_part('year', CURRENT_DATE) * 12 + date_part('month', CURRENT_DATE)) "
            "- (date_part('year', e.fecha_movimiento) * 12 + date_part('month', e.fecha_movimiento)) >= 4")


@pytest.mark.parametrize(("alias", "filtro"), [
    ("iva_soportado_pagado", PAGADO),
    ("iva_repercutido_cobrado", COBRADO),
    ("iva_soportado_pagado_hasta_4t", f"{PAGADO} AND {HASTA_4T}"),
    ("iva_repercutido_cobrado_hasta_4t", f"{COBRADO} AND {HASTA_4T}"),
    ("iva_soportado_pagado_hasta_4m", f"{PAGADO} AND {HASTA_4M}"),
    ("iva_repercutido_cobrado_hasta_4m", f"{COBRADO} AND {HASTA_4M}"),
])
def test_f150_r43_cada_iva_con_su_filtro(alias: str, filtro: str) -> None:
    assert (f"SUM(e.importe * COALESCE(d.fraccion_iva, 0)) FILTER (WHERE {filtro}) "
            f"AS {alias}") in _saldo()
    assert f"ROUND(COALESCE(s.{alias}, 0), 2) AS {alias}" in _saldo()


def test_f150_r43_la_fecha_del_movimiento() -> None:
    """Lo realizado, en su fecha real (o su vencimiento); el original agrupado, en su vencimiento."""
    assert ("CASE WHEN e.estado_tesoreria = 'REALIZADO' THEN COALESCE(e.fecha_real, "
            "e.fecha_vencimiento) ELSE e.fecha_vencimiento END AS fecha_movimiento") in _saldo()


def test_f150_r43_el_sql_no_elige_h30() -> None:
    """Las tres opciones de H30 tienen su columna; elegir es de la receta."""
    texto = _saldo()
    for opcion in ("MENSUAL_REDEME", "COMPENSA_EMPRESA", "ANUAL"):
        assert opcion not in texto
