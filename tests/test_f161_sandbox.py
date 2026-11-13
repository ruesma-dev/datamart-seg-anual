# tests/test_f161_sandbox.py
"""
F-161 · El catálogo completo, ejecutado contra un PostgreSQL desechable
(R1-R5, R11, R12, R14-R16 en sintético, y el oráculo igual al SQL).

Solo con `F161_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA y la borra al terminar, como
`tests/test_f157_sandbox.py`. Carga `stg/00_functions.sql` y `stg/01_ddl.sql`
reales, un `raw` mínimo con los tipos de la ingesta (ids y fechas `integer`,
cantidades `double precision`, texto `character varying`) y ejecuta los
ficheros REALES: `stg/08_plan_mensual.sql` (compuesto como lo compone el step),
`stg/10_master_versiones.sql`, `mart/01_ddl.sql`, `mart/01b_master_versiones.sql`
y `mart/02_build_fact.sql`.

La obra A (100) tiene, en coste (ámbito 8):
- v0 sin reparto (fuera, D6);
- v1 Planif Inicial con reparto y una línea a 0 € sin él (COMPLETO);
- v2 Cuatrimestral con reparto y una línea con importe sin él (PARCIAL);
- v3 «CIERRE SEPTIEMBRE-26» con ancla y sin ningún `planif` (NINGUNO, la 0698 v24);
- v4 con líneas y SIN cabecera (D5);
- v5 con la cabecera DUPLICADA y sin ancla (D13);
y en venta (ámbito 11) la v1 con reparto y la v3 sin él, las dos con el texto
vacío (lo pone el de coste, como en `08`).

La obra B (200) es la 0721: solo una v1 «CIERRE INICIAL_OBRA» sin reparto.
"""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    componer_sql_tramo,
)
from etl_sigrid.domain.master_versiones import (
    VersionMaster,
    clasificar_reparto,
    tipo_master,
    version_vigente,
)
from etl_sigrid.infrastructure.postgres.master_versiones_sql import (
    CATALOGO_ANTERIOR,
    sql_comparacion_catalogo,
)

DSN = os.environ.get("F161_SANDBOX_DSN")
DIRECTORIO_SQL_MART = DIRECTORIO_SQL_STG.parent / "mart"

OBRA_A, OBRA_B = 100, 200

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA stg; CREATE SCHEMA mart;
CREATE TABLE raw.obrfasamb (ide integer, obride integer, amb integer, fas integer,
                            plafec integer, fec integer, res varchar, tex varchar);
CREATE TABLE raw.obrparpre (ide integer, obride integer, paride integer, amb integer,
                            fas integer, can double precision, pre double precision,
                            planif varchar, totinc double precision,
                            impcoe double precision);
"""

#: (ide, obra, ámbito, versión, plafec, fec, res, tex)
CABECERAS = [
    (1, OBRA_A, 8, 0, 0, 20250101, "V0", "CIERRE INICIAL_ESTUDIO"),
    (2, OBRA_A, 8, 1, 20250201, 20250110, "Version 1", "PLANIFICACION VALORADA INICIAL"),
    (3, OBRA_A, 8, 2, 20260201, 20260210, "Version 2", "PLANIFICACION CUATRIMESTRAL FEB-26"),
    (4, OBRA_A, 8, 3, 20260901, 20260905, "", "CIERRE SEPTIEMBRE-26"),
    (5, OBRA_A, 8, 5, 0, 20261001, "Vieja", "CIERRE VIEJO"),
    (6, OBRA_A, 8, 5, 0, 20261002, "Nueva", "CIERRE OCTUBRE-26"),
    (7, OBRA_A, 11, 1, 20250201, 20250110, "Venta 1", ""),
    (8, OBRA_A, 11, 3, 20260901, 20260905, "Venta 3", ""),
    (9, OBRA_B, 8, 1, 0, 20250301, "Version 1", "CIERRE INICIAL_OBRA"),
]

#: (obra, partida, ámbito, versión, cantidad, precio, planif)
LINEAS = [
    (OBRA_A, 1, 8, 0, 1.0, 50.0, None),
    (OBRA_A, 1, 8, 1, 2.0, 100.0, "0.5|1"),
    (OBRA_A, 2, 8, 1, 0.0, 10.0, None),
    (OBRA_A, 1, 8, 2, 2.0, 110.0, "0.2|0.6|1"),
    (OBRA_A, 2, 8, 2, 3.0, 10.0, None),
    (OBRA_A, 1, 8, 3, 2.0, 120.0, None),
    (OBRA_A, 2, 8, 3, 3.0, 10.0, None),
    (OBRA_A, 1, 8, 4, 1.0, 130.0, "1"),
    (OBRA_A, 1, 8, 5, 1.0, 140.0, None),
    (OBRA_A, 1, 11, 1, 2.0, 150.0, "0.5|1"),
    (OBRA_A, 1, 11, 3, 2.0, 160.0, None),
    (OBRA_B, 3, 8, 1, 10.0, 1000.0, None),
]


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F161_SANDBOX_DSN: la sandbox SQL de F-161 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f161_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            for nombre in ("00_functions.sql", "01_ddl.sql"):
                c.execute(_stg(nombre))
            _cargar(c)
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _stg(nombre: str) -> str:
    return (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")


def _mart(nombre: str) -> str:
    return (DIRECTORIO_SQL_MART / nombre).read_text(encoding="utf-8")


def _cargar(c) -> None:
    with c.cursor() as cur:
        cur.executemany(
            "INSERT INTO raw.obrfasamb VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", CABECERAS
        )
        filas = [
            (1000 + i, obra, partida, amb, fas, can, pre, planif)
            for i, (obra, partida, amb, fas, can, pre, planif) in enumerate(LINEAS)
        ]
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
    c.execute(
        "INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, empresa_id, clave_obra) VALUES "
        "(100, '0698', 'OBRA A', 1, '1-0698'), (200, '0721', 'OBRA B', 1, '1-0721')"
    )
    c.execute(
        "INSERT INTO stg.partidas (partida_id, obra_id, codigo_partida, descripcion_corta, "
        "categoria, ruta_capitulos) VALUES "
        "(1, 100, 'P1', 'PARTIDA 1', 'CD', 'C1 > P1'), (2, 100, 'P2', 'PARTIDA 2', 'CD', 'C1 > P2'),"
        "(3, 200, 'P3', 'PARTIDA 3', 'CI', 'C2 > P3')"
    )
    c.execute(componer_sql_tramo(_stg("08_plan_mensual.sql"), [OBRA_A, OBRA_B]))
    c.execute(_stg("10_master_versiones.sql"))
    for nombre in ("01_ddl.sql", "01b_master_versiones.sql", "02_build_fact.sql",
                   "06_cp_tipologia.sql"):
        c.execute(_mart(nombre))


def _catalogo(c) -> dict[tuple[int, int, int], dict]:
    cur = c.execute("SELECT * FROM mart.master_versiones_tipadas")
    nombres = [d.name for d in cur.description]
    return {(f[0], f[1], f[2]): dict(zip(nombres, f, strict=True)) for f in cur.fetchall()}


# --- R1 · el universo ---------------------------------------------------------


def test_f161_r1_el_universo_y_la_v0_fuera(conexion) -> None:
    claves = set(_catalogo(conexion))
    assert claves == {
        (OBRA_A, 8, 1), (OBRA_A, 8, 2), (OBRA_A, 8, 3), (OBRA_A, 8, 4), (OBRA_A, 8, 5),
        (OBRA_A, 11, 1), (OBRA_A, 11, 3), (OBRA_B, 8, 1),
    }
    assert conexion.execute("SELECT count(*) FROM stg.master_versiones").fetchone() == (8,)


# --- R2 · la marca por línea ---------------------------------------------------


def test_f161_r2_la_marca_por_linea_es_dejar_filas(conexion) -> None:
    distintas = conexion.execute(
        "SELECT l.presupuesto_id FROM stg.v_master_lineas l "
        "WHERE l.tiene_reparto <> EXISTS (SELECT 1 FROM stg.plan_mensual pm "
        "WHERE pm.presupuesto_id = l.presupuesto_id)"
    ).fetchall()
    assert distintas == []
    con = conexion.execute(
        "SELECT obra_id, ambito_id, version, partida_id FROM stg.v_master_lineas "
        "WHERE tiene_reparto ORDER BY 1, 2, 3, 4"
    ).fetchall()
    # La v4 tiene `planif` pero no cabecera: `08` no la reparte.
    assert con == [(OBRA_A, 8, 1, 1), (OBRA_A, 8, 2, 1), (OBRA_A, 11, 1, 1)]
    assert conexion.execute(
        "SELECT count(*) FROM stg.v_master_lineas WHERE version = 0"
    ).fetchone() == (0,)


# --- R3 · el reparto de la versión = el oráculo ---------------------------------


def test_f161_r3_reparto_y_totales_iguales_al_oraculo(conexion) -> None:
    lineas: dict[tuple, list] = defaultdict(list)
    for obra, amb, ver, importe, con in conexion.execute(
        "SELECT obra_id, ambito_id, version, importe, tiene_reparto FROM stg.v_master_lineas"
    ).fetchall():
        lineas[(obra, amb, ver)].append((importe, con))
    for clave, fila in _catalogo(conexion).items():
        propias = lineas[clave]
        assert fila["reparto"] == clasificar_reparto(propias, fila["tiene_reparto"]), clave
        assert fila["n_lineas"] == len(propias), clave
        assert fila["n_lineas_con_reparto"] == sum(1 for _, c in propias if c), clave
        total = sum((i for i, _ in propias), Decimal(0))
        con = sum((i for i, c in propias if c), Decimal(0))
        assert fila["importe_total"] == total, clave
        assert fila["importe_con_reparto"] == con, clave
        assert fila["importe_sin_reparto"] == total - con, clave
        assert fila["tipo_master"] == tipo_master(fila["version_tex"]), clave


def test_f161_r3_los_tres_repartos_esperados(conexion) -> None:
    cat = _catalogo(conexion)
    assert cat[(OBRA_A, 8, 1)]["reparto"] == "COMPLETO"
    assert cat[(OBRA_A, 8, 2)]["reparto"] == "PARCIAL"
    assert cat[(OBRA_A, 8, 3)]["reparto"] == "NINGUNO"
    assert cat[(OBRA_A, 8, 3)]["importe_total"] == Decimal("270.00")


# --- R4 · los atributos ----------------------------------------------------------


def test_f161_r4_con_reparto_son_los_de_plan_mensual(conexion) -> None:
    plan = {
        f[:3]: f[3:]
        for f in conexion.execute(
            "SELECT DISTINCT obra_id, ambito_id, version, version_fec_creacion, "
            "version_fec_efectiva, version_descripcion, version_tex FROM stg.plan_mensual "
            "WHERE ambito_id IN (8, 11)"
        ).fetchall()
    }
    cat = _catalogo(conexion)
    assert set(plan) == {k for k, v in cat.items() if v["tiene_reparto"]}
    for clave, atributos in plan.items():
        fila = cat[clave]
        assert (
            fila["version_fec_creacion"], fila["version_fec_efectiva"],
            fila["version_descripcion"], fila["version_tex"],
        ) == atributos


def test_f161_r4_sin_reparto_salen_de_la_cabecera_como_en_08(conexion) -> None:
    cat = _catalogo(conexion)
    v3 = cat[(OBRA_A, 8, 3)]
    assert (v3["version_fec_creacion"], v3["version_fec_efectiva"]) == (
        date(2026, 9, 5), date(2026, 9, 5),
    )
    assert v3["version_descripcion"] == "Master coste sin descripción"
    assert v3["version_tex"] == "CIERRE SEPTIEMBRE-26"
    venta3 = cat[(OBRA_A, 11, 3)]
    assert venta3["version_tex"] == "CIERRE SEPTIEMBRE-26", "el texto de coste para la venta"
    assert venta3["version_descripcion"] == "Venta 3"
    b = cat[(OBRA_B, 8, 1)]
    assert (b["version_tex"], b["tipo_master"], b["reparto"]) == (
        "CIERRE INICIAL_OBRA", "Cierre mensual", "NINGUNO",
    )


# --- R5 · sin cabecera, y la cabecera duplicada (D13) ---------------------------


def test_f161_r5_sin_cabecera_todo_nulo(conexion) -> None:
    v4 = _catalogo(conexion)[(OBRA_A, 8, 4)]
    assert v4["tiene_cabecera"] is False and v4["tiene_ancla"] is False
    # La v4 tiene `planif`, pero sin cabecera `08` no la reparte.
    assert v4["tiene_reparto"] is False
    for columna in ("version_fec_creacion", "version_fec_efectiva", "version_descripcion",
                    "version_tex"):
        assert v4[columna] is None, columna


def test_f161_r5_d13_la_cabecera_de_ide_mayor_y_sin_ancla(conexion) -> None:
    v5 = _catalogo(conexion)[(OBRA_A, 8, 5)]
    assert (v5["tiene_cabecera"], v5["tiene_ancla"]) == (True, False)
    assert (v5["version_descripcion"], v5["version_tex"]) == ("Nueva", "CIERRE OCTUBRE-26")
    assert v5["version_fec_creacion"] == date(2026, 10, 2)
    v3 = _catalogo(conexion)[(OBRA_A, 8, 3)]
    assert (v3["tiene_cabecera"], v3["tiene_ancla"]) == (True, True)


# --- R11 · el catálogo de hoy está dentro, idéntico ------------------------------


def test_f161_r11_sin_diferencias_con_el_catalogo_de_hoy(conexion) -> None:
    assert conexion.execute(sql_comparacion_catalogo()).fetchall() == []
    anterior = conexion.execute(CATALOGO_ANTERIOR).fetchall()
    assert len(anterior) == 3, "control: v1 y v2 de coste y v1 de venta"


# --- R12 · el coste por versión y partida -----------------------------------------


def test_f161_r12_la_version_sin_reparto_por_partida(conexion) -> None:
    filas = conexion.execute(
        "SELECT clave_obra, concepto, tipo_master, reparto, codigo_partida, importe, "
        "tiene_reparto FROM mart.v_master_version_partida "
        "WHERE obra_id = %s AND ambito_id = 8 AND version = 3 ORDER BY codigo_partida",
        (OBRA_A,),
    ).fetchall()
    assert filas == [
        ("1-0698", "COSTE", "Cierre mensual", "NINGUNO", "P1", Decimal("240.00"), False),
        ("1-0698", "COSTE", "Cierre mensual", "NINGUNO", "P2", Decimal("30.00"), False),
    ]
    total = conexion.execute(
        "SELECT count(*), sum(importe) FROM mart.v_master_version_partida "
        "WHERE obra_id = %s AND ambito_id = 8 AND version = 3",
        (OBRA_A,),
    ).fetchone()
    assert total == (2, _catalogo(conexion)[(OBRA_A, 8, 3)]["importe_total"])


# --- R14-R16 · el planificado de importe al lado del temporal ---------------------


def _versiones(c, obra: int, ambito: int) -> list[VersionMaster]:
    return [
        VersionMaster(
            version=f["version"], fec_efectiva=f["version_fec_efectiva"], tipo=f["tipo_master"],
            n_lineas=f["n_lineas"], tiene_reparto=f["tiene_reparto"],
            importe_total=f["importe_total"], fec_creacion=f["version_fec_creacion"],
        )
        for (o, a, _), f in _catalogo(c).items()
        if (o, a) == (obra, ambito)
    ]


def test_f161_r14_cada_mes_es_el_oraculo(conexion) -> None:
    filas = conexion.execute(
        "SELECT obra_id, ambito_id, anio_mes, version_importe, importe_total_importe, "
        "version_temporal, importe_total_temporal, importe_con_reparto_temporal, "
        "diferencia_importe, diferencia_importe_con_reparto, es_misma_version "
        "FROM mart.master_importe_mensual ORDER BY 1, 2, 3"
    ).fetchall()
    assert filas
    hoy = conexion.execute("SELECT date_trunc('month', CURRENT_DATE)::DATE").fetchone()[0]
    por_par: dict[tuple, list] = defaultdict(list)
    for f in filas:
        por_par[(f[0], f[1])].append(f)
    for (obra, amb), meses in por_par.items():
        versiones = _versiones(conexion, obra, amb)
        assert meses[-1][2] == hoy, "hasta el mes del build (D9)"
        for _, _, mes, v_imp, imp, v_tmp, imp_tmp, rep_tmp, dif, dif_rep, misma in meses:
            i = version_vigente(versiones, mes, temporal=False)
            t = version_vigente(versiones, mes, temporal=True)
            assert v_imp == (i.version if i else None), (obra, amb, mes)
            assert v_tmp == (t.version if t else None), (obra, amb, mes)
            assert imp == (i.importe_total if i else None)
            assert imp_tmp == (t.importe_total if t else None)
            if i and t:
                assert dif == i.importe_total - t.importe_total
                assert dif_rep == i.importe_total - rep_tmp
            else:
                assert dif is None and dif_rep is None
            assert misma == bool(i and t and i.version == t.version)


def test_f161_r14_hoy_el_ultimo_cierre_frente_a_la_temporal(conexion) -> None:
    hoy = conexion.execute(
        "SELECT version_importe, version_temporal, diferencia_importe "
        "FROM mart.master_importe_mensual WHERE obra_id = %s AND ambito_id = 8 "
        "AND anio_mes = date_trunc('month', CURRENT_DATE)::DATE",
        (OBRA_A,),
    ).fetchone()
    # La v5 (CIERRE OCTUBRE-26) es la última con fecha efectiva: es el último cierre.
    assert hoy[0] == 5 and hoy[1] == 2


def test_f161_r15_la_0721_sin_temporal_con_importe(conexion) -> None:
    filas = conexion.execute(
        "SELECT DISTINCT version_importe, importe_total_importe, version_temporal, "
        "diferencia_importe FROM mart.master_importe_mensual WHERE obra_id = %s",
        (OBRA_B,),
    ).fetchall()
    assert filas == [(1, Decimal("10000.00"), None, None)]


def test_f161_r16_el_mensual_usa_la_version_temporal(conexion) -> None:
    discrepancias = conexion.execute(
        """
        SELECT f.obra_id, f.ambito_id, f.anio_mes, f.version_master, m.version_temporal
        FROM (SELECT DISTINCT obra_id, ambito_id, anio_mes, version_master
              FROM mart.fact_seguimiento_mensual WHERE tipo_dato = 'PLANIFICADO') f
        JOIN mart.master_importe_mensual m
          ON m.obra_id = f.obra_id AND m.ambito_id = f.ambito_id AND m.anio_mes = f.anio_mes
        WHERE f.version_master IS DISTINCT FROM m.version_temporal
        """
    ).fetchall()
    assert discrepancias == []
    cubiertos = conexion.execute(
        "SELECT count(*) FROM mart.fact_seguimiento_mensual f JOIN mart.master_importe_mensual m "
        "ON m.obra_id = f.obra_id AND m.ambito_id = f.ambito_id AND m.anio_mes = f.anio_mes "
        "WHERE f.tipo_dato = 'PLANIFICADO'"
    ).fetchone()[0]
    assert cubiertos > 0, "control: el cruce no puede estar vacío"


# --- R10 · la vigencia anual solo mira versiones con reparto --------------------


def test_f161_r10_master_vigente_anual_solo_con_reparto(conexion) -> None:
    fuera = conexion.execute(
        "SELECT va.obra_id, va.ambito_id, va.version FROM mart.master_vigente_anual va "
        "JOIN mart.master_versiones_tipadas vt USING (obra_id, ambito_id, version) "
        "WHERE NOT vt.tiene_reparto"
    ).fetchall()
    assert fuera == []
    assert conexion.execute("SELECT count(*) FROM mart.master_vigente_anual").fetchone()[0] > 0
