# etl_sigrid/infrastructure/postgres/postgres_client.py
"""
Cliente Postgres del ETL. Responsabilidades:

  1. Auto-bootstrap perezoso: la primera vez que cualquier método toca Postgres,
     se asegura de que la BBDD existe (la crea si no), los schemas están creados,
     y la tabla _meta.etl_runs existe. El usuario no tiene que ejecutar nada
     manualmente.
  2. Conectarse con psycopg 3.
  3. Crear dinámicamente tablas raw.* a partir de la metadata de Sigrid
     (CREATE TABLE IF NOT EXISTS con tipos derivados de INFORMATION_SCHEMA).
  4. Cargar masivamente con COPY FROM STDIN (10-100x más rápido que INSERT).
  5. Soportar carga incremental (cursor sobre MAX(ide) ya cargado).

Toda la mecánica está encapsulada aquí. Los Steps de la capa application no
saben de psycopg, solo invocan métodos limpios.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Json

from etl_sigrid.domain.coherencia import EstadoPaso, EstadoTablaRaw
from etl_sigrid.domain.ejecucion import MOTIVO_HUERFANA
from etl_sigrid.domain.entities import ColumnSpec
from etl_sigrid.domain.perfil_carga import FilaPerfil
from etl_sigrid.domain.tiemod import COLUMNA_TIEMOD, EstadoTiemod
from etl_sigrid.domain.ventana import ObraCensada
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.conninfo import safe_dsn
from etl_sigrid.infrastructure.postgres.fingerprint import build_estructura_query
from etl_sigrid.infrastructure.postgres.frescura import FilaFrescura
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements
from etl_sigrid.infrastructure.postgres.timings import Timing

logger = get_logger(__name__)


# Schemas del data mart
SCHEMAS = ("raw", "aux", "stg", "mart", "_meta")

# Cuántas mediciones devolver cuando no hay un arranque de `ingest_raw` al que
# anclarse. Evita volcar el histórico entero de _meta.etl_runs.
TIMINGS_SIN_ANCLA = 100

# Una cadena de conexión, o algo que la produzca. Es callable porque con
# autenticación Entra la "contraseña" es un token que caduca y hay que
# resolverlo en cada conexión, no una vez al arrancar.
ConnInfo = str | Callable[[], str]


# --- Troceo y puerta de disco del build de plan_mensual (F-019) -------------

# Gigabyte binario: es la unidad en la que Azure declara el disco del Flexible
# Server (64 GB desde el 2026-08-29; 32 antes) y en la que se compara
# `PG_DISCO_TOTAL_GB`. El tamaño no se cablea aquí: lo dice esa variable.
BYTES_POR_GB = 1024 * 1024 * 1024

# Ocupación del disco del SERVIDOR, no de nuestra base: el disco es compartido
# con otros CINCO inquilinos —`albaranes`, `partes`, `dedicacion`, `postventa`
# y `facturas`—, y lo que hay que vigilar es el total.
#
# `pg_database_size` sobre otra base exige normalmente privilegio CONNECT, y
# durante un año el rol del ETL lo tuvo sobre todas las que había (frontera
# medida en F-005). Dejó de ser verdad sin que nadie nos avisara: el 2026-09-07
# apareció `facturas`, con dueño propio (`facturas_owner`) y sin CONNECT para
# nosotros, y la nocturna murió justo aquí —«permission denied for database
# facturas»— sin llegar al tramo 1 y sin tocar una tabla; está contado en
# progress/incidencia_nocturna_20260907.md.
#
# La frontera de hoy YA NO es CONNECT. El 2026-09-07 el humano concedió a
# `sigrid_dm_etl` el rol predefinido `pg_read_all_stats`, que permite
# `pg_database_size` sobre CUALQUIER base sin CONNECT y sin dar acceso a sus
# datos, y que además cubre las bases que se creen en el futuro: eso es lo que
# de verdad falló, que la lista de inquilinos crece sola. Verificado ese mismo
# día: `pg_has_role('sigrid_dm_etl','pg_read_all_stats','member')` devuelve `t`
# y esta consulta devuelve las nueve bases del servidor.
#
# No cuenta WAL ni logs del servidor: ese hueco lo absorbe el margen entre el
# límite (80 %) y la protección de Azure (~95 %).
SQL_OCUPACION_DISCO = "SELECT SUM(pg_database_size(datname)) FROM pg_database"

# Peso de cada obra = filas de raw.obrparpre que le tocan, ponderando la rama
# master por el número de posiciones de su `planif`, que es lo que de verdad
# explota el CROSS JOIN LATERAL. Las filas de reales (amb 3/7) no se explotan:
# pesan una. Es una agregación sin ventanas, así que no derrama como el build.
SQL_PESOS_PLAN_MENSUAL = """
SELECT
    pp.obra_id,
    SUM(
        CASE
            WHEN pp.ambito_id IN (8, 11)
                THEN COALESCE(
                    cardinality(
                        string_to_array(NULLIF(TRIM(op.planif), ''), '|')
                    ),
                    0
                )
            ELSE 1
        END
    )::BIGINT AS peso
FROM stg.presupuesto pp
JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
WHERE pp.ambito_id IN (3, 7, 8, 11)
GROUP BY pp.obra_id
"""


# --- La ventana de negocio (F-025) ------------------------------------------
#
# Las consultas van como constantes de módulo, igual que las de F-019 y F-024,
# para que los tests estáticos lean EXACTAMENTE el SQL que se envía y no una
# reconstrucción parecida.

# EL CENSO. Una fila por obra con todo lo que hace falta para decidir sobre
# ella. Se une a `_meta.obra_build` por la IZQUIERDA: una obra que nunca se ha
# construido sale igual, con el registro a nulo, y entra por R18. Un INNER JOIN
# la escondería, que es justo el silencio que esta feature elimina.
#
# EL UNIVERSO ES `raw.obr JOIN raw.con`, la misma definición de obra que usa
# `maestro.obras` (`c.ide = o.ide`: la obra ES un concepto). Se replica aquí en
# vez de leer la vista por dos razones: `maestro.obras` la construye
# `build_maestros`, que en `run-all` va DESPUÉS de este build, y en una base
# recién creada todavía no existe. Leyendo `raw` no hay dependencia de orden y
# el estado es el de la ingesta de esta misma noche.
#
# `stg.fases` sí está recién construida cuando esto se ejecuta: `05_fases.sql`
# va antes que `06_presupuesto.sql`, que es el primer sub-paso acotado.
#
# LOS DOS `EXISTS` SON BARATOS, y esa es la razón de que sean `EXISTS` y no un
# `GROUP BY`: `idx_plan_mensual_obra_amb` e `idx_pres_obra_amb` empiezan los
# dos por `obra_id` (verificado contra `pg_indexes` el 2026-09-02), así que
# Postgres resuelve cada uno con una sonda de índice por obra y se para en la
# primera fila. Contar las filas de cada obra habría costado dos barridos de
# 29 M y 13,8 M de filas en un servidor sin créditos de CPU.
SQL_ESTADO_OBRAS = """
SELECT
    c.ide                                   AS obra_id,
    COALESCE(TRIM(c.cod), '')               AS codigo_obra,
    c.est                                   AS estado_id,
    ult.ultima_actividad                    AS ultima_actividad,
    EXISTS (SELECT 1 FROM stg.plan_mensual pm WHERE pm.obra_id = c.ide)
                                            AS tiene_plan_mensual,
    EXISTS (SELECT 1 FROM stg.presupuesto  p WHERE p.obra_id  = c.ide)
                                            AS tiene_presupuesto,
    (b.obra_id IS NOT NULL)                 AS registrada,
    b.sello_sql                             AS sello_registrado,
    b.firma_origen                          AS firma_registrada,
    b.firma_actual                          AS firma_actual
FROM raw.obr o
JOIN raw.con c ON c.ide = o.ide
LEFT JOIN LATERAL (
    SELECT MAX(make_date(f.anio, GREATEST(f.mes, 1), 1)) AS ultima_actividad
    FROM stg.fases f
    WHERE f.obra_id = c.ide
      AND f.anio BETWEEN 1990 AND 2100
) ult ON TRUE
LEFT JOIN _meta.obra_build b ON b.obra_id = c.ide
ORDER BY c.ide
"""

# LA FIRMA DEL ORIGEN, sobre `raw` (R16, §3.2 del diseño). `raw` es lo único
# que la ingesta sigue trayendo COMPLETO cada noche (R34), y por eso es la
# única señal posible una vez que `stg.presupuesto` deja de reconstruirse
# entera (DA-2).
#
# AQUÍ SOLO SE AGREGA: el hash lo calcula `domain.ventana.firma_de_obra`. No es
# manía de capas, es lo que hace la firma testable con fixtures y lo que la
# pone bajo la campaña de mutación de DA-6.
#
# ES UNA AGREGACIÓN POR HASH, SIN VENTANAS, y eso importa: no derrama a
# ficheros temporales, que es lo que llenó el disco compartido en F-019. Y
# sustituye a un paso que hoy lee esta misma tabla y ADEMÁS escribe 13,8 M de
# filas.
#
# LA VARIANTE BARATA (R20): no incluye `planif`, que es un texto largo en 13,8
# M de filas y habría que detoastar entero. La laguna que deja —un cambio de
# planificación pura que no mueva ninguna cantidad ni ningún precio— queda
# declarada en el diccionario y la cierra la reconstrucción del domingo (R25).
# La variante cara es `SQL_FIRMA_ORIGEN_CON_PLANIF`, aquí abajo, y la mide T2b.
SQL_FIRMA_ORIGEN = """
WITH pre AS (
    SELECT pp.obride                             AS obra_id,
           count(*)                              AS pre_filas,
           sum(pp.can::NUMERIC)                  AS pre_suma_can,
           sum(pp.pre::NUMERIC)                  AS pre_suma_pre,
           sum(COALESCE(pp.impcoe::NUMERIC, 0))  AS pre_suma_impcoe,
           max(pp.fas)                           AS pre_max_fase,
           max(pp.ide)                           AS pre_max_ide
    FROM raw.obrparpre pp
    WHERE pp.obride IS NOT NULL
    GROUP BY 1
), par AS (
    SELECT pa.obride    AS obra_id,
           count(*)     AS par_filas,
           max(pa.ide)  AS par_max_ide
    FROM raw.obrparpar pa
    WHERE pa.obride IS NOT NULL
    GROUP BY 1
), fas AS (
    SELECT fa.obride    AS obra_id,
           count(*)     AS fas_filas,
           max(fa.ide)  AS fas_max_ide,
           max(COALESCE(fa.ano, 0) * 100 + COALESCE(fa.mes, 0)) AS fas_max_periodo
    FROM raw.obrfas fa
    WHERE fa.obride IS NOT NULL
    GROUP BY 1
)
SELECT o.ide AS obra_id,
       pre.pre_filas, pre.pre_suma_can, pre.pre_suma_pre, pre.pre_suma_impcoe,
       pre.pre_max_fase, pre.pre_max_ide,
       par.par_filas, par.par_max_ide,
       fas.fas_filas, fas.fas_max_ide, fas.fas_max_periodo
FROM raw.obr o
LEFT JOIN pre ON pre.obra_id = o.ide
LEFT JOIN par ON par.obra_id = o.ide
LEFT JOIN fas ON fas.obra_id = o.ide
ORDER BY o.ide
"""

#: Los nombres de las columnas de agregado de `SQL_FIRMA_ORIGEN`, sin
#: `obra_id`. Entran en el hash **por nombre** (ver `firma_de_obra`), así que
#: esta tupla es parte del contrato: cambiarla cambia la firma de las 920 obras
#: y provoca una reconstrucción completa la primera noche. Que sea así es lo
#: correcto —el significado de la firma ha cambiado—, pero conviene saberlo
#: antes de tocarla.
COLUMNAS_FIRMA_ORIGEN = (
    "pre_filas",
    "pre_suma_can",
    "pre_suma_pre",
    "pre_suma_impcoe",
    "pre_max_fase",
    "pre_max_ide",
    "par_filas",
    "par_max_ide",
    "fas_filas",
    "fas_max_ide",
    "fas_max_periodo",
)

# LA VARIANTE CARA (R20, T2b). **No se ejecuta**: vive aquí para que el humano
# pueda medir su coste sin volver a escribir el SQL, y para que la diferencia
# entre las dos esté a la vista en un solo sitio.
#
# `planif` es el texto que `08_plan_mensual.sql` explota con `unnest`, así que
# es lo único que cierra la laguna de la variante barata. El precio es
# detoastar un texto largo en 13,8 M de filas sobre un B1ms con techo de
# 10 MiB/s. Si T2b lo declara asumible, sustituye a `SQL_FIRMA_ORIGEN`; si no,
# la laguna se queda declarada y la cierra el domingo.
SQL_FIRMA_ORIGEN_CON_PLANIF = """
SELECT pp.obride AS obra_id,
       count(*) AS pre_filas,
       md5(string_agg(COALESCE(pp.planif, ''), chr(10) ORDER BY pp.ide)) AS pre_planif
FROM raw.obrparpre pp
WHERE pp.obride IS NOT NULL
GROUP BY 1
ORDER BY 1
"""

# LA ÚLTIMA RECONSTRUCCIÓN COMPLETA (R25). Sale de `_meta.etl_runs` y no de una
# tabla nueva, para que `python main.py timings` la vea como un paso más y para
# que sobreviva a una obra que aparezca o desaparezca del maestro, que es lo
# que rompería derivarla de un `MIN(construido_at)` sobre `_meta.obra_build`.
SQL_ULTIMA_COMPLETA = """
SELECT MAX(finished_at)
FROM _meta.etl_runs
WHERE step = %(paso)s AND status = 'SUCCESS'
"""

# EL REGISTRO POR OBRA (R14). Upsert: una fila por obra, la última manda.
#
# `firma_actual` NO se toca aquí —la escribe el sub-paso de la firma, tras la
# ingesta— y `firma_origen` se fija al valor que tenía el origen CUANDO se
# construyó la obra. Que sean dos columnas distintas es lo que permite comparar
# «de qué es el dato» contra «qué hay ahora en el origen»: con una sola, la
# ingesta pisaría la referencia cada noche y la comparación no diría nada.
SQL_REGISTRAR_OBRA = """
INSERT INTO _meta.obra_build (
    obra_id, codigo_obra, firma_origen, sello_sql,
    batch_id, construido_at, filas, congelada, motivo, detalle
)
VALUES (
    %(obra_id)s, %(codigo_obra)s, %(firma_origen)s, %(sello_sql)s,
    %(batch_id)s, %(construido_at)s, %(filas)s, FALSE, %(motivo)s, %(detalle)s
)
ON CONFLICT (obra_id) DO UPDATE SET
    codigo_obra   = EXCLUDED.codigo_obra,
    firma_origen  = EXCLUDED.firma_origen,
    sello_sql     = EXCLUDED.sello_sql,
    batch_id      = EXCLUDED.batch_id,
    construido_at = EXCLUDED.construido_at,
    filas         = EXCLUDED.filas,
    congelada     = FALSE,
    motivo        = EXCLUDED.motivo,
    detalle       = EXCLUDED.detalle
"""

# LA MARCA DE LA DECISIÓN SOBRE UNA OBRA CONGELADA. Se escriben el motivo y el
# detalle, pero **NO `construido_at` ni `filas`**: esta noche no se ha
# construido nada de esa obra, y mover su fecha sería mentir sobre la frescura,
# que es justamente el dato por el que existe `_meta.v_frescura_obra`.
SQL_MARCAR_CONGELADA = """
INSERT INTO _meta.obra_build (obra_id, codigo_obra, congelada, motivo, detalle)
VALUES (%(obra_id)s, %(codigo_obra)s, TRUE, %(motivo)s, %(detalle)s)
ON CONFLICT (obra_id) DO UPDATE SET
    codigo_obra = EXCLUDED.codigo_obra,
    congelada   = TRUE,
    motivo      = EXCLUDED.motivo,
    detalle     = EXCLUDED.detalle
"""

# LA FIRMA DE ESTA NOCHE, escrita por el sub-paso que va tras la ingesta.
SQL_REGISTRAR_FIRMA_ACTUAL = """
INSERT INTO _meta.obra_build (obra_id, firma_actual, firma_actual_at)
VALUES (%(obra_id)s, %(firma_actual)s, %(firma_actual_at)s)
ON CONFLICT (obra_id) DO UPDATE SET
    firma_actual    = EXCLUDED.firma_actual,
    firma_actual_at = EXCLUDED.firma_actual_at
"""

#: Las dos tablas que la ventana acota. El nombre se valida contra esta tupla
#: antes de interpolarlo en `SQL_OBRAS_CON_FILAS`: es la única interpolación de
#: identificador de todo el bloque y no puede depender de la buena fe de quien
#: llame.
TABLAS_ACOTADAS = ("plan_mensual", "presupuesto")

# OBRAS QUE HOY TIENEN FILAS. Solo se consulta en la reconstrucción completa, y
# solo para NOMBRAR las que no están en el censo (ver `fetch_obras_con_filas`:
# no se borran). Va por `DISTINCT` sobre el índice —del orden de 700 valores
# distintos— y no por un `NOT IN` sobre la tabla entera, que sería un barrido
# de 29 M de filas cada domingo.
SQL_OBRAS_CON_FILAS = "SELECT DISTINCT obra_id FROM stg.{tabla}"

# CUÁNTAS FILAS HA DEJADO CADA OBRA EN EL TRAMO (R14). Alimenta la columna
# `filas` de `_meta.obra_build`, que es lo que permite responder «esta obra se
# construyó y salió vacía» sin volver a barrer la tabla.
#
# El `WHERE` NO es decoración: sin él esto sería un `GROUP BY` sobre 29,7 M de
# filas cada noche en un servidor sin créditos de CPU. Se cuenta SOLO lo que se
# acaba de construir —decenas de obras—, que además es lo único de lo que se va
# a escribir la traza. Las obras van por parámetro (`= ANY`); el nombre de tabla
# es la segunda y última interpolación de identificador del bloque, y se valida
# contra `TABLAS_ACOTADAS` igual que `SQL_OBRAS_CON_FILAS`.
SQL_FILAS_POR_OBRA = """
SELECT obra_id, COUNT(*)
FROM stg.{tabla}
WHERE obra_id = ANY(%(obras)s)
GROUP BY obra_id
"""


def _exigir_tabla_acotada(tabla: str) -> None:
    """Corta antes de interpolar un nombre de tabla que venga de fuera.

    Lo comparten las dos consultas que interpolan identificador
    (`SQL_OBRAS_CON_FILAS` y `SQL_FILAS_POR_OBRA`) para que la lista blanca sea
    una sola y no dos copias que puedan divergir.
    """
    if tabla not in TABLAS_ACOTADAS:
        raise ValueError(
            f"tabla no acotada por la ventana: {tabla!r}. Las unicas son "
            f"{', '.join(TABLAS_ACOTADAS)}, y este nombre se interpola en el "
            f"SQL: no puede venir de fuera."
        )

# --- Coherencia ante cargas truncadas (F-024) -------------------------------
#
# Las consultas van como constantes de módulo, igual que `SQL_OCUPACION_DISCO`,
# para que los tests estáticos lean EXACTAMENTE el SQL que se envía. Ninguna se
# ejecuta con parámetros salvo la primera: `LIKE 'build_stg%'` lleva un `%` que
# psycopg tomaría por marcador si hubiera parámetros que sustituir.

# Cierra de una vez todas las filas que dejó abiertas un proceso muerto. NO
# filtra por antigüedad (toda `RUNNING` que exista al arrancar es de otro
# proceso, por definición) ni por batch (las nuestras aún no existen). El
# `WHERE status = 'RUNNING'` es lo único que separa esto de reescribir el
# histórico entero, incluidos los SUCCESS de las cargas buenas.
SQL_ABORTAR_HUERFANOS = """
UPDATE _meta.etl_runs
SET status        = 'ABORTED',
    finished_at   = %(ahora)s,
    error_message = %(motivo)s
WHERE status = 'RUNNING'
RETURNING id, step, started_at
"""

# De qué carga viene cada tabla de raw. Se lee de la VISTA y no de `etl_runs`
# para que la puerta, `check-coherencia`, el MCP y Power BI vean exactamente lo
# mismo: una sola definición de «última ingesta», en el DDL.
SQL_ESTADO_RAW = """
SELECT tabla, status, batch_id, started_at, finished_at, filas
FROM _meta.v_raw_state
ORDER BY tabla
"""

# El último intento de construir stg. Por `id` DESC y no por fecha: la fila de
# PASO se inserta al TERMINAR el step, y su `started_at` es el del arranque,
# anterior al de todos sus sub-pasos. Ordenando por fecha, un stage terminado
# devolvería su último tramo y la puerta de mart lo tomaría por incompleto.
SQL_ULTIMO_INTENTO_STG = """
SELECT id, step, status, batch_id, started_at, finished_at
FROM _meta.etl_runs
WHERE step LIKE 'build_stg%'
ORDER BY id DESC
LIMIT 1
"""

SQL_FRESCURA = """
SELECT paso,
       ultimo_ok_finished_at,
       ultimo_ok_batch_id,
       ultimo_ok_filas,
       horas_desde_ultimo_ok,
       ultimo_intento_started_at,
       ultimo_intento_status,
       ultimo_intento_error
FROM _meta.v_frescura
ORDER BY paso
"""

# --- Perfil de carga (F-011, R1-R3) -----------------------------------------
#
# SOLO LECTURA y sobre `_meta.etl_runs` y nada más: es el «medir antes de
# optimizar» de F-011, y no hace falta ejecutar ninguna carga nueva para
# responderlo, porque cada tabla ya deja su fila `ingest_raw.<tabla>` desde
# F-024.
#
# El ancla es la ÚLTIMA carga con `batch_id`, elegida por `ORDER BY batch_id
# DESC`: el identificador de F-024 es UTC compacto, así que ordena
# cronológicamente sin parsear nada (fue una decisión explícita de esa
# feature). Y se ancla a `step = 'ingest_raw'` porque es el primer paso de
# `run-all`: así el perfil sale de una carga de verdad y no de un
# `apply-grants` suelto que se ejecutó después.
SQL_PERFIL_CARGA = """
SELECT stage, step, started_at, finished_at, status, rows_processed, batch_id
FROM _meta.etl_runs
WHERE batch_id = COALESCE(
        %(batch)s,
        (SELECT batch_id
         FROM _meta.etl_runs
         WHERE step = 'ingest_raw' AND batch_id IS NOT NULL
         ORDER BY batch_id DESC
         LIMIT 1)
      )
ORDER BY started_at, id
"""

# --- Diagnóstico de `tiemod` (F-011, R6-R7) ---------------------------------
#
# SOLO LECTURA sobre `raw`. Responde si la marca de modificación de Sigrid
# sirve como watermark **sin volver a leer Sigrid**: sus valores ya están
# guardados en `_source_tiemod`, carga tras carga, desde que existe
# `copy_rows(tiemod_column=...)`.
#
# El COUNT(DISTINCT) no es gratis —obliga a recorrer la tabla entera— y por eso
# esto es un comando que se lanza a mano, no un paso del pipeline.
SQL_TABLAS_CON_TIEMOD = """
SELECT table_name
FROM information_schema.columns
WHERE table_schema = 'raw' AND column_name = %(columna)s
ORDER BY table_name
"""

#: Plantilla: la tabla y la columna se interpolan con `psycopg.sql.Identifier`,
#: nunca por concatenación. Va como constante para que un test pueda leer
#: exactamente el SQL que se envía, igual que hace F-024.
SQL_DIAGNOSTICO_TIEMOD = """
SELECT COUNT(*)                                  AS filas,
       COUNT(*) FILTER (WHERE {col} IS NULL)     AS nulos,
       MIN({col})                                AS minimo,
       MAX({col})                                AS maximo,
       COUNT(DISTINCT {col})                     AS distintos
FROM raw.{tabla}
"""

#: Filas cuya marca supera la de la fotografía anterior. Es la traducción
#: operativa de «cuántas filas cambiaron» de R7: si `tiemod` es una marca de
#: modificación, toda fila tocada desde la foto anterior está por encima de su
#: máximo. Si no lo es, este recuento sale 0, que es justo la señal de NO SIRVE.
SQL_FILAS_DESDE_TIEMOD = "SELECT COUNT(*) FROM raw.{tabla} WHERE {col} > %(umbral)s"

SQL_RUN_START = """
INSERT INTO _meta.etl_runs (stage, step, started_at, status, batch_id)
VALUES (%s, %s, %s, 'RUNNING', %s)
RETURNING id
"""

SQL_RUN_COMPLETED = """
INSERT INTO _meta.etl_runs
    (stage, step, started_at, finished_at, status,
     rows_processed, error_message, metadata, batch_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""


def _float_o_none(valor: Any) -> float | None:
    """Convierte a `float` respetando el nulo de SQL.

    Existe para que cada columna se lea con su propio valor y no con el índice
    de la de al lado: `MIN` y `MAX` de la misma columna son nulos a la vez, así
    que confundirlos no lo detecta ningún dato posible. Con el helper, la
    confusión ni se puede escribir.
    """
    return None if valor is None else float(valor)


def porcentaje_ocupacion(bytes_usados: int, total_gb: int) -> float:
    """Ocupación del disco en tanto por ciento, con el total en GB binarios.

    La validación mira `total_gb` y no los bytes ya calculados: es el valor que
    de verdad configura el humano (`PG_DISCO_TOTAL_GB`), y así el mensaje habla
    de lo que hay que corregir.
    """
    if total_gb <= 0:
        raise ValueError(
            f"PG_DISCO_TOTAL_GB debe ser un entero positivo, y vale {total_gb}. "
            f"Sin tamaño de disco no hay puerta de seguridad que valga."
        )
    return bytes_usados * 100.0 / (total_gb * BYTES_POR_GB)


class PostgresClient:
    """
    Cliente Postgres con auto-bootstrap perezoso.

    Constructor:
        conninfo       : conexión a la BBDD del data mart (ej. sigrid_dm)
        admin_conninfo : conexión a una BBDD admin existente (ej. postgres) para
                         poder hacer CREATE DATABASE si la nuestra no existe
        target_db      : nombre de la BBDD a crear si no existe
        auto_create_db : si es False, NUNCA se ejecuta CREATE DATABASE ni se
                         abre conexión contra la BBDD admin; la base tiene que
                         existir ya. Es lo obligatorio contra el servidor
                         compartido de Azure, donde viven albaranes y partes.
        set_role       : rol de grupo al que hacer SET ROLE al abrir cada
                         sesión, para que todos los objetos tengan el mismo
                         propietario conecte quien conecte.
    """

    def __init__(
        self,
        conninfo: ConnInfo,
        admin_conninfo: ConnInfo,
        target_db: str,
        *,
        auto_create_db: bool = True,
        set_role: str | None = None,
    ) -> None:
        self._conninfo = conninfo
        self._admin_conninfo = admin_conninfo
        self._target_db = target_db
        self._auto_create_db = auto_create_db
        self._set_role = (set_role or "").strip()
        self._bootstrap_done = False

    # ---------------------------------------------------------------------
    # Conexión (con auto-bootstrap)
    # ---------------------------------------------------------------------

    @staticmethod
    def _resolve(conninfo: ConnInfo) -> str:
        """Resuelve la cadena de conexión (puede venir de un proveedor callable)."""
        return conninfo() if callable(conninfo) else conninfo

    def _connect(self, conninfo: ConnInfo, *, autocommit: bool = False) -> psycopg.Connection:
        """
        Abre una conexión y le aplica `SET ROLE` como PRIMERA sentencia de la
        sesión (R7). Todo el cliente pasa por aquí: si alguna ruta se saltara
        el SET ROLE, crearía objetos con otro propietario y el siguiente
        proceso no podría recrearlos.
        """
        conn = psycopg.connect(self._resolve(conninfo), autocommit=autocommit)
        if self._set_role:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("SET ROLE {}").format(sql.Identifier(self._set_role))
                    )
            except Exception:
                conn.close()
                raise
        return conn

    @contextmanager
    def connection(self) -> psycopg.Connection:
        """
        Context manager que abre y cierra una conexión psycopg.
        En la primera llamada de la vida del cliente, ejecuta auto-bootstrap
        (crea BBDD si no existe, crea schemas, crea _meta.etl_runs).
        """
        if not self._bootstrap_done:
            self._auto_bootstrap()
            self._bootstrap_done = True

        conn = self._connect(self._conninfo)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_connectivity(self) -> str:
        """
        Smoke test: garantiza que la BBDD existe y devuelve la versión de Postgres.
        Si la BBDD no existe, la crea automáticamente (con sus schemas).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            return row[0] if row else "unknown"

    # ---------------------------------------------------------------------
    # Bootstrap automático
    # ---------------------------------------------------------------------

    def _auto_bootstrap(self) -> None:
        """
        Idempotente. Asegura:
          1. La BBDD `target_db` existe (la crea si no, y solo si
             `auto_create_db`; contra Azure la crea el humano una vez).
          2. Los schemas (raw, aux, stg, mart, _meta) existen.
          3. La tabla _meta.etl_runs existe.
        """
        if self._auto_create_db:
            created = self._ensure_database()
            if created:
                logger.info("postgres_db_created", db=self._target_db)
            else:
                logger.debug("postgres_db_already_exists", db=self._target_db)
        else:
            self._assert_database_reachable()

        self._bootstrap_schemas_and_meta()
        logger.debug("postgres_bootstrap_done", schemas=list(SCHEMAS))

    def _assert_database_reachable(self) -> None:
        """
        Con `auto_create_db=False` no se toca la BBDD admin ni se crea nada
        (R9): lo único que se hace es comprobar que la base ya existe abriendo
        una conexión contra ella. Si no responde, el mensaje remite al script de
        provisión y al runbook en vez de intentar crearla (R10).
        """
        try:
            conn = self._connect(self._conninfo)
        except psycopg.OperationalError as e:
            raise RuntimeError(
                f"No puedo conectar a la BBDD '{self._target_db}' y "
                f"PG_AUTO_CREATE_DB=false, así que NO se intenta crearla: este "
                f"servidor puede estar compartido con otras bases en producción. "
                f"Créala con infra/sql/01_create_database.sql y sus roles con "
                f"infra/sql/02_roles.sql, siguiendo docs/runbook_postgres_azure.md. "
                f"Conexión usada: {safe_dsn(self._resolve(self._conninfo))}. "
                f"Detalle: {e}"
            ) from e
        conn.close()

    def _ensure_database(self) -> bool:
        """
        Comprueba si la BBDD existe consultando pg_database via la BBDD admin.
        Si no existe, la crea. Devuelve True si fue creada, False si ya existía.

        CREATE DATABASE no puede ejecutarse dentro de una transacción, por eso
        usamos autocommit=True para esta conexión administrativa.
        """
        try:
            admin_conn = self._connect(self._admin_conninfo, autocommit=True)
        except psycopg.OperationalError as e:
            raise RuntimeError(
                f"No puedo conectar a la BBDD admin para verificar/crear "
                f"'{self._target_db}'. Comprueba que el servidor Postgres está "
                f"accesible y que la BBDD admin existe (variable PG_ADMIN_DB, "
                f"por defecto 'postgres'). Detalle: {e}"
            ) from e

        try:
            with admin_conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (self._target_db,),
                )
                if cur.fetchone() is not None:
                    return False

                # No existe: la creamos
                cur.execute(
                    sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8'").format(
                        sql.Identifier(self._target_db)
                    )
                )
                return True
        finally:
            admin_conn.close()

    def _bootstrap_schemas_and_meta(self) -> None:
        """Crea los schemas y la tabla _meta.etl_runs si no existen. Idempotente."""
        ddl_path = Path(__file__).parent / "sql" / "ddl" / "00_meta.sql"
        with ddl_path.open(encoding="utf-8") as f:
            ddl_meta = f.read()

        conn = self._connect(self._conninfo)
        try:
            with conn.cursor() as cur:
                for schema in SCHEMAS:
                    cur.execute(
                        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                            sql.Identifier(schema)
                        )
                    )
                cur.execute(ddl_meta)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def force_bootstrap(self) -> None:
        """
        Fuerza el bootstrap aunque ya se haya hecho (idempotente igualmente).
        Útil para el comando CLI 'bootstrap' si el usuario quiere reejecutarlo.
        """
        self._auto_bootstrap()
        self._bootstrap_done = True

    # ---------------------------------------------------------------------
    # DDL dinámico de tablas raw
    # ---------------------------------------------------------------------

    def ensure_raw_table(
        self,
        target_table: str,
        columns: list[ColumnSpec],
        *,
        primary_key: str = "ide",
    ) -> None:
        """
        Crea la tabla raw.<target_table> si no existe, con los tipos derivados
        de la metadata de Sigrid. Añade dos columnas técnicas:
            _ingested_at   TIMESTAMP   cuándo se cargó la fila en Postgres
            _source_tiemod DOUBLE PRECISION  valor de tiemod de Sigrid (NULL si no existe)
        Si la tabla ya existe, no la toca.
        """
        if not columns:
            raise ValueError(f"Sin columnas para crear raw.{target_table}")

        col_definitions = []
        for c in columns:
            null_clause = "NULL" if c.is_nullable else "NOT NULL"
            col_definitions.append(
                sql.SQL("{} {} {}").format(
                    sql.Identifier(c.name),
                    sql.SQL(c.postgres_type),
                    sql.SQL(null_clause),
                )
            )

        # Columnas técnicas
        col_definitions.append(sql.SQL("_ingested_at TIMESTAMP NOT NULL DEFAULT NOW()"))
        col_definitions.append(sql.SQL("_source_tiemod DOUBLE PRECISION NULL"))

        # PK si la columna existe en la lista
        pk_clause = sql.SQL("")
        if any(c.name == primary_key for c in columns):
            pk_clause = sql.SQL(", PRIMARY KEY ({})").format(sql.Identifier(primary_key))

        ddl = sql.SQL("CREATE TABLE IF NOT EXISTS raw.{} ({}{})").format(
            sql.Identifier(target_table),
            sql.SQL(", ").join(col_definitions),
            pk_clause,
        )

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(ddl)

        logger.info(
            "raw_table_ready",
            table=f"raw.{target_table}",
            columns=len(columns),
            pk=primary_key,
        )

    def table_exists(self, schema: str, table: str) -> bool:
        """Devuelve True si la tabla existe en el schema dado."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                (schema, table),
            )
            return cur.fetchone() is not None

    def get_table_columns(self, schema: str, table: str) -> list[str]:
        """
        Devuelve la lista ordenada de nombres de columnas de una tabla.

        Útil para validación previa antes de ejecutar SQL que asume ciertas
        columnas. Si la tabla no existe, devuelve [].
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            )
            return [row[0] for row in cur.fetchall()]

    def assert_columns_exist(
        self,
        schema: str,
        table: str,
        required_columns: list[str],
    ) -> None:
        """
        Verifica que `required_columns` están todas presentes en `schema.table`.
        Si falta alguna, lanza ValueError con un mensaje claro que indica:
          - qué columnas faltan
          - qué columnas SÍ tiene la tabla (para facilitar el diagnóstico)

        Llamar al inicio de un Step evita fallos a mitad de transformación con
        mensajes crípticos. Es el patrón "fail fast".
        """
        if not self.table_exists(schema, table):
            raise ValueError(
                f"La tabla {schema}.{table} no existe. "
                f"¿Has ejecutado el step de ingesta previo?"
            )

        actual = set(self.get_table_columns(schema, table))
        required = set(required_columns)
        missing = required - actual
        if missing:
            raise ValueError(
                f"Columnas faltantes en {schema}.{table}: "
                f"{sorted(missing)}. "
                f"Columnas presentes: {sorted(actual)}. "
                f"Posibles causas: (1) la columna se llama distinto en tu Sigrid; "
                f"(2) está en exclude_columns del YAML; (3) Sigrid ha cambiado el esquema."
            )

    def get_max_id(self, schema: str, table: str, id_column: str = "ide") -> int:
        """Devuelve el MAX(id_column) de la tabla. 0 si está vacía o no existe."""
        if not self.table_exists(schema, table):
            return 0
        query = sql.SQL("SELECT COALESCE(MAX({}), 0) FROM {}.{}").format(
            sql.Identifier(id_column),
            sql.Identifier(schema),
            sql.Identifier(table),
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def truncate_table(self, schema: str, table: str) -> None:
        """TRUNCATE de la tabla. Útil para full-refresh."""
        query = sql.SQL("TRUNCATE TABLE {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
        logger.info("table_truncated", table=f"{schema}.{table}")

    def count_rows(self, schema: str, table: str) -> int:
        """COUNT(*) de la tabla."""
        if not self.table_exists(schema, table):
            return 0
        query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    # ---------------------------------------------------------------------
    # Huella de las vistas de consumo
    # ---------------------------------------------------------------------

    def list_view_columns(self, schemas: Iterable[str]) -> list[tuple]:
        """
        Columnas de todas las VISTAS de los esquemas dados:
        (esquema, vista, posición, columna, tipo), en orden estable.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(build_estructura_query(list(schemas)))
            return list(cur.fetchall())

    def fetch_aggregates(self, query: str) -> tuple:
        """
        Ejecuta una consulta de agregados de una sola fila y devuelve sus
        valores. La consulta la construye `fingerprint.build_agregado_query`,
        que cita los identificadores; aquí no se concatena nada.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            fila = cur.fetchone()
            return tuple(fila) if fila else ()

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        """Ejecuta un `SELECT` de diagnóstico y devuelve sus filas (F-042).

        La transacción va **`READ ONLY`** con su `statement_timeout`, las dos con
        `SET LOCAL`: acotadas a esta transacción, sin tocar la configuración de un
        servidor que comparten `albaranes` y `partes` en producción. Si el texto
        intentara escribir, lo rechaza el motor, no la buena voluntad de quien lo
        construyó.

        Existe una sola vez y la usan `check-cierres` y `huella-obras` porque la
        alternativa era que cada uno abriera su conexión y emitiera sus propias
        sentencias previas. Ahí es donde una de las dos copias se deja el
        `transaction_read_only` un martes por la tarde.
        """
        from etl_sigrid.infrastructure.postgres.unicidad_sql import (
            sentencias_previas,
        )

        with self.connection() as conn:
            try:
                with conn.cursor() as cur:
                    for previa in sentencias_previas(timeout_s):
                        cur.execute(previa)
                    cur.execute(sql_text)
                    filas = list(cur.fetchall())
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return filas

    def comprobar_unicidad(
        self, consulta, timeout_s: int
    ) -> tuple[int, int] | str | None:
        """Ejecuta UNA comprobación de unicidad (F-006, T26).

        Devuelve `(claves_duplicadas, filas_implicadas)`, o **`None` si la
        consulta agotó el `statement_timeout`**. Ese `None` no es un cero: es
        «no lo sabemos», y quien lo reciba tiene que reportarlo como NO
        COMPROBADO. Contarlo como correcto convertiría el límite de tiempo
        —que está para no ahogar un servidor compartido con `albaranes` y
        `partes`— en una forma de aprobar sin mirar.

        La transacción va `READ ONLY` y el `statement_timeout` es `SET LOCAL`,
        así que ni escribe ni cambia la configuración del servidor.
        """
        import psycopg

        from etl_sigrid.infrastructure.postgres.unicidad_sql import (
            sentencias_previas,
        )

        # NO se toca `autocommit`: `self.connection()` devuelve una conexion que
        # ya viene EN TRANSACCION (`INTRANS`), y cambiarlo ahi revienta con
        # `can't change 'autocommit' now`. Paso de verdad al ejecutar T26 contra
        # la base: el doble no lo reprodujo porque en el `autocommit` era un
        # atributo normal. Es justo lo que un doble no puede garantizar, y por
        # eso hacia falta la ejecucion real.
        with self.connection() as conn:
            try:
                with conn.cursor() as cur:
                    for previa in sentencias_previas(timeout_s):
                        cur.execute(previa)
                    cur.execute(consulta.sql)
                    fila = cur.fetchone()
                conn.commit()
            except psycopg.errors.QueryCanceled:
                conn.rollback()
                return None
            except psycopg.errors.UndefinedTable:
                # El objeto esta fichado y NO existe en la base. No es un fallo
                # del chequeo: es el hallazgo. Paso de verdad con
                # `cierre.v_pbi_planif_vs_real`, que el repositorio crea y la
                # base no tiene porque `build-cierre` no se ha vuelto a lanzar.
                conn.rollback()
                return "NO_EXISTE"
            except Exception:
                conn.rollback()
                raise
        if fila is None:
            return (0, 0)
        return (int(fila[0]), int(fila[1]))

    def comprobar_relacion(
        self, consulta, timeout_s: int
    ) -> tuple[int, int] | str | None:
        """Ejecuta UNA comprobación de relación (F-006, T40).

        Devuelve `(valores_muestreados, valores_que_casan)`, **`None` si la
        consulta agotó el `statement_timeout`** y `"NO_EXISTE"` si falta en la
        base alguno de los dos extremos o la columna. Los tres desenlaces se
        distinguen porque exigen cosas distintas de quien los lea: «la relación
        no une» se arregla en la ficha, «no he podido comprobarlo» se vuelve a
        lanzar, y «eso no está en la base» significa que falta un build.

        `UndefinedColumn` va junto a `UndefinedTable` porque es el caso que de
        verdad aparece cuando la base va por detrás del árbol: el objeto está y
        la columna todavía no. Sin capturarlo, una sola relación reventaría el
        barrido entero.

        Mismas dos sentencias previas que `comprobar_unicidad`, y las emite el
        cliente: la transacción va `READ ONLY` y el `statement_timeout` es `SET
        LOCAL`, así que ni escribe ni toca la configuración del servidor, que
        comparten `albaranes` y `partes` en producción.
        """
        import psycopg

        from etl_sigrid.infrastructure.postgres.unicidad_sql import (
            sentencias_previas,
        )

        # NO se toca `autocommit`: `self.connection()` devuelve la conexion ya
        # EN TRANSACCION (`INTRANS`) y cambiarlo ahi revienta. Mismo motivo,
        # mismo comentario y misma cicatriz que en `comprobar_unicidad`.
        with self.connection() as conn:
            try:
                with conn.cursor() as cur:
                    for previa in sentencias_previas(timeout_s):
                        cur.execute(previa)
                    cur.execute(consulta.sql)
                    fila = cur.fetchone()
                conn.commit()
            except psycopg.errors.QueryCanceled:
                conn.rollback()
                return None
            except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
                conn.rollback()
                return "NO_EXISTE"
            except Exception:
                conn.rollback()
                raise
        if fila is None:
            return (0, 0)
        return (int(fila[0]), int(fila[1]))

    def fetch_hash_publicado(self) -> tuple[str, str] | None:
        """`(version, hash_fuente)` de lo que hay publicado, o `None` si no hay.

        Es lo que permite detectar que **lo publicado ya no es lo del
        repositorio**, que es como se quedo `_meta` sirviendo un grano que T26
        habia demostrado falso: la ficha se corrigio y no se republico.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT version, hash_fuente FROM _meta.diccionario_publicacion"
            )
            fila = cur.fetchone()
            return (str(fila[0]), str(fila[1])) if fila else None

    # ---------------------------------------------------------------------
    # Permisos del rol de solo lectura
    # ---------------------------------------------------------------------

    def role_exists(self, role: str) -> bool:
        """True si el rol existe en el servidor."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            return cur.fetchone() is not None

    def list_schemas(self) -> list[str]:
        """Esquemas que existen realmente en la BBDD."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            return [row[0] for row in cur.fetchall()]

    def apply_readonly_grants(
        self,
        readonly_role: str,
        owner_role: str,
        schemas: Iterable[str],
    ) -> list[str]:
        """
        Reaplica los permisos de lectura y devuelve las sentencias ejecutadas.

        Solo se conceden permisos sobre los esquemas que existen: `run-all` no
        construye `cierre`, `compras`, `maestro` ni `retenciones` (van en
        comandos aparte), así que en una base recién creada esos esquemas
        pueden no estar todavía. Intentarlo daría error y tumbaría el paso por
        algo que no es un problema.
        """
        existentes = set(self.list_schemas())
        pedidos = list(schemas)
        aplicables = [s for s in pedidos if s in existentes]
        ausentes = [s for s in pedidos if s not in existentes]
        if ausentes:
            logger.warning("grants_esquemas_inexistentes", schemas=ausentes)

        sentencias = build_readonly_grant_statements(
            readonly_role, owner_role, aplicables, database=self._target_db
        )
        if not sentencias:
            return []

        with self.connection() as conn, conn.cursor() as cur:
            for stmt in sentencias:
                cur.execute(stmt)

        logger.info(
            "grants_aplicados",
            role=readonly_role,
            schemas=aplicables,
            statements=len(sentencias),
        )
        return sentencias

    # ---------------------------------------------------------------------
    # Diccionario semántico (F-006)
    # ---------------------------------------------------------------------

    def publicar_diccionario(
        self,
        dicc,
        *,
        hash_fuente: str,
        informe,
        batch_id: str | None = None,
        ahora: datetime | None = None,
    ) -> int:
        """Reemplaza el diccionario publicado y devuelve las filas escritas.

        TODO ocurre dentro de UNA transacción, y esa es la garantía que el
        contrato con `mcp-bbdd` le debe a quien consulte mientras se publica:
        verá el diccionario anterior completo o el nuevo completo, nunca uno a
        medias y nunca vacío. Una tabla vacía dejaría al MCP inventándose los
        significados, que es justo lo que esta feature existe para impedir.

        El vaciado es `DELETE` y jamás `DROP`: un `DROP` se lleva por delante
        los `GRANT` del rol de lectura y dejaría al MCP ciego hasta el
        `apply-grants` siguiente.
        """
        from etl_sigrid.infrastructure.postgres.diccionario_sql import (
            SQL_BORRAR_CONTEXTO,
            SQL_BORRAR_DICCIONARIO,
            SQL_BORRAR_PUBLICACION,
            SQL_BORRAR_REGLAS,
            SQL_INSERT_CONTEXTO,
            SQL_INSERT_DICCIONARIO,
            SQL_INSERT_PUBLICACION,
            SQL_INSERT_REGLA,
            fila_publicacion,
            filas_diccionario,
            filas_contexto,
            filas_reglas,
        )

        instante = ahora if ahora is not None else datetime.utcnow()
        fichas = filas_diccionario(dicc)
        reglas = filas_reglas(dicc)
        contexto = filas_contexto(dicc)
        publicacion = fila_publicacion(dicc, hash_fuente, instante, batch_id, informe)

        with self.connection() as conn, conn.cursor() as cur:
            # Borrar antes de insertar: al revés chocaría con la clave primaria.
            cur.execute(SQL_BORRAR_DICCIONARIO)
            cur.execute(SQL_BORRAR_REGLAS)
            cur.execute(SQL_BORRAR_CONTEXTO)
            cur.execute(SQL_BORRAR_PUBLICACION)
            if fichas:
                cur.executemany(SQL_INSERT_DICCIONARIO, fichas)
            if reglas:
                cur.executemany(SQL_INSERT_REGLA, reglas)
            if contexto:
                cur.executemany(SQL_INSERT_CONTEXTO, contexto)
            cur.execute(SQL_INSERT_PUBLICACION, publicacion)

        escritas = len(fichas) + len(reglas) + len(contexto) + 1
        logger.info(
            "diccionario_publicado",
            version=publicacion[1],
            hash_fuente=hash_fuente[:12],
            objetos=len(fichas),
            reglas=len(reglas),
            contexto=len(contexto),
            filas=escritas,
        )
        return escritas

    def list_objetos_catalogo(self, schemas: Sequence[str]) -> list[tuple]:
        """Los objetos que la base tiene DE VERDAD, para `check-diccionario`.

        Es la única fuente no heurística: la puerta offline lee el SQL del
        repositorio con expresiones regulares y no puede ver un objeto creado
        por otra vía. Incluye funciones además de tablas y vistas, porque el
        diccionario también las documenta.
        """
        from etl_sigrid.infrastructure.postgres.diccionario_sql import (
            SQL_OBJETOS_CATALOGO,
        )

        pedidos = list(schemas)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_OBJETOS_CATALOGO, (pedidos, pedidos))
            return list(cur.fetchall())

    # ---------------------------------------------------------------------
    # Ejecución de archivos SQL (DDL, transformaciones stg/mart)
    # ---------------------------------------------------------------------

    def execute_sql_file(
        self,
        path: Path,
        *,
        params: dict | tuple | None = None,
    ) -> None:
        """
        Ejecuta el contenido de un archivo .sql contra Postgres.

        Comportamiento:
          - Sin parámetros: ejecuta todo el texto en una sola llamada
            (psycopg permite múltiples statements separados por ';').
          - Con parámetros: divide el texto en statements individuales
            (split por ';' respetando comentarios y strings) y los ejecuta
            uno a uno. Solo aplica los parámetros al/los statement(s) que
            realmente los contienen como placeholders. Esto es necesario
            porque Postgres no permite "multiple commands" en una prepared
            statement.

        Si el SQL falla, lanza la excepción de psycopg con el mensaje original
        (incluye nombre del error y posición).
        """
        if not path.exists():
            raise FileNotFoundError(f"SQL no encontrado: {path}")

        sql_text = path.read_text(encoding="utf-8")

        with self.connection() as conn, conn.cursor() as cur:
            if params is None:
                cur.execute(sql_text)
            else:
                statements = _split_sql_statements(sql_text)
                for stmt in statements:
                    if _statement_has_placeholders(stmt, params):
                        cur.execute(stmt, params)
                    else:
                        cur.execute(stmt)

        logger.info(
            "sql_file_executed",
            file=str(path.name),
            has_params=params is not None,
            param_style="dict" if isinstance(params, dict) else ("tuple" if params else "none"),
        )

    # ---------------------------------------------------------------------
    # Build por tramos de stg.plan_mensual (F-019)
    # ---------------------------------------------------------------------

    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        """Peso estimado de cada obra para planificar los tramos.

        Devuelve {obra_id: filas estimadas}. Es la entrada de
        `domain.tramos.planificar_tramos`, que no sabe de BBDD.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_PESOS_PLAN_MENSUAL)
            return {int(fila[0]): int(fila[1]) for fila in cur.fetchall()}

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        """Ocupación del disco del servidor, en tanto por ciento.

        **Propaga las excepciones a propósito**: quien llama tiene que abortar
        si esto falla (R10). Devolver un 0 «por si acaso» sería seguir a
        ciegas, que es exactamente lo que hacía el build que llenó el disco.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_OCUPACION_DISCO)
            fila = cur.fetchone()

        if not fila or fila[0] is None:
            raise RuntimeError(
                "No se pudo medir la ocupación del disco del servidor: la "
                "consulta sobre pg_database no devolvió ningún valor. Sin esa "
                "medición no se ejecuta ningún tramo."
            )
        return porcentaje_ocupacion(int(fila[0]), total_gb)

    # ---------------------------------------------------------------------
    # La ventana de negocio (F-025)
    # ---------------------------------------------------------------------

    def fetch_censo_de_obras(self) -> list[ObraCensada]:
        """El censo con el que se decide qué se reconstruye esta noche (R1).

        Devuelve entidades de dominio ya montadas, no tuplas: la decisión la
        toma `domain.ventana.clasificar_obras`, que no sabe de BBDD, y traducir
        aquí es lo que le permite no saberlo.

        `tiene_filas` exige las DOS tablas. Una obra con presupuesto y sin plan
        mensual —o al revés— está a medio construir, y media obra construida no
        se congela: se completa.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ESTADO_OBRAS)
            filas = list(cur.fetchall())

        return [
            ObraCensada(
                obra_id=int(fila[0]),
                codigo_obra=str(fila[1] or ""),
                estado_id=int(fila[2]) if fila[2] is not None else None,
                ultima_actividad=fila[3],
                tiene_filas=bool(fila[4]) and bool(fila[5]),
                registrada=bool(fila[6]),
                sello_registrado=fila[7],
                firma_registrada=fila[8],
                firma_origen=fila[9],
            )
            for fila in filas
        ]

    def fetch_firma_origen(self) -> dict[int, dict[str, Any]]:
        """Los agregados de `raw` por obra (R16). **Aquí no se hashea nada.**

        Devuelve `{obra_id: {columna: valor}}` con las columnas declaradas en
        `COLUMNAS_FIRMA_ORIGEN`. El hash lo calcula `domain.ventana.firma_de_obra`
        a partir de este diccionario, y por eso los nombres de las claves son
        parte del contrato: entran en la firma.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_FIRMA_ORIGEN)
            filas = list(cur.fetchall())

        return {
            int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))
            for fila in filas
        }

    def fetch_ultima_reconstruccion_completa(self, paso: str) -> datetime | None:
        """Cuándo terminó la última reconstrucción completa, o `None` (R25).

        `None` significa «nunca», y quien lo reciba tiene que hacer una: es la
        línea base, y sin ella no se puede afirmar cuántos días lleva ninguna
        obra sin reconstruirse.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ULTIMA_COMPLETA, {"paso": paso})
            fila = cur.fetchone()
        return fila[0] if fila and fila[0] is not None else None

    def fetch_obras_con_filas(self, tabla: str) -> set[int]:
        """Las obras que hoy tienen filas en `stg.<tabla>`.

        Solo lo usa la reconstrucción completa, y **solo para NOMBRAR** las
        obras que tienen filas y no están en el censo: el borrado derivado no
        las alcanza nunca —nadie las va a reinsertar, así que nadie las borra— y
        sin esto se quedarían ahí sin que nadie lo supiera. Es la contrapartida
        de haber quitado el `TRUNCATE`, y se denuncia en vez de aceptarse en
        silencio.

        **Lo que NO se hace con esta lista es borrarla.** Ver
        `build_stg_step._denunciar_obras_sobrantes`: borrar por lo que un `JOIN`
        del censo no vea sería destruir datos buenos en silencio, y R10 dice que
        lo que se borra se deriva de lo que se va a escribir.
        """
        _exigir_tabla_acotada(tabla)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_OBRAS_CON_FILAS.format(tabla=tabla))
            return {int(fila[0]) for fila in cur.fetchall() if fila[0] is not None}

    def fetch_filas_por_obra(
        self, tabla: str, obras: Sequence[int]
    ) -> dict[int, int]:
        """Cuántas filas tiene en `stg.<tabla>` cada una de esas obras (R14).

        Es la pareja de `registrar_obras_construidas`: de aquí sale la columna
        `filas` de `_meta.obra_build`, o sea, cuánto dejó construido esta noche
        cada obra. Se pregunta SOLO por las obras que se acaban de construir
        —decenas—, nunca por la tabla entera: un `GROUP BY` sobre los 29,7 M de
        `plan_mensual` costaría más que el propio tramo en un `B1ms` sin
        créditos de CPU.

        **Una obra sin filas NO lleva clave en el resultado**, porque no sale
        del `GROUP BY`. Es deliberado y quien llama ya lo espera
        (`build_stg_step._registrar_construidas` resuelve con
        `filas.get(obra_id, 0)`): así el diccionario dice lo que respondió la
        base y no lo que suponemos que habría respondido. Inventar un `0` por
        cada obra pedida sería afirmar «la miré y estaba vacía» también en el
        caso en que la consulta ni siquiera la alcanzó.

        Sin obras no se abre conexión: el sub-paso puede quedarse sin nada que
        reconstruir (R9) y preguntarlo sería un viaje a la base para nada.

        `tabla` llega del step como nombre corto del tramo y se interpola en el
        SQL, así que se valida contra `TABLAS_ACOTADAS` antes de tocar nada.
        """
        _exigir_tabla_acotada(tabla)
        if not obras:
            return {}

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                SQL_FILAS_POR_OBRA.format(tabla=tabla),
                {"obras": [int(obra) for obra in obras]},
            )
            return {
                int(fila[0]): int(fila[1])
                for fila in cur.fetchall()
                if fila[0] is not None
            }

    def registrar_obras_construidas(self, registros: Sequence[dict]) -> int:
        """Escribe en `_meta.obra_build` lo construido esta noche (R14).

        Todos los upserts en **una transacción**: o queda registrada la tanda
        entera o ninguna. Un registro a medias haría que la noche siguiente unas
        obras se reconstruyeran por R18 y otras no, sin ningún criterio.

        Va en llamada aparte y no dentro del SQL del tramo por una razón
        práctica: `execute_sql_text` devuelve el `rowcount` de la ÚLTIMA
        sentencia, y meter aquí el upsert convertiría «filas insertadas en
        plan_mensual» en «obras registradas». Si el proceso muere entre el tramo
        y su registro, la obra queda construida y sin registrar, y la noche
        siguiente entra por R18: se reconstruye de más, que es el lado correcto
        en el que fallar.
        """
        if not registros:
            return 0
        with self.connection() as conn, conn.cursor() as cur:
            for registro in registros:
                cur.execute(SQL_REGISTRAR_OBRA, registro)
        return len(registros)

    def marcar_obras_congeladas(self, registros: Sequence[dict]) -> int:
        """Deja escrito por qué NO se ha reconstruido cada obra congelada.

        No toca `construido_at` ni `filas`: esta noche no se ha construido nada
        de esas obras y mover su fecha sería mentir sobre la frescura.
        """
        if not registros:
            return 0
        with self.connection() as conn, conn.cursor() as cur:
            for registro in registros:
                cur.execute(SQL_MARCAR_CONGELADA, registro)
        return len(registros)

    def registrar_firmas_actuales(self, firmas: Mapping[int, str]) -> int:
        """Guarda la firma del origen de ESTA noche, por obra (R16).

        La escribe el sub-paso que va tras `ingest_raw`, sobre `raw` recién
        cargado. Es la mitad de la comparación; la otra es `firma_origen`, que
        solo se mueve cuando la obra se reconstruye.
        """
        if not firmas:
            return 0
        ahora = datetime.utcnow()
        with self.connection() as conn, conn.cursor() as cur:
            for obra_id, firma in firmas.items():
                cur.execute(
                    SQL_REGISTRAR_FIRMA_ACTUAL,
                    {
                        "obra_id": int(obra_id),
                        "firma_actual": firma,
                        "firma_actual_at": ahora,
                    },
                )
        return len(firmas)

    def vacuum_analyze(self, schema: str, table: str) -> None:
        """`VACUUM (ANALYZE)` de una tabla acotada, **fuera de transacción**.

        Postgres no admite `VACUUM` dentro de una transacción, y
        `self.connection()` devuelve una conexión que ya viene en una: por eso
        esto abre la suya propia en `autocommit`. Es el mismo motivo por el que
        `comprobar_unicidad` no toca el `autocommit` de una conexión ya abierta.

        Hace falta porque el borrado derivado deja tuplas muertas cada noche en
        un servidor sin créditos de CPU, donde el autovacuum llega tarde
        (§9.1 del diseño). Quien llama decide qué hacer si falla; aquí se
        propaga.
        """
        if table not in TABLAS_ACOTADAS:
            raise ValueError(
                f"tabla no acotada por la ventana: {table!r}. Este nombre se "
                f"interpola en el SQL del VACUUM: no puede venir de fuera."
            )
        conn = self._connect(self._conninfo, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("VACUUM (ANALYZE) {}.{}").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
        finally:
            conn.close()
        logger.info("tabla_vacuum_analyze", table=f"{schema}.{table}")

    def execute_sql_text(self, sql_text: str) -> int:
        """Ejecuta un SQL ya compuesto y devuelve las filas afectadas.

        Una llamada = una conexión = **una transacción** (lo garantiza
        `connection()`). Es lo que impide que el pico de temporales de un
        tramo se apile con el del siguiente.

        El recuento sale del `rowcount` del cursor, no de un `COUNT(*)` sobre
        la tabla: un seq-scan por tramo sobre millones de filas en 1 vCPU
        sería castigo gratuito.

        **Se devuelve el recuento de la ÚLTIMA sentencia, y desde F-025 eso
        importa.** El texto de un tramo ya no es una sola sentencia: es un
        `DELETE` de las obras del tramo seguido del `INSERT` que las reescribe.
        `cur.execute()` con varias sentencias deja el cursor **en el primer
        resultado** —lo dice `Cursor.nextset`: «move to the next result set if
        execute() returned more than one»—, así que leer `rowcount` sin avanzar
        devolvería **las filas BORRADAS en vez de las escritas**.

        Y sería un error de los caros de detectar: la primera noche los dos
        números son parecidos, así que el dato de `_meta.etl_runs` y de
        `python main.py timings` saldría plausible y equivocado.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql_text)
            filas = cur.rowcount
            while cur.nextset():
                filas = cur.rowcount

        # psycopg deja rowcount en -1 cuando la sentencia no trae recuento.
        return max(int(filas), 0) if filas is not None else 0

    # ---------------------------------------------------------------------
    # Carga masiva con COPY

    # ---------------------------------------------------------------------

    def copy_rows(
        self,
        schema: str,
        table: str,
        columns: list[str],
        rows: Iterable[dict[str, Any]],
        *,
        tiemod_column: str | None = None,
    ) -> int:
        """
        Inserta filas en `schema.table` usando COPY FROM STDIN en formato texto.

        `rows` es un iterable de dicts (no se materializa entero en memoria).
        `columns` define el orden y selección de columnas a insertar.
        Añade automáticamente `_source_tiemod` si `tiemod_column` se proporciona
        y existe en cada fila.

        Devuelve el número de filas insertadas.
        """
        if not columns:
            raise ValueError("Lista de columnas vacía")

        # Cláusula de columnas para COPY. Incluye _source_tiemod si procede.
        copy_columns = list(columns)
        if tiemod_column:
            copy_columns.append("_source_tiemod")

        copy_sql = sql.SQL(
            "COPY {}.{} ({}) FROM STDIN WITH (FORMAT text, NULL '\\N')"
        ).format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in copy_columns),
        )

        rows_written = 0

        with self.connection() as conn, conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for row in rows:
                fields: list[str] = []
                for c in columns:
                    fields.append(_pg_text_format(row.get(c)))
                if tiemod_column:
                    fields.append(_pg_text_format(row.get(tiemod_column)))
                copy.write("\t".join(fields) + "\n")
                rows_written += 1

        return rows_written

    # ---------------------------------------------------------------------
    # Tracking de runs (_meta.etl_runs)
    # ---------------------------------------------------------------------

    def record_run_start(
        self, stage: str, step: str, batch_id: str | None = None
    ) -> int:
        """Inserta una fila en _meta.etl_runs con status=RUNNING. Devuelve el run_id.

        `batch_id` es opcional a propósito (F-024): este método lo llaman los
        sub-pasos de `build_stg` y sus ~60 tramos, y hacerlo obligatorio
        rompería todos los llamantes a la vez. Sin él se escribe NULL, que es
        exactamente lo que tiene el histórico anterior a la feature.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_RUN_START, (stage, step, datetime.utcnow(), batch_id))
            row = cur.fetchone()
            return int(row[0])

    # ---------------------------------------------------------------------
    # Coherencia ante cargas truncadas (F-024)
    # ---------------------------------------------------------------------

    def abortar_runs_huerfanos(
        self, batch_id: str, ahora: datetime | None = None
    ) -> list[tuple[int, str, datetime]]:
        """Cierra como ABORTED las filas que dejó abiertas un proceso muerto.

        Devuelve `(id, step, started_at)` de cada fila marcada, para que quien
        llama emita un WARNING por fila: enterarse de que anoche murió algo es
        justo lo que no pasaba antes de F-024.

        **Propaga las excepciones**: quien llama decide. Y decide continuar
        (R7), porque esto es contabilidad y el paso que venga detrás fallará
        por sí mismo si la BBDD no está.
        """
        instante = datetime.utcnow() if ahora is None else ahora
        motivo = MOTIVO_HUERFANA.format(
            batch_id=batch_id,
            ahora=instante.isoformat(sep=" ", timespec="seconds"),
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ABORTAR_HUERFANOS, {"ahora": instante, "motivo": motivo})
            return [
                (int(fila[0]), str(fila[1]), fila[2]) for fila in cur.fetchall()
            ]

    def fetch_estado_raw(self) -> list[EstadoTablaRaw]:
        """Última ingesta conocida de cada tabla de `raw`, desde la vista."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ESTADO_RAW)
            return [
                EstadoTablaRaw(
                    tabla=fila[0],
                    status=fila[1],
                    batch_id=fila[2],
                    started_at=fila[3],
                    finished_at=fila[4],
                    filas=int(fila[5] or 0),
                )
                for fila in cur.fetchall()
            ]

    def fetch_ultimo_intento_stg(self) -> EstadoPaso | None:
        """La fila más reciente de `build_stg%`, o `None` si no hay ninguna."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ULTIMO_INTENTO_STG)
            fila = cur.fetchone()

        if fila is None:
            return None
        return EstadoPaso(
            id=int(fila[0]),
            step=fila[1],
            status=fila[2],
            batch_id=fila[3],
            started_at=fila[4],
            finished_at=fila[5],
        )

    def fetch_frescura(self) -> list[FilaFrescura]:
        """`_meta.v_frescura` tal cual, con las horas ya en `float`.

        La vista las devuelve como `numeric` (psycopg las trae en `Decimal`) y
        `format_frescura` las compara con un umbral entero: la conversión se
        hace aquí, una vez, y no en cada llamante.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_FRESCURA)
            return [
                FilaFrescura(
                    paso=fila[0],
                    ultimo_ok_finished_at=fila[1],
                    ultimo_ok_batch_id=fila[2],
                    ultimo_ok_filas=fila[3],
                    horas_desde_ultimo_ok=(
                        None if fila[4] is None else float(fila[4])
                    ),
                    ultimo_intento_started_at=fila[5],
                    ultimo_intento_status=fila[6],
                    ultimo_intento_error=fila[7],
                )
                for fila in cur.fetchall()
            ]

    def fetch_timings(self, last: int = 1) -> list[Timing]:
        """
        Mediciones de las `last` ejecuciones más recientes del pipeline.

        Una "ejecución" se ancla al arranque de `ingest_raw`, que es el primer
        paso de `run-all`: se devuelven todas las filas desde el arranque
        número `last` hacia atrás. Así entran también los pasos que se lanzan
        después con comandos sueltos (build-cierre, apply-grants), que es
        justo lo que interesa medir en la carga inicial.

        Si todavía no hay ningún `ingest_raw` registrado —caso de una base
        cargada antes de que el orquestador instrumentara los pasos— se
        devuelven las últimas `TIMINGS_SIN_ANCLA` filas en vez del histórico
        entero, que puede ser de años.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(started_at) FROM (
                    SELECT started_at
                    FROM _meta.etl_runs
                    WHERE step = 'ingest_raw'
                    ORDER BY started_at DESC
                    LIMIT %s
                ) AS arranques
                """,
                (last,),
            )
            row = cur.fetchone()
            desde = row[0] if row else None

            if desde is not None:
                cur.execute(
                    """
                    SELECT stage, step, started_at, finished_at, status, rows_processed
                    FROM _meta.etl_runs
                    WHERE started_at >= %s
                    ORDER BY started_at, id
                    """,
                    (desde,),
                )
                filas = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT stage, step, started_at, finished_at, status, rows_processed
                    FROM _meta.etl_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT %s
                    """,
                    (TIMINGS_SIN_ANCLA,),
                )
                filas = list(reversed(cur.fetchall()))

            return [
                Timing(
                    stage=fila[0],
                    step=fila[1],
                    started_at=fila[2],
                    finished_at=fila[3],
                    status=fila[4],
                    rows_processed=int(fila[5] or 0),
                )
                for fila in filas
            ]

    def fetch_perfil_carga(
        self, batch_id: str | None = None
    ) -> tuple[str | None, list[FilaPerfil]]:
        """
        Desglose de una carga: una fila por paso y una por tabla de la ingesta.

        Devuelve el par `(batch medido, filas)`. El `batch_id` viaja de vuelta
        —y no solo las filas, como apuntaba el diseño— porque R8 exige que el
        informe de medición diga de QUÉ carga salen los números: sin él, quien
        lee el perfil no puede saber si midió la nocturna buena o la noche que
        murió a los diez minutos.

        Sin argumento mide la última carga registrada. Solo `SELECT`: no marca
        huérfanas ni registra paso (R25).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_PERFIL_CARGA, {"batch": batch_id})
            filas = cur.fetchall()

        medido = batch_id
        perfil: list[FilaPerfil] = []
        for stage, step, started_at, finished_at, status, rows, batch in filas:
            if medido is None:
                medido = batch
            perfil.append(
                FilaPerfil(
                    stage=stage,
                    step=step,
                    segundos=(
                        0.0
                        if started_at is None or finished_at is None
                        else (finished_at - started_at).total_seconds()
                    ),
                    filas=int(rows or 0),
                    status=status,
                )
            )
        return medido, perfil

    def fetch_diagnostico_tiemod(self) -> list[EstadoTiemod]:
        """
        Estado de `_source_tiemod` en cada tabla de `raw` que la tenga (R6).

        Una consulta de agregación por tabla, en una sola conexión. Es cara
        —recorre cada tabla entera— y por eso solo la lanza el comando
        `diagnostico-tiemod`, nunca el pipeline.
        """
        columna = sql.Identifier(COLUMNA_TIEMOD)
        estados: list[EstadoTiemod] = []

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_TABLAS_CON_TIEMOD, {"columna": COLUMNA_TIEMOD})
            tablas = [fila[0] for fila in cur.fetchall()]

            for tabla in tablas:
                cur.execute(
                    sql.SQL(SQL_DIAGNOSTICO_TIEMOD).format(
                        col=columna, tabla=sql.Identifier(tabla)
                    )
                )
                # Una agregación sin GROUP BY siempre devuelve exactamente una
                # fila: no hay rama defensiva que probar aquí, y añadirla solo
                # dejaría código muerto que ningún test puede recorrer.
                fila = cur.fetchone()
                estados.append(
                    EstadoTiemod(
                        tabla=tabla,
                        filas=int(fila[0] or 0),
                        nulos=int(fila[1] or 0),
                        minimo=_float_o_none(fila[2]),
                        maximo=_float_o_none(fila[3]),
                        distintos=int(fila[4] or 0),
                    )
                )
        return estados

    def fetch_filas_desde_tiemod(self, tabla: str, umbral: float) -> int:
        """Cuántas filas de `raw.<tabla>` tienen la marca por encima de `umbral` (R7)."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL(SQL_FILAS_DESDE_TIEMOD).format(
                    tabla=sql.Identifier(tabla),
                    col=sql.Identifier(COLUMNA_TIEMOD),
                ),
                {"umbral": umbral},
            )
            fila = cur.fetchone()
            return int(fila[0]) if fila else 0

    def record_run_completed(
        self,
        stage: str,
        step: str,
        started_at: datetime | None,
        finished_at: datetime | None,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        batch_id: str | None = None,
    ) -> int:
        """
        Inserta de una vez la fila de un paso YA terminado, y devuelve su id.

        Es distinto de `record_run_start` + `record_run_end`: ese par lo usan
        los steps que se instrumentan a sí mismos. Este lo usa el orquestador
        para dejar rastro de TODOS los pasos, incluidos los que no se
        instrumentan por dentro (build_mart, build_cierre), que son los pesados.

        Estas son las filas de PASO que después lee `_meta.v_frescura`, y por
        eso son las que más importa que lleven `batch_id` (F-024).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                SQL_RUN_COMPLETED,
                (
                    stage,
                    step,
                    started_at or datetime.utcnow(),
                    finished_at,
                    status,
                    rows_processed,
                    error_message,
                    Json(metadata) if metadata else None,
                    batch_id,
                ),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def record_run_end(
        self,
        run_id: int,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Cierra la fila de _meta.etl_runs con status final."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE _meta.etl_runs
                SET finished_at    = %s,
                    status         = %s,
                    rows_processed = %s,
                    error_message  = %s
                WHERE id = %s
                """,
                (datetime.utcnow(), status, rows_processed, error_message, run_id),
            )


# -------------------------------------------------------------------------
# Helpers de formato para COPY (formato texto de Postgres)
# -------------------------------------------------------------------------

def _pg_text_format(value: Any) -> str:
    """
    Codifica un valor Python al formato texto de COPY de Postgres.

    Reglas:
      - None        → \\N (NULL)
      - bool        → 't' / 'f'
      - bytes       → \\\\x<hex>   (formato hex de bytea)
      - resto       → str(value) con escapado de \\, tab, newline, CR
    """
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, bytes):
        return "\\\\x" + value.hex()
    s = str(value)
    # Escapado para formato texto de COPY
    return (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


# -------------------------------------------------------------------------
# Helpers para ejecutar SQL con múltiples statements + parámetros
# -------------------------------------------------------------------------

def _split_sql_statements(sql_text: str) -> list[str]:
    """
    Divide un texto SQL en statements individuales por ';'.

    Maneja:
      - Comentarios de línea (-- ...): se ignoran al detectar separadores.
      - Strings literales con comilla simple: no divide por ';' dentro de ellas.

    Suficiente para los SQL controlados de este proyecto. NO maneja:
      - Bloques delimitados con $$ ... $$ (CREATE FUNCTION con plpgsql).
        Por eso 00_functions.sql se ejecuta sin parámetros (caso simple).
      - Comentarios de bloque /* ... */.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    in_line_comment = False

    i = 0
    while i < len(sql_text):
        ch = sql_text[i]

        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_string:
            current.append(ch)
            if ch == "'":
                # Comilla doble '' dentro de string = escape, no fin
                if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                    current.append("'")
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        # Detectar inicio de comentario de línea
        if ch == "-" and i + 1 < len(sql_text) and sql_text[i + 1] == "-":
            in_line_comment = True
            current.append(ch)
            i += 1
            continue

        if ch == "'":
            in_string = True
            current.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    # Último statement sin ; final
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def _statement_has_placeholders(stmt: str, params: dict | tuple) -> bool:
    """
    Devuelve True si el statement contiene placeholders compatibles con `params`.

    Reglas:
      - dict params + %(nombre)s en el SQL → True si alguna clave del dict aparece
      - tuple params + %s en el SQL → True si %s está presente

    Sirve para no pasar parámetros a statements que no los necesitan (TRUNCATE, etc.),
    lo cual evita errores 'argument formats can't be mixed' en psycopg.
    """
    # Eliminar comentarios de línea antes de buscar
    cleaned_lines = []
    for line in stmt.splitlines():
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    if isinstance(params, dict):
        return any(f"%({k})s" in cleaned for k in params)
    return "%s" in cleaned
