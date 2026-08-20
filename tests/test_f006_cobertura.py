# tests/test_f006_cobertura.py
"""
F-006 · La puerta de cobertura del diccionario (R24-R27, R29).

Dos mitades, con propósitos distintos:

* **`dominio`** — funciones puras: extraer el inventario de objetos a partir de
  textos SQL y del YAML de tablas, y evaluar la cobertura. Sin ficheros, sin
  red, sin BBDD.
* **`puerta`** — la puerta real sobre ESTE repositorio: inventaría
  `etl_sigrid/infrastructure/postgres/sql/**` y `config/tables_sigrid.yaml`,
  carga el diccionario de `config/diccionario/` y falla si algún objeto
  publicado no está documentado ni declarado en `pendientes`.

La puerta es **un trinquete barato, no una demostración**: no prueba que el
diccionario esté completo, prueba que nadie ha añadido una vista al repositorio
sin documentarla. La comprobación contra el catálogo real de la base es
`python main.py check-diccionario` (R28), que **todavía no existe**: es del
bloque H. Mientras tanto, lo que esta puerta no ve no lo ve nadie.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.inventario import (
    InformeCobertura,
    ObjetoPublicado,
    evaluar_cobertura,
    formatear_cobertura,
    objetos_de_raw,
    objetos_de_sql,
)
from tests.test_f006_formato import _columna, _dicc, _ficha

# ===========================================================================
# dominio · objetos_de_sql (R24, R29)
# ===========================================================================


def test_f006_r24_dominio_detecta_create_table_view_y_function() -> None:
    textos = {
        "mart/01_ddl.sql": "CREATE TABLE mart.fact_seguimiento_mensual (\n  x INT\n);",
        "mart/05_views.sql": "CREATE VIEW mart.v_pbi_fact AS SELECT 1;",
        "cierre/00_setup.sql": "CREATE OR REPLACE FUNCTION cierre.fn_mes_de_fase(\n",
    }

    objetos = objetos_de_sql(textos)

    assert {(o.esquema, o.objeto, o.tipo) for o in objetos} == {
        ("mart", "fact_seguimiento_mensual", "tabla"),
        ("mart", "v_pbi_fact", "vista"),
        ("cierre", "fn_mes_de_fase", "funcion"),
    }


@pytest.mark.parametrize(
    "sentencia",
    [
        "CREATE TABLE IF NOT EXISTS stg.obras (",
        "CREATE TABLE stg.obras AS SELECT 1;",
        "create table if not exists stg.obras (",
        "CREATE   TABLE   IF   NOT   EXISTS   stg.obras (",
    ],
)
def test_f006_r24_dominio_todas_las_formas_de_create_table(sentencia: str) -> None:
    objetos = objetos_de_sql({"x.sql": sentencia})

    assert [(o.esquema, o.objeto, o.tipo) for o in objetos] == [("stg", "obras", "tabla")]


@pytest.mark.parametrize(
    "sentencia",
    [
        "CREATE VIEW stg.ambitos AS SELECT 1;",
        "CREATE OR REPLACE VIEW stg.ambitos AS SELECT 1;",
        "CREATE MATERIALIZED VIEW stg.ambitos AS SELECT 1;",
    ],
)
def test_f006_r24_dominio_todas_las_formas_de_create_view(sentencia: str) -> None:
    objetos = objetos_de_sql({"x.sql": sentencia})

    assert [(o.esquema, o.objeto, o.tipo) for o in objetos] == [
        ("stg", "ambitos", "vista")
    ]


def test_f006_r24_dominio_ignora_los_comentarios_de_linea() -> None:
    """Un `CREATE` comentado no publica nada. Es el caso que más se da."""
    texto = (
        "-- CREATE TABLE mart.tabla_que_no_existe (\n"
        "CREATE TABLE mart.tabla_de_verdad (x INT);\n"
    )

    objetos = objetos_de_sql({"x.sql": texto})

    assert [o.objeto for o in objetos] == ["tabla_de_verdad"]


def test_f006_r24_dominio_ignora_los_comentarios_de_bloque() -> None:
    texto = "/* CREATE VIEW mart.fantasma AS */ CREATE VIEW mart.real AS SELECT 1;"

    objetos = objetos_de_sql({"x.sql": texto})

    assert [o.objeto for o in objetos] == ["real"]


def test_f006_r24_dominio_no_confunde_un_drop_con_un_create() -> None:
    texto = (
        "DROP VIEW IF EXISTS cierre.v_pbi_snapshot_final CASCADE;\n"
        "DROP TABLE IF EXISTS mart.fact_cierre_mensual CASCADE;\n"
    )

    assert objetos_de_sql({"x.sql": texto}) == []


def test_f006_r24_dominio_ve_los_create_dentro_de_execute() -> None:
    """`retenciones/00_setup.sql` crea dos vistas con SQL dinámico.

    Verlas es mejor que no verlas, aunque el docstring siga declarando la
    heurística: son objetos publicados de verdad y el MCP los ve en el catálogo.
    """
    texto = "    EXECUTE 'CREATE VIEW retenciones.v_src_lineas_compra AS SELECT 1';"

    objetos = objetos_de_sql({"x.sql": texto})

    assert [(o.esquema, o.objeto) for o in objetos] == [
        ("retenciones", "v_src_lineas_compra")
    ]


def test_f006_r24_dominio_deduplica_el_mismo_objeto_en_dos_ficheros() -> None:
    """`aux.periodificacion_partida` se crea en `auxiliar/` y en `mart/`."""
    textos = {
        "auxiliar/01.sql": "CREATE TABLE IF NOT EXISTS aux.periodificacion_partida (x INT);",
        "mart/04.sql": "CREATE TABLE IF NOT EXISTS aux.periodificacion_partida (x INT);",
    }

    objetos = objetos_de_sql(textos)

    assert len(objetos) == 1
    assert objetos[0].objeto == "periodificacion_partida"


def test_f006_r24_dominio_el_inventario_sale_ordenado() -> None:
    """Determinismo: el mismo repositorio da siempre el mismo informe."""
    textos = {
        "z.sql": "CREATE VIEW stg.ambitos AS SELECT 1;",
        "a.sql": "CREATE TABLE mart.fact_seguimiento_mensual (x INT);",
    }

    objetos = objetos_de_sql(textos)

    assert [o.esquema for o in objetos] == ["mart", "stg"]


def test_f006_r24_dominio_guarda_el_fichero_de_origen() -> None:
    """Para poder decir dónde está el objeto que falta por documentar."""
    objetos = objetos_de_sql({"mart/01_ddl.sql": "CREATE TABLE mart.f (x INT);"})

    assert objetos[0].origen == "mart/01_ddl.sql"


def test_f006_r29_dominio_el_docstring_declara_la_heuristica() -> None:
    """R29: leer SQL con expresiones regulares no es leer el catálogo."""
    doc = objetos_de_sql.__doc__ or ""

    assert "heurístic" in doc.lower()
    assert "tables_sigrid.yaml" in doc


def test_f006_r28_lo_que_se_dice_de_check_diccionario_es_cierto_hoy() -> None:
    """El docstring dice que `check-diccionario` no existe. Que siga siendo verdad.

    La review señaló que este test rozaba la circularidad: comprobaba que la
    cadena `check-diccionario` estuviera ESCRITA, es decir, verificaba la
    promesa y no el comando. Ahora comprueba un hecho sobre `main.py`, y el día
    que alguien implemente R28 este test se pone en rojo y obliga a corregir los
    docstrings que hoy lo dan por futuro. Que es exactamente lo que se quiere:
    que las dos cosas no se separen.
    """
    from etl_sigrid.domain.inventario import objetos_de_sql as _objetos

    main_py = (RAIZ / "main.py").read_text(encoding="utf-8")
    existe = 'cli.command("check-diccionario")' in main_py

    textos = [
        _objetos.__doc__ or "",
        (RAIZ / "etl_sigrid/domain/inventario.py").read_text(encoding="utf-8"),
        (RAIZ / "tests/test_f006_fichas.py").read_text(encoding="utf-8"),
        __doc__ or "",
    ]
    lo_dan_por_futuro = any(
        "sin implementar" in t or "todavía no existe" in t or "TODAVÍA NO EXISTE" in t
        for t in textos
    )

    assert existe is not lo_dan_por_futuro, (
        "el comando `check-diccionario` "
        + ("YA existe" if existe else "NO existe")
        + " y los docstrings dicen lo contrario"
    )


# ===========================================================================
# dominio · objetos_de_raw (R29)
# ===========================================================================


def test_f006_r29_dominio_raw_se_inventaria_desde_el_yaml_de_tablas() -> None:
    """Las tablas de `raw` las crea `ensure_raw_table` desde Python: no hay SQL."""
    tablas = [
        {"source_table": "con", "target_table": "con"},
        {"source_table": "obrparpre", "target_table": "obrparpre"},
    ]

    objetos = objetos_de_raw(tablas)

    assert {(o.esquema, o.objeto, o.tipo) for o in objetos} == {
        ("raw", "con", "tabla"),
        ("raw", "obrparpre", "tabla"),
    }
    assert all(o.origen == "config/tables_sigrid.yaml" for o in objetos)


def test_f006_r29_dominio_raw_usa_el_nombre_destino_no_el_de_origen() -> None:
    objetos = objetos_de_raw([{"source_table": "dbo_con", "target_table": "con"}])

    assert objetos[0].objeto == "con"


def test_f006_r29_dominio_raw_ignora_entradas_sin_destino() -> None:
    objetos = objetos_de_raw([{"source_table": "con"}, {"target_table": "obr"}])

    assert [o.objeto for o in objetos] == ["obr"]


# ===========================================================================
# dominio · evaluar_cobertura (R25, R26, R27)
# ===========================================================================


def _inventario(*nombres: str) -> list[ObjetoPublicado]:
    return [
        ObjetoPublicado(
            esquema=n.split(".")[0], objeto=n.split(".")[1], tipo="vista", origen="x.sql"
        )
        for n in nombres
    ]


def test_f006_r25_dominio_un_objeto_sin_ficha_rompe_la_puerta() -> None:
    """Es el caso peligroso: el agente lo ve en el catálogo e INVENTA su significado."""
    informe = evaluar_cobertura(
        _dicc(), _inventario("mart.fact_seguimiento_mensual", "mart.v_pbi_fact"), ()
    )

    assert not informe.ok
    assert [o.esquema + "." + o.objeto for o in informe.sin_ficha] == ["mart.v_pbi_fact"]


def test_f006_r25_dominio_un_objeto_declarado_pendiente_se_tolera() -> None:
    """El trinquete existe solo para poder entregar por bloques."""
    informe = evaluar_cobertura(
        _dicc(),
        _inventario("mart.fact_seguimiento_mensual", "mart.v_pbi_fact"),
        ("mart.v_pbi_fact",),
    )

    assert informe.ok
    assert informe.pendientes_declarados == ("mart.v_pbi_fact",)


def test_f006_r25_dominio_todo_documentado_es_verde() -> None:
    informe = evaluar_cobertura(_dicc(), _inventario("mart.fact_seguimiento_mensual"), ())

    assert informe.ok
    assert informe.sin_ficha == ()


def test_f006_r27_dominio_un_pendiente_ya_documentado_rompe_la_puerta() -> None:
    """El trinquete solo baja: dejar en `pendientes` algo ya escrito lo falsea."""
    informe = evaluar_cobertura(
        _dicc(),
        _inventario("mart.fact_seguimiento_mensual"),
        ("mart.fact_seguimiento_mensual",),
    )

    assert not informe.ok
    assert informe.pendientes_ya_documentados == ("mart.fact_seguimiento_mensual",)


def test_f006_r27_dominio_un_pendiente_que_no_existe_rompe_la_puerta() -> None:
    """Un pendiente fantasma infla el trinquete sin documentar nada."""
    informe = evaluar_cobertura(
        _dicc(), _inventario("mart.fact_seguimiento_mensual"), ("mart.objeto_borrado",)
    )

    assert not informe.ok
    assert "mart.objeto_borrado" in informe.pendientes_fantasma


def test_f006_r25_dominio_una_ficha_sin_objeto_publicado_rompe_la_puerta() -> None:
    """Una ficha huérfana describe algo que no existe. El agente la creerá igual."""
    informe = evaluar_cobertura(_dicc(), _inventario("mart.v_pbi_fact"), ())

    assert not informe.ok
    assert "mart.fact_seguimiento_mensual" in informe.fichas_huerfanas


def test_f006_r26_dominio_una_columna_sin_significado_en_consumo_rompe_la_puerta() -> None:
    """100 % de columnas descritas dentro de la superficie de consumo."""
    ficha = _ficha(columnas=(_columna(), _columna("mes", significado="  ")))

    informe = evaluar_cobertura(
        _dicc(fichas=[ficha]), _inventario("mart.fact_seguimiento_mensual"), ()
    )

    assert not informe.ok
    assert any("mes" in c for c in informe.columnas_sin_significado)


def test_f006_r26_dominio_un_objeto_de_consumo_sin_columnas_rompe_la_puerta() -> None:
    ficha = _ficha(columnas=())

    informe = evaluar_cobertura(
        _dicc(fichas=[ficha]), _inventario("mart.fact_seguimiento_mensual"), ()
    )

    assert not informe.ok
    assert informe.columnas_sin_significado


def test_f006_r26_dominio_fuera_del_consumo_la_falta_de_columnas_es_aviso() -> None:
    """0 % exigido fuera de la superficie de consumo: `raw` son ~800 columnas
    de Sigrid cuyo diccionario real es `azure-apps/sigrid_tablas.md` (DA-2)."""
    ficha = _ficha(
        esquema="raw",
        objeto="obrparpre",
        capa="origen",
        consumo_recomendado=False,
        motivo_no_consumo="Copia literal de Sigrid.",
        columnas=(),
        ejemplos_preguntas=(),
        paso_etl="ingest_raw",
    )

    informe = evaluar_cobertura(_dicc(fichas=[ficha]), _inventario("raw.obrparpre"), ())

    assert informe.ok
    assert informe.avisos_columnas
    assert informe.columnas_sin_significado == ()


def test_f006_r26_dominio_bajar_el_booleano_no_es_gratis() -> None:
    """El antídoto contra la trampa evidente es R3, que exige `motivo_no_consumo`.

    Aquí solo se comprueba que la puerta efectivamente deja de exigir columnas:
    quien lo haga tendrá que escribir el motivo y eso se ve en el diff.
    """
    con_consumo = evaluar_cobertura(
        _dicc(fichas=[_ficha(columnas=())]),
        _inventario("mart.fact_seguimiento_mensual"),
        (),
    )
    sin_consumo = evaluar_cobertura(
        _dicc(
            fichas=[
                _ficha(
                    columnas=(),
                    consumo_recomendado=False,
                    motivo_no_consumo="Motivo escrito y visible en el diff.",
                    ejemplos_preguntas=(),
                )
            ]
        ),
        _inventario("mart.fact_seguimiento_mensual"),
        (),
    )

    assert not con_consumo.ok
    assert sin_consumo.ok


def test_f006_r25_dominio_el_informe_es_determinista() -> None:
    inventario = _inventario("mart.v_pbi_fact", "cierre.v_pbi_cierre_resumen")

    uno = evaluar_cobertura(_dicc(), inventario, ())
    dos = evaluar_cobertura(_dicc(), list(reversed(inventario)), ())

    assert formatear_cobertura(uno) == formatear_cobertura(dos)


def test_f006_r25_dominio_el_informe_dice_que_abrir() -> None:
    informe = evaluar_cobertura(_dicc(), _inventario("mart.v_pbi_fact"), ())

    texto = formatear_cobertura(informe)

    assert "mart.v_pbi_fact" in texto
    assert "x.sql" in texto
    assert "pendientes" in texto


def test_f006_r25_dominio_un_informe_limpio_lo_dice() -> None:
    informe = evaluar_cobertura(_dicc(), _inventario("mart.fact_seguimiento_mensual"), ())

    assert "OK" in formatear_cobertura(informe)


def test_f006_r25_dominio_el_informe_es_inmutable() -> None:
    from dataclasses import FrozenInstanceError

    informe = evaluar_cobertura(_dicc(), _inventario("mart.fact_seguimiento_mensual"), ())

    assert isinstance(informe, InformeCobertura)
    with pytest.raises(FrozenInstanceError):
        informe.sin_ficha = ()  # type: ignore[misc]


# ===========================================================================
# puerta · la puerta REAL sobre este repositorio (R24-R27)
#
# Esto es lo que corre en cada `bash harness/init.sh`. No prueba que el
# diccionario esté completo: prueba que **nadie ha añadido un objeto al
# repositorio sin documentarlo ni declararlo pendiente**.
# ===========================================================================

from pathlib import Path  # noqa: E402 - la puerta sí toca ficheros

import yaml  # noqa: E402

from etl_sigrid.infrastructure.diccionario.cargador_yaml import (  # noqa: E402
    cargar_diccionario,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
YAML_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"

#: EL TRINQUETE (R27). Es el número de objetos que el diccionario todavía se
#: permite no haber escrito. **Solo baja.** Cada bloque de fichas lo reduce y
#: ninguna tarea lo sube; al cerrar F-006 vale 0 y `pendientes` está vacía.
#:
#: Historia, para que se vea que baja de verdad:
#:   98  T8  · andamiaje, con el inventario entero declarado pendiente
#:   96  T12 · las dos tablas de hecho de `mart`
#:   85  T13 · las once vistas de `mart`
#:   73  T14 · los doce objetos de `cierre`
PENDIENTES_MAX = 73


def _inventario_del_repositorio():
    """Los objetos que este repositorio publica, leídos de sus propios ficheros."""
    textos = {
        str(ruta.relative_to(DIR_SQL)).replace("\\", "/"): ruta.read_text(
            encoding="utf-8"
        )
        for ruta in DIR_SQL.rglob("*.sql")
    }
    tablas = yaml.safe_load(YAML_TABLAS.read_text(encoding="utf-8"))["tables"]
    return objetos_de_sql(textos) + objetos_de_raw(tablas)


def test_f006_r24_puerta_el_inventario_no_esta_vacio() -> None:
    """Un inventario vacío haría pasar la puerta sin comprobar nada.

    Es el modo de fallo silencioso de este tipo de puertas: si mañana cambia la
    ruta del SQL, el `rglob` no encuentra nada y todo queda verde.
    """
    inventario = _inventario_del_repositorio()

    assert len(inventario) >= 90, f"solo se inventariaron {len(inventario)} objetos"
    esquemas = {o.esquema for o in inventario}
    assert {"mart", "cierre", "compras", "retenciones", "maestro", "stg", "raw",
            "aux", "_meta"} <= esquemas


def test_f006_r1_puerta_el_diccionario_real_se_carga() -> None:
    """`config/diccionario/` parsea y produce entidades."""
    dicc, hash_fuente = cargar_diccionario(DIR_DICCIONARIO)

    assert dicc.base == "sigrid_dm"
    assert len(hash_fuente) == 64


def test_f006_r25_puerta_todo_objeto_publicado_tiene_ficha_o_esta_pendiente() -> None:
    """LA PUERTA. Un objeto publicado sin ficha es el caso peligroso: el agente
    lo ve en el catálogo del servidor MCP e **inventa** su significado."""
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)

    informe = evaluar_cobertura(dicc, _inventario_del_repositorio(), dicc.pendientes)

    assert informe.ok, "\n" + formatear_cobertura(informe)


def test_f006_r27_puerta_el_trinquete_solo_baja() -> None:
    """`pendientes` no puede crecer. Al cerrar F-006 tiene que estar vacía."""
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)

    assert len(dicc.pendientes) <= PENDIENTES_MAX, (
        f"el diccionario declara {len(dicc.pendientes)} pendientes y el trinquete "
        f"está en {PENDIENTES_MAX}. El trinquete SOLO BAJA: documenta el objeto en "
        f"vez de subirlo"
    )


def test_f006_r27_puerta_el_trinquete_no_esta_holgado() -> None:
    """Un trinquete muy por encima de la realidad deja hueco para colar objetos.

    Se exige que la constante sea exactamente lo que hay declarado: bajarla es
    parte de la tarea que documenta, no un apaño posterior.
    """
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)

    assert len(dicc.pendientes) == PENDIENTES_MAX, (
        f"PENDIENTES_MAX vale {PENDIENTES_MAX} y hay {len(dicc.pendientes)} "
        f"pendientes declarados: ajusta la constante en esta misma tarea"
    )


# ---------------------------------------------------------------------------
# El informe que se lee cuando la puerta se pone en rojo
#
# Es la única salida que va a ver quien rompa la puerta a las 8 de la mañana.
# Si no nombra el objeto, el fichero y qué hacer con él, la puerta cuesta más
# de lo que vale.
# ---------------------------------------------------------------------------


def _informe_con_todo() -> InformeCobertura:
    """Un informe con las cinco clases de hueco a la vez."""
    ficha_muda = _ficha(columnas=(_columna("mes", significado="  "),))
    fuera_de_consumo = _ficha(
        esquema="raw",
        objeto="obrparpre",
        capa="origen",
        consumo_recomendado=False,
        motivo_no_consumo="Copia literal de Sigrid.",
        columnas=(),
        ejemplos_preguntas=(),
        paso_etl="ingest_raw",
    )

    return evaluar_cobertura(
        _dicc(fichas=[ficha_muda, fuera_de_consumo]),
        _inventario("mart.fact_seguimiento_mensual", "cierre.v_pbi_cierre_resumen"),
        ("mart.fact_seguimiento_mensual", "mart.objeto_borrado"),
    )


def test_f006_r25_dominio_el_informe_nombra_las_cinco_clases_de_hueco() -> None:
    informe = _informe_con_todo()

    texto = formatear_cobertura(informe)

    assert "KO" in texto
    # publicado y sin ficha
    assert "cierre.v_pbi_cierre_resumen" in texto
    # con ficha y sin objeto publicado
    assert "raw.obrparpre" in texto
    # columna sin describir dentro de la superficie de consumo
    assert "mart.fact_seguimiento_mensual.mes" in texto
    # pendiente ya documentado y pendiente fantasma
    assert "mart.objeto_borrado" in texto
    assert "trinquete" in texto
    # aviso, que no bloquea
    assert "No bloquea" in texto


def test_f006_r25_dominio_el_informe_dice_que_hacer_con_lo_que_falta() -> None:
    """No basta con listar: hay que decir dónde se escribe la ficha."""
    informe = _informe_con_todo()

    texto = formatear_cobertura(informe)

    assert "config/diccionario/" in texto
    assert "pendientes" in texto


def test_f006_r27_dominio_un_informe_solo_con_pendientes_no_es_un_fallo() -> None:
    """Entregar por bloques tiene que poder verse verde, pero con la cuenta a la vista."""
    informe = evaluar_cobertura(
        _dicc(), _inventario("mart.fact_seguimiento_mensual", "mart.v_pbi_fact"),
        ("mart.v_pbi_fact",),
    )

    texto = formatear_cobertura(informe)

    assert informe.ok
    assert "OK con pendientes declarados" in texto
    assert "pendientes declarados: 1" in texto


# ---------------------------------------------------------------------------
# Defensa (d) de la puerta · el trinquete tiene que ser un trinquete
#
# `PENDIENTES_MAX` es una constante escrita a mano al lado de la lista que
# vigila: subir las dos a la vez pasaba en verde. Demostrado en la review
# desdocumentando `mart.v_pbi_dim_escenario`, devolviendolo a `pendientes` y
# subiendo el tope a 74. La regla de hierro 4 de `tasks.md` dice que eso no
# puede pasar, y hasta ahora era un comentario, no un test.
#
# Se ancla a dos cosas que NO estan en la linea que se edita:
#
#   * el **inventario**: `pendientes` tiene que ser exactamente lo que falta
#     por documentar, ni un objeto mas;
#   * el **historial de git** del propio fichero: la lista solo puede encoger.
#     Un objeto que ya tuvo ficha no puede volver a `pendientes`.
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402
from itertools import pairwise  # noqa: E402


def test_f006_r27_pendientes_es_exactamente_lo_que_falta_por_documentar() -> None:
    """Ni un objeto de más: `pendientes` no es una lista libre.

    Con esto, inflar el trinquete exige borrar una ficha, y borrar una ficha se
    ve en el diff y lo caza el trinquete de git de abajo.
    """
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    inventario = _inventario_del_repositorio()

    esperados = {o.nombre for o in inventario} - set(dicc.por_nombre)

    assert set(dicc.pendientes) == esperados
    assert len(dicc.pendientes) == len(inventario) - len(dicc.fichas)


def _pendientes_en(revision: str) -> set[str] | None:
    """La lista de `pendientes` tal y como estaba en esa revisión de git."""
    import yaml as yaml_lib

    hecho = subprocess.run(
        ["git", "show", f"{revision}:config/diccionario/00_global.yaml"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if hecho.returncode != 0:
        return None
    return set(yaml_lib.safe_load(hecho.stdout).get("pendientes") or [])


def test_f006_r27_el_trinquete_solo_baja_a_lo_largo_del_historial() -> None:
    """LA COMPROBACIÓN QUE FALTABA: ningún objeto vuelve a `pendientes`.

    Se recorre el historial del propio fichero y se exige que cada revisión sea
    un subconjunto de la anterior. No hay forma de saltárselo editando una
    constante, porque la referencia es lo que ya está escrito en git.
    """
    revisiones = subprocess.run(
        ["git", "log", "--format=%H", "-40", "--", "config/diccionario/00_global.yaml"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if revisiones.returncode != 0:
        pytest.skip("sin git no hay historial contra el que comparar")

    historial = revisiones.stdout.split()
    assert historial, "el fichero del diccionario no tiene historial en git"

    # De la más nueva a la más vieja: cada una tiene que caber en la siguiente.
    # EL ÁRBOL DE TRABAJO VA EL PRIMERO: sin él, el test compara commits ya
    # hechos entre sí y deja pasar exactamente lo que viene a impedir. Se
    # comprobó: sin esta línea, el experimento de la review pasaba en verde.
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    listas = [("árbol de trabajo", set(dicc.pendientes))]
    listas += [(rev, _pendientes_en(rev)) for rev in historial]
    listas = [(rev, lista) for rev, lista in listas if lista is not None]

    for (rev_nueva, nueva), (rev_vieja, vieja) in pairwise(listas):
        vueltos = sorted(nueva - vieja)
        assert not vueltos, (
            f"{vueltos} volvieron a `pendientes` en {rev_nueva[:8]} "
            f"(no estaban en {rev_vieja[:8]}): el trinquete solo baja"
        )


def test_f006_r27_el_trinquete_de_hoy_cabe_en_el_de_la_primera_revision() -> None:
    """Control del test de arriba: si el historial no se leyera, pasaría solo."""
    primera = subprocess.run(
        ["git", "log", "--format=%H", "--reverse", "--",
         "config/diccionario/00_global.yaml"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if primera.returncode != 0 or not primera.stdout.split():
        pytest.skip("sin git no hay historial contra el que comparar")

    inicial = _pendientes_en(primera.stdout.split()[0])
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)

    assert inicial, "no se pudo leer la primera revisión del diccionario"
    assert set(dicc.pendientes) < inicial, (
        "la lista de hoy tiene que ser un subconjunto ESTRICTO de la inicial"
    )
