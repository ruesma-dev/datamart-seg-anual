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
sin documentarla. La verdad la dice `python main.py check-diccionario` contra el
catálogo real de la base (R28), que es otra tarea.
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
    assert "check-diccionario" in doc
    assert "tables_sigrid.yaml" in doc


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
