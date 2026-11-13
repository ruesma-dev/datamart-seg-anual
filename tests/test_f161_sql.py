# tests/test_f161_sql.py
"""
F-161 · El catálogo completo de versiones master, comprobado sobre su TEXTO
(R1-R10, R12, R14, R15, R17).

Sin red ni BBDD: lo que se ejecuta lo prueba `tests/test_f161_sandbox.py`. Aquí
se fija la FORMA:

- `stg/01_ddl.sql`: la tabla `stg.master_versiones` (PK de negocio) y la vista
  `stg.v_master_lineas` (la marca por línea, D12).
- `stg/10_master_versiones.sql`: el universo (D5), la v0 solo con reparto (D6),
  la marca por `presupuesto_id` (D7), la cabecera sin duplicar (D13) y las
  expresiones copiadas de `08_plan_mensual.sql` (R4).
- `build_stg_step`: el sub-paso nuevo detrás de `fase0`, entero y fuera del
  sello (R6).
- `mart/01b_master_versiones.sql`: el ÚNICO catálogo (R7-R9), el coste por
  partida (R12) y el planificado de importe al lado del temporal (R14-R17).
- Los consumidores filtran `tiene_reparto` (R10, D4): la parte temporal no
  cambia.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from tests.test_f006_fichas import columnas_proyectadas, cuerpo_de_vista

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DDL_STG = DIR_SQL / "stg" / "01_ddl.sql"
VERSIONES_STG = DIR_SQL / "stg" / "10_master_versiones.sql"
PLAN_MENSUAL = DIR_SQL / "stg" / "08_plan_mensual.sql"
CATALOGO_MART = DIR_SQL / "mart" / "01b_master_versiones.sql"
BUILD_FACT = DIR_SQL / "mart" / "02_build_fact.sql"
CP_TIPOLOGIA = DIR_SQL / "mart" / "06_cp_tipologia.sql"
FIN_OBRA = DIR_SQL / "retenciones" / "05_fin_obra.sql"

#: Las ocho columnas del catálogo de hoy, en su orden (R8).
OCHO = [
    "obra_id", "ambito_id", "version", "version_fec_creacion",
    "version_fec_efectiva", "version_descripcion", "version_tex", "tipo_master",
]

#: Las nueve que F-161 añade detrás (R3, R5, R7).
NUEVAS = [
    "tiene_reparto", "reparto", "n_lineas", "n_lineas_con_reparto",
    "importe_total", "importe_con_reparto", "importe_sin_reparto",
    "tiene_cabecera", "tiene_ancla",
]

#: La cascada del tipo, rama a rama (la de `06` y `02` hasta F-161).
CASCADA = (
    "WHEN version_tex IS NULL OR length(trim(version_tex)) = 0 THEN 'Sin clasificar'",
    "WHEN UPPER(version_tex) LIKE '%ABC%' THEN 'ABC'",
    "WHEN UPPER(version_tex) LIKE '%INICIAL%' AND UPPER(version_tex) "
    "LIKE '%VALORADA%' THEN 'Planif Inicial'",
    "WHEN UPPER(version_tex) LIKE '%CUATRIM%' OR UPPER(version_tex) "
    "LIKE '%VALORADA%' THEN 'Cuatrimestral'",
    "WHEN UPPER(version_tex) LIKE '%CIERRE%' THEN 'Cierre mensual'",
    "ELSE 'Sin clasificar' END AS tipo_master",
)

#: El catálogo de HOY, la sección 1 de `06_cp_tipologia.sql` en `491fbf1`,
#: compactado. Es la fotografía contra la que se compara el catálogo nuevo (R11).
CATALOGO_491FBF1 = (
    "SELECT DISTINCT obra_id, ambito_id, version, version_fec_creacion, "
    "version_fec_efectiva, version_descripcion, version_tex, CASE WHEN version_tex "
    "IS NULL OR length(trim(version_tex)) = 0 THEN 'Sin clasificar' WHEN "
    "UPPER(version_tex) LIKE '%ABC%' THEN 'ABC' WHEN UPPER(version_tex) LIKE "
    "'%INICIAL%' AND UPPER(version_tex) LIKE '%VALORADA%' THEN 'Planif Inicial' WHEN "
    "UPPER(version_tex) LIKE '%CUATRIM%' OR UPPER(version_tex) LIKE '%VALORADA%' THEN "
    "'Cuatrimestral' WHEN UPPER(version_tex) LIKE '%CIERRE%' THEN 'Cierre mensual' "
    "ELSE 'Sin clasificar' END AS tipo_master FROM stg.plan_mensual WHERE ambito_id "
    "IN (8, 11) AND version_fec_efectiva IS NOT NULL"
)


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


@cache
def _leer(ruta: Path) -> str:
    assert ruta.exists(), f"no existe {ruta.relative_to(RAIZ)}"
    return ruta.read_text(encoding="utf-8")


def _ejecutable(ruta: Path) -> str:
    return _compacto(_leer(ruta))


def _cuerpo(ruta: Path, esquema: str, objeto: str) -> str:
    cuerpo = cuerpo_de_vista(_leer(ruta), esquema, objeto)
    assert cuerpo is not None, f"no se encontró el CREATE de {esquema}.{objeto}"
    return cuerpo


def _cte(texto: str, nombre: str) -> str:
    """El cuerpo compactado de la CTE `nombre AS (...)`, por paréntesis."""
    limpio = _sin_comentarios(texto)
    m = re.search(rf"\b{nombre}\s+AS\s*\(", limpio)
    assert m, f"no hay CTE {nombre}"
    profundidad, i = 1, m.end()
    while profundidad:
        profundidad += {"(": 1, ")": -1}.get(limpio[i], 0)
        i += 1
    return re.sub(r"\s+", " ", limpio[m.end() : i - 1]).strip()


# ===========================================================================
# R1-R5 · stg.master_versiones y stg.v_master_lineas
# ===========================================================================


def _create_tabla_stg() -> str:
    m = re.search(
        r"CREATE TABLE IF NOT EXISTS stg\.master_versiones \((.*?)\n\);",
        _leer(DDL_STG),
        re.S,
    )
    assert m, "01_ddl.sql no crea stg.master_versiones"
    return _compacto(m.group(1))


def test_f161_r1_la_tabla_de_stg_tiene_su_clave_de_negocio() -> None:
    assert (
        "CONSTRAINT pk_master_versiones PRIMARY KEY (obra_id, ambito_id, version)"
        in _create_tabla_stg()
    )


def test_f161_r1_solo_ambitos_master() -> None:
    assert "CHECK (ambito_id IN (8, 11))" in _create_tabla_stg()


@pytest.mark.parametrize("columna", OCHO[:-1] + NUEVAS)
def test_f161_r3_r5_la_tabla_de_stg_declara_cada_columna(columna: str) -> None:
    assert re.search(rf"(^|, ){columna} ", _create_tabla_stg()), columna


def test_f161_r3_el_reparto_solo_admite_tres_valores() -> None:
    assert "CHECK (reparto IN ('NINGUNO', 'COMPLETO', 'PARCIAL'))" in _create_tabla_stg()


def test_f161_r1_la_tabla_va_despues_de_plan_mensual_fase0() -> None:
    texto = _leer(DDL_STG)
    assert texto.index("CREATE TABLE IF NOT EXISTS stg.plan_mensual_fase0") < texto.index(
        "CREATE TABLE IF NOT EXISTS stg.master_versiones"
    )


def test_f161_r6_se_reconstruye_entera() -> None:
    texto = _ejecutable(VERSIONES_STG)
    assert texto.startswith("TRUNCATE TABLE stg.master_versiones;")
    assert "INSERT INTO stg.master_versiones (" in texto
    assert "/*F0" not in _leer(VERSIONES_STG), "no se acota por obra: se ejecuta entera"


def test_f161_r1_lee_presupuesto_plan_mensual_y_la_cabecera() -> None:
    texto = _ejecutable(VERSIONES_STG)
    for origen in ("FROM stg.presupuesto pp", "FROM stg.plan_mensual", "FROM raw.obrfasamb fa"):
        assert origen in texto, origen
    assert "mart." not in texto, "stg no lee de mart"


def test_f161_r1_d5_el_universo_es_lineas_union_reparto() -> None:
    universo = _cte(_leer(VERSIONES_STG), "universo")
    assert "FROM agregado" in universo
    assert "UNION" in universo
    assert "FROM plan" in universo
    assert "cabecera" not in universo, "la cabecera es opcional (D5)"


def test_f161_r1_d6_la_version_0_solo_si_tiene_reparto() -> None:
    lineas = _cte(_leer(VERSIONES_STG), "lineas")
    assert "pp.ambito_id IN (8, 11)" in lineas
    assert (
        "pp.fase_num >= 1 OR EXISTS ( SELECT 1 FROM plan p WHERE p.obra_id = pp.obra_id "
        "AND p.ambito_id = pp.ambito_id AND p.version = pp.fase_num )"
    ) in lineas


def test_f161_r2_d7_la_linea_tiene_reparto_si_deja_filas() -> None:
    marca = (
        "EXISTS ( SELECT 1 FROM stg.plan_mensual pm "
        "WHERE pm.presupuesto_id = pp.presupuesto_id )"
    )
    assert marca in _cte(_leer(VERSIONES_STG), "lineas")
    assert marca in _compacto(_cuerpo(DDL_STG, "stg", "v_master_lineas"))


def test_f161_r1_la_version_con_reparto_sale_de_plan_mensual() -> None:
    plan = _cte(_leer(VERSIONES_STG), "plan")
    assert plan.startswith("SELECT DISTINCT ON (obra_id, ambito_id, version)")
    assert "FROM stg.plan_mensual WHERE ambito_id IN (8, 11)" in plan
    assert (
        "ORDER BY obra_id, ambito_id, version, version_fec_efectiva DESC NULLS LAST, "
        "version_fec_creacion DESC NULLS LAST"
    ) in plan


def test_f161_r1_d13_la_cabecera_no_se_duplica() -> None:
    dedup = _cte(_leer(VERSIONES_STG), "fa_dedup")
    assert dedup.startswith("SELECT DISTINCT ON (obride, amb, fas)")
    assert "WHERE amb IN (8, 11)" in dedup
    assert dedup.endswith("ORDER BY obride, amb, fas, ide DESC")


def test_f161_r4_las_expresiones_de_la_cabecera_son_las_de_08() -> None:
    """Fecha efectiva, descripción por defecto y texto de coste para la venta:
    las MISMAS expresiones que la rama master de `08_plan_mensual.sql`."""
    ocho = _ejecutable(PLAN_MENSUAL)
    diez = _cte(_leer(VERSIONES_STG), "cabecera")
    for expresion in (
        "stg.fn_sigrid_date_to_date(fa.fec) AS fec_creacion",
        "stg.fn_master_fecha_efectiva( COALESCE(NULLIF(TRIM(fa.tex), ''), "
        "NULLIF(TRIM(fa_coste.tex), '')), fa.res, stg.fn_sigrid_date_to_date(fa.fec) ) "
        "AS fec_efectiva",
        "COALESCE( NULLIF(TRIM(fa.res), ''), CASE fa.amb WHEN 8 THEN 'Master coste sin "
        "descripción' WHEN 11 THEN 'Master venta sin descripción' ELSE NULL END ) "
        "AS res_descripcion",
        "COALESCE( NULLIF(TRIM(fa.tex), ''), NULLIF(TRIM(fa_coste.tex), '') ) "
        "AS tex_descripcion",
    ):
        assert expresion in ocho, f"08 ya no dice: {expresion}"
        assert expresion in diez, f"10 no copia: {expresion}"
    assert (
        "LEFT JOIN fa_dedup fa_coste ON fa_coste.obride = fa.obride AND fa_coste.fas = fa.fas "
        "AND fa_coste.amb = 8 AND fa.amb = 11"
    ) in diez


def test_f161_r4_con_reparto_manda_plan_mensual_y_si_no_la_cabecera() -> None:
    texto = _ejecutable(VERSIONES_STG)
    for plan, cab in (
        ("version_fec_creacion", "fec_creacion"),
        ("version_fec_efectiva", "fec_efectiva"),
        ("version_descripcion", "res_descripcion"),
        ("version_tex", "tex_descripcion"),
    ):
        assert (
            f"CASE WHEN p.obra_id IS NOT NULL THEN p.{plan} ELSE c.{cab} END AS {plan}"
        ) in texto, plan


def test_f161_r3_el_reparto_de_la_version() -> None:
    texto = _ejecutable(VERSIONES_STG)
    assert (
        "CASE WHEN p.obra_id IS NULL THEN 'NINGUNO' "
        "WHEN COALESCE(a.hay_sin_reparto_con_importe, FALSE) THEN 'PARCIAL' "
        "ELSE 'COMPLETO' END AS reparto"
    ) in texto
    assert "(p.obra_id IS NOT NULL) AS tiene_reparto" in texto
    agregado = _cte(_leer(VERSIONES_STG), "agregado")
    assert "BOOL_OR(NOT con_reparto AND importe <> 0) AS hay_sin_reparto_con_importe" in agregado
    assert "COUNT(*) FILTER (WHERE con_reparto) AS n_lineas_con_reparto" in agregado
    assert "SUM(importe) FILTER (WHERE con_reparto)" in agregado


def test_f161_r3_importe_sin_reparto_es_la_resta() -> None:
    assert (
        "(COALESCE(a.importe_total, 0) - COALESCE(a.importe_con_reparto, 0))::NUMERIC(18,2) "
        "AS importe_sin_reparto"
    ) in _ejecutable(VERSIONES_STG)


def test_f161_r5_cabecera_y_ancla() -> None:
    texto = _ejecutable(VERSIONES_STG)
    assert "(c.obra_id IS NOT NULL) AS tiene_cabecera" in texto
    assert "COALESCE(c.tiene_ancla, FALSE) AS tiene_ancla" in texto
    assert "(fa.plafec IS NOT NULL AND fa.plafec > 0) AS tiene_ancla" in _cte(
        _leer(VERSIONES_STG), "cabecera"
    )


def test_f161_r2_la_vista_de_lineas() -> None:
    cuerpo = _cuerpo(DDL_STG, "stg", "v_master_lineas")
    assert columnas_proyectadas(cuerpo) == [
        "presupuesto_id", "obra_id", "partida_id", "ambito_id", "version",
        "cantidad", "precio", "importe", "tiene_reparto",
    ]
    compacto = _compacto(cuerpo)
    assert "FROM stg.presupuesto pp" in compacto
    assert "WHERE pp.ambito_id IN (8, 11) AND pp.fase_num >= 1" in compacto


def test_f161_r2_d12_la_marca_por_linea_es_vista_sin_disco() -> None:
    assert "CREATE OR REPLACE VIEW stg.v_master_lineas AS" in _leer(DDL_STG)
    assert "CREATE TABLE IF NOT EXISTS stg.master_lineas" not in _leer(DDL_STG)


# ===========================================================================
# R6 · el sub-paso de build_stg
# ===========================================================================


def _sub_pasos_stg() -> list:
    """Los sub-pasos de `BuildStgStep.run`, leídos del texto del step."""
    texto = (RAIZ / "etl_sigrid" / "application" / "steps" / "build_stg_step.py").read_text(
        encoding="utf-8"
    )
    return re.findall(r'_SubStep\(\s*"(\w+)",\s*"([\w.]*)"', texto)


def test_f161_r6_el_sub_paso_va_detras_de_fase0_y_es_el_ultimo() -> None:
    nombres = [n for n, _ in _sub_pasos_stg()]
    assert nombres[-2:] == ["build_plan_mensual_fase0", "build_master_versiones"]
    assert ("build_master_versiones", "10_master_versiones.sql") in _sub_pasos_stg()


def test_f161_r6_cuenta_su_tabla_y_se_ejecuta_entero() -> None:
    texto = (RAIZ / "etl_sigrid" / "application" / "steps" / "build_stg_step.py").read_text(
        encoding="utf-8"
    )
    bloque = re.search(r'_SubStep\(\s*"build_master_versiones".*?\)', texto, re.S)
    assert bloque, "no hay sub-paso build_master_versiones"
    assert '"stg"' in bloque.group(0) and '"master_versiones"' in bloque.group(0)
    for marca in ("acotado", "por_tramos", "es_plan_ventana"):
        assert marca not in bloque.group(0), f"{marca}: se ejecuta entero (R6)"


def test_f161_r6_fuera_del_sello_y_de_la_ventana() -> None:
    from etl_sigrid.application.steps.build_stg_step import FICHEROS_DEL_SELLO
    from etl_sigrid.infrastructure.postgres.postgres_client import TABLAS_ACOTADAS

    assert "10_master_versiones.sql" not in FICHEROS_DEL_SELLO
    assert "master_versiones" not in TABLAS_ACOTADAS
    assert FICHEROS_DEL_SELLO == (
        "00_functions.sql", "06_presupuesto.sql", "08_plan_mensual.sql",
        "09_plan_mensual_fase0.sql",
    ), "el sello no cambia: F-161 no toca 06, 08, 09 ni 00 (design §2)"


def test_f161_r6_el_fichero_existe_en_el_directorio_del_step() -> None:
    from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG

    assert (DIRECTORIO_SQL_STG / "10_master_versiones.sql").exists()


# ===========================================================================
# R7-R9 · un solo catálogo, en mart
# ===========================================================================


def _sub_pasos_mart() -> list:
    from etl_sigrid.application.steps.build_mart_step import SUB_PASOS

    return list(SUB_PASOS)


def test_f161_r7_el_catalogo_va_entre_ddl_y_build_fact() -> None:
    ficheros = [s.sql_file for s in _sub_pasos_mart()]
    assert ficheros[:3] == ["01_ddl.sql", "01b_master_versiones.sql", "02_build_fact.sql"]
    sub = _sub_pasos_mart()[1]
    assert sub.name == "master_versiones"
    assert (sub.target_schema, sub.target_table) == ("mart", "master_versiones_tipadas")
    assert ficheros[-1] == "06_cp_tipologia.sql"


def test_f161_r7_se_construye_desde_stg_master_versiones() -> None:
    cuerpo = _compacto(_cuerpo(CATALOGO_MART, "mart", "master_versiones_tipadas"))
    assert "FROM stg.master_versiones" in cuerpo
    assert "stg.plan_mensual" not in cuerpo


@pytest.mark.parametrize("rama", CASCADA)
def test_f161_r7_la_cascada_copiada_literal(rama: str) -> None:
    assert rama in _compacto(_cuerpo(CATALOGO_MART, "mart", "master_versiones_tipadas"))


def test_f161_r7_la_tabla_tiene_las_ocho_y_detras_las_nuevas() -> None:
    assert columnas_proyectadas(_cuerpo(CATALOGO_MART, "mart", "master_versiones_tipadas")) == (
        OCHO + NUEVAS
    )


def test_f161_r7_la_tabla_lleva_su_clave_primaria() -> None:
    assert (
        "ALTER TABLE mart.master_versiones_tipadas ADD CONSTRAINT pk_master_versiones_tipadas "
        "PRIMARY KEY (obra_id, ambito_id, version);"
    ) in _ejecutable(CATALOGO_MART)


def test_f161_r8_la_vista_ocho_columnas_y_detras_las_nuevas() -> None:
    cuerpo = _cuerpo(CATALOGO_MART, "mart", "v_master_versiones_tipadas")
    assert columnas_proyectadas(cuerpo) == OCHO + NUEVAS
    assert "FROM mart.master_versiones_tipadas" in _compacto(cuerpo)


def test_f161_r7_los_drop_van_antes_que_los_create() -> None:
    texto = _ejecutable(CATALOGO_MART)
    for objeto in (
        "VIEW IF EXISTS mart.v_master_version_partida",
        "VIEW IF EXISTS mart.v_master_versiones_tipadas",
        "TABLE IF EXISTS mart.master_importe_mensual",
        "TABLE IF EXISTS mart.master_versiones_tipadas",
    ):
        assert f"DROP {objeto} CASCADE;" in texto, objeto
        assert texto.index(f"DROP {objeto}") < texto.index("CREATE TABLE mart.master_versiones_tipadas")


def test_f161_r9_06_ya_no_construye_el_catalogo() -> None:
    texto = _ejecutable(CP_TIPOLOGIA)
    assert "CREATE TABLE mart.master_versiones_tipadas" not in texto
    assert "CREATE OR REPLACE VIEW mart.v_master_versiones_tipadas" not in texto
    assert "DROP TABLE IF EXISTS mart.master_versiones_tipadas" not in texto
    assert "DROP VIEW IF EXISTS mart.v_master_versiones_tipadas" not in texto
    assert "LIKE '%ABC%'" not in texto, "la cascada del tipo vive solo en 01b (D11)"


def test_f161_r9_02_lee_la_tabla_y_no_repite_la_cascada() -> None:
    texto = _ejecutable(BUILD_FACT)
    assert "LIKE '%ABC%'" not in texto, "la cascada del tipo vive solo en 01b (D11)"
    assert "versiones_master AS" not in texto
    catalogo = _cte(_leer(BUILD_FACT), "versiones_tipadas")
    assert "FROM mart.master_versiones_tipadas" in catalogo
    assert "stg.plan_mensual" not in catalogo


def test_f161_r9_ningun_otro_fichero_de_mart_tipa_versiones() -> None:
    for ruta in sorted((DIR_SQL / "mart").glob("*.sql")):
        if ruta.name == CATALOGO_MART.name:
            continue
        assert "END AS tipo_master" not in _ejecutable(ruta), ruta.name
        assert "LIKE '%CUATRIM%'" not in _ejecutable(ruta), ruta.name


def test_f161_r9_la_cabecera_de_02_ya_no_deduce_el_catalogo_de_plan_mensual() -> None:
    cabecera = _leer(BUILD_FACT).split("TRUNCATE TABLE", 1)[0]
    assert "mart.master_versiones_tipadas" in cabecera
    assert "01b_master_versiones.sql" in cabecera


# ===========================================================================
# R10 · los consumidores filtran tiene_reparto (D4)
# ===========================================================================


def test_f161_r10_02_filtra_reparto_y_las_dos_fechas() -> None:
    catalogo = _cte(_leer(BUILD_FACT), "versiones_tipadas")
    assert catalogo == (
        "SELECT obra_id, ambito_id, version, version_fec_creacion, version_fec_efectiva, "
        "version_descripcion, version_tex, tipo_master "
        "FROM mart.master_versiones_tipadas "
        "WHERE tiene_reparto AND version_fec_creacion IS NOT NULL "
        "AND version_fec_efectiva IS NOT NULL"
    )


def test_f161_r10_el_resto_de_02_no_cambia() -> None:
    """La elección de la versión vigente es la de siempre."""
    texto = _ejecutable(BUILD_FACT)
    assert "JOIN versiones_tipadas vt ON vt.obra_id = mpm.obra_id AND vt.ambito_id = mpm.ambito_id" in texto
    assert "WHERE vt.version_fec_efectiva < (mpm.anio_mes + INTERVAL '1 month') AND vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')" in texto


def test_f161_r10_master_vigente_anual_filtra_reparto() -> None:
    cuerpo = _compacto(_cuerpo(CP_TIPOLOGIA, "mart", "master_vigente_anual"))
    assert (
        "JOIN mart.master_versiones_tipadas vt ON vt.obra_id = ao.obra_id AND vt.tiene_reparto "
        "AND vt.tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')"
    ) in cuerpo


def test_f161_r10_la_cuatrimestral_de_fin_obra_filtra_reparto() -> None:
    cuat = _cte(_leer(FIN_OBRA), "cuatrimestral")
    assert "WHERE v.tipo_master = 'Cuatrimestral' AND v.tiene_reparto" in cuat
    assert (
        "IF NOT EXISTS (SELECT 1 FROM mart.master_versiones_tipadas "
        "WHERE tipo_master = 'Cuatrimestral' AND tiene_reparto) THEN"
    ) in _ejecutable(FIN_OBRA)


# ===========================================================================
# R12 · el coste por versión y partida
# ===========================================================================

COLUMNAS_PARTIDA = [
    "empresa_id", "clave_obra", "obra_id", "ambito_id", "concepto", "version",
    "tipo_master", "reparto", "partida_id", "codigo_partida", "descripcion_partida",
    "categoria", "ruta_capitulos", "cantidad", "precio", "importe", "tiene_reparto",
]


def test_f161_r12_la_vista_por_partida_y_sus_columnas() -> None:
    cuerpo = _cuerpo(CATALOGO_MART, "mart", "v_master_version_partida")
    assert columnas_proyectadas(cuerpo) == COLUMNAS_PARTIDA
    assert "CREATE OR REPLACE VIEW mart.v_master_version_partida AS" in _leer(CATALOGO_MART)


def test_f161_r12_d14_lee_las_lineas_y_el_catalogo_sin_mirar_el_reparto() -> None:
    cuerpo = _compacto(_cuerpo(CATALOGO_MART, "mart", "v_master_version_partida"))
    assert "FROM stg.v_master_lineas l" in cuerpo
    assert (
        "JOIN mart.master_versiones_tipadas vt ON vt.obra_id = l.obra_id "
        "AND vt.ambito_id = l.ambito_id AND vt.version = l.version"
    ) in cuerpo
    assert "JOIN stg.partidas p ON p.partida_id = l.partida_id" in cuerpo
    assert "LEFT JOIN stg.obras o ON o.obra_id = l.obra_id" in cuerpo
    assert "WHERE" not in cuerpo, "no depende del reparto ni del ámbito (D14)"
    assert "CASE l.ambito_id WHEN 8 THEN 'COSTE' WHEN 11 THEN 'VENTA' END AS concepto" in cuerpo


# ===========================================================================
# R14-R17 · el planificado de importe al lado del temporal
# ===========================================================================

COLUMNAS_IMPORTE = [
    "obra_id", "empresa_id", "clave_obra", "ambito_id", "concepto", "anio_mes",
    "version_importe", "tipo_master_importe", "version_tex_importe", "importe_total_importe",
    "version_temporal", "tipo_master_temporal", "importe_total_temporal",
    "importe_con_reparto_temporal", "diferencia_importe", "diferencia_importe_con_reparto",
    "es_misma_version",
]


def _importe() -> str:
    return _cuerpo(CATALOGO_MART, "mart", "master_importe_mensual")


def test_f161_r14_columnas_del_planificado_de_importe() -> None:
    assert columnas_proyectadas(_importe()) == COLUMNAS_IMPORTE
    assert "CREATE TABLE mart.master_importe_mensual AS" in _leer(CATALOGO_MART)


def test_f161_r14_d8_el_ultimo_cierre_de_cualquier_tipo() -> None:
    elegibles = _cte(_importe(), "elegibles")
    assert elegibles == (
        "SELECT * FROM mart.master_versiones_tipadas WHERE version >= 1 AND n_lineas > 0 "
        "AND version_fec_efectiva IS NOT NULL"
    )
    assert "tipo_master" not in elegibles


def test_f161_r14_r16_la_temporal_con_el_predicado_de_02() -> None:
    temporales = _cte(_importe(), "temporales")
    assert temporales == (
        "SELECT * FROM mart.master_versiones_tipadas WHERE tiene_reparto "
        "AND version_fec_creacion IS NOT NULL AND version_fec_efectiva IS NOT NULL "
        "AND tipo_master IN ('Planif Inicial', 'ABC', 'Cuatrimestral')"
    )


@pytest.mark.parametrize(("cte", "origen"), [("importe", "elegibles"), ("temporal", "temporales")])
def test_f161_r14_la_eleccion_por_mes(cte: str, origen: str) -> None:
    cuerpo = _cte(_importe(), cte)
    assert (
        "ROW_NUMBER() OVER ( PARTITION BY m.obra_id, m.ambito_id, m.anio_mes "
        "ORDER BY e.version_fec_efectiva DESC, e.version DESC ) AS rn"
    ) in cuerpo
    assert f"JOIN {origen} e ON e.obra_id = m.obra_id AND e.ambito_id = m.ambito_id" in cuerpo
    assert "WHERE e.version_fec_efectiva < (m.anio_mes + INTERVAL '1 month')" in cuerpo


def test_f161_r14_d9_de_la_primera_version_hasta_el_mes_del_build() -> None:
    meses = _cte(_importe(), "meses")
    assert (
        "generate_series(i.primer_mes, date_trunc('month', p.hoy)::DATE, INTERVAL '1 month')"
        in meses
    )


def test_f161_r14_d10_las_dos_diferencias_sin_reescalar() -> None:
    texto = _compacto(_importe())
    assert "(i.importe_total - t.importe_total)::NUMERIC(18,2) AS diferencia_importe" in texto
    assert (
        "(i.importe_total - t.importe_con_reparto)::NUMERIC(18,2) AS diferencia_importe_con_reparto"
        in texto
    )
    assert "/" not in _sin_comentarios(_importe()), "sin reescalar (D3): ni una división"


def test_f161_r15_sin_temporal_el_importe_se_publica_igual() -> None:
    texto = _compacto(_importe())
    assert "LEFT JOIN importe i ON i.obra_id = m.obra_id AND i.ambito_id = m.ambito_id AND i.anio_mes = m.anio_mes AND i.rn = 1" in texto
    assert "LEFT JOIN temporal t ON t.obra_id = m.obra_id AND t.ambito_id = m.ambito_id AND t.anio_mes = m.anio_mes AND t.rn = 1" in texto


def test_f161_r17_hoy_es_la_fecha_del_build_y_solo_en_params() -> None:
    texto = _ejecutable(CATALOGO_MART)
    assert texto.count("CURRENT_DATE") == 1
    assert "params AS ( SELECT CURRENT_DATE AS hoy )" in _compacto(_importe())


def test_f161_r14_la_tabla_lleva_su_clave_primaria() -> None:
    assert (
        "ALTER TABLE mart.master_importe_mensual ADD CONSTRAINT pk_master_importe_mensual "
        "PRIMARY KEY (obra_id, ambito_id, anio_mes);"
    ) in _ejecutable(CATALOGO_MART)


# ===========================================================================
# R11 · la fotografía del catálogo de hoy
# ===========================================================================


def test_f161_r11_catalogo_anterior_es_la_seccion_1_de_06_en_491fbf1() -> None:
    from etl_sigrid.infrastructure.postgres.master_versiones_sql import CATALOGO_ANTERIOR

    assert _compacto(CATALOGO_ANTERIOR) == CATALOGO_491FBF1


def test_f161_r11_la_comparacion_es_un_except_en_los_dos_sentidos() -> None:
    from etl_sigrid.infrastructure.postgres.master_versiones_sql import (
        sql_comparacion_catalogo,
    )

    sql = _compacto(sql_comparacion_catalogo())
    assert sql.count("EXCEPT") == 2
    assert "'solo_anterior'" in sql and "'solo_nuevo'" in sql
    assert (
        "FROM mart.master_versiones_tipadas WHERE tiene_reparto "
        "AND version_fec_efectiva IS NOT NULL"
    ) in sql
    assert CATALOGO_491FBF1 in sql
