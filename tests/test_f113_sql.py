# tests/test_f113_sql.py
"""
F-113 · El SQL de la categoría, comprobado sobre su texto (R7, R10, R11).

`sql/stg/04_partidas.sql` no se puede ejecutar aquí: escribe en `stg.partidas`
de un Postgres compartido en producción. Lo que sí se puede es fijar que el SQL
dice **lo mismo** que `etl_sigrid/domain/categoria_partida.py`, cuya regla prueba
`tests/test_f113_categoria.py`: los patrones esperados se **construyen** desde
las constantes del dominio, así que si una de las dos orillas cambia sin la otra
la suite cae. Mismo patrón que `tests/test_f052_sql.py` con el tope de 40.

Que la expresión haga lo que debe contra datos reales lo prueba T5 (la consulta
del árbol nuevo en solo lectura contra Azure, `progress/impl_F-113.md`).
"""

from __future__ import annotations

import re
from functools import lru_cache

from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG
from etl_sigrid.domain.categoria_partida import (
    CARACTERES_IGNORADOS_EN_INTERMEDIO,
    CATEGORIA_DE_RAIZ_NUMERICA,
    CATEGORIAS_DE_CAPITULO,
    OTRO,
    RAICES_NUMERICAS_FUERA,
)
from tests.test_f052_sql import _columnas_proyectadas

RUTA = DIRECTORIO_SQL_STG / "04_partidas.sql"


@lru_cache(maxsize=1)
def _sql() -> str:
    return RUTA.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _rama_raiz() -> str:
    """De `WITH RECURSIVE` hasta el `UNION ALL`, sin comentarios."""
    texto = _sql()
    return _sin_comentarios(
        texto[texto.index("WITH RECURSIVE") : texto.index("UNION ALL")]
    )


def _rama_recursiva() -> str:
    """Del `UNION ALL` hasta el `INSERT`, sin comentarios."""
    texto = _sql()
    return _sin_comentarios(
        texto[texto.index("UNION ALL") : texto.index("INSERT INTO stg.partidas")]
    )


def _insert() -> str:
    texto = _sql()
    return _sin_comentarios(texto[texto.index("INSERT INTO stg.partidas") :])


def _lista_sql(valores: tuple[str, ...]) -> str:
    """`('CD', 'CI', 'CP')` como patrón, tolerante a espacios."""
    return r"\(\s*" + r"\s*,\s*".join(f"'{re.escape(v)}'" for v in valores) + r"\s*\)"


def _limpieza_del_intermedio() -> str:
    """`UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))`, construido desde
    `CARACTERES_IGNORADOS_EN_INTERMEDIO` en su orden."""
    patron = r"h\.cod"
    for caracter in CARACTERES_IGNORADOS_EN_INTERMEDIO:
        patron = rf"REPLACE\(\s*{patron}\s*,\s*'{re.escape(caracter)}'\s*,\s*''\s*\)"
    return rf"UPPER\(\s*{patron}\s*\)"


# ---------------------------------------------------------------------------
# R11 · el trinquete: ningún comodín por delante
# ---------------------------------------------------------------------------


def test_f113_r11_ningun_like_con_comodin_delante():
    """`LIKE '%CI%'` es el defecto entero: casa `AVDA_FRANCIA` y `P1414_PISCIN`.
    Se mira el fichero completo, comentarios fuera."""
    codigo = _sin_comentarios(_sql())
    assert not re.search(r"LIKE\s+'%", codigo, re.I), (
        "04_partidas.sql vuelve a buscar letras en mitad del código"
    )
    assert "arbol_categorizado" not in codigo, (
        "vuelve el CTE que categorizaba por la raíz con `LIKE '%..%'`"
    )


# ---------------------------------------------------------------------------
# R10 · la raíz: prefijo, numérica y OTRO, con los literales del dominio
# ---------------------------------------------------------------------------


def test_f113_r10_la_raiz_prueba_cada_prefijo_con_su_categoria():
    raiz = _rama_raiz()
    for categoria in CATEGORIAS_DE_CAPITULO:
        assert re.search(
            rf"WHEN\s+UPPER\(\s*p\.cod\s*\)\s+LIKE\s+'{categoria}%'\s+THEN\s+'{categoria}'",
            raiz,
        ), f"la raíz no clasifica por el prefijo {categoria}"


def test_f113_r10_la_raiz_numerica_con_las_excepciones_del_dominio():
    raiz = _rama_raiz()
    assert re.search(
        r"WHEN\s+p\.cod\s+~\s+'\^\[0-9\]\+\$'\s+AND\s+p\.cod\s+NOT\s+IN\s+"
        + _lista_sql(RAICES_NUMERICAS_FUERA)
        + rf"\s+THEN\s+'{CATEGORIA_DE_RAIZ_NUMERICA}'",
        raiz,
    ), "la regla numérica de la raíz no es la del dominio"


def test_f113_r10_la_raiz_completa_y_en_el_orden_del_dominio():
    """El `CASE` entero, en el orden de `CATEGORIAS_DE_CAPITULO`, la numérica
    después y OTRO al final. Construido desde el dominio: si cambia una orilla
    sin la otra, cae."""
    whens = r"\s+".join(
        rf"WHEN\s+UPPER\(\s*p\.cod\s*\)\s+LIKE\s+'{c}%'\s+THEN\s+'{c}'"
        for c in CATEGORIAS_DE_CAPITULO
    )
    patron = (
        r"\(\s*CASE\s+"
        + whens
        + r"\s+WHEN\s+p\.cod\s+~\s+'\^\[0-9\]\+\$'\s+AND\s+p\.cod\s+NOT\s+IN\s+"
        + _lista_sql(RAICES_NUMERICAS_FUERA)
        + rf"\s+THEN\s+'{CATEGORIA_DE_RAIZ_NUMERICA}'"
        + rf"\s+ELSE\s+'{OTRO}'\s+END\s*\)::TEXT\s+AS\s+categoria\b"
    )
    assert re.search(patron, _rama_raiz()), (
        "el CASE de la raíz no es exactamente el de domain/categoria_partida.py"
    )


# ---------------------------------------------------------------------------
# R10 · el intermedio: código exacto, sin puntos ni espacios, o el del padre
# ---------------------------------------------------------------------------


def test_f113_r10_el_intermedio_compara_el_codigo_limpio_con_la_lista_exacta():
    recursiva = _rama_recursiva()
    limpio = _limpieza_del_intermedio()
    patron = (
        rf"\(\s*CASE\s+WHEN\s+{limpio}\s+IN\s+"
        + _lista_sql(CATEGORIAS_DE_CAPITULO)
        + rf"\s+THEN\s+{limpio}\s+ELSE\s+a\.categoria\s+END\s*\)::TEXT\s+AS\s+categoria\b"
    )
    assert re.search(patron, recursiva), (
        "el CASE de la rama recursiva no es exactamente el de "
        "domain/categoria_partida.py: código exacto sin "
        f"{CARACTERES_IGNORADOS_EN_INTERMEDIO} o la categoría del padre"
    )


def test_f113_r10_un_replace_por_cada_caracter_ignorado():
    recursiva = _rama_recursiva()
    for caracter in CARACTERES_IGNORADOS_EN_INTERMEDIO:
        assert len(
            re.findall(rf",\s*'{re.escape(caracter)}'\s*,\s*''\s*\)", recursiva)
        ) == 2, f"el intermedio no quita '{caracter}' en el WHEN y en el THEN"


def test_f113_r5_el_intermedio_no_usa_prefijo():
    """En los intermedios, prefijo NO: `CI10`, `CPI8001` y `CP110` son partidas
    de catálogo bajo raíces CD (582 medidas)."""
    recursiva = _rama_recursiva()
    assert not re.search(r"\bLIKE\b", recursiva, re.I), (
        "la rama recursiva clasifica con LIKE: un código de catálogo `CI10` "
        "pasaría a CI"
    )
    assert re.search(r"ELSE\s+a\.categoria\s+END", recursiva), (
        "el intermedio sin código exacto no hereda la categoría del padre"
    )


# ---------------------------------------------------------------------------
# R7 · dentro del recursivo existente, misma columna y misma posición
# ---------------------------------------------------------------------------


def test_f113_r7_categoria_en_las_dos_ramas_y_en_la_misma_posicion():
    de_la_raiz = _columnas_proyectadas(_rama_raiz())
    de_la_recursiva = _columnas_proyectadas(_rama_recursiva())

    assert "categoria" in de_la_raiz and "categoria" in de_la_recursiva
    assert de_la_raiz.index("categoria") == de_la_recursiva.index("categoria")
    assert de_la_raiz[-1] == "categoria", (
        "la columna nueva va al final, tras nivel_bruto (design §4)"
    )


def test_f113_r7_el_insert_toma_la_categoria_del_recursivo():
    insert = _insert()
    select = insert[insert.index("SELECT") :]

    assert re.search(r"FROM\s+arbol_partidas\s+WHERE\s+publicable", select), (
        "el INSERT tiene que leer del CTE recursivo, sin CTE intermedio"
    )
    columnas = [
        " ".join(c.split())
        for c in select[len("SELECT") : select.index("FROM arbol_partidas")].split(",")
    ]
    assert "categoria" in columnas, (
        "el INSERT no copia la categoría del recursivo tal cual"
    )


def test_f113_r7_el_tope_y_el_corta_ciclos_no_cambian():
    recursiva = _rama_recursiva()
    assert re.search(r"NOT\s*\(\s*h\.ide\s*=\s*ANY\s*\(\s*a\.visitados\s*\)\s*\)", recursiva)
    assert re.search(r"a\.nivel_bruto\s*<\s*40\b", recursiva)


# ---------------------------------------------------------------------------
# R16 · la cabecera explica la regla nueva
# ---------------------------------------------------------------------------


def test_f113_r16_la_cabecera_explica_la_regla_y_el_porque():
    cabecera = _sql()[: _sql().index("TRUNCATE TABLE stg.partidas")]
    texto = " ".join(cabecera.replace("--", " ").split()).lower()

    assert "prefijo" in texto
    assert "exactamente" in texto
    assert "más cercano" in texto
    assert "ci10" in texto and "cpi8001" in texto, (
        "la cabecera no explica por qué no se usa prefijo en los intermedios"
    )
    assert "contiene 'ci'" not in texto, "la cabecera sigue describiendo la regla vieja"
