# tests/test_f132_contraste.py
"""
F-132 · Lo que QUEDA del contraste foto diaria <-> `rac`.

El comando `python main.py contraste-estados` (R12-R17) y su SQL vivieron en la
Fase A: compararon la foto diaria de F-067 con `rac` durante 2 noches (492
cambios, 0 discrepancias, `progress/contraste_F-132.md`) y, con eso delante, el
humano decidió BORRAR la foto (Fase B, D7, 2026-10-09). El contraste se fue con
ella: sin foto no hay nada que contrastar. `tests/test_f132_retirada.py` fija
que el comando, su SQL y su dominio ya no están.

Queda una pieza que el contraste trajo y que es de uso general:
`PostgresClient.filas_solo_lectura` acepta parámetros (`params`) sin dejar de
ir en una transacción READ ONLY. Sus dos tests siguen aquí.

Ningún test toca red ni BBDD: el cliente es un doble.
"""

from __future__ import annotations

#: Una consulta parametrizada cualquiera, de la forma que la estrenó (`= ANY`).
SQL_CON_PARAMETRO = "SELECT documento_id FROM compras.documento_procesos WHERE documento_id = ANY(%s)"


class _Cursor:
    def __init__(self) -> None:
        self.ejecutadas: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *args):
        self.ejecutadas.append((sql, *args))

    def fetchall(self):
        return [(1,)]


class _Conexion:
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        raise AssertionError("no debía fallar")


class _Cliente:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    def connection(self):
        return self._conexion


def test_f132_r17_los_parametros_viajan_tras_el_read_only() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cursor = _Cursor()
    filas = PostgresClient.filas_solo_lectura(
        _Cliente(_Conexion(cursor)), SQL_CON_PARAMETRO, 30, ([1, 2],)
    )

    assert filas == [(1,)]
    assert cursor.ejecutadas[0] == ("SET LOCAL statement_timeout = '30s'",)
    assert cursor.ejecutadas[1] == ("SET LOCAL transaction_read_only = on",)
    assert cursor.ejecutadas[2] == (SQL_CON_PARAMETRO, ([1, 2],))


def test_f132_r17_sin_parametros_la_llamada_es_la_de_siempre() -> None:
    """Sin `params` el `execute` va SIN segundo argumento: un `%` literal de los
    SQL de diagnóstico de siempre no se interpreta como marcador."""
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    cursor = _Cursor()
    PostgresClient.filas_solo_lectura(_Cliente(_Conexion(cursor)), "SELECT '50%'", 30)

    assert cursor.ejecutadas[2] == ("SELECT '50%'",)
