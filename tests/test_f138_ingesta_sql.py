# tests/test_f138_ingesta_sql.py
"""
F-138 · La ingesta de `conala` y `auxala`, el SQL de las alarmas y la marca
«liquidatoria», y su sub-paso, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f090_ingesta_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ninguna alarma de empleados entra en `raw`** (R3) y las de recursos y
   partes NO llegan a la general (R11, R14, D9).
2. **Los literales del SQL y del YAML son los del dominio** (R13): familias,
   traducción, patrones y precedencia.
3. **Lo existente no se toca** (R21): `01_` y `07_` no nombran las alarmas.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import liquidatoria as liq
from etl_sigrid.infrastructure.sigrid.bench_extraccion import construir_sql_de_pagina

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
RUTA_SQL = DIR_SQL / "15_alarmas_liquidatoria.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    corte = trozo.find("- source_table:")
    return trozo[:corte] if corte >= 0 else trozo


def _familias_de(filtro: str) -> list[int]:
    casa = re.search(r"tip IN \(([^)]*)\)", filtro)
    assert casa, f"el filtro no lleva `tip IN (...)`: {filtro!r}"
    return [int(x) for x in casa.group(1).split(",")]


# ===========================================================================
# R1-R3 · la ingesta
# ===========================================================================


def test_f138_r1_conala_filtrada_en_origen_sin_tiemod() -> None:
    conala = _tablas()["conala"]
    assert conala["target_table"] == "conala"
    assert conala["id_column"] == "ide"
    assert conala["incremental_column"] is None, "`conala` no tiene tiemod (R1)"
    assert conala["where"] == liq.filtro_conala(), "el filtro de `conala` no es el del dominio (R1)"
    assert conala["exclude_columns"] == [], "`conala` entra sin columnas excluidas (R1)"


def test_f138_r1_auxala_entera_con_tiemod() -> None:
    auxala = _tablas()["auxala"]
    assert auxala["target_table"] == "auxala"
    assert auxala["id_column"] == "ide"
    assert auxala["incremental_column"] == "tiemod"
    assert auxala["where"] is None
    assert auxala["exclude_columns"] == []


def test_f138_r1_el_comentario_de_conala_da_cifras_y_motivos() -> None:
    comentario = _comentario_de("conala").lower()
    for dato in ("f-138", "45.747", "1,79 mb", "~2 s", "d3", "43", "fallar cerrada",
                 "d9", "compras_restringida", "`fec1`", "`fec2`", "`creusu`", "login",
                 "filtro_conala()"):
        assert dato in comentario, f"el comentario de `conala` no dice «{dato}» (R1)"


def test_f138_r1_el_filtro_sale_como_lectura_hacia_sigrid() -> None:
    sql = construir_sql_de_pagina("conala", ["ide", "conide", "tex"], 10_000,
                                  where=_tablas()["conala"]["where"])
    assert sql.startswith("SELECT TOP 10000")


def test_f138_r3_la_familia_43_no_esta_en_el_filtro_de_ingesta() -> None:
    familias = _familias_de(_tablas()["conala"]["where"])
    assert liq.FAMILIA_EMPLEADOS not in familias, "las alarmas de empleados entrarían en raw (R3)"
    assert familias == sorted(liq.FAMILIAS_ALARMAS), "el filtro no es la lista explícita (R4)"
    assert "<>" not in _tablas()["conala"]["where"], "lista explícita, no exclusión (D3)"


def test_f138_r3_la_43_tampoco_en_el_sql() -> None:
    sql = _texto(RUTA_SQL)
    assert not re.search(r"\bWHEN 43\b", sql)
    for lista in re.findall(r"tip IN \(([^)]*)\)", sql):
        assert "43" not in [x.strip() for x in lista.split(",")], lista


# ===========================================================================
# R2 · el censo
# ===========================================================================


def test_f138_r2_el_censo_pasa_a_76() -> None:
    assert len(_tablas()) == 78  # +2 de F-140 (`auxcob`, `auxefc`)
    assert len(_lista_tablas()) == 78, "tabla declarada dos veces"
    assert {"conala", "auxala"} <= set(_tablas())


# ===========================================================================
# R11-R14 · las alarmas en dos esquemas (T5)
# ===========================================================================

COLUMNAS_GENERAL = [
    "alarma_id", "documento_id", "tipo_documento_codigo", "familia", "tipo_documento",
    "codigo_documento", "tipo_alarma_codigo", "tipo_alarma", "texto", "ver_al_abrir",
    "creada_el", "creada_por", "clase_liquidacion",
]
COLUMNAS_COMPLETA = [*COLUMNAS_GENERAL, "restringido", "motivo_restriccion"]


def _sql() -> str:
    return _texto(RUTA_SQL)


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def _bloque(objeto: str) -> str:
    """Desde el `CREATE TABLE <objeto> AS` hasta el `;` que cierra la sentencia."""
    sql = _sql()
    inicio = sql.index(f"CREATE TABLE {objeto} AS")
    return sql[inicio: sql.index(";\n", inicio)]


def _alias_finales(bloque: str) -> list[str]:
    """Las columnas del SELECT exterior: el último `AS x` (o el nombre) de cada línea."""
    exterior = bloque.rsplit("\nSELECT", 1)[1].split("\nFROM", 1)[0]
    columnas = []
    for linea in exterior.splitlines():
        linea = linea.split("--")[0].strip().rstrip(",")
        if not linea:
            continue
        casa = re.search(r"\bAS (\w+)$", linea) or re.fullmatch(r"(?:\w+\.)?(\w+)", linea)
        assert casa, f"línea del SELECT que no sé leer: {linea!r}"
        columnas.append(casa.group(1))
    return columnas


def test_f138_r11_las_dos_tablas_se_reconstruyen_cada_noche() -> None:
    sql = _sql()
    for objeto in ("compras_restringida.documento_alarmas", "compras.documento_alarmas"):
        assert f"DROP TABLE IF EXISTS {objeto} CASCADE;" in sql
        assert sql.index(f"DROP TABLE IF EXISTS {objeto} CASCADE;") < sql.index(
            f"CREATE TABLE {objeto} AS")
        assert f"ALTER TABLE {objeto} ADD PRIMARY KEY (alarma_id);" in sql
    assert sql.index("CREATE TABLE compras_restringida.documento_alarmas AS") < sql.index(
        "CREATE TABLE compras.documento_alarmas AS"), "la general sale de la completa"


def test_f138_r11_la_completa_sale_de_conala_con_su_documento() -> None:
    bloque = _bloque("compras_restringida.documento_alarmas")
    assert "FROM      raw.conala a" in bloque
    assert "JOIN      raw.con c ON c.ide = a.conide" in bloque
    assert "LEFT JOIN raw.auxala x ON x.ide = NULLIF(a.alaide, 0)" in bloque


def test_f138_r11_la_general_es_la_completa_sin_las_restringidas() -> None:
    bloque = _bloque("compras.documento_alarmas")
    assert "FROM compras_restringida.documento_alarmas" in bloque
    assert "WHERE NOT restringido" in bloque


def test_f138_r12_columnas_de_las_dos() -> None:
    assert _alias_finales(_bloque("compras_restringida.documento_alarmas")) == COLUMNAS_COMPLETA
    assert _alias_finales(_bloque("compras.documento_alarmas")) == COLUMNAS_GENERAL


def test_f138_r12_expresiones_de_la_completa() -> None:
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    for expresion in (
        "CASE WHEN c.tip IN (14, 15, 44) THEN compras.fn_tipo_documento(c.tip, "
        "compras.fn_serie(c.cod)) END",
        "x.cod AS tipo_alarma_codigo",
        "NULLIF(btrim(x.res), '') AS tipo_alarma",
        "NULLIF(a.tex, '') AS texto",
        "COALESCE(a.tipabr, 0) = 1 AS ver_al_abrir",
        "NULLIF(btrim(a.creusu), '') AS creada_por",
        "compras.fn_clase_liquidacion(a.tex) AS clase_liquidacion",
    ):
        assert expresion in bloque, f"falta «{expresion}» (R12)"
    for prohibida in ("fec1", "fec2", "a.usu", "a.rol"):
        assert prohibida not in bloque, f"`{prohibida}` no se publica (R24)"


def test_f138_r10_creada_el_en_sql_es_el_oraculo() -> None:
    """Fecha 0 o imposible (la de `fn_sigrid_date`) u hora imposible: NULL."""
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    assert ("CASE WHEN a.crehor BETWEEN 1 AND 235959 AND a.crehor % 10000 / 100 < 60 "
            "AND a.crehor % 100 < 60 THEN compras.fn_sigrid_date(a.crefec) + make_interval("
            "hours => a.crehor / 10000, mins => a.crehor % 10000 / 100, secs => a.crehor % 100) "
            "END AS creada_el") in bloque


def test_f138_r13_la_traduccion_es_la_del_dominio() -> None:
    cuerpo = _sql().split("FUNCTION compras.fn_texto_normalizado")[1].split("$$;")[0]
    assert (f"translate(COALESCE(t, ''), '{liq.TRADUCCION_ORIGEN}', "
            f"'{liq.TRADUCCION_DESTINO}')") in cuerpo
    assert f"'{liq.PATRON_NO_ALFANUMERICO}', ' ', 'g'" in cuerpo
    # el orden de R5: translate -> regexp_replace -> upper -> btrim
    assert "btrim(upper(regexp_replace(translate(" in cuerpo
    assert "IMMUTABLE" in cuerpo


def _cuerpo_clase() -> str:
    return _sql().split("FUNCTION compras.fn_clase_liquidacion")[1].split("$$;")[0]


def _ramas_sql() -> list[tuple[str, str, str]]:
    """(operador, patrón, clase) de cada `WHEN` de `fn_clase_liquidacion`, en orden."""
    return re.findall(r"WHEN x\.n (!?~) '([^']*)' THEN (?:'(\w+)'|CASE)", _cuerpo_clase())


def test_f138_r13_los_patrones_en_el_orden_de_r6() -> None:
    assert _ramas_sql() == [
        ("!~", liq.PATRON_MENCION, ""),
        ("~", liq.PATRON_REMITE, "REMITE"),
        ("~", liq.PATRON_NEGADA, "NEGADA"),
        ("~", liq.PATRON_CARTA, "CARTA_LIQUIDACION"),
        ("~", liq.PATRON_DUDOSA, "DUDOSA"),
    ]
    assert "ELSE 'LIQUIDATORIA'" in _cuerpo_clase()
    assert "compras.fn_texto_normalizado(t) AS n" in _cuerpo_clase()
    assert "IMMUTABLE" in _cuerpo_clase()


def _clasificar_como_el_sql(texto: str | None) -> str | None:
    """Ejecuta en Python las ramas tal como están escritas en el SQL."""
    n = liq.normalizar(texto)
    ramas = _ramas_sql()
    if not re.search(ramas[0][1], n):
        return "REMITE" if re.search(ramas[1][1], n) else None
    for _, patron, clase in ramas[2:]:
        if re.search(patron, n):
            return clase
    return "LIQUIDATORIA"


def test_f138_r13_el_sql_clasifica_como_el_oraculo() -> None:
    from tests.test_f138_dominio import test_f138_r6_la_regla_en_los_bordes as bordes
    from tests.test_f138_dominio import test_f138_r8_casos_de_la_spec as spec

    casos = [m.args[1] for t in (spec, bordes) for m in t.pytestmark if m.name == "parametrize"]
    textos = [texto for lista in casos for texto, _ in lista]
    assert len(textos) > 30
    for texto in textos:
        assert _clasificar_como_el_sql(texto) == liq.clasificar(texto), texto


def test_f138_r13_las_familias_son_las_del_dominio() -> None:
    bloque = _bloque("compras_restringida.documento_alarmas")
    caso = bloque.split("CASE c.tip", 1)[1].split("END", 1)[0]
    parejas = {int(t): n for t, n in re.findall(r"WHEN (\d+) THEN '(\w+)'", caso)}
    assert parejas == liq.FAMILIAS_ALARMAS
    tips = ", ".join(str(t) for t in sorted(liq.FAMILIAS_ALARMAS))
    assert f"WHERE c.tip IN ({tips})" in _plano(bloque), "la completa falla cerrada, como la ingesta"


def test_f138_r13_las_restringidas_son_las_del_dominio() -> None:
    restringidas = ", ".join(str(t) for t in sorted(liq.FAMILIAS_RESTRINGIDAS))
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    assert f"c.tip IN ({restringidas}) AS restringido" in bloque
    assert "CASE WHEN b.restringido THEN b.familia END AS motivo_restriccion" in bloque
    guarda = _sql().split("R14 · la guarda de la restricción")[1]
    assert f"c.tip IN ({restringidas})" in guarda


def test_f138_r14_guarda_de_ingesta_antes_de_construir() -> None:
    sql = _sql()
    guarda = sql[: sql.index("CREATE TABLE")]
    assert "raw.conala" in guarda and "c.tip = 15" in guarda
    assert "RAISE EXCEPTION 'F-138" in guarda


def test_f138_r14_guarda_de_la_restriccion_tras_la_general() -> None:
    sql = _sql()
    inicio = sql.index("R14 · la guarda de la restricción")
    assert inicio > sql.index("CREATE TABLE compras.documento_alarmas AS")
    guarda = sql[inicio: sql.index("END $$;", inicio)]
    assert "JOIN raw.con c ON c.ide = g.documento_id" in guarda, "recalcula desde raw.con"
    assert "v_general + v_restringidas <> v_completa" in guarda
    assert "RAISE EXCEPTION 'F-138" in guarda


def test_f138_r20_un_solo_fichero_sin_control_de_transaccion() -> None:
    sql = _sql()
    assert not re.search(r"^\s*(COMMIT|BEGIN|ROLLBACK)\s*;", sql, re.MULTILINE | re.IGNORECASE)
    assert sql.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql")


def test_f138_r11_00_setup_crea_el_esquema_restringido() -> None:
    assert "CREATE SCHEMA IF NOT EXISTS compras_restringida;" in _texto(DIR_SQL / "00_setup.sql")


# ===========================================================================
# R15-R16 · compras.documento_liquidatoria (T6)
# ===========================================================================

COLUMNAS_LIQUIDATORIA = [
    "documento_id", "tipo_documento_codigo", "tipo_documento", "codigo_documento",
    "fecha_alta", "marca_liquidacion", "es_liquidatoria", "pendiente_carta_liquidacion",
    "cierra_contrato", "texto_alarmas", "liquidacion_creada_el", "clase_memo",
]


def test_f138_r15_se_reconstruye_con_su_clave() -> None:
    sql = _sql()
    objeto = "compras.documento_liquidatoria"
    assert sql.index(f"DROP TABLE IF EXISTS {objeto} CASCADE;") < sql.index(
        f"CREATE TABLE {objeto} AS")
    assert f"ALTER TABLE {objeto} ADD PRIMARY KEY (documento_id);" in sql
    assert sql.index("R14 · la guarda de la restricción") < sql.index(f"CREATE TABLE {objeto} AS"), (
        "la marca se construye DESPUÉS de comprobar la restricción"
    )


def test_f138_r15_lee_la_general_y_solo_las_familias_de_la_marca() -> None:
    bloque = _plano(_bloque("compras.documento_liquidatoria"))
    familias = ", ".join(str(t) for t in liq.FAMILIAS_MARCA)
    assert "FROM compras.documento_alarmas" in bloque
    assert "compras_restringida" not in bloque, "14 y 15 no son restringidas: lee la general"
    assert f"WHERE tipo_documento_codigo IN ({familias})" in bloque
    assert f"WHERE c.tip IN ({familias}) AND c.tex ILIKE '%liq%'" in bloque, "prefiltro del memo"
    assert "compras.fn_clase_liquidacion(c.tex) AS clase_memo" in bloque


def test_f138_r15_universo_alarmas_o_memo_con_clase() -> None:
    bloque = _plano(_bloque("compras.documento_liquidatoria"))
    assert "SELECT documento_id FROM al WHERE marca IS NOT NULL UNION " \
           "SELECT documento_id FROM memo WHERE clase_memo IS NOT NULL" in bloque


def test_f138_r9_la_marca_en_sql_sigue_la_precedencia() -> None:
    bloque = _bloque("compras.documento_liquidatoria")
    orden = re.findall(r"WHEN bool_or\(clase_liquidacion = '(\w+)'\) THEN '(\w+)'", bloque)
    assert orden == [(c, c) for c in liq.PRECEDENCIA]


def test_f138_r16_columnas() -> None:
    assert _alias_finales(_bloque("compras.documento_liquidatoria")) == COLUMNAS_LIQUIDATORIA


def test_f138_r16_los_tres_booleanos_nunca_null_y_sin_el_memo() -> None:
    bloque = _plano(_bloque("compras.documento_liquidatoria"))
    cierre = ", ".join(f"'{c}'" for c in sorted(liq.CLASES_CIERRE))
    for expresion in (
        "COALESCE(al.marca = 'LIQUIDATORIA', FALSE) AS es_liquidatoria",
        "COALESCE(al.marca = 'CARTA_LIQUIDACION', FALSE) AS pendiente_carta_liquidacion",
        f"COALESCE(al.marca IN ({cierre}), FALSE) AS cierra_contrato",
    ):
        assert expresion in bloque, f"falta «{expresion}» (R16)"
    final = _bloque("compras.documento_liquidatoria").rsplit("\nSELECT", 1)[1]
    assert final.count("clase_memo") == 2, "el memo no entra en los booleanos (D5)"
    assert "m.clase_memo AS clase_memo" in final


def test_f138_r16_texto_y_fecha_de_las_alarmas() -> None:
    bloque = _plano(_bloque("compras.documento_liquidatoria"))
    cierre = ", ".join(f"'{c}'" for c in sorted(liq.CLASES_CIERRE))
    assert ("string_agg(texto, ' | ' ORDER BY alarma_id) FILTER "
            "(WHERE clase_liquidacion IS NOT NULL) AS texto_alarmas") in bloque
    assert (f"min(creada_el) FILTER (WHERE clase_liquidacion IN ({cierre})) "
            "AS liquidacion_creada_el") in bloque
    assert ("CASE WHEN al.marca IN (" + cierre + ") THEN al.liquidacion_creada_el END "
            "AS liquidacion_creada_el") in bloque, "solo si el documento cierra"
    assert "compras.fn_sigrid_date(c.fec) AS fecha_alta" in bloque
    assert "compras.fn_tipo_documento(c.tip, compras.fn_serie(c.cod)) AS tipo_documento" in bloque


# ===========================================================================
# R17-R19 · los contratos: contrato_liquidacion y facturas_tras_liquidacion (T7)
# ===========================================================================

COLUMNAS_CONTRATO = [
    "contrato_id", "codigo_contrato", "obra_id", "codigo_obra", "facturas_terminadas",
    "tipo_cierre", "factura_cierre_id", "codigo_factura_cierre", "fecha_cierre",
    "num_facturas_liquidatorias", "num_facturas_carta_liquidacion",
    "num_albaranes_liquidatorios", "num_facturas_posteriores", "ultima_factura_cierra",
]
COLUMNAS_TRAS = [
    "contrato_id", "codigo_contrato", "obra_id", "codigo_obra", "factura_id",
    "codigo_factura", "fecha", "fecha_factura", "proveedor_id", "proveedor_nombre",
    "factura_cierre_id", "codigo_factura_cierre", "fecha_cierre", "dias_tras_cierre",
    "cierra_contrato",
]


def _cadena_de_la_vista() -> tuple[str, str]:
    """La cadena factura -> contrato de `fact_por_ctr` en `v_pbi_contrato_consumo`."""
    vista = _texto(DIR_SQL / "03_views.sql").split("fact_por_ctr AS (", 1)[1].split("GROUP BY", 1)[0]
    coalesce = re.search(r"COALESCE\(fl\.contrato_id_directo,.*?\)", vista, re.DOTALL)
    assert coalesce
    joins = vista[vista.index("FROM compras.factura_lineas fl"): vista.index("WHERE")]
    return _plano(coalesce.group(0)), _plano(joins).strip()


def test_f138_r17_las_dos_se_reconstruyen_en_orden() -> None:
    sql = _sql()
    previa = sql.index("CREATE TABLE compras.documento_liquidatoria AS")
    contrato = sql.index("CREATE TABLE compras.contrato_liquidacion AS")
    tras = sql.index("CREATE TABLE compras.facturas_tras_liquidacion AS")
    assert previa < contrato < tras
    for objeto in ("compras.contrato_liquidacion", "compras.facturas_tras_liquidacion"):
        assert sql.index(f"DROP TABLE IF EXISTS {objeto} CASCADE;") < sql.index(
            f"CREATE TABLE {objeto} AS")
    assert "ALTER TABLE compras.contrato_liquidacion ADD PRIMARY KEY (contrato_id);" in sql
    assert ("ALTER TABLE compras.facturas_tras_liquidacion ADD PRIMARY KEY "
            "(contrato_id, factura_id);") in sql


def test_f138_r17_la_cadena_es_la_de_v_pbi_contrato_consumo() -> None:
    coalesce, joins = _cadena_de_la_vista()
    for objeto in ("compras.contrato_liquidacion", "compras.facturas_tras_liquidacion"):
        bloque = _plano(_bloque(objeto))
        assert f"SELECT DISTINCT fl.factura_id, {coalesce} AS contrato_id" in bloque, objeto
        assert joins in bloque, f"{objeto} no copia los JOIN de fact_por_ctr"
        assert f"WHERE {coalesce} IS NOT NULL" in bloque, objeto


def test_f138_r17_todos_los_contratos_y_la_factura_de_cierre() -> None:
    bloque = _plano(_bloque("compras.contrato_liquidacion"))
    assert "FROM compras.contratos k LEFT JOIN cierre ci ON ci.contrato_id = k.contrato_id" in bloque
    assert ("SELECT DISTINCT ON (contrato_id) contrato_id, factura_id, codigo_factura, fecha, "
            "es_liquidatoria FROM fac WHERE cierra ORDER BY contrato_id, fecha, factura_id") in bloque
    assert ("SELECT DISTINCT ON (contrato_id) contrato_id, cierra FROM fac "
            "ORDER BY contrato_id, fecha DESC NULLS LAST, factura_id DESC") in bloque
    assert "LEFT JOIN compras.documento_liquidatoria dl ON dl.documento_id = fc.factura_id" in bloque
    assert "COALESCE(dl.cierra_contrato, FALSE) AS cierra" in bloque


def test_f138_r18_columnas_y_nunca_null() -> None:
    assert _alias_finales(_bloque("compras.contrato_liquidacion")) == COLUMNAS_CONTRATO
    bloque = _plano(_bloque("compras.contrato_liquidacion"))
    assert "ci.factura_id IS NOT NULL AS facturas_terminadas" in bloque
    for cuenta in ("num_facturas_liquidatorias", "num_facturas_carta_liquidacion",
                   "num_albaranes_liquidatorios", "num_facturas_posteriores"):
        assert re.search(rf"COALESCE\(\w+\.{cuenta}, 0\) AS {cuenta}", bloque), cuenta


def test_f138_r18_albaranes_y_proformas_y_posteriores() -> None:
    bloque = _plano(_bloque("compras.contrato_liquidacion"))
    assert "WHERE a.tipo_documento IN ('ALBARAN', 'PROFORMA')" in bloque
    assert "dl.documento_id = x.albaran_id AND dl.es_liquidatoria" in bloque
    assert "WHERE f.fecha > ci.fecha" in bloque
    assert ("CASE WHEN ci.factura_id IS NOT NULL THEN CASE WHEN ci.es_liquidatoria "
            "THEN 'LIQUIDATORIA' ELSE 'CARTA_LIQUIDACION' END END AS tipo_cierre") in bloque


def test_f138_r19_facturas_tras_liquidacion() -> None:
    assert _alias_finales(_bloque("compras.facturas_tras_liquidacion")) == COLUMNAS_TRAS
    bloque = _plano(_bloque("compras.facturas_tras_liquidacion"))
    assert ("JOIN compras.contrato_liquidacion cl ON cl.contrato_id = fc.contrato_id "
            "AND cl.facturas_terminadas") in bloque
    assert "JOIN compras.facturas f ON f.factura_id = fc.factura_id AND f.fecha > cl.fecha_cierre" in bloque
    assert "f.fecha - cl.fecha_cierre AS dias_tras_cierre" in bloque
    assert "COALESCE(dl.cierra_contrato, FALSE) AS cierra_contrato" in bloque


# ===========================================================================
# R20-R21 · el sub-paso y la frontera (T8)
# ===========================================================================


def test_f138_r20_el_sub_paso_es_el_ultimo_y_cuenta_la_general() -> None:
    from etl_sigrid.application.steps.build_compras_step import SUB_PASOS

    ultimo = SUB_PASOS[-1]
    assert (ultimo.name, ultimo.sql_file, ultimo.target_schema, ultimo.target_table) == (
        "alarmas_liquidatoria", "15_alarmas_liquidatoria.sql", "compras", "documento_alarmas",
    )
    assert [s.sql_file for s in SUB_PASOS].count("15_alarmas_liquidatoria.sql") == 1
    assert (DIR_SQL / ultimo.sql_file).exists()


def test_f138_r20_el_paso_ejecuta_el_15_al_final(monkeypatch) -> None:
    """Con el cliente simulado: el 15 se ejecuta el último y se cuenta la general."""
    from types import SimpleNamespace

    from etl_sigrid.application.steps import build_compras_step as modulo
    from etl_sigrid.domain.entities import StepStatus

    ejecutados: list[str] = []
    contados: list[tuple[str, str]] = []

    class _Pg:
        def execute_sql_file(self, path):
            ejecutados.append(Path(path).name)

        def count_rows(self, schema, table):
            contados.append((schema, table))
            return 1

    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: _Pg())
    resultado = modulo.BuildComprasStep(SimpleNamespace()).run()
    assert resultado.status == StepStatus.SUCCESS
    assert ejecutados[-1] == "15_alarmas_liquidatoria.sql"
    assert contados[-1] == ("compras", "documento_alarmas")


def test_f138_r20_el_docstring_y_el_comentario_lo_cuentan() -> None:
    texto = _texto(RAIZ / "etl_sigrid" / "application" / "steps" / "build_compras_step.py")
    docstring = texto.split('"""', 2)[1]
    assert "15_alarmas_liquidatoria.sql" in docstring and "F-138" in docstring
    assert "compras_restringida" in docstring
    comentario = texto.split('name="documento_adjuntos"')[1]
    assert "F-138" in comentario


def test_f138_r21_lo_existente_no_nombra_las_alarmas() -> None:
    for fichero in ("01_documentos.sql", "07_texto.sql"):
        texto = _texto(DIR_SQL / fichero).lower()
        for tabla in ("conala", "auxala"):
            assert tabla not in texto, f"{fichero} nombra `{tabla}` (R21, D7)"


def test_f138_r21_solo_el_15_nombra_las_alarmas() -> None:
    for ruta in sorted(DIR_SQL.glob("*.sql")):
        if ruta.name == "15_alarmas_liquidatoria.sql":
            continue
        texto = _texto(ruta).lower()
        assert "raw.conala" not in texto and "raw.auxala" not in texto, ruta.name
        assert "documento_alarmas" not in texto, ruta.name
