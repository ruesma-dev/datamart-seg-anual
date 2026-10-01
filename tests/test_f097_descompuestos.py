# tests/test_f097_descompuestos.py
"""
F-097 · El esquema `descompuestos` comprobado OFFLINE: el texto del SQL, el paso
`build_descompuestos`, su cableado en `main.py`, la configuracion, el
diccionario y la documentacion (R2, R12-R28).

Ningun test toca red ni base de datos: el esquema se construye contra el
PostgreSQL compartido de produccion, y construirlo desde la suite seria
escribir alli. Se fija, sobre el TEXTO del SQL (sin comentarios `--`), lo que la
spec decidio. Las cifras contra la base (partidas 419079 y 377070, recuentos
por origen, la primera carga) son verificacion MANUAL del humano (T17-T19).

Mismo estilo que `tests/test_f056_contabilidad.py`; los helpers se copian y no
se importan: la suite de otra feature no es una API.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from etl_sigrid.domain.descompuestos import (
    ESTADOS_CUADRE,
    ORIGENES,
    PATRON_NUMERO,
    POSICIONES,
    TIPOS_ELEMENTO,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DES = DIR_SQL / "descompuestos"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_CLAUDE = RAIZ / "CLAUDE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

SETUP = "00_setup.sql"
TROCEADO = "01_troceado.sql"
COSTE = "02_lineas_coste.sql"
MASTER = "03_lineas_master.sql"
ELEMENTOS = "04_elementos.sql"
CUADRE = "05_cuadre.sql"
VISTAS = "06_views.sql"
FICHEROS = [SETUP, TROCEADO, COSTE, MASTER, ELEMENTOS, CUADRE, VISTAS]

#: Las columnas de `descompuestos.lineas`, EN ORDEN: el contrato con el
#: consumidor y con la ficha del diccionario (R12, R18, R19).
COLUMNAS_LINEAS = [
    "origen", "obra_id", "partida_id", "presupuesto_id", "ambito_id", "fase_num",
    "orden", "codigo_elemento", "descripcion", "unidad", "codigo_alternativo",
    "tipo_elemento_codigo", "tipo_elemento", "naturaleza_codigo", "naturaleza",
    "rendimiento", "precio", "importe_unitario", "cantidad_total", "importe_total",
    "es_porcentaje", "porcentaje", "base_porcentaje", "dncpro_id", "producto_id",
    "proveedor_recomendado_id", "contrato_id", "contrato_linea_id", "fecha_maxima",
    "grupo_planificacion_id", "nivel", "es_nivel_padre", "es_version_inicial",
    "es_primera_abc", "es_vigente", "es_ultima", "tipo_version", "texto_version",
    "factor",  # F-120, al final (D8)
]

COLUMNAS_CUADRE = [
    "origen", "obra_id", "partida_id", "ambito_id", "fase_num", "presupuesto_id",
    "precio_partida", "suma_descompuesto", "diferencia", "num_lineas", "estado",
]

COLUMNAS_ELEMENTOS = [
    "obra_id", "codigo_elemento", "descripcion", "unidad", "tipo_elemento",
    "num_lineas", "lineas_estudio", "lineas_planif_jo", "lineas_master_inicial",
    "lineas_master_pre_abc", "lineas_master_planif_jo", "producto_id", "via_producto",
]

COLUMNAS_DES_TEXTO = [
    "presupuesto_id", "obra_id", "partida_id", "ambito_id", "fase_num", "cantidad",
    "precio", "haydes", "des", "batch_id",
]

COLUMNAS_VERSIONES = [
    "obra_id", "fase_num", "filas", "bytes", "huella", "batch_id", "cargada_at",
    "sello_troceado", "troceada_at", "atributos_troceado",
]

VISTAS_POR_ORIGEN = {
    "v_pbi_estudio": "ESTUDIO",
    "v_pbi_planif_jo": "PLANIF_JO",
    "v_pbi_master_planif_jo": "MASTER_PLANIF_JO",
}


@cache
def _crudo(nombre: str) -> str:
    ruta = DIR_DES / nombre
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    sin_comentarios = "\n".join(
        linea.split("--", 1)[0] for linea in _crudo(nombre).splitlines()
    )
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _bloque(nombre: str, desde: str, hasta: str | None = None) -> str:
    texto = _sql(nombre)
    assert desde in texto, f"no encuentro «{desde}» en {nombre}"
    trozo = texto.split(desde, 1)[1]
    if hasta is not None:
        assert hasta in trozo, f"no encuentro «{hasta}» detras de «{desde}» en {nombre}"
        trozo = trozo.split(hasta, 1)[0]
    return trozo


def _columnas_ddl(nombre: str, tabla: str) -> list[str]:
    """Las columnas de un `CREATE TABLE IF NOT EXISTS <tabla> (...)`, en orden."""
    cuerpo = _bloque(nombre, f"CREATE TABLE IF NOT EXISTS {tabla} (", ");")
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", cuerpo):
        palabra = trozo.strip().split(" ", 1)[0]
        if palabra and palabra.upper() not in {"CONSTRAINT", "PRIMARY", "CHECK", "UNIQUE"}:
            columnas.append(palabra)
    return columnas


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(objeto: str) -> dict:
    return _yaml("descompuestos.yaml")["objetos"][objeto]


def _texto_ficha(ficha: dict) -> str:
    return yaml.safe_dump(ficha, allow_unicode=True, width=10_000)


def _settings_falso(presupuesto_mb: float = 300) -> SimpleNamespace:
    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        ),
        business_rules={"sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}}},
        descompuestos=SimpleNamespace(presupuesto_mb=presupuesto_mb),
    )


# ===========================================================================
# R2 · el estado persistente que `--full` no trunca
# ===========================================================================


def test_f097_r2_esquema_y_tablas_de_estado_sin_drop() -> None:
    texto = _sql(SETUP)
    assert "CREATE SCHEMA IF NOT EXISTS descompuestos;" in texto
    assert _columnas_ddl(SETUP, "descompuestos._des_texto") == COLUMNAS_DES_TEXTO
    assert _columnas_ddl(SETUP, "descompuestos._versiones_cargadas") == COLUMNAS_VERSIONES
    assert "presupuesto_id BIGINT PRIMARY KEY" in texto
    assert "PRIMARY KEY (obra_id, fase_num)" in texto
    assert ("CREATE INDEX IF NOT EXISTS ix_des_texto_version ON descompuestos._des_texto "
            "(obra_id, ambito_id, fase_num);") in texto
    for nombre in FICHEROS:
        cuerpo = _sql(nombre)
        for tabla in ("_des_texto", "_versiones_cargadas"):
            assert not re.search(rf"(DROP TABLE|TRUNCATE)[^;]*{tabla}", cuerpo), (
                f"{nombre} destruye {tabla}: el incremental es estado persistente (R2)"
            )


# ===========================================================================
# R12 · R18 · R20 · descompuestos.lineas
# ===========================================================================


def test_f097_r12_lineas_con_origen_restringido() -> None:
    assert _columnas_ddl(COSTE, "descompuestos.lineas") == COLUMNAS_LINEAS
    ddl = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.lineas (", ");")
    assert "origen TEXT NOT NULL" in ddl
    lista = ", ".join(f"'{o}'" for o in ORIGENES)
    assert f"CONSTRAINT ck_lineas_origen CHECK (origen IN ({lista}))" in ddl


def test_f097_r18_identificacion_de_cada_linea() -> None:
    ddl = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.lineas (", ");")
    for columna in ("obra_id BIGINT NOT NULL", "partida_id BIGINT NOT NULL",
                    "presupuesto_id BIGINT", "ambito_id INTEGER NOT NULL",
                    "fase_num INTEGER NOT NULL", "orden INTEGER NOT NULL",
                    "dncpro_id BIGINT", "producto_id BIGINT"):
        assert columna in ddl, columna


def test_f097_r20_clave_de_negocio_unica() -> None:
    """Con `obra_id` dentro: las 227 filas con `obride = 0` de la version 26
    repiten partida con otra obra (medido el 2026-09-28, desviacion 1)."""
    ddl = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.lineas (", ");")
    assert ("CONSTRAINT pk_lineas PRIMARY KEY (origen, obra_id, partida_id, ambito_id, "
            "fase_num, orden)") in ddl
    texto = _sql(COSTE)
    assert ("CREATE INDEX IF NOT EXISTS ix_lineas_version ON descompuestos.lineas "
            "(obra_id, ambito_id, fase_num);") in texto
    assert "CREATE INDEX IF NOT EXISTS ix_lineas_partida ON descompuestos.lineas (partida_id);" in texto


# ===========================================================================
# R13 · R14 · R19 · el troceado, una sola definicion
# ===========================================================================


def test_f097_r13_parte_por_salto_seguido_de_registro() -> None:
    texto = _sql(TROCEADO)
    assert "CREATE OR REPLACE FUNCTION descompuestos.fn_trocear(des TEXT)" in texto
    assert ("regexp_split_to_table(replace(des, E'\\r', ''), E'\\n(?=~[A-Z]\\\\|)') "
            "WITH ORDINALITY AS r(reg, pos)") in texto
    assert "rtrim(r.reg, E'\\n') AS reg" in texto
    assert "WHERE r.reg ~ '^~[A-Z]\\|'" in texto
    assert "row_number() OVER (ORDER BY r.pos)" in texto


def test_f097_r13_las_posiciones_son_las_del_dominio() -> None:
    """Cada campo sale de `split_part(g.reg, '|', posicion + 1)`: el mismo
    mapa que `POSICIONES`, que es lo que prueba el espejo en Python."""
    encontradas = {
        m.group(2): int(m.group(1)) - 1
        for m in re.finditer(r"split_part\(g\.reg, '\|', (\d+)\).*? AS (\w+)", _sql(TROCEADO))
    }
    assert encontradas == POSICIONES


def test_f097_r13_una_sola_definicion_para_ambito_3_y_master() -> None:
    for nombre in (COSTE, MASTER, CUADRE):
        assert "descompuestos.fn_trocear(d.des)" in _sql(nombre), nombre
        assert "regexp_split_to_table" not in _sql(nombre), f"{nombre} trocea por su cuenta"
        assert "split_part" not in _sql(nombre), f"{nombre} mapea campos por su cuenta"


def test_f097_r14_fn_num_mismo_patron_que_el_dominio() -> None:
    texto = _sql(SETUP)
    assert "CREATE OR REPLACE FUNCTION descompuestos.fn_num(t TEXT) RETURNS NUMERIC" in texto
    assert f"WHEN btrim(t) ~ '{PATRON_NUMERO}' THEN btrim(t)::NUMERIC" in texto
    assert "IMMUTABLE" in _bloque(SETUP, "FUNCTION descompuestos.fn_num", "$$")


def test_f097_r14_fn_fecha_y_el_enlace_sin_excepcion() -> None:
    texto = _sql(SETUP)
    assert "CREATE OR REPLACE FUNCTION descompuestos.fn_fecha(d BIGINT) RETURNS DATE" in texto
    assert "RETURN to_date(d::TEXT, 'YYYYMMDD'); EXCEPTION WHEN OTHERS THEN RETURN NULL;" in texto
    troceado = _sql(TROCEADO)
    assert "WHEN split_part(g.reg, '|', 37) ~ '^[0-9]{1,18}$'" in troceado
    assert "descompuestos.fn_num(split_part(g.reg, '|', 4)) AS precio" in troceado


def test_f097_r19_tipo_de_elemento_por_case() -> None:
    texto = _sql(TROCEADO)
    for codigo, tipo in TIPOS_ELEMENTO.items():
        assert f"WHEN '{codigo}' THEN '{tipo}'" in texto, codigo
    assert "WHEN c.tipo_elemento_codigo IS NULL THEN 'SIN_TIPO'" in texto
    assert "ELSE 'DESCONOCIDO'" in texto


def test_f097_r19_importes_y_porcentajes() -> None:
    texto = _sql(TROCEADO)
    # Review 1: lo que no cabe en NUMERIC(18,2) tras redondear es NULL, no un
    # `numeric field overflow` que tumbe el build (el espejo hace lo mismo).
    assert ("CASE WHEN abs(ROUND(c.precio * c.factor * c.rendimiento, 2)) < 1e16 "
            "THEN ROUND(c.precio * c.factor * c.rendimiento, 2)::NUMERIC(18,2) END AS importe_unitario") in texto
    assert ("CASE WHEN abs(ROUND(c.cantidad_total * c.precio, 2)) < 1e16 "
            "THEN ROUND(c.cantidad_total * c.precio, 2)::NUMERIC(18,2) END AS importe_total") in texto
    assert "COALESCE(c.tipo_elemento_codigo IN ('4', '13'), FALSE) AS es_porcentaje" in texto
    assert "CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.rendimiento * 100 END AS porcentaje" in texto
    assert "CASE WHEN c.tipo_elemento_codigo IN ('4', '13') THEN c.precio END AS base_porcentaje" in texto


# ===========================================================================
# R15 · R16 · ESTUDIO y PLANIF_JO
# ===========================================================================


def test_f097_r15_estudio_sin_las_partidas_enlazadas() -> None:
    texto = _sql(COSTE)
    assert "DELETE FROM descompuestos.lineas WHERE origen IN ('ESTUDIO', 'PLANIF_JO');" in texto
    estudio = _bloque(COSTE, "enlazadas AS (", "INSERT INTO descompuestos.lineas")
    assert "WHERE t.dncpro_id IS NOT NULL" in estudio
    insert = _bloque(COSTE, "SELECT 'ESTUDIO'", ";")
    assert "d.ambito_id = 3 AND d.fase_num = 0" in _sql(COSTE)
    assert "NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id)" in insert


def test_f097_r16_planif_jo_desde_dncpro_de_la_obra() -> None:
    planif = _bloque(COSTE, "SELECT 'PLANIF_JO'", ";")
    assert "FROM raw.obr o JOIN raw.dncpro p ON p.dncide = o.dncide" in planif
    assert "WHERE COALESCE(o.dncide, 0) <> 0 AND COALESCE(p.paride, 0) <> 0" in planif
    assert "row_number() OVER (PARTITION BY o.ide, p.paride ORDER BY p.pos, p.ide)" in planif
    for expresion in ("NULLIF(p.entide, 0)", "NULLIF(p.adjctride, 0)", "NULLIF(p.adjctrlin, 0)",
                      "descompuestos.fn_fecha(p.fec)", "NULLIF(p.gpcide, 0)", "p.niv",
                      "COALESCE(p.nivpad, 0) <> 0", "LEFT JOIN raw.con c ON c.ide = p.proide",
                      "LEFT JOIN raw.auxpronat n ON n.ide = p.natide"):
        assert expresion in planif, expresion
    assert "o.ide, p.paride, NULL::BIGINT, 3, 0," in planif, "presupuesto NULL, ambito 3 y fase 0"


def test_f097_r19_planif_jo_con_sus_importes() -> None:
    planif = _bloque(COSTE, "SELECT 'PLANIF_JO'", ";")
    assert ("CASE WHEN abs(ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2)) < 1e16 "
            "THEN ROUND(p.pre::NUMERIC * f.factor * p.canren::NUMERIC, 2) END") in planif, "F-120"
    assert ("CASE WHEN abs(ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2)) < 1e16 "
            "THEN ROUND(p.can::NUMERIC * p.pre::NUMERIC, 2) END") in planif
    assert "'SIN_TIPO'" in planif


# ===========================================================================
# R17 · R21 · el master por lotes
# ===========================================================================


def test_f097_r17_origen_de_cada_version() -> None:
    atributos = _bloque(MASTER, "CREATE TEMP TABLE _atributos", ";")
    assert ("CASE WHEN v.fase_num = 0 THEN 'MASTER_INICIAL' WHEN abc.fase_abc IS NOT NULL "
            "AND v.fase_num >= abc.fase_abc THEN 'MASTER_PLANIF_JO' ELSE 'MASTER_PRE_ABC' END "
            "AS origen") in atributos
    assert "WHERE amb = 8 AND UPPER(tex) LIKE '%ABC%'" in atributos, "la regla de mart"
    assert "cod = /*F097_COD_VIGENTE*/" in _crudo(MASTER)
    for flag in ("es_version_inicial", "es_primera_abc", "es_vigente", "es_ultima",
                 "tipo_version", "texto_version"):
        assert f"AS {flag}" in atributos, flag


def test_f097_r17_tipo_version_es_la_regla_de_mart() -> None:
    mart = re.sub(r"\s+", " ", (DIR_SQL / "mart" / "02_build_fact.sql").read_text(encoding="utf-8"))
    for literal in ("'Sin clasificar'", "'ABC'", "'Planif Inicial'", "'Cuatrimestral'",
                    "'Cierre mensual'", "LIKE '%CUATRIM%'", "LIKE '%VALORADA%'",
                    "LIKE '%INICIAL%'", "LIKE '%CIERRE%'"):
        assert literal in mart and literal in _sql(MASTER), literal


def test_f097_r17_texto_de_version_sin_duplicar_obrfasamb() -> None:
    """`obrfasamb` guarda versiones DOS veces (caso documentado en docs/referencia/05)."""
    atributos = _bloque(MASTER, "CREATE TEMP TABLE _atributos", ";")
    assert ("SELECT DISTINCT ON (obride, fas) obride AS obra_id, fas AS fase_num, "
            "NULLIF(TRIM(tex), '') AS texto_version FROM raw.obrfasamb WHERE amb = 8 "
            "ORDER BY obride, fas, ide DESC") in atributos


def test_f097_r21_el_lote_por_marcador_una_vez() -> None:
    crudo = _crudo(MASTER)
    assert crudo.count("/*F097_LOTE*/") == 1
    assert crudo.count("/*F097_COD_VIGENTE*/") == 1
    assert crudo.count("/*F097_SELLO*/") == 1
    assert ("CREATE TEMP TABLE _lote ON COMMIT DROP AS SELECT v.obra_id, v.fase_num FROM "
            "descompuestos._versiones_cargadas v WHERE /*F097_LOTE*/;") in re.sub(r"\s+", " ", crudo)


def test_f097_r21_borra_e_inserta_lineas_y_cuadre_del_lote() -> None:
    texto = _sql(MASTER)
    origenes = "('MASTER_INICIAL', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')"
    assert (f"DELETE FROM descompuestos.lineas l USING _lote t WHERE l.ambito_id = 8 AND "
            f"l.obra_id = t.obra_id AND l.fase_num = t.fase_num AND l.origen IN {origenes};") in texto
    assert ("DELETE FROM descompuestos.cuadre_partida q USING _lote t WHERE q.ambito_id = 8 AND "
            "q.obra_id = t.obra_id AND q.fase_num = t.fase_num;") in texto
    insert = _bloque(MASTER, "INSERT INTO descompuestos.lineas", ";")
    assert "JOIN _lote l ON l.obra_id = d.obra_id AND l.fase_num = d.fase_num" in insert
    assert "WHERE d.ambito_id = 8" in insert
    assert "LEFT JOIN raw.dncpro dp ON dp.ide = t.dncpro_id" in insert
    assert "INSERT INTO descompuestos.cuadre_partida" in texto


def test_f097_r21_sello_y_fecha_del_troceado() -> None:
    crudo = re.sub(r"\s+", " ", _crudo(MASTER))
    assert ("SET sello_troceado = /*F097_SELLO*/, troceada_at = (now() AT TIME ZONE 'UTC'), "
            "atributos_troceado = a.huella_atributos") in crudo


def test_f097_r21_borra_lo_de_las_versiones_que_ya_no_estan() -> None:
    texto = _sql(MASTER)
    assert ("SELECT DISTINCT obra_id, fase_num FROM descompuestos.lineas WHERE ambito_id = 8 "
            "EXCEPT SELECT obra_id, fase_num FROM descompuestos._versiones_cargadas") in texto
    assert ("SELECT DISTINCT obra_id, fase_num FROM descompuestos.cuadre_partida WHERE ambito_id = 8 "
            "EXCEPT SELECT obra_id, fase_num FROM descompuestos._versiones_cargadas") in texto


def test_f097_r21_los_flags_se_recalculan_solo_donde_cambian() -> None:
    """La vigente y la ultima cambian sin que cambie el texto: `UPDATE` barato,
    solo de las versiones cuya huella de atributos no es la aplicada."""
    texto = _sql(MASTER)
    cambiadas = _bloque(MASTER, "CREATE TEMP TABLE _cambiadas", ";")
    assert "v.troceada_at IS NOT NULL" in cambiadas
    assert "v.atributos_troceado IS DISTINCT FROM a.huella_atributos" in cambiadas
    assert "NOT EXISTS (SELECT 1 FROM _lote l WHERE l.obra_id = a.obra_id AND l.fase_num = a.fase_num)" in cambiadas
    assert "UPDATE descompuestos.lineas l SET origen = c.origen" in texto
    assert "UPDATE descompuestos.cuadre_partida q SET origen = c.origen" in texto


# ===========================================================================
# R22 · R23 · R24 · catalogo, cuadre y vistas
# ===========================================================================


def test_f097_r22_catalogo_de_elementos() -> None:
    texto = _sql(ELEMENTOS)
    assert "DROP TABLE IF EXISTS descompuestos.elementos;" in texto
    assert "CREATE TABLE descompuestos.elementos AS" in texto
    assert "GROUP BY obra_id, codigo_elemento" in texto
    assert "mode() WITHIN GROUP (ORDER BY descripcion) AS descripcion" in texto
    assert "mode() WITHIN GROUP (ORDER BY unidad) AS unidad" in texto
    for origen in ORIGENES:
        assert f"COUNT(*) FILTER (WHERE origen = '{origen}') AS lineas_{origen.lower()}" in texto
    assert "FROM raw.pro p JOIN raw.con c ON c.ide = p.ide" in texto
    assert "pe.emp = co.emp AND pe.cod = a.codigo_elemento" in texto
    assert "COALESCE(a.producto_enlazado, pe.producto_id) AS producto_id" in texto
    assert "ALTER TABLE descompuestos.elementos ADD PRIMARY KEY (obra_id, codigo_elemento);" in texto
    final = _bloque(ELEMENTOS, "CREATE TABLE descompuestos.elementos AS", ";")
    ultimo_select = final[final.rindex("SELECT "):]
    columnas = re.findall(r" AS (\w+)(?:,| FROM)", ultimo_select)
    assert columnas == [c for c in COLUMNAS_ELEMENTOS if c not in ("obra_id", "codigo_elemento")]


def test_f097_r23_cuadre_estados_y_tolerancia() -> None:
    assert ESTADOS_CUADRE == ("CUADRA", "NO_CUADRA", "SIN_DESCOMPUESTO", "SUSTITUIDO_POR_PLANIFICACION")
    assert _columnas_ddl(COSTE, "descompuestos.cuadre_partida") == COLUMNAS_CUADRE
    ddl = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.cuadre_partida (", ");")
    assert "CONSTRAINT pk_cuadre_partida PRIMARY KEY (origen, partida_id, ambito_id, fase_num)" in ddl
    lista = ", ".join(f"'{e}'" for e in ESTADOS_CUADRE)
    assert f"CONSTRAINT ck_cuadre_estado CHECK (estado IN ({lista}))" in ddl
    for nombre in (CUADRE, MASTER):
        texto = _sql(nombre)
        assert "ABS(h.precio_partida - COALESCE(s.suma, 0)) <= 0.01 THEN 'CUADRA'" in texto, nombre
        assert "ELSE 'NO_CUADRA'" in texto and "THEN 'SIN_DESCOMPUESTO'" in texto
        assert "NOT EXISTS (SELECT 1 FROM raw.obrparpar x WHERE x.padide = pp.paride)" in texto, (
            f"{nombre}: solo las partidas hoja"
        )
        assert "COALESCE(pp.pre, 0) <> 0 AND pp.obride <> 0" in texto
        assert "ROUND(pp.pre::NUMERIC, 2) AS precio_partida" in texto


def test_f097_r23_estudio_sustituido_por_la_planificacion() -> None:
    texto = _sql(CUADRE)
    assert "DELETE FROM descompuestos.cuadre_partida WHERE origen IN ('ESTUDIO', 'PLANIF_JO');" in texto
    assert "WHEN o.origen = 'ESTUDIO' AND su.partida_id IS NOT NULL THEN 'SUSTITUIDO_POR_PLANIFICACION'" in texto
    assert "CROSS JOIN (VALUES ('ESTUDIO'), ('PLANIF_JO')) o(origen)" in texto
    assert "pp.amb = 3 AND pp.fas = 0" in texto


def test_f097_r24_tres_vistas_cada_una_con_su_origen() -> None:
    texto = _sql(VISTAS)
    for vista, origen in VISTAS_POR_ORIGEN.items():
        cuerpo = _bloque(VISTAS, f"CREATE OR REPLACE VIEW descompuestos.{vista} AS", ";")
        assert f"FROM descompuestos.lineas WHERE origen = '{origen}'" in cuerpo, vista
    assert texto.count("CREATE OR REPLACE VIEW") == 3


# ===========================================================================
# R25 · el paso de build, el pipeline y los comandos
# ===========================================================================


class _PgBuild:
    """Doble de `PostgresClient` para el paso de build."""

    def __init__(self, pendientes: list[tuple] | None = None, falla_en: str | None = None) -> None:
        self._pendientes = pendientes or []
        self._falla_en = falla_en
        self.orden: list[str] = []

    def execute_sql_file(self, path: Path, *, params: dict | tuple | None = None) -> None:
        self.orden.append(path.name)
        if self._falla_en == path.name:
            raise RuntimeError("relation raw.dncpro does not exist")

    def execute_sql_text(self, sql_text: str) -> int:
        self.orden.append(sql_text)
        if self._falla_en == MASTER:
            raise RuntimeError("duplicate key value violates unique constraint pk_lineas")
        return 0

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.orden.append("pendientes")
        return list(self._pendientes)

    def count_rows(self, schema: str, table: str) -> int:
        return {"lineas": 10, "elementos": 3, "cuadre_partida": 4}[table]


def _build(monkeypatch: pytest.MonkeyPatch, pg: _PgBuild, **kwargs):
    from etl_sigrid.application.steps import build_descompuestos_step
    from etl_sigrid.application.steps.build_descompuestos_step import BuildDescompuestosStep

    monkeypatch.setattr(build_descompuestos_step, "build_postgres_client", lambda _s: pg)
    settings = kwargs.pop("settings", _settings_falso())
    return BuildDescompuestosStep(settings, **kwargs).run()


def test_f097_r25_paso_con_sus_dependencias() -> None:
    from etl_sigrid.application.steps import build_descompuestos_step
    from etl_sigrid.application.steps.build_descompuestos_step import BuildDescompuestosStep

    paso = BuildDescompuestosStep(_settings_falso())
    assert paso.name == "build_descompuestos"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["ingest_raw", "ingest_descompuestos"]
    assert [s.sql_file for s in build_descompuestos_step.SUB_PASOS] == FICHEROS
    declarados = [(s.name, s.target_table, s.por_lotes) for s in build_descompuestos_step.SUB_PASOS]
    assert declarados == [
        ("setup", None, False), ("troceado", None, False), ("lineas_coste", None, False),
        ("lineas_master", "lineas", True), ("elementos", "elementos", False),
        ("cuadre", "cuadre_partida", False), ("vistas", None, False),
    ]


def test_f097_r25_encadena_y_trocea_por_lotes(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.domain.descompuestos import MB
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgBuild(pendientes=[(7, 1, int(0.4 * MB), True), (9, 0, int(0.4 * MB), False)])
    resultado = _build(monkeypatch, pg)

    assert resultado.status == StepStatus.SUCCESS, resultado.error_message
    assert pg.orden[:4] == [SETUP, TROCEADO, COSTE, "pendientes"]
    (lote,) = [o for o in pg.orden if "_lote" in o]
    assert "(v.obra_id, v.fase_num) IN ((7, 1), (9, 0))" in lote
    assert "/*F097_" not in lote, "ningun marcador sin sustituir"
    assert pg.orden[-3:] == [ELEMENTOS, CUADRE, VISTAS]
    assert resultado.rows_processed == 10 + 3 + 4
    assert resultado.metadata["versiones_troceadas"] == 2
    assert resultado.metadata["lotes"] == 1
    assert resultado.metadata["versiones_aplazadas"] == 0


def test_f097_r25_un_fallo_sale_con_su_nombre_y_para(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgBuild(pendientes=[(7, 1, 10, True)], falla_en=MASTER)
    resultado = _build(monkeypatch, pg)
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en lineas_master:")
    assert ELEMENTOS not in pg.orden, "tras el fallo no se ejecuta nada mas"
    assert resultado.finished_at is not None


def test_f097_r25_falta_el_fichero_y_sale_con_su_nombre(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_descompuestos_step
    from etl_sigrid.application.steps.build_descompuestos_step import _SubStep
    from etl_sigrid.domain.entities import StepStatus

    monkeypatch.setattr(build_descompuestos_step, "SUB_PASOS",
                        (_SubStep(name="setup", sql_file=SETUP),
                         _SubStep(name="fantasma", sql_file="99_no_existe.sql")))
    pg = _PgBuild()
    resultado = _build(monkeypatch, pg)
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en fantasma:")
    assert pg.orden == [SETUP]


def test_f097_r21_sin_pendientes_el_master_corre_igual_con_lote_vacio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin versiones que trocear, el fichero se ejecuta UNA vez con el lote a
    FALSE: los flags de la vigente y el borrado de lo que ya no esta no esperan."""
    pg = _PgBuild(pendientes=[])
    resultado = _build(monkeypatch, pg)
    (lote,) = [o for o in pg.orden if "_lote" in o]
    assert "WHERE FALSE;" in lote
    assert resultado.metadata["versiones_troceadas"] == 0 and resultado.metadata["lotes"] == 0


def test_f097_r21_el_tope_del_build_aplaza(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.domain.descompuestos import MB

    pendientes = [(1, f, int(0.6 * MB), False) for f in range(3)]
    resultado = _build(monkeypatch, _PgBuild(pendientes=pendientes),
                       settings=_settings_falso(presupuesto_mb=1))
    assert resultado.metadata["versiones_troceadas"] == 1
    assert resultado.metadata["versiones_aplazadas"] == 2
    resultado = _build(monkeypatch, _PgBuild(pendientes=pendientes),
                       settings=_settings_falso(presupuesto_mb=1), sin_tope=True)
    assert resultado.metadata["versiones_troceadas"] == 3


def test_f097_r21_la_consulta_de_pendientes() -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import sql_versiones_pendientes

    texto = sql_versiones_pendientes("0123456789abcdef", "15")
    assert "FROM descompuestos._versiones_cargadas v" in texto
    assert "WHERE v.sello_troceado IS DISTINCT FROM '0123456789abcdef'" in texto
    assert "FROM raw.conext WHERE cod = '15'" in texto
    with pytest.raises(ValueError, match="sello"):
        sql_versiones_pendientes("'; DROP", "15")


def test_f097_r21_componer_el_lote() -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import componer_sql_lote

    plantilla = "A /*F097_LOTE*/ B /*F097_SELLO*/ C /*F097_COD_VIGENTE*/"
    assert componer_sql_lote(plantilla, [(1, 0), (2, 3)], "abcdef0123456789", "15") == (
        "A (v.obra_id, v.fase_num) IN ((1, 0), (2, 3)) B 'abcdef0123456789' C '15'"
    )
    assert componer_sql_lote(plantilla, [], "abcdef0123456789", "15").startswith("A FALSE B")
    for lote in ([(True, 0)], [(1, "0")], [(1.0, 2)]):
        with pytest.raises(ValueError, match="entero"):
            componer_sql_lote(plantilla, lote, "abcdef0123456789", "15")
    with pytest.raises(ValueError, match="marcador"):
        componer_sql_lote("A /*F097_LOTE*/ /*F097_LOTE*/", [(1, 0)], "abcdef0123456789", "15")
    with pytest.raises(ValueError, match="sello"):
        componer_sql_lote(plantilla, [(1, 0)], "no-hex!", "15")
    with pytest.raises(ValueError, match="cod"):
        componer_sql_lote(plantilla, [(1, 0)], "abcdef0123456789", "1'5")


def test_f097_r11_sello_del_sql_de_troceado(tmp_path: Path) -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import (
        FICHEROS_DEL_SELLO,
        sello_de_troceado,
    )

    assert FICHEROS_DEL_SELLO == (SETUP, TROCEADO, MASTER), "00 entra con F-120"
    real = sello_de_troceado()
    assert re.fullmatch(r"[0-9a-f]{16}", real)
    for nombre in (SETUP, TROCEADO, MASTER, COSTE):
        (tmp_path / nombre).write_text(_crudo(nombre), encoding="utf-8")
    assert sello_de_troceado(tmp_path) == real
    (tmp_path / COSTE).write_text("otra cosa", encoding="utf-8")
    assert sello_de_troceado(tmp_path) == real, "02 no entra en el sello: se rehace entero cada noche"
    (tmp_path / TROCEADO).write_text(_crudo(TROCEADO) + "\n-- cambio", encoding="utf-8")
    assert sello_de_troceado(tmp_path) != real


def test_f097_r25_orden_en_run_all() -> None:
    import main

    nombres = [p.name for p in main.build_pipeline_steps(_settings_falso())]
    assert nombres.index("build_contabilidad") < nombres.index("ingest_descompuestos")
    assert nombres.index("ingest_descompuestos") < nombres.index("build_descompuestos")
    assert nombres.index("build_descompuestos") < nombres.index("build_cierre")


def test_f097_r25_nadie_depende_de_los_descompuestos() -> None:
    import main
    from etl_sigrid.application.orchestrator import Orchestrator

    pasos = main.build_pipeline_steps(_settings_falso())
    ordenados = [p.name for p in Orchestrator(pasos)._topological_sort()]
    assert ordenados.index("ingest_raw") < ordenados.index("build_descompuestos")
    assert ordenados.index("ingest_descompuestos") < ordenados.index("build_descompuestos")
    for paso in pasos:
        if paso.name != "build_descompuestos":
            assert "ingest_descompuestos" not in paso.depends_on, paso.name
        assert "build_descompuestos" not in paso.depends_on, paso.name


@pytest.mark.parametrize(
    ("comando", "clase"),
    [("ingest-descompuestos", "IngestDescompuestosStep"),
     ("build-descompuestos", "BuildDescompuestosStep")],
)
def test_f097_r25_comandos_sueltos_con_sin_tope(comando: str, clase: str) -> None:
    import main

    assert comando in main.cli.commands
    opciones = {o.name for o in main.cli.commands[comando].params}
    assert "sin_tope" in opciones
    fuente = Path(main.__file__).read_text(encoding="utf-8")
    inicio = fuente.index(f'@cli.command("{comando}")')
    fin = fuente.index("@cli.command(", inicio + 10)
    cuerpo = fuente[inicio:fin]
    assert "ejecucion = _arrancar_ejecucion(pg)" in cuerpo
    assert f"_ejecutar_paso({clase}(" in cuerpo and "sin_tope=sin_tope" in cuerpo
    assert "PublicarDiccionarioStep" not in cuerpo


def test_f097_r25_comandos_en_la_lista_de_f024() -> None:
    from tests.test_f024_cli import COMANDOS_QUE_ESCRIBEN, STEPS_POR_COMANDO

    assert STEPS_POR_COMANDO["ingest-descompuestos"] == (
        "IngestDescompuestosStep", "ingest_descompuestos", "ingest")
    assert STEPS_POR_COMANDO["build-descompuestos"] == (
        "BuildDescompuestosStep", "build_descompuestos", "build_aux")
    assert {"ingest-descompuestos", "build-descompuestos"} <= set(COMANDOS_QUE_ESCRIBEN)


# ===========================================================================
# R26 · solo `raw` y su propio esquema
# ===========================================================================


def test_f097_r26_solo_raw() -> None:
    for nombre in FICHEROS:
        texto = _sql(nombre)
        # `IS DISTINCT FROM a.col` no es una lectura: el lookbehind lo descarta
        esquemas = set(re.findall(r"(?<!DISTINCT )(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(\w+)\.\w+", texto))
        assert esquemas <= {"raw", "descompuestos"}, f"{nombre} usa {sorted(esquemas)}"
        for vetado in ("stg.", "mart.", "cierre.", "compras.", "maestro.", "contabilidad."):
            assert not re.search(rf"(?<![\w]){re.escape(vetado)}", texto), f"{nombre} nombra {vetado}"


@pytest.mark.parametrize("nombre", FICHEROS)
def test_f097_r26_ficheros_con_cabecera_y_ruta(nombre: str) -> None:
    primera = _crudo(nombre).splitlines()[0]
    assert primera == f"-- etl_sigrid/infrastructure/postgres/sql/descompuestos/{nombre}"


# ===========================================================================
# R27 · configuracion, esquemas y diccionario
# ===========================================================================


def test_f097_r27_esquemas_de_consumo_y_del_datamart() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS, DescompuestosSettings
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    assert "descompuestos" in ESQUEMAS_DEL_DATAMART
    assert "descompuestos" in DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    assert DescompuestosSettings.model_fields["presupuesto_mb"].default == 300
    entorno = (RAIZ / ".env.example").read_text(encoding="utf-8")
    linea = next(f for f in entorno.splitlines() if f.startswith("PG_CONSUMPTION_SCHEMAS="))
    assert "descompuestos" in linea.split("=", 1)[1].split(",")
    assert "DESCOMPUESTOS_PRESUPUESTO_MB=300" in entorno.splitlines()


def test_f097_r27_el_presupuesto_lo_lee_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import DescompuestosSettings

    monkeypatch.setenv("DESCOMPUESTOS_PRESUPUESTO_MB", "120")
    assert DescompuestosSettings(_env_file=None).presupuesto_mb == 120
    monkeypatch.setenv("DESCOMPUESTOS_PRESUPUESTO_MB", "0")
    with pytest.raises(ValueError):
        DescompuestosSettings(_env_file=None)


def test_f097_r27_check_declarados_ve_el_esquema() -> None:
    from etl_sigrid.domain.inventario import objetos_de_sql

    textos = {f"descompuestos/{f.name}": f.read_text(encoding="utf-8") for f in sorted(DIR_DES.glob("*.sql"))}
    declarados = {(o.esquema, o.objeto) for o in objetos_de_sql(textos)}
    esperados = {("descompuestos", o) for o in (
        "_des_texto", "_versiones_cargadas", "lineas", "cuadre_partida", "elementos",
        *VISTAS_POR_ORIGEN, "fn_num", "fn_fecha", "fn_trocear")}
    assert declarados == esperados


def test_f097_r27_fichas_de_todos_los_objetos() -> None:
    objetos = _yaml("descompuestos.yaml")["objetos"]
    assert set(objetos) == {
        "_des_texto", "_versiones_cargadas", "lineas", "cuadre_partida", "elementos",
        *VISTAS_POR_ORIGEN, "fn_num", "fn_fecha", "fn_trocear"}
    assert list(_ficha("lineas")["columnas"]) == COLUMNAS_LINEAS
    assert list(_ficha("cuadre_partida")["columnas"]) == COLUMNAS_CUADRE
    assert list(_ficha("elementos")["columnas"]) == COLUMNAS_ELEMENTOS
    assert list(_ficha("_des_texto")["columnas"]) == COLUMNAS_DES_TEXTO
    assert list(_ficha("_versiones_cargadas")["columnas"]) == COLUMNAS_VERSIONES
    for tabla in ("_des_texto", "_versiones_cargadas"):
        assert _ficha(tabla)["consumo_recomendado"] is False, "estado del incremental, no se consulta"
        assert _ficha(tabla)["paso_etl"] == "ingest_descompuestos"
    for objeto in ("lineas", "cuadre_partida", "elementos", *VISTAS_POR_ORIGEN):
        assert _ficha(objeto)["consumo_recomendado"] is True, objeto
        assert _ficha(objeto)["paso_etl"] == "build_descompuestos"
    assert _ficha("lineas")["clave_negocio"] == [
        "origen", "obra_id", "partida_id", "ambito_id", "fase_num", "orden"]
    assert _ficha("cuadre_partida")["clave_negocio"] == ["origen", "partida_id", "ambito_id", "fase_num"]
    assert _ficha("elementos")["clave_negocio"] == ["obra_id", "codigo_elemento"]


def test_f097_r27_las_fichas_avisan_de_lo_provisional() -> None:
    lineas = _texto_ficha(_ficha("lineas"))
    assert "PROVISIONAL" in lineas and "D8" in lineas, "tipos 3 y 11 sin validar con Negocio"
    cabecera = (DIR_DICCIONARIO / "descompuestos.yaml").read_text(encoding="utf-8")
    for texto in (lineas, _texto_ficha(_ficha("cuadre_partida"))):
        assert "INCOMPLETO" in texto and "primera carga" in texto, (
            "sin la primera carga el master sale incompleto: la ficha lo avisa"
        )
    assert "R-DESCOMPUESTO-ORIGEN" in cabecera
    assert "134,35" in lineas and "419079" in lineas, "el caso de Juan, con su cifra"


def test_f097_r27_global_esquema_regla_y_version() -> None:
    glob = _yaml("00_global.yaml")
    assert glob["version"] >= 37, "F-118 la sube a 38"
    esquema = glob["esquemas"]["descompuestos"]
    assert esquema["pasos_etl"] == ["ingest_descompuestos", "build_descompuestos"]
    assert esquema["refresco"] == "nocturno" and esquema["consumo_recomendado"] is True
    reglas = {r["codigo"]: r for r in glob["reglas"]}
    regla = reglas["R-DESCOMPUESTO-ORIGEN"]
    assert regla["severidad"] == "bloqueante"
    assert "descompuestos.lineas" in regla["ambito"]
    texto = regla["regla"] + regla["motivo"]
    for termino in ("origen", "ESTUDIO", "PLANIF_JO", "MASTER_PLANIF_JO", "fase_num"):
        assert termino in texto, termino
    assert "descompuestos" in reglas["R-FRESCURA"]["ambito"]
    assert glob["pendientes"] == []


# ===========================================================================
# R28 · la documentacion, en el mismo trabajo
# ===========================================================================


def test_f097_r28_documentacion() -> None:
    arquitectura = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("descompuestos.lineas", "ingest_descompuestos", "build_descompuestos",
                    "_versiones_cargadas", "Planificación compras", "~D|",
                    "obrparpre` no tiene `tiemod"):
        assert termino in arquitectura, f"ARCHITECTURE.md no dice «{termino}»"
    claude = DOC_CLAUDE.read_text(encoding="utf-8")
    assert "`descompuestos/`" in claude and "ingest_descompuestos" in claude
    import main

    documentacion = main.run_all.__doc__ or ""
    assert "siete build" in documentacion and "descompuestos" in documentacion
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("F-097", "ingest_descompuestos", "descompuestos.lineas", "obrparpre"):
        assert termino in texto, f"azure-apps no dice «{termino}» (R28)"


def test_f097_un_test_por_requisito() -> None:
    """R2-R29 con al menos un test (R1, R30 y R31 son verificacion MANUAL)."""
    import tests.test_f097_ingesta_descompuestos as ingesta
    import tests.test_f097_planificador as planificador
    import tests.test_f097_tiemod_obrparpre as tiemod

    nombres = [n for modulo in (globals(), vars(ingesta), vars(planificador), vars(tiemod))
               for n in modulo if n.startswith("test_f097_r")]
    for n in range(2, 30):
        assert any(x.startswith(f"test_f097_r{n}_") for x in nombres), f"R{n} sin test"


@pytest.mark.parametrize(
    ("comando", "atributo", "nombre", "stage"),
    [("ingest-descompuestos", "IngestDescompuestosStep", "ingest_descompuestos", "ingest"),
     ("build-descompuestos", "BuildDescompuestosStep", "build_descompuestos", "build_aux")],
)
def test_f097_r7_sin_la_opcion_no_hay_primera_carga(
    monkeypatch: pytest.MonkeyPatch, comando: str, atributo: str, nombre: str, stage: str
) -> None:
    """Review 2, superviviente S2 (`default=True` en `--sin-tope`): el comando a
    secas llega al paso con `sin_tope=False`, y solo con la opcion con `True`.
    Es lo que impide lanzar sin querer la primera carga de 2,14 GB (1,5-2 h)."""
    from click.testing import CliRunner

    import main
    from tests.test_f024_cli import PgFalso, paso_falso, settings_falsos

    construcciones: list[dict] = []
    monkeypatch.setattr(main, "get_settings", lambda: settings_falsos())
    monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "_get_pg", lambda: PgFalso())
    monkeypatch.setattr(main, atributo, paso_falso(nombre, stage, construcciones=construcciones))

    a_secas = CliRunner().invoke(main.cli, [comando])
    con_opcion = CliRunner().invoke(main.cli, [comando, "--sin-tope"])

    assert a_secas.exit_code == 0 and con_opcion.exit_code == 0, a_secas.output
    assert [c["sin_tope"] for c in construcciones] == [False, True]
