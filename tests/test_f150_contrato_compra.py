# tests/test_f150_contrato_compra.py
"""
F-150 · El coste pendiente de la obra repartido por CONTRATO de compra (N17,
R48-R51; cuarta tanda, 31-10).

El devengo de coste del master no dice a qué proveedor se pagará; Sigrid sí
dice qué contratos de compra tienen cada partida (`raw.ctrpro.paride`) y
cuánto les queda por servir (`can` - `canser`). Lo ENLAZADO de una partida es
`min(pendiente sin personal, Σ pendiente de servir)`, repartido entre sus
contratos por su pendiente de servir; ese trozo se paga con la forma de pago,
los días y la retención DEL CONTRATO (H01, H04, H06), y el resto sigue con H02
(medido el 31-10: 48,90 de 112,85 M EUR en 21 obras, 43 %; 0686 1,64 de 2,39).

Primero el dominio (`fracciones_contrato`, `repartir_por_contratos`); después el
SQL de `00_setup` y `07` leído como texto: ni red ni BBDD.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import fracciones_contrato, repartir_por_contratos

D = Decimal


# ===========================================================================
# R48 · fracciones_contrato
# ===========================================================================


def test_f150_r48_sin_contratos_nada_enlazado() -> None:
    assert fracciones_contrato(D("1000"), {}) == {}


def test_f150_r48_pendiente_de_servir_cero_o_negativo_no_enlaza() -> None:
    """Lo ya servido no tiene pendiente: el contrato no se lleva nada."""
    assert fracciones_contrato(D("1000"), {7: D("0"), 8: D("0")}) == {}
    assert fracciones_contrato(D("1000"), {7: D("0"), 8: None}) == {}
    assert fracciones_contrato(D("1000"), {7: D("-5"), 8: D("400")}) == {8: D("0.4")}
    # Mutante superviviente de T44 (`ps >= 0`): el servido entero no aparece ni a 0.
    assert fracciones_contrato(D("1000"), {7: D("0"), 8: D("400")}) == {8: D("0.4")}


def test_f150_r48_un_pendiente_de_centimos_tambien_enlaza() -> None:
    """Mutante superviviente de T44 (`pendiente <= 1`): 0,50 EUR pendientes se enlazan."""
    assert fracciones_contrato(D("0.50"), {7: D("1")}) == {7: D("1")}


@pytest.mark.parametrize("pendiente", [D("0"), D("-10"), None])
def test_f150_r48_sin_pendiente_no_hay_fraccion(pendiente) -> None:
    assert fracciones_contrato(pendiente, {7: D("500")}) == {}


def test_f150_r48_lo_contratado_de_mas_no_es_devengo() -> None:
    """Pendiente de servir > pendiente: se enlaza TODO el pendiente, nada más."""
    assert fracciones_contrato(D("1000"), {7: D("5000")}) == {7: D("1")}


def test_f150_r48_lo_devengado_de_mas_no_tiene_contrato() -> None:
    """Pendiente de servir < pendiente: se enlaza lo de servir; el resto, H02."""
    assert fracciones_contrato(D("1000"), {7: D("250")}) == {7: D("0.25")}


def test_f150_r48_varios_contratos_por_su_pendiente_de_servir() -> None:
    f = fracciones_contrato(D("1000"), {7: D("300"), 9: D("100")})
    assert f == {7: D("0.3"), 9: D("0.1")}
    # Con más contratado que pendiente, se reparte el pendiente entero 3:1.
    f = fracciones_contrato(D("200"), {7: D("300"), 9: D("100")})
    assert f == {7: D("0.75"), 9: D("0.25")}
    assert sum(f.values()) == D("1")


def test_f150_r48_la_suma_de_fracciones_no_pasa_de_uno() -> None:
    for pendiente, ps in [(D("100"), {1: D("33"), 2: D("33"), 3: D("34")}),
                          (D("7"), {1: D("1"), 2: D("2"), 3: D("3")}),
                          (D("3"), {1: D("1"), 2: D("1"), 3: D("1")})]:
        f = fracciones_contrato(pendiente, ps)
        assert D("0") < sum(f.values()) <= D("1")


# ===========================================================================
# R48 · repartir_por_contratos
# ===========================================================================


def test_f150_r48_sin_fracciones_todo_sin_contrato() -> None:
    assert repartir_por_contratos(D("123.45"), {}) == {None: D("123.45")}


def test_f150_r48_un_contrato_parcial() -> None:
    assert repartir_por_contratos(D("1000.00"), {7: D("0.25")}) == {
        7: D("250.00"), None: D("750.00")}


def test_f150_r48_todo_enlazado_deja_resto_cero() -> None:
    assert repartir_por_contratos(D("100.00"), {7: D("0.75"), 9: D("0.25")}) == {
        7: D("75.00"), 9: D("25.00"), None: D("0.00")}


def test_f150_r48_los_centimos_por_acumulado() -> None:
    """Tres contratos a 1/3 de 100: 33,33 + 33,34 + 33,33 y resto 0 (Σ exacta)."""
    tercio = D(1) / D(3)
    r = repartir_por_contratos(D("100.00"), {1: tercio, 2: tercio, 3: tercio})
    assert r == {1: D("33.33"), 2: D("33.34"), 3: D("33.33"), None: D("0.00")}


def test_f150_r48_el_round_contrato_a_contrato_dejaria_resto_negativo() -> None:
    """0,335 + 0,335 + 0,329 de 1 EUR: el ROUND de cada uno da 0,34 + 0,34 + 0,33
    = 1,01 > 1. Por acumulado: 0,34 + 0,33 + 0,33 y resto 0."""
    f = {1: D("0.335"), 2: D("0.335"), 3: D("0.329")}
    r = repartir_por_contratos(D("1.00"), f)
    assert r == {1: D("0.34"), 2: D("0.33"), 3: D("0.33"), None: D("0.00")}


def test_f150_r48_el_orden_es_el_del_contrato() -> None:
    f = {9: D("0.5"), 3: D("0.5")}
    r = repartir_por_contratos(D("0.01"), f)
    # Acumulado en orden 3, 9: ROUND(0,005) = 0,01 para el 3 y 0 para el 9.
    assert r == {3: D("0.01"), 9: D("0.00"), None: D("0.00")}


@pytest.mark.parametrize(
    ("importe", "ps", "pendiente"),
    [
        (D("0.01"), {1: D("1"), 2: D("1")}, D("3")),
        (D("1234.57"), {1: D("13"), 2: D("17"), 3: D("19")}, D("100")),
        (D("99.99"), {1: D("1"), 2: D("2"), 3: D("3"), 4: D("4")}, D("7")),
        (D("0.00"), {1: D("5")}, D("10")),
        (D("50000000.00"), {1: D("0.01"), 2: D("12345678.9")}, D("12345680")),
    ],
)
def test_f150_r48_invariantes(importe, ps, pendiente) -> None:
    r = repartir_por_contratos(importe, fracciones_contrato(pendiente, ps))
    assert sum(r.values()) == importe, "Σ = importe exacto"
    assert all(v >= 0 for v in r.values()), "ningún trozo < 0"
    assert r[None] >= 0
    assert all(v == v.quantize(D("0.01")) for v in r.values()), "al céntimo"


@pytest.mark.parametrize("importe", [D("-0.11"), D("0.00"), D("-1234.56")])
def test_f150_r48_un_mes_negativo_o_cero_va_entero_sin_contrato(importe) -> None:
    """design §5.11 paso 3: solo se reparten los (partida, mes) con importe > 0.
    Un mes NEGATIVO del plan de V (medido el 31-10: la 1-0702, partida 387660,
    noviembre, -0,11) daría trozos negativos a cada contrato y R50 tumbaría la
    noche: va entero a la fila sin contrato."""
    assert repartir_por_contratos(importe, {1: D("0.5"), 2: D("0.25")}) == {None: importe}


def test_f150_r48_no_modifica_la_entrada() -> None:
    ps = {1: D("10"), 2: D("20")}
    f = fracciones_contrato(D("15"), ps)
    copia = dict(f)
    repartir_por_contratos(D("15.00"), f)
    assert ps == {1: D("10"), 2: D("20")} and f == copia


# ===========================================================================
# El SQL (R49, R50): literales = dominio
# ===========================================================================

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RUTA_SETUP = DIR_SQL / "tesoreria" / "00_setup.sql"
RUTA_DEVENGO = DIR_SQL / "tesoreria" / "07_devengo_pendiente.sql"

#: Las columnas de la tabla nueva, en su orden (design.md §5.11).
COLUMNAS_CONTRATO_MES = (
    "obra_id", "empresa_id", "clave_obra", "anio_mes", "categoria", "contrato_id",
    "importe_pendiente", "num_partidas",
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


def test_f150_r49_setup_crea_la_tabla_con_sus_columnas_y_tipos() -> None:
    m = re.search(r"CREATE TABLE IF NOT EXISTS tesoreria\.devengo_pendiente_contrato_mes "
                  r"\((.*?)\);", _ejecutable(RUTA_SETUP))
    assert m, "falta la tabla en 00_setup.sql"
    columnas = [c.strip().split(" ")[0] for c in re.split(r",(?![^()]*\))", m.group(1))]
    assert tuple(columnas) == COLUMNAS_CONTRATO_MES
    assert re.search(r"importe_pendiente +NUMERIC\(18,2\) +NOT NULL", m.group(1))
    assert re.search(r"anio_mes +DATE +NOT NULL", m.group(1))
    assert re.search(r"contrato_id +INTEGER,", m.group(1)), "NULL = sin contrato"


def test_f150_r49_setup_la_clave_con_nulls_not_distinct() -> None:
    assert ("CREATE UNIQUE INDEX IF NOT EXISTS uq_tes_devengo_pendiente_contrato_mes ON "
            "tesoreria.devengo_pendiente_contrato_mes (obra_id, anio_mes, categoria, "
            "contrato_id) NULLS NOT DISTINCT;") in _ejecutable(RUTA_SETUP)


def test_f150_r49_setup_el_corte_gana_lo_enlazado() -> None:
    assert ("ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS "
            "pendiente_enlazado_contrato NUMERIC(18,2);") in _ejecutable(RUTA_SETUP)


@pytest.mark.parametrize("columna", COLUMNAS_CONTRATO_MES + ("pendiente_enlazado_contrato",))
def test_f150_r49_ninguna_columna_es_de_caja(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna)


def test_f150_r49_lo_pendiente_de_servir_por_contrato_y_partida() -> None:
    """(Alias `cl`: `l.tot` es el de `raw.dcfpro` en la cuota CP.) Por (contrato, partida) y no por línea (las líneas se sirven cruzadas),
    suelo 0, `double precision` casteado, el umbral de `R-ALBARAN-ABSURDO`."""
    texto = _devengo()
    assert "CREATE TEMP TABLE _dev_ctr ON COMMIT DROP AS" in texto
    # Una línea sin cantidad (`can` 0) no dice qué se sirvió: cuenta entera como
    # no servida (el `COALESCE` de la segunda suma).
    assert ("GREATEST(0, SUM(cl.tot::NUMERIC(18, 2)) - COALESCE(SUM(cl.tot::NUMERIC(18, 2) * "
            "COALESCE(cl.canser, 0)::NUMERIC / NULLIF(cl.can::NUMERIC, 0)), 0)) AS pendiente_servir"
            ) in texto
    assert "abs(cl.tot) < 1e8" in texto and dom.UMBRAL_IMPORTE_ABSURDO == 1e8
    assert "NULLIF(cl.paride, 0) AS partida_id" in texto
    assert "FROM raw.ctrpro cl JOIN raw.ctr c ON c.ide = cl.docide" in texto
    assert "JOIN raw.con k ON k.ide = c.ide" in texto
    assert "GROUP BY v.obra_id, NULLIF(cl.paride, 0), c.ide" in texto


def test_f150_r49_misma_obra_vivos_y_con_condiciones() -> None:
    """Terminado (8) y Rescindido (9) fuera; la obra del contrato es la del
    devengo; solo contratos de `condiciones_contrato_compra` (H01 necesita su
    forma de pago)."""
    texto = _devengo()
    assert "JOIN _dev_version v ON v.obra_id = c.obride AND v.concepto = 'COSTE'" in texto
    assert "k.est NOT IN (8, 9)" in texto
    assert ("c.ide IN (SELECT contrato_id FROM tesoreria.condiciones_contrato_compra)"
            in texto)


def test_f150_r49_las_fracciones_como_el_dominio() -> None:
    """`fracciones_contrato`: solo ps > 0; enlazado = LEAST(np, S); f = enlazado
    / np x ps / S; sin np > 0, nada."""
    texto = _devengo()
    assert "WHERE x.pendiente_servir > 0" in texto
    assert ("LEAST(p.np, t.total_servir) / p.np * x.pendiente_servir / t.total_servir "
            "AS fraccion") in texto
    assert "p.np > 0" in texto
    # np = pendiente - personal, de las partidas de COSTE que no son CP.
    assert ("d.pendiente - COALESCE(d.pendiente_personal, 0) AS np" in texto)
    assert "COALESCE(dp.categoria, '') <> 'CP'" in texto


def test_f150_r49_el_reparto_por_acumulado_como_el_dominio() -> None:
    texto = _devengo()
    assert ("SUM(f.fraccion) OVER (PARTITION BY f.obra_id, f.partida_id, r.anio_mes "
            "ORDER BY f.contrato_id) AS acumulada") in texto
    assert ("ROUND(r.importe_np * a.acumulada, 2) - ROUND(r.importe_np * (a.acumulada - "
            "a.fraccion), 2) AS importe") in texto
    assert ("r.importe_np - COALESCE(ROUND(r.importe_np * e.total_fraccion, 2), 0) "
            "AS importe") in texto
    # Solo los (partida, mes) con importe > 0 van a contrato (design §5.11 paso 3);
    # un mes negativo o cero, entero a la fila sin contrato.
    assert "JOIN r ON r.obra_id = f.obra_id AND r.partida_id = f.partida_id AND r.importe_np > 0" in texto
    assert ("LEFT JOIN e ON e.obra_id = r.obra_id AND e.partida_id = r.partida_id "
            "AND r.importe_np > 0") in texto


def test_f150_r49_lo_repartido_es_el_mes_sin_personal() -> None:
    """Cada (partida, mes) del reparto de `07`: su importe menos su personal."""
    texto = _devengo()
    assert "rp.pendiente - COALESCE(rp.importe_personal, 0) AS importe_np" in texto


def test_f150_r49_truncate_e_insert_agrupado() -> None:
    texto = _devengo()
    tabla = "tesoreria.devengo_pendiente_contrato_mes"
    assert texto.index(f"TRUNCATE {tabla};") < texto.index(f"INSERT INTO {tabla} (")
    m = re.search(rf"INSERT INTO {re.escape(tabla)} \((.*?)\)", texto)
    assert m
    assert tuple(c.strip() for c in m.group(1).split(",")) == COLUMNAS_CONTRATO_MES
    assert "GROUP BY q.obra_id, q.anio_mes, q.categoria, q.contrato_id" in texto


def test_f150_r50_la_guarda_suma_y_negativos_antes_del_corte() -> None:
    """Σ por obra = Σ (importe_pendiente - personal) sin CP de la obra-mes, y
    ningún importe < 0; si no, RAISE con el recuento y la transacción entera
    (también la partida y la obra-mes) vuelve a la de ayer."""
    texto = _devengo()
    insert = texto.index("INSERT INTO tesoreria.devengo_pendiente_contrato_mes (")
    guarda = texto[texto.index("DO $$", insert):]
    guarda = guarda[: guarda.index("END $$;")]
    assert "tesoreria.devengo_pendiente_contrato_mes" in guarda
    assert ("SUM(importe_pendiente - COALESCE(importe_pendiente_personal, 0)) "
            "FILTER (WHERE categoria <> 'CP')") in guarda
    assert "importe_pendiente < 0" in guarda
    assert "RAISE EXCEPTION" in guarda and "IS DISTINCT FROM" in guarda
    assert texto.index("DO $$", insert) < texto.index("INSERT INTO tesoreria.devengo_corte_obra")


def test_f150_r49_el_corte_publica_lo_enlazado_solo_en_coste() -> None:
    texto = _devengo()
    assert ("CASE WHEN v.concepto = 'COSTE' THEN COALESCE(en.pendiente_enlazado_contrato, 0) END "
            "AS pendiente_enlazado_contrato") in texto
    assert ("SELECT obra_id, SUM(importe_pendiente) AS pendiente_enlazado_contrato FROM "
            "tesoreria.devengo_pendiente_contrato_mes WHERE contrato_id IS NOT NULL "
            "GROUP BY obra_id") in texto


def test_f150_r49_la_guarda_de_entrada_exige_los_contratos() -> None:
    texto = _devengo()
    entrada = texto[: texto.index("CREATE TEMP TABLE")]
    for objeto in ("raw.ctrpro", "raw.ctr", "raw.con", "tesoreria.condiciones_contrato_compra"):
        assert f"to_regclass('{objeto}') IS NULL" in entrada, objeto


def test_f150_r49_comment_de_la_tabla() -> None:
    m = re.search(r"COMMENT ON TABLE tesoreria\.devengo_pendiente_contrato_mes IS '(.*?)';",
                  _ejecutable(RUTA_DEVENGO))
    assert m
    for palabra in ("contrato", "H01", "H02", "personal", "CP", "Clave"):
        assert palabra in m.group(1), palabra
