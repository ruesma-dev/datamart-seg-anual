# etl_sigrid/infrastructure/postgres/catalogo.py
"""
Contraste contra el catálogo REAL de Postgres. Dos contrastes, no uno:

* `comparar` (F-006, R28) — **las fichas** del diccionario contra la base.
* `evaluar_construccion` (F-047) — **el SQL del repositorio** contra la base.

La puerta que corre en cada `init.sh` es **offline y heurística**: deduce lo que
el repositorio publica leyendo `sql/**` y `config/tables_sigrid.yaml`. Sirve para
que un objeto nuevo no se quede sin ficha, pero no puede ver dos cosas:

* que la **base vaya por detrás del repositorio** —un objeto que el SQL crea y
  que nadie ha construido todavía—, y
* que la base tenga algo que el repositorio **ya no crea**.

Las dos aparecieron el 2026-08-21 en la primera ejecución real: `cierre` tenía
en la base 8 de sus objetos fichados, y faltaba `cierre.v_pbi_planif_vs_real`,
que `cierre/06_views_planif_vs_real.sql` sí crea.

**LA CAUSA, encontrada el 2026-08-28 y distinta de la que este fichero decía.**
Aquí se escribió que era que `build_cierre` no registrase paso en
`_meta.etl_runs`; eso ni era cierto —`build-cierre` sí registraba, vía
`_ejecutar_paso`— ni explicaba nada: no saber cuándo se lanzó un build no borra
una vista. La causa real es que `mart/03_agg_categoria.sql` dropea
`mart.fact_seguimiento_categoria` con CASCADE, y la vista CUELGA de esa tabla.
La nocturna no dejaba de crearla: **la destruía**, y `build-cierre` no entraba
en `run-all` para recrearla. Detalle en `progress/explore_F-047.md`.

Esa vez el hallazgo salió **de rebote**, por un `except UndefinedTable` del
chequeo de unicidad, que solo recorre la superficie de consumo: **47 de 102
objetos**. Este módulo lo hace de frente y sobre todos.

No abre conexión: recibe las filas del catálogo y compara. Quien las trae es
`PostgresClient`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from etl_sigrid.domain.diccionario import Diccionario
from etl_sigrid.domain.inventario import ObjetoPublicado


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


# ===========================================================================
# El guardián de F-047 · lo que el REPOSITORIO declara, contra la base
#
# `comparar` (arriba) contrasta las FICHAS contra el catálogo. Esto contrasta
# el SQL del repositorio contra el catálogo, que es otra pregunta y la que
# nadie hacía: «lo que `sql/**` dice que crea, ¿existe de verdad?».
#
# Por ese hueco se coló F-047. `mart/03_agg_categoria.sql` dropea
# `mart.fact_seguimiento_categoria` con CASCADE, y eso se llevaba por delante
# `cierre.v_pbi_planif_vs_real`, que cuelga de esa tabla. Como `build-cierre` no
# entraba en `run-all`, nadie la recreaba: la nocturna terminaba en verde
# habiendo destruido un objeto que el repositorio declara.
# ===========================================================================


@dataclass(frozen=True, slots=True)
class EvaluacionConstruccion:
    """Qué declara el repositorio y qué de eso existe en la base."""

    #: Cuántos objetos declara el repositorio (`sql/**` + `tables_sigrid.yaml`).
    declarados: int = 0
    #: Cuántos de esos existen en la base.
    construidos: int = 0
    #: Declarados, ausentes y NO aplazados. **Bloqueante**: un build no hizo lo
    #: que el repositorio dice que hace, o algo se lo llevó por delante.
    no_construidos: tuple[ObjetoPublicado, ...] = ()
    #: `(objeto, tipo declarado, tipo en la base)`. **Bloqueante**.
    tipos_distintos: tuple[tuple[str, str, str], ...] = ()
    #: Lo que se reconoce como aún no construido (el cierre no está terminado).
    pendientes_declarados: tuple[str, ...] = ()
    #: Declarado pendiente y YA construido: el trinquete solo baja.
    pendientes_ya_construidos: tuple[str, ...] = ()
    #: Declarado pendiente y que el repositorio ni siquiera declara.
    pendientes_fantasma: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not (
            self.no_construidos
            or self.tipos_distintos
            or self.pendientes_ya_construidos
            or self.pendientes_fantasma
        )


def evaluar_construccion(
    inventario: Sequence[ObjetoPublicado],
    catalogo: Iterable[Sequence[object]],
    pendientes: Sequence[str],
) -> EvaluacionConstruccion:
    """Contrasta el inventario del repositorio contra el catálogo real.

    `catalogo` son filas `(esquema, objeto, tipo)`; el tipo se normaliza aquí
    para poder pasar directamente lo que devuelve `information_schema`.

    **Lo que esta puerta NO mira, y es deliberado**: lo que la base tiene de más.
    Un objeto publicado que el repositorio ya no crea lo denuncia
    `check-diccionario` como `PUBLICADO Y SIN FICHA`; duplicarlo aquí daría dos
    alarmas por el mismo hecho y obligaría a opinar sobre objetos creados por
    otra vía con la única información de que existen.

    **Límites del inventario, heredados de `objetos_de_sql` (R29)**: lee SQL con
    expresiones regulares. Ve los `CREATE` dentro de un `EXECUTE '...'` —el DDL
    condicional de `retenciones/00_setup.sql`, cuyas dos ramas crean el mismo
    objeto con el mismo tipo, así que no genera falso positivo— y no ve un
    objeto de nombre calculado. Un `CREATE MATERIALIZED VIEW` sí lo vería, pero
    las vistas materializadas NO aparecen en `information_schema.tables`, así
    que saldrían como no construidas: hoy no hay ninguna y
    `test_f047_guardian.py` vigila que siga siendo así.

    `pendientes` es el mismo trinquete que usa el diccionario (R27) y se le
    exige lo mismo en los dos sentidos: un pendiente ya construido o que nadie
    declara **rompe la puerta**, porque un trinquete que no baja no es un
    trinquete.
    """
    reales: dict[str, str] = {}
    for fila in catalogo:
        esquema, objeto, tipo = fila[0], fila[1], fila[2]
        reales[f"{esquema}.{objeto}"] = normalizar_tipo(str(tipo))

    declarados = {objeto.nombre: objeto for objeto in inventario}
    tolerados = set(pendientes)

    no_construidos = tuple(
        declarados[nombre]
        for nombre in sorted(declarados)
        if nombre not in reales and nombre not in tolerados
    )
    tipos_distintos = tuple(
        (nombre, declarados[nombre].tipo, reales[nombre])
        for nombre in sorted(set(declarados) & set(reales))
        if declarados[nombre].tipo != reales[nombre]
    )

    return EvaluacionConstruccion(
        declarados=len(declarados),
        construidos=len(set(declarados) & set(reales)),
        no_construidos=no_construidos,
        tipos_distintos=tipos_distintos,
        pendientes_declarados=tuple(sorted(tolerados)),
        pendientes_ya_construidos=tuple(sorted(tolerados & set(reales))),
        pendientes_fantasma=tuple(sorted(tolerados - set(declarados))),
    )


def formatear_construccion(informe: EvaluacionConstruccion) -> str:
    """El informe, escrito para que quien lo vea en rojo sepa qué abrir."""
    lineas = [
        "Lo que el repositorio DECLARA, contra el catalogo real de Postgres",
        f"  declarados: {informe.declarados}   "
        f"construidos: {informe.construidos}",
        "",
    ]

    if informe.ok and not informe.pendientes_declarados:
        lineas.append(
            "OK   todo lo que `sql/**` declara existe en la base y con su tipo."
        )
        return "\n".join(lineas)

    lineas.append(
        "OK   con pendientes declarados." if informe.ok else "KO"
    )
    lineas.append("")

    if informe.no_construidos:
        lineas.append(
            f"DECLARADO Y NO CONSTRUIDO ({len(informe.no_construidos)}). Un build "
            f"no hizo lo que el repositorio dice, o algo se lo llevo por delante:"
        )
        for objeto in informe.no_construidos:
            lineas.append(f"  - {objeto.nombre}  [{objeto.tipo}]  {objeto.origen}")
        lineas.append(
            "    Relanza el build de ese esquema, o declaralo en "
            "`config/objetos_pendientes.yaml` si aun no toca construirlo."
        )
        lineas.append("")

    if informe.tipos_distintos:
        lineas.append(f"TIPO QUE NO CASA ({len(informe.tipos_distintos)}):")
        for nombre, declarado, real in informe.tipos_distintos:
            lineas.append(
                f"  - {nombre}: el SQL crea un(a) `{declarado}` y la base tiene "
                f"un(a) `{real}`"
            )
        lineas.append("")

    if informe.pendientes_ya_construidos:
        lineas.append(
            "PENDIENTES QUE YA EXISTEN. El trinquete solo baja: borralos de "
            "`config/objetos_pendientes.yaml`:"
        )
        lineas.extend(f"  - {n}" for n in informe.pendientes_ya_construidos)
        lineas.append("")

    if informe.pendientes_fantasma:
        lineas.append(
            "PENDIENTES QUE EL REPOSITORIO NO DECLARA. Inflan el trinquete sin "
            "aplazar nada:"
        )
        lineas.extend(f"  - {n}" for n in informe.pendientes_fantasma)
        lineas.append("")

    if informe.pendientes_declarados:
        lineas.append(
            f"  · pendientes declarados: {len(informe.pendientes_declarados)} "
            f"(trinquete: solo baja)"
        )

    return "\n".join(lineas)
