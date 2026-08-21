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
    assert "no descarta nada" in _columna("stg.fases", "anio").significado, (
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


@pytest.mark.parametrize("objeto", _objetos_que_sirven_medidas_del_fact())
def test_f006_r10_todo_objeto_que_sirve_medidas_del_fact_avisa(objeto: str) -> None:
    """Quien publica una medida del fact tiene que decir que hay duplicado."""
    ficha = _dicc().por_nombre[objeto]
    texto = f"{ficha.descripcion} {ficha.grano or ''}"
    assert "8.778" in texto, (
        f"{objeto} sirve medidas de `mart.fact_seguimiento_mensual` y no avisa "
        f"de sus 8.778 combinaciones duplicadas"
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

#: Las columnas cuyo VALOR ALMACENADO está doblado por el `SUM` sobre las filas
#: duplicadas. Se derivan: son las acumuladas a origen de los objetos que
#: agregan el fact.
_ACUMULADAS = ("importe_origen", "importe_origen_raw", "can_origen", "total_incurrido")


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
        ) and any(c.nombre in _ACUMULADAS for c in ficha.columnas)
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


@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_el_aviso_del_doblado_esta_en_la_columna(objeto: str) -> None:
    """En el `significado` de cada acumulada, no en la cabecera del objeto.

    Quien consulta una columna concreta recibe su ficha de columna. Un aviso en
    la descripción del objeto no le llega.
    """
    ficha = _dicc().por_nombre[objeto]
    mudas = [
        c.nombre
        for c in ficha.columnas
        if c.nombre in _ACUMULADAS and "DOBLADO" not in (c.significado or "")
    ]
    assert mudas == [], (
        f"{objeto}: las columnas {mudas} tienen el valor almacenado DOBLADO y su "
        f"`significado` no lo dice. Quien lea una fila recibe el doble con el "
        f"diccionario respaldándolo"
    )


@pytest.mark.parametrize("objeto", _objetos_que_agregan_el_fact())
def test_f006_r10_la_columna_sana_dice_que_lo_es(objeto: str) -> None:
    """Para no repetir el error de alarmar en bloque sobre la medida buena."""
    ficha = _dicc().por_nombre[objeto]
    mes = next((c for c in ficha.columnas if c.nombre == "importe_mes"), None)
    if mes is None:
        pytest.skip(f"{objeto} no publica `importe_mes`")
    assert "NO esta afectada" in mes.significado, (
        f"{objeto}.importe_mes es la vía buena y su ficha no lo dice: sin eso, el "
        f"aviso de al lado se lee como que todo el objeto está mal"
    )
