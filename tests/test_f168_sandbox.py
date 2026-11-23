# tests/test_f168_sandbox.py
"""
F-168 · El texto largo, ejecutado contra un PostgreSQL desechable (design §6).

Solo con `F168_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA y la borra al terminar, como
`tests/test_f161_sandbox.py`. Carga `stg/00_functions.sql` y `stg/01_ddl.sql`
reales, un `raw` mínimo con los tipos de la ingesta (ids `integer`, importes
`double precision`, `tex` como `text`) y ejecuta los ficheros REALES
`stg/11_texto_largo.sql`, `stg/12_partida_texto.sql`, `compras/07_texto.sql`,
`compras/16_textos_linea.sql` y `descompuestos/00`, `01` y `02` (ESTUDIO y
PLANIF_JO). El oráculo es `domain/texto_largo.py`.

Casos: partida solo de venta y capítulo con texto (R10), texto de 16.000
(R8), CRLF y control (R5), línea con partida sin texto y con la planificación
editada (R14), dos líneas con el mismo texto -> un `textos` (R15), comparativo
con memo (R18), vista sin pérdida (R16), PLANIF_JO con el mismo `texto_id` que
su NECESIDAD (R20, R21) y un fallo provocado que deja la tabla anterior (R23).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from etl_sigrid.domain.texto_largo import TOPE_CARACTERES, limpiar, texto_id

DSN = os.environ.get("F168_SANDBOX_DSN")
DIR_SQL = Path(__file__).resolve().parents[1] / "etl_sigrid" / "infrastructure" / "postgres" / "sql"

RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA stg; CREATE SCHEMA mart; CREATE SCHEMA compras;
CREATE TABLE raw.obrparpar (ide integer, obride integer, des varchar, tex text);
CREATE TABLE raw.dnc (ide integer, obride integer);
CREATE TABLE raw.dncpro (ide integer, dncide integer, paride integer, pos integer,
                         cod2 varchar, res varchar, unimed varchar,
                         can double precision, canren double precision,
                         pre double precision, natide integer, proide integer,
                         factip integer, faccan double precision, entide integer,
                         adjctride integer, adjctrlin integer, fec integer,
                         gpcide integer, niv integer, nivpad integer, tex text);
CREATE TABLE raw.dcopro (ide integer, docide integer, obride integer, paride integer,
                         dncproide integer, tex text);
CREATE TABLE raw.ctrpro (LIKE raw.dcopro);
CREATE TABLE raw.dcapro (LIKE raw.dcopro);
CREATE TABLE raw.dcfpro (LIKE raw.dcopro);
CREATE TABLE raw.con (ide integer, tip integer, cod varchar, tex text);
CREATE TABLE raw.obr (ide integer, dncide integer);
CREATE TABLE raw.auxpronat (ide integer, cod varchar, res varchar);
"""

OBRA = 100
LARGO = "x" * (TOPE_CARACTERES + 500)          # Sigrid lo entrega cortado a 16.000
EXACTO = "y" * TOPE_CARACTERES
SUCIO = "  Hormigón HA-25\r\nvertido\x07 con bomba \r\n"
NEC = "Encofrado metálico a dos caras"
EDITADO = "Encofrado metálico a dos caras, con berenjenos"

#: (ide, obra, tex) de `obrparpar`: 1 y 2 partidas, 3 capítulo, 4 solo de venta,
#: 5 recortada, 6 de 16.000 justos, 7 vacía tras limpiar, 8 sin texto.
PARTIDAS = [
    (1, OBRA, SUCIO), (2, OBRA, NEC), (3, OBRA, "Capítulo de estructura"),
    (4, OBRA, "Solo de venta"), (5, OBRA, LARGO[:TOPE_CARACTERES]),
    (6, OBRA, EXACTO[:-1]), (7, OBRA, " \r\n\t "), (8, OBRA, None),
]


def _registro(campos: dict[int, str], total: int = 38) -> str:
    lista = [""] * total
    lista[0] = "~D"
    for posicion, valor in campos.items():
        lista[posicion] = valor
    return "|".join(lista)


def _leer(nombre: str) -> str:
    return (DIR_SQL / nombre).read_text(encoding="utf-8")


def _funcion(fichero: str, nombre: str) -> str:
    texto = _leer(fichero)
    inicio = texto.index(f"CREATE OR REPLACE FUNCTION {nombre}")
    return texto[inicio:texto.index("$$;", inicio) + 3]


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F168_SANDBOX_DSN: la sandbox SQL de F-168 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f168_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            for nombre in ("stg/00_functions.sql", "stg/01_ddl.sql"):
                c.execute(_leer(nombre))
            _cargar(c)
            for nombre in ("stg/11_texto_largo.sql", "stg/12_partida_texto.sql"):
                c.execute(_leer(nombre))
            for funcion in ("compras.fn_sigrid_date", "compras.fn_serie",
                            "compras.fn_tipo_documento"):
                c.execute(_funcion("compras/00_setup.sql", funcion))
            for nombre in ("compras/07_texto.sql", "compras/16_textos_linea.sql",
                           "descompuestos/00_setup.sql", "descompuestos/01_troceado.sql"):
                c.execute(_leer(nombre))
            _cargar_descompuestos(c)
            c.execute(_leer("descompuestos/02_lineas_coste.sql"))
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _cargar(c) -> None:
    with c.cursor() as cur:
        cur.executemany("INSERT INTO raw.obrparpar (ide, obride, tex) VALUES (%s, %s, %s)", PARTIDAS)
        cur.execute(
            "INSERT INTO stg.partidas (partida_id, obra_id, codigo_partida, descripcion_corta) "
            "VALUES (1, 100, '04.01', 'HORMIGON'), (2, 100, '04.02', 'ENCOFRADO'), "
            "(3, 100, '04', 'ESTRUCTURA'), (5, 100, '04.05', 'LARGA'), (6, 100, '04.06', 'EXACTA')")
        cur.execute("INSERT INTO raw.dnc VALUES (50, 100)")
        # Necesidad: 501 de la partida 2 con su texto; 502 de la partida 8 (sin texto
        # de partida); 503 sin texto propio (no sale).
        cur.executemany(
            "INSERT INTO raw.dncpro (ide, dncide, paride, pos, res, can, canren, pre, "
            "factip, faccan, tex) VALUES (%s, 50, %s, %s, 'R', 1, 1, 10, 0, 0, %s)",
            [(501, 2, 1, NEC), (502, 8, 2, "Texto propio de la 8"), (503, 2, 3, None)])
        # Oferta igual que su necesidad; contrato editado; albarán sin partida con
        # texto; dos facturas con el mismo texto (un solo `textos`).
        cur.execute("INSERT INTO raw.dcopro VALUES (601, 60, 100, 2, 501, %s)", (NEC,))
        cur.execute("INSERT INTO raw.ctrpro VALUES (701, 70, 100, 2, 501, %s)", (EDITADO,))
        cur.execute("INSERT INTO raw.dcapro VALUES (801, 80, 100, 8, 0, %s)", (SUCIO,))
        cur.executemany("INSERT INTO raw.dcfpro VALUES (%s, 90, 100, 1, 0, %s)",
                        [(901, SUCIO), (902, SUCIO.strip())])
        cur.executemany(
            "INSERT INTO raw.con (ide, tip, cod, tex) VALUES (%s, %s, %s, %s)",
            [(60, 12, 'OF-1', "Oferta revisada\n---\nAlta"),
             (46, 46, 'CMP-1', "Adjudicar a X [01/02/2026 10:00:00 Usuario: ana]\n---\nAlta"),
             (90, 15, 'FR-1', "Factura conforme")])
        cur.execute("INSERT INTO raw.obr VALUES (100, 50)")


def _cargar_descompuestos(c) -> None:
    des = "\n".join([
        _registro({1: "E01", 2: "Hormigon", 3: "10", 4: "1", 9: SUCIO.replace("\r\n", "\n"), 14: "1"}),
        _registro({1: "E02", 2: "Acero", 3: "5", 4: "1", 14: "2"}),
    ])
    c.execute(
        "INSERT INTO descompuestos._des_texto (presupuesto_id, obra_id, partida_id, ambito_id, "
        "fase_num, cantidad, precio, haydes, des) VALUES (1, 100, 1, 3, 0, 1, 20, 1, %s)", (des,))


def _uno(c, sql: str, *params):
    return c.execute(sql, params).fetchone()


# ---------------------------------------------------------------------------
# stg.partida_texto (R5, R8, R9, R10)
# ---------------------------------------------------------------------------


def test_f168_r10_sin_filtro_capitulo_y_solo_venta(conexion) -> None:
    filas = dict(conexion.execute(
        "SELECT partida_id, codigo_partida FROM stg.partida_texto").fetchall())
    assert set(filas) == {1, 2, 3, 4, 5, 6}, "7 queda vacía y 8 no tiene texto"
    assert filas[3] == "04" and filas[4] is None


def test_f168_r5_limpieza_igual_que_el_oraculo(conexion) -> None:
    for ide, _, tex in PARTIDAS:
        fila = _uno(conexion, "SELECT texto, texto_id FROM stg.partida_texto WHERE partida_id = %s", ide)
        esperado = limpiar(tex)
        if esperado is None:
            assert fila is None, ide
        else:
            assert fila == (esperado, texto_id(esperado)), ide
    assert _uno(conexion, "SELECT texto FROM stg.partida_texto WHERE partida_id = 1")[0] == (
        "Hormigón HA-25\nvertido con bomba")


def test_f168_r8_recortado_desde_el_tope(conexion) -> None:
    filas = dict(conexion.execute(
        "SELECT partida_id, recortado FROM stg.partida_texto WHERE partida_id IN (5, 6)").fetchall())
    assert filas == {5: True, 6: False}


# ---------------------------------------------------------------------------
# compras (R12-R16, R18)
# ---------------------------------------------------------------------------


def test_f168_r13_r14_las_igualdades(conexion) -> None:
    filas = {(t, i): (p, n) for t, i, p, n in conexion.execute(
        "SELECT tipo_linea, linea_id, igual_a_partida, igual_a_necesidad FROM compras.linea_texto")}
    assert filas[("NECESIDAD", 501)] == (True, None)
    assert filas[("NECESIDAD", 502)] == (None, None), "partida 8 sin texto: NULL, no FALSE"
    assert ("NECESIDAD", 503) not in filas
    assert filas[("OFERTA", 601)] == (True, True)
    assert filas[("CONTRATO", 701)] == (False, False), "editado respecto a la planificacion"
    assert filas[("ALBARAN", 801)] == (None, None)
    assert filas[("FACTURA", 901)] == (True, None)


def test_f168_r13_cero_es_nulo(conexion) -> None:
    assert _uno(conexion, "SELECT linea_necesidad_id FROM compras.linea_texto "
                          "WHERE tipo_linea = 'ALBARAN' AND linea_id = 801")[0] is None


def test_f168_r15_mismo_texto_un_solo_textos(conexion) -> None:
    ids = {r[0] for r in conexion.execute(
        "SELECT texto_id FROM compras.linea_texto WHERE linea_id IN (801, 901, 902)")}
    assert ids == {texto_id(limpiar(SUCIO))}
    assert _uno(conexion, "SELECT count(*) FROM compras.textos WHERE texto_id = %s",
                texto_id(limpiar(SUCIO)))[0] == 1


def test_f168_r16_la_vista_no_pierde_filas(conexion) -> None:
    assert (_uno(conexion, "SELECT count(*) FROM compras.v_linea_texto")
            == _uno(conexion, "SELECT count(*) FROM compras.linea_texto"))


def test_f168_r18_memo_de_oferta_y_comparativo(conexion) -> None:
    tipos = dict(conexion.execute(
        "SELECT documento_id, tipo_documento FROM compras.documento_texto").fetchall())
    assert tipos == {60: "OFERTA", 46: "COMPARATIVO", 90: "FACTURA"}
    usuario = _uno(conexion, "SELECT usuario FROM compras.documento_comentarios "
                             "WHERE documento_id = 46 AND orden = 1")[0]
    assert usuario == "ana"


# ---------------------------------------------------------------------------
# descompuestos (R20, R21)
# ---------------------------------------------------------------------------


def test_f168_r20_planif_jo_con_el_texto_id_de_su_necesidad(conexion) -> None:
    distintas = _uno(conexion, """
        SELECT count(*) FROM descompuestos.lineas d
        JOIN compras.linea_texto c ON c.tipo_linea = 'NECESIDAD' AND c.linea_id = d.dncpro_id
        WHERE d.origen = 'PLANIF_JO' AND d.texto_id IS DISTINCT FROM c.texto_id""")[0]
    assert distintas == 0
    assert _uno(conexion, "SELECT count(*) FROM descompuestos.lineas "
                          "WHERE origen = 'PLANIF_JO' AND texto_id IS NOT NULL")[0] == 2


def test_f168_r20_estudio_con_el_campo_9(conexion) -> None:
    filas = dict(conexion.execute(
        "SELECT codigo_elemento, texto_id FROM descompuestos.lineas WHERE origen = 'ESTUDIO'").fetchall())
    assert filas == {"E01": texto_id(limpiar(SUCIO)), "E02": None}


def test_f168_r21_toda_linea_con_texto_tiene_su_texto(conexion) -> None:
    huerfanas = _uno(conexion, """
        SELECT count(*) FROM descompuestos.lineas l
        LEFT JOIN descompuestos.textos t USING (texto_id)
        WHERE l.texto_id IS NOT NULL AND t.texto_id IS NULL""")[0]
    assert huerfanas == 0


def test_f168_r21_rehacer_no_duplica_textos(conexion) -> None:
    antes = _uno(conexion, "SELECT count(*) FROM descompuestos.textos")[0]
    conexion.execute(_leer("descompuestos/02_lineas_coste.sql"))
    assert _uno(conexion, "SELECT count(*) FROM descompuestos.textos")[0] == antes


# ---------------------------------------------------------------------------
# R23 · un fallo deja la tabla anterior
# ---------------------------------------------------------------------------


def test_f168_r23_un_fallo_deja_la_tabla_anterior(conexion) -> None:
    import psycopg

    antes = _uno(conexion, "SELECT count(*) FROM stg.partida_texto")[0]
    conexion.execute("ALTER TABLE stg.partidas RENAME TO partidas_fuera")
    try:
        with pytest.raises(psycopg.errors.UndefinedTable):
            conexion.execute(_leer("stg/12_partida_texto.sql"))
    finally:
        conexion.execute("ALTER TABLE stg.partidas_fuera RENAME TO partidas")
    assert _uno(conexion, "SELECT count(*) FROM stg.partida_texto")[0] == antes
