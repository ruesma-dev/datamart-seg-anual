# etl_sigrid/application/steps/apply_grants_step.py
"""
Step que reaplica los permisos de lectura del rol del MCP.

No es cosmético y no se puede saltar: las vistas de `mart`, `cierre`, `compras`
y `retenciones` se construyen con `DROP VIEW ... CASCADE` seguido de `CREATE`,
y un DROP se lleva por delante los GRANT. Sin este paso, el MCP deja de ver los
datos la primera noche que corre el ETL.

Dos comportamientos deliberados, ambos para que un problema de permisos no
tumbe el pipeline nocturno:

  - sin `PG_READONLY_ROLE` configurado (desarrollo local), el paso es un no-op
    que ni siquiera abre conexión;
  - si el rol está configurado pero no existe en el servidor, se avisa en el
    log y se termina en SUCCESS.

Desde F-068 este paso hace además lo contrario para unas pocas tablas: revoca
la lectura de `PG_EXCLUDED_TABLES` (hoy `raw.emp` y `raw.res`, datos personales
de empleados) después de conceder su esquema. Es TEMPORAL —el humano ya decidió
levantarlo cuando el MCP tenga control por usuario— y vive aquí precisamente
porque este paso corre cada noche: hecho a mano contra la base, el propio
`GRANT SELECT ON ALL TABLES IN SCHEMA raw` de este paso lo desharía.

Desde F-135 (2026-10-11) hace tres cosas más, en este orden:

  1. ANTES de abrir conexión, si un esquema está a la vez en la lista de
     consumo y en la de VETADOS (`PG_VETOED_SCHEMAS`: la contabilidad completa
     y `raw`), o si un esquema del rol autorizado no está vetado, termina en
     FAILED sin ejecutar nada. Es la guarda contra un `.env` viejo que aún
     liste `raw`: ya pasó con `personal`, y aquí reabriría la nómina en
     silencio.
  2. Tras los GRANT del rol general, le VETA esos esquemas (tablas, USAGE y
     privilegio por defecto) y concede la contabilidad completa al rol
     AUTORIZADO (`PG_RESTRICTED_ROLE`). Si ese rol no existe, avisa y sigue:
     su ausencia no expone nada.
  3. COMPRUEBA en el catálogo que el rol general no lee ningún esquema vetado
     ni tabla excluida. Si lee algo, FAILED con la lista: una concesión hecha
     a mano por otro concedente no la revoca la nocturna (la lección de
     F-068), y sin esta comprobación pasaría inadvertida.

Desde F-136 (2026-10-13) mira además el login de acceso TOTAL del MCP
(`PG_TOTAL_ROLE`), miembro del rol general y del autorizado:

  - ANTES de abrir conexión, FAILED si el total coincide con otro rol (R2) o si
    algún esquema que se le veta (`PG_TOTAL_VETOED_SCHEMAS`, `raw`) no está
    vetado al general o está en lo restringido o en el consumo (R3): lo
    heredaría por pertenencia.
  - NO le concede nada: lee por pertenencia. Tras las concesiones le VETA lo
    suyo, comprueba en el catálogo que no lo lee (FAILED con la lista, en el
    mismo mensaje que el general si los dos leen algo) y que llega a todo lo
    que debe (si no, solo aviso: leer de menos no expone nada).
  - Si el total no existe, avisa y sigue, como con el autorizado. La nocturna
    no puede darle las pertenencias (no tiene ADMIN OPTION): eso es
    `infra/sql/02_roles.sql`, punto 5 quater.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.grants import esquemas_en_conflicto

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import Settings
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)


class ApplyGrantsStep(PipelineStep):
    """Reaplica USAGE + SELECT del rol de solo lectura tras reconstruir las vistas."""

    def __init__(self, settings: Settings, client: PostgresClient | None = None) -> None:
        self._settings = settings
        # `client` existe para poder probar el paso sin BBDD. En producción es
        # None y el cliente lo construye la factoría.
        self._client = client

    @property
    def name(self) -> str:
        return "apply_grants"

    @property
    def stage(self) -> str:
        return "grants"

    @property
    def depends_on(self) -> list[str]:
        return ["build_mart"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg_settings = self._settings.postgres
        rol = (pg_settings.readonly_role or "").strip()

        if not rol:
            logger.info("apply_grants_sin_rol_configurado")
            result.status = StepStatus.SUCCESS
            result.rows_processed = 0
            result.metadata["motivo"] = "PG_READONLY_ROLE vacío: nada que aplicar"
            result.finished_at = datetime.utcnow()
            return result

        # F-068, y es TEMPORAL: `raw.emp` y `raw.res` traen datos personales de
        # empleados y el MCP no sabe todavía quién pregunta. El REVOKE viaja
        # AQUÍ, dentro del paso que corre cada noche, y no como una orden
        # suelta contra la base: una revocación a mano la deshace la primera
        # nocturna que pase. El porqué y la condición de reversión, en
        # `config/settings.py` (DEFAULT_EXCLUDED_TABLES).
        excluidas = list(pg_settings.excluded_table_list)
        consumo = list(pg_settings.consumption_schema_list)
        vetados = list(pg_settings.vetoed_schema_list)
        restringidos = list(pg_settings.restricted_schema_list)
        autorizado = (pg_settings.restricted_role or "").strip()
        dueno = (pg_settings.set_role or "").strip()

        # F-135, R17: una configuración contradictoria para ANTES de tocar nada
        conflicto = esquemas_en_conflicto(consumo, vetados)
        if conflicto:
            return self._fallo(
                result,
                f"PG_CONSUMPTION_SCHEMAS incluye esquemas vetados ({', '.join(conflicto)}): "
                "un .env viejo los reabriría al rol general. Quítalos de "
                "PG_CONSUMPTION_SCHEMAS (F-135); no se ha ejecutado nada.",
            )
        sin_vetar = [s for s in restringidos if s not in vetados]
        if sin_vetar:
            return self._fallo(
                result,
                f"PG_RESTRICTED_SCHEMAS tiene esquemas que no están en PG_VETOED_SCHEMAS "
                f"({', '.join(sin_vetar)}): el rol general podría leerlos (F-135); "
                "no se ha ejecutado nada.",
            )

        # F-136, R2: el login total no puede ser ninguno de los otros roles: le
        # vetaríamos `raw` al dueño, o le daríamos al general lo restringido.
        total = (pg_settings.total_role or "").strip()
        total_vetados = list(pg_settings.total_vetoed_schema_list)
        for variable, otro in (
            ("PG_READONLY_ROLE", rol),
            ("PG_RESTRICTED_ROLE", autorizado),
            ("PG_SET_ROLE", dueno),
        ):
            if total and total == otro:
                return self._fallo(
                    result,
                    f"PG_TOTAL_ROLE ('{total}') coincide con {variable}: el login total "
                    "tiene que ser un login propio (F-136); no se ha ejecutado nada.",
                )
        # F-136, R3: lo vetado al total, vetado también al general y fuera de lo
        # restringido y del consumo. Un `raw` añadido a lo restringido lo
        # heredaría el total por pertenencia sin que nadie lo viera.
        conflicto_total = [
            s for s in total_vetados
            if s in restringidos or s in consumo or s not in vetados
        ]
        if conflicto_total:
            return self._fallo(
                result,
                "PG_TOTAL_VETOED_SCHEMAS tiene esquemas que el login total heredaría "
                f"({', '.join(conflicto_total)}): cada uno tiene que estar en "
                "PG_VETOED_SCHEMAS y fuera de PG_RESTRICTED_SCHEMAS y de "
                "PG_CONSUMPTION_SCHEMAS (F-136); no se ha ejecutado nada.",
            )

        pg = self._client or build_postgres_client(self._settings)

        try:
            if not pg.role_exists(rol):
                logger.warning(
                    "apply_grants_rol_inexistente",
                    role=rol,
                    detalle="créalo con infra/sql/02_roles.sql",
                )
                result.status = StepStatus.SUCCESS
                result.rows_processed = 0
                result.metadata["motivo"] = f"el rol '{rol}' no existe en el servidor"
                result.finished_at = datetime.utcnow()
                return result

            sentencias = list(pg.apply_readonly_grants(
                readonly_role=rol,
                owner_role=dueno,
                schemas=consumo,
                excluded_tables=excluidas,
                vetoed_schemas=vetados,
            ))

            # F-135, R15: el rol autorizado. Sin él no se expone nada: se avisa.
            if not autorizado:
                estado_autorizado = "(sin configurar)"
            elif pg.role_exists(autorizado):
                sentencias += pg.apply_restricted_grants(autorizado, dueno, restringidos)
                estado_autorizado = autorizado
            else:
                logger.warning(
                    "apply_grants_rol_autorizado_inexistente",
                    role=autorizado,
                    detalle="créalo con infra/sql/02_roles.sql",
                )
                estado_autorizado = f"{autorizado} (no existe)"

            # F-136: el login TOTAL. Lee por pertenencia (al general y al
            # autorizado), así que NO se le concede nada: solo se le veta lo
            # suyo, DESPUÉS de las concesiones, y se pregunta al catálogo.
            indebidas_total: list[str] = []
            faltan_total: list[str] = []
            if not total:
                estado_total = "(sin configurar)"
            elif pg.role_exists(total):
                sentencias += pg.apply_veto(total, dueno, total_vetados)  # R7
                indebidas_total = pg.lecturas_indebidas(total, total_vetados, excluidas)  # R8
                faltan_total = pg.esquemas_sin_usage(total, consumo + restringidos)  # R10
                estado_total = total
            else:
                logger.warning(
                    "apply_grants_login_total_inexistente",
                    role=total,
                    detalle="créalo con infra/sql/02_roles.sql",
                )
                estado_total = f"{total} (no existe)"

            # F-135, R18: la postcondición, preguntada al catálogo
            indebidas = pg.lecturas_indebidas(rol, vetados, excluidas)
        except Exception as e:  # el resto del pipeline ya ha terminado bien
            logger.error("apply_grants_fallido", role=rol, error=str(e))
            result.status = StepStatus.FAILED
            result.error_message = str(e)
            result.finished_at = datetime.utcnow()
            return result

        result.metadata["esquemas"] = consumo
        result.metadata["tablas_excluidas"] = excluidas
        result.metadata["vetados"] = vetados
        result.metadata["rol_autorizado"] = estado_autorizado
        result.metadata["verificacion"] = indebidas or "ok"
        result.metadata["rol_total"] = estado_total
        if estado_total == total:
            result.metadata["verificacion_total"] = indebidas_total or "ok"
            result.metadata["acceso_total"] = faltan_total or "ok"
        else:
            result.metadata["verificacion_total"] = "no aplica"
            result.metadata["acceso_total"] = "no aplica"

        # F-136, R10 (D5): que el total lea DE MENOS no expone nada; se avisa.
        if faltan_total:
            logger.warning(
                "apply_grants_login_total_incompleto",
                role=total,
                faltan=faltan_total,
                detalle="le falta una pertenencia: punto 5 quater de infra/sql/02_roles.sql",
            )

        # F-135 R18 y F-136 R8-R9: un único FAILED que nombra a cada login con lo suyo
        motivos: list[str] = []
        if indebidas:
            motivos.append(
                f"el rol '{rol}' sigue leyendo lo vetado: {', '.join(indebidas)}. "
                "Es una concesión que esta nocturna no puede revocar (a PUBLIC, o de "
                "un concedente que no es el dueño): ejecuta el punto 5 ter de "
                "infra/sql/02_roles.sql y, si sigue, revoca la de PUBLIC (F-135, F-068)."
            )
        if indebidas_total:
            motivos.append(
                f"el login total '{total}' lee lo vetado: {', '.join(indebidas_total)}. "
                f"Tiene que ser miembro SOLO de '{rol}' y '{autorizado}' (punto 5 quater "
                "de infra/sql/02_roles.sql) y sin concesiones propias ni de PUBLIC "
                "(punto 5 ter) (F-136)."
            )
        if motivos:
            return self._fallo(result, " ".join(motivos))

        result.status = StepStatus.SUCCESS
        result.rows_processed = len(sentencias)
        result.finished_at = datetime.utcnow()
        return result

    @staticmethod
    def _fallo(result: StepResult, mensaje: str) -> StepResult:
        logger.error("apply_grants_fallido", error=mensaje)
        result.status = StepStatus.FAILED
        result.error_message = mensaje
        result.finished_at = datetime.utcnow()
        return result
