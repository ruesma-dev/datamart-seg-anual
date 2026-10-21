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

Desde F-141 (2026-10-17) mira además el perfil RESTRINGIDO del MCP, para
administrativos, que ve MENOS que el estándar: un grupo NOLOGIN con los permisos
(`PG_PERFIL_RESTRINGIDO_GROUP`) y un login miembro (`PG_PERFIL_RESTRINGIDO_LOGIN`).
Regla del humano: «ven como el estándar, menos el mayor, menos el mayor
analítico, menos la cartera de cobros (pero sí a retenciones)», y «personal
también quítalo, y saldos cuenta también». Desde F-146 (2026-10-21), nada de
`contabilidad`: el esquema salió de `PG_PERFIL_RESTRINGIDO_SCHEMAS` y se le veta
entero como cualquier esquema ajeno, sin código nuevo en este paso.

  - ANTES de abrir conexión, FAILED si `PG_RESTRICTED_ROLE` trae el nombre que
    F-141 retiró al renombrar el grupo autorizado (R3), si el grupo o el login
    coinciden con otro rol (R4), si sus esquemas no son del consumo o están
    vetados o restringidos (R5), si falta `_meta` (R6), si un objeto excluido
    está mal escrito (R7) o si leería los adjuntos sin sus documentos (R8).
  - Su bloque es el ÚLTIMO y no cambia nada de lo anterior. Le concede lo suyo
    con el privilegio por defecto en REVOKE; le veta todo esquema del CATÁLOGO
    que no sea suyo; busca las vistas que, vista sobre vista, leen lo que no ve
    (salvo `raw` y las tres vistas de pago de `compras`, excepciones nominales de
    D4) y los objetos con «mayor» en el nombre sin excluir (el mayor analítico
    de F-127): se los REVOCA y termina en FAILED, porque son la alarma. Luego
    pregunta al catálogo si el grupo o el login leen algo de lo que no deben y si
    el login es miembro de algo más que su grupo: FAILED en el mismo mensaje que
    el estándar y el total. Las pertenencias las da el punto 5 quinquies de
    `infra/sql/02_roles.sql`.
  - Grupo vacío: nada. Grupo, login o una excepción que ya no lee la cartera:
    avisa y sigue, como un login al que le falta lectura.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from config.settings import DEFAULT_RESTRICTED_ROLE, NOMBRE_AUTORIZADO_RETIRADO
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client
from etl_sigrid.infrastructure.postgres.grants import (
    ESQUEMAS_ORIGEN_DE_VISTAS,
    OBJETO_ADJUNTOS,
    PATRON_VIGILADO_RESTRINGIDO,
    esquemas_ajenos,
    esquemas_en_conflicto,
    excluidas_invalidas,
    origenes_de_adjuntos_sin_leer,
    perfil_restringido_en_conflicto,
    separar_excepciones,
)

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import Settings
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)

#: El esquema sin el cual el MCP no tiene diccionario (F-141, R6).
ESQUEMA_DICCIONARIO = "_meta"

#: La `metadata` del perfil restringido que vale «no aplica» si no se mira (R9-R10).
CLAVES_RESTRINGIDO = (
    "login_restringido",
    "verificacion_restringido",
    "filtraciones_restringido",
    "vigilados_restringido",
    "pertenencias_restringido",
    "acceso_restringido",
    "excepciones_sobrantes",
)


@dataclass(frozen=True, slots=True)
class _PerfilRestringido:
    """La configuración del perfil RESTRINGIDO (F-141) y lo que se hace con ella."""

    grupo: str
    login: str
    esquemas: list[str]
    excluidas: list[str]

    @classmethod
    def desde(cls, pg_settings: Any) -> _PerfilRestringido:
        grupo = (getattr(pg_settings, "perfil_restringido_group", "") or "").strip()
        if not grupo:
            return cls("", "", [], [])
        return cls(
            grupo=grupo,
            login=(pg_settings.perfil_restringido_login or "").strip(),
            esquemas=list(pg_settings.perfil_restringido_schema_list),
            excluidas=list(pg_settings.perfil_restringido_excluded_table_list),
        )

    def guarda(
        self,
        *,
        otros_roles: Sequence[tuple[str, str]],
        consumo: Sequence[str],
        vetados: Sequence[str],
        restringidos: Sequence[str],
        total_vetados: Sequence[str],
    ) -> str:
        """El motivo para parar ANTES de abrir conexión (R4-R8), o vacío si no hay."""
        if not self.grupo:
            return ""
        # R4: roles propios. Uno vacío no coincide con nada.
        propios = (
            ("PG_PERFIL_RESTRINGIDO_GROUP", self.grupo, otros_roles),
            ("PG_PERFIL_RESTRINGIDO_LOGIN", self.login,
             (*otros_roles, ("PG_PERFIL_RESTRINGIDO_GROUP", self.grupo))),
        )
        for variable, valor, contra in propios:
            for otra, otro in contra:
                if valor and valor == otro:
                    return (
                        f"{variable} ('{valor}') coincide con {otra}: el perfil restringido "
                        "necesita un grupo y un login propios"
                    )
        # R5: nada que el estándar no lea, ni nada vetado o restringido
        conflicto = perfil_restringido_en_conflicto(
            self.esquemas, consumo=consumo, vetados=vetados,
            restringidos=restringidos, total_vetados=total_vetados,
        )
        if conflicto:
            return (
                "PG_PERFIL_RESTRINGIDO_SCHEMAS tiene esquemas que el perfil restringido no "
                f"puede leer ({', '.join(conflicto)}): cada uno tiene que estar en "
                "PG_CONSUMPTION_SCHEMAS y fuera de PG_VETOED_SCHEMAS, PG_RESTRICTED_SCHEMAS "
                "y PG_TOTAL_VETOED_SCHEMAS"
            )
        # R6: sin `_meta` el MCP no explica nada
        if ESQUEMA_DICCIONARIO not in self.esquemas:
            return (
                f"PG_PERFIL_RESTRINGIDO_SCHEMAS no incluye {ESQUEMA_DICCIONARIO}: el MCP no "
                "tendría diccionario para el perfil restringido"
            )
        # R7: una exclusión que no apunta a nada protegido es una errata
        malas = excluidas_invalidas(self.excluidas, self.esquemas)
        if malas:
            return (
                "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES tiene objetos mal escritos o de un "
                f"esquema que no se le concede ({', '.join(malas)}): cada uno es "
                "'esquema.tabla' de PG_PERFIL_RESTRINGIDO_SCHEMAS"
            )
        # R8: F-139 D1, los adjuntos solo con sus documentos de origen
        sin_origen = origenes_de_adjuntos_sin_leer(self.esquemas, self.excluidas)
        if sin_origen:
            return (
                f"el perfil restringido leería {OBJETO_ADJUNTOS} sin sus documentos de "
                f"origen ({', '.join(sin_origen)}): excluye también {OBJETO_ADJUNTOS} o "
                "concédele esas tablas (F-139, D1)"
            )
        return ""

    def aplicar(self, pg: Any, dueno: str) -> _BloqueRestringido:
        """El bloque nocturno del perfil (R9-R18). Siempre el ÚLTIMO, tras el total."""
        if not self.grupo:
            return _BloqueRestringido.no_aplica("(sin configurar)")
        if not pg.role_exists(self.grupo):
            logger.warning(
                "apply_grants_restringido_inexistente",
                role=self.grupo,
                detalle="créalo con infra/sql/02_roles.sql",
            )
            return _BloqueRestringido.no_aplica(f"{self.grupo} (no existe)")

        # R18: sin login se comprueba solo el grupo (no expone nada: nadie conecta)
        if not self.login:
            login, estado_login = "", "(sin configurar)"
        elif pg.role_exists(self.login):
            login, estado_login = self.login, self.login
        else:
            logger.warning(
                "apply_grants_restringido_login_inexistente",
                role=self.login,
                detalle="créalo con infra/sql/02_roles.sql",
            )
            login, estado_login = "", f"{self.login} (no existe)"

        # R12: lo que no es suyo sale del CATÁLOGO, no de la configuración
        ajenos = esquemas_ajenos(pg.list_schemas(), self.esquemas)
        # R13 (D10): vistas que leen lo que no ve, salvo `raw` y las tres de D4
        objetivo = [e for e in ajenos if e not in ESQUEMAS_ORIGEN_DE_VISTAS]
        filtraciones, sobrantes = separar_excepciones(
            pg.vistas_que_filtran(self.esquemas, objetivo, self.excluidas)
        )
        # R14: el mayor analítico de F-127, si nace con «mayor» y sin excluir
        vigilados = [
            o for o in pg.objetos_vigilados(self.esquemas, PATRON_VIGILADO_RESTRINGIDO)
            if o not in self.excluidas
        ]
        revocar = list(dict.fromkeys(
            [*self.excluidas, *(vista for vista, _ in filtraciones), *vigilados]
        ))
        # R11-R12: lo suyo (con los REVOKE al final) y el veto de lo ajeno
        sentencias = list(pg.apply_perfil_restringido(self.grupo, dueno, self.esquemas, revocar))
        sentencias += pg.apply_veto(self.grupo, dueno, ajenos)

        # R16: la postcondición, preguntada al catálogo para el grupo y el login
        indebidas: dict[str, list[str]] = {}
        for quien in (self.grupo, login):
            if quien:
                leidas = pg.lecturas_indebidas(quien, ajenos, revocar)
                if leidas:
                    indebidas[quien] = leidas
        # R17: el login solo es miembro de su grupo; el grupo, de nadie
        pertenencias = [f"{login} -> {g}" for g in (pg.pertenencias(login) if login else [])
                        if g != self.grupo]
        pertenencias += [f"{self.grupo} -> {g}" for g in pg.pertenencias(self.grupo)]
        faltan = pg.esquemas_sin_usage(login or self.grupo, self.esquemas)

        if sobrantes:  # R15: no expone nada, pero la lista nominal miente
            logger.warning(
                "apply_grants_restringido_excepcion_sobrante",
                role=self.grupo,
                excepciones=sobrantes,
                detalle="ya no leen la cartera: quítalas de EXCEPCIONES_FILTRACION_RESTRINGIDO",
            )
        if faltan:  # R18: leer de menos no expone nada
            logger.warning(
                "apply_grants_restringido_incompleto",
                role=login or self.grupo,
                faltan=faltan,
                detalle="le falta la pertenencia o el GRANT: punto 5 quinquies de "
                        "infra/sql/02_roles.sql",
            )

        filtran = [f"{vista} -> {objeto}" for vista, objeto in filtraciones]
        motivos: list[str] = []
        if filtran:
            motivos.append(
                f"el perfil restringido '{self.grupo}' leería por vistas lo que no ve: "
                f"{', '.join(filtran)}. Ya se le han revocado; quita esa lectura de la "
                "vista, exclúyela en PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES o, si el humano "
                "lo decide, añádela a las excepciones de D4 (F-141)."
            )
        if vigilados:
            motivos.append(
                f"el perfil restringido '{self.grupo}' tiene objetos con «mayor» en el "
                f"nombre sin excluir: {', '.join(vigilados)}. Ya se le han revocado; si son "
                "el mayor analítico (F-127), añádelos a PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES "
                "(F-141)."
            )
        for quien, leidas in indebidas.items():
            motivos.append(
                f"el perfil restringido '{quien}' lee lo que no debe: {', '.join(leidas)}. "
                "Es una concesión que esta nocturna no puede revocar (a PUBLIC, o de un "
                "concedente que no es el dueño): ejecuta el punto 5 quinquies de "
                "infra/sql/02_roles.sql y, si sigue, revoca la de PUBLIC (F-141)."
            )
        if pertenencias:
            motivos.append(
                f"pertenencias indebidas del perfil restringido: {', '.join(pertenencias)}. "
                f"El login solo puede ser miembro de '{self.grupo}', y el grupo de ninguno "
                "(punto 5 quinquies de infra/sql/02_roles.sql) (F-141)."
            )
        return _BloqueRestringido(
            sentencias=sentencias,
            metadata={
                "rol_restringido": self.grupo,
                "login_restringido": estado_login,
                "verificacion_restringido": indebidas or "ok",
                "filtraciones_restringido": filtran or "ok",
                "vigilados_restringido": vigilados or "ok",
                "pertenencias_restringido": pertenencias or "ok",
                "acceso_restringido": faltan or "ok",
                "excepciones_sobrantes": sobrantes or "ok",
            },
            motivos=motivos,
        )


@dataclass(frozen=True, slots=True)
class _BloqueRestringido:
    """Lo que deja el bloque del perfil restringido: sentencias, `metadata` y motivos de FAILED."""

    sentencias: list[str]
    metadata: dict[str, Any]
    motivos: list[str]

    @classmethod
    def no_aplica(cls, estado: str) -> _BloqueRestringido:
        metadata: dict[str, Any] = {"rol_restringido": estado}
        metadata.update(dict.fromkeys(CLAVES_RESTRINGIDO, "no aplica"))
        return cls(sentencias=[], metadata=metadata, motivos=[])


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

        # F-141, R3: el nombre que F-141 retiró. Con un `.env` viejo el
        # autorizado «no existiría» y el total perdería las `*_restringida`
        # tras el primer DROP nocturno, con solo un aviso: se para aquí.
        if autorizado == NOMBRE_AUTORIZADO_RETIRADO:
            return self._fallo(
                result,
                f"PG_RESTRICTED_ROLE vale '{autorizado}', el nombre que F-141 retiró: el "
                f"grupo autorizado se llama ahora '{DEFAULT_RESTRICTED_ROLE}' (renombrado "
                "por infra/sql/02_roles.sql). Corrige el .env; no se ha ejecutado nada.",
            )

        # F-141, R4-R8: la configuración del perfil restringido. Sin grupo no
        # se mira (R9); `getattr` porque una configuración anterior a F-141 no
        # lo trae, y eso es exactamente «sin configurar».
        perfil = _PerfilRestringido.desde(pg_settings)
        error = perfil.guarda(
            otros_roles=(
                ("PG_READONLY_ROLE", rol),
                ("PG_RESTRICTED_ROLE", autorizado),
                ("PG_TOTAL_ROLE", total),
                ("PG_SET_ROLE", dueno),
            ),
            consumo=consumo,
            vetados=vetados,
            restringidos=restringidos,
            total_vetados=total_vetados,
        )
        if error:
            return self._fallo(result, f"{error} (F-141); no se ha ejecutado nada.")

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

            # F-141: el perfil RESTRINGIDO, el ÚLTIMO. No toca lo de antes: sus
            # sentencias van solo a su grupo, y sus fallos se suman al mensaje.
            restringido = perfil.aplicar(pg, dueno)
            sentencias += restringido.sentencias
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
        result.metadata.update(restringido.metadata)

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
        motivos += restringido.motivos  # F-141, R19: en el mismo mensaje, detrás
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
