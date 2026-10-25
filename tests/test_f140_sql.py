# tests/test_f140_sql.py
"""
F-140 · El SQL de los ingredientes de caja en `sql/tesoreria/` (R4-R18).

Se lee el SQL como texto: ni red ni BBDD. El SQL no llama al dominio, pero
lleva sus mismos literales (patrón de F-135), y aquí se comparan.
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
RUTA_PLAZOS = DIR_TESORERIA / "04_plazos_forma_pago.sql"
RUTA_COMPRA = DIR_TESORERIA / "05_condiciones_contrato_compra.sql"
RUTA_CLIENTE = DIR_TESORERIA / "06_condiciones_contrato_cliente.sql"
RUTA_DEVENGO = DIR_TESORERIA / "07_devengo_pendiente.sql"
RUTA_HIPOTESIS_OBRA = DIR_TESORERIA / "08_hipotesis_caja_obra.sql"

#: Los ficheros NUEVOS de F-140 (el 00 se amplía).
NUEVOS = (RUTA_PLAZOS, RUTA_COMPRA, RUTA_CLIENTE, RUTA_DEVENGO, RUTA_HIPOTESIS_OBRA)

#: Las ocho tablas nuevas y su clave primaria (design.md §4.1).
TABLAS_NUEVAS: dict[str, str] = {
    "tesoreria.hipotesis_caja": "codigo",
    "tesoreria.hipotesis_caja_manual": "clave_obra, codigo",
    "tesoreria.hipotesis_caja_obra": "obra_id, codigo",
    "tesoreria.condiciones_contrato_compra": "contrato_id",
    "tesoreria.condiciones_contrato_cliente": "contrato_cliente_id",
    "tesoreria.devengo_pendiente_partida": "obra_id, partida_id, concepto",
    "tesoreria.devengo_pendiente_obra_mes": "obra_id, anio_mes, concepto, categoria",
    "tesoreria.devengo_corte_obra": "obra_id, concepto",
}

#: Las columnas de la fórmula, las de R9, que repiten las condiciones (R10, R11).
COLUMNAS_FORMULA = (
    "plazo_formula", "dias_vencimientos", "num_vencimientos", "dias_retencion",
    "formula_reconocida",
)


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


def _cuerpo_tabla(tabla: str) -> str:
    m = re.search(
        rf"CREATE TABLE IF NOT EXISTS {re.escape(tabla)} \((.*?)\);", _ejecutable(RUTA_SETUP)
    )
    assert m, f"falta el CREATE TABLE IF NOT EXISTS de {tabla}"
    return m.group(1)


def _columnas(tabla: str) -> list[str]:
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", _cuerpo_tabla(tabla)):
        nombre = trozo.strip().split(" ")[0]
        if nombre and nombre.upper() != "PRIMARY":
            columnas.append(nombre)
    return columnas


def _cuerpo_funcion(nombre: str) -> str:
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(nombre)}\(.*?\$\$(.*?)\$\$;",
        _sql(RUTA_SETUP), re.S,
    )
    assert m, f"no encuentro {nombre}"
    return re.sub(r"\s+", " ", m.group(1))


FUNCIONES = ("tesoreria.fn_plazo_reconocido", "tesoreria.fn_plazo_dias",
             "tesoreria.fn_plazo_dias_retencion")


# ===========================================================================
# 00 · las funciones de la fórmula (R7, R8)
# ===========================================================================

@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f140_r8_setup_las_funciones_llevan_los_literales_del_dominio(funcion: str) -> None:
    cuerpo = _cuerpo_funcion(funcion)
    separador = "'" + dom.SEPARADOR_TOKENS + "'"
    assert f"regexp_split_to_array(btrim(f), {separador})" in cuerpo
    regex = {
        "tesoreria.fn_plazo_reconocido": (dom.REGEX_TOKEN_DIAS, dom.REGEX_TOKEN_RETENCION),
        "tesoreria.fn_plazo_dias": (dom.REGEX_TOKEN_DIAS,),
        "tesoreria.fn_plazo_dias_retencion": (dom.REGEX_TOKEN_RETENCION,),
    }[funcion]
    for literal in regex:
        assert f"'{literal}'" in cuerpo
    # ningún otro regex: lo que el SQL reconoce es lo que reconoce el dominio
    assert set(re.findall(r"~ '([^']*)'", cuerpo)) == set(regex)


@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f140_r8_setup_las_funciones_son_immutable_sobre_text(funcion: str) -> None:
    m = re.search(
        rf"CREATE OR REPLACE FUNCTION {re.escape(funcion)}\(f TEXT\)\s+RETURNS (\S+)\s+"
        rf"LANGUAGE sql IMMUTABLE AS",
        _sql(RUTA_SETUP),
    )
    assert m, funcion


def test_f140_r8_setup_los_tipos_que_devuelven() -> None:
    texto = re.sub(r"\s+", " ", _sql(RUTA_SETUP))
    assert "FUNCTION tesoreria.fn_plazo_reconocido(f TEXT) RETURNS BOOLEAN" in texto
    assert "FUNCTION tesoreria.fn_plazo_dias(f TEXT) RETURNS INT[]" in texto
    assert "FUNCTION tesoreria.fn_plazo_dias_retencion(f TEXT) RETURNS INT" in texto


def test_f140_r8_setup_reconocido_falla_cerrado() -> None:
    """Vacía o NULL, un token ajeno o dos `NR`: no reconocida (los casos de R8)."""
    cuerpo = _cuerpo_funcion("tesoreria.fn_plazo_reconocido")
    assert "f IS NOT NULL" in cuerpo
    assert "btrim(f) <> ''" in cuerpo
    assert f"t !~ '{dom.REGEX_TOKEN_DIAS}' AND t !~ '{dom.REGEX_TOKEN_RETENCION}'" in cuerpo
    assert f"WHERE t ~ '{dom.REGEX_TOKEN_RETENCION}') <= 1" in cuerpo


def test_f140_r8_setup_dias_y_retencion_solo_si_se_reconoce() -> None:
    dias = _cuerpo_funcion("tesoreria.fn_plazo_dias")
    assert "WHEN tesoreria.fn_plazo_reconocido(f)" in dias
    assert f"WHERE u.t ~ '{dom.REGEX_TOKEN_DIAS}' ORDER BY u.n" in dias, "en el orden escrito"
    assert "ELSE '{}'::INT[]" in dias, "no reconocida: sin días, como el dominio"
    retencion = _cuerpo_funcion("tesoreria.fn_plazo_dias_retencion")
    assert "WHEN tesoreria.fn_plazo_reconocido(f)" in retencion
    assert "left(t, -1)::INT" in retencion
    assert "ELSE" not in retencion, "no reconocida: NULL"


# ===========================================================================
# 00 · las ocho tablas (R4, R5, R10-R15, R16)
# ===========================================================================

@pytest.mark.parametrize(("tabla", "clave"), TABLAS_NUEVAS.items())
def test_f140_setup_cada_tabla_nueva_con_su_clave_primaria(tabla: str, clave: str) -> None:
    cuerpo = _cuerpo_tabla(tabla)
    if "," in clave:
        assert f"PRIMARY KEY ({clave})" in cuerpo, tabla
    else:
        assert re.search(rf"\b{clave} \w+(\(\d+\))? PRIMARY KEY", cuerpo), tabla


@pytest.mark.parametrize("tabla", TABLAS_NUEVAS)
def test_f140_setup_las_tablas_con_obra_se_buscan_por_obra(tabla: str) -> None:
    columnas = _columnas(tabla)
    if "obra_id" not in columnas:
        return
    clave = TABLAS_NUEVAS[tabla]
    indice = re.search(
        rf"CREATE INDEX IF NOT EXISTS \w+ ON {re.escape(tabla)} \(obra_id\);",
        _ejecutable(RUTA_SETUP),
    )
    assert clave.startswith("obra_id") or indice, f"{tabla}: índice por obra"


@pytest.mark.parametrize("tabla", TABLAS_NUEVAS)
def test_f140_r16_setup_ninguna_columna_de_caja(tabla: str) -> None:
    for columna in _columnas(tabla):
        assert not dom.es_columna_de_caja(columna), f"{tabla}.{columna}"


def test_f140_setup_no_dropea_ni_concede() -> None:
    ejecutable = _ejecutable(RUTA_SETUP).upper()
    assert "DROP TABLE" not in ejecutable and "DROP VIEW" not in ejecutable
    assert not re.search(r"\b(GRANT|REVOKE)\b", ejecutable)


def test_f140_setup_las_condiciones_repiten_las_columnas_de_la_formula() -> None:
    for tabla in ("tesoreria.condiciones_contrato_compra",
                  "tesoreria.condiciones_contrato_cliente"):
        columnas = _columnas(tabla)
        assert [c for c in columnas if c in COLUMNAS_FORMULA] == list(COLUMNAS_FORMULA), tabla


def test_f140_setup_los_valores_de_hipotesis_son_jsonb() -> None:
    """Un DIAS, un PORCENTAJE, una OPCION y un MAPA_DIAS en la misma columna."""
    for tabla, columna in (("tesoreria.hipotesis_caja", "valor_defecto"),
                           ("tesoreria.hipotesis_caja_manual", "valor"),
                           ("tesoreria.hipotesis_caja_obra", "valor")):
        assert re.search(rf"\b{columna} JSONB NOT NULL", _cuerpo_tabla(tabla)), tabla


def test_f140_setup_el_catalogo_tiene_los_campos_de_r1() -> None:
    assert _columnas("tesoreria.hipotesis_caja") == [
        "codigo", "sentido", "descripcion", "unidad", "valor_defecto", "opciones",
        "fuente_defecto", "ingrediente", "validado", "fecha_validacion", "admite_obra",
    ]
    assert _columnas("tesoreria.hipotesis_caja_manual") == [
        "clave_obra", "codigo", "valor", "motivo", "fecha",
    ]


def test_f140_r5_setup_las_columnas_de_la_hipotesis_por_obra() -> None:
    assert _columnas("tesoreria.hipotesis_caja_obra") == [
        "obra_id", "empresa_id", "clave_obra", "codigo", "valor", "nivel", "fuente", "motivo",
    ]
