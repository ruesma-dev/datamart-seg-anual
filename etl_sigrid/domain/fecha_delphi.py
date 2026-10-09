# etl_sigrid/domain/fecha_delphi.py
"""
La FECHA SERIE de Sigrid como fecha y hora: la época de Delphi (F-067).

Sigrid guarda algunas fechas como un número —días desde el 1899-12-30, con la
hora en la parte decimal—; la que se publica es `con.tiemod`, la última
modificación del documento (`compras.contratos.fecha_ultima_modificacion`).
46300,537627 es el 2026-10-05 a las 12:54:10. SQL Server convierte el mismo
número con la época 1900-01-01 y da DOS DÍAS MÁS (medido el 2026-10-06): la
buena es la de Delphi.

LA CONVERSIÓN LA EJECUTA SQL (`compras.fn_sigrid_tiempo`, en
`sql/compras/00_setup.sql`), y aquí está escrita **una sola vez** como oráculo:
`tests/test_f067_sql.py` comprueba que la época del SQL es `EPOCA_DELPHI`.

POR QUÉ ESTÁ SOLA EN SU MÓDULO. Nació en `domain/historial_estados.py`, junto a
la foto diaria de estados de F-067. F-132 (Fase B, decisión del humano del
2026-10-09) retiró la foto y borró aquel módulo; la época se queda aquí porque
`fn_sigrid_tiempo` la sigue usando.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Final

#: La época de las fechas serie de Sigrid (`con.tiemod`): la de Delphi. SQL
#: Server convierte el mismo número con 1900-01-01 y da dos días más.
EPOCA_DELPHI: Final[date] = date(1899, 12, 30)


def fecha_delphi(valor: float | None) -> datetime | None:
    """Una fecha serie de Sigrid (días desde 1899-12-30, hora en la parte
    decimal) como `datetime`. None para None, 0 o negativo, igual que el
    `CASE WHEN v > 0` de `compras.fn_sigrid_tiempo`."""
    if valor is None or valor <= 0:
        return None
    return datetime.combine(EPOCA_DELPHI, time()) + timedelta(days=valor)
