# tests/test_f157_sandbox.py
"""
F-157 · La fase 0 repartida, ejecutada contra un PostgreSQL desechable
(R2-R8, R10, R11, R13 y R22 en sintético).

Solo con `F157_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA y la borra al terminar: nunca se tira un esquema
(el veto de `tests/test_f067_reset.py`). Carga `00_functions.sql` y `01_ddl.sql`
reales, un `raw` mínimo con los tipos de la ingesta (ids y fechas `integer`,
cantidades e importes `double precision`, texto `character varying`) y ejecuta
el 08 y el 09 reales compuestos como los compone el step.

Lo que prueba:

1. `stg.fn_explotar_planif` = el oráculo `etl_sigrid/domain/planif.py` en los
   casos documentados y en 500 `planif` aleatorios con semilla fija.
2. El 08 (rama master, ámbito 8) y el 09 (ámbito 7) sobre el MISMO `planif`,
   cantidad, precio y decimales dan los mismos %, cantidades e importes.
3. El 09: solo fase 0 de 3 y 7, sin `plafec` no hay filas, la fila de
   `obrfasamb` de `ide` mayor, borrado derivado idempotente y la cobertura.
"""

from __future__ import annotations

import os
import random
import uuid
from decimal import Decimal

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    componer_sql_fase0,
    componer_sql_tramo,
)
from etl_sigrid.domain.planif import conservar, explotar_planif

DSN = os.environ.get("F157_SANDBOX_DSN")

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA stg;
CREATE TABLE raw.obrfasamb (ide integer, obride integer, amb integer, fas integer,
                            plafec integer, fec integer, res varchar, tex varchar);
CREATE TABLE raw.obrparpre (ide integer, obride integer, paride integer, amb integer,
                            fas integer, can double precision, pre double precision,
                            planif varchar, totinc double precision,
                            impcoe double precision);
"""

CASOS = [
    "0|0|0|0|0.15|0.85|1",
    "0.3439|1",
    "0.501|0.501|0.501|0|0|0|0|0|0|0.2|0.4|0.7|1",
    "0.2|0.5|0.93|0|0",
    "0.5|1.054|1.0|0|0",
    "0.5|1||",
    "0.5| |1",
    "0.5|x|1",
    "0,25|1",
    "0.5|-0.2|1",
    "0.5|0|-0.1",
    "1|3|1",
    "0.1234567|1",
    "0|0|0",
    "|",
    "",
]


def _aleatorios(n: int, semilla: int = 157) -> list[str]:
    azar = random.Random(semilla)
    piezas = ["0", "0", "1", "", " ", "x", "-0.05", "3", "0,5"]
    salida = []
    for _ in range(n):
        largo = azar.randint(1, 25)
        valores = [
            azar.choice(piezas)
            if azar.random() < 0.35
            else f"{azar.uniform(0, 1.3):.{azar.randint(0, 7)}f}"
            for _ in range(largo)
        ]
        salida.append("|".join(valores))
    return salida


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F157_SANDBOX_DSN: la sandbox SQL de F-157 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f157_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            for nombre in ("00_functions.sql", "01_ddl.sql"):
                c.execute((DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8"))
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _funcion(c, planif: str | None) -> list[tuple[int, Decimal, Decimal]]:
    return [
        (int(p), Decimal(a), Decimal(m))
        for p, a, m in c.execute(
            "SELECT posicion_mes, pct_acumulado, pct_mes FROM stg.fn_explotar_planif(%s)",
            (planif,),
        ).fetchall()
    ]


def _oraculo(planif: str | None) -> list[tuple[int, Decimal, Decimal]]:
    return [(p.posicion_mes, p.pct_acumulado, p.pct_mes) for p in explotar_planif(planif)]


# --- 1 · función = oráculo ---------------------------------------------------


@pytest.mark.parametrize("planif", CASOS + [None])
def test_f157_r8_funcion_igual_al_oraculo_en_los_casos(conexion, planif) -> None:
    assert _funcion(conexion, planif) == _oraculo(planif)


def test_f157_r8_funcion_igual_al_oraculo_en_500_aleatorios(conexion) -> None:
    distintos = [p for p in _aleatorios(500) if _funcion(conexion, p) != _oraculo(p)]
    assert distintos == []


# --- 2 · el 08 (master) y el 09 (fase 0) sobre el mismo planif ---------------

OBRA_M = 100  # obra con master (ámbito 8, versión 1) y fase 0 de venta (ámbito 7)
OBRA_SIN_PLAFEC = 200
OBRA_DOBLE = 300  # dos filas de obrfasamb (7, fas 0): manda la de ide mayor
PLAFEC = 20261015
PLANIFS_08_09 = CASOS[:13] + _aleatorios(60, semilla=2026)


def _cargar(c) -> None:
    c.execute("TRUNCATE raw.obrfasamb, raw.obrparpre, stg.presupuesto, stg.plan_mensual, stg.plan_mensual_fase0")
    c.execute(
        "INSERT INTO raw.obrfasamb VALUES "
        "(1, %(m)s, 8, 1, %(p)s, 20261001, 'V1', ''),"
        "(2, %(m)s, 7, 0, %(p)s, 0, '', ''),"
        "(3, %(m)s, 3, 0, 0, 0, '', ''),"
        "(4, %(s)s, 7, 0, 0, 0, '', ''),"
        "(5, %(d)s, 7, 0, 20250101, 0, '', ''),"
        "(6, %(d)s, 7, 0, 20250301, 0, '', '')",
        {"m": OBRA_M, "p": PLAFEC, "s": OBRA_SIN_PLAFEC, "d": OBRA_DOBLE},
    )
    ide = 1000
    filas = []
    for partida, planif in enumerate(PLANIFS_08_09, start=1):
        can, pre = 3.5 + partida, 117.294961 + partida
        for amb, fas in ((8, 1), (7, 0), (7, 1)):
            ide += 1
            filas.append((ide, OBRA_M, partida, amb, fas, can, pre, planif))
        # Coste fase 0 en una obra sin plafec de coste: no se reparte (R10).
        ide += 1
        filas.append((ide, OBRA_M, partida, 3, 0, can, pre, planif))
    ide += 1
    filas.append((ide, OBRA_SIN_PLAFEC, 1, 7, 0, 2.0, 10.0, "0.5|1"))
    ide += 1
    filas.append((ide, OBRA_DOBLE, 1, 7, 0, 2.0, 10.0, "0.5|1"))
    ide += 1
    filas.append((ide, OBRA_DOBLE, 2, 7, 0, 4.0, 10.0, None))  # sin planif
    with c.cursor() as cur:
        cur.executemany(
            "INSERT INTO raw.obrparpre (ide, obride, paride, amb, fas, can, pre, planif) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            filas,
        )
    c.execute(
        """
        INSERT INTO stg.presupuesto (presupuesto_id, obra_id, partida_id, ambito_id, fase_num,
                                     cantidad, precio, importe, dec_cantidades, dec_precios,
                                     dec_importes)
        SELECT ide, obride, paride, amb, fas, can::NUMERIC(20,6), pre::NUMERIC(20,6),
               ROUND(can::NUMERIC * ROUND(pre::NUMERIC, 2), 2), 3, 2, 2
        FROM raw.obrparpre
        """
    )
    obras = [OBRA_M, OBRA_SIN_PLAFEC, OBRA_DOBLE]
    c.execute(componer_sql_tramo(_texto("08_plan_mensual.sql"), obras))
    c.execute(componer_sql_fase0(_texto("09_plan_mensual_fase0.sql"), obras))


def _texto(nombre: str) -> str:
    return (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cargada(conexion):
    _cargar(conexion)
    return conexion


COLUMNAS = "partida_id, posicion_mes, pct_acumulado, pct_mes, can_mes, can_origen, importe_mes, importe_origen, importe_mes_raw, importe_origen_raw, anio_mes"


def test_f157_r22_master_y_fase0_dan_lo_mismo_sobre_el_mismo_planif(cargada) -> None:
    master = cargada.execute(
        f"SELECT {COLUMNAS} FROM stg.plan_mensual WHERE obra_id = %s AND ambito_id = 8 ORDER BY 1, 2",
        (OBRA_M,),
    ).fetchall()
    fase0 = cargada.execute(
        f"SELECT {COLUMNAS} FROM stg.plan_mensual_fase0 WHERE obra_id = %s AND ambito_id = 7 ORDER BY 1, 2",
        (OBRA_M,),
    ).fetchall()
    assert len(master) > 200
    assert fase0 == master


def test_f157_r6_r8_la_tabla_es_el_oraculo_filtrado(cargada) -> None:
    filas = cargada.execute(
        "SELECT partida_id, posicion_mes, pct_acumulado, pct_mes FROM stg.plan_mensual_fase0 "
        "WHERE obra_id = %s ORDER BY 1, 2",
        (OBRA_M,),
    ).fetchall()
    esperado = [
        (partida, p.posicion_mes, p.pct_acumulado, p.pct_mes)
        for partida, planif in enumerate(PLANIFS_08_09, start=1)
        for p in explotar_planif(planif)
        if conservar(p)
    ]
    assert [(a, b, Decimal(c), Decimal(d)) for a, b, c, d in filas] == esperado


def test_f157_r2_r10_solo_fase_0_de_venta_con_plafec(cargada) -> None:
    por_ambito = dict(
        cargada.execute(
            "SELECT ambito_id, count(*) FROM stg.plan_mensual_fase0 WHERE obra_id = %s GROUP BY 1",
            (OBRA_M,),
        ).fetchall()
    )
    assert set(por_ambito) == {7}  # el coste no tiene plafec en esta obra
    assert cargada.execute(
        "SELECT count(*) FROM stg.plan_mensual_fase0 WHERE obra_id = %s", (OBRA_SIN_PLAFEC,)
    ).fetchone() == (0,)
    # Las filas son de la fase 0: su presupuesto_id es el de fas = 0.
    assert cargada.execute(
        "SELECT count(*) FROM stg.plan_mensual_fase0 f JOIN stg.presupuesto p "
        "USING (presupuesto_id) WHERE p.fase_num <> 0"
    ).fetchone() == (0,)


def test_f157_r3_r4_ide_mayor_y_meses_desde_plafec(cargada) -> None:
    filas = cargada.execute(
        "SELECT partida_id, mes_inicio, anio_mes, posicion_mes, importe_partida "
        "FROM stg.plan_mensual_fase0 WHERE obra_id = %s ORDER BY 1, 4",
        (OBRA_DOBLE,),
    ).fetchall()
    assert [(str(f[1]), str(f[2]), f[3]) for f in filas] == [
        ("2025-03-01", "2025-03-01", 1),
        ("2025-03-01", "2025-04-01", 2),
    ]
    inicio = cargada.execute(
        "SELECT DISTINCT mes_inicio FROM stg.plan_mensual_fase0 WHERE obra_id = %s", (OBRA_M,)
    ).fetchall()
    assert [str(f[0]) for f in inicio] == ["2026-10-01"]


def test_f157_r11_cobertura(cargada) -> None:
    fila = cargada.execute(
        "SELECT mes_inicio, partidas, partidas_planificadas, importe_fase0, "
        "importe_planificado, importe_sin_planificar "
        "FROM stg.v_plan_mensual_fase0_cobertura WHERE obra_id = %s AND ambito_id = 7",
        (OBRA_DOBLE,),
    ).fetchone()
    assert (str(fila[0]), fila[1], fila[2]) == ("2025-03-01", 2, 1)
    assert (fila[3], fila[4], fila[5]) == (Decimal("60.00"), Decimal("20.00"), Decimal("40.00"))
    sin = cargada.execute(
        "SELECT mes_inicio, partidas_planificadas, importe_sin_planificar = importe_fase0 "
        "FROM stg.v_plan_mensual_fase0_cobertura WHERE obra_id = %s AND ambito_id = 3",
        (OBRA_M,),
    ).fetchone()
    assert sin == (None, 0, True)


def test_f157_r13_el_borrado_derivado_es_idempotente_y_no_toca_otras_obras(cargada) -> None:
    antes = cargada.execute(
        "SELECT obra_id, count(*) FROM stg.plan_mensual_fase0 GROUP BY 1 ORDER BY 1"
    ).fetchall()
    cargada.execute(componer_sql_fase0(_texto("09_plan_mensual_fase0.sql"), [OBRA_DOBLE]))
    cargada.execute(componer_sql_fase0(_texto("09_plan_mensual_fase0.sql"), [OBRA_DOBLE]))
    despues = cargada.execute(
        "SELECT obra_id, count(*) FROM stg.plan_mensual_fase0 GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert despues == antes
