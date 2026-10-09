# tests/test_f067_reset.py
"""
F-067 · F-132 · `reset-compras` vacía el esquema `compras` SIN tirarlo.

HISTORIA. Hasta el 2026-10-06 el comando hacía `DROP SCHEMA ... CASCADE`. F-067
lo cambió (decisión del humano, opción a) para conservar las dos tablas de la
foto diaria de estados, que no se reconstruían: borraba vistas, tablas y
funciones MENOS esas dos. F-132 (Fase B, rama BORRAR, decisión del humano del
2026-10-09) retiró la foto, y con ella la lista de conservadas (R26): hoy borra
TODAS las vistas, tablas y funciones de `compras`, y sigue sin tirar el esquema
(R26: «sin lista de persistentes y sin `DROP SCHEMA`»).

Ningún test abre red ni BBDD: el SQL se lee como texto y el comando se ejecuta
contra un doble de `main._get_pg`.
"""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

import main
from etl_sigrid.infrastructure.postgres import compras_reset_sql
from etl_sigrid.infrastructure.postgres.compras_reset_sql import SQL_RESET_COMPRAS

RAIZ = Path(__file__).resolve().parents[1]

#: El borrado del esquema entero, escrito por partes para que este fichero
#: no se cace a sí mismo.
VETO = re.compile(r"DROP\s+SCHEMA\s+(IF\s+EXISTS\s+)?" + "comp" + r"ras\b", re.IGNORECASE)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def test_f067_reset_no_borra_el_esquema() -> None:
    assert not VETO.search(SQL_RESET_COMPRAS)
    assert "DROP SCHEMA" not in SQL_RESET_COMPRAS.upper()


def test_f132_r26_reset_borra_todas_las_tablas_sin_lista_de_conservadas() -> None:
    sql = _compacto(SQL_RESET_COMPRAS)
    assert (
        "WHERE n.nspname = 'compras' AND c.relkind IN ('r', 'p') LOOP "
        "EXECUTE format('DROP TABLE IF EXISTS compras.%I CASCADE', r.relname);" in sql
    ), sql
    assert "NOT IN" not in sql.upper(), "sin la foto no queda nada que conservar"
    assert "historial_estados" not in SQL_RESET_COMPRAS


def test_f132_r26_reset_ya_no_depende_del_dominio_de_la_foto() -> None:
    assert not hasattr(compras_reset_sql, "TABLAS_PERSISTENTES")
    texto = Path(compras_reset_sql.__file__).read_text(encoding="utf-8")
    assert "domain.historial_estados" not in texto


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


def test_f067_reset_ningun_indice_se_borra_por_nombre() -> None:
    """Los índices mueren con su tabla: no hay ningún `DROP INDEX`."""
    assert "DROP INDEX" not in SQL_RESET_COMPRAS.upper()


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


def test_f132_r26_el_comando_vacia_compras_entero(monkeypatch) -> None:
    pg = _PgFalso()
    monkeypatch.setattr(main, "_get_pg", lambda: pg)

    resultado = CliRunner().invoke(main.cli, ["reset-compras"])

    assert resultado.exit_code == 0, resultado.output
    assert pg.conexion.ejecutadas == [SQL_RESET_COMPRAS]
    assert pg.conexion.commits == 1
    assert "historial_estados" not in resultado.output
    assert "SALVO" not in resultado.output
    assert "build-compras" in resultado.output


def test_f067_reset_veto_nadie_tira_el_esquema_compras() -> None:
    """Ni `main.py`, ni un script, ni un parche viejo tira el esquema entero
    (R26 de F-132 lo mantiene). Se barre el código del repositorio."""
    excluidos = {".git", ".claude", ".venv", "venv", "node_modules", "__pycache__"}
    culpables = []
    for patron in ("*.py", "*.sql", "*.ps1", "*.sh"):
        for ruta in RAIZ.rglob(patron):
            if excluidos & set(ruta.relative_to(RAIZ).parts):
                continue
            if VETO.search(ruta.read_text(encoding="utf-8", errors="replace")):
                culpables.append(ruta.relative_to(RAIZ).as_posix())
    assert culpables == []
