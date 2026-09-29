# etl_sigrid/domain/mes_fase.py
"""
F-118 (F-051 absorbida) · El mes de un cierre real lo da el TEXTO de su fase.

Sigrid archiva cada fase de obra (`raw.obrfas`) con un `ano`/`mes`, unas fechas
de inicio y fin y un texto libre (`res`, en `stg.fases.nombre_mes`) que es lo
que el jefe de obra escribe: «Agosto 2026», «Diciembre-24», «Enero 2020-Abril
2020». Decisión del humano del 2026-09-22: **manda el texto**; si no se entiende,
la fecha fin; si no hay, la de inicio; y en último lugar el mes archivado.

Este módulo es el **oráculo puro** de esa regla, token a token igual que
`stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase` (`sql/stg/00_functions.sql`).
`python main.py check-mes-fase` compara los dos lados sobre todas las fases: si
difieren, uno de los dos está mal. Capa **domain**: sin imports de
infraestructura, sin logging.

## El parser (R3, R4)

1. Mayúsculas y sin tildes; el punto de millar de un año suelto («2.013») se
   quita; letras y cifras pegadas se separan («AGOSTO17» → «AGOSTO 17»); todo
   lo que no es letra ni cifra separa tokens.
2. Se recorren **todos** los tokens (R3, rango → su último mes):
   - un nombre de mes sustituye al mes anterior;
   - un año de cuatro cifras 2000-2099 sustituye al anterior;
   - un número de **dos** cifras justo detrás de un nombre de mes es su año
     (2000 + n): «Mayo-17», «DICIEMBRE 09 A FEBRERO 2010»;
   - un número de dos cifras 20-99 sin año todavía es el año (lo que ya hacía el
     parser de `cierre`);
   - un 1-12 sin mes todavía es el mes («03/2021»).
3. Sin mes o sin año, no hay fecha: la decide la cascada de `mes_de_fase`.

El parser de `cierre` (`cierre.fn_parse_mes_fase`) NO cambia: decide también el
mes de las versiones master de cierre, y R3 le cambiaría textos como «CIERRE
ENERO-FEBRERO 25» que F-118 no mide (R5).

## El relleno (R10-R14)

Una fase de **rango** (el mes de su fecha fin es posterior al de su fecha de
inicio) cuyo texto cae después de su primer mes lleva todo su dinero al mes del
texto; los meses desde el de inicio hasta el anterior al del texto reciben filas
de **relleno**: movimiento 0 y el acumulado arrastrado. `meses_relleno` dice qué
meses rellena cada fase; qué partidas y con qué importe lo decide
`etl_sigrid.domain.serie_real`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

#: Prefijos de los nombres de mes, en el orden y con la misma forma que el
#: `CASE` de `stg.fn_parse_mes_texto`. Septiembre es el único con dos grafías.
_PREFIJOS_MES = (
    ("ENE", 1),
    ("FEB", 2),
    ("MAR", 3),
    ("ABR", 4),
    ("MAY", 5),
    ("JUN", 6),
    ("JUL", 7),
    ("AGO", 8),
    ("OCT", 10),
    ("NOV", 11),
    ("DIC", 12),
)

_TILDES = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN")
_MILLAR = re.compile(r"(?<![0-9.])([0-9])\.([0-9]{3})(?![0-9])")
_LETRA_CIFRA = re.compile(r"([A-Z])([0-9])")
_CIFRA_LETRA = re.compile(r"([0-9])([A-Z])")
_SEPARADOR = re.compile(r"[^A-Z0-9]+")


def _mes_del_token(token: str) -> int | None:
    if token == "SEP" or token.startswith("SEPT") or token.startswith("SET"):
        return 9
    for prefijo, numero in _PREFIJOS_MES:
        if token.startswith(prefijo):
            return numero
    return None


def tokens_del_texto(texto: str) -> list[str]:
    """Los tokens que recorre el parser, ya normalizados (paso 1)."""
    s = texto.upper().translate(_TILDES).strip()
    s = _MILLAR.sub(r"\1\2", s)
    s = _LETRA_CIFRA.sub(r"\1 \2", s)
    s = _CIFRA_LETRA.sub(r"\1 \2", s)
    return [t for t in _SEPARADOR.split(s) if t]


def parse_mes_fase(texto: str | None) -> date | None:
    """Primer día del mes que nombra el texto de una fase real, o `None`."""
    if texto is None:
        return None
    mes: int | None = None
    anio: int | None = None
    tras_mes = False
    for token in tokens_del_texto(texto):
        numero_mes = _mes_del_token(token)
        if numero_mes is not None:
            mes = numero_mes
            tras_mes = True
            continue
        if token.isdigit():
            valor = int(token)
            if len(token) == 4 and 2000 <= valor <= 2099:
                anio = valor
            elif len(token) == 2 and tras_mes:
                anio = 2000 + valor
            elif len(token) == 2 and valor >= 20 and anio is None:
                anio = 2000 + valor
            elif len(token) <= 2 and 1 <= valor <= 12 and mes is None:
                mes = valor
        tras_mes = False
    if mes is None or anio is None:
        return None
    return date(anio, mes, 1)


def _primero_de_mes(fecha: date | None) -> date | None:
    return None if fecha is None else fecha.replace(day=1)


def mes_de_fase(
    fecha_inicio: date | None,
    nombre_mes: str | None,
    fecha_fin: date | None = None,
    mes_archivado: date | None = None,
) -> date | None:
    """El mes de una fase real: texto → fecha fin → fecha inicio → archivado.

    R2: el texto manda aunque discrepe de las fechas, también en fases de un
    solo mes y aunque caiga fuera de ellas. R6 (D5): si no se lee, la cascada
    de fechas, de la fin a la de inicio y, sin ninguna, el `ano`/`mes` que
    archiva `obrfas`.
    """
    for candidato in (
        parse_mes_fase(nombre_mes),
        _primero_de_mes(fecha_fin),
        _primero_de_mes(fecha_inicio),
        _primero_de_mes(mes_archivado),
    ):
        if candidato is not None:
            return candidato
    return None


# ---------------------------------------------------------------------------
# El relleno de las fases de rango (R10, R11, R14)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaseReal:
    """Una fase VIGENTE de una (obra, ámbito) real, ya con el mes de su texto.

    `anio_mes` es `mes_de_fase(...)`; las fechas son las de `stg.fases`, y de
    ellas sale si la fase es de rango.
    """

    numero_fase: int
    anio_mes: date
    fecha_inicio: date | None
    fecha_fin: date | None


def _mes_siguiente(mes: date) -> date:
    return date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)


def meses_relleno(fases: Sequence[FaseReal]) -> dict[int, tuple[date, ...]]:
    """Los meses que rellena cada fase vigente de UNA (obra, ámbito).

    - R10: solo las fases de rango cuyo mes del texto es posterior al de su
      fecha de inicio, desde ese mes hasta el anterior al del texto.
    - R11 (D1 de F-051): nunca un mes que ya tiene cierre vigente propio, valga
      lo que valga.
    - R14: nada después del mes del texto.
    - Dos fases de rango solapadas que quieren el mismo mes: lo rellena la de
      mes del texto más cercano (la que cierra antes). Así ningún mes se
      repite y la serie de cada partida tiene una sola fila por mes.

    Las fases deben ser las VIGENTES (R8, F-042 sobre el mes del texto): una
    fase que pierde su mes no rellena nada. Dos del mismo mes son un error de
    quien llama, y se levanta `ValueError`.
    """
    ocupados: dict[date, int] = {}
    for fase in fases:
        if fase.anio_mes in ocupados:
            raise ValueError(
                f"las fases {ocupados[fase.anio_mes]} y {fase.numero_fase} tienen "
                f"el mismo mes {fase.anio_mes:%Y-%m}: aplica antes la regla de "
                f"F-042 (R8), solo rellenan las vigentes"
            )
        ocupados[fase.anio_mes] = fase.numero_fase

    duenio: dict[date, FaseReal] = {}
    for fase in fases:
        if fase.fecha_inicio is None or fase.fecha_fin is None:
            continue
        inicio = _primero_de_mes(fase.fecha_inicio)
        if _primero_de_mes(fase.fecha_fin) <= inicio or fase.anio_mes <= inicio:
            continue
        mes = inicio
        while mes < fase.anio_mes:
            if mes not in ocupados:
                actual = duenio.get(mes)
                if actual is None or fase.anio_mes < actual.anio_mes:
                    duenio[mes] = fase
            mes = _mes_siguiente(mes)

    resultado: dict[int, list[date]] = {}
    for mes in sorted(duenio):
        resultado.setdefault(duenio[mes].numero_fase, []).append(mes)
    return {fase: tuple(meses) for fase, meses in resultado.items()}
