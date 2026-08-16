# etl_sigrid/infrastructure/postgres/fingerprint.py
"""
Huella comparable de las vistas de consumo, para verificar que el datamart en
Azure responde igual que el local.

El problema que resuelve el diseño en tres bloques: Sigrid está vivo, así que
la captura local y la de Azure NO son del mismo instante. Comparar el total sin
más produce diferencias inexplicables y ruido que acaba en «pues será eso». Por
eso el criterio duro se aplica solo donde significa algo:

  - **estructura**: columnas y tipos. No depende del dato → igualdad exacta.
  - **cerrado**: agregados filtrando `anio_mes <= <mes cerrado>`. Los meses
    cerrados son inmutables por definición de negocio (`fas=1..N` son cierres)
    → recuento exacto y sumas con tolerancia de céntimo.
  - **vivo**: los mismos agregados sin filtro. Cambian entre capturas por
    definición → se informan como AVISO, nunca como fallo. Ahí cae también
    `mart.v_pbi_dim_fecha`, que se genera con CURRENT_DATE y cuyas columnas
    `es_mes_actual` / `es_pasado_o_actual` dependen del día de la captura.

Lo que NO entra en los agregados: las claves sustitutas (ver
`COLUMNAS_SUSTITUTAS`). Las asigna una secuencia por orden de inserción, así
que difieren entre máquinas con el mismo dato y solo producen fallos falsos.

Los CSV siguen `docs/CONVENTIONS.md`: UTF-8 con BOM, separador `;` y coma
decimal. `escribir_csv` y `leer_csv` son simétricos.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from psycopg import sql

# Columna de periodo del proyecto: DATE con el primer día del mes.
COLUMNA_PERIODO = "anio_mes"

# Tipos de information_schema que se agregan con SUM.
TIPOS_NUMERICOS = frozenset(
    {
        "smallint",
        "integer",
        "bigint",
        "decimal",
        "numeric",
        "real",
        "double precision",
    }
)

# Claves sustitutas: columnas BIGSERIAL que llegan a las vistas de consumo.
# NO se suman. Su valor lo asigna la secuencia por orden de inserción y los
# builds no llevan ORDER BY, así que dos máquinas con el MISMO dato reparten
# otros identificadores: la suma cambia sin que haya cambiado nada. Medido
# comparando local con Azure en F-019 T13: `sum_fact_id` era la ÚNICA
# diferencia de `mart.v_pbi_fact` y `mart.v_fact_periodificado`, con idéntico
# `count` e idénticas sumas de importes. Un fallo falso.
#
# La lista es explícita y se amplía a mano a propósito: excluir por sufijo
# `_id` se llevaría por delante `obra_id`, `partida_id`, `albaran_id`,
# `proveedor_id`... que son claves NATURALES de Sigrid, estables entre
# máquinas y de las mejores señales que tiene la huella.
#
# Al añadir una vista de consumo que exponga una columna nueva alimentada por
# una secuencia (hoy quedan fuera porque no llegan a las vistas: `cierre_id`,
# `plan_id`, `regla_id`), hay que añadirla aquí.
COLUMNAS_SUSTITUTAS = frozenset({"fact_id", "fact_cat_id"})

BLOQUE_ESTRUCTURA = "estructura"
BLOQUE_CERRADO = "cerrado"
BLOQUE_VIVO = "vivo"

METRICA_COUNT = "count"

CABECERA_CSV = ("esquema", "vista", "bloque", "metrica", "valor")

# Tolerancia absoluta en euros y tolerancia relativa para importes grandes,
# donde el error de coma flotante crece con la magnitud.
TOLERANCIA_ABSOLUTA = 0.01
TOLERANCIA_RELATIVA = 1e-9


@dataclass(frozen=True, slots=True)
class Metrica:
    """Una fila del CSV de huella."""

    esquema: str
    vista: str
    bloque: str
    metrica: str
    valor: str

    @property
    def clave(self) -> tuple[str, str, str, str]:
        return (self.esquema, self.vista, self.bloque, self.metrica)

    @property
    def vista_completa(self) -> str:
        return f"{self.esquema}.{self.vista}"


@dataclass(frozen=True, slots=True)
class Diferencia:
    """Una discrepancia entre dos huellas."""

    esquema: str
    vista: str
    bloque: str
    metrica: str
    valor_a: str | None
    valor_b: str | None
    gravedad: str  # 'FALLO' o 'AVISO'
    detalle: str

    @property
    def vista_completa(self) -> str:
        return f"{self.esquema}.{self.vista}"


FALLO = "FALLO"
AVISO = "AVISO"


# ---------------------------------------------------------------------------
# Construcción de consultas
# ---------------------------------------------------------------------------

def build_estructura_query(schemas: Sequence[str]) -> str:
    """
    Consulta que devuelve columnas y tipos de todas las VISTAS de `schemas`.

    Solo vistas: las tablas intermedias no son superficie de consumo y su
    estructura no forma parte del contrato con Power BI ni con el MCP.
    """
    lista = sql.SQL(", ").join(sql.Literal(s) for s in schemas)
    consulta = sql.SQL(
        """
        SELECT c.table_schema, c.table_name, c.ordinal_position,
               c.column_name, c.data_type
        FROM information_schema.columns AS c
        JOIN information_schema.views AS v
          ON v.table_schema = c.table_schema
         AND v.table_name = c.table_name
        WHERE c.table_schema IN ({lista})
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """
    ).format(lista=lista)
    return consulta.as_string(None)


def columnas_a_sumar(columnas: Sequence[tuple[str, str]]) -> list[str]:
    """
    De `(columna, tipo)` a la lista de columnas que se agregan con SUM.

    Numéricas, menos las claves sustitutas (`COLUMNAS_SUSTITUTAS`): esas siguen
    en el bloque `estructura` —si desaparecen o cambian de tipo es un FALLO—,
    pero su suma no compara nada porque el valor lo pone una secuencia.
    """
    return [
        c
        for c, tipo in columnas
        if tipo in TIPOS_NUMERICOS and c not in COLUMNAS_SUSTITUTAS
    ]


def build_agregado_query(
    esquema: str,
    vista: str,
    columnas_numericas: Sequence[str],
    periodo_col: str | None = None,
    periodo_hasta: date | None = None,
) -> str:
    """
    Consulta de agregados de una vista: `COUNT(*)` y una `SUM` por columna
    numérica, opcionalmente filtrando por periodo.

    El filtro se aplica SOLO si la vista tiene la columna de periodo y se ha
    pedido un mes: la columna se detecta con `information_schema`, no se asume.
    """
    selects: list[sql.Composable] = [sql.SQL("COUNT(*) AS {}").format(sql.Identifier(METRICA_COUNT))]
    for columna in columnas_numericas:
        selects.append(
            sql.SQL("SUM({col}) AS {alias}").format(
                col=sql.Identifier(columna),
                alias=sql.Identifier(f"sum_{columna}"),
            )
        )

    consulta = sql.SQL("SELECT {campos} FROM {esquema}.{vista}").format(
        campos=sql.SQL(", ").join(selects),
        esquema=sql.Identifier(esquema),
        vista=sql.Identifier(vista),
    )

    if periodo_col and periodo_hasta is not None:
        consulta = sql.SQL("{base} WHERE {col} <= {hasta}").format(
            base=consulta,
            col=sql.Identifier(periodo_col),
            hasta=sql.Literal(periodo_hasta),
        )

    return consulta.as_string(None)


# ---------------------------------------------------------------------------
# Construcción de métricas
# ---------------------------------------------------------------------------

def metricas_de_estructura(filas: Sequence[tuple]) -> list[Metrica]:
    """
    Convierte el resultado de `build_estructura_query` en métricas.

    Una métrica por columna, con su posición en la clave: así una columna
    renombrada, movida de sitio o con otro tipo sale como diferencia concreta y
    no como un bloque ilegible.
    """
    metricas: list[Metrica] = []
    for esquema, vista, posicion, columna, tipo in filas:
        metricas.append(
            Metrica(
                esquema=esquema,
                vista=vista,
                bloque=BLOQUE_ESTRUCTURA,
                metrica=f"col_{int(posicion):03d}",
                valor=f"{columna}:{tipo}",
            )
        )
    return metricas


def metricas_de_agregado(
    esquema: str,
    vista: str,
    bloque: str,
    nombres: Sequence[str],
    valores: Sequence[object],
) -> list[Metrica]:
    """Convierte una fila de agregados en métricas, una por columna del SELECT."""
    return [
        Metrica(
            esquema=esquema,
            vista=vista,
            bloque=bloque,
            metrica=nombre,
            valor=formatear_valor(valor),
        )
        for nombre, valor in zip(nombres, valores, strict=True)
    ]


def formatear_valor(valor: object) -> str:
    """
    Número a texto con coma decimal (convención del proyecto). NULL → cadena
    vacía, que es distinto de 0 y debe seguir siéndolo al comparar.
    """
    if valor is None:
        return ""
    if isinstance(valor, int):
        return str(valor)
    return f"{float(valor):.6f}".replace(".", ",")


def parsear_valor(texto: str) -> float | None:
    """Inverso de `formatear_valor` para lo que sea numérico; None si no lo es."""
    if texto == "":
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def mes_a_fecha(periodo: str) -> date:
    """
    'AAAA-MM' → primer día de ese mes, que es como el proyecto guarda
    `anio_mes` (DATE con el día 1).
    """
    try:
        anio, mes = periodo.split("-")
        return date(int(anio), int(mes), 1)
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Periodo '{periodo}' no válido: se espera AAAA-MM (ej. 2026-06)."
        ) from e


def construir_huella(
    pg: object,
    schemas: Sequence[str],
    periodo_hasta: date | None = None,
) -> list[Metrica]:
    """
    Huella completa de las vistas de `schemas`.

    `pg` se recibe por duck typing (`list_view_columns` y `fetch_aggregates`)
    para poder probar esta orquestación con un cliente falso.
    """
    filas = pg.list_view_columns(schemas)  # type: ignore[attr-defined]
    metricas: list[Metrica] = metricas_de_estructura(filas)

    columnas_por_vista: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for esquema, vista, _posicion, columna, tipo in filas:
        columnas_por_vista.setdefault((esquema, vista), []).append((columna, tipo))

    for (esquema, vista), columnas in columnas_por_vista.items():
        numericas = columnas_a_sumar(columnas)
        tiene_periodo = any(c == COLUMNA_PERIODO for c, _ in columnas)
        nombres = [METRICA_COUNT, *[f"sum_{c}" for c in numericas]]

        consultas = [(BLOQUE_VIVO, build_agregado_query(esquema, vista, numericas))]
        if tiene_periodo and periodo_hasta is not None:
            consultas.append(
                (
                    BLOQUE_CERRADO,
                    build_agregado_query(
                        esquema, vista, numericas, COLUMNA_PERIODO, periodo_hasta
                    ),
                )
            )

        for bloque, consulta in consultas:
            valores = pg.fetch_aggregates(consulta)  # type: ignore[attr-defined]
            metricas.extend(
                metricas_de_agregado(esquema, vista, bloque, nombres, valores)
            )

    return metricas


# ---------------------------------------------------------------------------
# E/S del CSV
# ---------------------------------------------------------------------------

def escribir_csv(metricas: Sequence[Metrica], path: Path) -> None:
    """UTF-8 con BOM y separador `;`, según docs/CONVENTIONS.md."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(CABECERA_CSV)
        for m in metricas:
            escritor.writerow([m.esquema, m.vista, m.bloque, m.metrica, m.valor])


def leer_csv(path: Path) -> list[Metrica]:
    """Simétrico de `escribir_csv`."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        filas = list(lector)

    if not filas:
        return []
    if tuple(filas[0]) != CABECERA_CSV:
        raise ValueError(
            f"{path} no parece una huella: se esperaba la cabecera "
            f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[0])}"
        )
    return [Metrica(*fila) for fila in filas[1:] if fila]


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------

def _iguales(valor_a: str, valor_b: str, *, tolerancia: float) -> tuple[bool, str]:
    """Compara dos valores; numéricamente si ambos lo son, si no como texto."""
    num_a, num_b = parsear_valor(valor_a), parsear_valor(valor_b)
    if num_a is None or num_b is None:
        return valor_a == valor_b, "texto"

    margen = max(tolerancia, abs(num_a) * TOLERANCIA_RELATIVA)
    diferencia = abs(num_a - num_b)
    return diferencia <= margen, f"diferencia {diferencia:.6f} (margen {margen:.6f})"


def comparar(
    a: Sequence[Metrica],
    b: Sequence[Metrica],
    *,
    tolerancia: float = TOLERANCIA_ABSOLUTA,
) -> list[Diferencia]:
    """
    Diferencias entre dos huellas, con la gravedad que corresponde a su bloque.

    | Bloque | Criterio de «igual» |
    |---|---|
    | estructura | idéntica; cualquier diferencia es FALLO |
    | cerrado · count | exacto; cualquier diferencia es FALLO |
    | cerrado · sumas | `abs(a-b) <= max(0,01, abs(a)*1e-9)` |
    | vivo | las diferencias se informan como AVISO |
    """
    por_clave_a = {m.clave: m for m in a}
    por_clave_b = {m.clave: m for m in b}

    vistas_a = {(m.esquema, m.vista) for m in a}
    vistas_b = {(m.esquema, m.vista) for m in b}

    diferencias: list[Diferencia] = []

    # R34: una vista que solo está en un lado es un fallo con nombre y apellido.
    for esquema, vista in sorted(vistas_a - vistas_b):
        diferencias.append(
            Diferencia(esquema, vista, "-", "-", "presente", "ausente", FALLO,
                       "la vista existe en la primera huella y no en la segunda")
        )
    for esquema, vista in sorted(vistas_b - vistas_a):
        diferencias.append(
            Diferencia(esquema, vista, "-", "-", "ausente", "presente", FALLO,
                       "la vista existe en la segunda huella y no en la primera")
        )

    comunes = vistas_a & vistas_b

    for clave in sorted(por_clave_a.keys() | por_clave_b.keys()):
        esquema, vista, bloque, metrica = clave
        if (esquema, vista) not in comunes:
            continue  # ya reportada como vista ausente; no se repite métrica a métrica

        m_a = por_clave_a.get(clave)
        m_b = por_clave_b.get(clave)
        gravedad = AVISO if bloque == BLOQUE_VIVO else FALLO

        if m_a is None or m_b is None:
            diferencias.append(
                Diferencia(
                    esquema, vista, bloque, metrica,
                    m_a.valor if m_a else None,
                    m_b.valor if m_b else None,
                    gravedad,
                    "la métrica solo aparece en una de las dos huellas",
                )
            )
            continue

        if bloque == BLOQUE_ESTRUCTURA or metrica == METRICA_COUNT:
            # Estructura y recuentos de meses cerrados: igualdad exacta.
            if m_a.valor != m_b.valor:
                detalle = (
                    "se exige igualdad exacta"
                    if gravedad == FALLO
                    else "diferencia en el periodo vivo, esperable"
                )
                diferencias.append(
                    Diferencia(esquema, vista, bloque, metrica, m_a.valor, m_b.valor,
                               gravedad, detalle)
                )
            continue

        igual, detalle = _iguales(m_a.valor, m_b.valor, tolerancia=tolerancia)
        if not igual:
            diferencias.append(
                Diferencia(esquema, vista, bloque, metrica, m_a.valor, m_b.valor,
                           gravedad, detalle)
            )

    return diferencias


def veredicto(diferencias: Sequence[Diferencia]) -> tuple[int, str]:
    """
    Código de salida e informe. Con al menos un FALLO el código es 1; con solo
    avisos, 0 (R35).
    """
    fallos = [d for d in diferencias if d.gravedad == FALLO]
    avisos = [d for d in diferencias if d.gravedad == AVISO]

    lineas: list[str] = []
    if fallos:
        lineas.append(f"FALLOS ({len(fallos)}):")
        lineas.extend(_formatear(d) for d in fallos)
    if avisos:
        if lineas:
            lineas.append("")
        lineas.append(
            f"AVISOS ({len(avisos)}): diferencias en el bloque vivo. Se esperan: "
            f"Sigrid sigue cambiando entre las dos capturas."
        )
        lineas.extend(_formatear(d) for d in avisos)

    if not lineas:
        lineas.append("Las dos huellas son equivalentes: sin fallos ni avisos.")
    else:
        lineas.append("")
        lineas.append(
            f"Resumen: {len(fallos)} fallo(s), {len(avisos)} aviso(s)."
        )

    return (1 if fallos else 0), "\n".join(lineas)


def _formatear(d: Diferencia) -> str:
    return (
        f"  [{d.gravedad}] {d.vista_completa} · {d.bloque} · {d.metrica}: "
        f"{d.valor_a!r} vs {d.valor_b!r} — {d.detalle}"
    )
