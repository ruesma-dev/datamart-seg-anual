# tests/test_f052_arbol.py
"""
F-052 · La regla del árbol de partidas, en dominio puro (R1 a R6).

**Por qué existe este fichero y no basta con probar el SQL.** El arreglo de esta
feature vive en un `WITH RECURSIVE` de `sql/stg/04_partidas.sql` que corre contra
`psql-albaranes-rs9k2`, compartido con `albaranes` y `partes` **en producción**, y
dentro de una nocturna de 3 h 45. Relajar el filtro de código vacío sin
corta-ciclos sobre las **12 partidas en ciclo** que hoy viven en `raw.obrparpar`
es un bucle infinito en esa nocturna. Aquí la misma regla se ejecuta **sin base
de datos**, así que el corta-ciclos se prueba antes de que nadie lo despliegue.

**Las fixtures no están inventadas.** Salen de `progress/explore_F-052.md`,
medido contra la base el 2026-08-31:

* el subárbol de la 0599 TANATORIO MAJADAHONDA: la raíz `CD` (ide 274277) con
  tres hijos de código **vacío** —280353 «FASE 1 …», 280354 «FASE 2 - OBRA
  CIVIL» y 280356 «FASE 2 - INSTALACIONES»— más el 307427 (`cod='999'`), el
  único que hoy sobrevive;
* los dos **auto-bucles** (`padide = ide`): 310512 «CHIMENEA IGNIFUGA» de la
  0630 y 375474 «LEGALIZACIÓN Y PUESTA EN MARCHA» de la 0686;
* el **bucle mutuo** de la 0565: 279988 (`20.12`) ↔ 279997 (`20.12.09`).

Ni red ni BBDD: sólo estructuras en memoria.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.arbol_partidas import (
    TOPE_DE_PROFUNDIDAD,
    Nodo,
    construir_arbol,
)

# ---------------------------------------------------------------------------
# Fixtures medidas: la 0599 y los tres ciclos
# ---------------------------------------------------------------------------

OBRA_0599 = 1442383
OBRA_0630 = 630630
OBRA_0686 = 686686
OBRA_0565 = 565565

#: La raíz `CD COSTES DIRECTOS` de la 0599 lleva un espacio al final en Sigrid.
COD_RAIZ_CD = "CD "


def _subarbol_0599() -> list[Nodo]:
    """`CD` → tres «FASE …» con `cod=''` → sus hijos, más el 999 que sí publica.

    Es el caso que amputa 1.323 partidas: los tres nodos intermedios no se
    publican, pero el recorrido **tiene que atravesarlos**.
    """
    return [
        Nodo(ide=274277, padide=0, cod=COD_RAIZ_CD, obra_id=OBRA_0599),
        # Los tres capítulos por fase de obra, con el código en blanco.
        Nodo(ide=280353, padide=274277, cod="", obra_id=OBRA_0599),
        Nodo(ide=280354, padide=274277, cod="", obra_id=OBRA_0599),
        Nodo(ide=280356, padide=274277, cod="", obra_id=OBRA_0599),
        # El único hijo directo de CD que hoy sobrevive.
        Nodo(ide=307427, padide=274277, cod="999", obra_id=OBRA_0599),
        # Descendientes de las fases: hoy amputados.
        Nodo(ide=280400, padide=280353, cod="01", obra_id=OBRA_0599),
        Nodo(ide=280401, padide=280400, cod="01.01", obra_id=OBRA_0599),
        Nodo(ide=280500, padide=280354, cod="02", obra_id=OBRA_0599),
        Nodo(ide=280600, padide=280356, cod="03", obra_id=OBRA_0599),
    ]


def _auto_bucles() -> list[Nodo]:
    """Los dos `padide = ide` medidos. No cuelgan de ninguna raíz."""
    return [
        Nodo(ide=310512, padide=310512, cod="15.03", obra_id=OBRA_0630),
        Nodo(ide=375474, padide=375474, cod="99.01", obra_id=OBRA_0686),
    ]


def _bucle_mutuo_0565() -> list[Nodo]:
    """279988 ↔ 279997, que arrastra nueve hermanos colgando de la pareja."""
    nodos = [
        Nodo(ide=279988, padide=279997, cod="20.12", obra_id=OBRA_0565),
        Nodo(ide=279997, padide=279988, cod="20.12.09", obra_id=OBRA_0565),
    ]
    nodos += [
        Nodo(ide=280000 + i, padide=279988, cod=f"20.12.{i:02d}", obra_id=OBRA_0565)
        for i in range(1, 10)
    ]
    return nodos


def _obra_sana() -> list[Nodo]:
    """Una rama sin un solo código vacío ni ciclo: el testigo de R6."""
    return [
        Nodo(ide=900, padide=0, cod="CI", obra_id=777),
        Nodo(ide=901, padide=900, cod="10", obra_id=777),
        Nodo(ide=902, padide=901, cod="10.01", obra_id=777),
    ]


def _arbol_completo():
    return construir_arbol(
        _subarbol_0599() + _auto_bucles() + _bucle_mutuo_0565() + _obra_sana()
    )


def _publicadas_por_id(arbol) -> dict[int, object]:
    return {p.partida_id: p for p in arbol.publicadas}


# ---------------------------------------------------------------------------
# R1 · se desciende A TRAVÉS del capítulo sin código
# ---------------------------------------------------------------------------


def test_f052_r1_el_recorrido_desciende_a_traves_de_un_capitulo_sin_codigo():
    """Las 1.323 partidas amputadas de la 0599 vuelven al árbol.

    Es el arreglo entero en una línea: el filtro de código vacío decide qué se
    publica, no por dónde se desciende.
    """
    publicadas = _publicadas_por_id(_arbol_completo())

    for ide in (280400, 280401, 280500, 280600):
        assert ide in publicadas, (
            f"la partida {ide} cuelga de un capítulo con cod='' y sigue amputada"
        )


# ---------------------------------------------------------------------------
# R2 · el capítulo sin código sigue SIN publicarse
# ---------------------------------------------------------------------------


def test_f052_r2_el_capitulo_sin_codigo_no_se_publica_como_fila():
    arbol = _arbol_completo()

    publicadas = {p.partida_id for p in arbol.publicadas}
    for ide in (280353, 280354, 280356):
        assert ide not in publicadas, (
            f"{ide} tiene cod='' y NO puede salir como fila de stg.partidas"
        )
    assert set(arbol.descartadas_sin_codigo) == {280353, 280354, 280356}


# ---------------------------------------------------------------------------
# R3 · el padre publicado y el nivel saltan el nodo colapsado
# ---------------------------------------------------------------------------


def test_f052_r3_el_padre_es_el_ancestro_publicado_mas_cercano():
    """Los hijos de las tres «FASE …» pasan a colgar de `CD` (ide 274277)."""
    publicadas = _publicadas_por_id(_arbol_completo())

    assert publicadas[280400].capitulo_padre_id == 274277
    assert publicadas[280500].capitulo_padre_id == 274277
    assert publicadas[280600].capitulo_padre_id == 274277
    # Y un nieto sigue colgando de su padre real, que sí se publica.
    assert publicadas[280401].capitulo_padre_id == 280400


def test_f052_r3_el_nivel_cuenta_solo_ancestros_publicados():
    publicadas = _publicadas_por_id(_arbol_completo())

    assert publicadas[274277].nivel == 0
    assert publicadas[280400].nivel == 1, "el capítulo vacío no puede sumar nivel"
    assert publicadas[280401].nivel == 2


def test_f052_r3_la_raiz_se_hereda_a_traves_del_nodo_colapsado():
    """`capitulo_raiz_cod` es la ENTRADA de la heurística de categoría: si no
    bajara por el nodo vacío, las 1.323 partidas quedarían sin categoría."""
    publicadas = _publicadas_por_id(_arbol_completo())

    for ide in (280400, 280401, 280500, 280600):
        assert publicadas[ide].capitulo_raiz_id == 274277
        assert publicadas[ide].capitulo_raiz_cod == COD_RAIZ_CD


# ---------------------------------------------------------------------------
# R4 · la ruta no lleva NUNCA un segmento vacío
# ---------------------------------------------------------------------------


def test_f052_r4_la_ruta_no_tiene_segmentos_vacios():
    """El efecto 3 del informe —`'CD >  > 01.01'` y un nivel en blanco en el
    «Árbol Presupuesto» de Power BI— queda eliminado por construcción."""
    publicadas = _publicadas_por_id(_arbol_completo())

    assert publicadas[280400].ruta_capitulos == f"{COD_RAIZ_CD} > 01"
    assert publicadas[280401].ruta_capitulos == f"{COD_RAIZ_CD} > 01 > 01.01"

    for partida in _arbol_completo().publicadas:
        assert " >  > " not in partida.ruta_capitulos
        assert all(
            segmento != "" for segmento in partida.ruta_capitulos.split(" > ")
        ), f"{partida.partida_id} tiene un segmento vacío: {partida.ruta_capitulos!r}"


# ---------------------------------------------------------------------------
# R5 · los ciclos se cortan y quedan denunciados
# ---------------------------------------------------------------------------


def test_f052_r5_un_auto_bucle_no_cuelga_el_recorrido_y_queda_denunciado():
    arbol = _arbol_completo()

    publicadas = {p.partida_id for p in arbol.publicadas}
    assert 310512 not in publicadas
    assert 375474 not in publicadas
    assert 310512 in arbol.en_ciclo
    assert 375474 in arbol.en_ciclo


def test_f052_r5_el_bucle_mutuo_de_la_0565_arrastra_a_sus_nueve_hermanos():
    """279988 ↔ 279997 y los nueve que cuelgan de ellos: once nodos que no son
    alcanzables desde ninguna raíz y que hoy se pierden en silencio."""
    arbol = _arbol_completo()

    en_ciclo = set(arbol.en_ciclo)
    assert {279988, 279997} <= en_ciclo
    for i in range(1, 10):
        assert 280000 + i in en_ciclo, (
            f"el hermano {280000 + i} cuelga del bucle y también se pierde"
        )


def test_f052_r5_los_doce_nodos_en_ciclo_son_los_medidos():
    """Las 12 partidas en ciclo de `progress/explore_F-052.md`, ni una más."""
    arbol = _arbol_completo()

    assert len(arbol.en_ciclo) == 12


def test_f052_r5_el_tope_de_profundidad_corta_una_cadena_absurda():
    """Cinturón y tirantes (DA-3): aunque el array de visitados es exacto, una
    cadena legítima más honda que el tope se corta en vez de crecer sin fin.

    La profundidad real máxima medida es de **7 niveles**, así que el tope de 40
    deja 33 de margen y no trunca nada de lo que hay hoy.
    """
    nodos = [Nodo(ide=1, padide=0, cod="CD", obra_id=1)]
    nodos += [
        Nodo(ide=i, padide=i - 1, cod=f"n{i}", obra_id=1)
        for i in range(2, TOPE_DE_PROFUNDIDAD + 10)
    ]

    arbol = construir_arbol(nodos)

    niveles = [p.nivel for p in arbol.publicadas]
    assert max(niveles) <= TOPE_DE_PROFUNDIDAD, (
        "el recorrido pasó del tope de profundidad"
    )
    assert len(arbol.publicadas) < len(nodos), "el tope no cortó nada"


# ---------------------------------------------------------------------------
# R6 · lo que hoy sale bien sale exactamente igual
# ---------------------------------------------------------------------------


def test_f052_r6_una_rama_sin_vacios_ni_ciclos_sale_identica():
    """El cambio es **estrictamente aditivo**: relajar el filtro sólo añade
    caminos, nunca altera uno existente. Es la condición bloqueante de R11."""
    solo_sana = construir_arbol(_obra_sana())
    con_todo = construir_arbol(
        _subarbol_0599() + _auto_bucles() + _bucle_mutuo_0565() + _obra_sana()
    )

    de_la_sana = {p.partida_id: p for p in con_todo.publicadas if p.obra_id == 777}
    assert de_la_sana == {p.partida_id: p for p in solo_sana.publicadas}

    hoja = de_la_sana[902]
    assert hoja.capitulo_padre_id == 901
    assert hoja.capitulo_raiz_id == 900
    assert hoja.ruta_capitulos == "CI > 10 > 10.01"
    assert hoja.nivel == 2


def test_f052_r6_el_hijo_con_codigo_de_la_raiz_cd_no_se_mueve():
    """La 307427 (`cod='999'`) es la única de la 0599 que hoy cuelga de `CD`
    directamente: después del arreglo tiene que seguir exactamente donde estaba."""
    publicadas = _publicadas_por_id(_arbol_completo())

    assert publicadas[307427].capitulo_padre_id == 274277
    assert publicadas[307427].nivel == 1
    assert publicadas[307427].ruta_capitulos == f"{COD_RAIZ_CD} > 999"


# ---------------------------------------------------------------------------
# Casos de borde (T3)
# ---------------------------------------------------------------------------


def test_f052_r3_dos_nodos_vacios_encadenados_se_colapsan_los_dos():
    nodos = [
        Nodo(ide=1, padide=0, cod="CD", obra_id=5),
        Nodo(ide=2, padide=1, cod="", obra_id=5),
        Nodo(ide=3, padide=2, cod="", obra_id=5),
        Nodo(ide=4, padide=3, cod="07", obra_id=5),
    ]

    arbol = construir_arbol(nodos)
    publicadas = _publicadas_por_id(arbol)

    assert set(arbol.descartadas_sin_codigo) == {2, 3}
    assert publicadas[4].capitulo_padre_id == 1
    assert publicadas[4].nivel == 1
    assert publicadas[4].ruta_capitulos == "CD > 07"


def test_f052_r2_un_nodo_vacio_que_es_hoja_solo_desaparece():
    nodos = [
        Nodo(ide=1, padide=0, cod="CD", obra_id=5),
        Nodo(ide=2, padide=1, cod="", obra_id=5),
    ]

    arbol = construir_arbol(nodos)

    assert [p.partida_id for p in arbol.publicadas] == [1]
    assert arbol.descartadas_sin_codigo == (2,)
    assert arbol.en_ciclo == ()


def test_f052_r1_una_raiz_sin_codigo_no_es_raiz_y_no_se_inventa_una():
    """DA-1: la rama raíz **no se toca**. Un `padide = 0` con `cod=''` no abre
    árbol, y su descendencia queda inalcanzable en vez de colgar de la nada.

    Hoy no existe ni un caso: los 7 nodos con `cod=''` son todos intermedios. El
    día que aparezca uno, el guardián de `check-cobertura` lo denuncia.
    """
    nodos = [
        Nodo(ide=1, padide=0, cod="", obra_id=5),
        Nodo(ide=2, padide=1, cod="01", obra_id=5),
    ]

    arbol = construir_arbol(nodos)

    assert arbol.publicadas == ()
    assert 2 in arbol.inalcanzables


def test_f052_r5_un_padre_inexistente_no_se_pierde_en_silencio():
    """El modo de fallo que esta feature existe para eliminar: si una partida no
    llega al árbol, tiene que quedar dicho en alguna de las tres listas."""
    nodos = [
        Nodo(ide=1, padide=0, cod="CD", obra_id=5),
        Nodo(ide=9, padide=999_999, cod="01", obra_id=5),
    ]

    arbol = construir_arbol(nodos)

    assert 9 in arbol.inalcanzables
    assert 9 not in {p.partida_id for p in arbol.publicadas}


@pytest.mark.parametrize(
    "nodos",
    [
        pytest.param(_subarbol_0599(), id="0599"),
        pytest.param(_obra_sana(), id="sana"),
        pytest.param(
            _subarbol_0599() + _auto_bucles() + _bucle_mutuo_0565() + _obra_sana(),
            id="todo",
        ),
    ],
)
def test_f052_r4_el_invariante_de_la_ruta_se_cumple_en_toda_partida(nodos):
    """`cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1`.

    Es de lo que vive `mart.v_pbi_dim_partida_niveles`: si un segmento vacío se
    colara, el «Árbol Presupuesto» de Power BI mostraría un nivel en blanco.
    """
    for partida in construir_arbol(nodos).publicadas:
        assert len(partida.ruta_capitulos.split(" > ")) == partida.nivel + 1, (
            f"{partida.partida_id}: ruta {partida.ruta_capitulos!r} contra "
            f"nivel {partida.nivel}"
        )


def test_f052_r6_todo_nodo_acaba_en_una_de_las_cuatro_listas():
    """Nada se cae en silencio: publicada, sin código, en ciclo o inalcanzable."""
    nodos = _subarbol_0599() + _auto_bucles() + _bucle_mutuo_0565() + _obra_sana()
    arbol = construir_arbol(nodos)

    clasificados = (
        {p.partida_id for p in arbol.publicadas}
        | set(arbol.descartadas_sin_codigo)
        | set(arbol.en_ciclo)
        | set(arbol.inalcanzables)
    )
    assert clasificados == {n.ide for n in nodos}
