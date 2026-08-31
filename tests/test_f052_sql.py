# tests/test_f052_sql.py
"""
F-052 · El SQL del árbol de partidas, comprobado sobre su texto (R1 a R5).

`sql/stg/04_partidas.sql` no se puede ejecutar aquí: escribe en `stg.partidas`
de un Postgres compartido con `albaranes` y `partes` **en producción**. Lo que sí
se puede es fijar por escrito las cinco cosas que el arreglo tiene que hacer, de
forma que un refactor que se lleve por delante cualquiera de ellas rompa la suite
y no la nocturna. Es el mismo criterio que `test_f042_sql.py` con
`08_plan_mensual.sql`.

**La regla equivalente, ejecutable, está en `tests/test_f052_arbol.py`.** Este
fichero comprueba que el SQL dice lo mismo que ella; aquel comprueba que lo que
dice es correcto. Ninguno de los dos sobra: el bloque B es SQL y la campaña de
mutación —eximida por el humano el 2026-08-31— nunca lo cubrió.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pytest

from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG
from etl_sigrid.domain.arbol_partidas import TOPE_DE_PROFUNDIDAD

RUTA = DIRECTORIO_SQL_STG / "04_partidas.sql"

#: El filtro que causó el daño. En la rama **raíz** se queda (DA-1); en la rama
#: **recursiva** es justo lo que hay que quitar.
FILTRO_DE_CODIGO_VACIO = "cod <> ''"


@lru_cache(maxsize=1)
def _sql() -> str:
    return RUTA.read_text(encoding="utf-8")


def _rama_raiz() -> str:
    """De `WITH RECURSIVE` hasta el `UNION ALL`."""
    texto = _sql()
    return texto[texto.index("WITH RECURSIVE") : texto.index("UNION ALL")]


def _rama_recursiva() -> str:
    """Del `UNION ALL` hasta el CTE que categoriza: es la que se relaja."""
    texto = _sql()
    return texto[
        texto.index("UNION ALL") : texto.index("arbol_categorizado AS (")
    ]


def _insert() -> str:
    texto = _sql()
    return texto[texto.index("INSERT INTO stg.partidas") :]


# ---------------------------------------------------------------------------
# R1 · el descenso se relaja, la raíz NO
# ---------------------------------------------------------------------------


def test_f052_r1_la_rama_recursiva_ya_no_exige_codigo_no_vacio():
    """El arreglo entero. Un capítulo con `cod = ''` deja de cortar el subárbol.

    `AND h.cod IS NOT NULL` se queda: un código nulo nunca formó parte de una
    ruta y seguir descendiendo por él no recuperaría nada.
    """
    rama = _rama_recursiva()

    filtro = rama[rama.index("WHERE") :]

    assert f"h.{FILTRO_DE_CODIGO_VACIO}" not in filtro, (
        "la rama recursiva sigue filtrando por código no vacío: el subárbol de "
        "un capítulo sin código se sigue amputando"
    )
    assert "h.cod IS NOT NULL" in rama


def test_f052_r1_da1_la_rama_raiz_conserva_su_filtro():
    """DA-1: la raíz **no se toca**.

    Los 7 nodos con `cod = ''` medidos son **todos intermedios**: relajar la raíz
    no recuperaría ni una fila hoy y obligaría a inventar reglas de
    `capitulo_raiz_id` sin un solo caso real que las valide.
    """
    raiz = _rama_raiz()

    assert "p.cod IS NOT NULL" in raiz
    assert "p.cod <> ''" in raiz, (
        "la rama raíz ha perdido su filtro: eso es DA-1 al revés"
    )


# ---------------------------------------------------------------------------
# R2, R3 · publicable y padre publicado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("columna", ("publicable", "padre_publicado_id", "visitados"))
def test_f052_r3_el_cte_propaga_las_tres_columnas_nuevas(columna: str):
    """Las tres viajan por las **dos** ramas del recursivo: si una sólo estuviera
    en la recursiva, Postgres rechazaría el `UNION ALL` por número de columnas,
    pero si estuviera sólo con otro nombre pasaría a valer otra cosa."""
    assert f"AS {columna}" in _rama_raiz(), f"la rama raíz no propaga {columna}"
    assert f"AS {columna}" in _rama_recursiva(), (
        f"la rama recursiva no propaga {columna}"
    )


def test_f052_r3_el_padre_publicado_salta_el_nodo_colapsado():
    """`CASE WHEN a.publicable THEN a.partida_id ELSE a.padre_publicado_id END`:
    el padre si publicaba, y si no, el que el padre ya traía heredado."""
    rama = _rama_recursiva()

    assert re.search(
        r"CASE\s+WHEN\s+a\.publicable\s+THEN\s+a\.partida_id\s+"
        r"ELSE\s+a\.padre_publicado_id\s+END",
        rama,
        re.I | re.S,
    ), "no se resuelve el ancestro publicado más cercano"


def test_f052_r2_el_insert_solo_publica_lo_publicable():
    """Los 7 nodos con `cod = ''` siguen sin salir como fila, igual que hoy."""
    insert = _insert()

    assert re.search(r"WHERE\s+publicable", insert, re.I), (
        "el INSERT no filtra por `publicable`: los capítulos sin código se "
        "publicarían, que es justo lo que abre la puerta al doble conteo"
    )


def test_f052_r3_el_insert_toma_el_padre_del_ancestro_publicado():
    """`capitulo_padre_id` deja de ser el `padide` de Sigrid."""
    insert = _insert()

    assert "padre_publicado_id" in insert, (
        "el INSERT sigue escribiendo el padre crudo de Sigrid en "
        "capitulo_padre_id, así que los 36 hijos de las tres «FASE …» "
        "apuntarían a una fila que no existe en stg.partidas"
    )


# ---------------------------------------------------------------------------
# R4 · la ruta y el nivel sólo avanzan en nodos publicables
# ---------------------------------------------------------------------------


def test_f052_r4_la_ruta_no_avanza_en_un_nodo_sin_codigo():
    """Sin esto sale `'CD >  > 01.01'` y `mart.v_pbi_dim_partida_niveles`
    genera un nivel en blanco en el «Árbol Presupuesto» de Power BI."""
    rama = _rama_recursiva()

    assert re.search(
        r"CASE\s+WHEN\s+h\.cod\s*<>\s*''\s+THEN\s+a\.ruta_capitulos\s*\|\|"
        r"\s*' > '\s*\|\|\s*h\.cod\s+ELSE\s+a\.ruta_capitulos\s+END",
        rama,
        re.I | re.S,
    ), "la ruta se concatena siempre, también al atravesar el nodo colapsado"


def test_f052_r4_el_nivel_solo_suma_en_un_nodo_publicable():
    """El invariante `cardinality(split(ruta)) = nivel + 1` se sostiene sobre
    esto: si el nivel sumara en el nodo vacío, dejaría de cumplirse."""
    rama = _rama_recursiva()

    assert re.search(
        r"a\.nivel\s*\+\s*CASE\s+WHEN\s+h\.cod\s*<>\s*''\s+THEN\s+1\s+ELSE\s+0\s+END",
        rama,
        re.I | re.S,
    ), "el nivel sigue sumando uno por cada salto, publicable o no"


# ---------------------------------------------------------------------------
# R5 · el corta-ciclos, que es lo que impide colgar la nocturna
# ---------------------------------------------------------------------------


def test_f052_r5_la_recursiva_no_vuelve_a_pisar_un_nodo_ya_visitado():
    """Array de visitados (DA-3 a). Es la mitad exacta del corta-ciclos.

    Sin él, relajar el filtro con **12 partidas en ciclo** vivas en
    `raw.obrparpar` es un `WITH RECURSIVE` infinito dentro de una nocturna de
    3 h 45.
    """
    rama = _rama_recursiva()

    assert re.search(
        r"NOT\s*\(\s*h\.ide\s*=\s*ANY\s*\(\s*a\.visitados\s*\)\s*\)", rama, re.I
    ), "no se comprueba la lista de visitados"
    assert re.search(r"a\.visitados\s*\|\|\s*h\.ide", rama, re.I), (
        "la lista de visitados no crece al bajar: comprobarla no serviría de nada"
    )


def test_f052_r5_hay_tope_de_profundidad_y_es_el_del_dominio():
    """Cinturón y tirantes (DA-3 b), y el mismo número en los dos sitios.

    `TOPE_DE_PROFUNDIDAD` vale 40 en `domain/arbol_partidas.py`. Si aquí dijera
    otra cosa, el dominio estaría probando una regla que la base no ejecuta.
    """
    rama = _rama_recursiva()

    assert re.search(
        rf"a\.nivel_bruto\s*<\s*{TOPE_DE_PROFUNDIDAD}\b", rama
    ), (
        f"falta el tope de profundidad, o no vale {TOPE_DE_PROFUNDIDAD} como en "
        f"etl_sigrid/domain/arbol_partidas.py"
    )


def test_f052_r5_el_tope_muerde_sobre_los_saltos_y_no_sobre_el_nivel():
    """`nivel_bruto` y no `nivel`, y la diferencia importa: una cadena de nodos
    colapsados en bucle no haría avanzar `nivel` **nunca**, así que un tope
    sobre `nivel` no cortaría nada."""
    rama = _rama_recursiva()

    assert "nivel_bruto" in rama
    assert not re.search(r"a\.nivel\s*<\s*\d+", rama), (
        "el tope está puesto sobre `nivel`, que no avanza en los nodos colapsados"
    )


# ---------------------------------------------------------------------------
# La cabecera, que hoy documenta el filtro al revés
# ---------------------------------------------------------------------------


def test_f052_la_cabecera_ya_no_dice_que_el_filtro_descarta_al_descender():
    """Una cabecera que describe el comportamiento de antes no es documentación
    incompleta: es una afirmación falsa, y aquí es la que explicaba como
    intencionado justo el defecto que costó 2.624.793,46 € de coste oculto."""
    cabecera = _sql()[: _sql().index("TRUNCATE TABLE stg.partidas")]

    assert "descarta filas estructurales sin código" not in cabecera
    assert "que se publica" in cabecera, (
        "la cabecera no explica que el filtro decide qué se publica y no por "
        "dónde se desciende"
    )


# ---------------------------------------------------------------------------
# T6 · el tramo de F-019 no entra aquí
# ---------------------------------------------------------------------------


def test_f052_el_arbol_no_necesita_marcador_de_tramo():
    """`04_partidas.sql` nunca llevó el marcador de tramo de F-019 y sigue sin
    llevarlo: el CTE ya particiona por obra a través de `padide`, que **nunca
    sale de su obra** (medido: causa (c) del informe = 0 casos)."""
    assert "F019_FILTRO_OBRAS" not in _sql()


def test_f052_el_arbol_no_escribe_fuera_de_stg_partidas():
    """El fichero vacía y rellena `stg.partidas`, y nada más."""
    texto = _sql().upper()

    assert texto.count("TRUNCATE TABLE STG.PARTIDAS") == 1
    assert texto.count("INSERT INTO") == 1
    for palabra in ("DROP", "ALTER", "DELETE", "UPDATE", "GRANT", "COPY"):
        assert not re.search(rf"\b{palabra}\b", texto), (
            f"04_partidas.sql contiene {palabra}"
        )
