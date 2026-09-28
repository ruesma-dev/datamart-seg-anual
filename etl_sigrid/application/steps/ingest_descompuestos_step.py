# etl_sigrid/application/steps/ingest_descompuestos_step.py
"""
Step que trae de Sigrid el texto de los descompuestos (`obrparpre.des`) a las
tablas de ESTADO del esquema `descompuestos` (F-097, D12).

**Por que no va en `config/tables_sigrid.yaml`.** La nocturna es `run-all
--full` y trunca todo `raw`: una entrada del YAML releeria cada noche los 2,14
GB de texto del master (65-94 minutos a 0,38-0,55 MB/s). El texto vive en
`descompuestos._des_texto`, que nadie trunca, y este paso lo mantiene de forma
INCREMENTAL por version. Tampoco toca la identidad de la ingesta ni la puerta de
F-024: la ingesta sigue en 71 tablas.

Cada noche, en este orden:

1. `00_setup.sql` (idempotente): el esquema y las dos tablas de estado.
2. **La huella de TODAS las versiones del master en UNA consulta** (R4): por
   `(obra, fase)`, `(filas, bytes, huella)` con la MISMA expresion que la
   medicion del 2026-09-27 (`progress/mediciones/F-097_huella_master.sql`), y
   la version vigente de cada obra (`conext`, cod de `business_rules.yaml`).
3. **El ambito 3 fase 0 entero** (R3), paginado por `ide`, en una sola
   sustitucion: borrado e insercion en la misma transaccion.
4. **El plan** (`domain.descompuestos.planificar_relectura`, R5-R7): nuevas,
   vigentes y de huella distinta, recortadas por el tope de MB
   (`DESCOMPUESTOS_PRESUPUESTO_MB`, 300) del que el ambito 3 consume primero;
   `--sin-tope` lo ignora (primera carga, MANUAL). Las que Sigrid ya no tiene
   se borran.
5. **Cada version en UNA transaccion** (R8, `PostgresClient.reemplazar_filas`):
   leida por `obride`, `amb = 8` y `fas` (indice `oaf` de Sigrid), paginada por
   `ide` de 1.000 en 1.000 (R10); si el recuento no es el de su huella, NO se
   escribe —queda la copia anterior—, se registra y se sigue con las demas; el
   paso termina `FAILED` al final (R9).

Todo lo que lee de Sigrid pasa por `SigridApiClient.leer_sql`, que rechaza lo
que no sea un `SELECT`. Lo que decide y lo que aplaza queda en el `metadata` del
resultado, que el grabador escribe en `_meta.etl_runs`.

**Un fallo de este paso SALTA `build_descompuestos`** (depende de el): R9 manda
terminar `FAILED` aunque falle una sola version. Lo construido la noche
anterior sigue publicado; `R-FRESCURA` avisa.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.descompuestos import (
    MB,
    ORDEN_DE_MOTIVOS,
    VersionCargada,
    VersionSigrid,
    cod_version_vigente,
    planificar_relectura,
)
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.postgres_client import FilaControl, PostgresClient
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
    SigridApiClient,
    SigridApiError,
)

logger = get_logger(__name__)

ESQUEMA = "descompuestos"
TABLA_TEXTO = "_des_texto"
TABLA_CONTROL = "_versiones_cargadas"
AMBITO_COSTE = 3
AMBITO_MASTER = 8

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "postgres" / "sql" / "descompuestos"
)
FICHERO_SETUP = "00_setup.sql"

#: Filas por pagina contra `sigrid-api` (R10): el limite documentado de la
#: pasarela. Una pagina del master pesa ~1,3 MB.
FILAS_POR_PAGINA = 1000

#: Segundos de la lectura de lo ya cargado (una tabla de ~3.000 filas).
TIMEOUT_LECTURA_S = 120

#: Las columnas de `descompuestos._des_texto`, en orden.
COLUMNAS_DES_TEXTO = (
    "presupuesto_id", "obra_id", "partida_id", "ambito_id", "fase_num",
    "cantidad", "precio", "haydes", "des", "batch_id",
)

_COLUMNAS_SIGRID = "ide, obride, paride, amb, fas, can, pre, haydes, des"

#: La huella de cada version con su vigente, en UNA consulta (R4). La expresion
#: de la huella es la de la medicion del 2026-09-27, caracter a caracter: T0 la
#: compara con aquella toma. SQL Server 2012: `HASHBYTES` admite 8.000 bytes,
#: asi que va el primer y el ultimo tramo, la longitud, `can` y `pre`.
SQL_HUELLA = (
    "SELECT h.obride, h.fas, h.filas, h.bytes, h.huella, v.vigente FROM ("
    "SELECT obride, fas, COUNT(*) filas, SUM(CAST(DATALENGTH(des) AS bigint)) bytes, "
    "CHECKSUM_AGG(CHECKSUM(ide, DATALENGTH(des), HASHBYTES('SHA2_256', "
    "SUBSTRING(CAST(des AS varchar(max)), 1, 8000)), HASHBYTES('SHA2_256', "
    "SUBSTRING(CAST(des AS varchar(max)), CASE WHEN DATALENGTH(des) > 8000 THEN "
    "DATALENGTH(des) - 7999 ELSE 1 END, 8000)), can, pre)) huella "
    "FROM obrparpre WHERE amb = 8 AND DATALENGTH(des) > 0 GROUP BY obride, fas) h "
    "LEFT JOIN (SELECT conide, MAX(valn) vigente FROM conext "
    "WHERE cod = ? AND valn IS NOT NULL GROUP BY conide) v ON v.conide = h.obride "
    "ORDER BY h.obride, h.fas"
)

#: El ambito 3 fase 0 con descompuesto, entero, paginado por `ide` (R3).
SQL_AMBITO_3 = (
    f"SELECT TOP {FILAS_POR_PAGINA} {_COLUMNAS_SIGRID} FROM obrparpre "
    "WHERE amb = 3 AND fas = 0 AND DATALENGTH(des) > 0 AND ide > ? ORDER BY ide"
)

#: Una version del master por el indice `oaf` (obride, amb, fas), paginada (R10).
SQL_VERSION = (
    f"SELECT TOP {FILAS_POR_PAGINA} {_COLUMNAS_SIGRID} FROM obrparpre "
    "WHERE obride = ? AND amb = 8 AND fas = ? AND DATALENGTH(des) > 0 AND ide > ? "
    "ORDER BY ide"
)

#: Lo ya cargado, con la huella que tenia Sigrid al cargarlo.
SQL_CARGADAS = (
    "SELECT obra_id, fase_num, filas, bytes, huella "
    "FROM descompuestos._versiones_cargadas"
)


class HuellaTruncada(RuntimeError):  # noqa: N818 - nombres en espanol
    """La huella volvio con tantas filas como el maximo pedido: puede faltar alguna."""


def abrir_api(settings: Settings) -> SigridApiClient:
    """El cliente de `sigrid-api`. Existe aparte para poder doblarlo en un test."""
    api = settings.sigrid_api
    return SigridApiClient(
        base_url=api.base_url,
        function_key=api.function_key.get_secret_value(),
        database=api.database,
        page_size=api.page_size,
        timeout_s=api.timeout_s,
        max_retries=api.max_retries,
    )


def leer_paginado(
    api: SigridApiClient,
    sql: str,
    parametros: Sequence[Any],
    *,
    filas_por_pagina: int = FILAS_POR_PAGINA,
) -> list[dict[str, Any]]:
    """Todas las filas de `sql`, pagina a pagina por `ide` (el ultimo `?`)."""
    filas: list[dict[str, Any]] = []
    ultimo = 0
    while True:
        respuesta = api.leer_sql(sql, [*parametros, ultimo], max_rows=filas_por_pagina)
        columnas = respuesta["columns"]
        pagina = respuesta["rows"]
        filas.extend(dict(zip(columnas, fila, strict=True)) for fila in pagina)
        if len(pagina) < filas_por_pagina:
            return filas
        siguiente = pagina[-1][columnas.index("ide")]
        if siguiente <= ultimo:
            raise RuntimeError(
                f"la paginacion por ide no avanza (ultimo {ultimo}, siguiente {siguiente})"
            )
        ultimo = siguiente


def leer_huellas(
    api: SigridApiClient, cod_vigente: str, max_filas: int
) -> tuple[list[VersionSigrid], dict[int, int]]:
    """La huella de cada version del master y la vigente de cada obra (R4)."""
    respuesta = api.leer_sql(SQL_HUELLA, [cod_vigente], max_rows=max_filas)
    filas = respuesta["rows"]
    if len(filas) >= max_filas:
        raise HuellaTruncada(
            f"la huella devolvio {len(filas)} filas, el maximo pedido: puede faltar "
            f"alguna version. Sube SIGRID_API_PAGE_SIZE por encima de {max_filas}"
        )
    columnas = respuesta["columns"]
    versiones: list[VersionSigrid] = []
    vigentes: dict[int, int] = {}
    for crudo in filas:
        fila = dict(zip(columnas, crudo, strict=True))
        versiones.append(
            VersionSigrid(
                obra_id=int(fila["obride"]),
                fase_num=int(fila["fas"]),
                filas=int(fila["filas"]),
                bytes=int(fila["bytes"]),
                huella=None if fila["huella"] is None else int(fila["huella"]),
            )
        )
        if fila["vigente"] is not None:
            vigentes[int(fila["obride"])] = int(fila["vigente"])
    return versiones, vigentes


def _a_texto(fila: Mapping[str, Any], batch_id: str | None) -> dict[str, Any]:
    """Una fila de `obrparpre` de Sigrid como fila de `descompuestos._des_texto`."""
    return {
        "presupuesto_id": fila["ide"],
        "obra_id": fila["obride"],
        "partida_id": fila["paride"],
        "ambito_id": fila["amb"],
        "fase_num": fila["fas"],
        "cantidad": fila["can"],
        "precio": fila["pre"],
        "haydes": fila["haydes"],
        "des": fila["des"],
        "batch_id": batch_id,
    }


class _FalloDeFase(Exception):  # noqa: N818 - nombres en espanol
    """Una fase del paso fallo; lleva su nombre para el mensaje (`Fallo en x:`)."""

    def __init__(self, fase: str, causa: Exception) -> None:
        super().__init__(f"Fallo en {fase}: {causa}")
        self.fase = fase


class IngestDescompuestosStep(PipelineStep):
    """Trae el `des` de Sigrid a `descompuestos._des_texto`, incremental por version."""

    def __init__(
        self,
        settings: Settings,
        *,
        sin_tope: bool = False,
        batch_id: str | None = None,
    ) -> None:
        self._settings = settings
        self._sin_tope = sin_tope
        self._batch_id = batch_id

    @property
    def name(self) -> str:
        return "ingest_descompuestos"

    @property
    def stage(self) -> str:
        return "ingest"

    @property
    def depends_on(self) -> list[str]:
        # Lee de Sigrid y escribe en su propio esquema: no necesita a nadie.
        return []

    def run(self) -> StepResult:
        result = self._new_result()
        pg = build_postgres_client(self._settings)
        try:
            self._fase("setup", pg.execute_sql_file, DIRECTORIO_SQL / FICHERO_SETUP)
            with abrir_api(self._settings) as api:
                metadata, filas, fallidas = self._ingerir(api, pg)
        except _FalloDeFase as e:
            logger.error("descompuestos_ingesta_fallida", fase=e.fase, error=str(e))
            result.status = StepStatus.FAILED
            result.error_message = str(e)
            result.finished_at = datetime.utcnow()
            return result

        result.rows_processed = filas
        result.metadata = metadata
        if fallidas:
            result.status = StepStatus.FAILED
            result.error_message = (
                f"{len(fallidas)} version(es) no se cargaron y conservan la copia "
                f"anterior: {'; '.join(fallidas)}"
            )
        else:
            result.status = StepStatus.SUCCESS
        result.finished_at = datetime.utcnow()
        return result

    @staticmethod
    def _fase(nombre: str, funcion, *args: Any, **kwargs: Any) -> Any:
        try:
            return funcion(*args, **kwargs)
        except Exception as e:  # captura amplia a proposito: el nombre de la fase
            raise _FalloDeFase(nombre, e) from e

    def _ingerir(
        self, api: SigridApiClient, pg: PostgresClient
    ) -> tuple[dict[str, Any], int, list[str]]:
        cod = self._fase("huella", cod_version_vigente, self._settings.business_rules)
        versiones, vigentes = self._fase(
            "huella", leer_huellas, api, cod, self._settings.sigrid_api.page_size
        )
        cargadas = [
            VersionCargada(
                obra_id=int(f[0]), fase_num=int(f[1]), filas=int(f[2]),
                bytes=int(f[3]), huella=None if f[4] is None else int(f[4]),
            )
            for f in self._fase("cargadas", pg.filas_solo_lectura, SQL_CARGADAS, TIMEOUT_LECTURA_S)
        ]

        ambito3 = self._fase("ambito_3", leer_paginado, api, SQL_AMBITO_3, [])
        escritas = self._fase(
            "ambito_3", pg.reemplazar_filas, ESQUEMA, TABLA_TEXTO, {"ambito_id": AMBITO_COSTE},
            COLUMNAS_DES_TEXTO, [_a_texto(f, self._batch_id) for f in ambito3],
        )
        bytes_ambito3 = sum(len(f["des"] or "") for f in ambito3)

        plan = self._fase(
            "plan", planificar_relectura, versiones, cargadas, vigentes,
            self._settings.descompuestos.presupuesto_mb, self._sin_tope,
            bytes_ya_usados=bytes_ambito3,
        )

        for obra, fase in plan.borrar:
            self._fase(
                "borrado", pg.reemplazar_filas, ESQUEMA, TABLA_TEXTO,
                {"obra_id": obra, "ambito_id": AMBITO_MASTER, "fase_num": fase},
                COLUMNAS_DES_TEXTO, [],
                FilaControl(schema=ESQUEMA, tabla=TABLA_CONTROL,
                            clave={"obra_id": obra, "fase_num": fase}, valores=None),
            )

        fallidas: list[str] = []
        releidas = 0
        for relectura in plan.releer:
            v = relectura.version
            etiqueta = f"{v.obra_id}/{v.fase_num}"
            try:
                filas = leer_paginado(api, SQL_VERSION, [v.obra_id, v.fase_num])
            except SigridApiError as e:
                fallidas.append(f"{etiqueta}: {e}")
                logger.error("descompuestos_version_ilegible", version=etiqueta, error=str(e))
                continue
            if len(filas) != v.filas:
                fallidas.append(f"{etiqueta}: Sigrid dio {len(filas)} filas y la huella dice {v.filas}")
                logger.error(
                    "descompuestos_version_no_cuadra", version=etiqueta,
                    filas_leidas=len(filas), filas_huella=v.filas,
                )
                continue
            escritas += self._fase(
                "versiones", pg.reemplazar_filas, ESQUEMA, TABLA_TEXTO,
                {"obra_id": v.obra_id, "ambito_id": AMBITO_MASTER, "fase_num": v.fase_num},
                COLUMNAS_DES_TEXTO, [_a_texto(f, self._batch_id) for f in filas],
                FilaControl(
                    schema=ESQUEMA, tabla=TABLA_CONTROL,
                    clave={"obra_id": v.obra_id, "fase_num": v.fase_num},
                    valores={
                        "filas": v.filas, "bytes": v.bytes, "huella": v.huella,
                        "batch_id": self._batch_id, "cargada_at": datetime.utcnow(),
                        "sello_troceado": None,
                    },
                ),
            )
            releidas += 1

        por_motivo = {m: sum(1 for r in plan.releer if r.motivo == m) for m in ORDEN_DE_MOTIVOS}
        metadata = {
            "filas_ambito_3": len(ambito3),
            "versiones_en_sigrid": len(versiones),
            "versiones_releidas": releidas,
            "releidas_por_motivo": por_motivo,
            "versiones_borradas": len(plan.borrar),
            "versiones_aplazadas": len(plan.aplazadas),
            "mb_aplazados": round(plan.bytes_aplazados / MB, 2),
            "mb_leidos": round((plan.bytes_releer + bytes_ambito3) / MB, 2),
            "versiones_fallidas": fallidas,
            "sin_tope": self._sin_tope,
        }
        logger.info("descompuestos_ingesta_hecha", **{k: v for k, v in metadata.items()
                                                       if k != "versiones_fallidas"})
        if plan.aplazadas:
            logger.warning(
                "descompuestos_versiones_aplazadas", versiones=len(plan.aplazadas),
                mb=metadata["mb_aplazados"],
            )
        return metadata, escritas, fallidas
