# tests/test_f150_iva_isp.py
"""
F-150 · N15, el IVA con inversión del sujeto pasivo (R41, T32).

H13 (el IVA efectivo de la compra) deja de ser solo el 5,5 % de la empresa: `08`
le da un valor SIGRID POR OBRA, cuota / base de las líneas de factura de compra
de la obra en los 12 meses hasta el build, si la base llega al umbral (0,5 M
EUR). La marca ISP de Sigrid es falsa en todas: se mide la cuota. El dominio
(`iva_efectivo_compra`) es el oráculo; el SQL dice lo mismo (sus literales).
"""

from __future__ import annotations

import re
from decimal import Decimal as D
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom

RAIZ = Path(__file__).resolve().parents[1]
RUTA_08 = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria" / "08_hipotesis_caja_obra.sql"


def _sin_comment_on(texto: str) -> str:
    return texto[: texto.index("COMMENT ON TABLE")] if "COMMENT ON TABLE" in texto else texto


def _sin_comentarios(texto: str) -> str:
    return "\n".join(linea.split("--")[0] for linea in texto.splitlines())


def _rama_h13() -> str:
    texto = _sin_comentarios(_sin_comment_on(RUTA_08.read_text(encoding="utf-8")))
    inicio = texto.rindex("UNION ALL", 0, texto.index("'H13'::VARCHAR(3) AS codigo"))
    fin = texto.index(") s ON s.obra_id", inicio)
    return texto[inicio:fin]


# ===========================================================================
# El dominio: iva_efectivo_compra
# ===========================================================================


def test_f150_r41_el_umbral_y_el_motivo() -> None:
    assert dom.UMBRAL_BASE_H13 == 500_000
    assert dom.MOTIVO_H13_COMPRAS == "Compras de la obra en 12 meses (cuota de IVA entre base)"


@pytest.mark.parametrize(("base", "cuota", "esperado"), [
    (D("15930000.00"), D("375948.00"), D("2.36")),      # la 0686, medida el 29-10
    (D("500000.00"), D("27500.00"), D("5.50")),          # justo en el umbral: cuenta
    (D("1000000.00"), D("210000.00"), D("21.00")),
    (D("1000000.00"), D("12345.00"), D("1.23")),         # 1,2345 -> 1,23
    (D("1000000.00"), D("12355.00"), D("1.24")),         # 1,2355 -> 1,24 (mitad arriba)
    (D("2000000.00"), D("-10000.00"), D("-0.50")),       # los abonos pesan con su signo
])
def test_f150_r41_cuota_entre_base_por_cien_a_dos_decimales(base, cuota, esperado) -> None:
    assert dom.iva_efectivo_compra(base, cuota) == esperado


@pytest.mark.parametrize(("base", "cuota"), [
    (D("499999.99"), D("100000.00")),   # bajo el umbral: DEFECTO
    (D("0"), D("0")),                   # sin compras
    (D("-600000.00"), D("-30000.00")),  # base negativa (abonos): no llega al umbral
    (None, D("1.00")),
])
def test_f150_r41_bajo_el_umbral_no_hay_valor(base, cuota) -> None:
    assert dom.iva_efectivo_compra(base, cuota) is None


def test_f150_r41_cuota_vacia_es_cero() -> None:
    assert dom.iva_efectivo_compra(D("600000"), None) == D("0.00")


# ===========================================================================
# `08`: la rama H13 SIGRID, con los literales del dominio
# ===========================================================================


def test_f150_r41_h13_es_codigo_sigrid_tras_h12() -> None:
    assert dom.CODIGOS_SIGRID == ("H09", "H10", "H11", "H12", "H13")
    texto = _sin_comment_on(RUTA_08.read_text(encoding="utf-8"))
    codigos = re.findall(r"'(H[0-9]{2})'::VARCHAR\(3\) AS codigo", texto)
    assert tuple(codigos) == dom.CODIGOS_SIGRID


def test_f150_r41_la_rama_lee_las_lineas_de_factura_de_la_obra() -> None:
    rama = _rama_h13()
    assert "FROM raw.dcfpro l JOIN raw.con c ON c.ide = l.docide" in rama
    assert "SELECT NULLIF(l.obride, 0) AS obra_id" in rama
    assert "WHERE x.obra_id IS NOT NULL" in rama


def test_f150_r41_los_double_de_sigrid_se_pasan_a_numeric() -> None:
    """LECCIÓN DEL 29-10: en Azure `tot` e `ivacuo` son `double precision`."""
    rama = _rama_h13()
    assert "SUM(COALESCE(l.tot, 0)::NUMERIC(18, 2)) AS base" in rama
    assert "SUM(COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)) AS cuota" in rama
    assert dom.UMBRAL_IMPORTE_ABSURDO == 1e8 and "abs(l.tot) < 1e8" in rama


def test_f150_r41_doce_meses_hasta_el_build_sin_aritmetica_de_fechas() -> None:
    rama = _rama_h13()
    assert "tesoreria.fn_fecha(c.fec) <= CURRENT_DATE" in rama
    assert "date_part('year', age(CURRENT_DATE, tesoreria.fn_fecha(c.fec))) = 0" in rama
    assert not re.search(r"\binterval\b", rama.lower())


def test_f150_r41_el_valor_y_el_umbral_son_los_del_dominio() -> None:
    rama = _rama_h13()
    assert (f"CASE WHEN x.base >= {dom.UMBRAL_BASE_H13} THEN "
            "to_jsonb(ROUND(100 * x.cuota / x.base, 2)) END AS valor") in rama
    assert f"'{dom.MOTIVO_H13_COMPRAS}' AS motivo" in rama


def test_f150_r41_la_cabecera_dice_que_lee_las_compras() -> None:
    cabecera = RUTA_08.read_text(encoding="utf-8").split("DO $$")[0]
    assert "raw.dcfpro y raw.con (H13, F-150 N15)" in cabecera
    assert "H13, el IVA efectivo de las compras de la obra" in cabecera
