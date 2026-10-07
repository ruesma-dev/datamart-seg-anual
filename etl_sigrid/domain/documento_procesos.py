# etl_sigrid/domain/documento_procesos.py
"""
El HISTORIAL DE PROCESOS de los documentos de Sigrid (F-085): quién hizo qué
paso, desde qué estado, a cuál y cuándo.

LA FUENTE ES `rac`, el registro de procesos de Sigrid —la ventana «Procesos»
del documento—: una fila por paso, con el proceso, el estado de ORIGEN
(`est1`) y de DESTINO (`est2`), el login (`usu`), la fecha (`fec`, AAAAMMDD) y
la hora (`hor`, HHMMSS, hora local de Madrid, la de pantalla). Medido el
2026-10-07 en solo lectura: cubre el 99,94 % de las facturas, el 97,1 % de los
contratos, el 97,0 % de los comparativos y el 72,2 % de las obras (las que
faltan no han salido de su estado inicial). Es la historia NETA: «Deshacer
proceso» BORRA el paso; la bruta está en `dbo.log` (F-105).

LA REGLA LA EJECUTA SQL (`sql/compras/12_documento_procesos.sql` y
`sql/personal/06_usuarios_sigrid.sql`), y aquí está escrita **una sola vez**
como oráculo puro: los literales —las familias, el orden de desempate, la
normalización del login, la empresa preferente— viven aquí y
`tests/test_f085_sql.py` comprueba que el SQL lleva LOS MISMOS. Mismo patrón
que `domain/historial_estados.py` (F-067).

Y AQUÍ VIVE LA LISTA DE CREDENCIALES de la tabla `usu` de Sigrid (contraseña,
firma digital, política de la clave, identificadores de seguridad y de
certificado). `config/tables_sigrid.yaml` las excluye de la ingesta y un test
falla si alguna deja de estar excluida (R3).

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

#: Las familias de documento (`con.tip`) del historial y su nombre publicado
#: (D2 del humano, 2026-10-07). Ampliar a otra familia es tocar ESTE dict: el
#: `IN` y el `CASE` del SQL tienen que llevar exactamente estas parejas.
FAMILIAS: Final[dict[int, str]] = {
    15: "FACTURA",
    44: "CONTRATO",
    46: "COMPARATIVO",
    42: "OBRA",
}

#: Las columnas de `usu` que son credenciales o metadatos de credencial (D4):
#: `cla` contraseña, `fir` firma digital, `feccla` y `diascla` la política de
#: la clave, `sid` Security ID y `cerid` certificado digital. NUNCA se ingieren.
COLUMNAS_CREDENCIALES_USU: Final[frozenset[str]] = frozenset(
    {"cla", "fir", "feccla", "diascla", "sid", "cerid"}
)

#: Cuando un código de empleado (`usu.codemp`) tiene una ficha por empresa, se
#: queda la de esta empresa (medido el 2026-10-07: 21 usuarios con varias
#: fichas, los 21 con exactamente una en la empresa 1).
EMPRESA_PREFERENTE: Final[int] = 1

#: Los segundos de un día: `dias_desde_anterior` es la diferencia en días.
_SEGUNDOS_DIA: Final[Decimal] = Decimal(86400)
_DOS_DECIMALES: Final[Decimal] = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Paso:
    """Una fila de `rac` ya traducida: el paso de un documento."""

    paso_id: int
    documento_id: int
    estado_origen_id: int | None
    estado_destino_id: int | None
    fecha: date | None
    hora: time | None

    @property
    def momento(self) -> datetime | None:
        """Fecha y hora juntas; None si falta cualquiera de las dos (R10)."""
        if self.fecha is None or self.hora is None:
            return None
        return datetime.combine(self.fecha, self.hora)


@dataclass(frozen=True, slots=True)
class PasoEncadenado:
    """Un paso con su posición en la cadena de su documento (R11-R13)."""

    paso: Paso
    orden: int
    es_ultimo: bool
    encaja_con_anterior: bool | None
    dias_desde_anterior: Decimal | None


def hora_sigrid(hhmmss: int | None) -> time | None:
    """La hora de `rac.hor` (entero HHMMSS), o None si no es una hora (R10).

    0 o None es «sin hora»; fuera de 1..235959, o con minutos o segundos
    de 60 o más, no es una hora válida.
    """
    if hhmmss is None or not 1 <= hhmmss <= 235959:
        return None
    horas, resto = divmod(hhmmss, 10000)
    minutos, segundos = divmod(resto, 100)
    if minutos >= 60 or segundos >= 60:
        return None
    return time(horas, minutos, segundos)


def normalizar_login(login: str | None) -> str | None:
    """El login para casar `rac.usu` con `usu.cod` (R14): `UPPER(BTRIM(x))`.

    `BTRIM` de Postgres quita solo espacios, así que aquí también. Vacío tras
    quitarlos es None: un login en blanco no casa con nadie.
    """
    if login is None:
        return None
    normalizado = login.strip(" ").upper()
    return normalizado or None


def _clave_orden(paso: Paso) -> tuple[bool, date, bool, time, int]:
    """`ORDER BY fecha NULLS LAST, hora NULLS LAST, paso_id` (R11)."""
    return (
        paso.fecha is None,
        paso.fecha or date.min,
        paso.hora is None,
        paso.hora or time.min,
        paso.paso_id,
    )


def _dias_entre(anterior: datetime | None, actual: datetime | None) -> Decimal | None:
    """Días con dos decimales, redondeo como `ROUND(numeric, 2)` de Postgres."""
    if anterior is None or actual is None:
        return None
    segundos = Decimal(int((actual - anterior).total_seconds()))
    return (segundos / _SEGUNDOS_DIA).quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def encadenar(pasos: Iterable[Paso]) -> list[PasoEncadenado]:
    """Los pasos numerados dentro de su documento (R11-R13).

    Por documento, en el orden de `_clave_orden`: `orden` desde 1, `es_ultimo`
    el de mayor orden, `encaja_con_anterior` si el origen es el destino del
    paso anterior (None en el primero) y `dias_desde_anterior` entre los dos
    momentos (None en el primero o si falta alguno). El resultado va por
    documento y orden.
    """
    por_documento: dict[int, list[Paso]] = {}
    for paso in pasos:
        por_documento.setdefault(paso.documento_id, []).append(paso)

    resultado: list[PasoEncadenado] = []
    for documento_id in sorted(por_documento):
        cadena = sorted(por_documento[documento_id], key=_clave_orden)
        anterior: Paso | None = None
        for orden, paso in enumerate(cadena, start=1):
            if anterior is None:
                encaja, dias = None, None
            else:
                encaja = paso.estado_origen_id == anterior.estado_destino_id
                dias = _dias_entre(anterior.momento, paso.momento)
            resultado.append(
                PasoEncadenado(
                    paso=paso,
                    orden=orden,
                    es_ultimo=orden == len(cadena),
                    encaja_con_anterior=encaja,
                    dias_desde_anterior=dias,
                )
            )
            anterior = paso
    return resultado


def empleado_de_usuario(candidatos: Sequence[tuple[int, int]]) -> int | None:
    """El empleado de un usuario de Sigrid, o None (R18).

    `candidatos` son `(empleado_id, empresa)` de las fichas de empleado
    (`con` tipo 43) cuyo código es el `usu.codemp`. Una → ésa. Varias (una por
    empresa) → la ÚNICA de `EMPRESA_PREFERENTE`. Ninguna, o varias sin una
    única de la empresa preferente → None: mejor sin empleado que con uno
    elegido al azar.
    """
    if len(candidatos) == 1:
        return candidatos[0][0]
    preferentes = [ide for ide, empresa in candidatos if empresa == EMPRESA_PREFERENTE]
    if len(preferentes) == 1:
        return preferentes[0]
    return None
