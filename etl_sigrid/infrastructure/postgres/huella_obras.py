# etl_sigrid/infrastructure/postgres/huella_obras.py
"""
F-042 · La huella de obra x ámbito x mes, en solo lectura y a CSV (R22).

Es el lado de infraestructura de la prueba que decide. Lee, agrega y escribe
**fuera de la base**; comparar y dictaminar es `domain/huella.py`.

## Las tres fuentes, y por qué son tres

* `--desde stg` — agrega `stg.plan_mensual`. Es la huella del **antes**.
* `--desde stg --propuesta` — **reejecuta la rama de reales ya modificada como
  `SELECT`, sin materializar**, y la agrega al vuelo. Es la huella del
  **después** sin escribir ni una fila en un servidor que comparten `albaranes`
  y `partes` en producción.
* `--desde mart` — agrega `mart.fact_seguimiento_categoria`, que es lo que Power
  BI y el MCP leen de verdad.

**El agregado de `stg` lleva los mismos `JOIN` que `mart`** (`stg.obras` y
`stg.partidas`, los dos `INNER`). No es un detalle: sin ellos la huella de `stg`
contaría partidas que `mart/02_build_fact.sql` descarta y dejaría de ser
predictiva.

**Con ellos, en los ámbitos REALES (3 y 7) el agregado de `stg` es exactamente
el que `mart.fact_seguimiento_categoria` publica** —medido el 2026-08-29 entre
las dos huellas: desviación **0 en 8.243 celdas**—, porque de `stg` a esa tabla
solo hay una proyección y un `SUM` por las mismas dimensiones.

**Y NO vale para los master (8 y 11).** Ahí `stg.plan_mensual` guarda **todas**
las versiones y `mart` publica **solo la vigente de cada mes**, así que este
agregado suma la obra tantas veces como versiones tenga: 3.504 celdas difieren y
en la 0644 son 43,6 M€ frente a 1,3 M€. **No invalida la comparación**
—`comparar-huellas` enfrenta `stg` contra `stg` y el artefacto se cancela—, pero
quien compare una huella de `stg` con una de `mart` sin saber esto creerá haber
encontrado un defecto de 40 millones.

## El texto de la propuesta no es una copia

El SQL del «después» sale de **`08_plan_mensual.sql` tal cual**, recortado entre
sus dos marcadores y envuelto en un `WITH` propio. Si fuera una copia de la
lógica, la prueba que decide estaría midiendo un texto distinto del que va a
correr esa noche, que es la forma más cara posible de equivocarse.

## Ámbitos 8 y 11

En la huella propuesta **son los actuales, copiados**: la rama master no se toca
—lo fija por hash `tests/test_f042_sql.py`— y hoy no tiene ni una clave
duplicada. Reejecutarla sería pagar el `CROSS JOIN LATERAL unnest` que provocó
el incidente de F-019 para obtener, por construcción, el mismo número.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from etl_sigrid.domain.huella import AMBITOS_DE_LA_HUELLA, FilaHuella
from etl_sigrid.domain.tramos import planificar_tramos
from etl_sigrid.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

#: Los dos marcadores que acotan la rama de reales dentro de
#: `sql/stg/08_plan_mensual.sql`. Son un contrato con ese fichero:
#: `tests/test_f042_sql.py` comprueba que siguen ahí, una sola vez y en orden.
MARCADOR_INICIO_REALES = "/*F042_INICIO_REALES*/"
MARCADOR_FIN_REALES = "/*F042_FIN_REALES*/"

#: El marcador de tramo de F-019, que viaja DENTRO del bloque de reales.
MARCADOR_FILTRO_OBRAS = "/*F019_FILTRO_OBRAS*/"

#: Segundos por consulta. Un tramo de la huella propuesta encadena las mismas
#: ventanas que el build, así que se le da margen; sigue acotado porque el
#: servidor es compartido.
TIMEOUT_POR_TRAMO_S = 900

_AMBITOS = ", ".join(str(a) for a in AMBITOS_DE_LA_HUELLA)

CABECERA_CSV = (
    "obra_id",
    "codigo_obra",
    "ambito_id",
    "periodo",
    "filas",
    "versiones",
    "importe_mes",
    "importe_origen",
    # F-052, T27. Vacia en las huellas de `stg` y de la propuesta, que no bajan
    # a ese grano; con valor en la de `mart`.
    "categoria",
)


class HuellaAbortada(RuntimeError):  # noqa: N818 - nombres en espanol
    """La huella paró a propósito: la puerta de disco dijo que no.

    Se distingue de cualquier otro error para que quede claro que fue una
    decisión del guardián y no un fallo inesperado. No deja nada a medias porque
    no escribe nada: el CSV se vuelca al final.
    """


# ---------------------------------------------------------------------------
# El bloque reutilizable de 08_plan_mensual.sql
# ---------------------------------------------------------------------------


def bloque_de_reales(sql_texto: str) -> str:
    """El texto de la rama de reales, entre sus dos marcadores.

    Levanta `ValueError` si falta alguno o si vienen al revés: antes que
    ejecutar media rama —que sería SQL inválido o, peor, SQL válido que mide
    otra cosa— se para aquí.
    """
    inicio = sql_texto.find(MARCADOR_INICIO_REALES)
    fin = sql_texto.find(MARCADOR_FIN_REALES)
    if inicio < 0 or fin < 0 or fin < inicio:
        raise ValueError(
            f"no se encuentran los marcadores {MARCADOR_INICIO_REALES} y "
            f"{MARCADOR_FIN_REALES} en orden dentro del SQL de plan_mensual. La "
            f"huella propuesta REUTILIZA ese texto y sin el no puede medir la "
            f"logica que se va a ejecutar de verdad"
        )
    return sql_texto[inicio + len(MARCADOR_INICIO_REALES) : fin]


def filtro_de_tramo(obras: Sequence[int]) -> str:
    """`ARRAY[...]::BIGINT[]` con las obras del tramo, validadas como enteros.

    No se reutiliza `build_stg_step.componer_sql_tramo` porque aquella exige el
    marcador **dos veces** (una por rama) y aquí solo viaja la rama de reales.
    Lo que sí se reutiliza es su regla dura: `type(obra) is not int` y no
    `isinstance`, porque `bool` es subclase de `int` y `ARRAY[True]` no es una
    lista de obras.
    """
    if not obras:
        raise ValueError(
            "Tramo sin obras: no se compone ni se ejecuta nada. El planificador "
            "de tramos no deberia producir tramos vacios."
        )
    for obra in obras:
        if type(obra) is not int:
            raise TypeError(
                f"El filtro de tramo solo admite identificadores de obra "
                f"enteros; llego {obra!r} ({type(obra).__name__})."
            )
    return f"ARRAY[{', '.join(str(o) for o in obras)}]::BIGINT[]"


# ---------------------------------------------------------------------------
# Las tres consultas
# ---------------------------------------------------------------------------

#: `array_to_string(array_agg(DISTINCT ... ORDER BY ...))` y no `string_agg`,
#: porque `string_agg` ordenaría el texto y dejaría «10|2|21». Aquí el orden es
#: numérico, que es como se leen los números de fase.
def _versiones(columna: str) -> str:
    return f"array_to_string(array_agg(DISTINCT {columna} ORDER BY {columna}), '|')"


def sql_huella_stg(obras: Sequence[int] | None = None) -> str:
    """La huella ANTES: `stg.plan_mensual` agregada, con los `JOIN` de `mart`."""
    filtro = f"\n  AND pm.obra_id = ANY ({filtro_de_tramo(obras)})" if obras else ""
    return (
        "SELECT pm.obra_id,\n"
        "       o.codigo_obra,\n"
        "       pm.ambito_id,\n"
        "       pm.anio_mes AS periodo,\n"
        "       count(*) AS filas,\n"
        f"       {_versiones('pm.version')} AS versiones,\n"
        "       COALESCE(SUM(pm.importe_mes), 0)    AS importe_mes,\n"
        "       COALESCE(SUM(pm.importe_origen), 0) AS importe_origen\n"
        "FROM stg.plan_mensual pm\n"
        "JOIN stg.obras    o ON o.obra_id    = pm.obra_id\n"
        "JOIN stg.partidas p ON p.partida_id = pm.partida_id\n"
        f"WHERE pm.ambito_id IN ({_AMBITOS})"
        f"{filtro}\n"
        "GROUP BY pm.obra_id, o.codigo_obra, pm.ambito_id, pm.anio_mes\n"
        "ORDER BY 1, 3, 4"
    )


def sql_huella_mart(obras: Sequence[int] | None = None) -> str:
    """La huella de lo que Power BI y el MCP leen de verdad.

    **Baja a CATEGORIA (F-052, T27), y no es un adorno.** Agregando sólo por
    obra x ámbito x mes, una partida que cambie de categoría —una CI que pase a
    CD— deja el total de la obra exactamente igual y **no se ve**. Lo que se
    rompe entonces no es el total: es el desglose, que es lo que Power BI
    dibuja. Con `categoria` en el grano, ese movimiento aparece como dos celdas
    que cambian en direcciones opuestas.
    """
    filtro = f"\n  AND fc.obra_id = ANY ({filtro_de_tramo(obras)})" if obras else ""
    return (
        "SELECT fc.obra_id,\n"
        "       MAX(fc.codigo_obra) AS codigo_obra,\n"
        "       fc.ambito_id,\n"
        "       fc.anio_mes AS periodo,\n"
        "       count(*) AS filas,\n"
        # `mart.fact_seguimiento_categoria` no publica el numero de fase: agrega
        # por categoria. La numeracion, por tanto, solo se puede mirar en `stg`.
        "       ''::TEXT AS versiones,\n"
        "       COALESCE(SUM(fc.importe_mes), 0)    AS importe_mes,\n"
        "       COALESCE(SUM(fc.importe_origen), 0) AS importe_origen,\n"
        "       fc.categoria\n"
        "FROM mart.fact_seguimiento_categoria fc\n"
        f"WHERE fc.ambito_id IN ({_AMBITOS})"
        f"{filtro}\n"
        "GROUP BY fc.obra_id, fc.ambito_id, fc.anio_mes, fc.categoria\n"
        "ORDER BY 1, 3, 4, 9"
    )


def sql_huella_propuesta(sql_plan_mensual: str, obras: Sequence[int]) -> str:
    """La huella DESPUÉS: la rama de reales ya modificada, como `SELECT`.

    Sin `INSERT`, sin `CREATE`, sin `TEMP`: el resultado sale por el cursor y se
    agrega al vuelo. El bloque de CTE se toma **literalmente** del fichero que
    ejecuta el build, con el marcador de tramo sustituido.

    Solo cubre los ámbitos 3 y 7. Los master se copian de la huella actual: su
    rama no se toca y reejecutarla costaría el `unnest` del incidente de F-019
    para obtener, por construcción, el mismo número.
    """
    bloque = bloque_de_reales(sql_plan_mensual)
    if bloque.count(MARCADOR_FILTRO_OBRAS) != 1:
        raise ValueError(
            f"el bloque de reales debe traer el marcador {MARCADOR_FILTRO_OBRAS} "
            f"exactamente una vez y trae {bloque.count(MARCADOR_FILTRO_OBRAS)}: "
            f"sin el, la huella se ejecutaria sobre la base entera de una pasada"
        )
    bloque = bloque.replace(MARCADOR_FILTRO_OBRAS, filtro_de_tramo(obras))

    return (
        f"WITH{bloque}\n"
        "SELECT rc.obra_id,\n"
        "       o.codigo_obra,\n"
        "       rc.ambito_id,\n"
        "       rc.anio_mes AS periodo,\n"
        "       count(*) AS filas,\n"
        f"       {_versiones('rc.mes_fase_num')} AS versiones,\n"
        # Los mismos redondeos que el INSERT del build: si la huella redondeara
        # distinto, inventaria diferencias de centimos que el build no tiene.
        "       COALESCE(SUM(ROUND(rc.importe_mes_round::NUMERIC, 2)), 0)\n"
        "           AS importe_mes,\n"
        "       COALESCE(SUM(ROUND(rc.importe_origen_round::NUMERIC, 2)), 0)\n"
        "           AS importe_origen\n"
        "FROM reales_con_lag rc\n"
        "JOIN stg.obras    o ON o.obra_id    = rc.obra_id\n"
        "JOIN stg.partidas p ON p.partida_id = rc.partida_id\n"
        "GROUP BY rc.obra_id, o.codigo_obra, rc.ambito_id, rc.anio_mes\n"
        "ORDER BY 1, 3, 4"
    )


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------


def _a_filas(resultado: Sequence[Sequence]) -> list[FilaHuella]:
    return [
        FilaHuella(
            obra_id=int(f[0]),
            codigo_obra=str(f[1] or ""),
            ambito_id=int(f[2]),
            periodo=f[3] if isinstance(f[3], date) else date.fromisoformat(str(f[3])),
            filas=int(f[4]),
            versiones=str(f[5] or ""),
            importe_mes=Decimal(str(f[6])),
            importe_origen=Decimal(str(f[7])),
            # Solo la huella de `mart` trae la novena columna; `stg` y la
            # propuesta agregan por encima de la categoria y la dejan vacia.
            categoria=str(f[8] or "") if len(f) > 8 else "",
        )
        for f in resultado
    ]


def construir_huella(
    pg,
    settings,
    *,
    desde: str,
    propuesta: bool,
    sql_plan_mensual: str | None = None,
    timeout_s: int = TIMEOUT_POR_TRAMO_S,
) -> list[FilaHuella]:
    """Lee la huella completa. **Solo lectura: no escribe ni una fila.**

    `mart` se lee de una pasada: son 24.684 filas y ninguna ventana. `stg` y la
    propuesta van **por tramos de obras**, con la puerta de disco de F-019
    **antes de cada tramo**, porque sus ventanas ordenan por (obra, partida,
    ámbito) y derraman a temporales sobre un disco compartido. No se inventa
    mecanismo nuevo: es el mismo que usa el build.
    """
    if desde == "mart":
        if propuesta:
            raise ValueError(
                "`--propuesta` solo tiene sentido con `--desde stg`: la huella "
                "propuesta se calcula reejecutando la rama de reales de "
                "plan_mensual, y `mart` es el resultado de haberla materializado"
            )
        return _a_filas(pg.filas_solo_lectura(sql_huella_mart(), timeout_s))

    if desde != "stg":
        raise ValueError(f"`--desde` admite 'stg' o 'mart', y ha llegado {desde!r}")

    total_gb = settings.postgres.disco_total_gb
    limite_pct = settings.postgres.disco_limite_pct
    tramos = planificar_tramos(
        pg.fetch_pesos_plan_mensual(), settings.postgres.tramo_max_filas
    )

    filas: list[FilaHuella] = []
    for tramo in tramos:
        etiqueta = f"{tramo.indice}/{len(tramos)}"
        try:
            ocupacion_pct = pg.medir_ocupacion_disco_pct(total_gb)
        except Exception as error:
            raise HuellaAbortada(
                f"no se pudo medir la ocupacion del disco antes del tramo "
                f"{etiqueta}: {error}. No se ejecuta a ciegas."
            ) from error
        if ocupacion_pct > limite_pct:
            raise HuellaAbortada(
                f"ocupacion del disco {ocupacion_pct} % por encima del limite "
                f"{limite_pct} % antes del tramo {etiqueta}: el servidor es "
                f"compartido y la huella para aqui."
            )

        t0 = datetime.now()
        if propuesta:
            # Reales (3, 7) con la logica NUEVA, sin materializar...
            nuevas = _a_filas(
                pg.filas_solo_lectura(
                    sql_huella_propuesta(sql_plan_mensual or "", tramo.obras),
                    timeout_s,
                )
            )
            # ...y los master (8, 11) COPIADOS de la huella actual, porque su
            # rama no cambia. Se filtran del agregado de stg del mismo tramo.
            actuales = _a_filas(
                pg.filas_solo_lectura(sql_huella_stg(tramo.obras), timeout_s)
            )
            nuevas += [f for f in actuales if f.ambito_id in (8, 11)]
            del_tramo = nuevas
        else:
            del_tramo = _a_filas(
                pg.filas_solo_lectura(sql_huella_stg(tramo.obras), timeout_s)
            )

        filas.extend(del_tramo)
        logger.info(
            "huella_obras_tramo",
            tramo=etiqueta,
            obras=len(tramo.obras),
            celdas=len(del_tramo),
            propuesta=propuesta,
            ocupacion_pct=ocupacion_pct,
            duracion_s=(datetime.now() - t0).total_seconds(),
        )

    filas.sort(key=lambda f: f.clave)
    return filas


# ---------------------------------------------------------------------------
# El CSV, fuera de la base
# ---------------------------------------------------------------------------


def _numero(valor: Decimal) -> str:
    """Coma decimal, convención de Ruesma para un CSV que se abre en Excel ES.

    Con `;` de separador no hay ambigüedad posible, y `leer_csv` deshace la
    conversión al leer: el ida y vuelta no pierde un céntimo.
    """
    return str(valor).replace(".", ",")


def escribir_csv(filas: Sequence[FilaHuella], path: Path) -> None:
    """UTF-8 con BOM, `;` de separador y coma decimal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(CABECERA_CSV)
        for fila in filas:
            escritor.writerow(
                [
                    fila.obra_id,
                    fila.codigo_obra,
                    fila.ambito_id,
                    fila.periodo.isoformat(),
                    fila.filas,
                    fila.versiones,
                    _numero(fila.importe_mes),
                    _numero(fila.importe_origen),
                    fila.categoria,
                ]
            )


def leer_csv(path: Path) -> list[FilaHuella]:
    """Lee una huella escrita por `escribir_csv`.

    La cabecera se comprueba: un CSV con otras columnas —o con las mismas en
    otro orden— se rechaza en vez de leerse mal en silencio, que en una prueba
    de no-regresión sería la peor forma de dar verde.
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        try:
            cabecera = next(lector)
        except StopIteration:
            raise ValueError(f"{path} esta vacio: no tiene ni cabecera") from None
        if tuple(cabecera) != CABECERA_CSV:
            raise ValueError(
                f"{path} no tiene la cabecera de una huella de F-042. Esperada: "
                f"{';'.join(CABECERA_CSV)}. Encontrada: {';'.join(cabecera)}"
            )
        return [
            FilaHuella(
                obra_id=int(fila[0]),
                codigo_obra=fila[1],
                ambito_id=int(fila[2]),
                periodo=date.fromisoformat(fila[3]),
                filas=int(fila[4]),
                versiones=fila[5],
                importe_mes=Decimal(fila[6].replace(",", ".")),
                importe_origen=Decimal(fila[7].replace(",", ".")),
                categoria=fila[8] if len(fila) > 8 else "",
            )
            for fila in lector
            if fila
        ]
