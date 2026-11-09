# tests/test_f040_sandbox.py
"""
F-040 · El SQL de `sql/ventas/`, EJECUTADO contra un PostgreSQL desechable
(R5-R25 en sintético).

Solo con `F040_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él,
`skip`. El fixture crea una BASE NUEVA y la borra al terminar: nunca se tira un
esquema (el veto de `tests/test_f067_reset.py`). Monta un `raw` mínimo con los
TIPOS DE LA INGESTA (ids, clases y fechas `integer`, `reccla` `smallint`,
importes y cantidades `double precision`, texto `character varying`: un
`ROUND(double, 2)` revienta aquí igual que en Azure), los dos objetos de
`tesoreria` que leen las vistas y un `maestro.centros_coste` de tabla, y
ejecuta los ocho ficheros en el orden de `build_ventas_step.SUB_PASOS`.

Lo que prueba:

1. Las funciones SQL dan lo mismo que el oráculo `etl_sigrid/domain/ventas.py`
   (R6, R8, R11) en los casos documentados y en 2.000 CIF aleatorios.
2. Las cifras de un caso construido a mano: persona física sin CIF y con
   nombre (R7), obra por centro y por cabecera (R10), las cuatro columnas
   (R11), a cuenta / a origen / `base_origen_contrato` (R15), el enlace N:M
   (R16), el cobro sin BAJA (R17), el seguimiento = dominio (R18), el
   contraste (R19), la cobertura (R20) y `ventas_restringida` (R21-R23).
3. La guarda (R24, R25) pasa con lo construido y revienta, con su cifra, si se
   cuela un CIF de persona, una descripción, una columna personal o una fila.
"""

from __future__ import annotations

import os
import random
import uuid
from decimal import Decimal

import pytest

from etl_sigrid.domain import ventas as v

DSN = os.environ.get("F040_SANDBOX_DSN")

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA maestro; CREATE SCHEMA tesoreria;
CREATE TABLE raw.con (ide integer, tip integer, cod varchar(24), res varchar(128),
                      emp integer, est integer, fecbaj integer);
CREATE TABLE raw.conest (ide integer, tip integer, est integer, cod varchar(24),
                         res varchar(128));
CREATE TABLE raw.cli (ide integer, tipcif varchar(2), cifpai varchar(2), cif varchar(24),
                      raz varchar(128), perfis integer, cenide integer, taride integer,
                      secide integer, pagide integer, efeide integer, cueide integer,
                      cueretide integer, dir1 varchar(48), dir2 varchar(48),
                      dircpo varchar(16), dir varchar(255), tel varchar(24),
                      tel2 varchar(24), ele varchar(128));
CREATE TABLE raw.obr (ide integer, cenide integer, entide integer);
CREATE TABLE raw.obrctr (ide integer, obride integer, cliide integer);
CREATE TABLE raw.dvf (ide integer, cla integer, entide integer, cenide integer,
                      ctride integer, fecdoc integer, totbas double precision,
                      totiva double precision, totdoc double precision, obride integer,
                      fas integer, tot double precision, totpag double precision,
                      impbru double precision, impnet double precision,
                      impdes double precision, imprec double precision, ivaide integer,
                      pagide integer, efeide integer, estfac integer, docoriide integer,
                      expide integer, cueide integer, entcif varchar(24),
                      entres varchar(128), diremp1 varchar(255), dircon1 varchar(255),
                      dirdir1 varchar(255), diremp2 varchar(255), dircon2 varchar(255),
                      dirdir2 varchar(255), diremp3 varchar(255), dircon3 varchar(255),
                      dirdir3 varchar(255));
CREATE TABLE raw.dvfpro (ide integer, docide integer, pos integer, res varchar(255),
                         can double precision, pre double precision, tot double precision,
                         ivaide integer, ivacuo double precision, cenide integer,
                         obride integer, paride integer, docoritip integer,
                         docoriide integer, linoriide integer, unimed varchar(8),
                         proide integer);
CREATE TABLE raw.dvfrec (ide integer, docide integer, recide integer, pos integer,
                         bas double precision, valpor double precision,
                         cuo double precision, reccla smallint);
CREATE TABLE raw.cer (ide integer, cla integer, entide integer, cenide integer,
                      obride integer, ctride integer, fas integer, fecdoc integer,
                      estfac integer, docoriide integer, totbas double precision,
                      totiva double precision, totdoc double precision);
CREATE TABLE raw.cerpro (ide integer, docide integer, pos integer, res varchar(255),
                         can double precision, pre double precision, tot double precision,
                         imporiori double precision, imporiant double precision);
CREATE TABLE raw.cerrec (ide integer, docide integer, recide integer, pos integer,
                         bas double precision, valpor double precision,
                         cuo double precision, reccla smallint);
CREATE TABLE raw.cerprodes (ide integer, docproide integer, can double precision,
                            docdestip integer, docdescod varchar(24), docdeside integer,
                            lindeside integer);
CREATE TABLE raw.cob (ide integer, conide integer, tot double precision);
CREATE TABLE maestro.centros_coste (centro_coste_id integer, obra_id integer,
                                    codigo_obra varchar(24));
CREATE TABLE tesoreria.efectos (efecto_id integer, sentido varchar(5), documento_id integer,
                                importe numeric(18,2), estado_tesoreria varchar(10),
                                fecha_real date);
CREATE TABLE tesoreria.devengo_corte_obra (obra_id integer, concepto varchar(5),
                                           venta_real_origen_con_coeficientes numeric(18,2));
"""

DATOS = """
INSERT INTO raw.conest (ide, tip, est, cod, res) VALUES
  (1, 11, 2, '2', 'Emitida'), (2, 54, 1, '1', 'Pendiente de emision'),
  (3, 54, 3, '3', 'Emitida'), (4, 54, 4, '4', 'Aprobada por propiedad'),
  (5, 54, 2, '2', 'Aprobada por gerencia');
-- Clientes: 1 sociedad, 2 DNI con separadores, 3 perfis 1 con CIF de sociedad,
-- 4 el CIF de 1 escrito de otra forma (repetido) y un codigo (`con.cod`) con
-- forma de NIF de persona (R1-H1), 5 sin CIF.
INSERT INTO raw.cli (ide, tipcif, cifpai, cif, raz, perfis, dir, dir1, dircpo, tel, ele) VALUES
  (1, '01', 'ES', 'B12345678', 'ACME SA', 0, 'Calle A 1, Madrid', 'Calle A 1', '28001', '910000000', 'a@acme.es'),
  (2, '02', 'ES', '12345678-z', 'JUAN PEREZ', 0, 'Calle B 2', 'Calle B 2', '28002', '600000000', 'juan@x.es'),
  (3, '01', 'ES', 'B87654321', 'MARIA LOPEZ', 1, NULL, NULL, NULL, NULL, NULL),
  (4, '01', 'ES', 'b-12.345.678', 'ACME DUPLICADA', 0, NULL, NULL, NULL, NULL, NULL),
  (5, '01', 'ES', '', 'SIN CIF', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO raw.con (ide, tip, cod, res, emp, est, fecbaj) VALUES
  (1, 4, 'C1', 'ACME SA', 1, 0, 0), (2, 4, 'C2', 'JUAN PEREZ', 1, 0, 0),
  (3, 4, 'C3', 'MARIA LOPEZ', 1, 0, 0), (4, 4, '87654321-x', 'ACME DUP', 1, 0, 0),
  (5, 4, 'C5', 'SIN CIF', 1, 0, 0),
  (500, 3, '0500', 'OBRA 500', 1, 0, 0), (501, 3, '0501', 'OBRA 501', 1, 0, 0),
  (700, 30, 'CONT_PPAL', 'CONTRATO PRINCIPAL', 1, 0, 0),
  (1001, 11, 'FV1', 'f1', 1, 2, 0), (1002, 11, 'FV2', 'f2', 1, 2, 0),
  (1003, 11, 'FV3', 'f3', 1, 2, 20260105), (1004, 11, 'FV4', 'f4', 1, 2, 0),
  (4001, 54, '0500.CONT_PPAL.01', 'c1', 1, 3, 0),
  (4002, 54, '0500.CONT_PPAL.02', 'c2', 1, 4, 0),
  (4003, 54, '0500.CONT_PPAL.03', 'c3', 1, 1, 0),
  (4004, 54, '0500.SIN.01', 'c4', 1, 2, 0),
  (4005, 54, '0501.X.01', 'c5', 1, 3, 0),
  (4006, 54, '0501.X.02', 'c6', 1, 3, 0),
  (4007, 54, '0501.X.03', 'c7', 1, 3, 0),
  (8000, 60, 'COEF_RECGG', 'Gastos generales', 1, 0, 0),
  (8001, 60, 'RETESP', 'Retencion 5% garantia (sin iva)', 1, 0, 0),
  (8005, 60, 'RET5', 'Retencion 5%', 1, 0, 0),
  (8003, 60, 'ret02', 'Retencion alquiler', 1, 0, 0);
INSERT INTO raw.obr (ide, cenide, entide) VALUES (500, 900, 1), (501, 902, 2);
INSERT INTO raw.obrctr (ide, obride, cliide) VALUES (700, 500, 1);
INSERT INTO maestro.centros_coste VALUES (900, 500, '0500'), (901, NULL, NULL), (902, 501, '0501');
-- Facturas: 1001 por centro (obra 500); 1002 de persona, sin centro, por cabecera
-- (501); 1003 rectificativa con centro de estructura y cabecera 500 (sin obra:
-- el centro decide); 1004 de 501 por centro.
INSERT INTO raw.dvf (ide, cla, entide, cenide, ctride, fecdoc, totbas, totiva, totdoc, obride,
                     tot, totpag, entcif, entres, diremp1, dirdir1) VALUES
  (1001, 1, 1, 900, 700, 20260131, 100.1, 21.021, 121.121, 0, 112.121, 112.121,
   'B12345678', 'ACME SA', 'ACME', 'Calle A 1'),
  (1002, 1, 2, 0, 0, 20260215, 30.333, 6.37, 36.703, 501, 36.703, 36.703,
   '12345678Z', 'JUAN PEREZ', 'Juan', 'Calle B 2'),
  (1003, 1024, 1, 901, 0, 20260301, -50, -10.5, -60.5, 500, -60.5, -60.5,
   'B12345678', 'ACME ANTIGUA', NULL, NULL),
  (1004, 1, 1, 902, 0, 20260310, 40, 8.4, 48.4, 0, 48.4, 48.4, 'B12345678', 'ACME SA', NULL, NULL);
INSERT INTO raw.dvfpro (ide, docide, pos, res, can, pre, tot, docoriide, linoriide) VALUES
  (2001, 1001, 1, 'Certificacion 1', 1, 90.1, 90.1, 4001, 3001),
  (2002, 1001, 2, 'Ajuste', 1, 0.004, 0.004, 0, 0),
  (2003, 1002, 1, 'Alquiler plaza de garaje de Juan Perez', 1, 30.333, 30.333, 0, 0),
  (2004, 9999, 1, 'Linea huerfana', 1, 5, 5, 0, 0),
  (2005, 1004, 1, 'Linea de una certificacion que no es la suya', 1, 40, 40, 4002, 3001);
INSERT INTO raw.dvfrec (ide, docide, recide, bas, valpor, cuo, reccla) VALUES
  (6001, 1001, 8000, 90.1, 11.0988, 10.004, 0),
  (6002, 1001, 8001, 100.1, 5, -5.006, 1),
  (6003, 1001, 8005, 100.1, 4, -4.004, 5),
  (6004, 1001, 8003, 100.1, 1, -1.001, 3),
  (6005, 1002, NULL, 1, 1, 0.336, NULL),
  (6006, 9999, 8005, 1, 1, 7.777, 5);
-- Certificaciones del contrato 700: 4001 (3, emitida), 4002 (4), 4003 (1, borrador);
-- 4004 sin contrato; 4005 a 4007, de 501, para los estados del seguimiento.
INSERT INTO raw.cer (ide, cla, entide, cenide, obride, ctride, fas, fecdoc, estfac, docoriide,
                     totbas, totiva, totdoc) VALUES
  (4001, 1, 1, 900, 500, 700, 1, 20260131, 1, 0, 100.1, 21.021, 121.121),
  (4002, 1, 1, 900, 500, 700, 2, 20260228, 1, 4001, 50, 10.5, 60.5),
  (4003, 1, 1, 900, 500, 700, 3, 20260331, 0, 4002, 7, 1.47, 8.47),
  (4004, 1, 1, 900, 500, 0, 1, 20260131, 0, 0, 20, 4.2, 24.2),
  (4005, 1, 1, 902, 501, 0, 1, 20260331, 1, 0, 1, 0.21, 1.21),
  (4006, 1, 2, 902, 501, 0, 2, 20260331, 1, 0, 2, 0.42, 2.42),
  (4007, 1, 1, 902, 501, 0, 3, 20260331, 1, 0, 40, 8.4, 48.4);
INSERT INTO raw.cerpro (ide, docide, pos, tot, imporiori, imporiant) VALUES
  (3001, 4001, 1, 90.1, 90.1, 0), (3002, 4002, 1, 50, 140.1, 90.1),
  (3003, 4003, 1, 7, 147.1, 140.1), (3004, 4004, 1, 20, 20, NULL),
  (3005, 4005, 1, 1, 1, 0), (3006, 4006, 1, 2, 2, 0), (3007, 4007, 1, 40, 40, 0),
  (3008, 4001, 2, 0.004, NULL, NULL);
INSERT INTO raw.cerrec (ide, docide, recide, cuo, reccla) VALUES
  (7001, 4001, 8000, 10, 0), (7002, 4002, 8001, -2.5, 1), (7003, 4002, 8005, -2.5, 4);
-- 4001 -> 1001; 4002 -> 1001 y 1003 (1001 compartida); 4005 -> 1003; 4006 -> 1002;
-- 4007 -> 1004. Un destino de otro tipo y uno huerfano no entran.
INSERT INTO raw.cerprodes (ide, docproide, can, docdestip, docdeside) VALUES
  (1, 3001, 1, 11, 1001), (2, 3002, 0.5, 11, 1001), (3, 3002, 0.5, 11, 1003),
  (4, 3005, 1, 11, 1003), (5, 3006, 1, 11, 1002), (6, 3007, 1, 11, 1004),
  (7, 3008, 1, 11, 1001), (8, 3004, 1, 13, 1001), (9, 3004, 1, 11, 8888);
INSERT INTO raw.cob (ide, conide, tot) VALUES
  (5001, 1001, 60), (5002, 1001, 61.121), (5003, 0, 33), (5004, 1004, 48.4),
  (5005, 1002, 36.703);
INSERT INTO tesoreria.efectos VALUES
  (5001, 'COBRO', 1001, 60, 'REALIZADO', '2026-02-28'),
  (5002, 'COBRO', 1001, 61.12, 'PREVISTO', NULL),
  (5009, 'COBRO', 1001, 999, 'BAJA', NULL),
  (5004, 'COBRO', 1004, 48.40, 'REALIZADO', '2026-04-10'),
  (5005, 'COBRO', 1002, 36.70, 'PREVISTO', NULL),
  (5010, 'PAGO', 1001, 5, 'REALIZADO', '2026-02-01');
INSERT INTO tesoreria.devengo_corte_obra VALUES (500, 'VENTA', 300), (500, 'COSTE', 999),
                                                (501, 'COSTE', 10);
"""

FICHEROS = (
    "00_setup.sql", "01_clientes.sql", "02_facturas.sql", "03_certificaciones.sql",
    "04_enlace.sql", "05_vistas.sql", "06_restringida.sql", "07_guardas.sql",
)


def _dir_sql():
    from etl_sigrid.application.steps.build_ventas_step import DIR_SQL_VENTAS

    return DIR_SQL_VENTAS


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F040_SANDBOX_DSN: la sandbox SQL de F-040 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    from etl_sigrid.application.steps.build_ventas_step import SUB_PASOS

    base = f"f040_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            c.execute(DATOS)
            assert tuple(s.sql_file for s in SUB_PASOS) == FICHEROS
            for sub in SUB_PASOS:
                c.execute((_dir_sql() / sub.sql_file).read_text(encoding="utf-8"))
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _filas(c, sql: str, *params) -> list[tuple]:
    return c.execute(sql, params or None).fetchall()


def _uno(c, sql: str, *params):
    return c.execute(sql, params or None).fetchone()


def _d(x: str) -> Decimal:
    return Decimal(x)


# ===========================================================================
# 1 · funciones = oráculo
# ===========================================================================

CIFS = ["B12345678", "12345678Z", "12345678A", "X1234567L", "Y1234567X", "Z1234567R",
        "Z1234567T", "K1234567A", "A1234567J", "A1234567K", "I12345678", "", " ", None,
        "b-12.345 678", "1234", "ESB12345678", "00000000T", "12345678Z1", "x 1234567-l"]


def _cifs_aleatorios(n: int, semilla: int = 40) -> list[str]:
    azar = random.Random(semilla)
    cabezas = "0123456789XYZKLMABCDEFGHJNPQRSUVWIOT"
    colas = "TRWAGMYFPDXBNJZSQVHLCKE0123456789IOU"
    salida = []
    for _ in range(n):
        largo = azar.choice([7, 8, 9, 9, 9, 10])
        cuerpo = "".join(azar.choice("0123456789") for _ in range(max(largo - 2, 0)))
        cif = azar.choice(cabezas) + cuerpo + azar.choice(colas)
        if azar.random() < 0.2:
            cif = cif.lower()
        if azar.random() < 0.2:
            cif = cif[:3] + azar.choice(" .-") + cif[3:]
        salida.append(cif)
    return salida


@pytest.mark.parametrize("cif", CIFS + _cifs_aleatorios(2000))
def test_f040_sandbox_r6_r8_funciones_iguales_al_oraculo(conexion, cif) -> None:
    norm, persona0, persona1, valido = _uno(
        conexion,
        "SELECT ventas.fn_cif_normalizado(%s::TEXT), "
        "ventas.fn_es_persona_fisica(ventas.fn_cif_normalizado(%s::TEXT), 0), "
        "ventas.fn_es_persona_fisica(ventas.fn_cif_normalizado(%s::TEXT), 1), "
        "ventas.fn_cif_valido(ventas.fn_cif_normalizado(%s::TEXT))",
        cif, cif, cif, cif,
    )
    esperado = v.normalizar_cif(cif)
    assert norm == esperado
    assert persona0 is v.es_persona_fisica(esperado, 0)
    assert persona1 is v.es_persona_fisica(esperado, 1)
    assert valido is v.cif_valido(esperado)


@pytest.mark.parametrize("reccla", [None, 0, 1, 2, 3, 4, 5, 6, 255])
def test_f040_sandbox_r11_clase_recargo_igual_al_oraculo(conexion, reccla) -> None:
    (clase,) = _uno(conexion, "SELECT ventas.fn_clase_recargo(%s::INT)", reccla)
    assert clase == v.clase_recargo(reccla)


# ===========================================================================
# 2 · el caso construido a mano
# ===========================================================================


def test_f040_sandbox_r5_r8_clientes(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cliente_id, nombre, cif, cif_normalizado, es_persona_fisica, cif_valido,
               cif_repetido, num_obras, num_facturas, num_certificaciones, facturado_base,
               primera_factura::TEXT, ultima_factura::TEXT, codigo_cliente
        FROM ventas.clientes""")}
    assert len(filas) == 5
    assert filas[1][:6] == ("ACME SA", "B12345678", "B12345678", False, True, True)
    assert filas[1][6:9] == (1, 3, 6)
    assert filas[1][9] == _d("90.10") and filas[1][10:] == ("2026-01-31", "2026-03-10", "C1")
    # R7: la persona física, con nombre y sin CIF; válido y repetido, calculados antes.
    assert filas[2][:5] == ("JUAN PEREZ", None, None, True, True)
    assert filas[3][:4] == ("MARIA LOPEZ", None, None, True)
    assert filas[4][1:6] == ("b-12.345.678", "B12345678", False, True, True)
    assert filas[5][1:6] == ("", None, False, False, False)
    # R1-H1: el código, a NULL en persona física y con forma de NIF; = el dominio.
    codigos = {c: f[12] for c, f in filas.items()}
    assert codigos == {1: "C1", 2: None, 3: None, 4: None, 5: "C5"}
    personas = {c: f[3] for c, f in filas.items()}
    crudos = {1: "C1", 2: "C2", 3: "C3", 4: "87654321-x", 5: "C5"}
    for c, crudo in crudos.items():
        assert codigos[c] == v.codigo_cliente_publicado(crudo, personas[c]), c


def test_f040_sandbox_r9_r11_facturas(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT factura_id, cliente_id, nombre_cliente, cif_cliente, es_persona_fisica,
               obra_id, codigo_obra, obra_via, contrato_id, contrato_nombre, base, iva,
               total_sin_retencion, total, a_cobrar, importe_coeficientes,
               retencion_garantia, retencion_retesp, retencion_otras, num_lineas,
               anulada, estado_sigrid, fecha_factura::TEXT
        FROM ventas.facturas""")}
    assert filas[1001][:9] == (1, "ACME SA", "B12345678", False, 500, "0500", "CENTRO", 700,
                              "CONTRATO PRINCIPAL")
    assert filas[1001][9:14] == (_d("100.10"), _d("21.02"), _d("121.12"), _d("112.12"),
                                 _d("112.12"))
    # R11: coeficientes 10,00; garantía (clase 5) -4,00; RETESP -5,01 (en su columna);
    # otras (clase 3) -1,00.
    assert filas[1001][14:18] == (_d("10.00"), _d("-4.00"), _d("-5.01"), _d("-1.00"))
    assert filas[1001][18:] == (2, False, "Emitida", "2026-01-31")
    # R7 y R10: persona sin CIF y obra por la cabecera (sin centro).
    assert filas[1002][:8] == (2, "JUAN PEREZ", None, True, 501, "0501", "OBRA", None)
    assert filas[1002][17] == _d("0.34"), "reccla NULL va a otras"
    # R10: con centro de estructura la cabecera NO decide; anulada por fecbaj.
    assert filas[1003][4:7] == (None, None, None) and filas[1003][19] is True
    assert filas[1003][9] == _d("-50.00")


def test_f040_sandbox_r13_lineas_y_recargos(conexion) -> None:
    lineas = dict(_filas(conexion, "SELECT linea_id, descripcion FROM ventas.factura_lineas"))
    assert lineas[2001] == "Certificacion 1"
    assert lineas[2003] is None, "persona física"
    assert lineas[2004] is None, "factura inexistente: falla cerrado"
    origen = dict(_filas(conexion,
                         "SELECT linea_id, linea_certificacion_id FROM ventas.factura_lineas"))
    assert origen[2001] == 3001
    assert origen[2005] is None, "la línea 3001 no es del documento de origen 4002"
    recargos = {r[0]: r[1:] for r in _filas(conexion, """
        SELECT recargo_linea_id, codigo_recargo, clase_recargo, es_garantia, importe
        FROM ventas.factura_recargos""")}
    assert recargos[6002] == ("RETESP", "RETESP", False, _d("-5.01"))
    assert recargos[6003] == ("RET5", "GARANTIA", True, _d("-4.00"))
    assert recargos[6005] == (None, "OTRAS", False, _d("0.34"))
    assert len(recargos) == 6


def test_f040_sandbox_r14_r15_certificaciones(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT certificacion_id, cuenta, estado_sigrid, contrato_nombre, importe_a_cuenta,
               importe_a_origen, importe_anterior, base, base_origen_contrato,
               importe_coeficientes, retencion_garantia, retencion_retesp, num_lineas,
               mes::TEXT, certificacion_anterior_id, obra_id, facturada
        FROM ventas.certificaciones""")}
    assert filas[4001][:9] == (True, "Emitida", "CONTRATO PRINCIPAL", _d("90.10"), _d("90.10"),
                               _d("0.00"), _d("100.10"), _d("100.10"), _d("10.00"))
    assert filas[4001][9:] == (_d("0"), _d("0"), 2, "2026-01-01", None, 500, True)
    assert filas[4002][7] == _d("150.10"), "acumulada del contrato"
    assert filas[4002][9:11] == (_d("-2.50"), _d("-2.50")), "clase 4 garantía; RETESP aparte"
    assert filas[4002][13] == 4001
    assert filas[4003][:2] == (False, "Pendiente de emision")
    assert filas[4003][7] is None, "borrador: no cuenta"
    assert filas[4004][7] is None, "sin contrato"


def test_f040_sandbox_r16_enlace_n_m(conexion) -> None:
    pares = _filas(conexion, """SELECT certificacion_id, factura_id, num_lineas, cantidad
                                FROM ventas.certificacion_factura ORDER BY 1, 2""")
    assert pares == [
        (4001, 1001, 2, _d("2.0000")), (4002, 1001, 1, _d("0.5000")),
        (4002, 1003, 1, _d("0.5000")), (4005, 1003, 1, _d("1.0000")),
        (4006, 1002, 1, _d("1.0000")), (4007, 1004, 1, _d("1.0000")),
    ]


def test_f040_sandbox_r17_cobro_sin_bajas_ni_pagos(conexion) -> None:
    filas = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT factura_id, emitido, cobrado, pendiente, num_efectos, ultima_fecha_cobro::TEXT
        FROM ventas.v_factura_cobro""")}
    assert filas[1001] == (_d("121.12"), _d("60.00"), _d("61.12"), 2, "2026-02-28")
    assert filas[1003] == (_d("0"), _d("0"), _d("0"), 0, None)


def test_f040_sandbox_r18_seguimiento_igual_al_dominio(conexion) -> None:
    filas = _filas(conexion, """
        SELECT s.certificacion_id, s.estado_seguimiento, k.estado_codigo, s.num_facturas,
               s.emitido, s.cobrado, s.factura_compartida,
               (SELECT COALESCE(SUM(c.num_efectos), 0) FROM ventas.certificacion_factura cf
                JOIN ventas.v_factura_cobro c ON c.factura_id = cf.factura_id
                WHERE cf.certificacion_id = s.certificacion_id)
        FROM ventas.v_seguimiento_certificacion s
        JOIN ventas.certificaciones k ON k.certificacion_id = s.certificacion_id""")
    estados = {f[0]: f[1] for f in filas}
    assert estados == {
        4001: "COBRADA_PARCIAL", 4002: "COBRADA_PARCIAL", 4003: "BORRADOR",
        4004: "SIN_FACTURA", 4005: "FACTURADA_SIN_EFECTO", 4006: "PENDIENTE_COBRO",
        4007: "COBRADA",
    }
    for cert, estado, est, nfac, emitido, cobrado, _comp, nefe in filas:
        assert estado == v.estado_seguimiento(est, nfac, int(nefe), emitido, cobrado), cert
    compartida = {f[0]: f[6] for f in filas}
    assert compartida[4001] and compartida[4002] and not compartida[4007]


@pytest.mark.parametrize(("cobrado", "esperado"), [
    ("0.50", "COBRADA_PARCIAL"), ("0.01", "COBRADA_PARCIAL"), ("1.00", "COBRADA_PARCIAL"),
    ("0.00", "PENDIENTE_COBRO"),
])
def test_f040_sandbox_r18_frontera_de_lo_cobrado(conexion, cobrado, esperado) -> None:
    """R1-H3: lo cobrado entre 0 y 1 euro es COBRADA_PARCIAL, en la vista y en el
    dominio. La 4006 (factura 1002, 36,70 emitidos en un efecto PREVISTO) recibe
    un cobro REALIZADO de `cobrado`, dentro de una transacción que se deshace."""
    with conexion.transaction(force_rollback=True):
        conexion.execute("""INSERT INTO tesoreria.efectos
                             VALUES (5011, 'COBRO', 1002, %s, 'REALIZADO', '2026-03-15')""",
                         (_d(cobrado),))
        estado, est, nfac, emitido, cobrado_vista = _uno(conexion, """
            SELECT s.estado_seguimiento, k.estado_codigo, s.num_facturas, s.emitido, s.cobrado
            FROM ventas.v_seguimiento_certificacion s
            JOIN ventas.certificaciones k ON k.certificacion_id = s.certificacion_id
            WHERE s.certificacion_id = 4006""")
        nefe = _uno(conexion, """SELECT num_efectos FROM ventas.v_factura_cobro
                                  WHERE factura_id = 1002""")[0]
    assert cobrado_vista == _d(cobrado)
    assert estado == esperado
    assert estado == v.estado_seguimiento(est, nfac, int(nefe), emitido, cobrado_vista)


def test_f040_sandbox_r19_contraste_solo_venta(conexion) -> None:
    filas = _filas(conexion, "SELECT * FROM ventas.v_contraste_certificado_obra")
    # Certificado de 500: 4001 100,10 + 4002 50 + 4004 20 (4003, borrador, no);
    # facturado de 500: 1001 (1003 no tiene obra).
    assert filas == [(500, "0500", _d("300.00"), _d("170.10"), _d("100.10"), _d("129.90"),
                      _d("70.00"))]


def test_f040_sandbox_r20_cobertura(conexion) -> None:
    filas = {f[0]: f[1:5] for f in _filas(conexion, "SELECT * FROM ventas.cobertura_enlace")}
    assert filas == {
        "CERTIFICACION_FACTURA": (6, 5, _d("213.10"), _d("193.10")),
        "FACTURA_EFECTO": (4, 3, _d("120.43"), _d("170.43")),
        "EFECTO_FACTURA": (5, 4, _d("239.22"), _d("206.22")),
    }


def test_f040_sandbox_r21_r23_restringida(conexion) -> None:
    contacto = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT cliente_id, cif, es_persona_fisica, direccion, telefono, correo
        FROM ventas_restringida.clientes_contacto""")}
    assert contacto[2] == ("12345678-z", True, "Calle B 2", "600000000", "juan@x.es")
    codigos = dict(_filas(conexion, """SELECT cliente_id, codigo_cliente
                                       FROM ventas_restringida.clientes_contacto"""))
    assert codigos == {1: "C1", 2: "C2", 3: "C3", 4: "87654321-x", 5: "C5"}  # íntegros
    assert len(contacto) == 5
    cabecera = {f[0]: f[1:] for f in _filas(conexion, """
        SELECT factura_id, es_persona_fisica, nombre_cabecera, cif_cabecera,
               direccion_completa_1 FROM ventas_restringida.factura_cabecera""")}
    assert cabecera[1002] == (True, "JUAN PEREZ", "12345678Z", "Calle B 2")
    assert cabecera[1003][1] == "ACME ANTIGUA"
    lineas = dict(_filas(conexion, """SELECT linea_id, descripcion
                                      FROM ventas_restringida.factura_lineas_persona"""))
    assert lineas == {2003: "Alquiler plaza de garaje de Juan Perez", 2004: "Linea huerfana"}


# ===========================================================================
# 3 · la guarda
# ===========================================================================


def _guarda(c) -> None:
    c.execute((_dir_sql() / "07_guardas.sql").read_text(encoding="utf-8"))


def test_f040_sandbox_r24_r25_la_guarda_pasa_con_lo_construido(conexion) -> None:
    _guarda(conexion)


@pytest.mark.parametrize(("estropeo", "mensaje"), [
    ("UPDATE ventas.clientes SET cif = '12345678Z' WHERE cliente_id = 2",
     "F-040 R24: ventas.clientes publica el CIF de 1 personas fisicas"),
    ("UPDATE ventas.clientes SET cif = 'X1234567L' WHERE cliente_id = 1",
     "F-040 R24: ventas.clientes publica el CIF de 1 personas fisicas"),
    ("UPDATE ventas.clientes SET codigo_cliente = 'C2' WHERE cliente_id = 2",
     "F-040 R24: ventas.clientes publica el codigo de 1 clientes persona fisica o con forma de NIF"),
    ("UPDATE ventas.clientes SET codigo_cliente = '87654321X' WHERE cliente_id = 1",
     "F-040 R24: ventas.clientes publica el codigo de 1 clientes persona fisica o con forma de NIF"),
    ("UPDATE ventas.facturas SET cif_cliente = 'B87654321' WHERE factura_id = 1002",
     "F-040 R24: ventas.facturas publica el CIF de una persona fisica en 1 facturas"),
    ("UPDATE ventas.factura_lineas SET descripcion = 'x' WHERE linea_id = 2003",
     "F-040 R24: ventas.factura_lineas publica la descripcion de 1 lineas"),
    ("ALTER TABLE ventas.clientes ADD COLUMN telefono_movil TEXT",
     "F-040 R24: el esquema ventas tiene 1 columnas personales: clientes.telefono_movil"),
    ("ALTER TABLE ventas.facturas ADD COLUMN cif_cabecera TEXT",
     "F-040 R24: el esquema ventas tiene 1 columnas personales: facturas.cif_cabecera"),
    ("DELETE FROM ventas.facturas WHERE factura_id = 1004",
     "F-040 R25: ventas.facturas tiene 3 filas y raw.dvf 4"),
    ("DELETE FROM ventas.factura_lineas WHERE linea_id = 2004",
     "F-040 R25: ventas.factura_lineas tiene 4 filas y raw.dvfpro 5"),
    ("INSERT INTO ventas.certificaciones (certificacion_id) VALUES (1)",
     "F-040 R25: ventas.certificaciones tiene 8 filas y raw.cer 7"),
    ("DELETE FROM ventas_restringida.clientes_contacto WHERE cliente_id = 5",
     "F-040 R25: ventas_restringida.clientes_contacto tiene 4 filas y raw.cli 5"),
    ("DELETE FROM ventas_restringida.factura_cabecera WHERE factura_id = 1001",
     "F-040 R25: ventas_restringida.factura_cabecera tiene 3 filas y raw.dvf 4"),
    ("UPDATE ventas.facturas SET base = base + 0.01 WHERE factura_id = 1001",
     "F-040 R25: la base de ventas.facturas suma 120.44 y la de raw.dvf 120.43"),
    ("UPDATE ventas.facturas SET retencion_retesp = 0 WHERE factura_id = 1001",
     "F-040 R25: los recargos de ventas.facturas suman 5.34 y los de raw.dvfrec 0.33"),
    ("UPDATE ventas.certificaciones SET importe_coeficientes = 0 WHERE certificacion_id = 4001",
     "F-040 R25: los recargos de ventas.certificaciones suman -5.00 y los de raw.cerrec 5.00"),
])
def test_f040_sandbox_r24_r25_la_guarda_revienta_con_la_cifra(conexion, estropeo, mensaje) -> None:
    import psycopg

    with pytest.raises(psycopg.errors.RaiseException) as error:
        with conexion.transaction(force_rollback=True):
            conexion.execute(estropeo)
            _guarda(conexion)
    assert mensaje in str(error.value)
    _guarda(conexion)  # lo construido sigue intacto
