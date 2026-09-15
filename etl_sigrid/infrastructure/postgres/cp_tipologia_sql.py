# etl_sigrid/infrastructure/postgres/cp_tipologia_sql.py
"""
F-078 · La comprobación de que materializar NO cambió ni una cifra.
**Solo construye texto.**

Al estilo de `unicidad_sql.py`, `cierres_sql.py` y `cobertura_sql.py`: este
módulo **no abre ninguna conexión**. Quien la ejecuta es el comando
`python main.py check-cp-tipologia`, con la transacción en `READ ONLY` y su
`statement_timeout`, porque esto corre contra `psql-albaranes-rs9k2`, que
comparten `albaranes` y `partes` **en producción**.

## Qué compara, y por qué no es una tautología

F-078 movió el cálculo de `mart.v_pbi_cp_tipologia` de la vista a la tabla
`mart.fact_cp_tipologia`. Después del cambio, la vista **lee de la tabla**, así
que comparar la vista contra la tabla no demostraría nada: daría cero
diferencias aunque el build estuviera mal.

Por eso `SQL_VISTA_ANTERIOR` es una **fotografía congelada** del cálculo tal y
como lo hacía la vista antes de la feature (commit `b208a59`,
`sql/mart/06_views_cp_tipologia.sql`): recalcula desde `stg.plan_mensual` y
`stg.partidas`, **sin tocar ninguna de las tres tablas nuevas**. La comparación
es entonces lo que pide el criterio 3 de la ficha: el resultado de la vista de
antes contra la tabla de ahora, fila a fila sobre las claves
(`obra_id`, `anio`, `tipologia`) y sobre los tres importes.

**Congelada quiere decir congelada**: si mañana cambia la lógica de negocio,
esta copia NO se actualiza a la vez. Se retira, o deja de comparar lo que dice
comparar.

## El coste, que es el riesgo declarado

Recalcular la vista antigua es exactamente lo que F-078 vino a evitar: coste
estimado 6,6 millones de unidades y cinco recorridos de `stg.plan_mensual`. Por
eso el `statement_timeout` por defecto es de media hora y no de 30 segundos, y
por eso existe `--obra`: filtrando a una sola obra el barrido se desploma y sirve
como sonda antes de lanzar la comparación entera.

## Cuándo vale el resultado

La lógica usa `CURRENT_DATE` para decidir el año en curso y el mes de corte. En
la tabla esa fecha quedó **congelada en el build**; aquí se evalúa ahora. Si la
comparación se lanza un día distinto al del build y entre medias ha cambiado el
mes, las dos mitades cortan en meses distintos y las diferencias que salgan son
legítimas. **Se compara el mismo día en que se construyó la tabla.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: Segundos de `statement_timeout`. Media hora: la mitad izquierda de la
#: comparación es la consulta que no terminaba en 60 s, que es justo el motivo
#: de la feature. Si salta, el comando lo dice y **no lo cuenta como correcto**.
TIMEOUT_POR_CONSULTA_S = 1800

#: Las claves de negocio sobre las que se casan las dos mitades.
CLAVES = ("obra_id", "anio", "tipologia")

#: Lo que se compara además de la presencia de la fila.
MEDIDAS = ("cp_real", "cp_planificado", "cp_desviacion", "orden_tipologia")


@dataclass(frozen=True, slots=True)
class DiferenciaCP:
    """Una fila en la que la vista de antes y la tabla de ahora no coinciden."""

    obra_id: int
    anio: int
    tipologia: str
    motivo: str
    cp_real_antes: object
    cp_real_ahora: object
    cp_plan_antes: object
    cp_plan_ahora: object
    cp_desv_antes: object
    cp_desv_ahora: object
    orden_antes: object
    orden_ahora: object


def _filtro(alias: str, obra_id: int | None) -> str:
    """`AND <alias>obra_id = N`, o nada. `obra_id` se fuerza a entero: no hay
    forma de que llegue texto a la sentencia."""
    if obra_id is None:
        return ""
    return f"AND {alias}obra_id = {int(obra_id)}"


def sql_vista_anterior(obra_id: int | None = None) -> str:
    """El cálculo de `mart.v_pbi_cp_tipologia` **tal y como era antes de F-078**.

    Copia literal de la lógica de las tres vistas encadenadas del commit
    `b208a59`, con los dos helpers convertidos en CTE. Lee de `stg`, nunca de
    `mart.fact_cp_tipologia` ni de sus helpers: si leyera de ellos, la
    comparación se compararía consigo misma.
    """
    return f"""
WITH params AS (
    SELECT EXTRACT(YEAR  FROM CURRENT_DATE)::INT AS anio_actual,
           EXTRACT(MONTH FROM CURRENT_DATE)::INT AS mes_actual,
           CURRENT_DATE                          AS hoy
),
versiones_tipadas AS (
    SELECT DISTINCT
        obra_id, ambito_id, version, version_fec_creacion,
        version_fec_efectiva, version_descripcion, version_tex,
        CASE
            WHEN version_tex IS NULL OR length(trim(version_tex)) = 0
                THEN 'Sin clasificar'
            WHEN UPPER(version_tex) LIKE '%ABC%'
                THEN 'ABC'
            WHEN UPPER(version_tex) LIKE '%INICIAL%'
             AND UPPER(version_tex) LIKE '%VALORADA%'
                THEN 'Planif Inicial'
            WHEN UPPER(version_tex) LIKE '%CUATRIM%'
              OR UPPER(version_tex) LIKE '%VALORADA%'
                THEN 'Cuatrimestral'
            WHEN UPPER(version_tex) LIKE '%CIERRE%'
                THEN 'Cierre mensual'
            ELSE 'Sin clasificar'
        END AS tipo_master
    FROM stg.plan_mensual
    WHERE ambito_id IN (8, 11)
      AND version_fec_efectiva IS NOT NULL
      {_filtro("", obra_id)}
),
anios_obra AS (
    SELECT DISTINCT obra_id, EXTRACT(YEAR FROM anio_mes)::INT AS anio
    FROM stg.plan_mensual
    WHERE TRUE {_filtro("", obra_id)}
),
candidatos AS (
    SELECT
        ao.obra_id, ao.anio, vt.ambito_id, vt.version,
        ROW_NUMBER() OVER (
            PARTITION BY ao.obra_id, ao.anio, vt.ambito_id
            ORDER BY vt.version_fec_efectiva DESC, vt.version DESC
        ) AS rn
    FROM anios_obra ao
    CROSS JOIN params p
    JOIN versiones_tipadas vt
        ON vt.obra_id = ao.obra_id
       AND vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')
       AND vt.version_fec_efectiva <= CASE
                WHEN ao.anio < p.anio_actual THEN make_date(ao.anio, 12, 31)
                ELSE p.hoy
            END
),
vigente_anual AS (
    SELECT obra_id, anio, ambito_id, version
    FROM candidatos
    WHERE rn = 1
),
ultimo_real AS (
    SELECT
        obra_id,
        EXTRACT(YEAR  FROM anio_mes)::INT      AS anio,
        MAX(EXTRACT(MONTH FROM anio_mes)::INT) AS mes
    FROM stg.plan_mensual
    WHERE ambito_id = 3 {_filtro("", obra_id)}
    GROUP BY 1, 2
),
corte AS (
    SELECT
        ao.obra_id,
        ao.anio,
        CASE
            WHEN ao.anio <  par.anio_actual THEN 12
            WHEN ao.anio =  par.anio_actual THEN COALESCE(ur.mes, par.mes_actual)
            ELSE 0
        END AS mes_corte
    FROM anios_obra ao
    CROSS JOIN params par
    LEFT JOIN ultimo_real ur
        ON ur.obra_id = ao.obra_id
       AND ur.anio    = ao.anio
),
real_anual AS (
    SELECT
        pm.obra_id,
        EXTRACT(YEAR FROM pm.anio_mes)::INT AS anio,
        pm.partida_id,
        p.descripcion_corta,
        p.ruta_capitulos,
        SUM(pm.importe_mes)::NUMERIC(18,2)  AS cp_real
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    JOIN corte c
        ON c.obra_id = pm.obra_id
       AND c.anio    = EXTRACT(YEAR FROM pm.anio_mes)::INT
    WHERE pm.ambito_id = 3
      AND p.categoria  = 'CP'
      AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= c.mes_corte
      {_filtro("pm.", obra_id)}
    GROUP BY 1, 2, 3, 4, 5
),
plan_anual AS (
    SELECT
        pm.obra_id,
        EXTRACT(YEAR FROM pm.anio_mes)::INT AS anio,
        pm.partida_id,
        p.descripcion_corta,
        p.ruta_capitulos,
        SUM(pm.importe_mes)::NUMERIC(18,2)  AS cp_planificado
    FROM stg.plan_mensual pm
    JOIN stg.partidas p ON p.partida_id = pm.partida_id
    JOIN vigente_anual va
        ON va.obra_id   = pm.obra_id
       AND va.ambito_id = 8
       AND va.anio      = EXTRACT(YEAR FROM pm.anio_mes)::INT
       AND va.version   = pm.version
    JOIN corte c
        ON c.obra_id = pm.obra_id
       AND c.anio    = EXTRACT(YEAR FROM pm.anio_mes)::INT
    WHERE pm.ambito_id = 8
      AND p.categoria  = 'CP'
      AND EXTRACT(MONTH FROM pm.anio_mes)::INT <= c.mes_corte
      {_filtro("pm.", obra_id)}
    GROUP BY 1, 2, 3, 4, 5
),
detalle_partida AS (
    SELECT
        COALESCE(r.obra_id, p.obra_id)                     AS obra_id,
        COALESCE(r.anio, p.anio)                           AS anio,
        COALESCE(r.descripcion_corta, p.descripcion_corta) AS descripcion_corta,
        COALESCE(r.ruta_capitulos, p.ruta_capitulos)       AS ruta_capitulos,
        COALESCE(r.cp_real,        0)::NUMERIC(18,2)       AS cp_real,
        COALESCE(p.cp_planificado, 0)::NUMERIC(18,2)       AS cp_planificado
    FROM      real_anual r
    FULL JOIN plan_anual p
        ON r.obra_id     = p.obra_id
       AND r.anio        = p.anio
       AND r.partida_id  = p.partida_id
),
con_tipologia AS (
    SELECT
        obra_id, anio, cp_real, cp_planificado,
        CASE
            WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.9', 'CP.9_1')
                THEN 'LEVANTAMIENTO'
            WHEN split_part(ruta_capitulos, ' > ', 2) IN ('CP.1', 'CP.2', 'CP.3')
                THEN 'SEGUROS'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.4'
                THEN 'AVALES'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.6'
                THEN 'CONTRATACION'
            WHEN split_part(ruta_capitulos, ' > ', 2) = 'CP.12'
                THEN 'MEDIO AMBIENTE'
            WHEN UPPER(descripcion_corta) LIKE '%LEVANTAM%'
                THEN 'LEVANTAMIENTO'
            WHEN UPPER(descripcion_corta) LIKE '%SEGURO%'
                THEN 'SEGUROS'
            WHEN UPPER(descripcion_corta) LIKE '%AVAL%'
              OR UPPER(descripcion_corta) LIKE '%GARANTIA%'
                THEN 'AVALES'
            WHEN UPPER(descripcion_corta) LIKE '%CONTRATAC%'
                THEN 'CONTRATACION'
            WHEN UPPER(descripcion_corta) LIKE '%CALIDAD%'
              OR UPPER(descripcion_corta) LIKE '%MEDIO AMB%'
                THEN 'MEDIO AMBIENTE'
            ELSE 'APORTE GG'
        END AS tipologia
    FROM detalle_partida
)
SELECT
    obra_id,
    anio,
    tipologia,
    CASE tipologia
        WHEN 'LEVANTAMIENTO'  THEN 1
        WHEN 'SEGUROS'        THEN 2
        WHEN 'AVALES'         THEN 3
        WHEN 'CONTRATACION'   THEN 4
        WHEN 'MEDIO AMBIENTE' THEN 5
        WHEN 'APORTE GG'      THEN 6
        ELSE 9
    END                                  AS orden_tipologia,
    SUM(cp_real)::NUMERIC(18,2)          AS cp_real,
    SUM(cp_planificado)::NUMERIC(18,2)   AS cp_planificado,
    (SUM(cp_real) - SUM(cp_planificado))::NUMERIC(18,2) AS cp_desviacion
FROM con_tipologia
GROUP BY obra_id, anio, tipologia
HAVING SUM(cp_real) <> 0 OR SUM(cp_planificado) <> 0
""".strip()


def sql_comparacion(obra_id: int | None = None) -> str:
    """Las filas en las que las dos mitades NO coinciden. Vacío = todo cuadra.

    `IS DISTINCT FROM` y no `<>`: con `<>` una comparación contra `NULL` da
    `NULL`, la fila se cae del `WHERE` y una diferencia real se cuenta como
    coincidencia. Es el modo de fallo silencioso de este tipo de contrastes.
    """
    return f"""
WITH antes AS (
{sql_vista_anterior(obra_id)}
),
ahora AS (
    SELECT obra_id, anio, tipologia, orden_tipologia,
           cp_real, cp_planificado, cp_desviacion
    FROM mart.fact_cp_tipologia
    WHERE TRUE {_filtro("", obra_id)}
)
SELECT
    COALESCE(v.obra_id,   t.obra_id)   AS obra_id,
    COALESCE(v.anio,      t.anio)      AS anio,
    COALESCE(v.tipologia, t.tipologia) AS tipologia,
    CASE
        WHEN t.tipologia IS NULL THEN 'SOLO EN LA VISTA DE ANTES'
        WHEN v.tipologia IS NULL THEN 'SOLO EN LA TABLA NUEVA'
        ELSE 'IMPORTES DISTINTOS'
    END AS motivo,
    v.cp_real,        t.cp_real,
    v.cp_planificado, t.cp_planificado,
    v.cp_desviacion,  t.cp_desviacion,
    v.orden_tipologia, t.orden_tipologia
FROM      antes v
FULL JOIN ahora t
    ON t.obra_id   = v.obra_id
   AND t.anio      = v.anio
   AND t.tipologia = v.tipologia
WHERE v.tipologia IS NULL
   OR t.tipologia IS NULL
   OR v.cp_real         IS DISTINCT FROM t.cp_real
   OR v.cp_planificado  IS DISTINCT FROM t.cp_planificado
   OR v.cp_desviacion   IS DISTINCT FROM t.cp_desviacion
   OR v.orden_tipologia IS DISTINCT FROM t.orden_tipologia
ORDER BY 1, 2, 3
""".strip()


def sql_recuento_tabla(obra_id: int | None = None) -> str:
    """Cuántas filas tiene la tabla nueva. Barata, y necesaria: cero
    diferencias sobre cero filas a cada lado no demuestra nada."""
    return (
        "SELECT count(*) FROM mart.fact_cp_tipologia "
        f"WHERE TRUE {_filtro('', obra_id)}"
    )


def diferencias_de(filas: Sequence[Sequence]) -> tuple[DiferenciaCP, ...]:
    """Convierte el resultado crudo en entidades. Sin conexión ni E/S."""
    return tuple(
        DiferenciaCP(
            obra_id=int(f[0]),
            anio=int(f[1]),
            tipologia=str(f[2]),
            motivo=str(f[3]),
            cp_real_antes=f[4],
            cp_real_ahora=f[5],
            cp_plan_antes=f[6],
            cp_plan_ahora=f[7],
            cp_desv_antes=f[8],
            cp_desv_ahora=f[9],
            orden_antes=f[10],
            orden_ahora=f[11],
        )
        for f in filas
    )


def veredicto(diferencias: Sequence[DiferenciaCP], filas_tabla: int) -> str:
    """El veredicto, escrito para que no se pueda leer al revés.

    **Una tabla vacía NO es «cero diferencias»**: si el build no llegó a
    construir nada, la comparación saldría limpia porque las dos mitades están
    vacías. Por eso el recuento entra en el veredicto y no como adorno.
    """
    if filas_tabla == 0:
        return (
            "KO   mart.fact_cp_tipologia esta VACIA: no se ha comparado nada. "
            "Construyela con `python main.py build-mart` antes de creer un cero"
        )
    if not diferencias:
        return (
            f"OK   {filas_tabla} filas y CERO diferencias: materializar no "
            "cambio ninguna cifra"
        )
    return (
        f"KO   {len(diferencias)} diferencias sobre {filas_tabla} filas: "
        "la tabla NO reproduce lo que daba la vista"
    )
