# etl_sigrid/application/steps/build_descompuestos_step.py
"""
Step que construye el esquema `descompuestos` (F-097): trocea el texto que dejo
`ingest_descompuestos` en `descompuestos._des_texto` y publica las lineas, el
catalogo de elementos, el cuadre y las tres vistas de Power BI.

Encadena los SQL de `sql/descompuestos/` en orden:

    00_setup.sql           esquema, estado del incremental, fn_num, fn_fecha
    01_troceado.sql        descompuestos.fn_trocear (UNA definicion)
    02_lineas_coste.sql    lineas y cuadre (DDL) + ESTUDIO y PLANIF_JO enteros
    03_lineas_master.sql   el MASTER por lotes de versiones (ver abajo)
    04_elementos.sql       el catalogo de elementos (DROP + CREATE)
    05_cuadre.sql          el cuadre del ambito 3 (ESTUDIO y PLANIF_JO)
    06_views.sql           v_pbi_estudio, v_pbi_planif_jo, v_pbi_master_planif_jo

**El master es incremental (R21).** Solo se retrocean las versiones cuyo sello
de troceado no es el del SQL vigente: las que la ingesta releyo esta noche
(les pone el sello a NULL) y todas si cambia `00_setup.sql`, `01_troceado.sql`
o `03_lineas_master.sql` (el sello es el hash de los tres; `00` entra con F-120
porque `fn_num` decide el rendimiento y el factor). Van por orden
—vigentes primero—, recortadas por el mismo tope de MB que la ingesta
(`DESCOMPUESTOS_PRESUPUESTO_MB`; `--sin-tope` lo ignora) y en lotes de
`MB_POR_LOTE`, cada lote UNA transaccion: el fichero 03 con sus marcadores
sustituidos por texto (patron de F-019, entrada blindada). Sin versiones
pendientes, 03 se ejecuta igual una vez con el lote a `FALSE`: los flags de la
vigente y el borrado de las versiones que ya no estan no esperan.

**Un esquema modulo, como `contabilidad`.** Lee solo `raw` y su propio esquema
(R26); ningun paso declara `build_descompuestos` en su `depends_on`: si falla,
la noche sigue y `R-FRESCURA` avisa. Depende de `ingest_raw` (lee `raw.dncpro`,
`raw.obrparpre`...) y de `ingest_descompuestos` (el texto).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.descompuestos import (
    VersionPendiente,
    cod_version_vigente,
    planificar_troceado,
)
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "postgres" / "sql" / "descompuestos"
)

#: Los ficheros cuyo texto forma el SELLO del troceado (R11). Si cambia
#: cualquiera de los tres, esa noche se retrocean TODAS las versiones (dentro
#: del tope; de una vez con `--sin-tope`). El orden entra en el hash.
#: `00_setup.sql` entra con F-120 (R21): define `fn_num`, que convierte el
#: precio, la cantidad y cada lado del «factor x rendimiento»; antes, cambiarla
#: no retroceaba nada. Mismo arreglo que F-118 hizo con el sello de `stg`.
FICHEROS_DEL_SELLO = ("00_setup.sql", "01_troceado.sql", "03_lineas_master.sql")

#: Los marcadores de `03_lineas_master.sql`, cada uno UNA vez.
MARCADOR_LOTE = "/*F097_LOTE*/"
MARCADOR_SELLO = "/*F097_SELLO*/"
MARCADOR_COD_VIGENTE = "/*F097_COD_VIGENTE*/"

#: Segundos de la lectura de las versiones pendientes (~3.000 filas).
TIMEOUT_LECTURA_S = 120

_SELLO = re.compile(r"^[0-9a-f]{16}$")
_COD = re.compile(r"^[0-9]+$")


@dataclass(slots=True, frozen=True)
class _SubStep:
    name: str
    sql_file: str
    target_schema: str | None = None
    target_table: str | None = None
    por_lotes: bool = False


#: Los siete ficheros SQL, EN ORDEN, de que tabla se cuentan filas y cual va por
#: lotes. Dato de modulo, como en `build_contabilidad_step`: sustituirlo en un
#: test es lo que permite ejercitar el fichero que falta. `lineas` se cuenta
#: tras el master, que es cuando esta completa.
SUB_PASOS: tuple[_SubStep, ...] = (
    _SubStep(name="setup", sql_file="00_setup.sql"),
    _SubStep(name="troceado", sql_file="01_troceado.sql"),
    _SubStep(name="lineas_coste", sql_file="02_lineas_coste.sql"),
    _SubStep(
        name="lineas_master", sql_file="03_lineas_master.sql",
        target_schema="descompuestos", target_table="lineas", por_lotes=True,
    ),
    _SubStep(
        name="elementos", sql_file="04_elementos.sql",
        target_schema="descompuestos", target_table="elementos",
    ),
    _SubStep(
        name="cuadre", sql_file="05_cuadre.sql",
        target_schema="descompuestos", target_table="cuadre_partida",
    ),
    _SubStep(name="vistas", sql_file="06_views.sql"),
)


def sello_de_troceado(directorio: Path = DIRECTORIO_SQL) -> str:
    """El hash (16 hex) del texto de los ficheros del troceado (R11)."""
    resumen = hashlib.sha256()
    for nombre in FICHEROS_DEL_SELLO:
        resumen.update(nombre.encode("utf-8"))
        resumen.update(b"\0")
        resumen.update((directorio / nombre).read_text(encoding="utf-8").encode("utf-8"))
        resumen.update(b"\0")
    return resumen.hexdigest()[:16]


def _validar_sello_y_cod(sello: str, cod: str) -> None:
    if not isinstance(sello, str) or not _SELLO.fullmatch(sello):
        raise ValueError(f"el sello de troceado tiene que ser 16 hex y es {sello!r}")
    if not isinstance(cod, str) or not _COD.fullmatch(cod):
        raise ValueError(f"el cod de la vigente tiene que ser solo digitos y es {cod!r}")


def componer_sql_lote(
    sql_texto: str, lote: Sequence[tuple[int, int]], sello: str, cod_vigente: str
) -> str:
    """Sustituye los tres marcadores de `03_lineas_master.sql`.

    Composicion TEXTUAL (el precedente es `componer_sql_tramo` de F-019), asi
    que la entrada se blinda: cada marcador UNA vez, cada `(obra, fase)` dos
    enteros de verdad (`bool` no cuenta), el sello 16 hex y el cod solo digitos.
    Un lote vacio es `FALSE`: el fichero corre sin trocear nada.
    """
    _validar_sello_y_cod(sello, cod_vigente)
    for marcador in (MARCADOR_LOTE, MARCADOR_SELLO, MARCADOR_COD_VIGENTE):
        if sql_texto.count(marcador) != 1:
            raise ValueError(
                f"el SQL del master debe contener el marcador {marcador} exactamente "
                f"una vez y aparece {sql_texto.count(marcador)}: no se ejecuta"
            )
    pares = []
    for par in lote:
        if len(par) != 2 or any(type(n) is not int for n in par):
            raise ValueError(f"cada version del lote son dos enteros (obra, fase): {par!r}")
        pares.append(f"({par[0]}, {par[1]})")
    filtro = f"(v.obra_id, v.fase_num) IN ({', '.join(pares)})" if pares else "FALSE"
    return (
        sql_texto.replace(MARCADOR_LOTE, filtro)
        .replace(MARCADOR_SELLO, f"'{sello}'")
        .replace(MARCADOR_COD_VIGENTE, f"'{cod_vigente}'")
    )


def sql_versiones_pendientes(sello: str, cod_vigente: str) -> str:
    """Las versiones cargadas cuyo troceado no es el del SQL vigente."""
    _validar_sello_y_cod(sello, cod_vigente)
    return (
        "SELECT v.obra_id, v.fase_num, v.bytes, "
        "COALESCE(v.fase_num = g.fase_vigente, FALSE) AS es_vigente "
        "FROM descompuestos._versiones_cargadas v "
        "LEFT JOIN (SELECT conide AS obra_id, MAX(valn) AS fase_vigente "
        f"FROM raw.conext WHERE cod = '{cod_vigente}' AND valn IS NOT NULL "
        "GROUP BY conide) g ON g.obra_id = v.obra_id "
        f"WHERE v.sello_troceado IS DISTINCT FROM '{sello}' "
        "ORDER BY v.obra_id, v.fase_num"
    )


class BuildDescompuestosStep(PipelineStep):
    """Construye el esquema `descompuestos` (lineas, elementos, cuadre, vistas)."""

    def __init__(self, settings: Settings, *, sin_tope: bool = False) -> None:
        self._settings = settings
        self._sin_tope = sin_tope

    @property
    def name(self) -> str:
        return "build_descompuestos"

    @property
    def stage(self) -> str:
        return "build_aux"

    @property
    def depends_on(self) -> list[str]:
        return ["ingest_raw", "ingest_descompuestos"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)
        metadata: dict = {}

        total_rows = 0
        for sub in SUB_PASOS:
            sql_path = DIRECTORIO_SQL / sub.sql_file
            if not sql_path.exists():
                result.status = StepStatus.FAILED
                result.error_message = f"Fallo en {sub.name}: SQL file no encontrado: {sql_path}"
                result.finished_at = datetime.utcnow()
                return result

            t0 = datetime.utcnow()
            try:
                if sub.por_lotes:
                    metadata = self._trocear_master(pg, sql_path)
                else:
                    pg.execute_sql_file(sql_path)
            except Exception as e:  # captura amplia a proposito: el nombre del sub-paso
                logger.error(
                    "descompuestos_substep_failed",
                    sub_step=sub.name,
                    duration_s=(datetime.utcnow() - t0).total_seconds(),
                    exc_info=True,
                )
                result.status = StepStatus.FAILED
                result.error_message = f"Fallo en {sub.name}: {e}"
                result.finished_at = datetime.utcnow()
                return result

            rows = 0
            if sub.target_schema and sub.target_table:
                rows = pg.count_rows(sub.target_schema, sub.target_table)
                total_rows += rows
            logger.info(
                "descompuestos_substep_done",
                sub_step=sub.name, rows=rows,
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )

        result.status = StepStatus.SUCCESS
        result.rows_processed = total_rows
        result.metadata = metadata
        result.finished_at = datetime.utcnow()
        return result

    def _trocear_master(self, pg: PostgresClient, sql_path: Path) -> dict:
        """Las versiones pendientes, por lotes y dentro del tope (R21)."""
        sello = sello_de_troceado()
        cod = cod_version_vigente(self._settings.business_rules)
        pendientes = [
            VersionPendiente(
                obra_id=int(f[0]), fase_num=int(f[1]), bytes=int(f[2]), es_vigente=bool(f[3])
            )
            for f in pg.filas_solo_lectura(sql_versiones_pendientes(sello, cod), TIMEOUT_LECTURA_S)
        ]
        plan = planificar_troceado(
            pendientes, self._settings.descompuestos.presupuesto_mb, self._sin_tope
        )
        texto = sql_path.read_text(encoding="utf-8")
        for numero, lote in enumerate(plan.lotes or ((),), start=1):
            t0 = datetime.utcnow()
            pg.execute_sql_text(componer_sql_lote(texto, lote, sello, cod))
            logger.info(
                "descompuestos_lote_troceado", lote=numero, versiones=len(lote),
                duration_s=round((datetime.utcnow() - t0).total_seconds(), 2),
            )
        if plan.aplazadas:
            logger.warning("descompuestos_troceado_aplazado", versiones=len(plan.aplazadas))
        return {
            "sello_troceado": sello,
            "versiones_troceadas": sum(len(lote) for lote in plan.lotes),
            "versiones_aplazadas": len(plan.aplazadas),
            "lotes": len(plan.lotes),
            "sin_tope": self._sin_tope,
        }
