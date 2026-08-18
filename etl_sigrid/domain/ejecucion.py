# etl_sigrid/domain/ejecucion.py
"""
Identidad de una ejecución del pipeline (F-024).

Una «ejecución» es una invocación de un comando que ESCRIBE (`run-all`,
`ingest`, `stage`, `build-mart`...). Todas las filas que ese proceso deja en
`_meta.etl_runs` comparten un `batch_id`, y eso es lo que después permite
responder a la pregunta que nadie podía responder el 2026-08-18: ¿de qué
carga viene cada tabla de `raw`?

El formato `YYYYMMDDTHHMMSSZ-xxxxxx` se eligió para que el identificador se
ordene cronológicamente **como texto**: un `ORDER BY batch_id` en Postgres, o
en Power BI, sale ordenado sin parsear nada. El sufijo aleatorio existe porque
dos procesos pueden arrancar en el mismo segundo (el cron y alguien desde el
puesto), y entonces la marca temporal sola no distinguiría nada.

Dominio puro: sin psycopg, sin click, sin settings. Solo `datetime` y
`secrets` de la biblioteca estándar.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

#: Marca temporal del `batch_id`. UTC compacto y ordenable como texto: los
#: campos van de mayor a menor magnitud y todos con ancho fijo.
FORMATO_INSTANTE = "%Y%m%dT%H%M%SZ"

#: Bytes de aleatoriedad del sufijo. Tres bytes = seis caracteres hexadecimales
#: = 16,7 millones de valores por segundo. Sobra para desempatar dos arranques
#: simultáneos y cabe en una línea de log sin estorbar.
BYTES_DEL_SUFIJO = 3

#: `error_message` con el que se cierran las filas `RUNNING` que dejó un
#: proceso muerto (R4). Dice las tres cosas que hacen falta a las 8 de la
#: mañana: qué pasó, quién lo detectó y cuándo.
MOTIVO_HUERFANA = (
    "huérfana: el proceso que la abrió no la cerró "
    "—muerte externa: deadline, OOM o reinicio—; "
    "marcada por la ejecución {batch_id} el {ahora}"
)


@dataclass(frozen=True, slots=True)
class Ejecucion:
    """Identidad de una invocación que escribe. Inmutable a propósito.

    Que sea `frozen` no es decoración: si alguien reasignara el `batch_id` a
    mitad de una carga, las filas de antes y las de después dejarían de
    pertenecer a la misma ejecución y la puerta de coherencia vería dos
    batches donde solo hubo uno.
    """

    batch_id: str
    iniciada_en: datetime


def nueva_ejecucion(
    ahora: datetime | None = None,
    sufijo: str | None = None,
) -> Ejecucion:
    """Crea la identidad de esta ejecución.

    `ahora` y `sufijo` se inyectan solo para poder comprobar el resultado: en
    producción no los pasa nadie y salen del reloj UTC y de `secrets`.
    """
    instante = datetime.utcnow() if ahora is None else ahora
    aleatorio = secrets.token_hex(BYTES_DEL_SUFIJO) if sufijo is None else sufijo
    return Ejecucion(
        batch_id=f"{instante.strftime(FORMATO_INSTANTE)}-{aleatorio}",
        iniciada_en=instante,
    )
