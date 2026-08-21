# tests/test_f006_stg_trampas.py
"""
Las trampas de `stg` que la séptima pasada encontró, cada una con su fuente.

Cuatro fichas de `stg` afirmaban cosas que el SQL desmiente, y las cuatro son de
la clase que produce **números falsos**, no fealdad:

1. `stg.presupuesto` no dice que en los ámbitos REALES es **acumulado a
   origen**, y encima marca sus tres medidas como `agregacion: suma`. El
   desacumulado se hace aguas abajo por diferencia con la fase anterior
   (`08_plan_mensual.sql`: `cantidad - LAG(cantidad)`), así que sumar a través
   de `fase_num` multiplica. Es `R-IMPORTE-MES` otra vez, en la ficha que se
   autoproclama «la fuente buena para cuál es el presupuesto de la obra».
2. La misma ficha no repite la trampa de las **versiones master**, que aplica
   igual que en `plan_mensual`: en los ámbitos 8 y 11 hay una fila por versión.
3. `stg.fases.anio` y `.mes` declaraban salir de la fecha de inicio.
   `05_fases.sql` los copia de `f.ano` y `f.mes` de `raw.obrfas`, que son
   **independientes** de `fecini`.
4. `stg.partidas.capitulo_raiz_id` tenía el `nulo_significa` **invertido**.

Los cuatro se comprueban contra el SQL, no contra el informe.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"


@lru_cache(maxsize=1)
def _dicc():
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _ficha(nombre: str):
    return _dicc().por_nombre[nombre]


def _columna(nombre: str, columna: str):
    return next(c for c in _ficha(nombre).columnas if c.nombre == columna)


def _sql(ruta: str) -> str:
    return (DIR_SQL / ruta).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 y 2 · `stg.presupuesto`: acumulado a origen, y una fila por versión master
# ---------------------------------------------------------------------------


def test_f006_r10_el_sql_confirma_que_el_presupuesto_real_es_acumulado() -> None:
    """La fuente de la afirmación, para que no sea palabra contra palabra.

    Si `plan_mensual` desacumula por diferencia con la fase anterior, es porque
    lo que hay en `stg.presupuesto` viene acumulado a origen.
    """
    sql = _sql("stg/08_plan_mensual.sql")
    assert re.search(r"cantidad\s*-\s*COALESCE\(\s*LAG\(cantidad\)", sql), (
        "ya no se desacumula por diferencia con la fase anterior: si el origen "
        "cambió, la ficha de `stg.presupuesto` hay que revisarla entera"
    )
    assert re.search(r"ambito_id\s+IN\s*\(\s*3\s*,\s*7\s*\)", sql), (
        "el desacumulado ya no se aplica a los ámbitos reales 3 y 7"
    )


@pytest.mark.parametrize("columna", ["cantidad", "importe", "importe_oficial"])
def test_f006_r10_las_medidas_del_presupuesto_no_se_declaran_sumables(
    columna: str,
) -> None:
    """`suma` sobre un acumulado a origen es la invitación a multiplicar."""
    c = _columna("stg.presupuesto", columna)
    assert c.agregacion != "suma", (
        f"stg.presupuesto.{columna} se declara `suma` y en los ámbitos reales "
        f"viene ACUMULADO A ORIGEN: sumar a través de `fase_num` cuenta el mismo "
        f"importe una vez por cada mes transcurrido"
    )


@pytest.mark.parametrize("columna", ["cantidad", "importe", "importe_oficial"])
def test_f006_r10_cada_medida_avisa_del_acumulado(columna: str) -> None:
    """No basta con cambiar la etiqueta: hay que decir por qué, y qué hacer."""
    c = _columna("stg.presupuesto", columna)
    texto = c.significado.lower()
    assert "acumulad" in texto, (
        f"stg.presupuesto.{columna} no avisa de que en los ámbitos reales el "
        f"valor es acumulado a origen"
    )


def test_f006_r10_la_ficha_del_presupuesto_avisa_del_acumulado_a_origen() -> None:
    """En el grano, que es donde se mira antes de escribir un `SUM`."""
    texto = f"{_ficha('stg.presupuesto').descripcion} {_ficha('stg.presupuesto').grano}"
    bajo = texto.lower()
    assert "acumulado a origen" in bajo, "la trampa central no está en la ficha"
    assert "3" in texto and "7" in texto, "tiene que decir en qué ámbitos ocurre"


def test_f006_r10_la_ficha_del_presupuesto_repite_la_trampa_de_las_versiones() -> None:
    """Aplica igual que en `plan_mensual`, y la ficha invita a la pregunta.

    `stg.plan_mensual` avisa de que todas las versiones master conviven. En
    `stg.presupuesto` pasa lo mismo —una fila por versión en los ámbitos 8 y
    11— y quien lea solo esta ficha no se entera.
    """
    f = _ficha("stg.presupuesto")
    texto = f"{f.descripcion} {f.grano} {f.motivo_no_consumo or ''}".lower()
    assert "version" in texto, "no menciona las versiones master"
    assert "8" in texto and "11" in texto, (
        "tiene que nombrar los ámbitos master 8 y 11, que son donde hay una fila "
        "por versión"
    )


# ---------------------------------------------------------------------------
# 3 · `stg.fases.anio` y `.mes` vienen de Sigrid, no de la fecha de inicio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("columna", "origen"), [("anio", "f.ano"), ("mes", "f.mes")]
)
def test_f006_r26_anio_y_mes_de_las_fases_declaran_su_origen_real(
    columna: str, origen: str
) -> None:
    sql = _sql("stg/05_fases.sql")
    assert re.search(rf"{re.escape(origen)}\s+AS\s+{columna}\b", sql), (
        f"esperaba que `{columna}` saliera de `{origen}` en 05_fases.sql"
    )

    c = _columna("stg.fases", columna)
    texto = f"{c.significado} {c.nulo_significa or ''}"
    assert "obrfas" in texto, (
        f"stg.fases.{columna} tiene que decir que lo copia de `raw.obrfas`, no "
        f"que lo deriva de la fecha de inicio: son campos independientes"
    )
    assert "fecha de inicio" not in texto.lower(), (
        f"stg.fases.{columna} sigue diciendo que sale de la fecha de inicio"
    )


def test_f006_r26_anio_y_mes_avisan_de_que_el_plan_mensual_los_exige() -> None:
    """No es cosmético: si son nulos, la fila no entra en los ámbitos reales."""
    sql = _sql("stg/08_plan_mensual.sql")
    assert re.search(r"f\.anio\s+IS\s+NOT\s+NULL", sql, re.IGNORECASE)

    for columna in ("anio", "mes"):
        c = _columna("stg.fases", columna)
        texto = f"{c.significado} {c.nulo_significa or ''}"
        assert "plan_mensual" in texto, (
            f"stg.fases.{columna} no avisa de que `stg.plan_mensual` exige que no "
            f"sea nulo para construir los ámbitos reales"
        )


# ---------------------------------------------------------------------------
# 4 · `stg.partidas.capitulo_raiz_id`: el nulo estaba al revés
# ---------------------------------------------------------------------------


def test_f006_r2_el_capitulo_raiz_se_apunta_a_si_mismo_en_la_raiz() -> None:
    """`WHERE capitulo_raiz_id IS NULL` devolvía cero filas, siempre."""
    sql = _sql("stg/04_partidas.sql")
    assert re.search(r"p\.ide\s+AS\s+capitulo_raiz_id", sql), (
        "en la raíz ya no se apunta a sí misma; revisar la ficha entera"
    )

    c = _columna("stg.partidas", "capitulo_raiz_id")
    assert c.nulo_significa is None, (
        "`capitulo_raiz_id` nunca es NULL: en la raíz vale su propio `ide`. "
        f"La ficha declara: {c.nulo_significa!r}"
    )
    assert "capitulo_raiz_id = partida_id" in c.significado, (
        "tiene que decir cómo se reconoce una raíz de verdad, que es comparándola "
        "consigo misma"
    )


def test_f006_r2_el_codigo_del_capitulo_raiz_tampoco_declara_un_nulo_falso() -> None:
    """La hermana del defecto anterior, encontrada barriendo, no leyendo.

    `capitulo_raiz_id` tenía el `nulo_significa` invertido y `capitulo_raiz_cod`
    —el campo de al lado, con el mismo origen— repetía la mitad falsa: «La
    propia fila es el capitulo raiz, o no tiene codigo». En la raíz la fila se
    apunta a sí misma, así que ese NULL solo puede venir de que `cod` esté vacío.

    Es el tercer rechazo por lo mismo: una afirmación corregida en un campo y
    viva en el vecino. Por eso el barrido se hace a máquina.
    """
    sql = _sql("stg/04_partidas.sql")
    assert re.search(r"p\.cod\s+AS\s+capitulo_raiz_cod", sql)

    c = _columna("stg.partidas", "capitulo_raiz_cod")
    texto = str(c.nulo_significa or "")
    assert "propia fila" not in texto.lower(), (
        f"`capitulo_raiz_cod` repite la mitad falsa de su hermana: en la raíz la "
        f"fila se apunta a sí misma y este campo trae su propio código. "
        f"Declara: {texto!r}"
    )


# ---------------------------------------------------------------------------
# Una regla BLOQUEANTE no puede convivir con fichas que la contradicen (9ª)
# ---------------------------------------------------------------------------
#
# `R-IMPORTE-MES` dice, y es bloqueante: «de un total de un periodo se toma su
# valor del ÚLTIMO mes, no la suma». Su ámbito incluye `stg.plan_mensual`.
#
# Y `stg.plan_mensual` marcaba **sumables** cuatro columnas acumuladas a origen
# —`can_origen`, `importe_origen`, `importe_origen_raw`, `total_incurrido`—
# mientras sus **doce gemelas de `mart`**, con el mismo nombre y el mismo
# número, están en `ultimo_valor`. Que una regla bloqueante conviva con fichas
# que la contradicen es lo peor que puede pasarle a este diccionario: el agente
# recibe las dos cosas y no tiene forma de saber cuál vale.
#
# La comprobación no lista columnas: **deriva la coherencia**. La misma columna,
# en dos objetos del ámbito de la regla, es el mismo número y tiene que
# declararse igual. Así se caza la deriva en los dos sentidos, y sin lista que
# mantener.


def _objetos_del_ambito_de(codigo: str) -> list[str]:
    return list(next(r for r in _dicc().reglas if r.codigo == codigo).ambito)


def test_f006_r10_control_el_ambito_de_importe_mes_cubre_stg_y_mart() -> None:
    """Si el ámbito se encogiera, la comprobación de abajo pasaría en vacío."""
    ambito = _objetos_del_ambito_de("R-IMPORTE-MES")
    assert "stg.plan_mensual" in ambito
    assert "mart.fact_seguimiento_mensual" in ambito
    assert len(ambito) >= 8


def test_f006_r10_una_columna_repetida_se_declara_igual_en_todo_el_ambito() -> None:
    """`importe_origen` es el mismo número en `stg` y en `mart`: o las dos o ninguna."""
    ambito = _objetos_del_ambito_de("R-IMPORTE-MES")
    indice = _dicc().por_nombre

    por_columna: dict[str, dict[str, str]] = {}
    for nombre in ambito:
        ficha = indice.get(nombre)
        if ficha is None:
            continue
        for c in ficha.columnas:
            if c.agregacion:
                por_columna.setdefault(c.nombre, {})[nombre] = c.agregacion

    discrepantes = {
        col: dict(sorted(objs.items()))
        for col, objs in por_columna.items()
        if len(set(objs.values())) > 1
    }
    assert discrepantes == {}, (
        f"la misma columna se declara con `agregacion` distinta dentro del ámbito "
        f"de `R-IMPORTE-MES`, que es bloqueante: {discrepantes}. Son el mismo "
        f"número; si una es acumulada a origen lo es en los dos sitios"
    )


@pytest.mark.parametrize(
    "columna", ["can_origen", "importe_origen", "importe_origen_raw", "total_incurrido"]
)
def test_f006_r10_las_acumuladas_a_origen_no_son_sumables(columna: str) -> None:
    """Y el valor correcto es el que manda la regla: el del último mes."""
    c = _columna("stg.plan_mensual", columna)
    assert c.agregacion == "ultimo_valor", (
        f"stg.plan_mensual.{columna} es un acumulado a origen y se declara "
        f"`{c.agregacion}`. `R-IMPORTE-MES` dice que de un total de un periodo se "
        f"toma el valor del ULTIMO mes, no la suma"
    )
