# etl_sigrid/infrastructure/postgres/cobertura_sql.py
"""
F-052 · Las dos consultas de `check-cobertura` (R13 a R15, R18, R19).
**Solo construyen texto.**

Al estilo de `unicidad_sql.py` y `cierres_sql.py`: este módulo **no abre ninguna
conexión**. Quien las ejecuta es el comando, con la transacción en `READ ONLY` y
su `statement_timeout`, porque esto corre contra `psql-albaranes-rs9k2`, que
comparten `albaranes` y `partes` **en producción**.

Son dos preguntas, y son distintas:

1. **Huérfanas** — filas de `stg.plan_mensual` cuyo `partida_id` no está en
   `stg.partidas` o cuyo `obra_id` no está en `stg.obras`, agrupadas por obra y
   ámbito. Es exactamente lo que los cuatro `INNER JOIN` de
   `mart/02_build_fact.sql` borran hoy sin decir nada: **183.756 + 82.815 filas**
   medidas el 2026-08-31.
2. **Obra invisible** — obra con filas en `stg.plan_mensual` para un ámbito y
   **cero** en `mart.fact_seguimiento_mensual` para ese mismo ámbito.

## Por qué la segunda compara PRESENCIA y no conteo

El build de planificado no es un `JOIN` puro: `master_proyectado` elige la
versión vigente de cada mes, así que en los ámbitos master (8 y 11) muchísimas
filas de `stg` no llegan al fact **por diseño**, y contar sería inventarse una
alarma permanente. La condición es «cero filas en el fact», que en los reales
(3 y 7) es igual de exigente porque allí el build sí es un `JOIN` puro.

## Por qué se baja a `raw` a por el nombre

Una obra ausente de `stg.obras` no tiene allí ni código ni nombre —justamente las
19 que la consulta 1 denuncia—. Sin recuperarlos de `raw.con`, la denuncia diría
«obra 2824201» y nadie sabría cuál es, ni podría declararla como excepción en
`config/cobertura_excepciones.yaml`.

## El coste, que es un riesgo declarado

Las dos barren `stg.plan_mensual` entera —del orden de decenas de millones de
filas— sobre un `B1ms` con techo de 10 MiB/s, y encima de una nocturna que ya
cuesta 3 h 45. Por eso T13 lo **mide antes** de darlo por bueno y por eso cada
consulta lleva su `statement_timeout`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from etl_sigrid.domain.cobertura import FilaCobertura

# Reexportados a propósito, no copiados: las dos sentencias previas que dejan la
# transacción en READ ONLY con su timeout, y la lista de palabras que un SELECT
# de diagnóstico no puede contener ni por accidente, son EXACTAMENTE las mismas
# que las de las otras comprobaciones. Copiarlas aquí sería abrir la puerta a que
# una de las copias perdiera el `transaction_read_only` sin que nadie lo notara.
from etl_sigrid.infrastructure.postgres.cierres_sql import (  # noqa: F401
    PALABRAS_DE_ESCRITURA,
)
from etl_sigrid.infrastructure.postgres.unicidad_sql import (  # noqa: F401
    sentencias_previas,
)

#: Los cuatro ámbitos que el fact construye. Fuera de ellos `stg.plan_mensual`
#: guarda 6,7 millones de filas que el fact **no mira por diseño**: contarlas
#: como pérdida sería ruido permanente (R25).
AMBITOS_DEL_FACT = (3, 7, 8, 11)

#: Segundos por consulta. Generoso —las dos agregan `stg.plan_mensual` entera—
#: y aun así acotado, porque el servidor es compartido. Si salta, el comando lo
#: dice y **no lo cuenta como correcto**.
TIMEOUT_POR_CONSULTA_S = 300

_AMBITOS = ", ".join(str(a) for a in AMBITOS_DEL_FACT)


@dataclass(frozen=True, slots=True)
class ConsultaCobertura:
    """Una de las dos preguntas, lista para ejecutar."""

    nombre: str
    sql: str
    #: Lo que se le pasa a `PostgresClient.filas_solo_lectura`, que es quien
    #: emite de verdad `SET LOCAL statement_timeout` y
    #: `SET LOCAL transaction_read_only` (R19). Viaja aquí para que se pueda
    #: mirar sin conexión, y no como una copia muerta de las sentencias.
    timeout_s: int


def sql_huerfanas() -> str:
    """Filas de `stg.plan_mensual` sin ficha de partida o de obra (R15).

    `LEFT JOIN` y no `INNER`: con `INNER` la consulta perdería justo las filas
    que busca, que es el chiste exacto del defecto que denuncia.
    """
    return (
        "SELECT pm.obra_id,\n"
        "       COALESCE(o.codigo_obra, TRIM(c.cod), '')  AS codigo_obra,\n"
        "       COALESCE(o.nombre_obra, c.res, '')        AS nombre_obra,\n"
        "       pm.ambito_id,\n"
        "       count(*) AS huerfanas\n"
        "FROM stg.plan_mensual pm\n"
        "LEFT JOIN stg.obras    o ON o.obra_id    = pm.obra_id\n"
        "LEFT JOIN stg.partidas p ON p.partida_id = pm.partida_id\n"
        # `raw.con` es de donde `stg/03_obras.sql` saca el codigo y el nombre.
        "LEFT JOIN raw.con      c ON c.ide        = pm.obra_id\n"
        f"WHERE pm.ambito_id IN ({_AMBITOS})\n"
        "  AND (o.obra_id IS NULL OR p.partida_id IS NULL)\n"
        "GROUP BY pm.obra_id, 2, 3, pm.ambito_id\n"
        "ORDER BY 5 DESC, 1, 4"
    )


def sql_obras_invisibles() -> str:
    """Obras con filas en `stg` y **cero** en el fact para el mismo ámbito (R14)."""
    return (
        "WITH en_stg AS (\n"
        "    SELECT pm.obra_id, pm.ambito_id, count(*) AS filas\n"
        "    FROM stg.plan_mensual pm\n"
        f"    WHERE pm.ambito_id IN ({_AMBITOS})\n"
        "    GROUP BY 1, 2\n"
        "),\n"
        "en_mart AS (\n"
        "    SELECT f.obra_id, f.ambito_id, count(*) AS filas\n"
        "    FROM mart.fact_seguimiento_mensual f\n"
        f"    WHERE f.ambito_id IN ({_AMBITOS})\n"
        "    GROUP BY 1, 2\n"
        ")\n"
        "SELECT s.obra_id,\n"
        "       COALESCE(o.codigo_obra, TRIM(c.cod), '') AS codigo_obra,\n"
        "       COALESCE(o.nombre_obra, c.res, '')       AS nombre_obra,\n"
        "       s.ambito_id,\n"
        "       s.filas AS filas_stg,\n"
        "       COALESCE(m.filas, 0) AS filas_mart\n"
        "FROM en_stg s\n"
        "LEFT JOIN en_mart  m ON m.obra_id = s.obra_id\n"
        "                    AND m.ambito_id = s.ambito_id\n"
        "LEFT JOIN stg.obras o ON o.obra_id = s.obra_id\n"
        "LEFT JOIN raw.con   c ON c.ide     = s.obra_id\n"
        # Presencia, no conteo: ver la cabecera del modulo.
        "WHERE COALESCE(m.filas, 0) = 0\n"
        "ORDER BY 1, 4"
    )


def consultas_de_cobertura(
    timeout_s: int = TIMEOUT_POR_CONSULTA_S,
) -> tuple[ConsultaCobertura, ConsultaCobertura]:
    """Las dos, en el orden en el que se leen. **No abre ninguna conexión.**"""
    return (
        ConsultaCobertura("huerfanas", sql_huerfanas(), timeout_s),
        ConsultaCobertura("invisibles", sql_obras_invisibles(), timeout_s),
    )


def filas_de_cobertura(
    huerfanas: Sequence[Sequence], invisibles: Sequence[Sequence]
) -> tuple[FilaCobertura, ...]:
    """Funde los dos resultados en una fila por (obra × ámbito).

    Las dos mitades van juntas porque una obra puede ser invisible **y** tener
    huérfanas —la 0599 lo es en los dos sentidos— y separarlas obligaría a quien
    lee el informe a cruzarlas a mano.
    """
    por_clave: dict[tuple[int, int], dict] = {}

    def _hueco(obra_id: int, codigo: str, nombre: str, ambito_id: int) -> dict:
        clave = (int(obra_id), int(ambito_id))
        actual = por_clave.setdefault(
            clave,
            {
                "obra_id": int(obra_id),
                "codigo_obra": "",
                "nombre_obra": "",
                "ambito_id": int(ambito_id),
                "filas_stg": 0,
                "filas_mart": 0,
                "huerfanas": 0,
            },
        )
        # El primero que traiga identidad manda; los dos la resuelven igual.
        actual["codigo_obra"] = actual["codigo_obra"] or str(codigo or "")
        actual["nombre_obra"] = actual["nombre_obra"] or str(nombre or "")
        return actual

    for obra_id, codigo, nombre, ambito_id, cuantas in huerfanas:
        _hueco(obra_id, codigo, nombre, ambito_id)["huerfanas"] += int(cuantas)

    for obra_id, codigo, nombre, ambito_id, filas_stg, filas_mart in invisibles:
        fila = _hueco(obra_id, codigo, nombre, ambito_id)
        fila["filas_stg"] = int(filas_stg)
        fila["filas_mart"] = int(filas_mart)

    return tuple(
        FilaCobertura(**datos) for _clave, datos in sorted(por_clave.items())
    )
