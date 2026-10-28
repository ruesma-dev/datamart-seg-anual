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
    assert "o.coestr AS coeficientes_texto" in select
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
