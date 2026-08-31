# etl_sigrid/infrastructure/postgres/huella_ampliada.py
"""
F-052 · Las huellas 3 y 4, en solo lectura y a CSV (T28, T29, R11).

Lado de infraestructura de `domain/huella_ampliada.py`, igual que
`huella_obras.py` lo es de `domain/huella.py`: lee, agrega y escribe **fuera de
la base**; comparar y dictaminar es el dominio.

## Huella 3 · dimensión

`stg.partidas` resumida **por obra**. Las seis columnas que definen dónde está
una partida dentro del árbol —`codigo_partida`, `capitulo_padre_id`,
`capitulo_raiz_id`, `categoria`, `nivel` y `ruta_capitulos`— se concatenan por
fila, se ordenan por `partida_id` y se pasan por `md5`. Si una sola partida se
mueve, cambia el resumen de su obra.

**El `ORDER BY` dentro del `string_agg` no es cosmética**: sin él Postgres puede
devolver las filas en distinto orden entre dos ejecuciones y el `md5` cambiaría
sin que se haya movido nada. Una huella que da falsos positivos se acaba
ignorando, que es peor que no tenerla.

**Y los `COALESCE` tampoco.** `capitulo_padre_id` es NULL en las raíces, y en
Postgres concatenar un NULL devuelve NULL: sin ellos, el resumen de cualquier
obra con raíz sería NULL, la comparación no compararía nada y **parecería
verde**.

## Huella 4 · cierre

`cierre.fact_cierre_mensual` por obra x mes x concepto, con las cuatro métricas
que Negocio mira. Es la capa que esta feature mueve entera en la 0599: DIRECTOS
pasa de 0,00 € a ~2,62 M €.

## Las dos, de una pasada

Ninguna necesita tramos: la 3 devuelve una fila por obra (del orden de 700) y la
4, una por obra x mes x concepto (unas decenas de miles). No hay ventanas, así
que no derraman a los temporales del disco compartido, que es lo que obligaba a
trocear la huella de `stg`.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from etl_sigrid.domain.huella_ampliada import (
    FORMATO_CIERRE,
    FORMATO_DIMENSION,
    FilaAmpliada,
    FormatoHuella,
    formato_de,
)

# Reexportadas a propósito: las mismas sentencias previas y la misma lista de
# palabras prohibidas que las demás comprobaciones de solo lectura. Copiarlas
# sería abrir la puerta a que una copia perdiera el `transaction_read_only`.
from etl_sigrid.infrastructure.postgres.cierres_sql import (  # noqa: F401
    PALABRAS_DE_ESCRITURA,
)
from etl_sigrid.infrastructure.postgres.unicidad_sql import (  # noqa: F401
    sentencias_previas,
)

#: Segundos por consulta. Las dos son agregaciones completas sobre tablas
#: medianas —390.501 y ~24.000 filas—, así que no hace falta el margen de la
#: huella de `stg`; y sigue acotado, porque el servidor es compartido.
TIMEOUT_POR_CONSULTA_S = 300

#: Las seis columnas que definen dónde está una partida dentro del árbol. Es la
#: lista de `design.md` §7, huella 3, y el orden importa porque entra en el
#: `md5`: cambiarlo invalida cualquier huella capturada antes.
COLUMNAS_DEL_SITIO = (
    "p.codigo_partida",
    "p.capitulo_padre_id",
    "p.capitulo_raiz_id",
    "p.categoria",
    "p.nivel",
    "p.ruta_capitulos",
)


def sql_huella_dimension() -> str:
    """El árbol de `stg.partidas` resumido por obra (huella 3)."""
    partes = " || '|' ||\n            ".join(
        f"COALESCE({c}::TEXT, '')" for c in COLUMNAS_DEL_SITIO
    )
    return (
        "SELECT p.obra_id,\n"
        "       COALESCE(MAX(o.codigo_obra), '') AS codigo_obra,\n"
        "       count(*) AS partidas,\n"
        "       count(DISTINCT p.capitulo_raiz_id) AS raices,\n"
        "       COALESCE(max(p.nivel), 0) AS nivel_max,\n"
        "       md5(string_agg(\n"
        f"            COALESCE(p.partida_id::TEXT, '') || '|' ||\n"
        f"            {partes},\n"
        # El orden estable es lo que hace que el md5 signifique algo.
        "            E'\\n' ORDER BY p.partida_id)) AS resumen\n"
        "FROM stg.partidas p\n"
        "LEFT JOIN stg.obras o ON o.obra_id = p.obra_id\n"
        "GROUP BY p.obra_id\n"
        "ORDER BY p.obra_id"
    )


def sql_huella_cierre() -> str:
    """El cierre por obra x mes x concepto (huella 4)."""
    return (
        "SELECT f.obra_id,\n"
        "       COALESCE(MAX(f.codigo_obra), '') AS codigo_obra,\n"
        "       f.anio_mes AS periodo,\n"
        "       f.concepto,\n"
        "       count(*) AS filas,\n"
        "       COALESCE(SUM(f.ejecutado_origen), 0)  AS ejecutado_origen,\n"
        "       COALESCE(SUM(f.ejecutado_mes), 0)     AS ejecutado_mes,\n"
        "       COALESCE(SUM(f.final_importe), 0)     AS final_importe,\n"
        "       COALESCE(SUM(f.pendiente_importe), 0) AS pendiente_importe\n"
        "FROM cierre.fact_cierre_mensual f\n"
        "GROUP BY f.obra_id, f.anio_mes, f.concepto\n"
        "ORDER BY 1, 3, 4"
    )


#: Qué consulta corresponde a cada formato. Se resuelve aquí y no en el comando
#: para que añadir una huella sea declarar un formato y su SQL, y nada más.
_CONSULTAS = {
    FORMATO_DIMENSION.nombre: sql_huella_dimension,
    FORMATO_CIERRE.nombre: sql_huella_cierre,
}


def _texto(valor) -> str:
    """Un valor de la base como el texto que va al CSV.

    Coma decimal —convención de Ruesma para un CSV que se abre en Excel ES— y
    fechas en ISO. La comparación se hace luego sobre estas mismas cadenas, así
    que escribir y leer con la misma función es lo que garantiza que el ida y
    vuelta no invente una diferencia.
    """
    if valor is None:
        return ""
    if isinstance(valor, Decimal | float):
        return str(valor).replace(".", ",")
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _a_fila(formato: FormatoHuella, cruda: Sequence) -> FilaAmpliada:
    if len(cruda) != len(formato.cabecera):
        raise ValueError(
            f"la consulta de la huella `{formato.nombre}` ha devuelto "
            f"{len(cruda)} columna(s) y su cabecera declara "
            f"{len(formato.cabecera)}: {', '.join(formato.cabecera)}"
        )
    por_nombre = {c: _texto(v) for c, v in zip(formato.cabecera, cruda, strict=True)}
    return FilaAmpliada(
        codigo_obra=por_nombre["codigo_obra"],
        clave=tuple(por_nombre[c] for c in formato.columnas_clave),
        valores=tuple((c, por_nombre[c]) for c in formato.columnas_valor),
    )


def construir_huella_ampliada(
    pg, formato: FormatoHuella, timeout_s: int = TIMEOUT_POR_CONSULTA_S
) -> tuple[FilaAmpliada, ...]:
    """Lee la huella entera. **Solo lectura: no escribe ni una fila.**

    De una pasada y sin tramos: ninguna de las dos usa ventanas, así que no
    derraman a los temporales del disco que comparten `albaranes` y `partes`.
    """
    sql = _CONSULTAS[formato.nombre]()
    return tuple(_a_fila(formato, f) for f in pg.filas_solo_lectura(sql, timeout_s))


def escribir_csv_ampliada(
    formato: FormatoHuella, filas: Sequence[FilaAmpliada], path: Path
) -> None:
    """UTF-8 con BOM y `;` de separador, como el resto de CSV de la casa."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(formato.cabecera)
        for fila in filas:
            valores = dict(zip(formato.columnas_clave, fila.clave, strict=True))
            valores.update(fila.como_dict)
            escritor.writerow([valores[c] for c in formato.cabecera])


def leer_csv_ampliada(path: Path) -> tuple[FormatoHuella, tuple[FilaAmpliada, ...]]:
    """Lee una huella escrita por `escribir_csv_ampliada`, y **reconoce cuál es**.

    La cabecera decide el formato. Un CSV con otras columnas —o con las mismas
    en otro orden— se rechaza en vez de leerse mal en silencio, que en una prueba
    de no-regresión sería la peor forma posible de dar verde.
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        try:
            cabecera = next(lector)
        except StopIteration:
            raise ValueError(f"{path} esta vacio: no tiene ni cabecera") from None

        formato = formato_de(cabecera)
        if formato is None:
            conocidas = "; ".join(
                f"{f.nombre}: {','.join(f.cabecera)}"
                for f in (FORMATO_DIMENSION, FORMATO_CIERRE)
            )
            raise ValueError(
                f"{path} no tiene la cabecera de ninguna huella ampliada de "
                f"F-052. Encontrada: {';'.join(cabecera)}. Conocidas -> {conocidas}"
            )

        filas = tuple(
            _a_fila(formato, fila) for fila in lector if fila
        )
    return formato, filas
