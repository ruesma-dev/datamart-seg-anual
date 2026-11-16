# tests/test_f162_sandbox.py
"""
F-162 · `stg.obras` por ficha, ejecutado contra un PostgreSQL desechable (R23).

Solo con `F162_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA y la borra al terminar: nunca se tira un esquema
(el veto de `tests/test_f067_reset.py`). Carga `00_functions.sql` y `01_ddl.sql`
reales, un `raw` mínimo con los tipos de la ingesta (ids y empresa `integer`,
`tiemod` `double precision`, texto `character varying`) y ejecuta el
`03_obras.sql` real.

Lo que prueba:

1. La 0721 sale DOS veces, una por empresa, y `es_por_defecto` en la de la 1 (R2, R5).
2. Un código sin ficha de Ruesma con dos fichas: gana la de más líneas; con
   empate de líneas, la de `tiemod` mayor; con todo empatado, el `ide` mayor (R5).
3. La marca `conext` 15 en la ficha que no es la de Ruesma no cambia nada (R6).
4. Un código administrativo y uno de cinco dígitos se quedan fuera (R1).
5. En todos los códigos, el SQL marca lo mismo que el oráculo del dominio (R7).
6. La migración: sobre una `stg.obras` con el DDL de ANTES, `01_ddl.sql` deja las
   tres columnas al final y en orden (R3).
"""

from __future__ import annotations

import os
import uuid

import pytest

from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG
from etl_sigrid.domain.ficha_obra import FichaObra, ficha_por_defecto

DSN = os.environ.get("F162_SANDBOX_DSN")

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA stg;
CREATE TABLE raw.obr (ide integer);
CREATE TABLE raw.con (ide integer, cod character varying, res character varying,
                      emp integer, tiemod double precision);
CREATE TABLE raw.conext (ide integer, conide integer, cod character varying);
CREATE TABLE raw.obrparpre (ide integer, obride integer, paride integer, amb integer,
                            fas integer, can double precision, pre double precision);
"""

#: (ide, cod, res, emp, tiemod, líneas de obrparpre, con conext 15)
FICHAS = [
    # 0721: Ruesma con 3 líneas y PORSAN vacía pero más reciente y con cx15.
    (2759553, "0721", "OBRA 0721", 1, 100.0, 3, False),
    (2855829, "0721", "OBRA 0721", 28, 900.0, 0, True),
    # 0900: sin Ruesma; gana la de MÁS líneas aunque sea más antigua.
    (901, "0900", "SIN RUESMA LINEAS", 27, 1.0, 5, True),
    (902, "0900", "SIN RUESMA LINEAS", 31, 9.0, 2, False),
    # 0901: sin Ruesma; empate de líneas, gana el tiemod mayor.
    (911, "0901", "SIN RUESMA TIEMOD", 27, 9.0, 2, False),
    (912, "0901", "SIN RUESMA TIEMOD", 31, 1.0, 2, False),
    # 0902: sin Ruesma; todo empatado salvo el ide; tiemod NULL pierde.
    (921, "0902", "SIN RUESMA IDE", 27, 5.0, 0, False),
    (922, "0902", "SIN RUESMA IDE", 31, 5.0, 0, False),
    (923, "0902", "SIN RUESMA IDE", 12, None, 0, False),
    # 0903: ficha única de PORSAN: esa.
    (931, "0903", "UNICA PORSAN", 28, None, 0, False),
    # Fuera: administrativo y cinco dígitos.
    (941, "GG", "GASTOS GENERALES", 1, 1.0, 1, False),
    (951, "12345", "CODIGO LARGO", 1, 1.0, 1, False),
]

DENTRO = [f for f in FICHAS if f[1] not in ("GG", "12345")]


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F162_SANDBOX_DSN: la sandbox SQL de F-162 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f162_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            # La stg.obras de ANTES de F-162: la migración tiene que completarla.
            c.execute(
                "CREATE TABLE stg.obras (obra_id BIGINT PRIMARY KEY, codigo_obra VARCHAR(24),"
                " nombre_obra VARCHAR(255), activa BOOLEAN NOT NULL DEFAULT TRUE,"
                " _built_at TIMESTAMP NOT NULL DEFAULT NOW())"
            )
            linea = 0
            for ide, cod, res, emp, tiemod, lineas, cx15 in FICHAS:
                c.execute("INSERT INTO raw.obr VALUES (%s)", (ide,))
                c.execute(
                    "INSERT INTO raw.con VALUES (%s, %s, %s, %s, %s)",
                    (ide, cod, res, emp, tiemod),
                )
                if cx15:
                    c.execute("INSERT INTO raw.conext VALUES (%s, %s, '15')", (ide * 10, ide))
                for _ in range(lineas):
                    linea += 1
                    c.execute(
                        "INSERT INTO raw.obrparpre VALUES (%s, %s, 1, 3, 0, 1, 1)", (linea, ide)
                    )
            for nombre in ("00_functions.sql", "01_ddl.sql", "03_obras.sql"):
                c.execute((DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8"))
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _filas(c) -> dict[int, tuple]:
    return {
        fila[0]: fila[1:]
        for fila in c.execute(
            "SELECT obra_id, codigo_obra, empresa_id, clave_obra, es_por_defecto FROM stg.obras"
        ).fetchall()
    }


def test_f162_sandbox_r3_la_migracion_deja_las_tres_al_final(conexion) -> None:
    columnas = [
        fila[0]
        for fila in conexion.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'stg' AND table_name = 'obras' ORDER BY ordinal_position"
        ).fetchall()
    ]
    assert columnas == [
        "obra_id", "codigo_obra", "nombre_obra", "activa", "_built_at",
        "empresa_id", "clave_obra", "es_por_defecto",
    ]


def test_f162_sandbox_r1_una_fila_por_ficha_y_fuera_las_administrativas(conexion) -> None:
    assert sorted(_filas(conexion)) == sorted(f[0] for f in DENTRO)


def test_f162_sandbox_r2_la_0721_en_las_dos_empresas(conexion) -> None:
    filas = _filas(conexion)
    assert filas[2759553] == ("0721", 1, "1-0721", True)
    assert filas[2855829] == ("0721", 28, "28-0721", False), "conext 15 no decide (R6)"


@pytest.mark.parametrize(
    ("codigo", "ganadora"), [("0900", 901), ("0901", 911), ("0902", 922), ("0903", 931)]
)
def test_f162_sandbox_r5_sin_ruesma_deciden_los_datos(conexion, codigo, ganadora) -> None:
    filas = _filas(conexion)
    por_defecto = [oid for oid, f in filas.items() if f[0] == codigo and f[3]]
    assert por_defecto == [ganadora]


def test_f162_sandbox_r5_una_por_defecto_por_codigo(conexion) -> None:
    filas = _filas(conexion)
    codigos = {f[0] for f in filas.values()}
    assert sum(1 for f in filas.values() if f[3]) == len(codigos)


def test_f162_sandbox_r7_el_sql_marca_lo_mismo_que_el_oraculo(conexion) -> None:
    filas = _filas(conexion)
    for codigo in {f[1] for f in DENTRO}:
        fichas = [
            FichaObra(obra_id=ide, codigo_obra=cod, empresa_id=emp, num_lineas=lineas,
                      tiemod=tiemod)
            for ide, cod, _res, emp, tiemod, lineas, _cx in DENTRO
            if cod == codigo
        ]
        esperada = ficha_por_defecto(fichas).obra_id
        marcadas = [oid for oid, f in filas.items() if f[0] == codigo and f[3]]
        assert marcadas == [esperada], codigo
