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
from tests._texto import contiene, normalizado

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


def test_f006_r26_anio_y_mes_nunca_son_nulos_y_la_ficha_lo_dice() -> None:
    """Escribí este test en la 7ª pasada con la premisa al revés.

    Decía «si son nulos, la fila no entra en los ámbitos reales», y di por bueno
    que la ficha lo repitiera. Pero `anio` y `mes` se proyectan **en crudo**
    desde `raw.obrfas`, y Sigrid no guarda nulos en los enteros: nunca son NULL,
    «sin informar» llega como **0**.

    La consecuencia es la contraria de la que publiqué: el filtro
    `f.anio IS NOT NULL` de `stg/08_plan_mensual.sql` **no descarta nada**, y una
    fase con `anio = 0` entra igual. Lo destapó el guardián de nulos al cubrir el
    punto ciego de las tablas que se pueblan con `INSERT ... SELECT`.
    """
    fases = _sql("stg/05_fases.sql")
    for columna, origen in (("anio", "f.ano"), ("mes", "f.mes")):
        assert re.search(rf"{re.escape(origen)}\s+AS\s+{columna}\b", fases), (
            f"`{columna}` ya no se proyecta en crudo desde {origen}; revisar la ficha"
        )
        c = _columna("stg.fases", columna)
        assert c.nulo_significa is None, (
            f"stg.fases.{columna} declara un NULL que no puede ocurrir: "
            f"{c.nulo_significa!r}"
        )
        assert "0" in c.significado, (
            f"stg.fases.{columna} tiene que decir que «sin informar» es 0"
        )

    # Y que el filtro inerte siga estando, porque es lo que la ficha explica.
    plan = _sql("stg/08_plan_mensual.sql")
    assert re.search(r"f\.anio\s+IS\s+NOT\s+NULL", plan, re.IGNORECASE)
    assert contiene(_columna("stg.fases", "anio").significado, "no descarta nada"), (
        "la ficha tiene que decir que ese filtro no filtra: quien lo lea en el SQL "
        "va a suponer lo contrario"
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
    assert contiene(c.significado, "capitulo_raiz_id = partida_id"), (
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


# ---------------------------------------------------------------------------
# `es_hoja` promete lo que su heurística no cumple (9ª pasada)
# ---------------------------------------------------------------------------
#
# `es_hoja` se calcula `nivel >= 2 OR codigo_partida LIKE '%.%'` en las dos
# vistas que lo publican. Eso **no** es «no tiene hijos»: un capítulo de nivel 2
# con descendientes —`CI.2`, que tiene `CI.2.1`— sale marcado como hoja. Y la
# ficha prometía justo lo contrario: «para no sumar dos veces al agregar por la
# jerarquía». Quien se fíe suma el capítulo y sus hijas: **doble conteo**, que es
# el error que la columna decía evitar.
#
# O la ficha dice lo que la heurística hace de verdad, o no promete nada.

VISTAS_CON_ES_HOJA = ("mart.v_pbi_dim_partida", "mart.v_pbi_dim_partida_niveles")


def test_f006_r26_control_es_hoja_sigue_siendo_una_heuristica() -> None:
    """Si algún día se calcula de verdad, este test avisa de revisar las fichas."""
    for ruta in ("mart/05_views_powerbi.sql", "mart/05b_view_dim_partida_niveles.sql"):
        sql = _sql(ruta)
        assert re.search(
            r"nivel\s*>=\s*2\s+OR\s+\S*codigo_partida\s+LIKE\s+'%\.%'", sql
        ), (
            f"{ruta}: `es_hoja` ya no se calcula con la heurística de nivel y "
            f"código. Si ahora mira los hijos de verdad, las fichas pueden "
            f"volver a prometer que evita el doble conteo"
        )


@pytest.mark.parametrize("objeto", VISTAS_CON_ES_HOJA)
def test_f006_r26_es_hoja_no_promete_evitar_el_doble_conteo(objeto: str) -> None:
    """La promesa era falsa en las dos vistas; se comprueban las dos."""
    c = _columna(objeto, "es_hoja")
    texto = c.significado.lower()

    assert "para no sumar dos veces" not in texto, (
        f"{objeto}.es_hoja repite la promesa que la heuristica no cumple: un "
        f"capitulo de nivel 2 con hijas sale marcado como hoja, asi que fiarse "
        f"de ella produce justo el doble conteo que dice evitar"
    )
    assert "heuristica" in texto, (
        f"{objeto}.es_hoja tiene que decir que es una HEURISTICA sobre el nivel y "
        f"la forma del codigo, no una comprobacion de si la partida tiene hijos"
    )
    assert "nivel" in texto and "codigo" in texto, (
        "y decir cual es, para que se pueda juzgar cuando falla"
    )
    assert "capitulo" in texto, (
        "tiene que avisar de que un capitulo intermedio sale marcado como hoja"
    )


# ---------------------------------------------------------------------------
# El punto ciego de la comprobación cruzada, medido y acotado (10ª pasada)
# ---------------------------------------------------------------------------
#
# `test_f006_r10_una_columna_repetida_se_declara_igual_en_todo_el_ambito` compara
# la misma columna **entre objetos** del ámbito de una regla. Por construcción
# **no ve las columnas que existen en un solo objeto**: para ellas no hay con
# quién comparar y la comprobación pasa sin mirar.
#
# No es un caso raro. Medido sobre el ámbito de `R-IMPORTE-MES`: de las columnas
# con `agregacion`, **32 aparecen en un único objeto**. Ahí se escondía
# `stg.plan_mensual.pct_acumulado`, y marcarla `clave_sustituta` habría dejado la
# batería entera en verde.
#
# Se cierra la parte derivable —los porcentajes— y **se declara el resto**, que
# es lo que el líder pidió: un hueco escrito vale más que un hueco que parece
# cubierto.

PORCENTAJES_NO_SUMABLES = ("promedio", "no_sumable", "ultimo_valor", "clave_sustituta")


def _columnas_de_porcentaje():
    """Toda columna de porcentaje del diccionario, esté sola en su objeto o no.

    Se reconocen por el nombre (`pct_*`, `*_pct`) o por declarar `unidad: %`.
    Esta comprobación es **por columna**, no cruzada, así que alcanza también a
    las que están solas: es el complemento del punto ciego de arriba.
    """
    for ficha in _dicc().fichas:
        for c in ficha.columnas:
            es_pct = (
                c.nombre.startswith("pct_")
                or c.nombre.endswith("_pct")
                or (c.unidad or "") == "%"
            )
            if es_pct and c.agregacion:
                yield ficha.nombre, c


def test_f006_r10_control_hay_porcentajes_que_comprobar() -> None:
    """Sin esto, un cambio de convención de nombres dejaría el test en vacío."""
    encontrados = list(_columnas_de_porcentaje())
    assert len(encontrados) >= 8, (
        f"solo {len(encontrados)} columnas de porcentaje: o cambió la convención "
        f"de nombres, o la comprobación dejó de alcanzar a nadie"
    )


def test_f006_r10_ningun_porcentaje_se_declara_sumable() -> None:
    """Un porcentaje no se suma: ni entre partidas, ni entre meses.

    `cierre` ya lo tenía bien en sus siete `*_pct`, todos `promedio`. Los dos de
    `stg.plan_mensual` estaban en `suma_solo_dentro_del_mes` y nadie los veía,
    porque son únicos en su objeto y la comprobación cruzada no alcanza.
    """
    malos = [
        f"{objeto}.{c.nombre} -> {c.agregacion}"
        for objeto, c in _columnas_de_porcentaje()
        if c.agregacion not in PORCENTAJES_NO_SUMABLES
    ]
    assert malos == [], (
        f"un porcentaje declarado sumable invita a un `SUM` que no significa "
        f"nada: {malos}. Los de `cierre` son `promedio`"
    )


def test_f006_r10_el_punto_ciego_de_la_comprobacion_cruzada_esta_declarado() -> None:
    """El hueco que NO se cierra, contado con su número.

    Este test no comprueba una ficha: fija que el hueco siga siendo el que
    creemos. Si el número de columnas únicas se dispara, la comprobación cruzada
    está cubriendo mucho menos de lo que parece y hay que revisarla.
    """
    ambito = _objetos_del_ambito_de("R-IMPORTE-MES")
    indice = _dicc().por_nombre
    apariciones: dict[str, int] = {}
    for nombre in ambito:
        ficha = indice.get(nombre)
        if ficha is None:
            continue
        for c in ficha.columnas:
            if c.agregacion:
                apariciones[c.nombre] = apariciones.get(c.nombre, 0) + 1

    unicas = [c for c, n in apariciones.items() if n == 1]
    assert 25 <= len(unicas) <= 40, (
        f"el punto ciego de la comprobación cruzada ha cambiado de tamaño: "
        f"{len(unicas)} columnas aparecen en un solo objeto del ámbito de "
        f"`R-IMPORTE-MES` (se midieron 32). Para ellas no hay con quién comparar "
        f"y solo las alcanzan las comprobaciones POR COLUMNA, como la de los "
        f"porcentajes de aquí arriba"
    )


def test_f006_r26_el_ejemplo_del_anio_cero_lo_soporta_el_sql() -> None:
    """El ejemplo publicado tiene que ser ejecutable, no solo verosímil.

    La ficha decía que una fase con `anio = 0` «entra igual». El punto de fondo
    —el filtro `IS NOT NULL` es inerte— se sostiene, pero el ejemplo no: unas
    líneas más abajo `make_date(f.anio, f.mes, 1)` **aborta el build** con año 0.
    Un ejemplo que el SQL no soporta es una afirmación falsa aunque la
    conclusión sea cierta.
    """
    plan = _sql("stg/08_plan_mensual.sql")
    assert re.search(r"make_date\(\s*f\.anio\s*,\s*f\.mes", plan), (
        "`make_date` ya no construye el mes desde `f.anio`/`f.mes`: revisar la "
        "ficha, porque su explicación se apoya en esa línea"
    )
    texto = _columna("stg.fases", "anio").significado
    assert "entra igual" not in texto, (
        "la ficha vuelve a decir que una fase con `anio = 0` entra: `make_date` "
        "aborta el build"
    )
    assert "make_date" in texto, (
        "tiene que decir cuál es la guarda que SÍ actúa, ya que la del `WHERE` "
        "no hace nada"
    )


# ---------------------------------------------------------------------------
# El aviso del duplicado se DERIVA, no se propaga a mano (13ª pasada)
# ---------------------------------------------------------------------------
#
# Van **cuatro** veces que una propagación deja fuera a una hermana. La cuarta
# fue `mart.v_pbi_fact_categoria`, que sirve `importe_origen` **a las tarjetas de
# KPI de Power BI** y se quedó sin una palabra del problema.
#
# El patrón es siempre el mismo: corrijo donde me señalan y mantengo a mano una
# lista de quién más está afectado. Así que la lista deja de mantenerse a mano:
# se deriva de quién lee la familia del fact **y publica una medida**.

#: Las columnas cuyo valor depende del duplicado. Una ficha que las publique y
#: no avise manda a alguien a sumar mal.
_MEDIDAS_DEL_FACT = (
    "importe_mes",
    "importe_origen",
    "importe_mes_raw",
    "importe_origen_raw",
    "can_mes",
    "can_origen",
    "total_incurrido",
    "total_incurrido_mes",
)


def _objetos_que_sirven_medidas_del_fact() -> list[str]:
    """Fichas de `mart` que leen del fact y publican alguna de sus medidas.

    Las dimensiones (`v_pbi_dim_*`) leen del fact para sacar el calendario o el
    catálogo de obras, pero **no publican medidas**, así que el duplicado no las
    afecta y no tienen que avisar de nada.
    """
    afectados: list[str] = []
    for ficha in _dicc().fichas:
        if ficha.esquema != "mart":
            continue
        origen = _ficheros_del_objeto(ficha.nombre)
        if not origen:
            continue
        sql = "\n".join(origen)
        if not re.search(r"FROM\s+mart\.fact_seguimiento_(mensual|categoria)", sql):
            continue
        if any(c.nombre in _MEDIDAS_DEL_FACT for c in ficha.columnas):
            afectados.append(ficha.nombre)
    return sorted(afectados)


def _ficheros_del_objeto(nombre: str) -> list[str]:
    from tests.test_f006_fichas import _ficheros_que_pueblan

    raiz = pathlib.Path(__file__).resolve().parents[1]
    base = raiz / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
    return [
        (base / f).read_text(encoding="utf-8")
        for f in _ficheros_que_pueblan().get(nombre.lower(), ())
    ]


def test_f006_r10_control_la_derivacion_encuentra_los_afectados() -> None:
    """Sin esto, un cambio de nombre dejaría la lista vacía y el test en verde."""
    afectados = _objetos_que_sirven_medidas_del_fact()
    assert len(afectados) >= 4, f"solo {afectados}: la derivación se ha quedado corta"
    assert "mart.v_pbi_fact_categoria" in afectados, (
        "es la que la propagación a mano dejó fuera, y sirve `importe_origen` a "
        "las tarjetas de KPI"
    )
    # Y que NO arrastre las dimensiones, que no publican medidas.
    assert not [o for o in afectados if ".v_pbi_dim_" in o]


#: Los números medidos del defecto, cada uno con lo que mide. Un objeto puede
#: citar el suyo: exigir siempre «8.778» obligaba a `fact_seguimiento_categoria`
#: a dar un número que **no es el suyo** —allí el grano es la categoría y son 37
#: celdas—, y así el test empujaba a escribir una cifra menos precisa.
NUMEROS_DEL_DEFECTO = ("8.778", "37 celdas", "39,07")


@pytest.mark.parametrize("objeto", _objetos_que_sirven_medidas_del_fact())
def test_f006_r10_todo_objeto_que_sirve_medidas_del_fact_avisa(objeto: str) -> None:
    """Quien publica una medida del fact tiene que avisar, y con una cifra medida."""
    ficha = _dicc().por_nombre[objeto]
    texto = f"{ficha.descripcion} {ficha.grano or ''}"
    assert any(contiene(texto, n) for n in NUMEROS_DEL_DEFECTO), (
        f"{objeto} sirve medidas de `mart.fact_seguimiento_mensual` y no avisa "
        f"del duplicado con ninguna cifra medida ({list(NUMEROS_DEL_DEFECTO)})"
    )


@pytest.mark.parametrize("objeto", _objetos_que_sirven_medidas_del_fact())
def test_f006_r10_el_aviso_no_alarma_sobre_la_medida_sana(objeto: str) -> None:
    """El aviso estuvo INVERTIDO y es lo peor que le puede pasar a uno.

    Decía «el importe viene inflado» en bloque. Medido contra la base sobre 200
    series afectadas: `importe_mes` **telescopea** y su suma es correcta en
    200/200, mientras `SUM(importe_origen)` solo coincide en 28/200. O sea que el
    aviso alarmaba sobre la medida sana y callaba sobre la enferma: quien lo
    leyera evitaría `importe_mes`, que está bien, y sumaría `importe_origen`, que
    está mal.
    """
    ficha = _dicc().por_nombre[objeto]
    texto = f"{ficha.descripcion} {ficha.grano or ''}"
    if "importe_mes" not in [c.nombre for c in ficha.columnas]:
        pytest.skip(f"{objeto} no publica `importe_mes`")
    assert "telescopea" in texto or "telescopean" in texto, (
        f"{objeto} avisa del duplicado sin decir que las medidas del MES se "
        f"pueden sumar igualmente: sin eso, el aviso se lee como que todo está mal"
    )


# ---------------------------------------------------------------------------
# El aviso baja a la COLUMNA, no se queda en la cabecera (14ª pasada)
# ---------------------------------------------------------------------------
#
# El derivador anterior exigía el aviso en `descripcion` o `grano`, o sea **a
# nivel de objeto**. Y por ahí se coló el peor defecto de la feature:
# `mart.fact_seguimiento_categoria.importe_origen` **está doblado en el valor
# almacenado** —el build hace `SUM(importe_origen)` sobre filas duplicadas cuyo
# acumulado es idéntico— mientras su ficha de columna decía «ya es acumulado» con
# `agregacion: ultimo_valor`, es decir: *tómalo tal cual*.
#
# Medido el 2026-08-22: **37 celdas de 8 obras, 39,07 M EUR de más**. Alguien
# pregunta cuánto lleva a origen una obra, lee una fila y recibe el doble **con
# el diccionario respaldándolo**, que es peor que no documentar nada.
#
# El reviewer dio el defecto por cerrado media hora antes porque verificó
# `descripcion` y `grano` —donde el derivador exigía el aviso— y no abrió las
# fichas de columna: **heredó el punto ciego del guardián que estaba
# verificando**. Por eso la comprobación baja a la columna.

def _acumuladas_de(objeto: str) -> list[str]:
    """Las columnas acumuladas a origen de un objeto, DERIVADAS de su ficha.

    Antes esto era una tupla escrita a mano bajo un comentario que decía «se
    derivan». La afirmación falsa más barata de arreglar de toda la feature, y
    del mismo tipo que las que llevamos quince pasadas corrigiendo: un texto que
    describe un mecanismo que no existe.

    El criterio sí es derivable y sale del propio diccionario: una columna es
    acumulada a origen si se declara `ultimo_valor` —que es justamente lo que
    esa agregación significa: no se suma, se toma el último— y lleva una unidad,
    o sea es una medida y no una clave.
    """
    ficha = _dicc().por_nombre[objeto]
    return sorted(
        c.nombre
        for c in ficha.columnas
        if c.agregacion == "ultimo_valor" and (c.unidad or "").strip()
    )


def test_f006_r10_control_las_acumuladas_se_derivan_de_la_ficha() -> None:
    """Con los nombres que la lista a mano traía, para que la derivación valga."""
    derivadas = _acumuladas_de("mart.fact_seguimiento_categoria")
    assert "importe_origen" in derivadas and "importe_origen_raw" in derivadas
    assert "importe_mes" not in derivadas, "el del mes no es acumulado"
    assert derivadas, "la derivación no encuentra ninguna: revisar antes de fiarse"


def _objetos_que_agregan_el_fact() -> list[str]:
    """Los que hacen `SUM(...)` sobre el fact y por tanto doblan el acumulado.

    Se distingue de los que solo lo leen: una pasarela propaga el duplicado como
    filas —visible— y una agregación lo funde en un número —invisible—.
    """
    from tests.test_f006_fichas import _bloque_del_objeto

    agregan: list[str] = []
    for ficha in _dicc().fichas:
        if ficha.esquema != "mart":
            continue
        # SOLO su bloque: `05_views_powerbi.sql` construye seis vistas, y mirar
        # el fichero entero metía a `mart.v_pbi_fact` —que es una pasarela y NO
        # dobla nada— por el `FROM` de su vecina. Es el mismo punto ciego que ya
        # apareció en `_proyeccion_de` y en el derivador de alias.
        bloque = _bloque_del_objeto(
            "\n".join(_ficheros_del_objeto(ficha.nombre)), ficha.nombre
        )
        dobla = re.search(r"SUM\s*\(\s*importe_origen", bloque, re.IGNORECASE)
        hereda = re.search(
            r"FROM\s+mart\.fact_seguimiento_categoria", bloque, re.IGNORECASE
        ) and bool(_acumuladas_de(ficha.nombre))
        if dobla or hereda:
            agregan.append(ficha.nombre)
    return sorted(agregan)


def test_f006_r10_control_se_identifican_los_objetos_que_doblan() -> None:
    """Si la derivación se quedara vacía, los tests de abajo pasarían solos."""
    objetos = _objetos_que_agregan_el_fact()
    assert "mart.fact_seguimiento_categoria" in objetos, (
        "es el que hace `SUM(importe_origen)` sobre las filas duplicadas"
    )
    assert "mart.v_pbi_fact_categoria" in objetos, "y el que lo sirve a Power BI"


#: Lo que ancla el relato del defecto histórico en una ficha. Sustituye a la
#: palabra «DOBLADO», que era el marcador mientras el defecto estaba ABIERTO.
MARCA_DEFECTO_HISTORICO = "F-042"


@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_el_aviso_del_doblado_esta_en_la_columna(objeto: str) -> None:
    """En el `significado` de cada acumulada, no en la cabecera del objeto.

    Quien consulta una columna concreta recibe su ficha de columna. Un aviso en
    la descripción del objeto no le llega.

    **Qué exigía y por qué cambió (F-042, R18).** Exigía la palabra **DOBLADO**
    en cada acumulada, porque el defecto estaba ABIERTO y había que gritarlo. Con
    el build corregido, R18 pide justo lo contrario —retirar el aviso—, así que
    este guardián estaba **obligando a incumplir un requisito**: mientras
    existiera, la palabra no se podía quitar. Es el patrón «el guardián enseña a
    mirar donde él mira», ahora en su versión más cara: el guardián decidiendo lo
    que la ficha puede decir.

    Lo que ahora se exige es lo que no caduca: que la columna cuente **qué pasó**
    —y la marca de eso es citar la feature— y que diga **que es un acumulado**,
    que es la trampa permanente. La palabra de alarma se queda fuera, y que no
    vuelva lo vigila
    `test_f042_r18_ninguna_ficha_describe_el_doblado_como_vigente`.
    """
    ficha = _dicc().por_nombre[objeto]
    mudas = [
        c.nombre
        for c in ficha.columnas
        if c.nombre in _acumuladas_de(objeto)
        and not (
            contiene(c.significado or "", MARCA_DEFECTO_HISTORICO)
            and contiene(c.significado or "", "acumulado")
        )
    ]
    assert mudas == [], (
        f"{objeto}: las columnas {mudas} estuvieron al doble y su `significado` "
        f"no lo cuenta, o no dice que son un acumulado. Quien lea una fila y no "
        f"sepa ninguna de las dos cosas sumará mal o desconfiará de un dato bueno"
    )


@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_la_columna_sana_dice_que_lo_es(objeto: str) -> None:
    """Para no repetir el error de alarmar en bloque sobre la medida buena.

    **Qué exigía antes de F-042 y por qué cambió.** Exigía la frase «NO esta
    afectada [por el duplicado]». Con el duplicado ya corregido en el build, esa
    frase describe un defecto que no existe, y un guardián que obliga a
    escribirla convierte la ficha en un museo: dentro de un año nadie sabrá si
    el aviso sigue vigente.

    Lo que sí es permanente, y es lo que ahora se exige, es **por qué**
    `importe_mes` estaba sana y lo sigue estando: **telescopea**, cada fila trae
    la diferencia con la anterior. Esa propiedad es la que hace que su suma sea
    el movimiento del periodo, la que se midió 200/200 series, y la razón por la
    que F-042 renumera el orden interno de las fases en vez de limitarse a
    borrar la fila sobrante. Si algún día dejara de telescopear, este test cae.
    """
    ficha = _dicc().por_nombre[objeto]
    mes = next((c for c in ficha.columnas if c.nombre == "importe_mes"), None)
    if mes is None:
        pytest.skip(f"{objeto} no publica `importe_mes`")
    assert contiene(mes.significado, "elescopea"), (
        f"{objeto}.importe_mes es la vía buena y su ficha no dice por qué: sin "
        f"«telescopea», el aviso de al lado se lee como que todo el objeto está "
        f"mal, que es el error que ya se cometió una vez"
    )


# ---------------------------------------------------------------------------
# La cabecera no puede contradecir a las columnas (15ª pasada)
# ---------------------------------------------------------------------------
#
# Patrón con nombre: **el guardián enseña a mirar donde él mira**. Van tres.
#
#   13ª · el derivador exigía el aviso en `descripcion`/`grano`, y el reviewer
#         verificó ahí; el defecto vivía en las fichas de columna.
#   14ª · el derivador pasó a exigirlo en la columna, y el reviewer verificó
#         ahí; la cabecera se quedó afirmando lo contrario.
#   15ª · lo destapó ir a mirar **cómo llega el diccionario al agente**:
#         `listar_tablas` entrega descripción y grano **sin columnas**, así que
#         el agente veía solo el texto tranquilizador; `describir_tabla` entrega
#         las dos y las veía **contradiciéndose**.
#
# Mover la exigencia de sitio no cierra nada: la cierra exigir que **las dos
# partes digan lo mismo**. Eso es lo que comprueba esto.

@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_la_cabecera_no_contradice_a_sus_columnas(objeto: str) -> None:
    """Si una columna avisa de que su valor está doblado, la cabecera también.

    `listar_tablas` del MCP entrega **descripción y grano, sin columnas**
    (`presentadores.py`). Un aviso que solo vive en la columna no llega por esa
    vía, y una cabecera tranquilizadora se lee como que el objeto está sano.
    """
    ficha = _dicc().por_nombre[objeto]
    cabecera = f"{ficha.descripcion} {ficha.grano or ''}"

    columnas_avisadas = [
        c.nombre
        for c in ficha.columnas
        if contiene(c.significado or "", MARCA_DEFECTO_HISTORICO)
    ]
    if not columnas_avisadas:
        pytest.skip(f"{objeto} no tiene columnas que cuenten el defecto histórico")

    assert contiene(cabecera, MARCA_DEFECTO_HISTORICO), (
        f"{objeto}: las columnas {columnas_avisadas} cuentan que su valor estuvo "
        f"al doble y la cabecera no lo cuenta. Quien use `listar_tablas` recibe "
        f"solo la cabecera y no puede interpretar un informe viejo"
    )


@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_la_cabecera_nombra_las_columnas_afectadas(objeto: str) -> None:
    """La otra mitad, y esta vez SIN comparar frases.

    La versión anterior mantenía una lista de cuatro «frases tranquilizadoras» y
    entró por tres sitios a la vez:

    1. **Otra redacción.** «la clave sale única y no se repite ninguna fila» no
       estaba en la lista. Enumerar redacciones a mano es la comprobación mal
       planteada: el idioma tiene infinitas.
    2. **Frase partida por línea en blanco**, sin normalizar. El plegado, cuarta
       aparición.
    3. **El salvoconducto**, y era el peor: `"el numero de dentro" not in
       cabecera` se evaluaba sobre **todo el texto**, y esa frase es la
       formulación nueva y está siempre, así que **dejaba la lista entera
       inerte**. Un guardián verde que no miraba nada.

    Lo que sí es derivable, sin listas y sin juzgar prosa: **la cabecera tiene
    que NOMBRAR cada columna afectada**. Una cabecera que solo tranquiliza no
    puede pasar, porque no las nombra; y quien lea únicamente `listar_tablas`
    sabe cuáles no se puede creer.

    **Límite declarado**: decidir si un texto «tranquiliza» no es derivable, así
    que no se intenta. Se comprueba lo objetivo —el marcador y los nombres—, y
    lo demás queda en la revisión humana.
    """
    ficha = _dicc().por_nombre[objeto]
    cabecera = f"{ficha.descripcion} {ficha.grano or ''}"

    afectadas = [
        c.nombre
        for c in ficha.columnas
        if contiene(c.significado or "", MARCA_DEFECTO_HISTORICO)
    ]
    if not afectadas:
        pytest.skip(f"{objeto} no tiene columnas que cuenten el defecto histórico")

    sin_nombrar = [c for c in afectadas if not contiene(cabecera, c)]
    assert sin_nombrar == [], (
        f"{objeto}: la cabecera avisa del doblado pero no nombra {sin_nombrar}, "
        f"que son las columnas afectadas. Quien lea solo `listar_tablas` no sabe "
        f"de cuáles desconfiar"
    )


def test_f006_r10_control_el_guardian_de_coherencia_muerde() -> None:
    """Las tres vías por las que entró, convertidas en control permanente.

    Sin esto, cualquiera de los tres arreglos podría revertirse en verde.

    La 17ª pasada añade una cuarta, que es la segunda otra vez: el plegado
    seguía sin normalizar en el guardián hermano, dentro de este mismo módulo.
    Arreglar una comparación y dejar la de al lado es el patrón que lleva
    dieciséis pasadas repitiéndose, así que el criterio derivado que lo caza
    vive en `test_f006_copias.py` y barre todos los módulos, no este.
    """
    afectadas = ["importe_origen", "importe_origen_raw"]

    # Vía 1 · otra redacción: la cabecera tranquiliza sin nombrar nada.
    otra = "lo arreglo F-042, pero la clave sale unica y no se repite ninguna fila"
    assert [c for c in afectadas if not contiene(otra, c)] == afectadas, (
        "una cabecera que no nombra ninguna columna afectada tiene que fallar, "
        "diga lo que diga"
    )

    # Vía 2 · frase partida por el ajuste de línea: se ve igual.
    partida = "el valor de importe_origen\n\ny de importe_origen_raw, en F-042"
    assert [c for c in afectadas if not contiene(partida, c)] == [], (
        "normalizando espacios, una cabecera envuelta cuenta igual"
    )

    # Vía 2 bis · el mismo plegado seguía vivo **en el guardián de al lado**:
    # `..._la_columna_sana_dice_que_lo_es` buscaba «NO esta afectada» con `in` a
    # pelo sobre el `significado`. Una línea en blanco del bloque `>-` y el aviso
    # de la medida buena desaparecía para el test, no para el lector.
    plegada = "importe_mes NO esta\n\nafectada por el duplicado del fact"
    assert "NO esta afectada" not in plegada, "así estaba escrito, y así no se veía"
    assert contiene(plegada, "NO esta afectada"), "normalizando, sí"

    # Vía 3 · ya no hay lista de frases, así que no hay salvoconducto que la
    # apague. Se comprueba lo objetivo: que la constante no vuelva.
    fuente = pathlib.Path(__file__).read_text(encoding="utf-8")
    # El nombre se compone en tiempo de ejecución: escribirlo entero aquí haría
    # que este control se cazara a sí mismo, que es el fallo que ya tuvo la
    # primera versión de esta comprobación.
    constante = "_TRANQUI" + "LIZADORAS"
    assert f"{constante} = (" not in fuente, (
        "vuelve la lista de frases escritas a mano. Enumerar redacciones no "
        "funciona —el idioma tiene infinitas— y además invita al salvoconducto "
        "global que dejó la comprobación inerte"
    )


def test_f006_r10_control_la_coherencia_se_comprueba_sobre_alguien() -> None:
    """Si el derivador se vaciara, los dos de arriba pasarían sin mirar nada."""
    objetos = _objetos_que_agregan_el_fact()
    assert len(objetos) >= 2
    con_aviso = [
        o
        for o in objetos
        if any(
            contiene(c.significado or "", MARCA_DEFECTO_HISTORICO)
            for c in _dicc().por_nombre[o].columnas
        )
    ]
    assert len(con_aviso) >= 2, f"solo {con_aviso} cuentan el defecto en columna"


# ---------------------------------------------------------------------------
# Una remisión tiene que llevar a donde dice (17ª pasada)
# ---------------------------------------------------------------------------
#
# Las dos fichas del preagregado remitían así, en el texto que ve el agente:
#
#   «La consulta que da ese numero esta en el grano de
#    `mart.fact_seguimiento_mensual`, junto a la explicacion de por que 8.778,
#    37 y 22 son numeros distintos…»
#
# **Y la consulta que hay allí devuelve 8.778 y 9 obras**, no las 37 celdas ni
# los 39,07 M EUR de los que hablaba «ese numero». Quien la ejecute para
# comprobar el aviso obtiene otra cosa, y lo razonable es que desconfíe del aviso
# entero: justo el que más importa. Una remisión que no lleva a donde dice es
# peor que no ponerla, porque el agente la va a seguir.
#
# El criterio, derivable y sin juzgar prosa: **los números que una remisión
# atribuye a la consulta de otro objeto tienen que estar declarados junto a esa
# consulta**. Si no lo están, la remisión les atribuye un resultado que esa
# consulta no da. Y una remisión sin ningún número no dice qué devuelve: también
# falla, porque es la formulación vaga con la que entró este defecto.

_REMISION = re.compile(
    r"consult[ao][^.]{0,140}?\ben (?:el grano|la descripcion|la ficha) de "
    r"`([a-z_]+\.[a-z_0-9]+)`",
    re.IGNORECASE,
)


def _prosa_de(objeto: str) -> list[tuple[str, str]]:
    """Todos los campos de texto de una ficha, cabecera y columnas.

    Barrer solo `descripcion` es el punto ciego que ya costó cuatro pasadas: el
    defecto sobrevive **en el campo de al lado**.
    """
    ficha = _dicc().por_nombre[objeto]
    campos = [
        (f"{objeto}.descripcion", ficha.descripcion),
        (f"{objeto}.grano", ficha.grano or ""),
    ]
    campos += [(f"{objeto}.avisos[{i}]", a) for i, a in enumerate(ficha.avisos)]
    for columna in ficha.columnas:
        campos.append((f"{objeto}::{columna.nombre}.significado", columna.significado or ""))
        campos.append(
            (f"{objeto}::{columna.nombre}.nulo_significa", columna.nulo_significa or "")
        )
    return [(ruta, texto) for ruta, texto in campos if texto]


def _cifras(texto: str) -> set[str]:
    """Los números de un texto, sin las fechas ISO, que no son medidas."""
    sin_fechas = re.sub(r"\d{4}-\d{2}-\d{2}", " ", texto)
    return set(re.findall(r"\d[\d.,]*\d|\d", sin_fechas))


def _entorno_de_la_consulta(objeto: str) -> str:
    """El párrafo que publica una consulta y el que la presenta.

    Los bloques `>-` pliegan las líneas de un párrafo con espacios y dejan un
    salto real donde había una línea en blanco, así que un párrafo es una línea
    del texto cargado.
    """
    trozos: list[str] = []
    for _, texto in _prosa_de(objeto):
        parrafos = [p for p in texto.split("\n") if p.strip()]
        for i, parrafo in enumerate(parrafos):
            if re.search(r"\bSELECT\b", parrafo, re.IGNORECASE):
                trozos.extend(parrafos[max(0, i - 1) : i + 1])
    return " ".join(trozos)


def _remisiones_a_una_consulta() -> list[tuple[str, str, str]]:
    """(campo que remite, objeto remitido, frase). DERIVADO, sin lista."""
    salida: list[tuple[str, str, str]] = []
    for ficha in _dicc().fichas:
        for ruta, texto in _prosa_de(ficha.nombre):
            for frase in re.split(r"(?<=\.)\s+", normalizado(texto)):
                encontrada = _REMISION.search(frase)
                if encontrada:
                    salida.append((ruta, encontrada.group(1), frase))
    return salida


def test_f006_r10_control_hay_remisiones_que_comprobar() -> None:
    """Si el derivador se quedara vacío, el test de abajo pasaría sin mirar."""
    remisiones = _remisiones_a_una_consulta()
    assert len(remisiones) >= 2, f"solo {remisiones}: la derivación se ha quedado corta"
    destinos = {destino for _, destino, _ in remisiones}
    assert "mart.fact_seguimiento_mensual" in destinos, (
        "es el único objeto que publica una consulta y al que se remite"
    )
    entorno = _entorno_de_la_consulta("mart.fact_seguimiento_mensual")
    assert "8.778" in _cifras(entorno), (
        f"el entorno de la consulta remitida no declara su resultado: {entorno[:200]}"
    )


@pytest.mark.parametrize("origen,destino,frase", _remisiones_a_una_consulta())
def test_f006_r10_una_remision_dice_lo_que_esa_consulta_devuelve(
    origen: str, destino: str, frase: str
) -> None:
    """Y los números que le atribuye son los que están declarados con ella."""
    assert destino in _dicc().por_nombre, f"{origen} remite a `{destino}`, que no existe"

    entorno = _entorno_de_la_consulta(destino)
    assert entorno, (
        f"{origen} remite a la consulta de `{destino}` y `{destino}` no publica "
        f"ninguna consulta"
    )

    citadas = _cifras(frase)
    assert citadas, (
        f"{origen} remite a la consulta de `{destino}` sin decir qué devuelve. "
        f"«La consulta que da ese numero está en…» es la formulación con la que "
        f"entró una remisión falsa: el agente la sigue y obtiene otra cosa"
    )

    inventadas = sorted(citadas - _cifras(entorno))
    assert inventadas == [], (
        f"{origen} atribuye {inventadas} a la consulta de `{destino}`, y allí no "
        f"está declarado que la consulta dé eso. Quien la ejecute para comprobar "
        f"el aviso obtendrá otro número y desconfiará del aviso entero.\n"
        f"  frase: {frase}"
    )


def test_f006_r10_control_una_remision_inventada_no_pasa() -> None:
    """Sin esto, un entorno con muchos números dejaría pasar cualquier cosa."""
    entorno = _entorno_de_la_consulta("mart.fact_seguimiento_mensual")
    inventada = "La consulta del grano de `x.y` devuelve 123.456 filas."
    assert sorted(_cifras(inventada) - _cifras(entorno)) == ["123.456"], (
        "una cifra que la consulta no declara tiene que salir como inventada"
    )
    # Y el patrón reconoce la formulación vaga con la que entró el defecto.
    vieja = (
        "La consulta que da ese numero esta en el grano de "
        "`mart.fact_seguimiento_mensual`, junto a la explicacion."
    )
    assert _REMISION.search(vieja), "la remisión vaga tiene que ser reconocida"


# ---------------------------------------------------------------------------
# El 22 mide la CAUSA y el 9 el EFECTO: nunca van separados (17ª pasada)
# ---------------------------------------------------------------------------
#
# «22 obras» se publicó durante varias pasadas como si fuese el número de obras
# con filas duplicadas en el fact. No lo es: **22** obras tienen dos fases con el
# mismo `ano` y `mes` en Sigrid —la causa—, y de ellas solo **9** llegan a
# producir filas duplicadas, porque las demás no tienen presupuesto en esos
# meses. La corrección llegó a la cabecera y **no viajó** a las fichas de
# columna, que es el patrón de esta feature: el defecto sobrevive en el campo de
# al lado.
#
# Barrer el YAML crudo no lo habría visto —las frases van plegadas—, así que esto
# barre el diccionario **cargado**, campo a campo, cabecera y columnas.
#
# El criterio: donde se nombre el 22 tiene que estar el 9. Un 22 solo es la cifra
# mal atribuida otra vez.


def _parrafos_con_la_causa() -> list[tuple[str, str]]:
    """Párrafos del diccionario cargado que nombran las 22 obras."""
    salida: list[tuple[str, str]] = []
    for ficha in _dicc().fichas:
        for ruta, texto in _prosa_de(ficha.nombre):
            parrafos = [p for p in texto.split("\n") if p.strip()]
            for i, parrafo in enumerate(parrafos):
                if "22" in _cifras(parrafo):
                    salida.append((f"{ruta}#{i}", parrafo))
    for regla in _dicc().reglas:
        for campo in ("regla", "motivo"):
            texto = getattr(regla, campo) or ""
            for i, parrafo in enumerate(p for p in texto.split("\n") if p.strip()):
                if "22" in _cifras(parrafo):
                    salida.append((f"{regla.codigo}.{campo}#{i}", parrafo))
    return salida


def test_f006_r10_control_el_22_sigue_publicado_en_algun_sitio() -> None:
    """Si nadie lo nombrara, el test de abajo pasaría sin mirar nada."""
    parrafos = _parrafos_con_la_causa()
    assert len(parrafos) >= 4, f"solo {[r for r, _ in parrafos]}: barrido corto"
    rutas = {ruta.split("#")[0] for ruta, _ in parrafos}
    assert any("::importe_origen." in r for r in rutas), (
        "las fichas de COLUMNA son las que se quedaron sin la corrección: si ya "
        "no nombran la causa, revisar este control antes de fiarse"
    )


@pytest.mark.parametrize("ruta,parrafo", _parrafos_con_la_causa())
def test_f006_r10_donde_se_nombra_la_causa_se_nombra_el_efecto(
    ruta: str, parrafo: str
) -> None:
    """22 son las obras con dos fases; 9, las que duplican filas en el fact."""
    assert "9" in _cifras(parrafo), (
        f"{ruta} nombra las 22 obras sin decir que solo 9 duplican filas aquí. "
        f"El 22 mide la CAUSA en `stg.fases`; atribuirlo al duplicado del fact es "
        f"la cifra mal atribuida que ya se publicó.\n  párrafo: {parrafo[:300]}"
    )


# ---------------------------------------------------------------------------
# R18 · el defecto se cuenta en PASADO, y nadie lo resucita (F-042)
# ---------------------------------------------------------------------------
#
# R18 pide retirar el aviso de dato doblado. Retirarlo no es borrar la historia
# —un informe de hace un mes sigue trayendo el doble y hay que poder
# interpretarlo—, es dejar de afirmar que el defecto SIGUE. La diferencia se
# nota en el tiempo verbal, y el tiempo verbal sí es comprobable.
#
# Hasta esta pasada lo impedia un guardian: exigia la palabra «DOBLADO» en cada
# columna acumulada, asi que mientras existiera R18 no se podia cumplir. Un
# guardian decidiendo lo que la ficha puede decir es el caso mas caro del patron
# «el guardian ensena a mirar donde el mira».

#: Formas de afirmar el defecto EN PRESENTE. No se enumeran redacciones (eso ya
#: falló una vez): se enumeran los verbos en presente junto al hecho.
_EN_PRESENTE = (
    "esta doblado",
    "estan doblados",
    "viene doblado",
    "vienen doblados",
    "esta al doble",
    "el valor almacenado esta",
    "devuelve el doble",
)


def test_f042_r18_ninguna_ficha_describe_el_doblado_como_vigente() -> None:
    """Barre el diccionario CARGADO, cabecera y columnas, campo a campo.

    Barrer el YAML crudo no valdría: las frases van plegadas por el bloque `>-`
    y una afirmación partida por el ajuste de línea se escaparía. Es el mismo
    plegado que ya dejó ciega a media docena de comprobaciones de esta feature.
    """
    vivas: list[tuple[str, str]] = []
    for ficha in _dicc().fichas:
        for ruta, texto in _prosa_de(ficha.nombre):
            for forma in _EN_PRESENTE:
                # En minúsculas: el aviso viejo iba en MAYÚSCULAS («EL VALOR
                # ALMACENADO ESTA DOBLADO») y un detector sensible a la caja lo
                # habría dejado pasar entero.
                if contiene(texto.lower(), forma):
                    vivas.append((ruta, forma))

    assert vivas == [], (
        f"estas fichas siguen afirmando el doblado EN PRESENTE: {vivas}. R18 pide "
        f"retirar el aviso; el hecho se cuenta en pasado, con su cifra, para que "
        f"un informe viejo se pueda interpretar"
    )


def test_f042_r18_control_el_detector_de_presente_reconoce_la_redaccion_vieja() -> None:
    """Sin esto, cambiar una tilde dejaría el barrido inerte y en verde."""
    vieja = "**OJO: EL VALOR ALMACENADO ESTA DOBLADO en 37 celdas de 8 obras.**"

    assert any(contiene(vieja.lower(), f) for f in _EN_PRESENTE)
    # Y la redacción nueva, en pasado, tiene que pasar limpia.
    nueva = "Hasta el build de F-042 este valor salia al doble en 35 celdas."
    assert not any(contiene(nueva.lower(), f) for f in _EN_PRESENTE)


# ---------------------------------------------------------------------------
# R19 · la superficie de consumo de OTROS esquemas tambien cuelga del fact
# ---------------------------------------------------------------------------
#
# `_objetos_que_agregan_el_fact()` filtra `esquema != "mart"`, asi que
# `cierre.v_pbi_planif_vs_real` —que lee de `mart.fact_seguimiento_categoria` y
# es superficie de consumo servida al MCP y a Power BI— no lo miraba nadie. R19
# la nombra explicitamente y su texto se escribio, pero sin guardian: manana
# alguien lo borra y no se entera nadie. Es la leccion de F-006 —«el aviso baja
# al significado»— con el punto ciego una capa mas alla.


def _objetos_que_leen_el_fact_fuera_de_mart() -> list[str]:
    """Fichas de CUALQUIER esquema que no sea `mart` y lean de su familia."""
    fuera: list[str] = []
    for ficha in _dicc().fichas:
        if ficha.esquema == "mart":
            continue
        from tests.test_f006_fichas import _bloque_del_objeto

        origen = _ficheros_del_objeto(ficha.nombre)
        if not origen:
            continue
        # SOLO su bloque: el fichero que crea `v_fact_periodificado` crea
        # también `aux.periodificacion_partida`, y mirar el fichero entero
        # arrastraba a una tabla de reglas que NO lee del fact. Es el mismo
        # punto ciego que ya documenta `_objetos_que_agregan_el_fact`.
        bloque = _bloque_del_objeto("\n".join(origen), ficha.nombre)
        if re.search(r"FROM\s+mart\.fact_seguimiento_(mensual|categoria)", bloque):
            fuera.append(ficha.nombre)
    return sorted(fuera)


def test_f006_r19_control_hay_consumidores_del_fact_fuera_de_mart() -> None:
    """Si el derivador se vaciara, el test de abajo pasaría sin mirar nada."""
    objetos = _objetos_que_leen_el_fact_fuera_de_mart()

    assert "cierre.v_pbi_planif_vs_real" in objetos, (
        "es la vista que F-047 rescató y que R19 nombra: si ya no lee del fact, "
        "revisar este control antes de fiarse del verde"
    )


@pytest.mark.parametrize("objeto", _objetos_que_leen_el_fact_fuera_de_mart())
def test_f006_r19_un_consumidor_del_fact_de_otro_esquema_declara_de_que_cuelga(
    objeto: str,
) -> None:
    """Tiene que decir de qué tabla vive y por qué el defecto de esa tabla le
    afectó o no. «No le afectó» es una respuesta válida —y es la de esta vista,
    que usa `importe_mes`— pero hay que darla: el defecto de una tabla no se
    hereda entero, se hereda columna a columna."""
    ficha = _dicc().por_nombre[objeto]
    cabecera = f"{ficha.descripcion} {ficha.grano or ''}"

    assert contiene(cabecera, "fact_seguimiento"), (
        f"{objeto} lee de la familia del fact y su cabecera no lo dice"
    )
    assert contiene(cabecera, MARCA_DEFECTO_HISTORICO), (
        f"{objeto} cuelga de la tabla que estuvo al doble y no cuenta si eso le "
        f"afectó. Es superficie de consumo: quien la abre no ve `mart`"
    )
