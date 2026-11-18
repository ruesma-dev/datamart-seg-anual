# tests/test_f104_sandbox.py
"""
F-104 · El SQL de la retención de cliente, EJECUTADO contra un PostgreSQL desechable (T9).

Solo con `F104_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA y la borra al terminar: nunca se tira un esquema
(el veto de `tests/test_f067_reset.py`). Monta un `raw` mínimo con los TIPOS DE
LA INGESTA (ids y fechas `integer`, importes `double precision`, `reccla`
`smallint`), un `maestro.centros_coste` y un `ventas.facturas` de tabla, y
ejecuta `retenciones/00_setup.sql`, `01_movimientos.sql`, `02_views.sql` y
`08_saldo_cliente.sql`, y después `ventas/06b_retencion_cliente.sql`.

El caso, construido a mano (cifras en céntimos redondos):

- cuentas: 9001 (4308, la declara el cliente 100), 9002 (4338, no la declara
  nadie: UNEXUM), 9003 (5540, declarada fuera de 43x8), 9004 (4308 pero `tip`
  16: fuera), 9005 (4308, cliente 102) y 9010 (4300, no es de retención);
- un AGR agrupado (los originales 501 y 502 en `est 1` con `fecbaj`), dividido
  en un DIV vivo sin factura (511) y otro cobrado por remesa (`est 10`, 512);
- una apertura sin cierre previo (SALDO_INICIAL) y otra con cierre (APERTURA);
- facturas de los cinco `motivo`, una con RETESP a la 4338 sin efecto y un
  efecto vivo sin documento en su cuenta (511).
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

DSN = os.environ.get("F104_SANDBOX_DSN")

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
RETENCIONES = ("00_setup.sql", "01_movimientos.sql", "02_views.sql", "08_saldo_cliente.sql")

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA maestro; CREATE SCHEMA ventas;
CREATE TABLE raw.con (ide integer, tip integer, cod varchar(24), res varchar(128),
                      emp integer, est integer, fecbaj integer, fec integer);
CREATE TABLE raw.rec (ide integer, cla integer, valpor double precision,
                      valcan double precision, tipdev integer, diavto integer);
CREATE TABLE raw.prv (ide integer, cif varchar(24), cueretide integer);
CREATE TABLE raw.cli (ide integer, cif varchar(24), cueretide integer);
CREATE TABLE raw.pag (ide integer, retide integer, conide integer, entide integer,
                      cenide integer, cueide integer, tot double precision,
                      fecven integer, fecrea integer);
CREATE TABLE raw.cob (ide integer, retide integer, conide integer, entide integer,
                      cenide integer, cueide integer, tot double precision,
                      fecven integer, fecrea integer);
CREATE TABLE raw.apu (ide integer, asiide integer, fec integer, cueide integer,
                      res varchar(255), deb double precision, hab double precision,
                      cenide integer);
CREATE TABLE raw.dvfrec (ide integer, docide integer, recide integer, cueide integer,
                         cuo double precision, reccla smallint);
CREATE TABLE maestro.centros_coste (centro_coste_id integer, obra_id integer,
                                    codigo_obra varchar(24), nombre_obra varchar(128));
CREATE TABLE ventas.facturas (factura_id integer, codigo_factura varchar(24),
                              fecha_factura date, cliente_id integer,
                              nombre_cliente varchar(128), obra_id integer,
                              codigo_obra varchar(24), retencion_garantia numeric(18, 2),
                              retencion_retesp numeric(18, 2));
"""

DATOS = """
INSERT INTO raw.con (ide, tip, cod, res, emp, est, fecbaj, fec) VALUES
  (9001, 17, '4308000001', 'CLIENTE 100, Retenciones', 1, 0, 0, 0),
  (9002, 17, '4338000002', 'UNEXUM, Retenciones', 1, 0, 0, 0),
  (9003, 17, '5540000003', 'UTE, retenciones suplidos', 1, 0, 0, 0),
  (9004, 16, '4308000004', 'cuenta no imputable', 1, 0, 0, 0),
  (9005, 17, '4308000005', 'CLIENTE 102, Retenciones', 1, 0, 0, 0),
  (9010, 17, '4300000010', 'CLIENTE 100, Clientes', 1, 0, 0, 0),
  (8001, 17, '4008000001', 'PROVEEDOR, Retenciones', 1, 0, 0, 0),
  (7, 0, 'RET5', 'Retencion 5%', 1, 0, 0, 0),
  (100, 4, 'C100', 'CLIENTE 100 SA', 1, 0, 0, 0),
  (1001, 11, 'FV1', 'f1', 1, 2, 0, 20160301),
  (501, 24, 'FV1_02', 'e', 1, 1, 20200304, 0),
  (502, 24, 'FV1_02b', 'e', 1, 1, 20200304, 0),
  (510, 24, 'AGR20/0010', 'agr', 1, 15, 0, 0),
  (511, 24, 'DIV20/0010', 'div', 1, 1, 0, 0),
  (512, 24, 'DIV20/0011', 'div', 1, 10, 0, 0),
  (520, 24, 'FV2_02', 'e', 1, 1, 0, 0),
  (530, 24, 'FV3_02', 'e', 1, 1, 0, 0),
  (540, 24, 'FV5_01', 'e', 1, 1, 0, 0),
  (550, 24, 'FV6_02', 'e', 1, 1, 0, 0),
  (560, 24, 'FV10_02', 'e', 1, 1, 0, 0),
  (601, 25, 'P1', 'p', 1, 1, 0, 0);
INSERT INTO raw.rec (ide, cla, valpor, valcan, tipdev, diavto) VALUES (7, 4, 5, 0, 0, 0);
INSERT INTO raw.prv (ide, cif, cueretide) VALUES (300, 'B00000000', 8001);
INSERT INTO raw.cli (ide, cif, cueretide) VALUES
  (100, 'A00000000', 9001), (101, 'U00000000', 9003), (102, 'B11111111', 9005),
  (103, 'B22222222', 0);
INSERT INTO raw.cob (ide, retide, conide, entide, cenide, cueide, tot, fecven, fecrea) VALUES
  (501, 7, 1001, 100, 0, 9001, 100.10, 20170601, 0),
  (502, 7, 1001, 100, 0, 9001, 49.90, 20170601, 0),
  (510, 0, 0, 100, 0, 9001, 150, 20200304, 0),
  (511, 0, 0, 100, 0, 9001, 120, 20210101, 0),
  (512, 0, 0, 100, 0, 9001, 30, 20210101, 0),
  (520, 7, 1002, 100, 0, 9001, 40, 20200101, 0),
  (530, 7, 1003, 100, 0, 9001, 25, 20230101, 20240101),
  (540, 0, 1005, 100, 0, 9010, 999, 20230101, 0),
  (550, 7, 1006, 100, 0, 9010, 10, 20990101, 0),
  (560, 7, 1010, 102, 0, 9005, 40, 20990101, 0);
INSERT INTO raw.pag (ide, retide, conide, entide, cenide, cueide, tot, fecven, fecrea) VALUES
  (601, 7, 0, 300, 0, 8001, 77, 20990101, 0);
INSERT INTO raw.apu (ide, asiide, fec, cueide, res, deb, hab, cenide) VALUES
  (1, 0, 20160101, 9001, 'Asiento de apertura', 500, 0, 0),
  (2, 0, 20170301, 9001, 'Factura FV1', 200, 0, 0),
  (3, 0, 20180301, 9001, 'Cobro retencion', 0, 150, 0),
  (4, 0, 20181231, 9001, 'Asiento de cierre', 0, 550, 0),
  (5, 0, 20190101, 9001, 'Asiento de apertura', 550, 0, 0),
  (6, 0, 20250301, 9002, 'Factura FV9', 300, 0, 0),
  (7, 0, 20250301, 9005, 'Factura FV10', 40, 0, 0),
  (8, 0, 20250301, 9010, 'Factura normal', 1000, 0, 0);
INSERT INTO raw.dvfrec (ide, docide, recide, cueide, cuo, reccla) VALUES
  (1, 1001, 7, 9001, 150, 5),
  (2, 1002, 7, 9001, 50, 5),
  (3, 1004, 7, 9001, 200, 1),
  (4, 1007, 7, 9010, 30, 5),
  (5, 1009, 7, 9002, 300, 1),
  (6, 1010, 7, 9005, 40, 5),
  (7, 1011, 7, 9005, 70, 5);
INSERT INTO ventas.facturas VALUES
  (1001, 'FV1', '2016-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 150, 0),
  (1002, 'FV2', '2017-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 50, 0),
  (1003, 'FV3', '2018-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 0, 0),
  (1004, 'FV4', '2025-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 0, 200),
  (1006, 'FV6', '2025-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 0, 0),
  (1007, 'FV7', '2025-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 30, 0),
  (1008, 'FV8', '2025-03-01', 100, 'CLIENTE 100 SA', 1, 'O1', 0, 0),
  (1009, 'FV9', '2025-03-01', 103, 'UNEXUM', 2, 'O2', 0, 300),
  (1010, 'FV10', '2025-03-01', 102, 'CLIENTE 102', 3, 'O3', 40, 0),
  (1011, 'FV11', '2012-03-01', 102, 'CLIENTE 102', 3, 'O3', 70, 0);
"""


def _ejecutar_todo(c) -> None:
    for fichero in RETENCIONES:
        c.execute((SQL / "retenciones" / fichero).read_text(encoding="utf-8"))
    c.execute((SQL / "ventas" / "06b_retencion_cliente.sql").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F104_SANDBOX_DSN: la sandbox SQL de F-104 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f104_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            c.execute(DATOS)
            _ejecutar_todo(c)
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _filas(c, sql: str) -> list[tuple]:
    return c.execute(sql).fetchall()


def _d(valor: str) -> Decimal:
    return Decimal(valor)


# ===========================================================================
# retenciones
# ===========================================================================


def test_f104_sandbox_r4_cuentas_cliente_union(conexion) -> None:
    filas = _filas(conexion, """SELECT cuenta_id, cliente_id, codigo_cuenta, familia, criterio_seleccion
                                FROM retenciones.cuentas_cliente ORDER BY cuenta_id""")
    assert filas == [
        (9001, 100, "4308000001", "4308", "CUERETIDE"),
        (9002, None, "4338000002", "4338", "PREFIJO_43X8"),
        (9003, 101, "5540000003", "5540", "CUERETIDE"),
        (9005, 102, "4308000005", "4308", "CUERETIDE"),
    ]


def test_f104_sandbox_r1_r6_r7_estado_origen_y_cuenta(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT movimiento_id, estado, origen_retencion, cuenta_id, tipo_id, vencida_sin_liquidar
        FROM retenciones.movimientos WHERE sentido = 'CLIENTE'""")}
    assert filas == {
        501: ("BAJA", "EFECTO_RETENCION", 9001, 7, False),
        502: ("BAJA", "EFECTO_RETENCION", 9001, 7, False),
        510: ("BAJA", "CUENTA_RETENCION", 9001, None, False),
        511: ("VIVA", "CUENTA_RETENCION", 9001, None, True),
        512: ("LIQUIDADA", "CUENTA_RETENCION", 9001, None, False),
        520: ("VIVA", "EFECTO_RETENCION", 9001, 7, True),
        530: ("LIQUIDADA", "EFECTO_RETENCION", 9001, 7, False),
        550: ("VIVA", "EFECTO_RETENCION", 9010, 7, False),
        560: ("VIVA", "EFECTO_RETENCION", 9005, 7, False),
    }, "540 (retide 0 en una cuenta que no es de retención) no entra"


def test_f104_sandbox_r9_proveedor_intacto(conexion) -> None:
    assert _filas(conexion, """SELECT movimiento_id, estado, origen_retencion, cuenta_id, entidad_cif
                               FROM retenciones.movimientos WHERE sentido = 'PROVEEDOR'""") == [
        (601, "VIVA", "EFECTO_RETENCION", 8001, "B00000000"),
    ]
    assert _filas(conexion, "SELECT count(*) FROM retenciones.movimientos WHERE sentido = 'CLIENTE' "
                            "AND entidad_cif IS NOT NULL") == [(0,)]


def test_f104_sandbox_r11_saldo_contable_cliente(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cuenta_id, altas, bajas, saldo_inicial, saldo, saldo_anterior_2016, num_apuntes
        FROM retenciones.saldo_contable_cliente""")}
    assert filas == {
        9001: (_d("200.00"), _d("-150.00"), _d("500.00"), _d("550.00"), _d("500.00"), 3),
        9002: (_d("300.00"), _d("0.00"), _d("0.00"), _d("300.00"), _d("0.00"), 1),
        9005: (_d("40.00"), _d("0.00"), _d("0.00"), _d("40.00"), _d("0.00"), 1),
    }, "la 9010 no es de retención: sus apuntes no entran"


def test_f104_sandbox_r12_cuadre_por_cuenta(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cuenta_id, codigo_cuenta, cliente_id, saldo_contable, viva_efectos,
               num_efectos_vivos, diferencia, categoria
        FROM retenciones.v_cuadre_cliente""")}
    assert filas == {
        9001: ("4308000001", 100, _d("550.00"), _d("160.00"), 2, _d("390.00"), "CONTABILIDAD_MAYOR"),
        9002: ("4338000002", None, _d("300.00"), _d("0.00"), 0, _d("300.00"), "SIN_EFECTOS_VIVOS"),
        9005: ("4308000005", 102, _d("40.00"), _d("40.00"), 1, _d("0.00"), "CUADRA"),
        9010: ("4300000010", None, _d("0.00"), _d("10.00"), 1, _d("-10.00"), "SIN_SALDO_CONTABLE"),
    }


def test_f104_sandbox_r15_las_vistas_pbi_siguen_construyendo(conexion) -> None:
    assert _filas(conexion, "SELECT to_regclass('retenciones.v_pbi_retenciones_vivas') IS NOT NULL") == [
        (True,)
    ]


# ===========================================================================
# ventas
# ===========================================================================


def test_f104_sandbox_r27_r28_r29_retencion_factura(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT factura_id, cuenta_id, retencion, efectos, num_efectos, efectos_viva,
               efectos_liquidada, efectos_agrupada, diferencia, motivo
        FROM ventas.retencion_factura""")}
    cero = _d("0.00")
    assert filas == {
        1001: (9001, _d("150.00"), _d("150.00"), 2, cero, cero, _d("150.00"), cero, "CUADRA"),
        1002: (9001, _d("50.00"), _d("40.00"), 1, _d("40.00"), cero, cero, _d("10.00"), "DIFIERE"),
        1003: (9001, cero, _d("25.00"), 1, cero, _d("25.00"), cero, _d("-25.00"),
               "EFECTO_SIN_RETENCION"),
        1004: (9001, _d("200.00"), cero, 0, cero, cero, cero, _d("200.00"), "SIN_EFECTO"),
        1006: (9010, cero, _d("10.00"), 1, _d("10.00"), cero, cero, _d("-10.00"),
               "EFECTO_SIN_RETENCION"),
        1007: (None, cero, cero, 0, cero, cero, cero, cero, "SIN_CUENTA_RETENCION"),
        1009: (9002, _d("300.00"), cero, 0, cero, cero, cero, _d("300.00"), "SIN_EFECTO"),
        1010: (9005, _d("40.00"), _d("40.00"), 1, _d("40.00"), cero, cero, cero, "CUADRA"),
        1011: (9005, _d("70.00"), cero, 0, cero, cero, cero, _d("70.00"), "SIN_EFECTO"),
    }, "1008 (nada) no entra"


def test_f104_sandbox_r31_retencion_cuenta(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cuenta_id, cliente_id, categoria, retencion_facturas, retencion_sin_efecto,
               num_facturas_sin_efecto, viva_sin_factura, diferencia_sin_explicar
        FROM ventas.retencion_cuenta""")}
    assert filas == {
        9001: (100, "CONTABILIDAD_MAYOR", _d("400.00"), _d("200.00"), 1, _d("120.00"), _d("310.00")),
        9002: (None, "SIN_EFECTOS_VIVOS", _d("300.00"), _d("300.00"), 1, _d("0.00"), _d("0.00")),
        9005: (102, "CUADRA", _d("110.00"), _d("70.00"), 1, _d("0.00"), None),
        9010: (None, "SIN_SALDO_CONTABLE", _d("0.00"), _d("0.00"), 0, _d("0.00"), _d("-10.00")),
    }


def test_f104_sandbox_r32_v_retencion_cliente(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cliente_id, num_facturas, retencion, efectos, retencion_sin_efecto,
               diferencia_facturas, saldo_contable, viva_sin_factura, diferencia_sin_explicar
        FROM ventas.v_retencion_cliente""")}
    assert filas == {
        100: (6, _d("400.00"), _d("225.00"), _d("200.00"), _d("-25.00"), _d("550.00"),
              _d("120.00"), _d("310.00")),
        102: (2, _d("110.00"), _d("40.00"), _d("70.00"), _d("0.00"), _d("40.00"), _d("0.00"), None),
        103: (1, _d("300.00"), _d("0.00"), _d("300.00"), _d("0.00"), _d("0.00"), _d("0.00"), None),
    }


# ===========================================================================
# Las guardas (R5, R33)
# ===========================================================================


def _falla(conexion, sentencias: str, fichero: Path) -> str:
    import psycopg

    with pytest.raises(psycopg.Error) as error, conexion.transaction():
        conexion.execute(sentencias)
        conexion.execute(fichero.read_text(encoding="utf-8"))
    return str(error.value)


def test_f104_sandbox_r5_cuentas_vacias_fallan_con_su_nombre(conexion) -> None:
    mensaje = _falla(conexion, "UPDATE raw.cli SET cueretide = 0; UPDATE raw.con SET tip = 16;",
                     SQL / "retenciones" / "01_movimientos.sql")
    assert "retenciones.cuentas_cliente" in mensaje
    assert _filas(conexion, "SELECT count(*) FROM retenciones.cuentas_cliente") == [(4,)]


def test_f104_sandbox_r5_dos_clientes_una_cuenta_falla(conexion) -> None:
    mensaje = _falla(conexion, "UPDATE raw.cli SET cueretide = 9001 WHERE ide = 103;",
                     SQL / "retenciones" / "01_movimientos.sql")
    assert "cuentas_cliente" in mensaje


def test_f104_sandbox_r33_sin_cuadre_de_cliente_falla_antes_de_borrar(conexion) -> None:
    mensaje = _falla(conexion, "DROP VIEW retenciones.v_cuadre_cliente;",
                     SQL / "ventas" / "06b_retencion_cliente.sql")
    assert "retenciones.v_cuadre_cliente" in mensaje and "origen_retencion" in mensaje
    assert _filas(conexion, "SELECT count(*) FROM ventas.retencion_factura") == [(9,)]
