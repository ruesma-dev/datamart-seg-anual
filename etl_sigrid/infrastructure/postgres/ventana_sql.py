# etl_sigrid/infrastructure/postgres/ventana_sql.py
"""
F-025 · Las consultas de `check-ventana` (R26, R27, T17). **Solo texto.**

Al estilo de `unicidad_sql.py`, `cierres_sql.py` y `cobertura_sql.py`: este
módulo **no abre ninguna conexión**. Quien las ejecuta es el comando, con la
transacción en `READ ONLY` y su `statement_timeout`, porque esto corre contra
`psql-albaranes-rs9k2`, que comparten `albaranes` y `partes` **en producción**.

## Las cuatro preguntas, y por qué son cuatro y no una

El modo de fallo que esta feature no puede reintroducir es el de F-052: **un
dato que envejece y del que nadie se entera**. Con 880 obras congeladas hay
cuatro maneras distintas de que eso pase, y cada una necesita su pregunta:

1. **La firma cambió.** La obra congelada se movió en Sigrid. No se rescata
   —contradiría la decisión del humano (§3.1)— pero se **nombra**.
2. **Congelada y sin filas.** No debería poder pasar: R18 la habría
   reconstruido. Si pasa, hay un fallo en la clasificación y la obra está
   sencillamente ausente del datamart.
3. **El sello no es el vigente.** El SQL cambió y esa obra se quedó con la
   versión anterior. R17 lo evita reconstruyendo todo, así que esto denuncia el
   caso en el que R17 no llegó a aplicarse: una noche que murió a mitad.
4. **La reconstrucción completa está vencida.** El domingo no corrió, y el
   «hasta 6 días» que el humano aceptó ha dejado de ser cierto.

Ninguna de las cuatro barre `stg.plan_mensual`: todas se resuelven sobre
`_meta.obra_build`, que tiene una fila por obra —del orden de 900—. Es
deliberado, y es lo que las hace baratas de correr cada noche sobre un servidor
sin créditos de CPU. La única excepción es la comprobación de filas, que va por
`EXISTS` sobre el índice `idx_plan_mensual_obra_amb`.

## El sello vigente entra interpolado, y se valida antes

Es el único valor que se compone en el texto. Sale de un `sha256` calculado por
nosotros, no de fuera, pero se valida igual contra `^[0-9a-f]{64}$`: la
alternativa es confiar en que quien llame no lo cambie nunca, y ese tipo de
confianza es la que acaba en un incidente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from etl_sigrid.domain.ventana import (
    TIPO_COMPLETA_VENCIDA,
    TIPO_CONGELADA_SIN_FILAS,
    TIPO_FIRMA_DIVERGENTE,
    TIPO_SELLO_NO_VIGENTE,
    HallazgoVentana,
)

# Reexportadas a propósito, no copiadas: las sentencias previas que dejan la
# transacción en READ ONLY con su timeout son EXACTAMENTE las mismas que las de
# las otras comprobaciones. Copiarlas aquí sería abrir la puerta a que una de
# las copias perdiera el `transaction_read_only` sin que nadie lo notara.
from etl_sigrid.infrastructure.postgres.unicidad_sql import (  # noqa: F401
    sentencias_previas,
)

#: Segundos por consulta. Generoso pero acotado: las cuatro van sobre
#: `_meta.obra_build`, que tiene una fila por obra, así que si esto salta es que
#: pasa algo raro y el comando lo dirá en vez de contarlo como correcto.
TIMEOUT_POR_CONSULTA_S = 120

#: Un `sha256` hexadecimal. Es lo único que se interpola en estas consultas.
_SELLO = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ConsultaVentana:
    """Una de las cuatro preguntas, lista para ejecutar."""

    nombre: str
    sql: str
    #: Lo que se le pasa a `PostgresClient.filas_solo_lectura`, que es quien
    #: emite de verdad `SET LOCAL statement_timeout` y
    #: `SET LOCAL transaction_read_only`. Viaja aquí para que se pueda mirar sin
    #: conexión, y no como una copia muerta de las sentencias.
    timeout_s: int


def sql_censo_registrado() -> str:
    """Cuántas obras hay en el registro. **El denominador del veredicto.**

    Va como consulta propia porque un cero aquí no es «no hay nada malo», es
    «no he podido mirar», y las otras cuatro no saben distinguirlo: todas
    devolverían la lista vacía. Es el mismo arreglo que se le hizo a
    `check-cobertura` el 2026-09-03, y este guardián nace con él puesto.
    """
    return "SELECT count(*) FROM _meta.obra_build"


def sql_firma_divergente() -> str:
    """Obras congeladas cuyo origen ha cambiado (R16, R26).

    Se comparan las dos firmas **solo cuando las dos existen**: `a <> b` con
    cualquiera a `NULL` devuelve `NULL`, no `FALSE`, y en un `WHERE` eso
    descarta la fila en silencio. Con una firma a nulo la respuesta correcta es
    «no se sabe», y esa obra entra ya por R18.
    """
    return (
        "SELECT obra_id, COALESCE(codigo_obra, ''), construido_at, firma_actual_at\n"
        "FROM _meta.obra_build\n"
        "WHERE congelada\n"
        "  AND firma_origen IS NOT NULL\n"
        "  AND firma_actual IS NOT NULL\n"
        "  AND firma_origen <> firma_actual\n"
        "ORDER BY construido_at NULLS FIRST, obra_id"
    )


def sql_congelada_sin_filas() -> str:
    """Obras congeladas que no tienen filas construidas (R18, R26).

    **No debería devolver nada nunca**: R18 reconstruye toda obra sin filas. Si
    devuelve algo, hay un fallo en la clasificación y esa obra está ausente del
    datamart, que es el defecto de F-052 otra vez.

    El `NOT EXISTS` va por `idx_plan_mensual_obra_amb`, que empieza por
    `obra_id`: una sonda de índice por obra, no un barrido de 29 M de filas.
    """
    return (
        "SELECT b.obra_id, COALESCE(b.codigo_obra, ''), b.construido_at, b.motivo\n"
        "FROM _meta.obra_build b\n"
        "WHERE b.congelada\n"
        "  AND NOT EXISTS (\n"
        "        SELECT 1 FROM stg.plan_mensual pm WHERE pm.obra_id = b.obra_id\n"
        "      )\n"
        "ORDER BY b.obra_id"
    )


def sql_sello_no_vigente(sello_vigente: str) -> str:
    """Obras construidas con una versión del SQL que ya no es la vigente (R17).

    R17 evita este caso reconstruyendo TODAS las obras la noche en que el SQL
    cambia. Lo que denuncia esto es el caso en el que R17 **no llegó a
    aplicarse**: la noche murió a mitad y unas obras se rehicieron y otras no.
    """
    if not _SELLO.match(sello_vigente or ""):
        raise ValueError(
            f"el sello vigente tiene que ser un sha256 hexadecimal de 64 "
            f"caracteres y llego {sello_vigente!r}. Se interpola en el SQL: no "
            f"se compone con nada que no se haya validado."
        )
    return (
        "SELECT obra_id, COALESCE(codigo_obra, ''), construido_at, "
        "COALESCE(sello_sql, '')\n"
        "FROM _meta.obra_build\n"
        f"WHERE COALESCE(sello_sql, '') <> '{sello_vigente}'\n"
        "ORDER BY construido_at NULLS FIRST, obra_id"
    )


def consultas_de_ventana(
    sello_vigente: str, timeout_s: int = TIMEOUT_POR_CONSULTA_S
) -> tuple[ConsultaVentana, ...]:
    """Las cuatro lecturas, en el orden en que se leen. **Sin conexión.**"""
    return (
        ConsultaVentana("censo", sql_censo_registrado(), timeout_s),
        ConsultaVentana("firma_divergente", sql_firma_divergente(), timeout_s),
        ConsultaVentana("sin_filas", sql_congelada_sin_filas(), timeout_s),
        ConsultaVentana("sello", sql_sello_no_vigente(sello_vigente), timeout_s),
    )


def hallazgos_de(
    firma_divergente: list, sin_filas: list, sello: list
) -> tuple[HallazgoVentana, ...]:
    """Convierte las filas crudas en hallazgos con su detalle legible.

    El detalle lleva **la fecha de construcción** porque es lo primero que
    pregunta quien lee la denuncia: no es lo mismo una obra congelada desde
    anteayer que una que lleva sin tocarse desde marzo.
    """
    hallazgos: list[HallazgoVentana] = []

    for obra_id, codigo, construido_at, comprobado_at in firma_divergente:
        hallazgos.append(
            HallazgoVentana(
                tipo=TIPO_FIRMA_DIVERGENTE,
                obra_id=int(obra_id),
                codigo_obra=str(codigo or ""),
                detalle=(
                    f"el origen ha cambiado desde que se construyo "
                    f"({_fecha(construido_at)}); comprobado el "
                    f"{_fecha(comprobado_at)}. NO se reconstruye por su cuenta "
                    f"(decision del humano): la pone al dia el domingo"
                ),
            )
        )

    for obra_id, codigo, construido_at, motivo in sin_filas:
        hallazgos.append(
            HallazgoVentana(
                tipo=TIPO_CONGELADA_SIN_FILAS,
                obra_id=int(obra_id),
                codigo_obra=str(codigo or ""),
                detalle=(
                    f"congelada por «{motivo or 'sin motivo'}» y SIN filas en "
                    f"stg.plan_mensual (ultima construccion: "
                    f"{_fecha(construido_at)}). Esto no deberia pasar: R18 "
                    f"reconstruye toda obra sin filas"
                ),
            )
        )

    for obra_id, codigo, construido_at, sello_obra in sello:
        hallazgos.append(
            HallazgoVentana(
                tipo=TIPO_SELLO_NO_VIGENTE,
                obra_id=int(obra_id),
                codigo_obra=str(codigo or ""),
                detalle=(
                    f"construida el {_fecha(construido_at)} con el sello "
                    f"{(sello_obra or '(ninguno)')[:8]}, que ya no es el "
                    f"vigente: le falta el ultimo cambio del SQL"
                ),
            )
        )

    return tuple(hallazgos)


def hallazgo_completa_vencida(dias: float | None, maximo: int) -> HallazgoVentana:
    """La cuarta denuncia (R26): hace demasiado que no se rehace todo."""
    cuanto = "nunca se ha hecho" if dias is None else f"hace {dias:.1f} dias"
    return HallazgoVentana(
        tipo=TIPO_COMPLETA_VENCIDA,
        obra_id=0,
        codigo_obra="",
        detalle=(
            f"la ultima reconstruccion completa fue {cuanto}, por encima del "
            f"maximo de {maximo}. Las obras congeladas llevan mas tiempo del "
            f"aceptado sin actualizarse"
        ),
    )


def _fecha(valor) -> str:
    """Una marca de tiempo como la lee una persona, o «nunca»."""
    if valor is None:
        return "nunca"
    return str(valor)[:19]
