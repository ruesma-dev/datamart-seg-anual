# tests/test_f042_sql.py
"""
F-042 · Aserciones sobre el TEXTO de `sql/stg/08_plan_mensual.sql`.

Aquí no se abre ninguna conexión: se comprueba que el fichero que el build
ejecuta dice lo que la spec exige y, sobre todo, que **no dice nada más**.

## El test que más vale de este fichero

`test_f042_r9_la_rama_master_no_cambia_ni_un_byte`. La rama de los ámbitos 8 y
11 se fija por **hash**, calculado sobre el fichero tal y como estaba antes de
tocarlo. Es la garantía mecánica de R9 en el único sitio donde se puede dar sin
reconstruir la base: si alguien roza la rama master —hoy o dentro de un año— el
test cae y hay que justificarlo. Un `grep` de «no aparece la palabra X» no da
eso; un hash, sí.

Si el hash cambia **a propósito**, se recalcula así y se explica el porqué en el
commit:

    python -c "import hashlib,pathlib; t=pathlib.Path('etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql').read_bytes().decode('utf-8').replace(chr(13)+chr(10),chr(10)); i=t.index('WITH master_planif AS ('); print(hashlib.sha256(t[i:t.index('-- BRANCH B: REALES', i)].encode()).hexdigest())"
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    MARCADOR_FILTRO_OBRAS,
)

RUTA = DIRECTORIO_SQL_STG / "08_plan_mensual.sql"

#: Los dos marcadores que acotan el bloque de reales dentro del fichero. Aquí
#: van como literales **a propósito**: este test comprueba el SQL y no debe
#: depender de `huella_obras`, que es quien los consume y los declara como
#: constantes. Si una de las dos copias se desviara de la otra, uno de los dos
#: lados cae en el acto: aquí fallarían las aserciones de delimitación y allí
#: `bloque_de_reales()` levantaría el error de marcador ausente.
MARCADOR_INICIO_REALES = "/*F042_INICIO_REALES*/"
MARCADOR_FIN_REALES = "/*F042_FIN_REALES*/"

#: SHA-256 del bloque de CTE del master, del `WITH master_planif AS (` hasta el
#: banner de la rama de reales, con los saltos de línea normalizados a `\n`.
#: Medido sobre el fichero ANTES de F-042 (commit 818488b).
HASH_CTE_MASTER = "6382b061418c0d0ec1a85d89ec9b16e4b3ada2c9ac37112dfe20f46eda820150"

#: SHA-256 del `SELECT` del master dentro del `INSERT` final, del comentario
#: `-- ---- master ----` hasta el `UNION ALL`. Misma medición.
HASH_SELECT_MASTER = "04ecaa59b0cf646c3d3f6151773a4b949ecb93392c0f406f06042bb23e62d7d2"


@lru_cache(maxsize=1)
def _sql() -> str:
    """El fichero con los saltos de línea normalizados.

    Se normaliza porque el hash tiene que valer igual en un clon con CRLF: si no,
    el test cazaría un `git config core.autocrlf` en vez de un cambio de lógica.
    """
    return RUTA.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _sin_comentarios(texto: str) -> str:
    """El SQL sin las líneas `--`. Este fichero es medio comentario: sin esto,
    cualquier detector de «no aparece la palabra X» cazaría la explicación de por
    qué X no se usa."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _entre(texto: str, inicio: str, fin: str) -> str:
    desde = texto.index(inicio)
    return texto[desde : texto.index(fin, desde)]


@lru_cache(maxsize=1)
def _reales_con_lag() -> str:
    return _entre(_sql(), "reales_con_lag AS (", MARCADOR_FIN_REALES)


@lru_cache(maxsize=1)
def _bloque_de_reales() -> str:
    """El texto entre los dos marcadores, que es lo que reejecuta la huella."""
    texto = _sql()
    desde = texto.index(MARCADOR_INICIO_REALES) + len(MARCADOR_INICIO_REALES)
    return texto[desde : texto.index(MARCADOR_FIN_REALES)]


# ---------------------------------------------------------------------------
# R9 · la rama master no se toca
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "inicio", "fin", "esperado"),
    (
        (
            "las CTE del master",
            "WITH master_planif AS (",
            "-- BRANCH B: REALES",
            HASH_CTE_MASTER,
        ),
        (
            "el SELECT del master",
            "-- ---- master ----",
            "UNION ALL",
            HASH_SELECT_MASTER,
        ),
    ),
)
def test_f042_r9_la_rama_master_no_cambia_ni_un_byte(nombre, inicio, fin, esperado):
    """Los ámbitos 8 y 11 salen exactamente igual que antes de la feature.

    Hoy **no tienen ni una clave duplicada** (medido: 4.754 en el ámbito 3,
    4.024 en el 7, cero en 8 y 11), así que el resultado esperado del antes/
    después ahí es cero cambios (R24). Este hash es el argumento estructural que
    lo respalda: la rama que los produce es la misma.
    """
    bloque = _entre(_sql(), inicio, fin)
    real = hashlib.sha256(bloque.encode("utf-8")).hexdigest()

    assert real == esperado, (
        f"{nombre} ha cambiado ({len(bloque)} caracteres, sha256 {real}). "
        f"F-042 no puede tocar la rama de los ambitos 8 y 11: si el cambio es "
        f"deliberado, recalcula el hash y justificalo en el commit"
    )


def test_f042_r9_el_bloque_de_reales_no_menciona_ninguna_cte_del_master():
    """Los dos mundos están separados, y eso es lo que permite reejecutar la
    rama de reales sola en `huella-obras --propuesta`."""
    assert not re.search(r"\bmaster_\w+", _bloque_de_reales())


# ---------------------------------------------------------------------------
# Las tres CTE nuevas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cte", ("reales_cierres", "reales_vigente", "reales_orden"))
def test_f042_r1_existen_las_tres_cte_de_la_regla(cte: str):
    assert f"{cte} AS (" in _sql(), f"falta la CTE {cte}"


def test_f042_r1_el_vigente_prefiere_el_acumulado_con_dato_y_luego_el_mas_moderno():
    """`ORDER BY (acumulado <> 0) DESC, mes_fase_num DESC`, en ese orden.

    Si se invirtieran los dos criterios, 0606 · PUY DU FOU pasaría a publicar
    cero en febrero de 2021. El orden de las dos claves ES la regla.
    """
    vigente = _entre(_sql(), "reales_vigente AS (", "reales_orden AS (")

    assert "DISTINCT ON (obra_id, ambito_id, anio_mes)" in vigente
    assert re.search(
        r"\(acumulado <> 0\) DESC,\s*\n?\s*mes_fase_num DESC", vigente
    ), vigente


def test_f042_r11_el_acumulado_del_mes_no_puede_ser_nulo():
    """`COALESCE(SUM(...), 0)`: sin él, una fase sin ningún importe ganaría el mes.

    En Postgres `NULL <> 0` no es cierto, y en un `ORDER BY ... DESC` los nulos
    van PRIMERO. El `COALESCE` es lo que impide que la regla se decida por un
    dato que no existe.
    """
    cierres = _entre(_sql(), "reales_cierres AS (", "reales_vigente AS (")

    assert "COALESCE(SUM(importe_origen_round), 0)" in cierres


def test_f042_r5_el_orden_se_desplaza_por_descartes_y_nunca_con_dense_rank():
    """El desplazamiento cuenta los descartes ANTERIORES, con la ventana acotada
    a `ROWS ... AND 1 PRECEDING`. `dense_rank()` cerraría también los huecos que
    Sigrid ya trae (R6) y movería obras que hoy están bien."""
    orden = _entre(_sql(), "reales_orden AS (", MARCADOR_FIN_REALES)

    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING" in orden
    # Sin los comentarios: la cabecera del fichero EXPLICA por qué no se usa
    # `dense_rank()`, y esa explicación no puede hacer fallar al detector.
    assert "dense_rank" not in _sin_comentarios(_sql()).lower()


def test_f042_r5_la_ventana_del_desplazamiento_particiona_por_obra_y_ambito():
    """Ninguna ventana nueva cruza obras: es la condición que hace válido el
    troceo por tramos de F-019 sin marcador nuevo."""
    orden = _entre(_sql(), "reales_orden AS (", MARCADOR_FIN_REALES)

    assert "PARTITION BY c.obra_id, c.ambito_id ORDER BY c.mes_fase_num" in orden


# ---------------------------------------------------------------------------
# R5 · el LAG mira `orden_fase`, no `mes_fase_num`
# ---------------------------------------------------------------------------


def test_f042_r5_los_cuatro_case_del_lag_comparan_orden_fase():
    """Los cuatro: `can_mes`, `importe_mes_round`, `importe_mes_raw` y
    `total_incurrido_mes_calc`. Dejar uno con `mes_fase_num` daría una columna
    coherente y tres rotas, que es peor que romperlas todas."""
    bloque = _reales_con_lag()

    assert bloque.count("LAG(orden_fase) OVER w = orden_fase - 1") == 4
    assert "LAG(mes_fase_num) OVER w" not in bloque


def test_f042_r5_la_ventana_del_lag_ordena_por_orden_fase():
    bloque = _reales_con_lag()

    assert re.search(
        r"WINDOW w AS \(\s*\n\s*PARTITION BY obra_id, partida_id, ambito_id\s*\n"
        r"\s*ORDER BY orden_fase\s*\n\s*\)",
        bloque,
    ), bloque


def test_f042_r1_reales_con_lag_lee_solo_los_cierres_que_viven():
    bloque = _reales_con_lag()

    assert "reales_orden" in bloque
    assert re.search(r"WHERE\s+o\.vive", bloque), bloque


# ---------------------------------------------------------------------------
# R7 · `version` conserva el número original de Sigrid
# ---------------------------------------------------------------------------


def test_f042_r7_version_recibe_el_numero_de_fase_original():
    """No `orden_fase`. Seis `JOIN` de `cierre/` cruzan `pm.version` contra
    `stg.fases.numero_fase`: publicar el renumerado los desalinearía en
    silencio, y el diccionario documenta `version` como el número de Sigrid."""
    reales = _entre(_sql(), "-- ---- reales ----", ";")

    assert re.search(r"mes_fase_num\s+AS version\b", reales), reales
    assert "orden_fase" not in reales, (
        "el orden renumerado es INTERNO: no puede salir en el INSERT"
    )


def test_f042_r7_el_orden_interno_no_llega_a_ninguna_columna_publicada():
    """`orden_fase` vive entre `reales_orden` y el `LAG`, y ahí se queda."""
    insert = _sql()[_sql().index("INSERT INTO stg.plan_mensual") :]

    assert "orden_fase" not in insert


# ---------------------------------------------------------------------------
# F-019 · el troceo por tramos sigue en pie
# ---------------------------------------------------------------------------


def test_f042_el_filtro_de_tramos_sigue_en_las_dos_ramas():
    """Filtrar solo una duplicaría las filas de la otra en cada tramo."""
    assert _sql().count(MARCADOR_FILTRO_OBRAS) == 2


def test_f042_el_filtro_de_tramos_esta_dentro_del_bloque_de_reales():
    """La huella propuesta reejecuta ese bloque tramo a tramo: si el marcador se
    quedara fuera, la huella se ejecutaría de una pasada sobre la base entera,
    que es justo lo que llenó el disco el 2026-08-09."""
    assert MARCADOR_FILTRO_OBRAS in _bloque_de_reales()


# ---------------------------------------------------------------------------
# Los marcadores que delimitan el bloque reutilizable
# ---------------------------------------------------------------------------


def test_f042_r22_los_marcadores_delimitan_el_bloque_de_reales():
    """`huella-obras --propuesta` ejecuta ESTE bloque, no una copia suya.

    Es lo que impide que la huella y el build diverjan: si hubiera dos textos con
    la misma lógica, la prueba que decide estaría midiendo el equivocado.
    """
    texto = _sql()

    assert texto.count(MARCADOR_INICIO_REALES) == 1
    assert texto.count(MARCADOR_FIN_REALES) == 1
    assert texto.index(MARCADOR_INICIO_REALES) < texto.index(MARCADOR_FIN_REALES)

    bloque = _bloque_de_reales()
    for cte in (
        "reales_base",
        "reales_cierres",
        "reales_vigente",
        "reales_orden",
        "reales_con_lag",
    ):
        assert f"{cte} AS (" in bloque, f"{cte} fuera del bloque reutilizable"


def test_f042_r22_el_bloque_reutilizable_no_arrastra_el_insert():
    bloque = _bloque_de_reales()

    assert "INSERT INTO" not in bloque
    assert not bloque.rstrip().endswith(",")
