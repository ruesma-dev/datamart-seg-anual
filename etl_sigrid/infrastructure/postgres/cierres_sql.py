# etl_sigrid/infrastructure/postgres/cierres_sql.py
"""
F-042 · Las consultas de `check-cierres` (R16, R17). **Solo construyen texto.**

Al estilo de `unicidad_sql.py`: este módulo **no abre ninguna conexión**. Quien
las ejecuta es el comando, con la transacción en `READ ONLY` y su
`statement_timeout`, porque esto corre contra `psql-albaranes-rs9k2`, que
comparten `albaranes` y `partes` **en producción**.

Son tres preguntas:

1. **Los candidatos** — todas las fases que `reales_base` vería, recompuestas
   desde `stg.presupuesto` ⨝ `stg.fases`. Es el lado independiente del
   contraste: si salieran de `stg.plan_mensual`, la comprobación se estaría
   preguntando a sí misma y su verde no significaría nada.
2. **Lo publicado** — lo que `stg.plan_mensual` tiene de verdad, al mismo grano.
3. **El telescopio** — si `SUM(importe_mes)` sigue siendo el último
   `importe_origen` de cada serie (R16).

## Una honestidad sobre el telescopio

La propiedad vale cuando la serie de una (obra, partida, ámbito) es
**consecutiva**. Una serie con un hueco que la regla NO creó —fases 1, 2 y 4 en
Sigrid— nunca telescopeó y no va a empezar ahora: su `importe_mes` de la fase 4
es el acumulado entero, por diseño. Contarla como rota sería una alarma falsa;
callarla, una omisión. Se cuenta **aparte**, y el comando lo dice.
"""

from __future__ import annotations

from collections.abc import Sequence

from etl_sigrid.domain.cierres import Discrepancia

# Reexportado a propósito: las dos sentencias previas que dejan la transacción
# en READ ONLY con su timeout son EXACTAMENTE las mismas que las de la
# comprobación de unicidad. Copiarlas aquí sería abrir la puerta a que una de
# las dos copias perdiera el `transaction_read_only` sin que nadie lo notara.
from etl_sigrid.infrastructure.postgres.unicidad_sql import (  # noqa: F401
    sentencias_previas,
)

#: Los ámbitos donde `fas` es el mes y donde por tanto existe el problema. Los
#: master (8 y 11) usan `fas` como número de versión: ni se arreglan ni se miran.
AMBITOS_REALES = (3, 7)

#: Segundos por consulta. Más generoso que el de unicidad (30 s) porque el
#: telescopio agrega `stg.plan_mensual` entera, que ronda los 29 millones de
#: filas; y aun así acotado, porque el servidor es compartido. Si salta, el
#: comando lo dice y NO lo cuenta como correcto.
TIMEOUT_POR_CONSULTA_S = 300

#: Lo que un `SELECT` de diagnóstico no puede contener ni por accidente. La
#: transacción ya va `READ ONLY`, así que esto es el segundo cerrojo: el texto
#: se comprueba en los tests, sin conexión, antes de que nadie lo ejecute.
PALABRAS_DE_ESCRITURA = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "DROP",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COPY",
)

_AMBITOS = ", ".join(str(a) for a in AMBITOS_REALES)


def _filtro_de_obras(obras: Sequence[int] | None, alias: str = "") -> str:
    """`AND obra_id IN (...)` con los identificadores validados como enteros.

    Los `obra_id` llegan de la línea de órdenes y acaban dentro de un `SELECT`.
    Se convierten con `int()`, que rechaza cualquier cosa que no sea un entero:
    no hay interpolación de texto libre, ni siquiera del humano que lo teclea.
    """
    if not obras:
        return ""
    try:
        numeros = [int(obra) for obra in obras]
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"--obras solo admite identificadores numericos de obra, y ha "
            f"llegado {obras!r}. No se interpola texto libre en un SELECT"
        ) from error
    prefijo = f"{alias}." if alias else ""
    return f"\n      AND {prefijo}obra_id IN ({', '.join(str(n) for n in numeros)})"


def sql_cierres_candidatos(obras: Sequence[int] | None = None) -> str:
    """Todas las fases que el build vería, con su acumulado a origen.

    Reproduce el universo de `reales_base` al detalle —el `JOIN` con
    `raw.obrparpre`, `fase_num >= 1`, `anio`/`mes` no nulos y el mismo redondeo
    por decimales de la obra—, porque un oráculo que mirara más filas o menos
    inventaría discrepancias que el build no tiene.

    Grano: una fila por (obra, ámbito, mes, fase). Son miles, no millones.
    """
    return (
        "SELECT pp.obra_id,\n"
        "       pp.ambito_id,\n"
        "       make_date(f.anio, f.mes, 1) AS anio_mes,\n"
        "       pp.fase_num                 AS numero_fase,\n"
        "       COALESCE(SUM(ROUND(\n"
        "           pp.cantidad::NUMERIC * ROUND(pp.precio::NUMERIC, pp.dec_precios),\n"
        "           pp.dec_importes\n"
        "       )), 0) AS acumulado\n"
        "FROM stg.presupuesto pp\n"
        "JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id\n"
        "JOIN stg.fases     f\n"
        "    ON f.obra_id     = pp.obra_id\n"
        "   AND f.numero_fase = pp.fase_num\n"
        f"WHERE pp.ambito_id IN ({_AMBITOS})\n"
        "  AND pp.fase_num >= 1\n"
        "  AND f.anio IS NOT NULL\n"
        "  AND f.mes  IS NOT NULL"
        f"{_filtro_de_obras(obras, 'pp')}\n"
        "GROUP BY pp.obra_id, pp.ambito_id, make_date(f.anio, f.mes, 1), pp.fase_num\n"
        "ORDER BY 1, 2, 3, 4"
    )


def sql_cierres_publicados(obras: Sequence[int] | None = None) -> str:
    """Lo que `stg.plan_mensual` publica hoy, al mismo grano que los candidatos.

    `version` es el número de fase ORIGINAL de Sigrid (R7), así que se compara
    directamente contra `numero_fase` sin traducir nada.
    """
    return (
        "SELECT obra_id,\n"
        "       ambito_id,\n"
        "       anio_mes,\n"
        "       version AS numero_fase,\n"
        "       COALESCE(SUM(importe_origen), 0) AS acumulado\n"
        "FROM stg.plan_mensual\n"
        f"WHERE ambito_id IN ({_AMBITOS})"
        f"{_filtro_de_obras(obras)}\n"
        "GROUP BY obra_id, ambito_id, anio_mes, version\n"
        "ORDER BY 1, 2, 3, 4"
    )


def sql_telescopio(obras: Sequence[int] | None = None) -> str:
    """R16: `SUM(importe_mes)` = último `importe_origen` de cada serie.

    Devuelve **una fila** con tres números: series consecutivas comprobadas,
    cuántas de ellas no cuadran, y cuántas se han apartado por tener un hueco de
    origen. Las tres hacen falta: un «0 rotas» sobre 4 series comprobadas no
    dice lo mismo que sobre 4 millones.

    Es la consulta cara del comando —agrega `stg.plan_mensual` entera— y por eso
    admite `--obras`.
    """
    return (
        "WITH serie AS (\n"
        "    SELECT obra_id, partida_id, ambito_id, version,\n"
        "           importe_mes, importe_origen,\n"
        "           ROW_NUMBER() OVER (\n"
        "               PARTITION BY obra_id, partida_id, ambito_id\n"
        "               ORDER BY version DESC\n"
        "           ) AS desde_el_final,\n"
        "           LAG(version) OVER (\n"
        "               PARTITION BY obra_id, partida_id, ambito_id\n"
        "               ORDER BY version\n"
        "           ) AS version_previa\n"
        "    FROM stg.plan_mensual\n"
        f"    WHERE ambito_id IN ({_AMBITOS})"
        f"{_filtro_de_obras(obras)}\n"
        "),\n"
        "resumen AS (\n"
        "    SELECT obra_id, partida_id, ambito_id,\n"
        "           SUM(importe_mes) AS suma_movimientos,\n"
        "           MAX(importe_origen) FILTER (WHERE desde_el_final = 1)\n"
        "               AS ultimo_acumulado,\n"
        "           bool_or(version_previa IS NOT NULL\n"
        "                   AND version_previa <> version - 1) AS con_hueco\n"
        "    FROM serie\n"
        "    GROUP BY obra_id, partida_id, ambito_id\n"
        ")\n"
        "SELECT count(*) FILTER (WHERE NOT con_hueco) AS series_comprobadas,\n"
        "       count(*) FILTER (WHERE NOT con_hueco\n"
        "                        AND suma_movimientos <> ultimo_acumulado)\n"
        "           AS series_rotas,\n"
        "       count(*) FILTER (WHERE con_hueco) AS series_con_hueco\n"
        "FROM resumen"
    )


def sql_telescopio_detalle(
    obras: Sequence[int] | None = None, limite: int = 20
) -> str:
    """Las series que no cuadran, para pegar en un cliente y mirarlas.

    Es la diferencia entre «hay 3 series rotas» y «estas son». El mismo
    razonamiento que el `sql_detalle` de la comprobación de unicidad.
    """
    base = sql_telescopio(obras)
    consulta = base[: base.index("SELECT count(*)")]
    return (
        f"{consulta}SELECT obra_id, partida_id, ambito_id,\n"
        "       suma_movimientos, ultimo_acumulado,\n"
        "       suma_movimientos - ultimo_acumulado AS desvio\n"
        "FROM resumen\n"
        "WHERE NOT con_hueco AND suma_movimientos <> ultimo_acumulado\n"
        "ORDER BY abs(suma_movimientos - ultimo_acumulado) DESC\n"
        f"LIMIT {int(limite)}"
    )


def formatear_discrepancias(discrepancias: Sequence[Discrepancia]) -> str:
    """El informe, con obra, ámbito, mes y las fases de los dos lados (R17)."""
    if not discrepancias:
        return "0 discrepancias: cada mes de los ambitos reales publica el cierre que le toca."

    lineas = [
        f"{len(discrepancias)} discrepancia(s) entre stg.plan_mensual y la regla:",
        "",
    ]
    for d in discrepancias:
        publicado = ", ".join(map(str, d.publicado)) or "ninguno"
        esperado = ", ".join(map(str, d.esperado)) or "ninguno"
        lineas.append(
            f"KO   obra {d.obra_id} · ambito {d.ambito_id} · {d.anio_mes:%Y-%m}: "
            f"publica [{publicado}], deberia publicar [{esperado}]"
        )
        lineas.append(f"     {d.motivo}")
    return "\n".join(lineas)
