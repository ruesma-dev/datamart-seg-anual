# tests/test_f164_sandbox.py
"""
F-164 · El `06_adjuntos.sql` REAL ejecutado contra un PostgreSQL desechable (R10):
cada enlace sale con la familia que da `familia_publicada` del dominio (oráculo)
y con la `familia_documento` de `familia_adjunto` (F-156).

Solo con `F164_SANDBOX_DSN` (un Postgres local de usar y tirar); sin él, `skip`.
El fixture crea una BASE NUEVA (UTF-8) y la borra al terminar, como
`tests/test_f161_sandbox.py`. Carga un `raw` mínimo con los tipos de la ingesta
(ids, fechas y `gratipide` `integer`, texto `character varying`), ejecuta el
`00_setup.sql` y el `06_adjuntos.sql` reales y compara fila a fila. Así se
comprueba lo que el texto no puede: que los dos patrones valen igual en el ARE
de PostgreSQL que en `re` de Python, incluidos los acentos que pasa `upper()`,
y que ningún `NULL` abre un fichero.

Fixture SINTÉTICA: los 7 de `progress/spec_F-164.md` §3 con números inventados,
los controles abiertos, los restringidos sin texto y los bordes de R2-R7.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from etl_sigrid.domain import postventa as pv

DSN = os.environ.get("F164_SANDBOX_DSN")
DIR_PV = (Path(__file__).resolve().parents[1]
          / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "postventa")

INC, UNI, TAR = 708, 707, 47

RAW_DDL = """
CREATE SCHEMA raw;
CREATE TABLE raw.con (ide integer, tip integer, cod varchar, est integer);
CREATE TABLE raw.conest (ide integer, tip integer, est integer, cod varchar, res varchar);
CREATE TABLE raw.rcg (ide integer, con integer, gra integer, pos integer);
CREATE TABLE raw.gra (ide integer, cod varchar, emp integer, nom varchar, gratipide integer,
                      res varchar, fec integer, usu varchar);
CREATE TABLE raw.auxgra (ide integer, cod varchar, res varchar);
CREATE TABLE raw.rcp (ide integer, upvide integer);
CREATE TABLE raw.tar (ide integer, rcpide integer);
"""

#: (tipo, gratipide, nombre, descripción). `gratipide` 0 es «sin clase» en Sigrid.
CASOS: tuple[tuple[int, int | None, str | None, str | None], ...] = (
    # Los 7 (R8)
    (INC, 0, "VIV 1 - RS24.11-0123.pdf", "PARTE FIRMADO"),
    (INC, 0, "B1C - RS24.11-0456.pdf", "PARTE FIRMADO"),
    (INC, 34, "RS25.07 - 0321 FIRMADO.pdf", "PARTE FIRMADO"),
    (INC, 0, "0601 - RS26.10 - 0789 PARTE FIRMADO.pdf", None),
    (UNI, 35, "VIV 2 - RS24.11-0124.pdf", "PARTE FIRMADO"),
    (UNI, 35, "B2D - RS24.11-0457.pdf", "PARTE FIRMADO"),
    (UNI, 35, "VIV 3 - RS24.12-0125.pdf", "PARTE FIRMADO"),
    # Controles abiertos (R3)
    (INC, 34, "20250312_101010.jpg", None),
    (INC, 34, "20250312_101011.jpg", "PARTE TRASERA DEL ARMARIO"),
    (INC, 34, "foto_salon.jpg", "CONFIRMADO POR EL JEFE DE OBRA"),
    (INC, 34, "IMG_0001.jpg", "RS24.11-0123 salon"),
    (INC, 34, "  foto.jpg  ", "   "),
    (UNI, 39, "0601_02_03_04_PRIMERA_HAB1.pdf", None),
    (TAR, 37, "1_2_3_4_TAR_PRV_RCP.pdf", None),
    (TAR, 37, "1_2_3_4_TAR_PARTE_DE_TRABAJOS.pdf", "Informe"),
    # Restringidos sin texto (R1, R4, R5, R6)
    (INC, 0, "UNTITLED_1_2.pdf", None),
    (INC, None, "foto.jpg", None),
    (INC, 38, "foto.jpg", None),
    (TAR, 35, "informe.pdf", None),
    (UNI, 0, "ficha.pdf", None),
    (UNI, None, None, None),
    (INC, 0, "imagen.jpg", ""),
    (INC, 99, "video.mp4", None),
    (INC, 35, "20250312_101012.jpg", None),
    # Señales dentro de la lista abierta (R2), acentos y minúsculas (upper)
    (INC, 34, "hoja.pdf", "firma del cliente"),
    (INC, 34, "parte firmado por la dueña.pdf", None),
    (INC, 34, "rs24.11.012.jpg", None),
    (INC, 34, "VIV 1 - RS 24.11 / 0123.pdf", None),
    (INC, 34, "x_FIRMA_y.pdf", None),
    (UNI, 39, "ficha FIRMADA.pdf", None),
    (TAR, 37, "informe firmas.pdf", None),
    (INC, 34, "confirmación.pdf", None),
    (INC, 34, "áfirma.pdf", None),
    (INC, 34, "firmañ.pdf", None),
    (INC, 34, "firmamento.pdf", None),
    (INC, 34, "CON", None),
    (INC, 34, "CON", "FIRMADO"),
    (INC, 34, None, "FIRMAS"),
    (INC, 34, "RS24.11-12.pdf", None),
    (INC, 34, "RS24.110123.pdf", None),
)


@pytest.fixture(scope="module")
def conexion():
    if not DSN:
        pytest.skip("sin F164_SANDBOX_DSN: la sandbox SQL de F-164 no se ejecuta")
    import psycopg
    from psycopg.conninfo import make_conninfo

    base = f"f164_sandbox_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE \"{base}\" TEMPLATE template0 ENCODING 'UTF8'")
    try:
        with psycopg.connect(make_conninfo(DSN, dbname=base), autocommit=True) as c:
            c.execute(RAW_DDL)
            _cargar(c)
            c.execute((DIR_PV / "00_setup.sql").read_text(encoding="utf-8"))
            c.execute((DIR_PV / "06_adjuntos.sql").read_text(encoding="utf-8"))
            yield c
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)')


def _cargar(c) -> None:
    for ide, cod, res in ((34, "PV001", "Fotos de incidencias"), (35, "PV002", "Fotos Reparaciones"),
                          (37, "PV004", "Informes"), (38, "PV005", "Otra"),
                          (39, "PV006", "Ficha de inmueble")):
        c.execute("INSERT INTO raw.auxgra VALUES (%s, %s, %s)", (ide, cod, res))
    for n, (tip, clase, nombre, descripcion) in enumerate(CASOS, start=1):
        documento = 1000 + n
        c.execute("INSERT INTO raw.con VALUES (%s, %s, %s, 1)", (documento, tip, f"D{n}"))
        c.execute("INSERT INTO raw.gra VALUES (%s, %s, 1, %s, %s, %s, 20250312, 'u')",
                  (n, f"G{n}", nombre, clase, descripcion))
        c.execute("INSERT INTO raw.rcg VALUES (%s, %s, %s, 1)", (n, documento, n))
        if tip == INC:
            c.execute("INSERT INTO raw.rcp VALUES (%s, 7)", (documento,))
        if tip == TAR:
            c.execute("INSERT INTO raw.tar VALUES (%s, NULL)", (documento,))


def _filas(c) -> dict[int, tuple[str, str]]:
    cur = c.execute(
        "SELECT adjunto_id, familia, familia_documento FROM postventa.documento_adjuntos")
    return {int(a): (f, fd) for a, f, fd in cur.fetchall()}


def test_f164_r10_una_fila_por_enlace(conexion) -> None:
    assert set(_filas(conexion)) == set(range(1, len(CASOS) + 1))


def test_f164_r10_cada_familia_es_la_del_oraculo(conexion) -> None:
    filas = _filas(conexion)
    distintas = []
    for n, (tip, clase, nombre, descripcion) in enumerate(CASOS, start=1):
        esperado = pv.familia_publicada(tip, clase, nombre, descripcion)
        if filas[n][0] != esperado:
            distintas.append((n, tip, clase, nombre, descripcion, filas[n][0], esperado))
    assert not distintas, distintas


def test_f164_r10_familia_documento_es_la_de_f156(conexion) -> None:
    filas = _filas(conexion)
    for n, (tip, clase, _nombre, _descripcion) in enumerate(CASOS, start=1):
        assert filas[n][1] == pv.familia_adjunto(tip, clase), (n, tip, clase)


def test_f164_r10_los_siete_en_reparacion(conexion) -> None:
    filas = _filas(conexion)
    assert all(filas[n][0] == "REPARACION" for n in range(1, 8))


def test_f164_r10_hay_abiertos_y_cerrados(conexion) -> None:
    """La fixture ejercita las dos ramas del CASE: no es un todo-REPARACION."""
    familias = {f for f, _fd in _filas(conexion).values()}
    assert familias == {"INCIDENCIA", "UNIDAD", "TAREA", "REPARACION"}


def test_f164_r10_upper_pasa_los_acentos(conexion) -> None:
    """El oráculo da por hecho que `upper()` de PostgreSQL sube á, ñ, ó como Python."""
    fila = conexion.execute("SELECT upper('áéíóúñü confirmación')").fetchone()
    assert fila[0] == "áéíóúñü confirmación".upper()
