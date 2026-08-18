# etl_sigrid/infrastructure/postgres/frescura.py
"""
Frescura del datamart: la forma de una fila de `_meta.v_frescura` y el formato
con el que se enseña (F-024).

Responde a la pregunta que hoy no tiene respuesta desde fuera del ETL: lo que
estoy viendo en Power BI, ¿es de esta noche o de hace tres días?

Mismo patrón que `timings.py`: puro, sin BBDD. El cliente lee las filas; aquí
solo se les da forma y se emite el veredicto.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from etl_sigrid.domain.coherencia import (
    EstadoTablaRaw,
    VeredictoCoherencia,
    formatear_veredicto_raw,
)

#: Horas que puede llevar `mart` sin un build completo antes de considerarse
#: caducado (DA-4). El job arranca a las 02:00 UTC y tarda ~3 h 15: con 24 h
#: saltaría cada mañana durante la hora en que la carga nueva aún no ha
#: terminado. 30 h cubre una noche entera más la variación de duración.
#:
#: Este número vive también en `infra/env/dev.json` (`frescuraUmbralHoras`),
#: de donde sale la ventana de la alerta de Azure. El contenedor NO lleva ese
#: fichero, así que no se puede leer en tiempo de ejecución: lo único que
#: impide que los dos valores diverjan es un test que los cruza.
UMBRAL_FRESCURA_HORAS = 30

VEREDICTO_FRESCO = "FRESCO"
VEREDICTO_CADUCADO = "CADUCADO"
VEREDICTO_SIN_BUILD = "SIN BUILD REGISTRADO"

#: Con qué se señala una tabla que rompe la coherencia de `raw` (R20). Sin
#: marca visual hay que comparar 32 `batch_id` a ojo, que es justo lo que nadie
#: hace a las 8 de la mañana.
MARCA_INCOHERENTE = "!"

_SIN_DATO = "-"
_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True, slots=True)
class FilaFrescura:
    """Una fila de `_meta.v_frescura`.

    «Último OK» y «último intento» van por separado a propósito: un
    `build_mart` que falló esta noche deja `mart` con lo de ayer, y quien lo
    consulta necesita las dos noticias, no una.
    """

    paso: str
    ultimo_ok_finished_at: datetime | None
    ultimo_ok_batch_id: str | None
    ultimo_ok_filas: int | None
    horas_desde_ultimo_ok: float | None
    ultimo_intento_started_at: datetime | None
    ultimo_intento_status: str | None
    ultimo_intento_error: str | None


# ---------------------------------------------------------------------------
# R19 · Frescura: tabla y veredicto
# ---------------------------------------------------------------------------

_CABECERA_FRESCURA = (
    f"{'paso':<18} {'ultimo OK':<19} {'horas':>7} {'filas':>12}  "
    f"{'ultimo intento':<19} estado"
)


def format_frescura(
    filas: Sequence[FilaFrescura],
    umbral_horas: float = UMBRAL_FRESCURA_HORAS,
    paso: str = "build_mart",
    ahora: datetime | None = None,
) -> tuple[str, str]:
    """Tabla de frescura + veredicto del paso pedido.

    Devuelve `(texto, veredicto)`. El veredicto es uno de `FRESCO`,
    `CADUCADO` o `SIN BUILD REGISTRADO`, y de él sale el código de salida de
    `check-frescura`.

    Las horas se RECALCULAN aquí con `ahora` en vez de usar la columna
    `horas_desde_ultimo_ok` de la vista: esa columna existe para que el MCP y
    Power BI la lean sin lógica, pero un test no puede mover el reloj del
    servidor. El dato de origen —`ultimo_ok_finished_at`— es el mismo.

    La tabla sale ENTERA aunque el veredicto sea de un solo paso: el
    diagnóstico de «mart está viejo» suele estar en la fila de `ingest_raw`.
    """
    instante = datetime.utcnow() if ahora is None else ahora

    lineas = [_CABECERA_FRESCURA, "-" * len(_CABECERA_FRESCURA)]
    for fila in filas:
        horas = _horas_desde(fila.ultimo_ok_finished_at, instante)
        lineas.append(
            f"{fila.paso:<18} "
            f"{_fecha(fila.ultimo_ok_finished_at):<19} "
            f"{(f'{horas:.1f}' if horas is not None else _SIN_DATO):>7} "
            f"{(f'{fila.ultimo_ok_filas:,}' if fila.ultimo_ok_filas is not None else _SIN_DATO):>12}  "
            f"{_fecha(fila.ultimo_intento_started_at):<19} "
            f"{fila.ultimo_intento_status or _SIN_DATO}"
        )

    if not filas:
        lineas.append(
            "(sin filas en _meta.v_frescura: ningún paso ha dejado registro "
            "todavía)"
        )

    horas_del_paso = _horas_del_paso(filas, paso, instante)
    veredicto = _veredicto(horas_del_paso, umbral_horas)

    lineas.append("")
    lineas.append(
        f"{paso}: {veredicto} (umbral {umbral_horas} h, "
        f"lleva {f'{horas_del_paso:.1f}' if horas_del_paso is not None else _SIN_DATO} h "
        f"desde el último build correcto)"
    )
    return "\n".join(lineas), veredicto


def _veredicto(horas: float | None, umbral_horas: float) -> str:
    """Sin ningún OK no es lo mismo que caducado.

    «CADUCADO» significa «lo que ves es viejo»; «SIN BUILD REGISTRADO»
    significa «no hay nada que ver». Confundirlos manda a buscar datos viejos
    donde no hay datos.
    """
    if horas is None:
        return VEREDICTO_SIN_BUILD
    # El límite es superarlo, no alcanzarlo: mismo criterio que la puerta de
    # disco de F-019.
    return VEREDICTO_CADUCADO if horas > umbral_horas else VEREDICTO_FRESCO


def _horas_del_paso(
    filas: Sequence[FilaFrescura], paso: str, ahora: datetime
) -> float | None:
    for fila in filas:
        if fila.paso == paso:
            return _horas_desde(fila.ultimo_ok_finished_at, ahora)
    return None


def _horas_desde(momento: datetime | None, ahora: datetime) -> float | None:
    if momento is None:
        return None
    return (ahora - momento).total_seconds() / 3600.0


def _fecha(momento: datetime | None) -> str:
    return momento.strftime(_FORMATO_FECHA) if momento is not None else _SIN_DATO


# ---------------------------------------------------------------------------
# R20 · Estado por tabla de `raw`
# ---------------------------------------------------------------------------

_CABECERA_RAW = (
    f"  {'tabla':<20} {'estado':<9} {'batch':<26} {'fin':<19} {'filas':>12}"
)


def format_estado_raw(
    estados: Sequence[EstadoTablaRaw],
    veredicto: VeredictoCoherencia,
) -> str:
    """Una línea por tabla de `raw`, con las incoherentes marcadas.

    Cierra con el veredicto y, si es KO, con el mensaje accionable de R9. Es
    la salida de `check-coherencia`, el comando que responde «¿por qué se negó
    a construir?» sin tener que abrir una consola de psql.
    """
    incoherentes = _tablas_incoherentes(veredicto)

    lineas = [_CABECERA_RAW, "-" * len(_CABECERA_RAW)]
    for estado in estados:
        marca = MARCA_INCOHERENTE if estado.tabla in incoherentes else " "
        lineas.append(
            f"{marca} {estado.tabla:<20} {estado.status:<9} "
            f"{estado.batch_id or _SIN_DATO:<26} "
            f"{_fecha(estado.finished_at):<19} {estado.filas:>12,}"
        )

    for tabla in veredicto.faltantes:
        lineas.append(
            f"{MARCA_INCOHERENTE} {tabla:<20} {'(nunca ingerida)':<9}"
        )

    if not estados and not veredicto.faltantes:
        lineas.append("  (sin filas en _meta.v_raw_state: raw está vacío)")

    lineas.append("")
    lineas.append(formatear_veredicto_raw(veredicto))
    return "\n".join(lineas)


def _tablas_incoherentes(veredicto: VeredictoCoherencia) -> set[str]:
    """Las que rompen la coherencia, por cualquiera de los motivos de R8."""
    marcadas = {e.tabla for e in veredicto.no_exitosas}
    marcadas |= {e.tabla for e in veredicto.sin_batch}
    for _batch, tablas in veredicto.batches_distintos:
        marcadas |= {e.tabla for e in tablas}
    return marcadas
