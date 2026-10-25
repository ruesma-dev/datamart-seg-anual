# etl_sigrid/domain/reanudacion.py
"""
Reanudar en vez de repetir (F-148, R18-R23).

El job nocturno tiene `replicaRetryLimit` 1: si la primera réplica muere, la
plataforma lanza otra con el MISMO nombre de ejecución. Hasta F-148 esa segunda
réplica empezaba de cero —la ingesta entera otra vez— y el 22-10 la noche
terminó a las 04:31. Ahora las dos réplicas comparten `batch_id` (su sufijo sale
del nombre de la ejecución) y la segunda omite lo que la primera ya dejó en
`SUCCESS`.

Lo que se omite, y por qué así:

  - Un PASO, solo si tiene fila sin punto en `SUCCESS` en el lote y todas sus
    dependencias también se omiten: si se repite la ingesta, `build_stg` se
    reconstruye encima aunque hubiera terminado (R21).
  - Ni si se rehace algo que el paso LEE sin declararlo como dependencia
    (`LECTURAS_PARA_REANUDAR`): unas retenciones omitidas sobre un `stg`
    rehecho quedarían calculadas con el de la primera réplica (riesgo R-a).
  - `apply_grants` nunca: es barato, idempotente y el que decide la noche.
  - Una TABLA de `raw`, si su fila `ingest_raw.<tabla>` está en `SUCCESS` en el
    lote. Como el lote es el mismo, la puerta de `build_stg` ve un solo lote
    (R24).

Dominio puro: sin psycopg, sin click, sin settings.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence, Set
from datetime import timedelta

#: Hasta dónde se busca un lote que adoptar. Una réplica no vive más que el
#: `replicaTimeout` del job (7 h): una ventana de 8 h cubre la primera réplica
#: entera y no alcanza a la noche anterior.
VENTANA_REANUDACION = timedelta(hours=8)

#: Pasos que se ejecutan aunque el lote ya los tenga en `SUCCESS`.
PASOS_NUNCA_OMITIBLES = frozenset({"apply_grants"})

#: Lo que un paso lee de otro build SIN declararlo en `depends_on`, solo para
#: decidir si se omite al reanudar (riesgo R-a de la revisión de F-148). No
#: cambia el orden ni las dependencias de la noche normal: `build_retenciones`
#: sigue dependiendo solo de la ingesta para construirse aunque `stg` falle
#: (F-110, D4), pero `05_fin_obra.sql` lee `stg.plan_mensual` y
#: `mart.master_versiones_tipadas`. Desde F-140 `build_tesoreria` hace lo mismo:
#: `07_devengo_pendiente.sql` lee `stg.plan_mensual` y `mart`. Son los únicos
#: builds que leen sin declararlo una tabla de un build ANTERIOR de la misma
#: noche (barrido de la revisión de F-148, ampliado por F-140).
LECTURAS_PARA_REANUDAR: dict[str, frozenset[str]] = {
    "build_retenciones": frozenset({"build_stg", "build_mart"}),
    "build_tesoreria": frozenset({"build_stg", "build_mart"}),
}

#: Caracteres hexadecimales del sufijo: los mismos que el aleatorio de F-024
#: (`BYTES_DEL_SUFIJO` = 3 bytes), para que el `batch_id` siga ordenando.
ANCHO_SUFIJO = 6

#: Prefijo de las filas de tramo de la ingesta: `ingest_raw.<tabla>`.
PREFIJO_TABLA_RAW = "ingest_raw."


def sufijo_de_ejecucion_job(nombre: str) -> str:
    """Sufijo del `batch_id` que comparten las réplicas de una ejecución del job.

    Sale del SHA-256 del nombre de la ejecución (`CONTAINER_APP_JOB_EXECUTION_NAME`)
    y no del nombre en claro: tiene el ancho fijo del sufijo aleatorio y no
    deja el nombre del recurso en cada fila de `_meta.etl_runs`.
    """
    return hashlib.sha256(nombre.encode("utf-8")).hexdigest()[:ANCHO_SUFIJO]


def pasos_a_omitir(
    orden: Sequence[tuple[str, Sequence[str]]],
    terminados: Set[str],
) -> frozenset[str]:
    """Pasos que la reanudación omite (R21).

    `orden` va en orden topológico —(nombre, dependencias)—, así que al llegar a
    un paso ya se sabe si sus dependencias se omiten. Las filas con punto de
    `terminados` (tramos como `ingest_raw.con`) no casan con ningún nombre de
    paso y no acreditan nada.

    Las lecturas de `LECTURAS_PARA_REANUDAR` cuentan como dependencias si el
    paso leído está en esta ejecución; si aún no se ha decidido (va detrás en
    `orden`), el paso se rehace: ante la duda, construir.
    """
    en_ejecucion = {nombre for nombre, _dependencias in orden}
    omitidos: set[str] = set()
    for nombre, dependencias in orden:
        lecturas = LECTURAS_PARA_REANUDAR.get(nombre, frozenset()) & en_ejecucion
        if (
            nombre in terminados
            and nombre not in PASOS_NUNCA_OMITIBLES
            and all(dep in omitidos for dep in dependencias)
            and lecturas <= omitidos
        ):
            omitidos.add(nombre)
    return frozenset(omitidos)


def tablas_a_omitir(declaradas: Iterable[str], terminados: Set[str]) -> frozenset[str]:
    """Tablas declaradas cuya fila `ingest_raw.<tabla>` está en `SUCCESS` (R23).

    Solo las declaradas: `ingest_raw.firma_origen` u otra fila de tramo que no
    es una tabla de `tables_sigrid.yaml` no entra.
    """
    return frozenset(t for t in declaradas if PREFIJO_TABLA_RAW + t in terminados)
