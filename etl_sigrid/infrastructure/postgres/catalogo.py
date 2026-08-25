# etl_sigrid/infrastructure/postgres/catalogo.py
"""
Contraste del diccionario contra el catálogo REAL de Postgres (F-006, R28).

La puerta que corre en cada `init.sh` es **offline y heurística**: deduce lo que
el repositorio publica leyendo `sql/**` y `config/tables_sigrid.yaml`. Sirve para
que un objeto nuevo no se quede sin ficha, pero no puede ver dos cosas:

* que la **base vaya por detrás del repositorio** —un objeto que el SQL crea y
  que nadie ha construido todavía—, y
* que la base tenga algo que el repositorio **ya no crea**.

Las dos aparecieron el 2026-08-21 en la primera ejecución real: `cierre` tenía
en la base 8 de sus objetos fichados, y faltaba `cierre.v_pbi_planif_vs_real`,
que `cierre/06_views_planif_vs_real.sql` sí crea. La causa es que `build_cierre`
no registra paso en `_meta.etl_runs`, así que ni siquiera se sabía cuándo se
lanzó por última vez.

Esa vez el hallazgo salió **de rebote**, por un `except UndefinedTable` del
chequeo de unicidad, que solo recorre la superficie de consumo: **47 de 102
objetos**. Este módulo lo hace de frente y sobre los **102**.

No abre conexión: recibe las filas del catálogo y compara. Quien las trae es
`PostgresClient`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from etl_sigrid.domain.diccionario import Diccionario


@dataclass(frozen=True, slots=True)
class Discrepancia:
    """Una diferencia entre lo fichado y lo que la base tiene de verdad."""

    objeto: str
    clase: str  # sin_ficha | huerfana | tipo_distinto
    detalle: str


@dataclass(frozen=True, slots=True)
class InformeCatalogo:
    comprobados: int
    en_catalogo: int
    discrepancias: tuple[Discrepancia, ...]

    @property
    def ok(self) -> bool:
        return not self.discrepancias


#: Cómo se llama en la ficha cada `table_type` del catálogo.
_TIPOS = {"BASE TABLE": "tabla", "VIEW": "vista", "FOREIGN": "tabla", "LOCAL TEMPORARY": "tabla"}


def normalizar_tipo(table_type: str) -> str:
    """`information_schema` habla en inglés y en mayúsculas; la ficha, no."""
    return _TIPOS.get(table_type.upper(), table_type.lower())


def comparar(
    dicc: Diccionario, catalogo: Iterable[Sequence[object]]
) -> InformeCatalogo:
    """Compara las 102 fichas contra lo que la base tiene.

    `catalogo` son filas `(esquema, objeto, tipo)`, ya normalizadas o no: el
    tipo se normaliza aquí para que el llamante pueda pasar directamente lo que
    devuelve `information_schema`.

    Tres clases de discrepancia, y las tres importan por motivos distintos:

    * **`sin_ficha`**: la base publica algo que el diccionario no documenta. Es
      un agujero de cobertura: el MCP lo verá y no sabrá qué es.
    * **`huerfana`**: el diccionario documenta algo que la base no tiene. O la
      base va por detrás del repositorio —lo normal en los cuatro esquemas de
      refresco manual— o la ficha sobra.
    * **`tipo_distinto`**: la ficha dice tabla y es vista, o al revés. Cambia lo
      que se puede hacer con el objeto.
    """
    reales: dict[str, str] = {}
    for fila in catalogo:
        esquema, objeto, tipo = fila[0], fila[1], fila[2]
        reales[f"{esquema}.{objeto}"] = normalizar_tipo(str(tipo))

    fichadas = {f.nombre: f.tipo for f in dicc.fichas}
    discrepancias: list[Discrepancia] = []

    for nombre in sorted(set(reales) - set(fichadas)):
        discrepancias.append(
            Discrepancia(
                objeto=nombre,
                clase="sin_ficha",
                detalle=(
                    f"la base publica un(a) {reales[nombre]} que el diccionario "
                    f"no documenta: el MCP lo vera y no sabra que es"
                ),
            )
        )

    for nombre in sorted(set(fichadas) - set(reales)):
        discrepancias.append(
            Discrepancia(
                objeto=nombre,
                clase="huerfana",
                detalle=(
                    f"fichado como {fichadas[nombre]} y NO existe en la base. O "
                    f"falta lanzar el build de `{nombre.split('.')[0]}` —la base "
                    f"va por detras del repositorio— o la ficha sobra"
                ),
            )
        )

    for nombre in sorted(set(reales) & set(fichadas)):
        if reales[nombre] != fichadas[nombre]:
            discrepancias.append(
                Discrepancia(
                    objeto=nombre,
                    clase="tipo_distinto",
                    detalle=(
                        f"la ficha dice `{fichadas[nombre]}` y la base tiene "
                        f"un(a) `{reales[nombre]}`"
                    ),
                )
            )

    return InformeCatalogo(
        comprobados=len(fichadas),
        en_catalogo=len(reales),
        discrepancias=tuple(discrepancias),
    )


def formatear(informe: InformeCatalogo) -> str:
    """El informe, escrito para que la corrección sea evidente."""
    lineas = [
        f"Diccionario contra el catalogo real de Postgres",
        f"  fichas: {informe.comprobados}   objetos en la base: {informe.en_catalogo}",
        "",
    ]
    if informe.ok:
        lineas.append(
            "OK   biyeccion exacta: ni un objeto publicado sin ficha, ni una "
            "ficha sin objeto, ni un tipo que no case."
        )
        return "\n".join(lineas)

    for clase, titulo in (
        ("sin_ficha", "PUBLICADO Y SIN FICHA"),
        ("huerfana", "FICHADO Y NO EXISTE"),
        ("tipo_distinto", "TIPO QUE NO CASA"),
    ):
        delclase = [d for d in informe.discrepancias if d.clase == clase]
        if not delclase:
            continue
        lineas.append(f"{titulo} ({len(delclase)}):")
        lineas.extend(f"  - {d.objeto}: {d.detalle}" for d in delclase)
        lineas.append("")

    lineas.append(
        f"{len(informe.discrepancias)} discrepancia(s). La puerta offline no "
        f"puede verlas: lee el SQL del repositorio, no el catalogo."
    )
    return "\n".join(lineas)
