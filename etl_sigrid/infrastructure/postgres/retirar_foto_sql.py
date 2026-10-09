# etl_sigrid/infrastructure/postgres/retirar_foto_sql.py
"""
F-132 · Fase B · El SQL de `python main.py retirar-foto-estados`. **Solo
construye texto.**

La foto diaria de estados de F-067 (`compras.historial_estados` y
`compras.historial_estados_fotos`) se montó creyendo que Sigrid no fechaba el
cambio de estado. F-085 lo desmintió (`rac`), F-132 publicó la antigüedad del
estado desde `rac` y el contraste de las dos noches que hubo (492 cambios, 0
discrepancias) la dejó sin función. **Decisión del humano del 2026-10-09: D7 =
BORRAR.** Se pierde lo único que la foto veía y `rac` no —la noche en que se
DESHIZO un paso, ~9 al día—, hasta que F-105 lo traiga de `dbo.log`.

Este es el ÚNICO fichero de `etl_sigrid/` que nombra esas dos tablas (lo veta
`tests/test_f132_retirada.py`): ningún build las crea ni las lee ya.

- `SQL_TABLAS_FOTO`: cuáles de las dos existen y cuántas filas tienen. Un
  `SELECT` de solo lectura (el comando lo lanza con `filas_solo_lectura`, en
  una transacción READ ONLY); cuenta con `query_to_xml` para no fallar si una
  de las dos ya no está.
- `SENTENCIAS_RETIRADA`: el borrado, en UNA transacción. `DROP TABLE IF
  EXISTS` de las dos a la vez y **sin `CASCADE`**: nada depende de ellas desde
  F-132 (la vista sale de `rac`), y si algo dependiera, el `DROP` falla y no se
  borra nada. `lock_timeout` acotado a la transacción: si la nocturna de una
  imagen vieja las tuviera bloqueadas, se espera 30 s y se falla, en vez de
  quedarse colgado delante de todo lo que pida después un lock sobre ellas.
"""

from __future__ import annotations

#: Las dos tablas de la foto diaria de F-067, en orden alfabético.
TABLAS_FOTO: tuple[str, ...] = ("historial_estados", "historial_estados_fotos")

_LISTA = ", ".join(f"'{tabla}'" for tabla in TABLAS_FOTO)

SQL_TABLAS_FOTO = f"""
SELECT c.relname,
       (xpath('/row/n/text()',
              query_to_xml(format('SELECT count(*) AS n FROM compras.%I', c.relname),
                           FALSE, TRUE, '')))[1]::TEXT::BIGINT AS filas
FROM   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE  n.nspname = 'compras' AND c.relkind IN ('r', 'p')
  AND  c.relname IN ({_LISTA})
ORDER BY c.relname
"""

SENTENCIAS_RETIRADA: tuple[str, ...] = (
    "SET LOCAL lock_timeout = '30s'",
    "DROP TABLE IF EXISTS "
    + ", ".join(f"compras.{tabla}" for tabla in TABLAS_FOTO),
)
