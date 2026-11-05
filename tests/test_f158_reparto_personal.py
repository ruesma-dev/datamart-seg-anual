# tests/test_f158_reparto_personal.py
"""
F-158 · Hotfix: el personal del mes, por ACUMULADO sobre el pendiente ya
repartido (R1-R10).

Las nocturnas del 04-11 y del 05-11 fallaron en `build_tesoreria`: en
`_dev_reparto` (paso 5 de `07_devengo_pendiente.sql`) el pendiente y el personal
de cada partida se repartían en sus meses redondeando cada uno por su lado. Con
una cuota de personal de 0,999999 (1-0707, partida 392521) el último mes quedó
con 8.249,97 de pendiente y 8.250,02 de personal, el paso 5 bis publicó -0,05
sin contrato y la guarda R50 tumbó la transacción entera
(`progress/spec_F-158.md`).

Primero el dominio (`repartir_personal`, el oráculo); después el SQL de `07`
leído como texto (patrón de F-135) y las fichas del diccionario: ni red ni BBDD.
"""

from __future__ import annotations

import random
import re
import unicodedata
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import pendiente_personal, repartir_pendiente

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
RUTA_DEVENGO = (RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
                / "07_devengo_pendiente.sql")
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


def _mes(indice: int) -> date:
    """El mes `indice` contado desde 2026-11 (0 = 2026-11)."""
    total = 2026 * 12 + 10 + indice
    return date(total // 12, total % 12 + 1, 1)


# ===========================================================================
# El caso real: 1-0707, partida 392521 (CI.1.1), datos del 2026-11-05
# ===========================================================================
#
# `pendiente` 57.749,95; `cuota_personal` 0,999999 (partes 23.850,00 / real a
# origen 23.850,02) -> `pendiente_personal` 57.749,89. Perfil de 12 meses, de
# 2026-11 a 2027-10, con los cinco importes del diagnóstico en su orden: 3.264
# siete meses, 4.896, 8.976, 8.160, 4.080 y 8.160 (spec_F-158 §2; reconstruido
# con esos importes: es la única distribución que da los céntimos medidos en el
# último mes, 8.249,97 de pendiente y 8.250,02 de personal).

PENDIENTE_392521 = D("57749.95")
CUOTA_392521 = D("0.999999")
PLAN_392521 = [D("3264")] * 7 + [D("4896"), D("8976"), D("8160"), D("4080"), D("8160")]
PERFIL_392521 = [(_mes(i), plan) for i, plan in enumerate(PLAN_392521)]


def test_f158_r6_el_caso_tiene_los_numeros_del_diagnostico() -> None:
    assert len(PERFIL_392521) == 12
    assert PERFIL_392521[0][0] == date(2026, 11, 1)
    assert PERFIL_392521[-1][0] == date(2027, 10, 1)
    assert pendiente_personal(PENDIENTE_392521, CUOTA_392521) == D("57749.89")


def test_f158_r6_el_algoritmo_de_ayer_daba_el_negativo() -> None:
    """El RED, escrito: dos `repartir_pendiente` independientes (el paso 5 de
    `fbf43dd`) dejan el último mes con más personal que pendiente."""
    pp = pendiente_personal(PENDIENTE_392521, CUOTA_392521)
    pendiente = repartir_pendiente(PENDIENTE_392521, PERFIL_392521, _mes(0))
    personal = repartir_pendiente(pp, PERFIL_392521, _mes(0))
    assert pendiente[-1][1] == D("8249.97")
    assert personal[-1][1] == D("8250.02")
    assert pendiente[-1][1] - personal[-1][1] == D("-0.05")


def test_f158_r6_el_caso_1_0707_no_da_personal_mayor_que_pendiente() -> None:
    pp = pendiente_personal(PENDIENTE_392521, CUOTA_392521)
    reparto = repartir_pendiente(PENDIENTE_392521, PERFIL_392521, _mes(0))
    personal = dom.repartir_personal(reparto, PENDIENTE_392521, pp)
    assert [mes for mes, _ in personal] == [mes for mes, _, _ in reparto]
    for (mes, importe, _), (_, parte) in zip(reparto, personal, strict=True):
        assert D(0) <= parte <= importe, mes
    assert sum(parte for _, parte in personal) == pp
    # El último mes: el pendiente de siempre y un personal que no lo supera.
    assert reparto[-1][1] == D("8249.97")
    assert personal[-1][1] <= D("8249.97")


# ===========================================================================
# R1 · la fórmula, mes a mes
# ===========================================================================


def test_f158_r1_la_formula_por_acumulado() -> None:
    reparto = [(_mes(0), D("10.00"), False), (_mes(1), D("20.00"), False),
               (_mes(2), D("30.01"), False)]
    pendiente = D("60.01")
    pp = D("33.33")
    esperado = []
    anterior = D(0)
    acumulado = D(0)
    for mes, importe, _ in reparto:
        acumulado += importe
        hasta = (pp * acumulado / pendiente).quantize(D("0.01"), rounding="ROUND_HALF_UP")
        esperado.append((mes, hasta - anterior))
        anterior = hasta
    assert dom.repartir_personal(reparto, pendiente, pp) == esperado
    assert esperado == [(_mes(0), D("5.55")), (_mes(1), D("11.11")), (_mes(2), D("16.67"))]


def test_f158_r1_sin_pendiente_no_hay_reparto() -> None:
    assert dom.repartir_personal([], D(0), D(0)) == []


# ===========================================================================
# R2, R3 · invariantes con semilla fija
# ===========================================================================


def test_f158_r2_r3_invariantes() -> None:
    azar = random.Random(20261105)
    for _ in range(2000):
        meses = azar.randint(1, 24)
        perfil = [(_mes(i), D(azar.randint(1, 900_000)) / 100) for i in range(meses)]
        pendiente = D(azar.randint(1, 50_000_000)) / 100
        cuota = D(azar.randint(0, 1_000_000)) / 1_000_000
        if azar.random() < 0.2:
            cuota = azar.choice([D("0.999999"), D("0.999998"), D("0.000001"), D(1), D(0)])
        pp = pendiente_personal(pendiente, cuota)
        reparto = repartir_pendiente(pendiente, perfil, _mes(0))
        personal = dom.repartir_personal(reparto, pendiente, pp)
        assert len(personal) == len(reparto)
        for (mes, importe, _), (mes_p, parte) in zip(reparto, personal, strict=True):
            assert mes == mes_p
            assert D(0) <= parte <= importe, (pendiente, cuota, perfil)
        assert sum((parte for _, parte in personal), D(0)) == pp, (pendiente, cuota, perfil)


# ===========================================================================
# R4, R5 · cuota 1 y 0; sin perfil
# ===========================================================================


def test_f158_r4_cuota_uno_y_cero() -> None:
    pendiente = D("1234.57")
    perfil = [(_mes(i), D(p)) for i, p in enumerate(("1", "3", "7", "11"))]
    reparto = repartir_pendiente(pendiente, perfil, _mes(0))
    uno = dom.repartir_personal(reparto, pendiente, pendiente_personal(pendiente, D(1)))
    assert [parte for _, parte in uno] == [importe for _, importe, _ in reparto]
    cero = dom.repartir_personal(reparto, pendiente, pendiente_personal(pendiente, D(0)))
    assert [parte for _, parte in cero] == [D(0)] * len(reparto)


def test_f158_r5_sin_perfil_una_fila() -> None:
    pendiente = D("500.03")
    reparto = repartir_pendiente(pendiente, [], _mes(3))
    assert reparto == [(_mes(3), pendiente, True)]
    assert dom.repartir_personal(reparto, pendiente, D("499.99")) == [(_mes(3), D("499.99"))]


# ===========================================================================
# El SQL de `07` leído como texto (R7-R9)
# ===========================================================================


@cache
def _sql() -> str:
    return RUTA_DEVENGO.read_text(encoding="utf-8")


def _ejecutable() -> str:
    lineas = []
    for linea in _sql().splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return re.sub(r"\s+", " ", "\n".join(lineas))


def _paso_5() -> str:
    texto = _ejecutable()
    inicio = texto.index("CREATE TEMP TABLE _dev_reparto ON COMMIT DROP AS")
    return texto[inicio: texto.index("ANALYZE _dev_reparto;", inicio)]


def test_f158_r7_el_sql_sigue_al_dominio() -> None:
    paso = _paso_5()
    assert ("ROUND(q.pendiente_personal * q.acumulado / q.pendiente_partida, 2) - "
            "ROUND(q.pendiente_personal * (q.acumulado - q.importe) / q.pendiente_partida, 2) "
            "AS importe_personal") in paso
    assert ("SUM(x.importe) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id "
            "ORDER BY x.anio_mes) AS acumulado") in paso
    assert ", repartido_personal AS (" in paso
    assert "FROM repartido x" in paso
    assert "r.pendiente AS pendiente_partida" in paso
    # La rama del UNION ALL lee el personal por acumulado, no el de antes.
    assert "FROM repartido_personal r UNION ALL" in paso
    assert "FROM repartido r" not in paso
    # El reparto propio del personal, fuera.
    assert "r.pendiente_personal - (r.suma_partes_personal" not in paso
    assert "parte_personal" not in paso
    assert "suma_partes_personal" not in paso


def test_f158_r7_el_pendiente_y_los_coeficientes_no_cambian() -> None:
    paso = _paso_5()
    assert ("CASE WHEN r.desde_el_final = 1 THEN r.pendiente - (r.suma_partes - r.parte) "
            "ELSE r.parte END AS importe") in paso
    assert ("CASE WHEN r.desde_el_final = 1 THEN r.pendiente_con_coeficientes - "
            "(r.suma_partes_con_coef - r.parte_con_coef) ELSE r.parte_con_coef END "
            "AS importe_con_coef") in paso
    assert "WHERE d.pendiente > 0 AND d.total_perfil > 0" in paso
    assert "d.pendiente_personal AS importe_personal, TRUE AS es_retraso" in paso


def test_f158_r7_la_cabecera_lo_dice() -> None:
    cabecera = _sql()[: _sql().index("CREATE TEMP TABLE")]
    assert "por acumulado sobre el pendiente del mes (F-158)" in re.sub(r"\s*\n--\s*", " ", cabecera)


def test_f158_r8_un_mes_negativo_sigue_sin_contrato() -> None:
    """D2: un mes negativo del plan va entero sin contrato, como hoy (ya lo fija
    `test_f150_r49_*` en `tests/test_f150_contrato_compra.py`; aquí, solo que
    las dos condiciones siguen)."""
    texto = _ejecutable()
    assert "JOIN r ON r.obra_id = f.obra_id AND r.partida_id = f.partida_id AND r.importe_np > 0" in texto
    assert ("LEFT JOIN e ON e.obra_id = r.obra_id AND e.partida_id = r.partida_id AND "
            "r.importe_np > 0;") in texto


def test_f158_r9_las_guardas_no_cambian() -> None:
    texto = _ejecutable()
    # R14: la suma por (obra, concepto) iguala la de la partida, personal incluido.
    assert ("OR COALESCE(p.total_personal, 0) IS DISTINCT FROM COALESCE(m.total_personal, 0)"
            in texto)
    assert "RAISE EXCEPTION 'devengo_pendiente: el reparto de la obra % (%) suma % y la partida %" in texto
    # R50: el coste por contrato cuadra y no tiene negativos.
    assert ("SELECT count(*) INTO n_negativos FROM tesoreria.devengo_pendiente_contrato_mes "
            "WHERE importe_pendiente < 0;") in texto
    assert ("WHERE COALESCE(m.total, 0) IS DISTINCT FROM COALESCE(c.total, 0); "
            "IF n_obras > 0 OR n_negativos > 0 THEN") in texto
    # R58: los dos tramos suman el personal, fila a fila.
    assert ("WHERE concepto = 'COSTE' AND importe_personal_neto + importe_personal_irpf_ss "
            "IS DISTINCT FROM importe_pendiente_personal") in texto
    # Ni la cuota ni el pendiente de la partida.
    assert ("CASE WHEN d.concepto = 'COSTE' THEN ROUND(d.pendiente * d.cuota_personal, 2) END "
            "AS pendiente_personal") in texto
    assert ("WHEN pe.personal > 0 AND re.real_origen > 0 THEN LEAST(1, ROUND(pe.personal / "
            "re.real_origen, 6)) ELSE 0 END END AS cuota_personal") in texto


# ===========================================================================
# R10 · las fichas y la versión del diccionario
# ===========================================================================


def _plano(texto: str | None) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


@cache
def _tesoreria() -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / "tesoreria.yaml").read_text(encoding="utf-8"))


def _objeto(nombre: str) -> dict:
    datos = _tesoreria()
    objetos = datos.get("objetos", datos)
    return objetos[nombre]


def test_f158_r10_fichas() -> None:
    personal = _plano(_objeto("devengo_pendiente_obra_mes")["columnas"]
                      ["importe_pendiente_personal"]["significado"])
    assert "repartido por acumulado sobre `importe_pendiente`" in personal
    assert "nunca lo supera en un mes" in personal
    assert "f-158" in personal
    contrato = _plano(_objeto("devengo_pendiente_contrato_mes")["descripcion"])
    assert "la fila sin contrato solo es negativa por un mes negativo del plan" in contrato
    assert "f-158" in contrato


def test_f158_r10_version_72_con_su_nota() -> None:
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    cabecera, resto = texto.split("\nversion:", 1)
    assert int(resto.split()[0]) >= 72
    assert "# version 72 (F-158, 2026-11-05)" in cabecera


def test_f158_la_errata_de_postventa() -> None:
    texto = (DIR_DICCIONARIO / "postventa.yaml").read_text(encoding="utf-8")
    assert "lA MASCARA" not in texto
    assert "pero la máscara es heurística" in texto or "pero la mascara es heuristica" in texto
