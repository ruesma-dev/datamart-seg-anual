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


#: F-118 añade al SELECT del master las dos marcas de las filas reales, a NULL
#: (el INSERT es uno y la rama master tiene que dar las mismas columnas). Es la
#: ÚNICA diferencia permitida: se quitan antes de calcular el hash, así que
#: cualquier otro cambio de la rama master lo sigue cazando el hash de antes.
_MARCAS_F118 = (
    ",\n    NULL::BOOLEAN                                             AS es_relleno,"
    "\n    NULL::BOOLEAN                                             AS es_deshacer"
)


def _sin_marcas_de_f118(bloque: str) -> str:
    assert bloque.count(_MARCAS_F118) <= 1
    return bloque.replace(_MARCAS_F118, "")


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
    bloque = _sin_marcas_de_f118(_entre(_sql(), inicio, fin))
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


@pytest.mark.parametrize("cte", ("reales_cierres", "reales_vigente"))
def test_f042_r1_existen_las_cte_de_la_regla(cte: str):
    """F-118: `reales_orden` ya no existe. Solo aportaba `vive` y el orden del
    `LAG`; la serie densa ordena por mes y lee los vigentes por JOIN
    (`test_f118_sql.py::test_f118_r9_stg_sin_orden_fase_ni_case_de_consecutividad`)."""
    assert f"{cte} AS (" in _sql(), f"falta la CTE {cte}"


def test_f042_r1_el_vigente_prefiere_el_acumulado_con_dato_y_luego_el_mas_moderno():
    """`ORDER BY (acumulado <> 0) DESC, mes_fase_num DESC`, en ese orden.

    Si se invirtieran los dos criterios, 0606 · PUY DU FOU pasaría a publicar
    cero en febrero de 2021. El orden de las dos claves ES la regla.
    """
    vigente = _entre(_sql(), "reales_vigente AS (", "reales_relleno AS (")

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


def test_f042_r5_sin_dense_rank_ni_desplazamiento_de_fases():
    """F-118 sustituye el desplazamiento de F-042 por la serie densa.

    F-042 renumeraba `orden_fase` descontando descartes para que el `LAG`
    volviera a ser consecutivo, y NUNCA con `dense_rank()`, que habría cerrado
    también los huecos de Sigrid. F-118 deja de mirar el número de fase: el
    movimiento es la diferencia con el mes anterior de la serie de la partida,
    sin huecos, y un hueco de Sigrid ya no publica el acumulado entero (F-103
    absorbida). Sustitutos: `test_f118_sql.py::
    test_f118_r9_stg_el_movimiento_es_la_diferencia_con_el_mes_anterior` y el
    invariante de `test_f118_invariante.py`.
    """
    sin_comentarios = _sin_comentarios(_sql())
    assert "dense_rank" not in sin_comentarios.lower()
    assert "orden_fase" not in sin_comentarios
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING" not in sin_comentarios


def test_f042_r5_el_relleno_y_los_vigentes_se_deciden_por_obra_y_ambito():
    """Lo que antes garantizaba la ventana del desplazamiento (no cruzar obras)
    lo hacen ahora el `DISTINCT ON` de los vigentes y el del relleno."""
    assert "DISTINCT ON (obra_id, ambito_id, anio_mes)" in _entre(
        _sql(), "reales_vigente AS (", "reales_relleno AS ("
    )
    assert "DISTINCT ON (v.obra_id, v.ambito_id, gs.mes)" in _entre(
        _sql(), "reales_relleno AS (", "reales_meses AS ("
    )


# ---------------------------------------------------------------------------
# R5 · el movimiento: la diferencia con el mes anterior de la serie (F-118)
# ---------------------------------------------------------------------------


def test_f042_r5_los_cuatro_movimientos_restan_el_mes_anterior_de_la_serie():
    """Los cuatro: `cantidad_mes`, `importe_mes_round`, `importe_mes_raw` y
    `total_incurrido_mes_calc`. Antes eran cuatro `CASE WHEN LAG(orden_fase)
    OVER w = orden_fase - 1` que publicaban el acumulado entero si la fila
    anterior no era consecutiva: ese `CASE` era el defecto del fallo 1 de F-118.
    Ahora ninguno lo tiene y ninguno mira el número de fase."""
    bloque = _reales_con_lag()

    assert bloque.count("COALESCE(LAG(") == 4
    assert "LAG(orden_fase)" not in bloque
    assert "LAG(mes_fase_num) OVER w" not in bloque
    assert not re.search(r"CASE\s+WHEN\s+LAG", bloque)


def test_f042_r5_la_ventana_del_lag_ordena_por_mes():
    """F-118: por `anio_mes`, no por `orden_fase`. El mes es único por (obra,
    ámbito) tras F-042 sobre el mes del texto, y la serie no tiene huecos."""
    bloque = _reales_con_lag()

    assert re.search(
        r"WINDOW w AS \(\s*\n\s*PARTITION BY obra_id, partida_id, ambito_id\s*\n"
        r"\s*ORDER BY anio_mes\s*\n\s*\)",
        bloque,
    ), bloque


def test_f042_r1_las_filas_de_sigrid_son_solo_las_de_los_cierres_que_viven():
    """Antes `reales_con_lag` filtraba `WHERE o.vive`; ahora las filas de Sigrid
    entran por JOIN con los cierres vigentes (`reales_vigente_alta`), así que una
    fase descartada no aporta ninguna fila a la serie."""
    filas = _entre(_sql(), "reales_filas AS (", "reales_alta AS (")

    assert "FROM reales_base b" in filas
    assert "JOIN reales_vigente_alta v" in filas
    assert "v.mes_fase_num = b.mes_fase_num" in filas


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


def test_f042_ninguna_ventana_del_fichero_cruza_obras():
    """La condición que hace válido el troceo por tramos de F-019.

    Se lee de TODOS los `PARTITION BY` del fichero, no de una lista escrita a
    mano: una ventana nueva que particionara por otra cosa —o que no
    particionara— haría que un tramo viera filas de otra obra, y el resultado
    por tramos dejaría de ser idéntico al de una pasada única. F-042 añade dos
    ventanas, y por eso el detector se escribe ahora en vez de seguir fiándolo a
    un comentario de cabecera.
    """
    particiones = re.findall(r"PARTITION BY\s+([^\n]+)", _sin_comentarios(_sql()))

    assert particiones, "no se ha encontrado ninguna ventana: el detector mira al vacio"
    for particion in particiones:
        # Una ventana puede venir en una línea (`PARTITION BY x ORDER BY y`) o
        # repartida en varias: en el primer caso hay que cortar por `ORDER BY`.
        columnas = re.split(r"\bORDER BY\b|\bROWS\b|\bRANGE\b|\)", particion)[0]
        primera = columnas.split(",")[0].strip().split(".")[-1]
        assert primera in ("presupuesto_id", "obra_id"), (
            f"la ventana `PARTITION BY {particion.strip()}` no empieza por obra: "
            f"cruzaria obras y el troceo por tramos de F-019 dejaria de ser "
            f"equivalente a una pasada unica"
        )


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
        "reales_con_lag",
        "reales_final",
    ):
        assert f"{cte} AS (" in bloque, f"{cte} fuera del bloque reutilizable"


def test_f042_r22_el_bloque_reutilizable_no_arrastra_el_insert():
    bloque = _bloque_de_reales()

    assert "INSERT INTO" not in bloque
    assert not bloque.rstrip().endswith(",")
