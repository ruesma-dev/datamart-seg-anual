# etl_sigrid/domain/coherencia.py
"""
Veredicto de coherencia de las capas del datamart (F-024).

Responde a dos preguntas, y solo a esas dos:

  1. ¿Puedo construir `stg`? Es decir: ¿TODAS las tablas de `raw` que declara
     `config/tables_sigrid.yaml` vienen de la MISMA ejecución, y esa ejecución
     terminó bien para cada una de ellas?
  2. ¿Puedo construir `mart`? Es decir: ¿el último `build_stg` terminó?

Por qué esto vive en el dominio y no dentro de los steps: es la decisión de
«construir o negarse», la que evita que un `raw` mezclado acabe en cuadros que
no cuadran. Aquí se puede comprobar exhaustivamente sin BBDD, con fixtures, y
la mutación tiene dónde morder. Los steps se limitan a leer el estado, pedir
el veredicto y obedecerlo.

Funciones puras y deterministas: el mismo conjunto de estados produce el mismo
veredicto y el mismo texto, entre en el orden que entre. Un incidente que se
repite tiene que producir el mismo mensaje.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

#: El único estado que acredita una tabla ingerida por completo.
ESTADO_EXITOSO = "SUCCESS"

#: Nombre del paso de nivel de pipeline que construye `stg`. La puerta de
#: `mart` exige que la ÚLTIMA fila de `build_stg%` sea exactamente esta y no
#: un sub-paso: la fila de paso solo se inserta cuando el step termina.
PASO_STG = "build_stg"

#: Formato de las fechas dentro de los mensajes. Legible por un humano a las 8
#: de la mañana, no ISO para máquinas.
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

#: Las DOS únicas salidas ante un `raw` incoherente (R9). Se escriben aquí, una
#: sola vez, para que el mensaje no pueda ir sugiriendo cosas distintas según
#: quién lo edite.
ACCION_INGESTA_COMPLETA = "python main.py ingest --full"
ACCION_STAGE_SIN_PUERTA = "python main.py stage --sin-puerta"
ACCION_STAGE = "python main.py stage"
ACCION_MART_SIN_PUERTA = "python main.py build-mart --sin-puerta"


@dataclass(frozen=True, slots=True)
class EstadoTablaRaw:
    """Última ingesta conocida de una tabla de `raw` (fila de `v_raw_state`)."""

    tabla: str
    status: str
    batch_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    filas: int = 0


@dataclass(frozen=True, slots=True)
class EstadoPaso:
    """Una fila de `_meta.etl_runs` vista como «último intento de un paso»."""

    id: int
    step: str
    status: str
    batch_id: str | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class VeredictoCoherencia:
    """Resultado de una puerta: si se puede construir, y si no, por qué no.

    Los motivos van CLASIFICADOS y no como una lista de frases porque cada uno
    se arregla de una forma distinta, y porque el comando `check-coherencia`
    tiene que poder marcarlos tabla a tabla sin volver a parsear texto.
    """

    ok: bool
    batch_id: str | None = None
    #: Declaradas en el YAML que nunca se ingirieron.
    faltantes: tuple[str, ...] = ()
    #: Su último intento no terminó en SUCCESS (FAILED, ABORTED, RUNNING).
    no_exitosas: tuple[EstadoTablaRaw, ...] = ()
    #: Ingeridas antes de F-024: sin forma de saber de qué carga vienen.
    sin_batch: tuple[EstadoTablaRaw, ...] = ()
    #: Mapa batch -> tablas, ordenado por batch (y por tanto por fecha).
    batches_distintos: tuple[tuple[str, tuple[EstadoTablaRaw, ...]], ...] = ()
    #: Solo en el veredicto de `stg`: la fila que se miró para decidir.
    ultimo_paso: EstadoPaso | None = field(default=None)


# ---------------------------------------------------------------------------
# Puerta de `raw` antes de construir `stg` (R8)
# ---------------------------------------------------------------------------


def evaluar_coherencia_raw(
    estados: Iterable[EstadoTablaRaw],
    tablas_requeridas: Sequence[str],
) -> VeredictoCoherencia:
    """OK si y solo si todas las requeridas vienen del MISMO batch en SUCCESS.

    Las tablas de `raw` que no estén declaradas se ignoran: `raw` acumula
    restos de cargas manuales (compras, retenciones) que no son asunto de esta
    puerta.

    Un `raw` sin ninguna tabla requerida —o un YAML vacío— es KO: no hay batch
    único que acreditar. Es deliberadamente conservador.
    """
    requeridas = sorted(set(tablas_requeridas))
    por_tabla = {e.tabla: e for e in estados}

    faltantes = tuple(t for t in requeridas if t not in por_tabla)
    presentes = [por_tabla[t] for t in requeridas if t in por_tabla]

    no_exitosas = tuple(e for e in presentes if e.status != ESTADO_EXITOSO)
    exitosas = [e for e in presentes if e.status == ESTADO_EXITOSO]

    sin_batch = tuple(e for e in exitosas if not e.batch_id)

    agrupadas: dict[str, list[EstadoTablaRaw]] = {}
    for tabla in exitosas:
        if tabla.batch_id:
            agrupadas.setdefault(tabla.batch_id, []).append(tabla)
    batches = tuple((b, tuple(agrupadas[b])) for b in sorted(agrupadas))

    ok = (
        not faltantes
        and not no_exitosas
        and not sin_batch
        and len(batches) == 1
    )

    return VeredictoCoherencia(
        ok=ok,
        batch_id=batches[0][0] if ok else None,
        faltantes=faltantes,
        no_exitosas=no_exitosas,
        sin_batch=sin_batch,
        batches_distintos=batches if len(batches) > 1 else (),
    )


def formatear_veredicto_raw(veredicto: VeredictoCoherencia) -> str:
    """Mensaje accionable del veredicto de `raw` (R9).

    Termina con las DOS acciones posibles y solo esas. Que no haya una tercera
    sugerencia es parte del requisito: quien lee esto a las 8 de la mañana
    tiene que saber qué hacer, no elegir entre cinco caminos.
    """
    if veredicto.ok:
        return (
            f"Coherencia de raw: OK. Las tablas declaradas provienen todas de "
            f"la ejecucion {veredicto.batch_id}."
        )

    lineas = [
        "Coherencia de raw: KO. El esquema raw no acredita una carga completa "
        "y coherente, asi que no se construye stg encima:",
    ]

    if veredicto.faltantes:
        lineas.append(
            "  · declaradas en tables_sigrid.yaml y nunca ingeridas: "
            + ", ".join(veredicto.faltantes)
        )

    if veredicto.no_exitosas:
        detalle = ", ".join(
            f"{e.tabla} ({e.status})" for e in veredicto.no_exitosas
        )
        lineas.append(
            "  · su ultimo intento de ingesta no termino en SUCCESS: " + detalle
        )

    if veredicto.sin_batch:
        lineas.append(
            "  · ingeridas sin identidad de ejecucion (historico anterior a "
            "F-024): " + ", ".join(e.tabla for e in veredicto.sin_batch)
        )

    if veredicto.batches_distintos:
        lineas.append("  · provienen de ejecuciones DISTINTAS:")
        for batch, tablas in veredicto.batches_distintos:
            lineas.append(
                f"      {batch} (fin {_fin_de(tablas)}): "
                + ", ".join(e.tabla for e in tablas)
            )

    lineas.append("")
    lineas.append("Solo hay dos salidas:")
    lineas.append(f"  1. Relanzar la ingesta completa: {ACCION_INGESTA_COMPLETA}")
    lineas.append(
        f"  2. Si la carga parcial fue deliberada: {ACCION_STAGE_SIN_PUERTA} "
        f"(el veredicto queda registrado como SKIPPED en _meta.etl_runs)"
    )
    return "\n".join(lineas)


def _fin_de(tablas: Sequence[EstadoTablaRaw]) -> str:
    """Fecha en que terminó de ingerirse el batch: la más tardía del grupo."""
    fechas = [t.finished_at for t in tablas if t.finished_at is not None]
    return max(fechas).strftime(FORMATO_FECHA) if fechas else "sin fecha"


# ---------------------------------------------------------------------------
# Puerta de `stg` antes de construir `mart` (R15, DA-5)
# ---------------------------------------------------------------------------


def evaluar_coherencia_stg(ultimo: EstadoPaso | None) -> VeredictoCoherencia:
    """OK si y solo si la fila más reciente de `build_stg%` es el paso completo.

    La fila de paso `build_stg` la inserta el orquestador (o `_ejecutar_paso`)
    cuando el step TERMINA. Un proceso muerto a mitad deja como última fila un
    sub-paso o un tramo, y eso es exactamente lo que hay que detectar: `stg`
    mezclado, con unas tablas de esta noche y otras de ayer.

    Ojo al caso sutil: un sub-paso en SUCCESS tampoco vale. Que `build_obras`
    terminara bien no dice nada de `build_presupuesto`.
    """
    ok = (
        ultimo is not None
        and ultimo.step == PASO_STG
        and ultimo.status == ESTADO_EXITOSO
    )
    return VeredictoCoherencia(
        ok=ok,
        batch_id=ultimo.batch_id if ok else None,
        ultimo_paso=ultimo,
    )


def formatear_veredicto_stg(veredicto: VeredictoCoherencia) -> str:
    """Mensaje accionable del veredicto de `stg` (R15)."""
    if veredicto.ok:
        return (
            f"Coherencia de stg: OK. El ultimo build_stg termino correctamente "
            f"(ejecucion {veredicto.batch_id})."
        )

    ultimo = veredicto.ultimo_paso
    if ultimo is None:
        detalle = (
            "no hay ninguna fila de build_stg en _meta.etl_runs: stg nunca se "
            "ha construido, o su historico se perdio"
        )
    else:
        detalle = (
            f"la fila mas reciente de build_stg es '{ultimo.step}' en estado "
            f"{ultimo.status}, no el paso 'build_stg' completo: el ultimo "
            f"stage no llego a terminar y stg puede estar mezclado"
        )

    return "\n".join(
        [
            f"Coherencia de stg: KO. {detalle}.",
            "",
            "Solo hay dos salidas:",
            f"  1. Reconstruir stg: {ACCION_STAGE}",
            f"  2. Si construir sobre este stg fue deliberado: "
            f"{ACCION_MART_SIN_PUERTA} (el veredicto queda registrado como "
            f"SKIPPED en _meta.etl_runs)",
        ]
    )
