# tests/test_f150_receta.py
"""
F-150 · La receta de la caja en el dominio (R1, D7): cada hipótesis dice en
qué PASO de la receta se aplica, uno de siete y en este orden.

El orden es la receta: la IA pasa el devengo a caja SIEMPRE así, y la ficha de
`tesoreria.hipotesis_caja` lo cuenta con los mismos siete pasos (R2, T12).
Dominio puro: sin BBDD.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import date
from pathlib import Path

import pytest
from psycopg.types.json import Json

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import (
    PASOS_RECETA,
    Hipotesis,
    construir_catalogo,
    validar_catalogo,
    validar_valores_obra,
)
from etl_sigrid.infrastructure.config import hipotesis_caja_yaml as lector
from etl_sigrid.infrastructure.postgres import hipotesis_caja_sql as hsql


def _fila(**cambios) -> dict:
    base = {
        "codigo": "H01",
        "sentido": "PAGO",
        "descripcion": "Plazo de pago con contrato",
        "unidad": "DIAS",
        "valor_defecto": 60,
        "fuente_defecto": "forma de pago mas frecuente",
        "ingrediente": "tesoreria.plazos_forma_pago",
        "validado": False,
        "admite_obra": True,
        "paso_receta": "PLAZO",
    }
    base.update(cambios)
    return base


# ---------------------------------------------------------------------------
# R1 · los siete pasos, en su orden
# ---------------------------------------------------------------------------


def test_f150_r1_los_siete_pasos_en_el_orden_de_la_receta() -> None:
    assert PASOS_RECETA == (
        "DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA", "CARTERA",
    )


def test_f150_r1_una_fila_con_su_paso_es_valida() -> None:
    assert validar_catalogo([_fila()]) == []


@pytest.mark.parametrize("paso", PASOS_RECETA)
def test_f150_r1_cada_paso_de_la_lista_vale(paso: str) -> None:
    assert validar_catalogo([_fila(paso_receta=paso)]) == []


def test_f150_r1_sin_paso_receta_es_un_error() -> None:
    fila = _fila()
    del fila["paso_receta"]
    errores = validar_catalogo([fila])
    assert errores == ["H01: falta el campo paso_receta"], errores


@pytest.mark.parametrize("paso", ["plazo", "PAGO", "", None, 4, "COEFICIENTE", " PLAZO"])
def test_f150_r1_un_paso_fuera_de_la_lista_es_un_error(paso) -> None:
    errores = validar_catalogo([_fila(paso_receta=paso)])
    assert len(errores) == 1, errores
    assert errores[0].startswith("H01: paso_receta ")
    assert "fuera de" in errores[0] and "DEVENGO" in errores[0]


def test_f150_r1_construir_catalogo_falla_sin_paso() -> None:
    fila = _fila()
    del fila["paso_receta"]
    with pytest.raises(ValueError, match="falta el campo paso_receta"):
        construir_catalogo([fila])


def test_f150_r1_la_hipotesis_lleva_su_paso() -> None:
    (hipotesis,) = construir_catalogo([_fila(paso_receta="RETENCION")])
    assert hipotesis.paso_receta == "RETENCION"


def test_f150_r1_paso_receta_es_el_ultimo_campo_de_hipotesis() -> None:
    """Al final y con defecto: quien construye una `Hipotesis` sin él no se rompe."""
    campos = [c.name for c in dataclasses.fields(Hipotesis)]
    assert campos[-1] == "paso_receta"
    assert dataclasses.fields(Hipotesis)[-1].default == ""


def test_f150_r1_paso_receta_es_obligatorio_y_no_opcional() -> None:
    assert "paso_receta" in dom._CAMPOS_OBLIGATORIOS
    assert "paso_receta" not in dom._CAMPOS_OPCIONALES


# ===========================================================================
# El YAML real (T6): R1, R24, R26, R27, R28
# ===========================================================================

RAIZ = Path(__file__).resolve().parents[1]
RUTA_YAML = RAIZ / "config" / "hipotesis_caja.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"
RUTA_SETUP = DIR_SQL / "00_setup.sql"

#: `design.md` §6: el paso de la receta de cada una de las 27.
PASO_DE_CADA_CODIGO = {
    **dict.fromkeys(("H18", "H19", "H23", "H26"), "DEVENGO"),
    **dict.fromkeys(("H03", "H08"), "DOCUMENTO"),
    **dict.fromkeys(("H01", "H02", "H04", "H05", "H09", "H15", "H22", "H24", "H25"), "PLAZO"),
    **dict.fromkeys(("H06", "H07", "H10", "H11"), "RETENCION"),
    **dict.fromkeys(("H12", "H13", "H14"), "IVA"),
    **dict.fromkeys(("H16", "H17", "H20", "H21", "H27"), "CARTERA"),
}


def _catalogo() -> dict[str, Hipotesis]:
    leido = lector.cargar_hipotesis_caja(RUTA_YAML)
    assert leido.errores == []
    return {h.codigo: h for h in leido.catalogo}


def _texto(h: Hipotesis) -> str:
    return re.sub(r"\s+", " ", f"{h.descripcion} {h.fuente_defecto}")


def test_f150_r1_yaml_cada_codigo_en_su_paso_tabla_entera() -> None:
    catalogo = _catalogo()
    assert {c: h.paso_receta for c, h in catalogo.items()} == PASO_DE_CADA_CODIGO


def test_f150_r1_yaml_coeficientes_no_tiene_hipotesis() -> None:
    """Los coeficientes son DATO del contrato y del master: ninguna hipótesis."""
    assert "COEFICIENTES" not in {h.paso_receta for h in _catalogo().values()}


def test_f150_r24_h26_la_venta_ejecutada_pendiente_de_facturar() -> None:
    h = _catalogo()["H26"]
    assert (h.sentido, h.unidad, h.valor_defecto, h.opciones) == (
        "COBRO", "OPCION", "INCLUIR", ("INCLUIR", "NO_INCLUIR"),
    )
    assert h.ingrediente == "tesoreria.devengo_corte_obra"
    assert (h.paso_receta, h.admite_obra, h.validado) == ("DEVENGO", True, False)
    assert "venta_pendiente_facturar" in _texto(h) and "facturado_por_delante" in _texto(h)


def test_f150_r24_h27_la_antiguedad_maxima_de_lo_pendiente_de_facturar() -> None:
    h = _catalogo()["H27"]
    assert (h.sentido, h.unidad, h.valor_defecto) == ("PAGO", "MESES", 6)
    # N11 (29-10): el ingrediente son los albaranes NETOS por proveedor, no la
    # vista de compras, que solo suma lineas > 0.
    assert h.ingrediente == "tesoreria.albaranes_pendientes_neto"
    assert "0,52" in _texto(h) and "8,76" in _texto(h)
    assert (h.paso_receta, h.admite_obra, h.validado) == ("CARTERA", True, False)


def test_f150_r24_son_27() -> None:
    assert list(_catalogo()) == [f"H{n:02d}" for n in range(1, 28)]


@pytest.mark.parametrize(("codigo", "defecto"), [("H03", [[0, 100]]), ("H08", [[1, 100]])])
def test_f150_r26_h03_y_h08_pasan_a_perfil(codigo: str, defecto) -> None:
    h = _catalogo()[codigo]
    assert (h.unidad, h.valor_defecto, h.paso_receta) == ("PERFIL_MESES", defecto, "DOCUMENTO")


@pytest.mark.parametrize(("codigo", "sentido"), [("H24", "PAGO"), ("H25", "COBRO")])
def test_f150_r26_h24_y_h25_el_fraccionamiento(codigo: str, sentido: str) -> None:
    h = _catalogo()[codigo]
    assert (h.sentido, h.unidad, h.valor_defecto) == (sentido, "PERFIL_MESES", [[0, 100]])
    assert (h.paso_receta, h.admite_obra, h.validado) == ("PLAZO", True, False)
    assert h.ingrediente == "tesoreria.plazos_forma_pago"
    assert "fraccionamiento" in h.descripcion.lower()


def test_f150_r26_la_cabecera_del_yaml_explica_el_perfil_con_ejemplos() -> None:
    cabecera = RUTA_YAML.read_text(encoding="utf-8").split("version:", 1)[0]
    assert "PERFIL_MESES" in cabecera and "paso_receta" in cabecera
    assert "[[1, 50], [2, 50]]" in cabecera and "[[3, 50], [4, 50]]" in cabecera


def test_f150_r27_un_perfil_por_obra_valida_y_viaja_como_json() -> None:
    catalogo = _catalogo()
    fila = {"clave_obra": "1-0704", "codigo": "H25", "valor": [[3, 50], [4, 50]],
            "motivo": "Cobro fraccionado pactado", "fecha": "2026-10-28"}
    assert validar_valores_obra([{**fila, "fecha": date(2026, 10, 28)}], catalogo) == []
    (manual,) = hsql.filas_manuales([fila])
    assert isinstance(manual[2], Json) and manual[2].obj == [[3, 50], [4, 50]]


def test_f150_r27_unidad_admite_perfil_meses_en_la_tabla() -> None:
    sql = RUTA_SETUP.read_text(encoding="utf-8")
    assert "ALTER TABLE tesoreria.hipotesis_caja ALTER COLUMN unidad TYPE VARCHAR(20);" in sql
    assert len("PERFIL_MESES") <= 20


def test_f150_r1_la_carga_publica_paso_receta() -> None:
    sql = RUTA_SETUP.read_text(encoding="utf-8")
    assert ("ALTER TABLE tesoreria.hipotesis_caja ADD COLUMN IF NOT EXISTS paso_receta "
            "VARCHAR(12);") in sql
    assert max(len(p) for p in PASOS_RECETA) <= 12
    columnas = re.search(r"\((.*?)\) VALUES", hsql.SQL_INSERT_CATALOGO).group(1)
    assert [c.strip() for c in columnas.split(",")][-1] == "paso_receta"
    filas = hsql.filas_catalogo(tuple(_catalogo().values()))
    assert [f[-1] for f in filas] == [PASO_DE_CADA_CODIGO[f[0]] for f in filas]


def test_f150_r28_h10_y_h12_solo_cubren_la_base_sin_contrato() -> None:
    catalogo = _catalogo()
    h10, h12 = _texto(catalogo["H10"]), _texto(catalogo["H12"])
    assert "va en el devengo" in h10 and "sin_retencion_contrato" in h10
    assert "va en el devengo" in h12 and "sin_iva_contrato" in h12
    assert "ficha de la obra" in h12 and "21 %" in h12 and "Control de Costes" in h12


def test_f150_r28_h13_pendiente_de_adp_y_h14_mensual() -> None:
    catalogo = _catalogo()
    assert "pendiente de AdP" in _texto(catalogo["H13"])
    h14 = catalogo["H14"]
    assert h14.valor_defecto == "MENSUAL" and h14.opciones[0] == "MENSUAL"
    assert set(h14.opciones) == {"MENSUAL", "TRIMESTRAL", "NO_MODELAR"}
    assert "dia 20 del mes siguiente" in _texto(h14) and "AdP" in _texto(h14)


def test_f150_r28_h15_solo_con_varios_vencimientos() -> None:
    assert "varios vencimientos" in _texto(_catalogo()["H15"])
    assert "no aplica" in _texto(_catalogo()["H15"])


def test_f150_r28_h20_a_fin_de_mes_del_albaran_con_su_ingrediente() -> None:
    h = _catalogo()["H20"]
    assert (h.valor_defecto, h.opciones) == ("FIN_MES_ALBARAN", ("FIN_MES_ALBARAN", "EXCLUIR"))
    # N11 (29-10): ingrediente, los albaranes NETOS; la fuente dice por que.
    assert h.ingrediente == "tesoreria.albaranes_pendientes_neto"
    assert "56,9" in _texto(h) and "93 %" in _texto(h) and "8,76" in _texto(h)
    assert "neto por proveedor" in _texto(h) and "tras_cierre" in _texto(h)


def test_f150_r36_h02_sin_la_clave_cp() -> None:
    """N12: el coste proporcional no es caja de la obra; H02 no le da plazo."""
    h = _catalogo()["H02"]
    assert set(h.valor_defecto) == {"CD", "CI", "OTRO"}
    assert "el CP no es caja de la obra" in _texto(h)
