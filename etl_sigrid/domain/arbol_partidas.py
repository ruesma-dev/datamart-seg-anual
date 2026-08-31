# etl_sigrid/domain/arbol_partidas.py
"""
F-052 · El árbol de partidas de Sigrid, reconstruido (R1 a R6). **Dominio puro.**

Es la misma regla que ejecuta el `WITH RECURSIVE` de
`sql/stg/04_partidas.sql`, escrita aquí para poder probarla **sin tocar la
base**. Mismo patrón que `domain/cierres.py` frente a `cierres_sql.py`: la regla
se prueba con fixtures y el SQL se comprueba sobre su texto.

## El defecto que arregla

El filtro `AND h.cod <> ''` de la rama recursiva no decidía qué se publica:
decidía **por dónde se desciende**. Tres capítulos intermedios con el código en
blanco bajo la raíz `CD` de la 0599 cortaban el recorrido y **amputaban 1.323
partidas** —2.624.793,46 € de coste directo y el 100 % de la venta de esa obra—.
Aquí el filtro baja al final: el nodo sin código **se atraviesa** y **no se
publica**.

## Las cuatro reglas, y por qué colapsar y no publicar

1. **Se desciende a través del nodo sin código** (R1). La rama **raíz** no se
   toca (DA-1): un `padide = 0` con `cod = ''` sigue sin abrir árbol.
2. **El nodo sin código no sale como fila** (R2).
3. **Se colapsa**: el hijo de un nodo no publicable cuelga del **ancestro
   publicado más cercano**, y ni la ruta ni el nivel avanzan al atravesarlo
   (R3, R4). Publicarlo obligaría a darle un `codigo_partida` nulo o sintético y
   **abriría la puerta a doble conteo** si ese capítulo tuviera importes propios;
   colapsarlo no añade ni un euro y deja la relación
   `capitulo_padre_id → partida_id` apuntando a una fila que sí existe.
4. **Los ciclos se cortan** con la lista de visitados **y** un tope de
   profundidad (DA-3), y quedan **denunciados** en vez de perderse. Hay 12
   partidas en ciclo vivas en `raw.obrparpar`, una de ellas en la 0686
   VALDEBEBAS, que sigue en curso: sin corta-ciclos, relajar el filtro es un
   recursivo infinito dentro de una nocturna de 3 h 45.

## Nada se cae en silencio

Todo nodo acaba en **una** de las cuatro listas de `Arbol`. La cuarta,
`inalcanzables`, no la pedía el diseño: se añade porque una partida cuyo padre
no existe —o cuya raíz no abre árbol— no cabía en ninguna de las otras tres y
habría vuelto a desaparecer sin dejar rastro, que es exactamente el modo de
fallo que esta feature existe para eliminar. Hoy mide **cero casos** (causas (a)
y (c) del informe de exploración), y ese cero es un dato, no un descuido.

**La categoría NO se calcula aquí.** Es una heurística sobre
`capitulo_raiz_cod` que vive en el SQL y que esta feature no toca; duplicarla
crearía una segunda fuente de verdad para algo que nadie ha pedido mover. Lo que
sí viaja es `capitulo_raiz_cod`, que es su entrada.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

#: Tope duro de saltos del recorrido, como respaldo del array de visitados
#: (DA-3). La profundidad real máxima medida el 2026-08-31 es de **7 niveles,
#: con cero partidas de nivel 8 o más sobre 389.178**, así que deja 33 de margen
#: y no trunca nada legítimo. Es el mismo número que el `a.nivel_bruto < 40` de
#: `sql/stg/04_partidas.sql`, y `tests/test_f052_sql.py` cruza los dos.
TOPE_DE_PROFUNDIDAD = 40

#: El separador de `ruta_capitulos`, tal y como lo parte
#: `mart.v_pbi_dim_partida_niveles` con `string_to_array(..., ' > ')`.
SEPARADOR_DE_RUTA = " > "


@dataclass(frozen=True, slots=True)
class Nodo:
    """Una fila de `raw.obrparpar`, con lo justo para reconstruir el árbol.

    `cod` puede ser `None` (no llega nunca al árbol) o la **cadena vacía**, que
    es el caso de esta feature: `length(cod) = 0`, no nulo.
    """

    ide: int
    padide: int | None
    cod: str | None
    obra_id: int

    @property
    def es_raiz(self) -> bool:
        """`padide = 0` o nulo **y** con código: la rama raíz no se relaja (DA-1)."""
        return (self.padide or 0) == 0 and bool(self.cod)

    @property
    def publicable(self) -> bool:
        """Sale como fila de `stg.partidas`. Es el filtro que baja al final."""
        return self.cod is not None and self.cod != ""


@dataclass(frozen=True, slots=True)
class Partida:
    """Una fila de `stg.partidas` tal y como la deja el recorrido."""

    partida_id: int
    obra_id: int
    codigo_partida: str
    #: El **ancestro publicado más cercano**, no siempre el padre de Sigrid.
    capitulo_padre_id: int | None
    capitulo_raiz_id: int
    capitulo_raiz_cod: str
    ruta_capitulos: str
    #: Cuenta **sólo ancestros publicados**, así que cumple el invariante
    #: `len(ruta.split(' > ')) == nivel + 1` del que vive
    #: `mart.v_pbi_dim_partida_niveles`.
    nivel: int


@dataclass(frozen=True, slots=True)
class Arbol:
    """El resultado del recorrido, con **todo** nodo clasificado.

    Las cuatro listas son disjuntas y su unión son los nodos de entrada. Ese
    invariante es la garantía de que no se pierde nada en silencio, y lo fija un
    test.
    """

    publicadas: tuple[Partida, ...]
    #: Los nodos alcanzados cuyo `cod` es la cadena vacía: se atraviesan y no se
    #: publican. Medidos: **7**, en tres obras (0599, 0618, 0613).
    descartadas_sin_codigo: tuple[int, ...]
    #: Los nodos que no se alcanzan porque su cadena de `padide` da vueltas.
    #: Medidos: **12**, en tres obras (0630, 0686, 0565).
    en_ciclo: tuple[int, ...]
    #: Los nodos que no se alcanzan por cualquier otro motivo: padre inexistente,
    #: o una raíz que no abre árbol. Medidos: **0**.
    inalcanzables: tuple[int, ...]

    def por_id(self, partida_id: int) -> Partida | None:
        return next(
            (p for p in self.publicadas if p.partida_id == partida_id), None
        )


@dataclass(frozen=True, slots=True)
class _Paso:
    """El estado que el recorrido arrastra al bajar un nivel.

    Es literalmente lo que propagan las columnas del CTE: `publicable`,
    `padre_publicado_id`, `visitados` y `nivel_bruto`.
    """

    ide: int
    publicable: bool
    padre_publicado_id: int | None
    capitulo_raiz_id: int
    capitulo_raiz_cod: str
    ruta_capitulos: str
    nivel: int
    #: Saltos dados desde la raíz, contando también los nodos colapsados. Es
    #: contra esto —y no contra `nivel`— contra lo que muerde el tope, porque un
    #: ciclo de nodos sin código no haría avanzar `nivel` nunca.
    nivel_bruto: int
    visitados: frozenset[int]


def _hay_ciclo(nodo: Nodo, por_ide: dict[int, Nodo]) -> bool:
    """¿La cadena de `padide` de este nodo da vueltas?

    Se sube, que es como se midió el informe de exploración: un nodo está «en
    ciclo» si al remontar sus ancestros se vuelve a pisar un `ide` ya visto. Un
    hermano que cuelga de una pareja en bucle también lo está —los nueve de la
    0565— porque su camino a la raíz pasa por el bucle y no termina nunca.
    """
    visto: set[int] = set()
    actual: Nodo | None = nodo
    while actual is not None:
        if actual.ide in visto:
            return True
        visto.add(actual.ide)
        padre_id = actual.padide or 0
        if padre_id == 0:
            return False
        actual = por_ide.get(padre_id)
    return False


def construir_arbol(nodos: Iterable[Nodo]) -> Arbol:
    """Recorre el árbol entero y clasifica **todos** los nodos.

    Recorrido en anchura desde las raíces, que es lo que hace el `WITH
    RECURSIVE`. Se para en dos sitios y por dos motivos distintos:

    * **el array de visitados**, que es exacto y corta el ciclo en el primer
      nodo repetido;
    * **el tope de profundidad**, que es el respaldo: si algún día el array
      fallara —o si apareciera una cadena legítima absurdamente honda— el
      recorrido termina igual en vez de comerse la nocturna.
    """
    lista = list(nodos)
    por_ide: dict[int, Nodo] = {n.ide: n for n in lista}

    hijos: dict[int, list[Nodo]] = {}
    for nodo in lista:
        padre_id = nodo.padide or 0
        if padre_id:
            hijos.setdefault(padre_id, []).append(nodo)

    publicadas: list[Partida] = []
    sin_codigo: list[int] = []
    alcanzados: set[int] = set()

    frontera: list[_Paso] = []
    for nodo in lista:
        if not nodo.es_raiz:
            continue
        alcanzados.add(nodo.ide)
        cod = nodo.cod or ""
        frontera.append(
            _Paso(
                ide=nodo.ide,
                publicable=True,
                padre_publicado_id=None,
                capitulo_raiz_id=nodo.ide,
                capitulo_raiz_cod=cod,
                ruta_capitulos=cod,
                nivel=0,
                nivel_bruto=0,
                visitados=frozenset({nodo.ide}),
            )
        )
        publicadas.append(
            Partida(
                partida_id=nodo.ide,
                obra_id=nodo.obra_id,
                codigo_partida=cod,
                capitulo_padre_id=None,
                capitulo_raiz_id=nodo.ide,
                capitulo_raiz_cod=cod,
                ruta_capitulos=cod,
                nivel=0,
            )
        )

    while frontera:
        siguiente: list[_Paso] = []
        for paso in frontera:
            if paso.nivel_bruto >= TOPE_DE_PROFUNDIDAD:
                continue
            for hijo in hijos.get(paso.ide, ()):
                if hijo.cod is None or hijo.ide in paso.visitados:
                    continue

                alcanzados.add(hijo.ide)
                # El ancestro publicado más cercano: el padre si publicaba, y si
                # no, el que el padre traía heredado (R3).
                padre_publicado = (
                    paso.ide if paso.publicable else paso.padre_publicado_id
                )

                if hijo.publicable:
                    ruta = paso.ruta_capitulos + SEPARADOR_DE_RUTA + hijo.cod
                    nivel = paso.nivel + 1
                    publicadas.append(
                        Partida(
                            partida_id=hijo.ide,
                            obra_id=hijo.obra_id,
                            codigo_partida=hijo.cod,
                            capitulo_padre_id=padre_publicado,
                            capitulo_raiz_id=paso.capitulo_raiz_id,
                            capitulo_raiz_cod=paso.capitulo_raiz_cod,
                            ruta_capitulos=ruta,
                            nivel=nivel,
                        )
                    )
                else:
                    # Colapsado: se atraviesa, no se publica, y ni la ruta ni el
                    # nivel avanzan (R2, R3, R4).
                    ruta = paso.ruta_capitulos
                    nivel = paso.nivel
                    sin_codigo.append(hijo.ide)

                siguiente.append(
                    _Paso(
                        ide=hijo.ide,
                        publicable=hijo.publicable,
                        padre_publicado_id=padre_publicado,
                        capitulo_raiz_id=paso.capitulo_raiz_id,
                        capitulo_raiz_cod=paso.capitulo_raiz_cod,
                        ruta_capitulos=ruta,
                        nivel=nivel,
                        nivel_bruto=paso.nivel_bruto + 1,
                        visitados=paso.visitados | {hijo.ide},
                    )
                )
        frontera = siguiente

    en_ciclo: list[int] = []
    inalcanzables: list[int] = []
    for nodo in lista:
        if nodo.ide in alcanzados:
            continue
        (en_ciclo if _hay_ciclo(nodo, por_ide) else inalcanzables).append(nodo.ide)

    return Arbol(
        publicadas=tuple(publicadas),
        descartadas_sin_codigo=tuple(sin_codigo),
        en_ciclo=tuple(en_ciclo),
        inalcanzables=tuple(inalcanzables),
    )
