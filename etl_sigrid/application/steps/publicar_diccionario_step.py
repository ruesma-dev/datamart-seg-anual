# etl_sigrid/application/steps/publicar_diccionario_step.py
"""
Step que publica el diccionario semántico dentro de la propia base (F-006).

Es lo que convierte un YAML de este repositorio en algo que el servidor MCP
puede leer **por SQL**, igual que lee datos, sin conocer este proyecto. De ahí
que el multi-base salga gratis: cada base publicará su semántica en su propio
`_meta`.

Orden de las cosas dentro de `run()`, y ninguna es intercambiable:

  1. cargar los YAML y calcular el hash de la fuente;
  2. validar y derivar los avisos de cada ficha;
  3. evaluar la cobertura contra el inventario del repositorio;
  4. **si algo falla, terminar en FAILED sin haber abierto una sola conexión de
     escritura** (R19). El diccionario anterior se queda publicado intacto, que
     es mucho mejor que uno a medias: el MCP sigue respondiendo con la semántica
     de ayer en vez de inventársela;
  5. ejecutar el DDL idempotente, que crea las tablas la primera vez;
  6. reemplazar el contenido en UNA transacción.

`depends_on = ["build_mart"]` es formal: el diccionario **no depende de los
datos**. Es justo lo que permite la decisión DA-1 —publicarlo solo en `run-all`
y por comando suelto, y no al final de cada build manual—: publicar cinco veces
el mismo texto no añade nada y sí superficie de fallo.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.diccionario import derivar_avisos, formatear_errores, validar
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.domain.inventario import (
    evaluar_cobertura,
    formatear_cobertura,
    objetos_de_raw,
    objetos_de_sql,
)
from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
    DiccionarioIlegible,
    cargar_diccionario,
)
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.diccionario_sql import (
    fila_publicacion,
    resumen_publicacion,
)

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import Settings
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)

RAIZ = Path(__file__).resolve().parents[3]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DDL_DICCIONARIO = DIR_SQL / "ddl" / "01_diccionario.sql"
YAML_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"


class PublicarDiccionarioStep(PipelineStep):
    """Valida el diccionario y lo publica en `_meta`."""

    def __init__(
        self,
        settings: Settings,
        *,
        pasos_nocturnos: Sequence[str],
        client: PostgresClient | None = None,
        batch_id: str | None = None,
        directorio: Path | None = None,
    ) -> None:
        self._settings = settings
        # `pasos_nocturnos` se EXIGE, sin valor por defecto, y se inyecta desde
        # la composición del pipeline. Un default vacío haría que R14 diese por
        # mentirosa cualquier ficha `nocturno`; un default con la lista escrita
        # a mano se desincronizaría el día que `run-all` cambie. Las dos formas
        # de equivocarse quedan cerradas obligando a pasarlo.
        self._pasos_nocturnos = tuple(pasos_nocturnos)
        self._client = client
        self._batch_id = batch_id
        self._directorio = directorio or DIR_DICCIONARIO

    @property
    def name(self) -> str:
        return "publicar_diccionario"

    @property
    def stage(self) -> str:
        return "diccionario"

    @property
    def depends_on(self) -> list[str]:
        return ["build_mart"]

    @property
    def pasos_nocturnos(self) -> tuple[str, ...]:
        return self._pasos_nocturnos

    @pasos_nocturnos.setter
    def pasos_nocturnos(self, valor: Sequence[str]) -> None:
        """La composición del pipeline lo fija DESPUÉS de crear la lista.

        Es la única forma de que la lista salga de la propia composición y no
        de una copia: el paso no puede leerla al construirse porque en ese
        momento todavía se está construyendo el pipeline que la contiene.
        """
        self._pasos_nocturnos = tuple(valor)

    # -----------------------------------------------------------------
    # Ejecución
    # -----------------------------------------------------------------

    def run(self) -> StepResult:
        result = self._new_result()

        try:
            dicc, hash_fuente = cargar_diccionario(self._directorio)
        except DiccionarioIlegible as exc:
            return self._fallo(result, formatear_errores(exc.errores))

        errores = validar(dicc, self._pasos_nocturnos)
        if errores:
            return self._fallo(result, formatear_errores(errores))

        dicc = derivar_avisos(dicc)

        informe = evaluar_cobertura(dicc, self._inventario(), dicc.pendientes)
        if not informe.ok:
            return self._fallo(result, formatear_cobertura(informe))

        pg = self._client or build_postgres_client(self._settings)
        ahora = datetime.utcnow()

        try:
            # El DDL es idempotente y va ANTES de escribir: la primera
            # publicación de una base recién creada tiene que crear las tablas.
            pg.execute_sql_file(DDL_DICCIONARIO)
            filas = pg.publicar_diccionario(
                dicc,
                hash_fuente=hash_fuente,
                informe=informe,
                batch_id=self._batch_id,
                ahora=ahora,
            )
        except Exception as exc:
            # R21: el build de datos NO se deshace. `mart` queda construido y el
            # diccionario anterior sigue publicado; esto es una noticia, no una
            # catástrofe, y `run-all` sale con código 1 para que alguien mire.
            logger.error("publicar_diccionario_fallido", error=str(exc))
            return self._fallo(result, str(exc))

        result.status = StepStatus.SUCCESS
        result.rows_processed = filas
        result.metadata.update(
            resumen_publicacion(
                fila_publicacion(dicc, hash_fuente, ahora, self._batch_id, informe)
            )
        )
        result.finished_at = datetime.utcnow()
        logger.info("diccionario_publicado_ok", filas=filas, **result.metadata)
        return result

    # -----------------------------------------------------------------

    def _inventario(self):
        """Los objetos que este repositorio publica, leídos de sus ficheros."""
        import yaml

        textos = {
            str(ruta.relative_to(DIR_SQL)).replace("\\", "/"): ruta.read_text(
                encoding="utf-8"
            )
            for ruta in DIR_SQL.rglob("*.sql")
        }
        tablas = yaml.safe_load(YAML_TABLAS.read_text(encoding="utf-8"))["tables"]
        return objetos_de_sql(textos) + objetos_de_raw(tablas)

    def _fallo(self, result: StepResult, mensaje: str) -> StepResult:
        result.status = StepStatus.FAILED
        result.error_message = mensaje
        result.finished_at = datetime.utcnow()
        return result
