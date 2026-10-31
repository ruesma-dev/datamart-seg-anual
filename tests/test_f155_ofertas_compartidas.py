# tests/test_f155_ofertas_compartidas.py
"""F-155 · Una oferta compartida por dos comparativos no rompe `build_compras`.

El 2026-10-31 la nocturna falló dos veces en el sub-paso `comparativos`:
`could not create unique index "comparativo_ofertas_pkey" ... Key
(oferta_id)=(2796053) is duplicated`. En Sigrid se creó el comparativo
COM26/0014 reutilizando las 6 MISMAS ofertas del 0697.0_0037: `raw.comprv`
tenía 72.113 filas y 72.107 `docide` distintos. El grano de
`compras.comparativo_ofertas` pasa a ser la INVITACIÓN (`invitacion_id` =
`comprv.ide`, único: 72.113 de 72.113, medido en solo lectura).

Dos bloques:

* Estáticos (siempre): la clave declarada en el SQL y en el diccionario, y que
  los consumidores no unan por `oferta_id` como si fuera única.
* Sandbox (solo con `F155_SANDBOX_DSN`, un Postgres desechable): ejecuta
  `00_setup.sql`, `08`, `09` y `14` reales sobre `raw` con los TIPOS de la
  ingesta (importes `double precision`) y el caso reproducido: una oferta en
  dos comparativos. No toca Azure ni la base del `.env`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
DICCIONARIO = RAIZ / "config" / "diccionario" / "compras.yaml"


def _sql(nombre: str) -> str:
    return (DIR_SQL / nombre).read_text(encoding="utf-8")


def _compacto(texto: str) -> str:
    """El SQL sin comentarios de línea y con los espacios colapsados."""
    lineas = [ln.split("--", 1)[0] for ln in texto.splitlines()]
    return " ".join(" ".join(lineas).split())


def _fichas() -> dict:
    return yaml.safe_load(DICCIONARIO.read_text(encoding="utf-8"))["objetos"]


# ===========================================================================
# Estáticos
# ===========================================================================


def test_f155_la_clave_de_las_ofertas_es_la_invitacion() -> None:
    texto = _compacto(_sql("08_comparativos.sql"))
    assert "ALTER TABLE compras.comparativo_ofertas ADD PRIMARY KEY (invitacion_id)" in texto
    assert "ADD PRIMARY KEY (oferta_id)" not in texto


def test_f155_las_lineas_de_la_oferta_se_reparten_por_invitacion() -> None:
    """B (`importe_ofertado_lineas`) es de la invitación, no del documento."""
    texto = _compacto(_sql("08_comparativos.sql"))
    assert "li ON li.invitacion_id = p.ide" in texto
    assert "li ON li.docide = d.ide" not in texto
    assert (
        "ORDER BY lp.ide, COALESCE(q.comide = cl.comide, FALSE) DESC, q.ide" in texto
    )


def test_f155_cada_linea_de_oferta_va_a_una_sola_invitacion() -> None:
    texto = _compacto(_sql("09_comparativos_detalle.sql"))
    assert "SELECT DISTINCT ON (lp.ide) lp.ide AS linea_oferta_id" in texto
    assert (
        "ORDER BY lp.ide, COALESCE(o.comparativo_id = cl.comparativo_id, FALSE) DESC, "
        "o.invitacion_id" in texto
    )


def test_f155_el_objetivo_agrega_por_comparativo_y_oferta() -> None:
    texto = _compacto(_sql("09_comparativos_detalle.sql"))
    assert "GROUP BY l.comparativo_id, l.oferta_id" in texto
    assert (
        "LEFT JOIN con_porcentaje cp ON cp.comparativo_id = ob.comparativo_id "
        "AND cp.oferta_id = ob.oferta_id" in texto
    )


def test_f155_el_adjunto_de_una_oferta_toma_un_solo_comparativo() -> None:
    texto = _compacto(_sql("14_documento_adjuntos.sql"))
    assert "LEFT JOIN raw.comprv p ON p.docide = r.con" not in texto
    assert "SELECT DISTINCT ON (q.docide) q.docide, q.comide FROM raw.comprv q" in texto
    assert "ORDER BY q.docide, q.ide" in texto


def test_f155_diccionario_declara_la_invitacion_como_clave() -> None:
    ficha = _fichas()["comparativo_ofertas"]
    assert ficha["clave_negocio"] == ["invitacion_id"]
    assert ["comparativo_id", "oferta_id"] in ficha["claves_alternativas"]
    assert "F-155" in ficha["grano"]


def test_f155_ninguna_relacion_promete_oferta_id_unica() -> None:
    """Un lado `1` sobre `comparativo_ofertas.oferta_id` duplicaría importes."""
    fallos = []
    for nombre, ficha in _fichas().items():
        for rel in ficha.get("relaciones") or []:
            izq, der = rel["cardinalidad"].split(":")
            if rel["a"] == "compras.comparativo_ofertas.oferta_id" and der == "1":
                fallos.append((nombre, rel["de"]))
            if nombre == "comparativo_ofertas" and rel["de"] == "oferta_id" and izq == "1":
                fallos.append((nombre, rel["a"]))
    assert not fallos, f"relaciones que prometen oferta_id única: {fallos}"


# ===========================================================================
# Sandbox: el caso reproducido contra un Postgres desechable
# ===========================================================================

DSN = os.environ.get("F155_SANDBOX_DSN")

#: Las tablas de `raw` que leen 00, 08, 09 y 14, con los TIPOS de la ingesta
#: (leídos de `information_schema.columns` en Azure el 2026-10-31): ids y
#: fechas `integer`, importes y cantidades `double precision`, textos
#: `character varying`. Solo las columnas que esos ficheros nombran. Va en una
#: BASE NUEVA que el fixture crea y borra: nunca se tira un esquema (el veto de
#: `tests/test_f067_reset.py`).
RAW_DDL = """
CREATE SCHEMA raw; CREATE SCHEMA maestro; CREATE SCHEMA descompuestos;
CREATE TABLE raw.conest (ide integer, tip integer, est integer, cod varchar, res varchar);
CREATE TABLE raw.con (ide integer, tip integer, cod varchar, res varchar, fec integer, est integer);
CREATE TABLE raw.com (ide integer, obride integer, natide integer);
CREATE TABLE raw.comprv (ide integer, comide integer, prvide integer, pos integer, docide integer);
CREATE TABLE raw.dco (ide integer, entide integer, entcod varchar, entres varchar,
                      entcif varchar, totbas double precision);
CREATE TABLE raw.comlin (ide integer, comide integer, numlin integer, pos integer,
                         ctride integer, dncproide integer, dcoproide integer,
                         can double precision, pre double precision);
CREATE TABLE raw.dcopro (ide integer, docide integer, comlinide integer, proide integer,
                         res varchar, unimed varchar, can double precision,
                         pre double precision, tot double precision, dto varchar);
CREATE TABLE raw.dncpro (ide integer, paride integer);
CREATE TABLE raw.confir (ide integer, conide integer, cod varchar, rol varchar, usu varchar,
                         fec integer, hor integer, fir integer, firok integer, estfin integer);
CREATE TABLE raw.auxpronat (ide integer, res varchar);
CREATE TABLE raw.rcg (ide integer, con integer, gra integer, pos integer);
CREATE TABLE raw.gra (ide integer, cod varchar, emp integer, res varchar, usu varchar,
                      fec integer, nom varchar);
CREATE TABLE maestro.v_obra_fichas (obra_id integer, empresa_id integer, clave_obra text);
CREATE TABLE descompuestos.lineas (obra_id integer, partida_id integer, fase_num integer,
                                   es_primera_abc boolean, origen text, orden integer,
                                   precio numeric, dncpro_id integer);
"""

#: El caso del 31-10 en miniatura. Comparativos 100 (el original) y 200 (la
#: copia). Ofertas 11 (real, la ganadora), 12 (la OBJETIVO) y 13 (real, solo
#: en 100). La 11 y la 12 están invitadas en LOS DOS: invitaciones 1-2 en 100
#: y 4-5 en 200. La oferta 11 responde con una línea a cada comparativo (5001
#: a la línea 1000 de 100, 5004 a la 2000 de 200); la 12, solo al 100, y
#: trae además la 5005, cuya línea del concurso (9999) no existe: va a la
#: PRIMERA invitación de su oferta (la 2, del 100), como las 329 de Azure.
DATOS = """
INSERT INTO raw.conest VALUES (1, 12, 6, 'ACE', 'Aceptada definitivamente'),
                              (2, 12, 1, 'ELA', 'En elaboracion'),
                              (3, 46, 1, 'ELA', 'En elaboracion');
INSERT INTO raw.con VALUES (100, 46, '0697.0_0037', 'Original', 20260901, 1),
                           (200, 46, 'COM26/0014', 'Copia', 20261030, 1),
                           (11, 12, 'OF-11', 'Oferta 11', 20260902, 6),
                           (12, 12, 'OF-12', 'Oferta 12', 20260903, 1),
                           (13, 12, 'OF-13', 'Oferta 13', 20260904, 1);
INSERT INTO raw.com VALUES (100, 0, 0), (200, 0, 0);
INSERT INTO raw.comprv VALUES (1, 100, 0, 1, 11), (2, 100, 0, 2, 12), (3, 100, 0, 3, 13),
                              (4, 200, 0, 1, 11), (5, 200, 0, 2, 12);
INSERT INTO raw.dco VALUES (11, 501, 'P501', 'Proveedor real', 'B11111111', 100.25),
                           (12, 0, '', 'OBJETIVO', '', 90.10),
                           (13, 502, 'P502', 'Otro proveedor', 'B22222222', 120.40);
INSERT INTO raw.comlin VALUES (1000, 100, 1, 1, 0, 0, 0, 10, 4),
                              (2000, 200, 1, 1, 0, 0, 0, 10, 3);
INSERT INTO raw.dcopro VALUES
    (5001, 11, 1000, 0, 'L', 'ud', 10, 4, 40.004, NULL),
    (5002, 12, 1000, 0, 'L', 'ud', 10, 4.5, 45.0, '10%'),
    (5003, 13, 1000, 0, 'L', 'ud', 10, 5, 50.0, NULL),
    (5004, 11, 2000, 0, 'L', 'ud', 10, 3, 30.0, NULL),
    (5005, 12, 9999, 0, 'L', 'ud', 1, 2, 2.0, NULL);
INSERT INTO raw.rcg VALUES (9001, 11, 1, 1), (9002, 100, 1, 1);
INSERT INTO raw.gra VALUES (1, 'G1', 1, 'adjunto', 'login', 20260905, 'oferta.pdf');
"""

# `compras.contrato_lineas` la construye 01 (fuera del alcance): basta su forma.
STUB_COMPRAS = (
    "CREATE TABLE compras.contrato_lineas (contrato_id integer, importe numeric);"
)


@pytest.fixture(scope="module")
def sandbox():
    if not DSN:
        pytest.skip("sin F155_SANDBOX_DSN: la sandbox SQL de F-155 no se ejecuta")
    import uuid

    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f155_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{base}"')
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as conexion:
            yield from _construir(conexion)
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _construir(conexion):
    """`raw` con el caso, `00_setup.sql` y 08, 09 y 14 reales, cada uno en su transacción."""
    conexion.execute(RAW_DDL)
    conexion.execute(DATOS)
    conexion.execute(_sql("00_setup.sql"))
    conexion.execute(STUB_COMPRAS)
    for fichero in ("08_comparativos.sql", "09_comparativos_detalle.sql",
                    "14_documento_adjuntos.sql"):
        with conexion.transaction():
            conexion.execute(_sql(fichero))
    yield conexion


def _filas(conexion, sql: str) -> list[tuple]:
    return conexion.execute(sql).fetchall()


def test_f155_sandbox_una_fila_por_invitacion(sandbox) -> None:
    filas = _filas(sandbox, """
        SELECT invitacion_id, comparativo_id, oferta_id, importe_ofertado_documento,
               importe_ofertado_lineas, n_lineas
        FROM compras.comparativo_ofertas ORDER BY invitacion_id""")
    from decimal import Decimal as D
    assert filas == [
        (1, 100, 11, D("100.25"), D("40.00"), 1),
        (2, 100, 12, D("90.10"), D("47.00"), 2),
        (3, 100, 13, D("120.40"), D("50.00"), 1),
        (4, 200, 11, D("100.25"), D("30.00"), 1),
        (5, 200, 12, D("90.10"), None, 0),
    ]


def test_f155_sandbox_comparativos_sin_importes_duplicados(sandbox) -> None:
    from decimal import Decimal as D
    filas = _filas(sandbox, """
        SELECT comparativo_id, n_ofertas, n_ofertas_ganadoras, oferta_ganadora_id,
               importe_ofertado_documento_ganadora, importe_ofertado_lineas_ganadora
        FROM compras.comparativos ORDER BY comparativo_id""")
    assert filas == [
        (100, 3, 1, 11, D("100.25"), D("40.00")),
        (200, 2, 1, 11, D("100.25"), D("30.00")),
    ]


def test_f155_sandbox_cada_linea_de_oferta_una_vez_y_en_su_comparativo(sandbox) -> None:
    filas = _filas(sandbox, """
        SELECT linea_oferta_id, oferta_id, comparativo_id
        FROM compras.comparativo_oferta_lineas ORDER BY linea_oferta_id""")
    assert filas == [
        (5001, 11, 100), (5002, 12, 100), (5003, 13, 100), (5004, 11, 200), (5005, 12, 100),
    ]


def test_f155_sandbox_el_objetivo_de_cada_comparativo(sandbox) -> None:
    from decimal import Decimal as D
    filas = _filas(sandbox, """
        SELECT comparativo_id, oferta_objetivo_id, importe_objetivo, porcentaje_objetivo
        FROM compras.comparativo_objetivo ORDER BY comparativo_id""")
    # En el 200 la OBJETIVO no tiene líneas: su porcentaje no es el del 100.
    assert filas == [(100, 12, D("90.10"), D("10")), (200, 12, D("90.10"), None)]


def test_f155_sandbox_un_adjunto_de_oferta_compartida_una_sola_fila(sandbox) -> None:
    filas = _filas(sandbox, """
        SELECT adjunto_id, familia, comparativo_id
        FROM compras.documento_adjuntos ORDER BY adjunto_id""")
    # La oferta compartida toma el comparativo de su PRIMERA invitación.
    assert filas == [(9001, "OFERTA", 100), (9002, "COMPARATIVO", 100)]


def test_f155_el_diccionario_sube_de_version() -> None:
    texto = (RAIZ / "config" / "diccionario" / "00_global.yaml").read_text(encoding="utf-8")
    assert int(yaml.safe_load(texto)["version"]) >= 68
    assert "# version 68 (F-155, 2026-10-31, hotfix)" in texto
