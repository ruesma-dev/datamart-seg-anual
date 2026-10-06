# etl_sigrid/domain/historial_estados.py
"""
La FOTO DIARIA de estados de contratos y facturas (F-067) y la fecha de Delphi.

POR QUÉ EXISTE. Compras quiere «los contratos que llevan más de tres semanas
enviados y sin firmar», y la fecha del cambio de estado NO EXISTE en Sigrid:
`concam` audita 1,5 M de cambios y ni uno del campo `est`, y `confir` no tiene
ni una firma de contrato. Decisión del humano (2026-09-06): construirla aquí,
como una foto diaria, que empieza a contar el día que se despliega.

POR TRAMOS Y NO UNA FILA POR DÍA. Es la misma foto sin repetir lo que no
cambia: un tramo es (documento, estado, desde, hasta) y la foto de cualquier
día se reconstruye con `desde <= día < COALESCE(hasta, infinito)`. Medido el
2026-10-06: 185.754 documentos y decenas de cambios al día; por tramos son
< 50.000 filas al año, y una fila por día serían 68 M.

LA REGLA LA EJECUTA SQL (`sql/compras/11_historial_estados.sql`, un bloque
`DO`), y aquí está escrita **una sola vez** como oráculo puro: los literales
—los tipos, el umbral, los motivos y la época— viven aquí y
`tests/test_f067_sql.py` comprueba que el SQL lleva LOS MISMOS. Mismo patrón
que `domain/comparativos.py` (F-038).

`con.tiemod` NO ES LA FECHA DEL CAMBIO DE ESTADO (D2 del humano): medido, la
firma no lo mueve en el 85 % de los comparativos firmados. Se publica como
fecha de última modificación del contrato y nunca entra en la antigüedad.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal

#: Los tipos de documento (`con.tip`) de la foto: contrato y factura. El
#: comparativo no entra: sus firmas ya tienen fecha (F-038).
TIPOS_HISTORIAL: tuple[int, ...] = (44, 15)

#: La guarda contra una ingesta a medias (R6): si los documentos de la foto
#: presentes en `raw.con` son MENOS de este tanto por uno de los tramos
#: abiertos, la foto no se toma. Una `raw.con` a medias cerraría como
#: DESAPARECIDOS miles de documentos que siguen vivos, y eso no se deshace.
UMBRAL_PRESENCIA: Decimal = Decimal("0.98")

#: Por qué se cierra un tramo: el documento cambió de estado, o ya no está.
MOTIVOS_CIERRE: tuple[str, ...] = ("CAMBIO", "DESAPARECIDO")
_CAMBIO, _DESAPARECIDO = MOTIVOS_CIERRE

#: La época de las fechas serie de Sigrid (`con.tiemod`): la de Delphi. SQL
#: Server convierte el mismo número con 1900-01-01 y da dos días más.
EPOCA_DELPHI: date = date(1899, 12, 30)


@dataclass(frozen=True, slots=True)
class Tramo:
    """Una fila de `compras.historial_estados`.

    `desde` es la primera foto que ve el documento en ese estado y `hasta` la
    primera que ya no (NULL = vigente). El cambio ocurrió entre
    `observado_antes` (la foto anterior) y `desde`, no a una hora exacta. En la
    línea base `observado_antes` es NULL: ya estaba así y no se sabe desde
    cuándo.
    """

    documento_id: int
    tipo: int
    estado_id: int | None
    desde: datetime
    hasta: datetime | None
    observado_antes: datetime | None
    es_linea_base: bool
    motivo_cierre: str | None


@dataclass(frozen=True, slots=True)
class ResumenFoto:
    """Los contadores de una fila de `compras.historial_estados_fotos` (R8)."""

    n_documentos: int
    n_cambios: int
    n_altas: int
    n_desaparecidos: int


class FotoIncompletaError(Exception):
    """La ingesta trajo menos documentos de los que la historia tiene abiertos."""


def aplicar_foto(
    tramos: Sequence[Tramo],
    actuales: Mapping[int, tuple[int, int | None]],
    observado_en: datetime | None,
    ultima_foto: datetime | None,
) -> list[Tramo] | None:
    """Los tramos tras tomar la foto de `observado_en`, o None si no hay foto.

    `actuales` es `{con.ide: (con.tip, con.est)}`; lo que no sea de
    `TIPOS_HISTORIAL` se ignora, como el `WHERE tip IN (44, 15)` del SQL.

    - None si no hay instante observado o no es más nuevo que la última foto
      (R7): relanzar el build sin ingesta nueva no escribe nada.
    - `FotoIncompletaError` si hay tramos abiertos y los documentos presentes
      son menos del 98 % (R6).
    - Si no: cada tramo abierto cuyo documento ya no está con ese tipo se
      cierra como DESAPARECIDO (R5); si está con otro estado (comparado como
      `IS DISTINCT FROM`), como CAMBIO (R2). Cada documento presente sin tramo
      abierto abre uno con `desde = observado_en`, `observado_antes =
      ultima_foto` y línea base solo si no había foto anterior (R2-R4).
    """
    if observado_en is None:
        return None
    if ultima_foto is not None and observado_en <= ultima_foto:
        return None

    vigentes = {
        ide: valor for ide, valor in actuales.items() if valor[0] in TIPOS_HISTORIAL
    }
    n_abiertos = sum(1 for t in tramos if t.hasta is None)
    # Sin tramos abiertos (la línea base) la comparación es `n < 0`, que nunca
    # se cumple: no hace falta preguntar antes si hay alguno. El SQL lo escribe
    # explícito (`v_abiertos > 0 AND ...`) y es lo mismo; aquí, escrito así, la
    # campaña de mutación no tiene un mutante equivalente que justificar.
    if len(vigentes) < UMBRAL_PRESENCIA * n_abiertos:
        raise FotoIncompletaError(
            f"la ingesta trae {len(vigentes)} documentos de los tipos "
            f"{TIPOS_HISTORIAL} y la historia tiene {n_abiertos} tramos abiertos: "
            f"menos del {UMBRAL_PRESENCIA:.0%}. No se toma la foto."
        )

    resultado: list[Tramo] = []
    siguen_abiertos: set[int] = set()
    for tramo in tramos:
        if tramo.hasta is not None:
            resultado.append(tramo)
            continue
        actual = vigentes.get(tramo.documento_id)
        if actual is None or actual[0] != tramo.tipo:
            resultado.append(
                replace(tramo, hasta=observado_en, motivo_cierre=_DESAPARECIDO)
            )
        elif actual[1] != tramo.estado_id:
            resultado.append(replace(tramo, hasta=observado_en, motivo_cierre=_CAMBIO))
        else:
            resultado.append(tramo)
            siguen_abiertos.add(tramo.documento_id)

    for ide in sorted(vigentes):
        if ide in siguen_abiertos:
            continue
        tipo, estado = vigentes[ide]
        resultado.append(
            Tramo(
                documento_id=ide,
                tipo=tipo,
                estado_id=estado,
                desde=observado_en,
                hasta=None,
                observado_antes=ultima_foto,
                es_linea_base=ultima_foto is None,
                motivo_cierre=None,
            )
        )
    return resultado


def resumir_foto(tramos: Sequence[Tramo], observado_en: datetime) -> ResumenFoto:
    """Los contadores de la foto `observado_en` sobre los tramos resultantes.

    Un CAMBIO cierra un tramo y abre otro en la misma foto, así que las altas
    son los tramos abiertos en esa foto menos los cambios: documentos nuevos o
    que reaparecen. `n_documentos` son los tramos vigentes tras la foto, que es
    lo mismo que los documentos de la foto presentes en `raw.con`.
    """
    cambios = sum(
        1 for t in tramos if t.hasta == observado_en and t.motivo_cierre == _CAMBIO
    )
    desaparecidos = sum(
        1 for t in tramos if t.hasta == observado_en and t.motivo_cierre == _DESAPARECIDO
    )
    abiertos_en_la_foto = sum(1 for t in tramos if t.desde == observado_en)
    return ResumenFoto(
        n_documentos=sum(1 for t in tramos if t.hasta is None),
        n_cambios=cambios,
        n_altas=abiertos_en_la_foto - cambios,
        n_desaparecidos=desaparecidos,
    )


def dias_en_estado(desde: date, hoy: date) -> int:
    """Días de calendario desde que la foto vio el documento en su estado.

    En un tramo de línea base es un MÍNIMO («lleva al menos N días»): ya
    estaba así antes de la primera foto (R10).
    """
    return (hoy - desde).days


def fecha_delphi(valor: float | None) -> datetime | None:
    """Una fecha serie de Sigrid (días desde 1899-12-30, hora en la parte
    decimal) como `datetime`. None para None, 0 o negativo, igual que el
    `CASE WHEN v > 0` de `compras.fn_sigrid_tiempo`."""
    if valor is None or valor <= 0:
        return None
    return datetime.combine(EPOCA_DELPHI, time()) + timedelta(days=valor)
