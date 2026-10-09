# tests/test_f067_reset.py
"""
F-067 · `reset-compras` CONSERVA la foto diaria (decisión del 2026-10-06).

`compras.historial_estados` y `compras.historial_estados_fotos` son historia que
no existe en Sigrid: si se borran, no vuelven. `reset-compras` borraba el
esquema entero con `CASCADE` y se las habría llevado. Decisión del humano (delegada
en el líder, opción a): el comando borra todo lo demás de `compras` —vistas,
tablas y funciones— y NUNCA esas dos tablas ni sus índices.

Ningún test abre red ni BBDD: el SQL se lee como texto y el comando se ejecuta
contra un doble de `main._get_pg`.
"""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

import main
from etl_sigrid.domain.historial_estados import TABLAS_PERSISTENTES
from etl_sigrid.infrastructure.postgres.compras_reset_sql import SQL_RESET_COMPRAS

RAIZ = Path(__file__).resolve().parents[1]

#: El borrado del esquema entero, escrito por partes para que este fichero
#: no se cace a sí mismo.
VETO = re.compile(r"DROP\s+SCHEMA\s+(IF\s+EXISTS\s+)?" + "comp" + r"ras\b", re.IGNORECASE)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


# `las_persistentes_son_las_que_crea_la_foto` se retira con
# `11_historial_estados.sql` (F-132, Fase B): ya no hay foto que las cree.


def test_f067_reset_no_borra_el_esquema() -> None:
    assert not VETO.search(SQL_RESET_COMPRAS)
    assert "DROP SCHEMA" not in SQL_RESET_COMPRAS.upper()


def test_f067_reset_las_tablas_se_borran_todas_menos_las_persistentes() -> None:
    sql = _compacto(SQL_RESET_COMPRAS)
    lista = ", ".join(f"'{t}'" for t in TABLAS_PERSISTENTES)
    assert (
        "WHERE n.nspname = 'compras' AND c.relkind IN ('r', 'p') "
        f"AND c.relname NOT IN ({lista})" in sql
    ), sql
    assert "EXECUTE format('DROP TABLE IF EXISTS compras.%I CASCADE', r.relname);" in sql


def test_f067_reset_vistas_y_funciones_se_borran_todas() -> None:
    sql = _compacto(SQL_RESET_COMPRAS)
    assert "WHERE n.nspname = 'compras' AND c.relkind IN ('v', 'm')" in sql
    assert (
        "EXECUTE format('DROP %s IF EXISTS compras.%I CASCADE', CASE r.relkind "
        "WHEN 'v' THEN 'VIEW' ELSE 'MATERIALIZED VIEW' END, r.relname);" in sql
    )
    assert "WHERE n.nspname = 'compras' LOOP" in sql
    assert "EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.firma);" in sql


def test_f067_reset_borra_en_orden_vistas_tablas_funciones() -> None:
    sql = SQL_RESET_COMPRAS
    orden = [sql.index("'VIEW'"), sql.index("DROP TABLE"), sql.index("DROP FUNCTION")]
    assert orden == sorted(orden)


def test_f067_reset_ningun_indice_ni_tabla_persistente_se_nombra_para_borrar() -> None:
    """Los índices de las dos tablas mueren solo con su tabla: no hay ningún
    `DROP INDEX` y nada borra por nombre una persistente."""
    assert "DROP INDEX" not in SQL_RESET_COMPRAS.upper()
    for tabla in TABLAS_PERSISTENTES:
        assert f"compras.{tabla}" not in SQL_RESET_COMPRAS


class _Cursor:
    def __init__(self, ejecutadas: list[str]) -> None:
        self._ejecutadas = ejecutadas

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str) -> None:
        self._ejecutadas.append(sql)


class _Conexion:
    def __init__(self) -> None:
        self.ejecutadas: list[str] = []
        self.commits = 0

    def __enter__(self) -> _Conexion:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return _Cursor(self.ejecutadas)

    def commit(self) -> None:
        self.commits += 1


class _PgFalso:
    def __init__(self) -> None:
        self.conexion = _Conexion()

    def connection(self) -> _Conexion:
        return self.conexion


def test_f067_reset_el_comando_ejecuta_el_reset_que_conserva_la_foto(monkeypatch) -> None:
    pg = _PgFalso()
    monkeypatch.setattr(main, "_get_pg", lambda: pg)

    resultado = CliRunner().invoke(main.cli, ["reset-compras"])

    assert resultado.exit_code == 0, resultado.output
    assert pg.conexion.ejecutadas == [SQL_RESET_COMPRAS]
    assert pg.conexion.commits == 1
    assert "historial_estados" in resultado.output


def test_f067_reset_veto_nadie_tira_el_esquema_compras() -> None:
    """Ni `main.py`, ni un script, ni un parche viejo: tirar el esquema entero
    se llevaría la historia. Se barre el código del repositorio."""
    excluidos = {".git", ".claude", ".venv", "venv", "node_modules", "__pycache__"}
    culpables = []
    for patron in ("*.py", "*.sql", "*.ps1", "*.sh"):
        for ruta in RAIZ.rglob(patron):
            if excluidos & set(ruta.relative_to(RAIZ).parts):
                continue
            if VETO.search(ruta.read_text(encoding="utf-8", errors="replace")):
                culpables.append(ruta.relative_to(RAIZ).as_posix())
    assert culpables == []
