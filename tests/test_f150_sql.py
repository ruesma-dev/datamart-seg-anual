# tests/test_f150_sql.py
"""
F-150 · El SQL de la receta en `sql/tesoreria/` (R8, R10-R14, R18-R21, R23, R27).

Se lee el SQL como texto: ni red ni BBDD. El SQL no llama al dominio, pero
lleva sus mismos literales (patrón de F-135 y F-140) y aquí se comparan: la
gramática de `coestr`, las fuentes del coeficiente, los ámbitos 9 y 11, el
redondeo a 6, el orden del `COALESCE`, el suelo 0 del hueco y el motivo de H12.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom

RAIZ = Path(__file__).resolve().parents[1]
DIR_TESORERIA = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
RUTA_SETUP = DIR_TESORERIA / "00_setup.sql"
RUTA_CLIENTE = DIR_TESORERIA / "06_condiciones_contrato_cliente.sql"
RUTA_DEVENGO = DIR_TESORERIA / "07_devengo_pendiente.sql"
RUTA_HIPOTESIS_OBRA = DIR_TESORERIA / "08_hipotesis_caja_obra.sql"

#: Las columnas que F-150 añade a cada tabla, en su orden (design.md §5, R8-R23).
COLUMNAS_NUEVAS: dict[str, tuple[str, ...]] = {
    "tesoreria.condiciones_contrato_cliente": (
        "coeficientes_texto", "coeficientes_reconocidos", "coeficiente_gg", "coeficiente_bi",
        "coeficiente_otros", "coeficiente_baja", "retencion_coestr", "coeficiente_contrato",
        "iva_id", "iva_porcentaje",
    ),
    "tesoreria.devengo_pendiente_partida": (
        "contrato_cliente_id", "coeficiente_venta", "fuente_coeficiente", "coeficiente_master",
        "pendiente_con_coeficientes", "iva_porcentaje", "fuente_iva", "retencion_porcentaje",
        "fuente_retencion",
    ),
    "tesoreria.devengo_pendiente_obra_mes": (
        "importe_pendiente_con_coeficientes", "coeficiente_venta", "importe_iva_contrato",
        "base_sin_iva_contrato", "importe_retencion_contrato", "base_sin_retencion_contrato",
    ),
    "tesoreria.devengo_corte_obra": (
        "venta_real_origen_con_coeficientes", "venta_real_media_obra", "facturado_origen",
        "venta_pendiente_facturar", "facturado_por_delante", "iva_pendiente_facturar_contrato",
        "base_pendiente_facturar_sin_iva_contrato", "retencion_pendiente_facturar_contrato",
        "base_pendiente_facturar_sin_retencion_contrato",
        # N12 (29-10): la parte de coste proporcional de la cartera, solo en COSTE.
        "cartera_viva_coste_proporcional", "cartera_emitida_tras_cierre_coste_proporcional",
    ),
    "tesoreria.hipotesis_caja": ("paso_receta",),
}


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return "\n".join(lineas)


def _ejecutable(ruta: Path) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(_sql(ruta)))


def _sin_comment_on(ruta: Path) -> str:
    return re.sub(r"COMMENT ON .*?';", "", _ejecutable(ruta))


def _cuerpo_funcion(nombre: str) -> str:
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(nombre)}\(.*?\$\$(.*?)\$\$;",
        _sql(RUTA_SETUP), re.S,
    )
    assert m, f"no encuentro {nombre}"
    return re.sub(r"\s+", " ", m.group(1))


def _alters(tabla: str) -> list[str]:
    return re.findall(
        rf"ALTER TABLE {re.escape(tabla)} ADD COLUMN IF NOT EXISTS (\w+) ", _ejecutable(RUTA_SETUP)
    )


# ===========================================================================
# setup · las funciones de `coestr` (R8): literales = dominio
# ===========================================================================

FUNCIONES = ("tesoreria.fn_coeficientes", "tesoreria.fn_coeficientes_reconocidos")


def test_f150_setup_las_firmas_de_las_funciones() -> None:
    texto = _ejecutable(RUTA_SETUP)
    assert ("CREATE OR REPLACE FUNCTION tesoreria.fn_coeficientes(f TEXT) RETURNS NUMERIC[] "
            "LANGUAGE sql IMMUTABLE") in texto
    assert ("CREATE OR REPLACE FUNCTION tesoreria.fn_coeficientes_reconocidos(f TEXT) "
            "RETURNS BOOLEAN LANGUAGE sql IMMUTABLE") in texto


@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f150_setup_cada_funcion_tiene_comment_con_f150(funcion: str) -> None:
    m = re.search(rf"COMMENT ON FUNCTION {re.escape(funcion)}\(TEXT\) IS '(.*?)';",
                  _ejecutable(RUTA_SETUP))
    assert m, f"{funcion} sin COMMENT"
    assert m.group(1).startswith("F-150.")


def test_f150_r8_setup_fn_coeficientes_parte_por_lineas_y_campos_del_dominio() -> None:
    cuerpo = _cuerpo_funcion("tesoreria.fn_coeficientes")
    assert f"regexp_split_to_array(f, '{dom.SEPARADOR_LINEAS}')" in cuerpo
    assert f"split_part(l.t, '{dom.SEPARADOR_CAMPOS}', 1) AS codigo" in cuerpo
    assert f"btrim(split_part(l.t, '{dom.SEPARADOR_CAMPOS}', 3)) AS valor" in cuerpo
    assert "WHERE btrim(u.t0) <> ''" in cuerpo, "las líneas vacías se ignoran"
    assert f"WHEN valor ~ '{dom.REGEX_PORCENTAJE_COEF}' THEN valor::NUMERIC" in cuerpo


def test_f150_r8_setup_fn_coeficientes_clasifica_con_la_tabla_del_dominio() -> None:
    cuerpo = _cuerpo_funcion("tesoreria.fn_coeficientes")
    pares = dict(re.findall(r"WHEN '(\w+)' THEN '(\w+)'", cuerpo))
    assert pares == dom.CLASE_POR_CODIGO


def test_f150_r8_setup_fn_coeficientes_falla_cerrado_y_suma_por_clase() -> None:
    cuerpo = _cuerpo_funcion("tesoreria.fn_coeficientes")
    assert "WHEN count(*) > 0 AND count(*) = count(clase) AND count(*) = count(v)" in cuerpo
    clases = re.findall(r"sum\(v\) FILTER \(WHERE clase = '(\w+)'\)", cuerpo)
    assert tuple(clases) == dom.CoeficientesContrato._fields[:5], "{gg, bi, otros, baja, retencion}"


def test_f150_r8_setup_reconocidos_es_no_nulo() -> None:
    cuerpo = _cuerpo_funcion("tesoreria.fn_coeficientes_reconocidos")
    assert cuerpo.strip() == "SELECT tesoreria.fn_coeficientes(f) IS NOT NULL;"


# ===========================================================================
# setup · las columnas nuevas, con ALTER idempotente (R8, R11, R14, R19, R20, R23)
# ===========================================================================


@pytest.mark.parametrize("tabla", list(COLUMNAS_NUEVAS))
def test_f150_setup_las_columnas_nuevas_van_con_alter_y_en_orden(tabla: str) -> None:
    assert tuple(_alters(tabla)) == COLUMNAS_NUEVAS[tabla]


def test_f150_setup_sin_drop_ni_grant() -> None:
    texto = _ejecutable(RUTA_SETUP).upper()
    assert "DROP " not in texto
    assert "GRANT " not in texto and "REVOKE " not in texto


def test_f150_setup_los_alter_no_llevan_not_null() -> None:
    """Las tablas tienen filas en Azure: un `ADD COLUMN ... NOT NULL` sin defecto falla."""
    for linea in re.findall(r"ALTER TABLE [^;]*ADD COLUMN[^;]*;", _ejecutable(RUTA_SETUP)):
        assert "NOT NULL" not in linea, linea


# ===========================================================================
# R13 · ninguna columna nueva es de caja
# ===========================================================================


@pytest.mark.parametrize("columna", sorted({c for cs in COLUMNAS_NUEVAS.values() for c in cs}))
def test_f150_r13_ninguna_columna_nueva_es_de_caja(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna), columna


# ===========================================================================
# R27 · la unidad admite PERFIL_MESES
# ===========================================================================


def test_f150_r27_unidad_ensanchada_en_create_y_en_alter() -> None:
    texto = _ejecutable(RUTA_SETUP)
    assert "unidad VARCHAR(20) NOT NULL" in texto
    assert "ALTER TABLE tesoreria.hipotesis_caja ALTER COLUMN unidad TYPE VARCHAR(20);" in texto
    assert max(len(u) for u in dom.UNIDADES) <= 20


# ===========================================================================
# 06 · los coeficientes y el IVA del contrato con el cliente (R8, R18)
# ===========================================================================


def _insert(ruta: Path, tabla: str) -> tuple[list[str], str]:
    compacto = _sin_comment_on(ruta)
    m = re.search(rf"INSERT INTO {re.escape(tabla)} \((.*?)\) (SELECT .*?);", compacto)
    assert m, f"falta el INSERT de {tabla}"
    return [c.strip() for c in m.group(1).split(",")], m.group(2)


def test_f150_r8_06_publica_coestr_tal_cual_y_lo_lee_una_vez() -> None:
    columnas, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert columnas[-10:] == list(COLUMNAS_NUEVAS["tesoreria.condiciones_contrato_cliente"])
    # vacío en Sigrid = NULL publicado: es lo que dice su `nulo_significa` (guardián de F-006)
    assert "NULLIF(o.coestr, '') AS coeficientes_texto" in select
    assert "tesoreria.fn_coeficientes_reconocidos(o.coestr) AS coeficientes_reconocidos" in select
    assert "CROSS JOIN LATERAL (SELECT tesoreria.fn_coeficientes(o.coestr) AS c) AS k" in select
    assert select.count("tesoreria.fn_coeficientes(") == 1, "una sola lectura por contrato"


def test_f150_r8_06_cada_clase_en_su_posicion_del_array() -> None:
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    for n, columna in enumerate(("coeficiente_gg", "coeficiente_bi", "coeficiente_otros",
                                 "coeficiente_baja", "retencion_coestr"), start=1):
        assert f"k.c[{n}] AS {columna}" in select, columna


def test_f150_r8_06_el_factor_es_el_del_dominio_en_cascada() -> None:
    """Mismo cálculo que `factor_coeficientes`: GG+BI+otros sumados, la baja en cascada, a 6."""
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert (
        "CASE WHEN k.c[1] IS NOT NULL OR k.c[2] IS NOT NULL OR k.c[3] IS NOT NULL "
        "OR k.c[4] IS NOT NULL THEN ROUND((1 + (COALESCE(k.c[1], 0) + COALESCE(k.c[2], 0) "
        "+ COALESCE(k.c[3], 0)) / 100) * (1 + COALESCE(k.c[4], 0) / 100), 6) "
        "END AS coeficiente_contrato"
    ) in select
    assert "k.c[5]) / 100" not in select and "COALESCE(k.c[5]" not in select, (
        "la retención no entra en el factor"
    )


def test_f150_r18_06_el_iva_del_catalogo_en_tanto_por_cien() -> None:
    _cols, select = _insert(RUTA_CLIENTE, "tesoreria.condiciones_contrato_cliente")
    assert "NULLIF(o.ivaide, 0) AS iva_id" in select
    assert "ROUND((i.iva * 100)::NUMERIC, 4) AS iva_porcentaje" in select
    assert select.endswith("LEFT JOIN raw.iva i ON i.ide = NULLIF(o.ivaide, 0)")


def test_f150_r8_06_el_comment_dice_coeficientes_e_iva() -> None:
    m = re.search(r"COMMENT ON TABLE tesoreria\.condiciones_contrato_cliente IS '(.*?)';",
                  _ejecutable(RUTA_CLIENTE))
    assert m
    for trozo in ("F-150", "coestr", "coeficiente_contrato", "cascada", "IVA", "raw.iva"):
        assert trozo in m.group(1), trozo


def test_f150_r8_06_lee_raw_iva() -> None:
    assert "-- Lee de: raw.obrctr, raw.con, raw.auxcob, raw.auxefc, raw.rec, raw.iva." in _sql(
        RUTA_CLIENTE
    )


# ===========================================================================
# 07 · el coeficiente, el IVA y la retención de cada partida (R10-R14, R19, R20)
# ===========================================================================


def _devengo() -> str:
    return _sin_comment_on(RUTA_DEVENGO)


def _sin_to_regclass(texto: str) -> str:
    return re.sub(r"to_regclass\('[^']*'\)", "", texto)


def test_f150_r10_stg_presupuesto_solo_con_obra_ambitos_9_y_11_y_version() -> None:
    texto = _sin_to_regclass(_devengo())
    assert re.findall(r"\bstg\.\w+", texto) == ["stg.plan_mensual", "stg.presupuesto"]
    ambitos = ", ".join(str(a) for a in dom.AMBITO_COEFICIENTE.values())
    assert (
        "JOIN stg.presupuesto pp ON pp.obra_id = v.obra_id "
        f"AND pp.ambito_id IN ({ambitos}) AND pp.fase_num = v.version_master "
        "WHERE v.concepto = 'VENTA'"
    ) in texto


@pytest.mark.parametrize("ruta", sorted(DIR_TESORERIA.glob("*.sql")), ids=lambda r: r.name)
def test_f150_r10_ninguna_lectura_de_presupuesto_sin_sus_tres_filtros(ruta: Path) -> None:
    texto = _sin_to_regclass(_sin_comment_on(ruta))
    lecturas = re.findall(r"stg\.presupuesto (\w+) ON (.*?)(?= WHERE | GROUP BY |;)", texto)
    assert texto.count("stg.presupuesto") == len(lecturas), ruta.name
    for alias, condicion in lecturas:
        assert f"{alias}.obra_id = " in condicion
        assert f"{alias}.ambito_id IN (9, 11)" in condicion
        assert f"{alias}.fase_num = " in condicion


def test_f150_r9_el_coeficiente_del_master_como_el_dominio() -> None:
    """`_coeficiente_master`: ROUND(oficial / importe, 6), oficial ausente = importe, sin 0."""
    texto = _devengo()
    for fuente, ambito in dom.AMBITO_COEFICIENTE.items():
        sufijo = "cert" if fuente == "MASTER_CERT" else "venta"
        assert (f"SUM(pp.importe) FILTER (WHERE pp.ambito_id = {ambito}) AS importe_{sufijo}"
                in texto)
        assert (f"SUM(pp.importe_oficial) FILTER (WHERE pp.ambito_id = {ambito}) "
                f"AS oficial_{sufijo}") in texto
    assert (
        "CASE WHEN m.importe_cert <> 0 THEN ROUND(COALESCE(m.oficial_cert, m.importe_cert) "
        "/ m.importe_cert, 6) WHEN m.importe_venta <> 0 THEN ROUND(COALESCE(m.oficial_venta, "
        "m.importe_venta) / m.importe_venta, 6) END AS coeficiente_master"
    ) in texto
    assert (
        "CASE WHEN m.importe_cert <> 0 THEN 'MASTER_CERT' WHEN m.importe_venta <> 0 "
        "THEN 'MASTER_VENTA' END AS fuente_master"
    ) in texto


def test_f150_r9_manda_el_contrato_y_el_orden_del_coalesce_es_el_del_dominio() -> None:
    texto = _devengo()
    assert ("COALESCE(k.coeficiente_contrato, m.coeficiente_master) AS coeficiente_venta"
            in texto)
    assert (
        "CASE WHEN k.coeficiente_contrato IS NOT NULL THEN 'CONTRATO' "
        "WHEN m.coeficiente_master IS NOT NULL THEN m.fuente_master ELSE 'SIN' END "
        "AS fuente_coeficiente"
    ) in texto
    literales = set(re.findall(r"'(CONTRATO|MASTER_CERT|MASTER_VENTA|SIN)'", texto))
    assert literales == set(dom.FUENTES_COEFICIENTE)


def test_f150_r11_el_contrato_solo_si_es_de_la_misma_obra() -> None:
    texto = _devengo()
    assert "LEFT JOIN raw.obrparpar op ON op.ide = pv.partida_id" in texto
    assert (
        "LEFT JOIN tesoreria.condiciones_contrato_cliente k "
        "ON k.contrato_cliente_id = NULLIF(op.ctride, 0) AND k.obra_id = pv.obra_id"
    ) in texto


def test_f150_r11_r19_las_columnas_de_la_partida_solo_en_venta() -> None:
    texto = _devengo()
    assert (
        "LEFT JOIN _dev_contrato c ON c.obra_id = d.obra_id AND c.partida_id = d.partida_id "
        "AND d.concepto = 'VENTA'"
    ) in texto
    assert ("ROUND(GREATEST(0, d.plan_desde_version - d.ejecutado_intervalo) "
            "* c.coeficiente_venta, 2) AS pendiente_con_coeficientes") in texto
    columnas, _select = _insert(RUTA_DEVENGO, "tesoreria.devengo_pendiente_partida")
    assert columnas[-9:] == list(COLUMNAS_NUEVAS["tesoreria.devengo_pendiente_partida"])


def test_f150_r19_fuente_del_iva_y_de_la_retencion() -> None:
    texto = _devengo()
    assert ("CASE WHEN k.iva_porcentaje IS NOT NULL THEN 'CONTRATO' ELSE 'SIN' END "
            "AS fuente_iva") in texto
    assert ("CASE WHEN k.retencion_porcentaje IS NOT NULL THEN 'CONTRATO' ELSE 'SIN' END "
            "AS fuente_retencion") in texto
    assert dom.FUENTES_DATO_CONTRATO == ("CONTRATO", "SIN")


def test_f150_r12_la_guarda_de_d6_antes_de_vaciar() -> None:
    texto = _devengo()
    i_guarda = texto.index("partidas de venta con pendiente y sin coeficiente")
    assert i_guarda < texto.index("TRUNCATE"), "falla antes de vaciar nada"
    guarda = texto[texto.rindex("DO $$", 0, i_guarda):texto.index("END $$;", i_guarda)]
    assert ("WHERE d.concepto = 'VENTA' AND d.pendiente > 0 AND d.coeficiente_venta IS NULL"
            in guarda)
    assert "RAISE EXCEPTION" in guarda and "%" in guarda, "con su recuento"


def test_f150_r12_la_guarda_de_entrada_exige_las_fuentes_nuevas() -> None:
    texto = _devengo()
    entrada = texto[texto.index("DO $$"):texto.index("END $$;")]
    for objeto in ("stg.presupuesto", "raw.obrparpar", "raw.obr", "raw.dvf",
                   "tesoreria.condiciones_contrato_cliente"):
        assert f"to_regclass('{objeto}') IS NULL" in entrada, objeto


def test_f150_r14_el_reparto_con_coeficientes_es_el_mismo_reparto() -> None:
    texto = _devengo()
    assert ("ROUND(d.pendiente_con_coeficientes * pr.importe_mes / d.total_perfil, 2) "
            "AS parte_con_coef") in texto
    assert (
        "CASE WHEN r.desde_el_final = 1 THEN r.pendiente_con_coeficientes - "
        "(r.suma_partes_con_coef - r.parte_con_coef) ELSE r.parte_con_coef END"
    ) in texto
    assert "d.pendiente_con_coeficientes AS importe_con_coef" in texto, "sin perfil, entero"


def test_f150_r14_el_cociente_del_mes_a_seis_decimales() -> None:
    assert (
        "CASE WHEN x.concepto = 'VENTA' AND x.importe_pendiente <> 0 "
        "THEN ROUND(x.importe_con_coef / x.importe_pendiente, 6) END AS coeficiente_venta"
    ) in _devengo()


def test_f150_r14_la_guarda_de_la_suma_mira_tambien_la_suma_con_coeficientes() -> None:
    texto = _devengo()
    guarda = texto[texto.index("INSERT INTO tesoreria.devengo_pendiente_obra_mes"):]
    guarda = guarda[guarda.index("DO $$"):guarda.index("END $$;")]
    assert "SUM(pendiente_con_coeficientes) AS total_coef" in guarda
    assert "SUM(importe_pendiente_con_coeficientes) AS total_coef" in guarda
    assert ("OR COALESCE(p.total_coef, 0) IS DISTINCT FROM COALESCE(m.total_coef, 0)"
            in guarda)


def test_f150_r20_iva_y_retencion_de_la_obra_mes_redondeados_al_final() -> None:
    texto = _devengo()
    for dato, fuente in (("iva", "fuente_iva"), ("retencion", "fuente_retencion")):
        assert (f"SUM(r.importe_con_coef * r.{dato}_porcentaje) FILTER "
                f"(WHERE r.{fuente} = 'CONTRATO') AS {dato}_bruto") in texto
        assert (f"SUM(r.importe_con_coef) FILTER (WHERE r.{fuente} = 'SIN') "
                f"AS base_sin_{dato}") in texto
        assert (f"CASE WHEN x.concepto = 'VENTA' THEN ROUND(COALESCE(x.{dato}_bruto, 0) / 100, 2) "
                f"END AS importe_{dato}_contrato") in texto
        assert (f"CASE WHEN x.concepto = 'VENTA' THEN COALESCE(x.base_sin_{dato}, 0) END "
                f"AS base_sin_{dato}_contrato") in texto


def test_f150_r14_r20_las_columnas_del_mes_en_orden() -> None:
    columnas, _select = _insert(RUTA_DEVENGO, "tesoreria.devengo_pendiente_obra_mes")
    assert columnas[-6:] == list(COLUMNAS_NUEVAS["tesoreria.devengo_pendiente_obra_mes"])


# ===========================================================================
# 07 · el hueco de facturación de H26, NETO POR OBRA (R23, N9)
# ===========================================================================


def test_f150_r23_lo_real_a_origen_hasta_el_cierre_por_partida() -> None:
    texto = _devengo()
    assert (
        "JOIN mart.fact_seguimiento_mensual f ON f.obra_id = v.obra_id AND f.concepto = v.concepto "
        "AND f.tipo_dato = 'REAL' AND f.anio_mes <= v.mes_ultimo_cierre WHERE v.concepto = 'VENTA'"
    ) in texto


def test_f150_r23_la_media_de_la_obra_como_el_dominio() -> None:
    """`coeficiente_medio`: real x coef / real, solo con coeficiente, a 6; sin nada, 1."""
    texto = _devengo()
    assert (
        "COALESCE(ROUND(SUM(r.real_origen * c.coeficiente_venta) FILTER (WHERE "
        "c.coeficiente_venta IS NOT NULL) / NULLIF(SUM(r.real_origen) FILTER (WHERE "
        "c.coeficiente_venta IS NOT NULL), 0), 6), 1) AS coeficiente_medio"
    ) in texto


def test_f150_r23_lo_facturado_por_el_centro_de_coste_de_la_obra() -> None:
    texto = _devengo()
    assert "FROM raw.dvf fv JOIN raw.obr ob ON ob.cenide = fv.cenide" in texto
    assert "SUM(fv.totbas::NUMERIC(18, 2)) AS facturado_origen" in texto
    assert "fecdoc" not in texto, "sin corte de fecha (riesgo 6)"


def test_f150_r23_los_importes_de_raw_dvf_se_castean_a_numeric() -> None:
    """Arreglo del despliegue del 29-10: en Azure la ingesta guarda los importes
    de `raw.dvf` (`totbas`, `totiva`, `totdoc`) como `double precision`, y
    `ROUND(double precision, integer)` no existe en PostgreSQL. Todo importe de
    `raw.dvf` se lee con `::NUMERIC(18, 2)`, como `c.totbas` en 05 (F-140)."""
    texto = _devengo()
    cte = texto.split(", facturado AS (", 1)[1].split(", h AS (", 1)[0]
    assert "FROM raw.dvf" in cte
    usos = re.findall(r"fv\.(totbas|totiva|totdoc)(::NUMERIC\(18, 2\))?", cte)
    assert usos, "el CTE facturado debe leer algun importe de raw.dvf"
    sin_cast = [col for col, cast in usos if not cast]
    assert not sin_cast, f"importes de raw.dvf sin ::NUMERIC(18, 2): {sin_cast}"
    usos_fuera = re.findall(r"fv\.(totbas|totiva|totdoc)(?!::NUMERIC\(18, 2\))",
                            texto.replace(cte, ""))
    assert not usos_fuera, f"importes de raw.dvf fuera del CTE sin cast: {usos_fuera}"


def test_f150_r23_el_hueco_neto_por_obra_con_suelo_cero() -> None:
    texto = _devengo()
    assert ("GREATEST(0, h.venta_real_origen_con_coeficientes - h.facturado_origen) "
            "AS venta_pendiente_facturar") in texto
    assert ("GREATEST(0, h.facturado_origen - h.venta_real_origen_con_coeficientes) "
            "AS facturado_por_delante") in texto
    tramo_dvf = texto.split("FROM raw.dvf", 1)[1].split(";", 1)[0]
    assert "ctride" not in tramo_dvf, "nunca por contrato: solo 4.665 de 15.665 facturas lo llevan"


def test_f150_r23_iva_y_retencion_del_hueco_por_peso_de_contrato() -> None:
    texto = _devengo()
    for dato in ("iva", "retencion"):
        assert (f"ROUND(h.venta_pendiente_facturar * h.{dato}_ponderado / 100 / "
                f"NULLIF(h.real_con_coef_bruto, 0), 2)") in texto
        assert (f"ROUND(h.venta_pendiente_facturar * h.real_sin_{dato} / "
                f"NULLIF(h.real_con_coef_bruto, 0), 2)") in texto


def test_f150_r23_las_columnas_del_corte_en_orden_y_null_en_coste() -> None:
    columnas, select = _insert(RUTA_DEVENGO, "tesoreria.devengo_corte_obra")
    # 9 del hueco (R23) y, detrás, las 2 de la cartera de CP (N12, R36).
    assert columnas[-11:] == list(COLUMNAS_NUEVAS["tesoreria.devengo_corte_obra"])
    assert ("LEFT JOIN _dev_hueco hu ON hu.obra_id = v.obra_id AND v.concepto = 'VENTA'"
            in select)


def test_f150_r23_la_fuente_media_obra_no_se_escribe_como_fuente_de_partida() -> None:
    """MEDIA_OBRA solo vive en el hueco: ninguna partida la tiene como fuente."""
    assert f"'{dom.FUENTE_MEDIA_OBRA}'" not in _devengo()


def test_f150_r13_07_sigue_sin_leer_hipotesis() -> None:
    assert "hipotesis" not in _devengo().lower()


# ===========================================================================
# R21 · `08`: H12 SIGRID desde la ficha de la obra (N2, T10)
# ===========================================================================


def _hipotesis_obra() -> str:
    return _sin_comment_on(RUTA_HIPOTESIS_OBRA)


def test_f150_r21_h12_es_codigo_sigrid() -> None:
    """H12 se suma a los códigos que `08` resuelve como SIGRID; H09-H11 siguen
    (y N15 suma H13 detrás: `test_f150_iva_isp.py`)."""
    assert dom.CODIGOS_SIGRID[:4] == ("H09", "H10", "H11", "H12")
    codigos = re.findall(r"'(H[0-9]{2})'::VARCHAR\(3\) AS codigo", _hipotesis_obra())
    assert tuple(codigos) == dom.CODIGOS_SIGRID


def test_f150_r21_h12_sale_de_la_ficha_de_la_obra_por_cien() -> None:
    texto = _hipotesis_obra()
    rama = texto[texto.index("'H12'::VARCHAR(3) AS codigo"):]
    rama = rama[: rama.index("'H13'::VARCHAR(3) AS codigo")]
    assert "FROM raw.obr ob JOIN raw.iva i ON i.ide = NULLIF(ob.ivaide, 0)" in rama
    assert "to_jsonb(ROUND((i.iva * 100)::NUMERIC, 4)) AS valor" in rama
    assert f"'{dom.MOTIVO_H12_FICHA}' AS motivo" in rama
    assert "SELECT ob.ide AS obra_id, 'H12'::VARCHAR(3) AS codigo" in texto
    assert "condiciones_contrato_cliente" not in rama, "la ficha, no los contratos (N2)"


def test_f150_r21_el_orden_y_h10_no_cambian() -> None:
    texto = _hipotesis_obra()
    assert ("CASE WHEN m.valor IS NOT NULL THEN m.valor WHEN s.valor IS NOT NULL THEN s.valor "
            "ELSE h.valor_defecto END AS valor") in texto
    assert "k.retencion_porcentaje AS valor" in texto, "H10: la regla de F-140 (N3)"
    assert texto.count("FROM tesoreria.condiciones_contrato_cliente k") == 3


def test_f150_r21_el_comment_dice_cuantas_y_h12() -> None:
    comment = _sql(RUTA_HIPOTESIS_OBRA)
    comment = comment[comment.index("COMMENT ON TABLE tesoreria.hipotesis_caja_obra"):]
    assert f"las {_n_hipotesis()} hipotesis" in comment
    assert "H12" in comment and "ficha de la obra" in comment


def _n_hipotesis() -> int:
    """Cuantas hipotesis tiene el catalogo: los textos dicen ESA cifra (N14 y N15 la suben)."""
    import yaml as _yaml

    ruta = Path(__file__).resolve().parents[1] / "config" / "hipotesis_caja.yaml"
    return len(_yaml.safe_load(ruta.read_text(encoding="utf-8"))["hipotesis"])
