# tests/test_f159_reparto_envolvente.py
"""
F-159 · Hotfix 2: el pendiente de la partida, repartido por ACUMULADO sobre la
ENVOLVENTE del plan neto de V (R1-R12).

La nocturna del 07-11 falló en `build_tesoreria` (guarda R50): la V13 de 1-0710
trae en la partida 404326 un plan de -1.079,94 en 2026-11 y +1.080,00 en
2026-12 (un 0 intermedio del `planif`, estorno legítimo de `stg`). El paso 5 de
`07_devengo_pendiente.sql` repartía con pesos CON SIGNO: `total_perfil` 0,06 y
noviembre recibía -19.438.920,00 (`progress/spec_F-159.md`).

Primero el dominio (`repartir_pendiente`, el oráculo); después el SQL de `07`
leído como texto (patrón de F-135/F-158) y las fichas del diccionario: ni red
ni BBDD.
"""

from __future__ import annotations

import random
import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
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
NOV, DIC = date(2026, 11, 1), date(2026, 12, 1)


def _mes(indice: int) -> date:
    """El mes `indice` contado desde 2026-11 (0 = 2026-11)."""
    total = 2026 * 12 + 10 + indice
    return date(total // 12, total % 12 + 1, 1)


def _reparto_de_ayer(pendiente: Decimal, perfil: list[tuple[date, Decimal]],
                     primer_mes: date) -> list[tuple[date, Decimal, bool]]:
    """Copia PRIVADA del `repartir_pendiente` de `93fc38c`: pesos con signo,
    cada mes redondeado por su lado y el resto al último. Es el RED, escrito."""
    if pendiente == 0:
        return []
    meses = sorted((mes, plan) for mes, plan in perfil if plan != 0)
    total = sum((plan for _mes, plan in meses), D(0))
    if not meses or total <= 0:
        return [(primer_mes, pendiente, True)]
    reparto = []
    acumulado = D(0)
    for mes, plan in meses[:-1]:
        importe = (pendiente * plan / total).quantize(D("0.01"), rounding=ROUND_HALF_UP)
        acumulado += importe
        reparto.append((mes, importe, False))
    reparto.append((meses[-1][0], pendiente - acumulado, False))
    return reparto


def _importes(reparto: list[tuple[date, Decimal, bool]]) -> list[Decimal]:
    return [importe for _mes, importe, _r in reparto]


# ===========================================================================
# R6 · el caso real: 1-0710, partida 404326 (03.02.11), datos del 2026-11-07
# ===========================================================================

PENDIENTE_404326 = D("1080.00")
PERFIL_404326 = [(NOV, D("-1079.94")), (DIC, D("1080.00"))]


def test_f159_r6_el_caso_1_0710() -> None:
    reparto = repartir_pendiente(PENDIENTE_404326, PERFIL_404326, NOV)
    assert reparto == [(NOV, D("0.00"), False), (DIC, D("1080.00"), False)]


def test_f159_r6_el_algoritmo_de_ayer_amplificaba() -> None:
    """El RED, escrito: con pesos con signo, `total_perfil` 0,06 amplifica."""
    reparto = _reparto_de_ayer(PENDIENTE_404326, PERFIL_404326, NOV)
    assert reparto == [(NOV, D("-19438920.00"), False), (DIC, D("19440000.00"), False)]
    assert sum(_importes(reparto)) == PENDIENTE_404326, "R14 pasaba: por eso cayó en R50"


# ===========================================================================
# R1 · la envolvente absorbe un mes negativo hacia atrás
# ===========================================================================


def test_f159_r1_la_envolvente_absorbe_hacia_atras() -> None:
    p = D("60.00")
    tres = lambda a, b, c: [(_mes(0), D(a)), (_mes(1), D(b)), (_mes(2), D(c))]  # noqa: E731
    assert _importes(repartir_pendiente(p, tres(100, -100, 100), _mes(0))) == [
        D("0.00"), D("0.00"), D("60.00")]
    assert _importes(repartir_pendiente(p, tres(100, -40, 60), _mes(0))) == [
        D("30.00"), D("0.00"), D("30.00")]
    assert repartir_pendiente(p, [(_mes(0), D(-50)), (_mes(1), D(150))], _mes(0)) == [
        (_mes(0), D("0.00"), False), (_mes(1), D("60.00"), False)]


def test_f159_r1_un_negativo_al_final_tambien_se_absorbe() -> None:
    """Plan 100, 100, -50: lo neto (150) se reparte 100 / 50 / 0."""
    perfil = [(_mes(0), D(100)), (_mes(1), D(100)), (_mes(2), D(-50))]
    assert _importes(repartir_pendiente(D("150.00"), perfil, _mes(0))) == [
        D("100.00"), D("50.00"), D("0.00")]


def test_f159_r1_el_minimo_mira_hacia_delante_no_hacia_atras() -> None:
    """Plan 50, -10, 30, -60, 100: acumulado 50, 40, 70, 10, 110; envolvente
    10, 10, 10, 10, 110. Sin el suelo hacia delante, el tercer mes (70) se
    llevaría más de lo que queda neto tras el estorno del cuarto."""
    perfil = [(_mes(i), D(v)) for i, v in enumerate((50, -10, 30, -60, 100))]
    assert _importes(repartir_pendiente(D("110.00"), perfil, _mes(0))) == [
        D("10.00"), D("0.00"), D("0.00"), D("0.00"), D("100.00")]


def test_f159_r1_suelo_cero_y_desorden() -> None:
    """Un acumulado negativo intermedio no da peso negativo, venga como venga."""
    perfil = [(_mes(2), D(80)), (_mes(0), D(-20)), (_mes(1), D(40))]
    assert repartir_pendiente(D("100.00"), perfil, _mes(0)) == [
        (_mes(0), D("0.00"), False), (_mes(1), D("20.00"), False),
        (_mes(2), D("80.00"), False)]


# ===========================================================================
# R2 · por acumulado: el redondeo se reparte, no se queda en el último mes
# ===========================================================================


def test_f159_r2_la_formula_por_acumulado() -> None:
    """100 / 3: A = 33,33, 66,67 y 100 -> 33,33 / 33,34 / 33,33."""
    perfil = [(_mes(i), D(1)) for i in range(3)]
    assert _importes(repartir_pendiente(D("100"), perfil, _mes(0))) == [
        D("33.33"), D("33.34"), D("33.33")]


def test_f159_r2_multiplica_antes_de_dividir_como_el_sql() -> None:
    """0,17 x 0,13 / 0,26 = 0,085 exacto (ROUND -> 0,09); al revés, 0,0849..."""
    perfil = [(_mes(0), D("0.13")), (_mes(1), D("0.13"))]
    assert _importes(repartir_pendiente(D("0.17"), perfil, _mes(0))) == [D("0.09"), D("0.08")]


def test_f159_r2_el_ultimo_mes_es_el_pendiente_sin_redondear() -> None:
    assert _importes(repartir_pendiente(D("10.005"), [(_mes(0), D(1)), (_mes(1), D(1))],
                                        _mes(0))) == [D("5.00"), D("5.005")]


# ===========================================================================
# R3 + R7 · invariantes con semilla fija y perfiles CON SIGNO
# ===========================================================================


def _perfil_con_signo(azar: random.Random) -> list[tuple[date, Decimal]]:
    while True:
        meses = azar.randint(1, 24)
        perfil = []
        for i in range(meses):
            valor = D(azar.randint(-900_000, 900_000)) / 100
            if azar.random() < 0.15:
                valor = D(0)
            perfil.append((_mes(i), valor))
        if sum((v for _m, v in perfil), D(0)) > 0:
            return perfil


def test_f159_r3_r7_invariantes() -> None:
    azar = random.Random(20261107)
    for _ in range(2000):
        perfil = _perfil_con_signo(azar)
        pendiente = D(azar.randint(1, 50_000_000)) / 100
        cuota = D(azar.randint(0, 1_000_000)) / 1_000_000
        if azar.random() < 0.2:
            cuota = azar.choice([D("0.999999"), D("0.000001"), D(1), D(0)])
        reparto = repartir_pendiente(pendiente, perfil, _mes(0))
        caso = (pendiente, perfil)
        assert [m for m, _i, _r in reparto] == sorted(m for m, v in perfil if v != 0), caso
        for _mes_r, importe, retraso in reparto:
            assert D(0) <= importe <= pendiente, caso
            assert importe == importe.quantize(D("0.01")), caso
            assert retraso is False
        assert sum(_importes(reparto), D(0)) == pendiente, caso
        pp = pendiente_personal(pendiente, cuota)
        personal = dom.repartir_personal(reparto, pendiente, pp)
        for (_m, importe, _r), (_n, parte) in zip(reparto, personal, strict=True):
            assert D(0) <= parte <= importe, (caso, cuota)
        assert sum((parte for _n, parte in personal), D(0)) == pp, (caso, cuota)


# ===========================================================================
# R4 · sin meses negativos, solo cambia el redondeo
# ===========================================================================


def test_f159_r4_sin_negativos_solo_cambia_el_redondeo() -> None:
    azar = random.Random(4)
    for _ in range(2000):
        perfil = [(_mes(i), D(azar.randint(1, 900_000)) / 100) for i in range(azar.randint(1, 24))]
        pendiente = D(azar.randint(1, 50_000_000)) / 100
        nuevo = _importes(repartir_pendiente(pendiente, perfil, _mes(0)))
        viejo = _importes(_reparto_de_ayer(pendiente, perfil, _mes(0)))
        assert len(nuevo) == len(viejo)
        for n, v in zip(nuevo[:-1], viejo[:-1], strict=True):
            assert abs(n - v) <= D("0.01"), (pendiente, perfil)
        assert sum(nuevo) == sum(viejo) == pendiente


# ===========================================================================
# R5 · neto no positivo o sin perfil: al primer mes, como retraso
# ===========================================================================


def test_f159_r5_neto_no_positivo_al_primer_mes() -> None:
    primero = date(2026, 11, 1)
    for perfil in ([], [(_mes(1), D(0))], [(_mes(1), D(10)), (_mes(2), D(-30))],
                   [(_mes(1), D(-5)), (_mes(2), D(5))]):
        assert repartir_pendiente(D("80"), perfil, primero) == [(primero, D("80"), True)], perfil
    assert repartir_pendiente(D("0"), [(_mes(1), D(5))], primero) == []


# ===========================================================================
# El SQL de `07` leído como texto (R8-R11)
# ===========================================================================


@cache
def _sql() -> str:
    return RUTA_DEVENGO.read_text(encoding="utf-8")


@cache
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


def test_f159_r8_el_sql_sigue_al_dominio() -> None:
    paso = _paso_5()
    # La envolvente: el plan acumulado y su mínimo hacia delante, con suelo 0.
    assert ("SUM(pr.importe_mes) OVER (PARTITION BY pr.obra_id, pr.concepto, pr.partida_id "
            "ORDER BY pr.anio_mes) AS plan_acumulado") in paso
    assert ("GREATEST(0, MIN(a.plan_acumulado) OVER (PARTITION BY a.obra_id, a.concepto, "
            "a.partida_id ORDER BY a.anio_mes DESC ROWS BETWEEN UNBOUNDED PRECEDING AND "
            "CURRENT ROW)) AS peso_acumulado") in paso
    assert ("ROW_NUMBER() OVER (PARTITION BY a.obra_id, a.concepto, a.partida_id "
            "ORDER BY a.anio_mes DESC) AS desde_el_final") in paso
    # Lo repartido HASTA cada mes; el último, el pendiente entero.
    assert ("CASE WHEN en.desde_el_final = 1 THEN d.pendiente "
            "ELSE ROUND(d.pendiente * en.peso_acumulado / d.total_perfil, 2) END AS hasta") in paso
    assert ("CASE WHEN en.desde_el_final = 1 THEN d.pendiente_con_coeficientes "
            "ELSE ROUND(d.pendiente_con_coeficientes * en.peso_acumulado / d.total_perfil, 2) "
            "END AS hasta_con_coef") in paso
    # Cada mes, lo de hasta él menos lo de hasta el anterior.
    assert "r.hasta - COALESCE(LAG(r.hasta) OVER w, 0) AS importe" in paso
    assert ("r.hasta_con_coef - COALESCE(LAG(r.hasta_con_coef) OVER w, 0) "
            "AS importe_con_coef") in paso
    assert ("WINDOW w AS (PARTITION BY r.obra_id, r.concepto, r.partida_id "
            "ORDER BY r.anio_mes)") in paso
    assert "WHERE d.pendiente > 0 AND d.total_perfil > 0" in paso
    # La fórmula de ayer, fuera.
    assert "r.pendiente - (r.suma_partes - r.parte)" not in paso
    assert "pr.importe_mes / d.total_perfil" not in paso
    assert "suma_partes" not in paso


def test_f159_r8_la_cabecera_lo_dice() -> None:
    cabecera = re.sub(r"\s*\n--\s*", " ", _sql()[: _sql().index("CREATE TEMP TABLE")])
    assert "por ACUMULADO sobre el plan NETO acumulado de V" in cabecera
    assert "(un mes negativo se absorbe en los anteriores, F-159)" in cabecera


def test_f159_r9_la_guarda_nueva_antes_de_vaciar_la_obra_mes() -> None:
    texto = _ejecutable()
    analyze = texto.index("ANALYZE _dev_reparto;")
    truncate = texto.index("TRUNCATE tesoreria.devengo_pendiente_obra_mes;")
    guarda = texto[analyze:truncate]
    assert ("WHERE pendiente < 0 OR importe_personal < 0 OR importe_personal > pendiente"
            in guarda)
    assert ("RAISE EXCEPTION 'devengo_pendiente: la partida % de la obra % reparte % en % "
            "(personal %): un mes no puede ser negativo', fallo.partida_id, fallo.obra_id, "
            "fallo.pendiente, fallo.anio_mes, fallo.importe_personal;") in guarda
    assert "IF FOUND THEN" in guarda


def _guarda_r50() -> str:
    texto = _ejecutable()
    inicio = texto.index("TRUNCATE tesoreria.devengo_pendiente_contrato_mes;")
    return texto[inicio: texto.index("END $$;", inicio)]


def test_f159_r10_r50_nombra_su_primera_fila_negativa() -> None:
    guarda = _guarda_r50()
    # La condición, intacta.
    assert ("SELECT count(*) INTO n_negativos FROM tesoreria.devengo_pendiente_contrato_mes "
            "WHERE importe_pendiente < 0;") in guarda
    assert ("WHERE COALESCE(m.total, 0) IS DISTINCT FROM COALESCE(c.total, 0); "
            "IF n_obras > 0 OR n_negativos > 0 THEN") in guarda
    # La primera fila negativa, la más negativa.
    assert ("SELECT obra_id, anio_mes, categoria, contrato_id, importe_pendiente "
            "INTO neg_obra, neg_mes, neg_categoria, neg_contrato, neg_importe "
            "FROM tesoreria.devengo_pendiente_contrato_mes WHERE importe_pendiente < 0 "
            "ORDER BY importe_pendiente LIMIT 1;") in guarda
    # El prefijo de siempre (lo buscan los pasos MANUAL) y la fila al final.
    assert ("RAISE EXCEPTION 'devengo_pendiente: el coste por contrato no cuadra con la "
            "obra-mes en % obras o tiene % importes negativos (primera negativa: obra %, "
            "mes %, categoria %, contrato %, importe %)', n_obras, n_negativos, neg_obra, "
            "neg_mes, neg_categoria, neg_contrato, neg_importe;") in guarda


def test_f159_r11_lo_que_no_cambia() -> None:
    texto = _ejecutable()
    paso = _paso_5()
    # El perfil: los meses con plan tras el cierre, con su signo.
    assert ("p.anio_mes >= v.mes_version AND (v.mes_ultimo_cierre IS NULL OR "
            "p.anio_mes > v.mes_ultimo_cierre) AND p.importe_mes <> 0") in paso
    assert "pr.importe_mes AS plan_restante" in paso
    # Sin perfil, al primer mes y marcado (D19-A).
    assert "WHERE d.pendiente > 0 AND COALESCE(d.total_perfil, 0) <= 0" in paso
    assert "d.pendiente_personal AS importe_personal, TRUE AS es_retraso" in paso
    # El personal (F-158), por acumulado sobre el pendiente del mes.
    assert ("ROUND(q.pendiente_personal * q.acumulado / q.pendiente_partida, 2) - "
            "ROUND(q.pendiente_personal * (q.acumulado - q.importe) / q.pendiente_partida, 2) "
            "AS importe_personal") in paso
    assert "r.pendiente AS pendiente_partida" in paso
    # El pendiente y la cuota de la partida.
    assert "GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) AS pendiente" in texto
    assert ("CASE WHEN d.concepto = 'COSTE' THEN ROUND(d.pendiente * d.cuota_personal, 2) END "
            "AS pendiente_personal") in texto
    # 5 bis: solo los (partida, mes) con importe > 0 se reparten entre contratos.
    assert texto.count("r.importe_np > 0") == 2
    assert "AND rp.pendiente <> 0" in texto
    # R14 y R58, con su texto.
    assert ("RAISE EXCEPTION 'devengo_pendiente: el reparto de la obra % (%) suma % y la "
            "partida %") in texto
    assert ("WHERE concepto = 'COSTE' AND importe_personal_neto + importe_personal_irpf_ss "
            "IS DISTINCT FROM importe_pendiente_personal") in texto


# ===========================================================================
# R12 · las fichas y la versión del diccionario
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
    return datos.get("objetos", datos)[nombre]


def test_f159_r12_fichas() -> None:
    pendiente = _plano(_objeto("devengo_pendiente_obra_mes")["columnas"]
                       ["importe_pendiente"]["significado"])
    assert "plan neto acumulado de v" in pendiente
    assert "un mes negativo del plan se absorbe en los anteriores" in pendiente
    assert "por acumulado" in pendiente
    assert "nunca es negativo" in pendiente
    assert "f-159" in pendiente
    contrato = _plano(_objeto("devengo_pendiente_contrato_mes")["descripcion"])
    assert "la fila sin contrato solo es negativa" not in contrato
    assert "ninguna fila es negativa" in contrato
    assert "f-159" in contrato


def test_f159_r12_version_74_con_su_nota() -> None:
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    cabecera, resto = texto.split("\nversion:", 1)
    assert int(resto.split()[0]) >= 74
    assert "# version 74 (F-159, 2026-11-07)" in cabecera
