# tests/test_f150_personal.py
"""
F-150 · El personal del devengo de COSTE, pagado el último día del mes de su
devengo (N16, R44-R47; cuarta tanda, 31-10).

El humano: «el pago de salarios es a fin de mes siempre». El devengo de la
última versión master no separa el personal propio del resto del coste; se
identifica POR PARTIDA con su historia: Σ coste de los partes (`raw.hmores.tot`
de recursos PERSONA internos, el filtro de `10_saldo_partida.sql`) hasta el
cierre entre lo real a origen de la partida, con tope 1 (medido el 31-10: 11,44
de 11,65 M EUR de partes caen en 248 partidas CI con cuota ~1).

Primero el dominio (`cuota_personal`, el oráculo); después el SQL de `07` leído
como texto (literales = dominio, patrón de F-135): ni red ni BBDD.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import cuota_personal, fuente_personal, pendiente_personal

D = Decimal


# ===========================================================================
# R44 · cuota_personal: partes / real de la partida, tope 1, a 6 decimales
# ===========================================================================


def test_f150_r44_cuota_es_partes_entre_real() -> None:
    assert cuota_personal(D("250"), D("1000")) == D("0.250000")


def test_f150_r44_redondea_a_seis_decimales_la_mitad_lejos_del_cero() -> None:
    # 1 / 3 = 0,3333333... -> 0,333333; 2 / 3 -> 0,666667 (ROUND de PostgreSQL)
    assert cuota_personal(D("1"), D("3")) == D("0.333333")
    assert cuota_personal(D("2"), D("3")) == D("0.666667")
    # 0,0000005 exacto: la mitad sube (ROUND_HALF_UP), no al par.
    assert cuota_personal(D("0.5"), D("1000000")) == D("0.000001")


def test_f150_r44_tope_uno_partes_editados_tras_el_cierre() -> None:
    """Cuota ~1,00-1,09 medida: la diferencia es la edición de partes tras el
    cierre; el personal nunca es más que la partida."""
    assert cuota_personal(D("1090"), D("1000")) == D("1")
    assert cuota_personal(D("1000"), D("1000")) == D("1")


@pytest.mark.parametrize(
    ("personal", "real"),
    [
        (D("0"), D("1000")),       # sin partes
        (D("100"), D("0")),        # partes sin real (3 partidas medidas): no se divide
        (D("100"), D("-50")),      # real negativo (abonos): no hay cuota
        (D("-10"), D("1000")),     # partes negativos (rectificados): no hay cuota
        (None, D("1000")),
        (D("100"), None),
        (None, None),
    ],
)
def test_f150_r44_sin_los_dos_positivos_la_cuota_es_cero(personal, real) -> None:
    assert cuota_personal(personal, real) == D("0")


def test_f150_r44_la_cuota_esta_entre_cero_y_uno() -> None:
    for p, r in [(D("1"), D("7")), (D("7"), D("1")), (D("0.01"), D("99999999.99"))]:
        assert D("0") <= cuota_personal(p, r) <= D("1")


def test_f150_r44_pendiente_personal_al_centimo() -> None:
    assert pendiente_personal(D("1000.00"), D("0.333333")) == D("333.33")
    # 0,005 exacto sube (ROUND de PostgreSQL).
    assert pendiente_personal(D("0.01"), D("0.5")) == D("0.01")
    assert pendiente_personal(D("123.45"), D("0")) == D("0.00")
    assert pendiente_personal(D("123.45"), D("1")) == D("123.45")


def test_f150_r44_las_fuentes_del_personal() -> None:
    assert dom.FUENTES_PERSONAL == ("PARTES", "SIN_PARTES", "CP")


def test_f150_r44_fuente_cp_manda_aunque_tenga_partes() -> None:
    """El CP entero queda fuera de la caja de la obra, también su personal (0,11
    M EUR medidos, decisión (d) del spec-author)."""
    assert fuente_personal("CP", D("500")) == "CP"
    assert fuente_personal("CP", None) == "CP"


def test_f150_r44_fuente_partes_o_sin_partes() -> None:
    assert fuente_personal("CI", D("500")) == "PARTES"
    assert fuente_personal("CD", D("0.01")) == "PARTES"
    assert fuente_personal("CI", D("0")) == "SIN_PARTES"
    assert fuente_personal("CI", None) == "SIN_PARTES"
    assert fuente_personal(None, D("-3")) == "SIN_PARTES"
    for categoria, personal in [("CP", D("1")), ("CI", D("1")), ("CI", None)]:
        assert fuente_personal(categoria, personal) in dom.FUENTES_PERSONAL


# ===========================================================================
# El SQL de `07`, leído como texto (R45, R46): literales = dominio
# ===========================================================================

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_SETUP = DIR_SQL / "tesoreria" / "00_setup.sql"
RUTA_DEVENGO = DIR_SQL / "tesoreria" / "07_devengo_pendiente.sql"
RUTA_SALDO = DIR_SQL / "tesoreria" / "10_saldo_partida.sql"

#: Columnas nuevas por tabla, con su tipo (design.md §5.10).
COLUMNAS_PARTIDA = (
    ("cuota_personal", "NUMERIC(12,6)"),
    ("pendiente_personal", "NUMERIC(18,2)"),
    ("fuente_personal", "VARCHAR(12)"),
)
COLUMNAS_OBRA_MES = (("importe_pendiente_personal", "NUMERIC(18,2)"),)
COLUMNAS_CORTE = (
    ("pendiente_personal", "NUMERIC(18,2)"),
    ("pendiente_enlazado_contrato", "NUMERIC(18,2)"),
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


def _devengo() -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(RUTA_DEVENGO))


@pytest.mark.parametrize(
    ("tabla", "columna", "tipo"),
    [("devengo_pendiente_partida", c, t) for c, t in COLUMNAS_PARTIDA]
    + [("devengo_pendiente_obra_mes", c, t) for c, t in COLUMNAS_OBRA_MES]
    + [("devengo_corte_obra", c, t) for c, t in COLUMNAS_CORTE],
)
def test_f150_r45_setup_las_columnas_con_alter(tabla: str, columna: str, tipo: str) -> None:
    assert (f"ALTER TABLE tesoreria.{tabla} ADD COLUMN IF NOT EXISTS {columna} {tipo};"
            in _ejecutable(RUTA_SETUP))


@pytest.mark.parametrize(
    "columna", [c for c, _t in COLUMNAS_PARTIDA + COLUMNAS_OBRA_MES + COLUMNAS_CORTE]
)
def test_f150_r45_ninguna_columna_es_de_caja(columna: str) -> None:
    """Es devengo: ni una fecha de pago ni un importe con IVA (R13)."""
    assert not dom.es_columna_de_caja(columna)


def _filtro_personal(texto: str) -> str:
    """El `WHERE` de los partes de personal: de `WHERE r.cla` a `<= ... cierre`."""
    m = re.search(r"WHERE (r\.cla = 1 AND COALESCE\(r\.prvide, 0\) = 0 AND .*?"
                  r"<= [a-z]+\.mes_ultimo_cierre)", texto)
    assert m, "no está el filtro de los partes de personal"
    return re.sub(r"\b[a-z]+\.mes_ultimo_cierre", "X.mes_ultimo_cierre", m.group(1))


def test_f150_r45_el_personal_con_el_filtro_de_10_letra_a_letra() -> None:
    """PERSONA interna (`res.cla = 1`, sin proveedor) y hasta el cierre: el mismo
    personal que el saldo de partida (N14); los dos sitios los ata este test."""
    assert _filtro_personal(_devengo()) == _filtro_personal(_ejecutable(RUTA_SALDO))


def test_f150_r45_el_personal_por_partida_y_con_cast() -> None:
    """`raw.hmores.tot` es `double precision` en Azure: `::NUMERIC` antes de sumar."""
    texto = _devengo()
    assert "CREATE TEMP TABLE _dev_personal ON COMMIT DROP AS" in texto
    assert "SUM(COALESCE(h.tot, 0)::NUMERIC(18, 2)) AS personal" in texto
    assert "NULLIF(h.paride, 0) AS partida_id" in texto
    assert "FROM raw.hmores h JOIN raw.res r ON r.ide = h.reside" in texto
    assert re.findall(r"\bh\.tot\b(?!, 0\)::NUMERIC\(18, 2\))", texto) == [], "tot sin cast"


def test_f150_r45_lo_real_a_origen_tambien_en_coste() -> None:
    """`_dev_real` pasa a los dos conceptos (misma fuente que `real_origen_corte`)."""
    texto = _devengo()
    m = re.search(r"CREATE TEMP TABLE _dev_real ON COMMIT DROP AS (.*?);", texto)
    assert m
    assert "v.concepto" in m.group(1) and "GROUP BY v.obra_id, v.concepto, f.partida_id" in m.group(1)
    assert "WHERE v.concepto = 'VENTA'" not in m.group(1)


def test_f150_r45_la_cuota_es_la_del_dominio() -> None:
    """Literal de `cuota_personal`: los dos > 0, `LEAST(1, ROUND(p / r, 6))`; CP, 0."""
    texto = _devengo()
    assert ("CASE WHEN dp.categoria = 'CP' THEN 0 WHEN pe.personal > 0 AND re.real_origen > 0 "
            "THEN LEAST(1, ROUND(pe.personal / re.real_origen, 6)) ELSE 0 END") in texto


def test_f150_r45_la_fuente_es_la_del_dominio() -> None:
    texto = _devengo()
    assert ("CASE WHEN dp.categoria = 'CP' THEN 'CP' WHEN pe.personal > 0 THEN 'PARTES' "
            "ELSE 'SIN_PARTES' END") in texto
    for fuente in dom.FUENTES_PERSONAL:
        assert f"'{fuente}'" in texto


def test_f150_r45_pendiente_personal_redondeado_y_solo_en_coste() -> None:
    texto = _devengo()
    assert "ROUND(d.pendiente * d.cuota_personal, 2) AS pendiente_personal" in texto
    # En VENTA las tres columnas van NULL: se calculan solo para COSTE.
    assert "AND d.concepto = 'COSTE'" in texto


def test_f150_r46_el_reparto_lleva_la_parte_de_personal() -> None:
    """Mismo patrón que la parte con coeficientes: el último mes absorbe el
    redondeo; sin perfil, entero al primer mes pendiente."""
    texto = _devengo()
    assert ("ROUND(d.pendiente_personal * pr.importe_mes / d.total_perfil, 2) AS parte_personal"
            in texto)
    assert ("CASE WHEN r.desde_el_final = 1 THEN r.pendiente_personal - (r.suma_partes_personal - "
            "r.parte_personal) ELSE r.parte_personal END AS importe_personal") in texto
    assert ("SUM(x.parte_personal) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id) "
            "AS suma_partes_personal") in texto
    assert "d.pendiente_personal AS importe_personal" in texto


def test_f150_r46_la_obra_mes_publica_el_personal_solo_en_coste() -> None:
    texto = _devengo()
    assert ("CASE WHEN x.concepto = 'COSTE' THEN COALESCE(x.importe_personal, 0) END "
            "AS importe_pendiente_personal") in texto


def test_f150_r46_la_guarda_de_la_suma_mira_el_personal() -> None:
    texto = _devengo()
    assert "SUM(pendiente_personal) AS total_personal" in texto
    assert "SUM(importe_pendiente_personal) AS total_personal" in texto
    assert ("OR COALESCE(p.total_personal, 0) IS DISTINCT FROM COALESCE(m.total_personal, 0)"
            in texto)


def test_f150_r46_el_corte_publica_el_personal_solo_en_coste() -> None:
    texto = _devengo()
    assert "SUM(d.pendiente_personal) AS pendiente_personal" in texto
    assert ("CASE WHEN v.concepto = 'COSTE' THEN COALESCE(s.pendiente_personal, 0) END "
            "AS pendiente_personal") in texto


def test_f150_r45_la_guarda_de_entrada_exige_res_y_hmores() -> None:
    texto = _devengo()
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    assert "to_regclass('raw.res') IS NULL" in entrada
    assert "to_regclass('raw.hmores') IS NULL" in entrada


def test_f150_r45_los_comment_dicen_el_personal() -> None:
    texto = _ejecutable(RUTA_DEVENGO)
    for tabla in ("devengo_pendiente_partida", "devengo_pendiente_obra_mes", "devengo_corte_obra"):
        m = re.search(rf"COMMENT ON TABLE tesoreria\.{tabla} IS '(.*?)';", texto)
        assert m, tabla
        assert "personal" in m.group(1).lower(), tabla
        assert "fin de mes" in m.group(1).lower() or "ultimo dia" in m.group(1).lower(), tabla
