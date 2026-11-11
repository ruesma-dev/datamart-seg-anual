# etl_sigrid/domain/ficha_obra.py
"""
La ficha por defecto de un código de obra: el oráculo puro (F-162).

En Sigrid la obra es POR EMPRESA: el mismo código existe una vez por empresa
(Ruesma, Porsan, cada UTE) y es la misma obra vista desde cada una, sin
consolidar. Desde F-162 `stg.obras` lleva TODAS las fichas y marca en
`es_por_defecto` la que se lee cuando la pregunta no dice empresa.

El criterio es del humano (2026-11-11): «en caso de duda, Construcciones Ruesma
por delante, salvo que se diga lo contrario; los datos deciden antes que la
duda». En orden, y solo en este orden:

1. La ficha de la empresa 1 (Construcciones Ruesma), si el código la tiene.
2. Más líneas de presupuesto (`raw.obrparpre`, contadas por ficha).
3. `tiemod` más reciente; sin `tiemod`, pierde (`DESC NULLS LAST`).
4. `ide` mayor, solo como desempate final.

«Si solo hay una ficha, esa» sale sola: con una ficha no hay nada que ordenar.
La marca de vigente de `raw.conext` (cod 15) NO interviene (D2, design §3.2).

`sql/stg/03_obras.sql` aplica el mismo orden en su `ROW_NUMBER()`; los tests
fijan que los dos van criterio a criterio y la sandbox, que dan lo mismo.

Sin dependencias: dominio puro.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

#: `con.emp` de Construcciones Ruesma.
EMPRESA_RUESMA = 1

#: Los criterios, en el orden en que deciden. El `ORDER BY` del SQL los sigue uno a uno.
CRITERIOS = ("empresa_ruesma", "num_lineas", "tiemod", "obra_id")


@dataclass(frozen=True, slots=True)
class FichaObra:
    """Una ficha de obra (`raw.obr JOIN raw.con`) con lo que decide el criterio."""

    obra_id: int
    codigo_obra: str
    empresa_id: int | None
    num_lineas: int = 0
    tiemod: float | None = None


def clave_por_defecto(ficha: FichaObra) -> tuple:
    """Clave de orden de `ficha` dentro de su código: la MENOR es la por defecto.

    Un `empresa_id` nulo no es Ruesma, igual que `CASE WHEN empresa_id = 1` en SQL.
    """
    return (
        0 if ficha.empresa_id == EMPRESA_RUESMA else 1,
        -ficha.num_lineas,
        ficha.tiemod is None,
        -(ficha.tiemod or 0.0),
        -ficha.obra_id,
    )


def ficha_por_defecto(fichas: Iterable[FichaObra]) -> FichaObra:
    """La ficha por defecto de un código.

    Lanza `ValueError` si no hay fichas o si mezclan códigos: el criterio se
    aplica DENTRO de un código, nunca entre códigos distintos.
    """
    lista = list(fichas)
    if not lista:
        raise ValueError("sin fichas no hay ficha por defecto")
    codigos = {f.codigo_obra for f in lista}
    if len(codigos) > 1:
        raise ValueError(f"fichas de códigos distintos: {sorted(codigos)}")
    return min(lista, key=clave_por_defecto)
