# tests/test_f095_retenciones_contables.py
"""
F-095 · Las retenciones de proveedor desde la CONTABILIDAD, por obra, cuadradas
con los efectos y con vencimiento a contar desde el FIN DE OBRA.

Suite offline (R30): se fija sobre el TEXTO del SQL (comentarios `--` aparte),
el YAML del diccionario, `config/tables_sigrid.yaml` y el cableado del step, al
estilo de `test_f057_personal.py` y `test_f094_retenciones_obra.py`. Las cifras
(49.505 apuntes, 8.760.524,49 EUR, FERMALUX 64.201,96, R5 por cuenta) son
verificacion MANUAL contra la base: aqui no hay red ni BBDD.

Decisiones del humano del 2026-09-22 que estos tests sostienen (H1-H7 de
`specs/F-095-retenciones-contabilidad-fin-obra/design.md`): el vencimiento es
fin de obra + plazo y la fecha de la factura no interviene NUNCA (R23); fin de
obra = inicio de garantia con respaldo en el ultimo cierre con movimiento + 1
mes (H1); plazo = `plaret` -> `plagar` -> 12 (H2); `rac` filtrada (H4).

**F-110 (decision del humano del 2026-09-25) cambia H1**: sin inicio de
garantia, el fin de obra es el ultimo mes planificado de la ultima version
`Cuatrimestral` + 1 mes, y `ultimo_cierre` se queda como columna INFORMATIVA.
Los tests de aqui que fijaban el respaldo por el cierre estan REESCRITOS a la
regla nueva y lo dicen en su docstring (R21 de F-110); la suite propia de la
regla es `tests/test_f110_fin_obra_cuatrimestral.py`.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_RET = DIR_SQL / "retenciones"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
RUTA_PENDIENTES = RAIZ / "config" / "objetos_pendientes.yaml"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

APUNTES = "03_apuntes_contables.sql"
SALDO = "04_saldo_contable.sql"
FIN_OBRA = "05_fin_obra.sql"
VISTAS = "06_views_contables.sql"

FICHEROS_RETENCIONES = [
    "00_setup.sql", "01_movimientos.sql", "02_views.sql",
    APUNTES, SALDO, FIN_OBRA, VISTAS,
]

OBJETOS_NUEVOS = (
    "cuentas_proveedor", "apuntes_contables", "saldo_contable", "fin_obra",
    "v_cuadre_proveedor", "v_retencion_contable_obra",
)


@cache
def _crudo(nombre: str) -> str:
    return (DIR_RET / nombre).read_text(encoding="utf-8")


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    sin_comentarios = "\n".join(
        linea.split("--", 1)[0] for linea in _crudo(nombre).splitlines()
    )
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _bloque(nombre: str, desde: str, hasta: str | None = None) -> str:
    """El trozo del SQL entre dos marcas (la segunda excluida)."""
    texto = _sql(nombre)
    assert desde in texto, f"no encuentro «{desde}» en {nombre}"
    trozo = texto.split(desde, 1)[1]
    if hasta is not None:
        assert hasta in trozo, f"no encuentro «{hasta}» detras de «{desde}» en {nombre}"
        trozo = trozo.split(hasta, 1)[0]
    return trozo


def _cte(nombre: str, cte: str) -> str:
    """El cuerpo de un CTE, con los parentesis equilibrados."""
    texto = _sql(nombre)
    marca = re.search(rf"(?<![\w.]){cte} AS (?:MATERIALIZED )?\(", texto)
    assert marca, f"no encuentro el CTE «{cte}» en {nombre}"
    inicio = marca.end()
    nivel = 1
    for pos in range(inicio, len(texto)):
        if texto[pos] == "(":
            nivel += 1
        elif texto[pos] == ")":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:pos]
    raise AssertionError(f"el CTE «{cte}» de {nombre} no cierra")


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(objeto: str) -> dict:
    return _yaml("retenciones.yaml")["objetos"][objeto]


def _texto_ficha(ficha: dict) -> str:
    return yaml.safe_dump(ficha, allow_unicode=True, width=10_000)


def _tablas() -> dict[str, dict]:
    datos = yaml.safe_load(RUTA_TABLAS.read_text(encoding="utf-8"))
    return {t["target_table"]: t for t in datos["tables"]}


# ===========================================================================
# R1-R2 · las cuentas: por `prv.cueretide`, nunca por prefijo
# ===========================================================================


def test_f095_r1_cuentas_por_cueretide_no_por_prefijo() -> None:
    cuentas = _bloque(APUNTES, "CREATE TABLE retenciones.cuentas_proveedor AS", ";")
    assert "FROM raw.prv prv" in cuentas
    assert cuentas.strip().endswith("WHERE COALESCE(prv.cueretide, 0) <> 0"), (
        "las cuentas de retencion son TODAS las que el proveedor declara, sin "
        "ningun otro filtro (R1, R2)"
    )
    texto = _sql(APUNTES)
    assert not re.search(r"'4\d{2,}", texto), (
        "ningun literal de codigo de cuenta: la lista escrita dejaba fuera 4038 "
        "y 4128 (0,90 M EUR)"
    )
    assert "LIKE '4" not in texto and "cod IN (" not in texto


def test_f095_r2_cuentas_proveedor() -> None:
    cuentas = _bloque(APUNTES, "CREATE TABLE retenciones.cuentas_proveedor AS", ";")
    for fragmento in (
        "prv.ide AS proveedor_id",
        "ent.res AS proveedor_nombre",
        "prv.cueretide AS cuenta_id",
        "cue.cod AS codigo_cuenta",
        "cue.res AS nombre_cuenta",
        "LEFT(cue.cod, 4) AS familia",
        "LEFT JOIN raw.con ent ON ent.ide = prv.ide",
        "LEFT JOIN raw.con cue ON cue.ide = prv.cueretide",
    ):
        assert fragmento in cuentas, f"falta «{fragmento}» (R2)"
    texto = _sql(APUNTES)
    assert "ALTER TABLE retenciones.cuentas_proveedor ADD PRIMARY KEY (proveedor_id)" in texto
    assert re.search(
        r"CREATE UNIQUE INDEX \w+ ON retenciones\.cuentas_proveedor \(cuenta_id\)", texto
    ), "la cuenta es 1:1 con el proveedor: si deja de serlo, el build falla (R8)"


# ===========================================================================
# R3-R8, R10 · los apuntes: uno por fila, con clase y con obra
# ===========================================================================


def test_f095_r3_un_apunte_una_fila() -> None:
    texto = _sql(APUNTES)
    assert "CREATE TABLE retenciones.apuntes_contables AS" in texto
    assert re.search(
        r"FROM raw\.apu a JOIN retenciones\.cuentas_proveedor cp "
        r"ON cp\.cuenta_id = a\.cueide \)",
        texto,
    ), "los apuntes de las cuentas, SIN filtrar ninguno: el CTE acaba en el JOIN (R3)"
    for fragmento in (
        "a.ide AS apunte_id",
        "NULLIF(a.asiide, 0) AS asiento_id",
        "retenciones.fn_sigrid_date(a.fec) AS fecha",
        "a.cueide AS cuenta_id",
        "cp.proveedor_id AS proveedor_id",
        "a.res AS concepto",
        "COALESCE(a.hab, 0)::NUMERIC(18, 2) AS importe_alta",
        "COALESCE(a.deb, 0)::NUMERIC(18, 2) AS importe_baja",
        "(COALESCE(a.hab, 0) - COALESCE(a.deb, 0))::NUMERIC(18, 2) AS importe",
        "NULLIF(a.cenide, 0) AS centro_coste_id",
    ):
        assert fragmento in texto, f"falta «{fragmento}» (R3)"


def test_f095_r4_clase_de_apunte() -> None:
    texto = _sql(APUNTES)
    esperado = (
        "CASE WHEN ap.concepto LIKE 'Asiento de cierre%' THEN 'CIERRE' "
        "WHEN ap.concepto LIKE 'Asiento de apertura%' AND cc.cuenta_id IS NULL "
        "THEN 'SALDO_INICIAL' "
        "WHEN ap.concepto LIKE 'Asiento de apertura%' THEN 'APERTURA' "
        "WHEN ap.importe > 0 THEN 'ALTA' "
        "ELSE 'BAJA' END AS clase"
    )
    assert esperado in texto, "clase de apunte en el orden de R4"
    assert not re.search(r"\.ori\b", texto), "`asi.ori` vale 0 en todos: no se usa (R4)"
    assert "raw.asi " not in texto


def test_f095_r5_saldo_inicial_por_cuenta() -> None:
    """La apertura sin cierre previo DE ESA CUENTA es saldo inicial: por cuenta
    y no por fecha (D4). Excluirla perderia 642.775,50 EUR de 2008."""
    cierres = _cte(APUNTES, "cierres_cuenta")
    assert "SELECT DISTINCT ap.cuenta_id, ap.ejercicio FROM apuntes ap" in cierres
    # «NOT EXISTS un cierre de la misma cuenta el ejercicio anterior», escrito
    # como anti-join: dentro del CASE el NOT EXISTS no se hashea (desviacion de
    # forma justificada en progress/current.md, misma semantica)
    assert (
        "LEFT JOIN cierres_cuenta cc ON cc.cuenta_id = ap.cuenta_id "
        "AND cc.ejercicio = ap.ejercicio - 1"
    ) in _sql(APUNTES)
    assert "WHERE ap.concepto LIKE 'Asiento de cierre%'" in cierres
    assert "EXTRACT(YEAR FROM retenciones.fn_sigrid_date(a.fec))::INT AS ejercicio" in _sql(APUNTES)
    assert "2008" not in _sql(APUNTES), "nada de fechas escritas: la regla es por cuenta"


def test_f095_r6_prescripcion_marca_no_filtra() -> None:
    texto = _sql(APUNTES)
    assert "UPPER(COALESCE(ap.concepto, '')) LIKE '%PRESCRI%' AS es_prescripcion" in texto
    assert texto.count("PRESCRI") == 1, "se marca, no se filtra (R6)"


def test_f095_r7_cascada_de_obra() -> None:
    texto = _sql(APUNTES)
    assert (
        "CASE WHEN cc_apu.obra_id IS NOT NULL THEN 'APUNTE' "
        "WHEN cc_fac.obra_id IS NOT NULL THEN 'FACTURA' "
        "WHEN cc_efe.obra_id IS NOT NULL THEN 'EFECTO' "
        "WHEN cc_prv.obra_id IS NOT NULL THEN 'PROVEEDOR_UNA_OBRA' "
        "ELSE 'SIN_OBRA' END AS via_obra"
    ) in texto, "la cascada de R7, en su orden"
    assert (
        "COALESCE(cc_apu.obra_id, cc_fac.obra_id, cc_efe.obra_id, cc_prv.obra_id) AS obra_id"
    ) in texto
    for union in (
        "LEFT JOIN maestro.centros_coste cc_apu ON cc_apu.centro_coste_id = ap.centro_coste_id",
        "LEFT JOIN rac_asiento ra ON ra.asiento_id = ap.asiento_id",
        "LEFT JOIN efectos_factura ef ON ef.documento_id = ra.documento_id AND ef.num_centros = 1",
        "LEFT JOIN maestro.centros_coste cc_fac ON cc_fac.centro_coste_id = NULLIF(ef.centro_coste_id, 0)",
        "LEFT JOIN raw.pag efe ON efe.ide = ra.documento_id",
        "LEFT JOIN maestro.centros_coste cc_efe ON cc_efe.centro_coste_id = NULLIF(efe.cenide, 0)",
        "LEFT JOIN proveedor_una_obra pu ON pu.proveedor_id = ap.proveedor_id",
        "LEFT JOIN maestro.centros_coste cc_prv ON cc_prv.centro_coste_id = pu.centro_coste_id",
    ):
        assert union in texto, f"falta «{union}» (R7)"
    assert "ra.documento_id AS documento_id" in texto


def test_f095_r7_factura_solo_con_centro_unico() -> None:
    """«Solo si todos tienen el mismo `cenide`» (design): un efecto sin centro
    cuenta como otro valor, asi que la factura no se atribuye a medias."""
    efectos = _cte(APUNTES, "efectos_factura")
    assert "COUNT(DISTINCT COALESCE(p.cenide, 0)) AS num_centros" in efectos
    assert "MIN(COALESCE(p.cenide, 0)) AS centro_coste_id" in efectos
    assert "FROM raw.pag p WHERE COALESCE(p.retide, 0) <> 0" in efectos
    assert "GROUP BY p.conide" in efectos


def test_f095_r7_proveedor_una_obra() -> None:
    """[H3] el proveedor cuyos efectos de retencion caen en un solo centro."""
    bloque = _cte(APUNTES, "proveedor_una_obra")
    assert "FROM raw.pag p WHERE COALESCE(p.retide, 0) <> 0 AND COALESCE(p.cenide, 0) <> 0" in bloque
    assert "GROUP BY p.entide HAVING COUNT(DISTINCT p.cenide) = 1" in bloque


def test_f095_r8_pk_y_sin_multiplicar() -> None:
    texto = _sql(APUNTES)
    assert "ALTER TABLE retenciones.apuntes_contables ADD PRIMARY KEY (apunte_id)" in texto
    for columna in ("proveedor_id", "obra_id", "clase"):
        assert re.search(
            rf"CREATE INDEX \w+ ON retenciones\.apuntes_contables \({columna}\)", texto
        ), f"falta el indice por {columna}"


def test_f095_r8_lateral_o_preagregado() -> None:
    """Cada salto de la cascada une contra algo UNICO por su clave."""
    rac = _cte(APUNTES, "rac_asiento")
    assert "SELECT r.asiide AS asiento_id, MIN(r.conide) AS documento_id FROM raw.rac r" in rac
    assert "GROUP BY r.asiide" in rac
    assert "GROUP BY p.conide" in _cte(APUNTES, "efectos_factura")
    assert "GROUP BY p.entide" in _cte(APUNTES, "proveedor_una_obra")
    # `raw.pag` se une SOLO por su identificador; el resto de saltos, a CTE
    # agregados o a `maestro.centros_coste`, unico por construccion (F-073).
    uniones_pag = re.findall(r"JOIN raw\.pag (\w+) ON ([^ ]+) = ", _sql(APUNTES))
    assert uniones_pag == [("efe", "efe.ide")]


def test_f095_r10_veta_apu_obr_y_cen_obride() -> None:
    texto = _sql(APUNTES)
    assert not re.search(r"\ba\.obr\b", texto), "`apu.obr` no atribuye obra (R10)"
    assert "obride" not in texto, "`cen.obride` esta a 0 en las 804 filas (R10)"
    assert "raw.cen" not in texto and "raw.obr " not in texto
    assert texto.count("JOIN maestro.centros_coste") == 4, "centro -> obra solo por el puente"


# ===========================================================================
# R9 · `rac`, filtrada
# ===========================================================================


def test_f095_r9_rac_declarada_con_filtro() -> None:
    rac = _tablas().get("rac")
    assert rac is not None, "raw.rac no esta declarada en tables_sigrid.yaml (R9)"
    assert rac["source_table"] == "rac"
    assert rac["id_column"] == "ide"
    assert rac["incremental_column"] is None, "`rac` no tiene tiemod"
    assert rac["where"] == "asiide <> 0", "[H4] 755.086 de 2.505.089 filas"
    assert rac["exclude_columns"] == ["tex"]


def test_f095_r9_el_filtro_explica_sus_cifras() -> None:
    texto = RUTA_TABLAS.read_text(encoding="utf-8")
    trozo = texto.split("source_table: rac", 1)[1][:2500]
    for cifra in ("755.086", "2.505.089", "F-091", "97,2", "10,8"):
        assert cifra in trozo, f"el comentario de `rac` no dice «{cifra}»"


# ===========================================================================
# R11-R13 · el saldo contable por proveedor y obra
# ===========================================================================


def test_f095_r11_saldo_sin_cierre_ni_apertura() -> None:
    texto = _sql(SALDO)
    assert "CREATE TABLE retenciones.saldo_contable AS" in texto
    assert "FROM retenciones.apuntes_contables a" in texto
    for fragmento in (
        "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'ALTA'), 0)::NUMERIC(18, 2) AS altas",
        "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'BAJA'), 0)::NUMERIC(18, 2) AS bajas",
        "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'SALDO_INICIAL'), 0)::NUMERIC(18, 2) AS saldo_inicial",
        "COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS saldo",
        "COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('APERTURA', 'SALDO_INICIAL') AND a.ejercicio = 2016), 0)::NUMERIC(18, 2) AS saldo_anterior_2016",
        "MIN(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS primer_movimiento",
        "MAX(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS ultimo_movimiento",
    ):
        assert fragmento in texto, f"falta «{fragmento}» (R11)"
    assert "'CIERRE'" not in texto, "un cierre no suma nunca aqui (R11)"
    assert "WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL') OR (a.clase = 'APERTURA' AND a.ejercicio = 2016)" in texto
    assert (
        "GROUP BY a.proveedor_id, cp.proveedor_nombre, a.obra_id, a.empresa_id, "
        "a.codigo_obra, a.clave_obra, a.nombre_obra"
    ) in texto


def test_f095_r11_clave_con_la_fila_sin_obra() -> None:
    assert re.search(
        r"CREATE UNIQUE INDEX \w+ ON retenciones\.saldo_contable "
        r"\(proveedor_id, obra_id\) NULLS NOT DISTINCT",
        _sql(SALDO),
    ), "la fila sin obra es UNA por proveedor (R11)"


def test_f095_r13_sin_obra_no_se_reparte() -> None:
    texto = _sql(SALDO)
    assert "obra_id IS NOT NULL" not in texto, "la fila sin obra se publica (R13)"
    assert "via_obra" not in texto, "no se reparte por reglas inventadas (D6)"
    ficha = _texto_ficha(_ficha("saldo_contable"))
    assert "SIN_OBRA" in ficha and "sin repartir" in ficha


# ===========================================================================
# R17-R23 · el fin de obra, el plazo y el vencimiento
# ===========================================================================


def test_f095_r17_una_fila_por_obra_de_raw_obr() -> None:
    texto = _sql(FIN_OBRA)
    assert "CREATE TABLE retenciones.fin_obra AS" in texto
    assert "FROM raw.obr obr LEFT JOIN raw.con con ON con.ide = obr.ide" in texto
    assert "ALTER TABLE retenciones.fin_obra ADD PRIMARY KEY (obra_id)" in texto
    assert "con.est AS estado_obra" in texto
    assert "con.emp AS empresa_id" in texto
    assert "con.emp::text || '-' || con.cod AS clave_obra" in texto, (
        "R-CODIGO-POR-EMPRESA: la misma clave legible que maestro.v_obra_fichas"
    )


def test_f095_r17_garantia_obrctr_manda() -> None:
    texto = _sql(FIN_OBRA)
    assert "MAX(NULLIF(c.fecinigar, 0)) AS fec_inicio_garantia" in texto
    assert (
        "COALESCE(retenciones.fn_sigrid_date(oc.fec_inicio_garantia), "
        "retenciones.fn_sigrid_date(obr.garfecini)) AS fecha_inicio_garantia"
    ) in texto, "obrctr manda y obr es el respaldo (H1)"
    assert "FROM raw.obrctr c GROUP BY c.obride" in texto, "obrctr agregada: una fila por obra"


def test_f095_r17_fin_real_igual_que_cierre() -> None:
    """D5: la regla de fin real se REPLICA; si cierre la cambia, esto avisa."""
    def normalizado(texto: str) -> str:
        return (
            texto.replace("stg.fn_sigrid_date_to_date", "FECHA")
            .replace("retenciones.fn_sigrid_date", "FECHA")
        )

    cierre = (DIR_SQL / "cierre" / "05_views_cabecera.sql").read_text(encoding="utf-8")
    cierre = re.sub(r"\s+", " ", "\n".join(linea.split("--", 1)[0] for linea in cierre.splitlines()))
    agregado = "FECHA(MAX(NULLIF(c.fecreafin, 0))) AS fec_real_fin"
    fin_real = "COALESCE( oc.fec_real_fin, FECHA(obr.fecfinrea) ) AS fecha_fin_real"
    assert agregado in normalizado(cierre) and fin_real in normalizado(cierre), (
        "la regla de fin real de cierre cambio: revisa la replica de F-095"
    )
    assert agregado in normalizado(_sql(FIN_OBRA))
    assert fin_real in normalizado(_sql(FIN_OBRA))


def test_f095_r17_informativas_cada_una_en_su_columna() -> None:
    texto = _sql(FIN_OBRA)
    assert "retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0))) AS fec_recepcion_provisional" in texto
    assert "oc.fec_recepcion_provisional AS fecha_recepcion_provisional" in texto
    assert "retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0))) AS fec_prev_fin" in texto
    assert (
        "COALESCE( oc.fec_prev_fin, retenciones.fn_sigrid_date(obr.fecfinpre) ) AS fecha_fin_prevista"
    ) in texto


def test_f095_r18_ultimo_cierre_con_movimiento() -> None:
    """La regla de `ultimo_cierre` no cambia; desde F-110 es solo INFORMATIVA (D5)."""
    bloque = _cte(FIN_OBRA, "cierres")
    assert "SELECT f.obra_id, MAX(f.anio_mes) AS ultimo_cierre" in bloque
    assert "FROM cierre.fact_cierre_mensual f WHERE f.ejecutado_mes <> 0" in bloque, (
        "el ultimo cierre que MOVIO algo, no la ultima fase creada (R18)"
    )
    assert "GROUP BY f.obra_id" in bloque
    assert "stg.fases" not in _sql(FIN_OBRA)


def test_f095_r21_guarda_cierre_vacio() -> None:
    """Reescrito por F-110 (R14): del cierre queda solo la guarda de EXISTENCIA.

    `ultimo_cierre` ya es informativa, asi que una tabla del cierre VACIA no
    tumba el vencimiento; las otras tres guardas son de la version y del plan.
    """
    texto = _sql(FIN_OBRA)
    guarda = _bloque(FIN_OBRA, "DO $$", "END $$;")
    assert "to_regclass('cierre.fact_cierre_mensual') IS NULL" in guarda
    assert "IF NOT EXISTS (SELECT 1 FROM cierre.fact_cierre_mensual)" not in guarda
    assert guarda.count("RAISE EXCEPTION") == 4
    assert guarda.count("RAISE EXCEPTION 'fin_obra: ") == 4, "el fallo lleva el nombre del sub-paso (R21)"
    assert texto.index("DO $$") < texto.index("CREATE TABLE retenciones.fin_obra"), (
        "la guarda va ANTES de publicar nada"
    )


def test_f095_r19_fin_obra_y_fuente() -> None:
    """Reescrito por F-110 (R8, R9): el respaldo es el ultimo cuatrimestral, no el cierre."""
    texto = _sql(FIN_OBRA)
    assert (
        "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia "
        "WHEN b.ultimo_mes_planificado IS NOT NULL THEN "
        "(b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE "
        "END AS fecha_fin_obra"
    ) in texto, "garantia; si no, ultimo dia del mes siguiente al ultimo mes planificado (F-110)"
    assert (
        "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' "
        "WHEN b.ultimo_mes_planificado IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES' "
        "END AS fuente_fin_obra"
    ) in texto
    assert "ULTIMO_CIERRE_MAS_1_MES" not in texto


def test_f095_r19_no_usa_informativas() -> None:
    calculo = _cte(FIN_OBRA, "fin")
    vencimiento = _bloque(FIN_OBRA, "f.fuente_plazo, (", "AS fecha_vencimiento")
    for informativa in ("fecha_fin_real", "fecha_recepcion_provisional", "fecha_fin_prevista"):
        assert informativa not in calculo, (
            f"`{informativa}` es solo informativa: no entra en el fin de obra (R19)"
        )
        assert informativa not in vencimiento


def test_f095_r20_sin_fecha_no_se_inventa() -> None:
    """Reescrito por F-110 (R11): sin garantia ni cuatrimestral con plan, NULL."""
    texto = _sql(FIN_OBRA)
    assert (
        "(f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25)) "
        "AS terminada_sin_fin_obra"
    ) in texto
    assert "ELSE" not in _bloque(FIN_OBRA, "END AS fuente_plazo,", "END AS fecha_fin_obra"), (
        "sin garantia ni cuatrimestral con plan, NULL: no se inventa una fecha (F-110 R11)"
    )


def test_f095_r22_plazo_y_fuente() -> None:
    texto = _sql(FIN_OBRA)
    assert "NULLIF(MAX(c.plaret), 0) AS plazo_retencion" in texto
    assert "NULLIF(MAX(c.plagar), 0) AS plazo_garantia" in texto
    assert (
        "COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT AS plazo_meses"
    ) in texto
    assert (
        "CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE' "
        "WHEN oc.plazo_garantia IS NOT NULL THEN 'PLAZO_GARANTIA_CLIENTE' "
        "ELSE 'PLAZO_FIJO_12' END AS fuente_plazo"
    ) in texto
    assert "garpla" not in texto, "`obr.garpla` no interviene (design)"


def test_f095_r22_doce_en_una_sola_constante() -> None:
    texto = _sql(FIN_OBRA)
    assert "constantes AS ( SELECT 12 AS plazo_fijo_meses )" in texto
    assert len(re.findall(r"(?<![\w.])12(?![\w.])", texto)) == 1, (
        "el 12 vive en UNA constante [H2]"
    )


def test_f095_r23_vencimiento_desde_el_fin_de_obra() -> None:
    assert (
        "(f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE AS fecha_vencimiento"
    ) in _sql(FIN_OBRA)


@pytest.mark.parametrize("nombre", [FIN_OBRA, VISTAS, SALDO])
def test_f095_r23_no_usa_fecha_de_factura(nombre: str) -> None:
    """Decision del humano del 2026-09-22: la fecha de la factura no interviene."""
    texto = _sql(nombre)
    for vetado in ("fecven", "fecha_documento", "fecha_prevista_devolucion", "con.fec ", "doc.fec"):
        assert vetado not in texto, f"`{vetado}` en {nombre}: el vencimiento es fin de obra + plazo (R23)"


# ===========================================================================
# R14-R16, R24 · las vistas
# ===========================================================================


def test_f095_r14_cuadre_no_recalcula_viva() -> None:
    cuadre = _bloque(VISTAS, "CREATE VIEW retenciones.v_cuadre_proveedor AS", ";")
    assert (
        "FROM retenciones.movimientos WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA'"
    ) in cuadre, "el criterio de viva es el de F-094, se lee (R14)"
    for vetado in ("fecrea", "fecbaj", "estado_sigrid", "fecha_baja", "raw."):
        assert vetado not in cuadre, f"`{vetado}`: el cuadre no recalcula el estado (R14)"
    assert not re.search(r"\best\b", cuadre)
    assert "FULL JOIN efectos e ON e.proveedor_id = c.proveedor_id" in cuadre
    assert "FROM retenciones.saldo_contable" in cuadre
    for columna in ("saldo_contable", "viva_efectos", "diferencia", "saldo_anterior_2016", "prescrito", "categoria"):
        assert re.search(rf"AS {columna}\b", cuadre), f"falta la columna {columna}"


def test_f095_r15_categorias_en_orden() -> None:
    cuadre = _bloque(VISTAS, "CREATE VIEW retenciones.v_cuadre_proveedor AS", ";")
    assert (
        "CASE WHEN ABS(x.saldo_contable - x.viva_efectos) < 1 THEN 'CUADRA' "
        "WHEN ABS(x.viva_efectos) < 1 THEN 'SIN_EFECTOS_VIVOS' "
        "WHEN ABS(x.saldo_contable) < 1 THEN 'SIN_SALDO_CONTABLE' "
        "WHEN x.saldo_contable > x.viva_efectos THEN 'CONTABILIDAD_MAYOR' "
        "ELSE 'EFECTOS_MAYOR' END AS categoria"
    ) in cuadre, "las cinco categorias, evaluadas en el orden de R15"
    assert "WHERE ABS(x.saldo_contable) >= 1 OR ABS(x.viva_efectos) >= 1" in cuadre, (
        "el universo del reparto medido en H7: saldo o viva >= 1 EUR"
    )


def test_f095_r15_y_r16_la_ficha_publica_el_reparto_y_fermalux() -> None:
    texto = _texto_ficha(_ficha("v_cuadre_proveedor"))
    for dato in ("520", "5,07", "81", "0,99", "38", "0,20", "41", "0,10", "0,47", "761"):
        assert dato in texto, f"el reparto medido de H7 no trae «{dato}» (R15)"
    assert "FERMALUX" in texto and "64.201,96" in texto and "1958815" in texto, "R16"


def test_f095_r24_estados_de_vencimiento() -> None:
    vista = _bloque(VISTAS, "CREATE VIEW retenciones.v_retencion_contable_obra AS", ";")
    assert (
        "CASE WHEN s.obra_id IS NULL THEN 'SIN_OBRA' "
        "WHEN f.fecha_vencimiento IS NULL THEN 'SIN_FIN_OBRA' "
        "WHEN f.fecha_vencimiento < CURRENT_DATE THEN 'VENCIDA' "
        "ELSE 'PENDIENTE' END AS estado_vencimiento"
    ) in vista
    assert "FROM retenciones.saldo_contable s LEFT JOIN retenciones.fin_obra f ON f.obra_id = s.obra_id" in vista
    assert "WHERE s.saldo <> 0" in vista
    for columna in (
        "fecha_fin_obra", "fuente_fin_obra", "plazo_meses", "fuente_plazo",
        "fecha_vencimiento", "dias_hasta_vencimiento", "saldo",
    ):
        assert re.search(rf"\b{columna}\b", vista), f"falta {columna} (R24)"
    assert "CURRENT_DATE" not in _sql(FIN_OBRA), (
        "la tabla no congela el dia del build: el estado se calcula en la vista"
    )


# ===========================================================================
# R25 · lo de Sigrid se queda como esta
# ===========================================================================


def test_f095_r25_movimientos_intacto() -> None:
    mov = _sql("01_movimientos.sql")
    assert "retenciones.fn_sigrid_date(p.fecven) AS fecha_prevista_devolucion" in mov
    assert "AS vencida_sin_liquidar" in mov
    for nombre in (APUNTES, SALDO, FIN_OBRA, VISTAS):
        texto = _sql(nombre)
        assert "retenciones.movimientos " not in texto.replace(
            "FROM retenciones.movimientos WHERE", ""
        ), f"{nombre} solo LEE movimientos"
        for vetado in ("UPDATE ", "ALTER TABLE retenciones.movimientos", "INSERT INTO"):
            assert vetado not in texto, f"{nombre} escribe en lo de F-094"


def test_f095_r25_la_ficha_dice_de_quien_es_cada_vencimiento() -> None:
    columnas = _ficha("movimientos")["columnas"]
    texto = _texto_ficha(columnas["fecha_prevista_devolucion"])
    assert "15 meses" in texto and "fin de obra" in texto
    assert "v_retencion_contable_obra" in texto


# ===========================================================================
# R26 · cliente fuera
# ===========================================================================


def test_f095_r26_sin_saldo_contable_de_cliente() -> None:
    for nombre in (APUNTES, SALDO, FIN_OBRA, VISTAS):
        texto = _sql(nombre)
        assert "raw.cli" not in texto and "raw.cob" not in texto, f"{nombre}: cliente es F-104 (H5)"
        assert "4308" not in texto
        assert "'CLIENTE'" not in texto


# ===========================================================================
# PROPAGACION · el step, main, grants y los guardianes (R27, D3, D7)
# ===========================================================================


def test_f095_r27_sub_pasos_y_dependencias() -> None:
    from etl_sigrid.application.steps import build_retenciones_step
    from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep

    assert [s.sql_file for s in build_retenciones_step.SUB_PASOS] == FICHEROS_RETENCIONES
    por_nombre = {s.name: s for s in build_retenciones_step.SUB_PASOS}
    assert (por_nombre["apuntes"].target_schema, por_nombre["apuntes"].target_table) == (
        "retenciones", "apuntes_contables")
    assert (por_nombre["saldo"].target_schema, por_nombre["saldo"].target_table) == (
        "retenciones", "saldo_contable")
    assert (por_nombre["fin_obra"].target_schema, por_nombre["fin_obra"].target_table) == (
        "retenciones", "fin_obra")
    assert por_nombre["views_contables"].target_table is None
    for sub in build_retenciones_step.SUB_PASOS:
        assert (DIR_RET / sub.sql_file).exists(), f"{sub.sql_file} declarado y no existe"

    paso = BuildRetencionesStep(SimpleNamespace())
    assert paso.name == "build_retenciones"
    assert paso.stage == "build_retenciones"
    assert paso.depends_on == ["ingest_raw"], "D3 y D7: sin dependencias nuevas"


def test_f095_r27_el_step_encadena_y_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_retenciones_step
    from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return 3

    pg = _PgFalso()
    monkeypatch.setattr(build_retenciones_step, "build_postgres_client", lambda _s: pg)

    resultado = BuildRetencionesStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS_RETENCIONES
    assert pg.contados == [
        ("retenciones", "tipos"), ("retenciones", "movimientos"),
        ("retenciones", "apuntes_contables"), ("retenciones", "saldo_contable"),
        ("retenciones", "fin_obra"),
    ]
    assert resultado.rows_processed == 15


def test_f095_r21_un_fallo_en_fin_obra_sale_con_su_nombre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reescrito por F-110 (R14): el error de ejemplo es una de las guardas nuevas."""
    from etl_sigrid.application.steps import build_retenciones_step
    from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgQueFalla:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)
            if path.name == FIN_OBRA:
                raise RuntimeError(
                    "fin_obra: mart.master_versiones_tipadas no tiene ninguna version Cuatrimestral"
                )

        def count_rows(self, schema: str, table: str) -> int:
            return 1

    pg = _PgQueFalla()
    monkeypatch.setattr(build_retenciones_step, "build_postgres_client", lambda _s: pg)

    resultado = BuildRetencionesStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en fin_obra:")
    assert VISTAS not in pg.ejecutados, "sin fin de obra no se publican las vistas"


def test_f095_r27_main_y_grants_sin_cambios() -> None:
    """main.py, el orquestador y los permisos cubren lo nuevo POR ESQUEMA."""
    import main
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    texto_main = (RAIZ / "main.py").read_text(encoding="utf-8")
    comando = texto_main.split('@cli.command("build-retenciones")', 1)[1][:1500]
    assert "BuildRetencionesStep(settings)" in comando

    ajustes = SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )
    nombres = [p.name for p in main.build_pipeline_steps(ajustes)]
    assert "build_retenciones" in nombres, "run-all construye retenciones"
    assert "retenciones" in DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    assert "raw" in DEFAULT_CONSUMPTION_SCHEMAS.split(","), "raw.rac la lee el MCP (riesgo b)"
    assert "retenciones" in ESQUEMAS_DEL_DATAMART


def test_f095_d3_centros_coste_solo_raw() -> None:
    texto = (DIR_SQL / "maestro" / "04_centros_coste.sql").read_text(encoding="utf-8")
    compacto = re.sub(r"\s+", " ", "\n".join(linea.split("--", 1)[0] for linea in texto.splitlines()))
    lecturas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)\.\w+", compacto))
    assert lecturas == {"raw"}, (
        f"`maestro.centros_coste` lee {sorted(lecturas)}: si deja de ser SQL puro "
        f"sobre raw, `build_retenciones` necesita declarar `build_maestros` (D3)"
    )
    assert "CREATE OR REPLACE VIEW maestro.centros_coste" in compacto, "nunca se dropea"


def test_f095_d7_solo_fact_cierre() -> None:
    """Reescrito por F-110 (D4): ademas de `raw` y el cierre, la version y el plan."""
    texto = _sql(FIN_OBRA)
    de_cierre = set(re.findall(r"(?<![\w])cierre\.(\w+)", texto))
    assert de_cierre == {"fact_cierre_mensual"}, (
        f"de `cierre` solo se lee la tabla de hechos (D7), no {sorted(de_cierre)}"
    )
    assert set(re.findall(r"(?<![\w])mart\.(\w+)", texto)) == {"master_versiones_tipadas"}
    assert set(re.findall(r"(?<![\w])stg\.(\w+)", texto)) == {"plan_mensual"}
    esquemas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)\.\w+", texto))
    assert esquemas == {"raw", "cierre", "mart", "stg"}, f"05_fin_obra.sql lee {sorted(esquemas)}"


def test_f095_d7_apuntes_solo_raw_y_el_puente() -> None:
    esquemas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)\.\w+", _sql(APUNTES)))
    assert esquemas <= {"raw", "retenciones", "maestro"}
    assert set(re.findall(r"maestro\.(\w+)", _sql(APUNTES))) == {"centros_coste"}


@pytest.mark.parametrize("nombre", [APUNTES, SALDO, FIN_OBRA, VISTAS])
def test_f095_r27_ficheros_con_cabecera_y_ruta(nombre: str) -> None:
    primera = _crudo(nombre).splitlines()[0]
    assert primera == f"-- etl_sigrid/infrastructure/postgres/sql/retenciones/{nombre}"


@pytest.mark.parametrize(
    ("nombre", "objetos"),
    [
        (APUNTES, ("cuentas_proveedor", "apuntes_contables")),
        (SALDO, ("saldo_contable",)),
        (FIN_OBRA, ("fin_obra",)),
    ],
)
def test_f095_r27_tablas_idempotentes(nombre: str, objetos: tuple[str, ...]) -> None:
    texto = _sql(nombre)
    for objeto in objetos:
        assert f"DROP TABLE IF EXISTS retenciones.{objeto} CASCADE;" in texto
        assert texto.index(f"DROP TABLE IF EXISTS retenciones.{objeto}") < texto.index(
            f"CREATE TABLE retenciones.{objeto} AS"
        )


def test_f095_r27_vistas_idempotentes() -> None:
    texto = _sql(VISTAS)
    for vista in ("v_cuadre_proveedor", "v_retencion_contable_obra"):
        assert f"DROP VIEW IF EXISTS retenciones.{vista} CASCADE;" in texto
        assert f"CREATE VIEW retenciones.{vista} AS" in texto


# ===========================================================================
# R12, R28-R29, R31 · el diccionario, los guardianes y la documentacion
# ===========================================================================


def test_f095_r12_fuente_que_manda() -> None:
    for objeto in ("movimientos", "v_pbi_retencion_entidad", "v_pbi_retencion_obra",
                   "v_pbi_retenciones_vivas", "v_pbi_retenciones_vencidas",
                   "v_pbi_retencion_resumen"):
        texto = _ficha(objeto)["descripcion"]
        assert "retenciones.saldo_contable" in texto and "contabilidad" in texto, (
            f"la ficha de {objeto} no dice que el saldo vivo lo manda la contabilidad (R12)"
        )
    esquema = _yaml("00_global.yaml")["esquemas"]["retenciones"]["para_que_sirve"]
    assert "retenciones.saldo_contable" in esquema


@pytest.mark.parametrize("objeto", OBJETOS_NUEVOS)
def test_f095_r28_fichas_claves_relaciones(objeto: str) -> None:
    ficha = _ficha(objeto)
    assert ficha["grano"] and ficha["clave_negocio"], f"{objeto} sin grano o sin clave"
    assert ficha["paso_etl"] == "build_retenciones"
    destinos = {r["a"] for r in ficha.get("relaciones", [])}
    columnas = ficha["columnas"]
    if "obra_id" in columnas:
        assert "maestro.obras.obra_id" in destinos, f"{objeto}: obra -> maestro.obras (R28)"
    if "proveedor_id" in columnas:
        assert "maestro.proveedores.proveedor_id" in destinos, f"{objeto}: proveedor -> maestro.proveedores"


def test_f095_r28_claves_de_negocio() -> None:
    claves = {o: _ficha(o)["clave_negocio"] for o in OBJETOS_NUEVOS}
    assert claves == {
        "cuentas_proveedor": ["proveedor_id"],
        "apuntes_contables": ["apunte_id"],
        "saldo_contable": ["proveedor_id", "obra_id"],
        "fin_obra": ["obra_id"],
        "v_cuadre_proveedor": ["proveedor_id"],
        "v_retencion_contable_obra": ["proveedor_id", "obra_id"],
    }
    recomendados = {o for o in OBJETOS_NUEVOS if _ficha(o)["consumo_recomendado"]}
    assert recomendados == {"saldo_contable", "v_cuadre_proveedor", "v_retencion_contable_obra"}


def test_f095_r28_las_fichas_traen_las_cifras_medidas() -> None:
    """Reescrito por F-110 (R19): las cifras de `fin_obra` son las de la regla nueva;
    las de F-095 siguen en la ficha como historicas y con fecha."""
    apuntes = _texto_ficha(_ficha("apuntes_contables"))
    for dato in ("49.505", "APUNTE", "FACTURA", "EFECTO", "PROVEEDOR_UNA_OBRA", "SIN_OBRA",
                 "642.775,50", "SALDO_INICIAL"):
        assert dato in apuntes, f"la ficha de apuntes_contables no dice «{dato}»"
    fin = _texto_ficha(_ficha("fin_obra"))
    for dato in ("20,9", "76,1", "97,0", "132.544,84", "INICIO_GARANTIA",
                 "ULTIMO_CUATRIMESTRAL_MAS_1_MES", "2.960.583,38", "260.028,59",
                 "PLAZO_FIJO_12", "una noche"):
        assert dato in fin, f"la ficha de fin_obra no dice «{dato}»"
    saldo = _texto_ficha(_ficha("saldo_contable"))
    assert "8.760.524,49" in saldo


def test_f095_r28_raw_rac_y_orden_de_magnitud() -> None:
    raw = _yaml("raw.yaml")["objetos"]
    assert "rac" in raw, "falta la ficha de raw.rac"
    texto = raw["rac"]["descripcion"]
    assert "asiide <> 0" in texto and "azure-apps/sigrid_tablas.md" in texto
    assert "`usu`" in texto, "rac.usu es un login y raw es legible por el MCP (riesgo b)"

    glob = _yaml("00_global.yaml")
    assert int(glob["version"]) >= 31
    ordenes = glob["ordenes_de_magnitud"]
    contable = [o for o in ordenes if "retenciones.saldo_contable" in o["concepto"]]
    assert len(contable) == 1, "el orden de magnitud del saldo contable (R28)"
    assert contable[0]["valor_aproximado"] == 8760000
    assert ordenes.index(contable[0]) == 0, "el que manda va el primero"
    assert "34,7 M" not in contable[0]["concepto"]
    assert glob["pendientes"] == []


def test_f095_r29_declarados_y_pendientes() -> None:
    from etl_sigrid.domain.inventario import objetos_de_sql

    textos = {
        f"retenciones/{f.name}": f.read_text(encoding="utf-8")
        for f in sorted(DIR_RET.glob("*.sql"))
    }
    declarados = {(o.esquema, o.objeto) for o in objetos_de_sql(textos)}
    for objeto in OBJETOS_NUEVOS:
        assert ("retenciones", objeto) in declarados, f"check-declarados no ve {objeto}"
    pendientes = yaml.safe_load(RUTA_PENDIENTES.read_text(encoding="utf-8"))
    assert pendientes["pendientes"] == []


def test_f095_r31_arquitectura_y_azure_apps() -> None:
    arquitectura = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("71 tablas", "`rac`", "F-095", "cueretide", "SALDO_INICIAL",
                    "retenciones.saldo_contable", "fin de obra"):
        assert termino in arquitectura, f"ARCHITECTURE.md no dice «{termino}»"
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("71 tablas", "`rac`", "F-095", *(f"retenciones.{o}" for o in OBJETOS_NUEVOS)):
        assert termino in texto, f"azure-apps no dice «{termino}» (R31)"


# ===========================================================================
# EL CONTRATO DEL SQL, EXPRESION A EXPRESION (review de F-095, pasada 1)
# ===========================================================================
#
# El review encontro 11 mutantes vivos (S1-S11): los tests fijaban el ALIAS de
# una columna y no su FORMULA, asi que `SUM(s.altas) AS saldo_contable` pasaba.
# Aqui se fija, para cada SELECT de cada CREATE de `03`-`06` (CTE incluidos, en
# orden de aparicion): si lleva DISTINCT, cada expresion proyectada tal cual y
# cada clausula de su FROM (JOIN con su ON, WHERE, GROUP BY, HAVING). Cambiar
# una formula obliga a cambiar esta tabla, delante del reviewer. Revisada
# contra la spec linea a linea: R1-R8 (03), R11 (04), R17-R23 (05), R14-R15 y
# R24 (06), y R-CODIGO-POR-EMPRESA en las claves de obra. F-110 reescribe la
# entrada de `fin_obra`: CTE `cuatrimestral` y `plan`, sus dos columnas en `base`
# y en la lista final, y el fin de obra por el ultimo mes planificado.

_CLAUSULAS = ("WHERE ", "GROUP BY ", "HAVING ", "LEFT JOIN ", "FULL JOIN ",
              "CROSS JOIN ", "JOIN ", "ORDER BY ")


def _profundidades(texto: str) -> list[int]:
    nivel, prof, cadena = 0, [], False
    for c in texto:
        if c == "'":
            cadena = not cadena
        if not cadena and c == "(":
            prof.append(nivel)
            nivel += 1
        elif not cadena and c == ")":
            nivel -= 1
            prof.append(nivel)
        else:
            prof.append(nivel if not cadena else -1)
    return prof


def _trocear(texto: str, ini: int, fin: int, prof: list[int], nivel: int) -> list[str]:
    trozos, a = [], ini
    for i in range(ini, fin):
        if prof[i] == nivel and texto[i] == ",":
            trozos.append(texto[a:i])
            a = i + 1
    trozos.append(texto[a:fin])
    return [t.strip() for t in trozos if t.strip()]


def _consultas_de(texto: str, ini: int, fin: int) -> list[tuple[bool, list[str], list[str]]]:
    """(DISTINCT, expresiones, clausulas) de cada SELECT del tramo, en orden."""
    prof = _profundidades(texto)
    res = []
    for m in re.finditer(r"(?<![\w.])SELECT ", texto[ini:fin]):
        s = ini + m.start()
        nivel = prof[s]
        q_fin = s
        while q_fin < fin and not (texto[q_fin] == ")" and prof[q_fin] < nivel):
            q_fin += 1
        desde = next((k for k in range(s + 7, q_fin)
                      if prof[k] == nivel and texto.startswith(" FROM ", k)), None)
        lista = s + 7
        distinct = texto.startswith("DISTINCT ", lista)
        if distinct:
            lista += 9
        items = _trocear(texto, lista, desde if desde is not None else q_fin, prof, nivel)
        clausulas: list[str] = []
        if desde is not None:
            marcas = []
            for k in range(desde + 6, q_fin):
                if prof[k] != nivel or texto[k - 1] != " ":
                    continue
                for kw in _CLAUSULAS:
                    if texto.startswith(kw, k) and not (
                        kw == "JOIN " and texto[k - 5:k] in ("LEFT ", "FULL ", "ROSS ")
                    ):
                        marcas.append(k)
                        break
            for i, k in enumerate(marcas):
                hasta = marcas[i + 1] if i + 1 < len(marcas) else q_fin
                clausulas.append(texto[k:hasta].strip())
        res.append((distinct, items, clausulas))
    return res


def _contrato_real(objeto: str) -> list[tuple[bool, list[str], list[str]]]:
    for nombre in (APUNTES, SALDO, FIN_OBRA, VISTAS):
        texto = _sql(nombre)
        m = re.search(rf"CREATE (?:TABLE|VIEW) {re.escape(objeto)} AS ", texto)
        if m:
            return _consultas_de(texto, m.end(), texto.index(";", m.end()))
    raise AssertionError(f"{objeto} no se crea en ningun fichero de F-095")


CONTRATO_SQL: dict[str, list[tuple[bool, list[str], list[str]]]] = {
    'retenciones.cuentas_proveedor': [
        (
            False,
            [
                'prv.ide AS proveedor_id',
                'ent.res AS proveedor_nombre',
                'prv.cueretide AS cuenta_id',
                'cue.cod AS codigo_cuenta',
                'cue.res AS nombre_cuenta',
                'LEFT(cue.cod, 4) AS familia',
            ],
            [
                'LEFT JOIN raw.con ent ON ent.ide = prv.ide',
                'LEFT JOIN raw.con cue ON cue.ide = prv.cueretide',
                'WHERE COALESCE(prv.cueretide, 0) <> 0',
            ],
        ),
    ],
    'retenciones.apuntes_contables': [
        (
            False,
            [
                'a.ide AS apunte_id',
                'NULLIF(a.asiide, 0) AS asiento_id',
                'retenciones.fn_sigrid_date(a.fec) AS fecha',
                'EXTRACT(YEAR FROM retenciones.fn_sigrid_date(a.fec))::INT AS ejercicio',
                'a.cueide AS cuenta_id',
                'cp.codigo_cuenta AS codigo_cuenta',
                'cp.proveedor_id AS proveedor_id',
                'a.res AS concepto',
                'COALESCE(a.hab, 0)::NUMERIC(18, 2) AS importe_alta',
                'COALESCE(a.deb, 0)::NUMERIC(18, 2) AS importe_baja',
                '(COALESCE(a.hab, 0) - COALESCE(a.deb, 0))::NUMERIC(18, 2) AS importe',
                'NULLIF(a.cenide, 0) AS centro_coste_id',
            ],
            [
                'JOIN retenciones.cuentas_proveedor cp ON cp.cuenta_id = a.cueide',
            ],
        ),
        (
            True,
            [
                'ap.cuenta_id',
                'ap.ejercicio',
            ],
            [
                "WHERE ap.concepto LIKE 'Asiento de cierre%'",
            ],
        ),
        (
            False,
            [
                'r.asiide AS asiento_id',
                'MIN(r.conide) AS documento_id',
            ],
            [
                'WHERE r.asiide <> 0 AND r.conide <> 0',
                'GROUP BY r.asiide',
            ],
        ),
        (
            False,
            [
                'p.conide AS documento_id',
                'COUNT(DISTINCT COALESCE(p.cenide, 0)) AS num_centros',
                'MIN(COALESCE(p.cenide, 0)) AS centro_coste_id',
            ],
            [
                'WHERE COALESCE(p.retide, 0) <> 0 AND COALESCE(p.conide, 0) <> 0',
                'GROUP BY p.conide',
            ],
        ),
        (
            False,
            [
                'p.entide AS proveedor_id',
                'MIN(p.cenide) AS centro_coste_id',
            ],
            [
                'WHERE COALESCE(p.retide, 0) <> 0 AND COALESCE(p.cenide, 0) <> 0',
                'GROUP BY p.entide',
                'HAVING COUNT(DISTINCT p.cenide) = 1',
            ],
        ),
        (
            False,
            [
                'ap.apunte_id',
                'ap.asiento_id',
                'ap.fecha',
                'ap.ejercicio',
                'ap.cuenta_id',
                'ap.codigo_cuenta',
                'ap.proveedor_id',
                'ap.concepto',
                'ap.importe_alta',
                'ap.importe_baja',
                'ap.importe',
                "CASE WHEN ap.concepto LIKE 'Asiento de cierre%' THEN 'CIERRE' WHEN ap.concepto LIKE 'Asiento de apertura%' AND cc.cuenta_id IS NULL THEN 'SALDO_INICIAL' WHEN ap.concepto LIKE 'Asiento de apertura%' THEN 'APERTURA' WHEN ap.importe > 0 THEN 'ALTA' ELSE 'BAJA' END AS clase",
                "UPPER(COALESCE(ap.concepto, '')) LIKE '%PRESCRI%' AS es_prescripcion",
                'ap.centro_coste_id',
                'COALESCE(cc_apu.obra_id, cc_fac.obra_id, cc_efe.obra_id, cc_prv.obra_id) AS obra_id',
                "CASE WHEN cc_apu.obra_id IS NOT NULL THEN 'APUNTE' WHEN cc_fac.obra_id IS NOT NULL THEN 'FACTURA' WHEN cc_efe.obra_id IS NOT NULL THEN 'EFECTO' WHEN cc_prv.obra_id IS NOT NULL THEN 'PROVEEDOR_UNA_OBRA' ELSE 'SIN_OBRA' END AS via_obra",
                'ra.documento_id AS documento_id',
            ],
            [
                'LEFT JOIN cierres_cuenta cc ON cc.cuenta_id = ap.cuenta_id AND cc.ejercicio = ap.ejercicio - 1',
                'LEFT JOIN maestro.centros_coste cc_apu ON cc_apu.centro_coste_id = ap.centro_coste_id',
                'LEFT JOIN rac_asiento ra ON ra.asiento_id = ap.asiento_id',
                'LEFT JOIN efectos_factura ef ON ef.documento_id = ra.documento_id AND ef.num_centros = 1',
                'LEFT JOIN maestro.centros_coste cc_fac ON cc_fac.centro_coste_id = NULLIF(ef.centro_coste_id, 0)',
                'LEFT JOIN raw.pag efe ON efe.ide = ra.documento_id',
                'LEFT JOIN maestro.centros_coste cc_efe ON cc_efe.centro_coste_id = NULLIF(efe.cenide, 0)',
                'LEFT JOIN proveedor_una_obra pu ON pu.proveedor_id = ap.proveedor_id',
                'LEFT JOIN maestro.centros_coste cc_prv ON cc_prv.centro_coste_id = pu.centro_coste_id',
            ],
        ),
        (
            False,
            [
                'r.apunte_id',
                'r.asiento_id',
                'r.fecha',
                'r.ejercicio',
                'r.cuenta_id',
                'r.codigo_cuenta',
                'r.proveedor_id',
                'r.concepto',
                'r.importe_alta',
                'r.importe_baja',
                'r.importe',
                'r.clase',
                'r.es_prescripcion',
                'r.centro_coste_id',
                'r.obra_id',
                'ob.emp AS empresa_id',
                'ob.cod AS codigo_obra',
                "ob.emp::text || '-' || ob.cod AS clave_obra",
                'ob.res AS nombre_obra',
                'r.via_obra',
                'r.documento_id',
            ],
            [
                'LEFT JOIN raw.con ob ON ob.ide = r.obra_id',
            ],
        ),
    ],
    'retenciones.saldo_contable': [
        (
            False,
            [
                'a.proveedor_id',
                'cp.proveedor_nombre',
                'a.obra_id',
                'a.empresa_id',
                'a.codigo_obra',
                'a.clave_obra',
                'a.nombre_obra',
                "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'ALTA'), 0)::NUMERIC(18, 2) AS altas",
                "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'BAJA'), 0)::NUMERIC(18, 2) AS bajas",
                "COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'SALDO_INICIAL'), 0)::NUMERIC(18, 2) AS saldo_inicial",
                "COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)::NUMERIC(18, 2) AS saldo",
                "COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('APERTURA', 'SALDO_INICIAL') AND a.ejercicio = 2016), 0)::NUMERIC(18, 2) AS saldo_anterior_2016",
                "COUNT(*) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS num_apuntes",
                "MIN(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS primer_movimiento",
                "MAX(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS ultimo_movimiento",
            ],
            [
                'JOIN retenciones.cuentas_proveedor cp ON cp.proveedor_id = a.proveedor_id',
                "WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL') OR (a.clase = 'APERTURA' AND a.ejercicio = 2016)",
                'GROUP BY a.proveedor_id, cp.proveedor_nombre, a.obra_id, a.empresa_id, a.codigo_obra, a.clave_obra, a.nombre_obra',
            ],
        ),
    ],
    'retenciones.fin_obra': [
        (
            False,
            [
                '12 AS plazo_fijo_meses',
            ],
            [
            ],
        ),
        (
            False,
            [
                'c.obride AS obra_id',
                'MAX(NULLIF(c.fecinigar, 0)) AS fec_inicio_garantia',
                'retenciones.fn_sigrid_date(MAX(NULLIF(c.fecreafin, 0))) AS fec_real_fin',
                'retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0))) AS fec_recepcion_provisional',
                'retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0))) AS fec_prev_fin',
                'NULLIF(MAX(c.plaret), 0) AS plazo_retencion',
                'NULLIF(MAX(c.plagar), 0) AS plazo_garantia',
                'COUNT(*) AS num_contratos_obra',
            ],
            [
                'GROUP BY c.obride',
            ],
        ),
        (
            False,
            [
                'f.obra_id',
                'MAX(f.anio_mes) AS ultimo_cierre',
            ],
            [
                'WHERE f.ejecutado_mes <> 0',
                'GROUP BY f.obra_id',
            ],
        ),
        (
            False,
            [
                'v.obra_id',
                'MAX(v.version) AS version_cuatrimestral',
            ],
            [
                "WHERE v.tipo_master = 'Cuatrimestral'",
                'GROUP BY v.obra_id',
            ],
        ),
        (
            False,
            [
                'c.obra_id',
                'c.version_cuatrimestral',
                'MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ultimo_mes_planificado',
            ],
            [
                'LEFT JOIN stg.plan_mensual pm ON pm.obra_id = c.obra_id AND pm.version = c.version_cuatrimestral AND pm.ambito_id IN (8, 11)',
                'GROUP BY c.obra_id, c.version_cuatrimestral',
            ],
        ),
        (
            False,
            [
                'obr.ide AS obra_id',
                'con.emp AS empresa_id',
                'con.cod AS codigo_obra',
                "con.emp::text || '-' || con.cod AS clave_obra",
                'con.res AS nombre_obra',
                'con.est AS estado_obra',
                'COALESCE(retenciones.fn_sigrid_date(oc.fec_inicio_garantia), retenciones.fn_sigrid_date(obr.garfecini)) AS fecha_inicio_garantia',
                'ci.ultimo_cierre AS ultimo_cierre',
                'pl.version_cuatrimestral AS version_cuatrimestral',
                'pl.ultimo_mes_planificado AS ultimo_mes_planificado',
                'COALESCE( oc.fec_real_fin, retenciones.fn_sigrid_date(obr.fecfinrea) ) AS fecha_fin_real',
                'oc.fec_recepcion_provisional AS fecha_recepcion_provisional',
                'COALESCE( oc.fec_prev_fin, retenciones.fn_sigrid_date(obr.fecfinpre) ) AS fecha_fin_prevista',
                'COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT AS plazo_meses',
                "CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE' WHEN oc.plazo_garantia IS NOT NULL THEN 'PLAZO_GARANTIA_CLIENTE' ELSE 'PLAZO_FIJO_12' END AS fuente_plazo",
                'COALESCE(oc.num_contratos_obra, 0) AS num_contratos_obra',
            ],
            [
                'LEFT JOIN raw.con con ON con.ide = obr.ide',
                'LEFT JOIN oc ON oc.obra_id = obr.ide',
                'LEFT JOIN cierres ci ON ci.obra_id = obr.ide',
                'LEFT JOIN plan pl ON pl.obra_id = obr.ide',
                'CROSS JOIN constantes k',
            ],
        ),
        (
            False,
            [
                'b.*',
                "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia WHEN b.ultimo_mes_planificado IS NOT NULL THEN (b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE END AS fecha_fin_obra",
                "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' WHEN b.ultimo_mes_planificado IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES' END AS fuente_fin_obra",
            ],
            [
            ],
        ),
        (
            False,
            [
                'f.obra_id',
                'f.empresa_id',
                'f.codigo_obra',
                'f.clave_obra',
                'f.nombre_obra',
                'f.estado_obra',
                'f.fecha_inicio_garantia',
                'f.ultimo_cierre',
                'f.version_cuatrimestral',
                'f.ultimo_mes_planificado',
                'f.fecha_fin_real',
                'f.fecha_recepcion_provisional',
                'f.fecha_fin_prevista',
                'f.fecha_fin_obra',
                'f.fuente_fin_obra',
                '(f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25)) AS terminada_sin_fin_obra',
                'f.plazo_meses',
                'f.fuente_plazo',
                '(f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE AS fecha_vencimiento',
                'f.num_contratos_obra',
            ],
            [
            ],
        ),
    ],
    'retenciones.v_cuadre_proveedor': [
        (
            False,
            [
                's.proveedor_id',
                'MAX(s.proveedor_nombre) AS proveedor_nombre',
                'SUM(s.saldo) AS saldo_contable',
                'SUM(s.saldo_anterior_2016) AS saldo_anterior_2016',
            ],
            [
                'GROUP BY s.proveedor_id',
            ],
        ),
        (
            False,
            [
                'a.proveedor_id',
                '-SUM(a.importe) AS prescrito',
            ],
            [
                "WHERE a.es_prescripcion AND a.clase IN ('ALTA', 'BAJA')",
                'GROUP BY a.proveedor_id',
            ],
        ),
        (
            False,
            [
                'entidad_id AS proveedor_id',
                'MAX(entidad_nombre) AS proveedor_nombre',
                'SUM(importe) AS viva_efectos',
            ],
            [
                "WHERE sentido = 'PROVEEDOR' AND estado = 'VIVA' AND entidad_id IS NOT NULL",
                'GROUP BY entidad_id',
            ],
        ),
        (
            False,
            [
                'COALESCE(c.proveedor_id, e.proveedor_id) AS proveedor_id',
                'COALESCE(c.proveedor_nombre, e.proveedor_nombre) AS proveedor_nombre',
                'COALESCE(c.saldo_contable, 0)::NUMERIC(18, 2) AS saldo_contable',
                'COALESCE(e.viva_efectos, 0)::NUMERIC(18, 2) AS viva_efectos',
                'COALESCE(c.saldo_anterior_2016, 0)::NUMERIC(18, 2) AS saldo_anterior_2016',
            ],
            [
                'FULL JOIN efectos e ON e.proveedor_id = c.proveedor_id',
            ],
        ),
        (
            False,
            [
                'x.proveedor_id',
                'x.proveedor_nombre',
                'x.saldo_contable',
                'x.viva_efectos',
                '(x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2) AS diferencia',
                "CASE WHEN ABS(x.saldo_contable - x.viva_efectos) < 1 THEN 'CUADRA' WHEN ABS(x.viva_efectos) < 1 THEN 'SIN_EFECTOS_VIVOS' WHEN ABS(x.saldo_contable) < 1 THEN 'SIN_SALDO_CONTABLE' WHEN x.saldo_contable > x.viva_efectos THEN 'CONTABILIDAD_MAYOR' ELSE 'EFECTOS_MAYOR' END AS categoria",
                'x.saldo_anterior_2016',
                'COALESCE(p.prescrito, 0)::NUMERIC(18, 2) AS prescrito',
            ],
            [
                'LEFT JOIN prescripciones p ON p.proveedor_id = x.proveedor_id',
                'WHERE ABS(x.saldo_contable) >= 1 OR ABS(x.viva_efectos) >= 1',
            ],
        ),
    ],
    'retenciones.v_retencion_contable_obra': [
        (
            False,
            [
                's.proveedor_id',
                's.proveedor_nombre',
                's.obra_id',
                's.empresa_id',
                's.codigo_obra',
                's.clave_obra',
                's.nombre_obra',
                's.saldo',
                's.ultimo_movimiento',
                'f.fecha_fin_obra',
                'f.fuente_fin_obra',
                'f.plazo_meses',
                'f.fuente_plazo',
                'f.fecha_vencimiento',
                "CASE WHEN s.obra_id IS NULL THEN 'SIN_OBRA' WHEN f.fecha_vencimiento IS NULL THEN 'SIN_FIN_OBRA' WHEN f.fecha_vencimiento < CURRENT_DATE THEN 'VENCIDA' ELSE 'PENDIENTE' END AS estado_vencimiento",
                '(f.fecha_vencimiento - CURRENT_DATE) AS dias_hasta_vencimiento',
                'f.terminada_sin_fin_obra',
            ],
            [
                'LEFT JOIN retenciones.fin_obra f ON f.obra_id = s.obra_id',
                'WHERE s.saldo <> 0',
            ],
        ),
    ],
}


@pytest.mark.parametrize("objeto", sorted(CONTRATO_SQL))
def test_f095_contrato_expresion_a_expresion(objeto: str) -> None:
    real = _contrato_real(objeto)
    esperado = CONTRATO_SQL[objeto]
    assert len(real) == len(esperado), f"{objeto}: cambio el numero de SELECT (CTE)"
    for n, ((d_r, i_r, c_r), (d_e, i_e, c_e)) in enumerate(zip(real, esperado, strict=True), 1):
        assert d_r == d_e, f"{objeto}, SELECT {n}: cambio el DISTINCT"
        assert i_r == i_e, f"{objeto}, SELECT {n}: cambio una expresion proyectada"
        assert c_r == c_e, f"{objeto}, SELECT {n}: cambio un JOIN, WHERE, GROUP BY o HAVING"


def test_f095_contrato_control_el_parser_ve_lo_que_debe() -> None:
    """Si el parser dejara de ver expresiones, el contrato pasaria en vacio."""
    total = sum(len(i) for q in CONTRATO_SQL.values() for _, i, _ in q)
    clausulas = sum(len(c) for q in CONTRATO_SQL.values() for _, _, c in q)
    assert total >= 150 and clausulas >= 35
    x = _contrato_real("retenciones.v_cuadre_proveedor")
    assert "SUM(s.saldo) AS saldo_contable" in x[0][1]
    assert "(x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2) AS diferencia" in x[4][1]
