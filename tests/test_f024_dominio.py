# tests/test_f024_dominio.py
"""
F-024 · Tests del dominio puro: identidad de ejecución (R1) y veredicto de
coherencia (R8, R9).

NINGÚN test de este fichero abre red ni BBDD. Todo lo que se prueba aquí son
funciones puras: reciben datos y devuelven datos. Es a propósito, y es la
razón de que la decisión de «construir o negarse» viva en el dominio y no
dentro de un step: así se puede comprobar exhaustivamente sin un servidor
delante.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from etl_sigrid.domain.ejecucion import (
    BYTES_DEL_SUFIJO,
    FORMATO_INSTANTE,
    MOTIVO_HUERFANA,
    Ejecucion,
    nueva_ejecucion,
)
from etl_sigrid.domain.entities import StepStatus

# La forma exacta que exige R1: UTC compacto + guion + 6 hexadecimales. Se
# escribe aquí como literal y no derivada del código para que un cambio en el
# formato tenga que pasar por este test: el `batch_id` acaba en `_meta` de
# producción y en las consultas del MCP, no es un detalle interno.
FORMA_BATCH = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")


# ---------------------------------------------------------------------------
# R1 · Cada ejecución tiene un identificador único
# ---------------------------------------------------------------------------


def test_f024_r1_batch_id_tiene_forma_y_es_unico() -> None:
    """Forma `YYYYMMDDTHHMMSSZ-xxxxxx` y sin colisiones dentro del proceso."""
    ejecucion = nueva_ejecucion()

    assert FORMA_BATCH.match(ejecucion.batch_id), (
        f"batch_id fuera de forma: {ejecucion.batch_id!r}"
    )

    # 500 en el mismo segundo: el sufijo es lo único que las distingue, así que
    # esto comprueba de verdad que hay aleatoriedad y cuánta.
    lote = {nueva_ejecucion().batch_id for _ in range(500)}
    assert len(lote) == 500, "hay batch_id repetidos dentro del mismo proceso"


def test_f024_r1_el_sufijo_aleatorio_mide_seis_hexadecimales() -> None:
    """Seis, ni cinco ni ocho: es lo que fija la forma de R1 y lo que da
    16,7 millones de combinaciones por segundo."""
    assert BYTES_DEL_SUFIJO == 3  # 3 bytes = 6 caracteres hex

    sufijo = nueva_ejecucion().batch_id.split("-")[1]
    assert len(sufijo) == 6
    assert set(sufijo) <= set("0123456789abcdef")


def test_f024_r1_batch_id_ordena_cronologicamente() -> None:
    """Como TEXTO. Es lo que permite `ORDER BY batch_id` sin parsear nada."""
    instantes = [
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2026, 1, 1, 0, 0, 1),
        datetime(2026, 1, 1, 0, 1, 0),
        datetime(2026, 1, 1, 1, 0, 0),
        datetime(2026, 1, 2, 0, 0, 0),
        datetime(2026, 2, 1, 0, 0, 0),
        datetime(2027, 1, 1, 0, 0, 0),
    ]
    batches = [nueva_ejecucion(ahora=t, sufijo="aaaaaa").batch_id for t in instantes]

    assert batches == sorted(batches)
    # Y estrictamente creciente: dos instantes distintos no dan el mismo texto.
    assert len(set(batches)) == len(batches)


def test_f024_r1_el_instante_inyectado_manda_sobre_el_reloj() -> None:
    """`ahora` y `sufijo` se inyectan para que el resultado sea comprobable."""
    momento = datetime(2026, 8, 18, 2, 0, 5)
    ejecucion = nueva_ejecucion(ahora=momento, sufijo="0f1e2d")

    assert ejecucion.batch_id == "20260818T020005Z-0f1e2d"
    assert ejecucion.iniciada_en == momento
    assert momento.strftime(FORMATO_INSTANTE) == "20260818T020005Z"


def test_f024_r1_sin_instante_se_usa_el_reloj_utc() -> None:
    """Sin `ahora`, la marca es la de este momento en UTC (no la local)."""
    antes = datetime.utcnow()
    ejecucion = nueva_ejecucion()
    despues = datetime.utcnow()

    assert antes <= ejecucion.iniciada_en <= despues
    assert ejecucion.batch_id.startswith(ejecucion.iniciada_en.strftime(FORMATO_INSTANTE))


def test_f024_r1_la_ejecucion_es_inmutable() -> None:
    """Una vez creada no se le cambia el batch: todas las filas de esa
    ejecución tienen que compartir el mismo, y un objeto mutable invita a
    reasignarlo a mitad de una carga."""
    ejecucion = nueva_ejecucion(ahora=datetime(2026, 8, 18), sufijo="abc123")

    with pytest.raises(FrozenInstanceError):
        ejecucion.batch_id = "otro"  # type: ignore[misc]


def test_f024_r1_dos_ejecuciones_iguales_son_iguales() -> None:
    """Dataclass con igualdad por valor: lo que permite compararlas en tests
    y meterlas en un conjunto sin sorpresas."""
    momento = datetime(2026, 8, 18, 2, 0, 0)
    una = Ejecucion(batch_id="20260818T020000Z-aaaaaa", iniciada_en=momento)
    otra = nueva_ejecucion(ahora=momento, sufijo="aaaaaa")

    assert una == otra
    assert len({una, otra}) == 1


# ---------------------------------------------------------------------------
# R4 (vocabulario) · el motivo de la marca de huérfana y el estado ABORTED
# ---------------------------------------------------------------------------


def test_f024_r4_el_motivo_de_huerfana_nombra_ejecucion_e_instante() -> None:
    """El `error_message` tiene que decir QUIÉN la marcó y CUÁNDO: sin eso,
    una fila ABORTED es indistinguible de un fallo real del paso."""
    motivo = MOTIVO_HUERFANA.format(
        batch_id="20260818T020000-abc123", ahora="2026-08-19 07:31:02"
    )

    assert "20260818T020000-abc123" in motivo
    assert "2026-08-19 07:31:02" in motivo
    assert "huérfana" in motivo
    # Y por qué pasó: es lo que se lee a las 8 de la mañana sin más contexto.
    for pista in ("deadline", "OOM", "reinicio"):
        assert pista in motivo, f"el motivo no menciona '{pista}'"

    # La plantilla no deja marcadores sin sustituir.
    assert "{" not in motivo and "}" not in motivo


def test_f024_r4_aborted_es_parte_del_vocabulario_de_estados() -> None:
    """`ABORTED` no es una cadena suelta: es un `StepStatus` como los demás,
    y es lo que escribe el SQL de la marca a través de `.value`."""
    assert StepStatus.ABORTED.value == "ABORTED"
    assert StepStatus("ABORTED") is StepStatus.ABORTED
    # No sustituye a ninguno de los que ya había.
    assert {s.value for s in StepStatus} == {
        "PENDING", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "ABORTED",
    }
