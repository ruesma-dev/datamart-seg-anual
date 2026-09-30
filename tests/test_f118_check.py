# tests/test_f118_check.py
"""
F-118 · Las comprobaciones de solo lectura contra la base, sin base.

- `check-cierres` (R37): el telescopio deja de apartar series «con hueco de
  origen» y compara la suma de `importe_mes` de TODA serie con el acumulado de
  la partida en el último cierre publicado del ámbito de la obra. Y, como la
  regla de F-042 se aplica ahora sobre el mes del texto (R8), los candidatos
  salen con ese mes y lo publicado sin las filas de relleno.
- `check-mes-fase` (R25, T23): el SQL del mes contra el oráculo, fase a fase.

El cliente es un doble que sirve filas enlatadas y estalla si alguien intenta
escribir. Ni red ni BBDD.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.infrastructure.postgres.cierres_sql import (
    sql_cierres_candidatos,
    sql_cierres_publicados,
    sql_telescopio,
    sql_telescopio_detalle,
)

# ---------------------------------------------------------------------------
# R37 · el telescopio sin apartados
# ---------------------------------------------------------------------------


def test_f118_r37_telescopio_no_aparta_ninguna_serie() -> None:
    """Apartar las series «con hueco» es lo que escondió el fallo 1: la 0709 y
    las 32 obras de `progress/spec_F-118.md` §2 caían ahí."""
    texto = sql_telescopio()
    assert "con_hueco" not in texto
    assert "descarte" not in texto
    assert "orden_fase" not in texto
    assert "WHERE NOT" not in texto


def test_f118_r37_telescopio_compara_con_el_ultimo_cierre_del_ambito_de_la_obra() -> None:
    """No con la última fila de la partida: una partida que salió de la obra
    tiene que sumar 0, y comparada con su última fila sumaría lo que tenía."""
    texto = sql_telescopio()
    assert re.search(
        r"MAX\(anio_mes\) AS ultimo_mes\s+FROM serie\s+GROUP BY obra_id, ambito_id", texto
    ), texto
    assert (
        "COALESCE(SUM(s.importe_origen) FILTER (WHERE s.anio_mes = u.ultimo_mes), 0)"
        in texto
    )
    assert "JOIN ultimo u USING (obra_id, ambito_id)" in texto


def test_f118_r37_telescopio_devuelve_comprobadas_y_rotas() -> None:
    texto = sql_telescopio()
    final = texto[texto.index("SELECT count(*)") :]
    assert "AS series_comprobadas" in final
    assert "AS series_rotas" in final
    assert "series_con_hueco" not in texto


def test_f118_r37_telescopio_detalle_lista_las_rotas_sin_filtro_de_hueco() -> None:
    texto = sql_telescopio_detalle(limite=5)
    assert "WHERE suma_movimientos <> ultimo_acumulado" in texto
    assert "con_hueco" not in texto
    assert texto.rstrip().endswith("LIMIT 5")


class PgFalso:
    """Candidatos, publicados y telescopio enlatados; estalla si escribe."""

    def __init__(self, telescopio: tuple[int, int]) -> None:
        self._telescopio = telescopio
        self.consultas: list[str] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        if "plan_mensual" not in sql_text:
            return [(1, 3, date(2026, 8, 1), 12, Decimal("10.00"))]
        if "importe_mes" in sql_text:
            return [self._telescopio]
        return [(1, 3, date(2026, 8, 1), 12, Decimal("10.00"))]

    def __getattr__(self, nombre: str):
        raise AssertionError(f"`check-cierres` es de solo lectura (pg.{nombre})")


def _check(monkeypatch: pytest.MonkeyPatch, pg: PgFalso):
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner().invoke(main.cli, ["check-cierres"])


def test_f118_r37_telescopio_el_comando_sale_0_con_cero_rotas(monkeypatch) -> None:
    resultado = _check(monkeypatch, PgFalso((1200, 0)))
    assert resultado.exit_code == 0, resultado.output
    assert "1200 serie(s) comprobada(s), 0 sin cuadrar" in resultado.output
    assert "apartada" not in resultado.output


def test_f118_r37_telescopio_el_comando_falla_con_una_rota(monkeypatch) -> None:
    resultado = _check(monkeypatch, PgFalso((1200, 1)))
    assert resultado.exit_code != 0
    assert "1 sin cuadrar" in resultado.output
    assert "suma_movimientos <> ultimo_acumulado" in resultado.output


# ---------------------------------------------------------------------------
# R8 · la regla de F-042 sobre el mes del texto, en check-cierres
# ---------------------------------------------------------------------------


def test_f118_r8_check_cierres_candidatos_con_el_mes_del_texto() -> None:
    """El contraste independiente tiene que agrupar por el MISMO mes que el
    build, o cada fase de rango saldría como discrepancia."""
    texto = sql_cierres_candidatos()
    assert re.search(
        r"stg\.fn_mes_de_fase\(\s*f\.fecha_inicio,\s*f\.nombre_mes,\s*f\.fecha_fin", texto
    ), texto
    assert "make_date(f.anio, f.mes, 1) AS anio_mes" not in texto
    assert "plan_mensual" not in texto


def test_f118_r8_check_cierres_publicados_sin_relleno() -> None:
    """Un mes de relleno no es un cierre: lleva la versión de la fase que lo
    genera, y contado como cierre saldría como «publicado sin candidato»."""
    assert "COALESCE(es_relleno, FALSE) = FALSE" in sql_cierres_publicados()
