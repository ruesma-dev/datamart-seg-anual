# tests/test_f067_sql.py
"""
F-067 · El SQL de la foto diaria, del contrato y del código 2, sobre su TEXTO.

`sql/compras/*.sql` y `sql/descompuestos/06_views.sql` construyen objetos en un
Postgres **compartido con producción**, así que aquí no se ejecutan: se leen.
Mismo criterio que `tests/test_f084_sql.py` y `tests/test_f038_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Las dos tablas de la foto NO se reconstruyen** (R8): ni `DROP`, ni
   `TRUNCATE`, ni `DELETE` en `11_historial_estados.sql`. Es historia que no
   existe en Sigrid; lo que se borre no vuelve.
2. **Los literales del SQL son los del dominio** (`domain/historial_estados.py`):
   los tipos, el 0.98, los motivos y la época de Delphi. El oráculo se prueba
   en `tests/test_f067_dominio.py`; aquí, que el SQL dice lo mismo.
3. **Las columnas nuevas van AL FINAL** de tablas que ya consumen Power BI y el
   MCP, y las de siempre no se mueven.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from etl_sigrid.domain.historial_estados import EPOCA_DELPHI

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
RUTA_SETUP = DIRECTORIO_SQL / "compras" / "00_setup.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _funcion(texto: str, nombre: str) -> str:
    """La definición compactada de una función, de su `CREATE` a su `$$;`."""
    ejecutable = _sin_comentarios(texto)
    marca = f"CREATE OR REPLACE FUNCTION {nombre}("
    assert marca in ejecutable, f"`{nombre}` no está definida"
    inicio = ejecutable.index(marca)
    fin = ejecutable.index("$$;", ejecutable.index("AS $$", inicio))
    return re.sub(r"\s+", " ", ejecutable[inicio:fin])


# ===========================================================================
# R14 · `compras.fn_sigrid_tiempo`: la fecha de Delphi de `con.tiemod`
# ===========================================================================


def test_f067_r14_tiempo_la_funcion_esta_definida_una_vez() -> None:
    ejecutable = _sin_comentarios(_texto(RUTA_SETUP))
    assert ejecutable.count("CREATE OR REPLACE FUNCTION compras.fn_sigrid_tiempo(") == 1


def test_f067_r14_tiempo_firma_double_a_timestamp_e_inmutable() -> None:
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    assert "fn_sigrid_tiempo(v DOUBLE PRECISION) RETURNS TIMESTAMP" in cuerpo
    assert "IMMUTABLE" in cuerpo


def test_f067_r14_tiempo_la_epoca_del_sql_es_la_del_dominio() -> None:
    """La de Delphi (1899-12-30), no la de SQL Server (1900-01-01): esa da dos
    días de más, medido con la fila modificada el 2026-10-05."""
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    epocas = re.findall(r"TIMESTAMP '(\d{4}-\d{2}-\d{2})'", cuerpo)
    assert epocas == [EPOCA_DELPHI.isoformat()]


def test_f067_r14_tiempo_cero_y_negativo_son_nulo_y_la_hora_es_decimal() -> None:
    cuerpo = _funcion(_texto(RUTA_SETUP), "compras.fn_sigrid_tiempo")
    assert "CASE WHEN v > 0 THEN" in cuerpo, "el 0 de Sigrid es NULL, no 1899-12-30"
    assert "ELSE" not in cuerpo, "fuera del CASE tiene que salir NULL"
    assert "+ v * INTERVAL '1 day' END" in cuerpo, (
        "la parte decimal es la hora: multiplicar por un día la conserva"
    )
