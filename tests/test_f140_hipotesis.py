# tests/test_f140_hipotesis.py
"""
F-140 · El catálogo de hipótesis de conversión devengo -> caja (R1-R3, R5).

El catálogo vive en `config/hipotesis_caja.yaml` (D13) con sus valores por
defecto PROPUESTOS (`validado: false`, D17) y los valores por obra en su sección
`obras` (D14). Aquí se prueba el dominio que lo valida y resuelve, y que el
YAML real pasa esa validación. Ni red ni BBDD.
"""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import (
    Hipotesis,
    construir_catalogo,
    resolver_hipotesis,
    validar_catalogo,
    validar_valores_obra,
)

RAIZ = Path(__file__).resolve().parents[1]
RUTA_YAML = RAIZ / "config" / "hipotesis_caja.yaml"


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
    }
    base.update(cambios)
    return base


def _catalogo_valido() -> list[dict]:
    return [
        _fila(),
        _fila(codigo="H02", unidad="PORCENTAJE", valor_defecto=5.5),
        _fila(codigo="H03", unidad="OPCION", valor_defecto="FIN_OBRA",
              opciones=["FIN_OBRA", "SIGRID"]),
        _fila(codigo="H04", unidad="BOOLEANO", valor_defecto=True, admite_obra=False),
        _fila(codigo="H05", unidad="MAPA_DIAS", valor_defecto={"CD": 120, "CI": 90}),
        _fila(codigo="H06", unidad="MESES", valor_defecto=12, sentido="COBRO"),
    ]


# ===========================================================================
# R2 · validar el catálogo
# ===========================================================================

def test_f140_r2_el_catalogo_valido_no_tiene_errores() -> None:
    assert validar_catalogo(_catalogo_valido()) == []


def test_f140_r2_las_listas_cerradas_son_las_del_diseno() -> None:
    assert dom.UNIDADES == ("DIAS", "MESES", "PORCENTAJE", "BOOLEANO", "OPCION", "MAPA_DIAS")
    assert dom.NIVELES == ("DEFECTO", "OBRA", "USUARIO")
    assert dom.FUENTES == ("DEFECTO", "SIGRID", "MANUAL")
    assert dom.SENTIDOS == ("PAGO", "COBRO", "AMBOS")
    assert dom.REGEX_CODIGO_HIPOTESIS == r"^H[0-9]{2}$"


def test_f140_r2_un_catalogo_vacio_es_un_error() -> None:
    assert validar_catalogo([]) != []


def test_f140_r2_codigo_repetido() -> None:
    errores = validar_catalogo([_fila(), _fila(descripcion="otra")])
    assert any("H01" in e and "repetido" in e for e in errores), errores


@pytest.mark.parametrize("codigo", ["H1", "H001", "h01", "X01", "H0A", "", None, 1])
def test_f140_r2_codigo_mal_formado(codigo) -> None:
    errores = validar_catalogo([_fila(codigo=codigo)])
    assert any("codigo" in e for e in errores), errores


@pytest.mark.parametrize("unidad", ["HORAS", "dias", "", None])
def test_f140_r2_unidad_fuera_de_lista(unidad) -> None:
    errores = validar_catalogo([_fila(unidad=unidad)])
    assert any("unidad" in e for e in errores), errores


@pytest.mark.parametrize("sentido", ["ENTRADA", "pago", None])
def test_f140_r2_sentido_fuera_de_lista(sentido) -> None:
    errores = validar_catalogo([_fila(sentido=sentido)])
    assert any("sentido" in e for e in errores), errores


@pytest.mark.parametrize(
    ("unidad", "valor", "extra"),
    [
        ("DIAS", -1, {}),
        ("DIAS", 30.5, {}),
        ("DIAS", True, {}),
        ("DIAS", "30", {}),
        ("DIAS", None, {}),
        ("MESES", -2, {}),
        ("MESES", 1.5, {}),
        ("MESES", False, {}),
        ("PORCENTAJE", -0.1, {}),
        ("PORCENTAJE", 100.01, {}),
        ("PORCENTAJE", "21", {}),
        ("PORCENTAJE", True, {}),
        ("BOOLEANO", 1, {}),
        ("BOOLEANO", "si", {}),
        ("OPCION", "OTRA", {"opciones": ["A", "B"]}),
        ("OPCION", 3, {"opciones": ["A", "B"]}),
        ("MAPA_DIAS", {}, {}),
        ("MAPA_DIAS", {"CD": -1}, {}),
        ("MAPA_DIAS", {"CD": "120"}, {}),
        ("MAPA_DIAS", {"CD": True}, {}),
        ("MAPA_DIAS", {1: 120}, {}),
        ("MAPA_DIAS", [120], {}),
    ],
)
def test_f140_r2_valor_que_no_casa_con_la_unidad(unidad, valor, extra) -> None:
    errores = validar_catalogo([_fila(unidad=unidad, valor_defecto=valor, **extra)])
    assert any("valor" in e for e in errores), errores


@pytest.mark.parametrize(
    ("unidad", "valor"),
    [("DIAS", 0), ("MESES", 0), ("PORCENTAJE", 0), ("PORCENTAJE", 100),
     ("PORCENTAJE", 21), ("MAPA_DIAS", {"OTRO": 0})],
)
def test_f140_r2_los_bordes_validos(unidad, valor) -> None:
    assert validar_catalogo([_fila(unidad=unidad, valor_defecto=valor)]) == []


def test_f140_r2_opcion_sin_opciones_es_un_error() -> None:
    errores = validar_catalogo([_fila(unidad="OPCION", valor_defecto="A")])
    assert any("opciones" in e for e in errores), errores


@pytest.mark.parametrize("opciones", [[], ["A", "A"], ["A", 3], "A"])
def test_f140_r2_opciones_mal_formadas(opciones) -> None:
    errores = validar_catalogo([_fila(unidad="OPCION", valor_defecto="A", opciones=opciones)])
    assert any("opciones" in e for e in errores), errores


def test_f140_r2_opciones_en_una_unidad_que_no_es_opcion() -> None:
    errores = validar_catalogo([_fila(opciones=["A"])])
    assert any("opciones" in e for e in errores), errores


@pytest.mark.parametrize("campo", ["validado", "admite_obra"])
@pytest.mark.parametrize("valor", ["no", 0, None])
def test_f140_r2_las_marcas_son_booleanas(campo, valor) -> None:
    errores = validar_catalogo([_fila(**{campo: valor})])
    assert any(campo in e for e in errores), errores


@pytest.mark.parametrize("campo", ["descripcion", "fuente_defecto"])
@pytest.mark.parametrize("valor", ["", "   ", None, 3])
def test_f140_r2_los_textos_obligatorios(campo, valor) -> None:
    errores = validar_catalogo([_fila(**{campo: valor})])
    assert any(campo in e for e in errores), errores


def test_f140_r2_el_ingrediente_puede_faltar_pero_no_ser_vacio() -> None:
    assert validar_catalogo([_fila(ingrediente=None)]) == []
    assert any("ingrediente" in e for e in validar_catalogo([_fila(ingrediente="")]))
    assert any("ingrediente" in e for e in validar_catalogo([_fila(ingrediente=3)]))


@pytest.mark.parametrize("falta", ["codigo", "sentido", "descripcion", "unidad",
                                   "valor_defecto", "fuente_defecto", "ingrediente",
                                   "validado", "admite_obra"])
def test_f140_r1_r2_todos_los_campos_son_obligatorios(falta) -> None:
    fila = _fila()
    del fila[falta]
    errores = validar_catalogo([fila])
    assert any(falta in e for e in errores), errores


def test_f140_r2_un_campo_desconocido_es_un_error() -> None:
    errores = validar_catalogo([_fila(valor_por_defecto=3)])
    assert any("valor_por_defecto" in e for e in errores), errores


def test_f140_r2_validado_exige_fecha_y_al_reves() -> None:
    assert any("fecha_validacion" in e for e in validar_catalogo([_fila(validado=True)]))
    assert any("fecha_validacion" in e for e in validar_catalogo(
        [_fila(validado=False, fecha_validacion=date(2026, 11, 1))]))
    assert validar_catalogo([_fila(validado=True, fecha_validacion=date(2026, 11, 1))]) == []
    assert any("fecha_validacion" in e for e in validar_catalogo(
        [_fila(validado=True, fecha_validacion="2026-11-01")]))


def test_f140_r2_una_fila_que_no_es_un_mapa() -> None:
    errores = validar_catalogo(["H01"])
    assert errores and "fila 1" in errores[0]


def test_f140_r2_los_errores_dicen_el_codigo() -> None:
    errores = validar_catalogo([_fila(codigo="H07", unidad="HORAS")])
    assert errores and all("H07" in e for e in errores), errores


def test_f140_r2_junta_todos_los_errores_no_solo_el_primero() -> None:
    errores = validar_catalogo([_fila(unidad="HORAS"), _fila(codigo="H9", validado="no")])
    assert len(errores) >= 3, errores


def test_f140_r2_construir_falla_con_la_lista() -> None:
    with pytest.raises(ValueError) as exc:
        construir_catalogo([_fila(unidad="HORAS"), _fila(codigo="H9")])
    assert "unidad" in str(exc.value) and "codigo" in str(exc.value)


def test_f140_r2_construir_da_las_hipotesis_en_su_orden() -> None:
    catalogo = construir_catalogo(_catalogo_valido())
    assert [h.codigo for h in catalogo] == ["H01", "H02", "H03", "H04", "H05", "H06"]
    h03 = catalogo[2]
    assert isinstance(h03, Hipotesis)
    assert h03.opciones == ("FIN_OBRA", "SIGRID")
    assert catalogo[0].opciones == ()
    assert catalogo[0].fecha_validacion is None
    assert catalogo[3].admite_obra is False
    assert catalogo[4].valor_defecto == {"CD": 120, "CI": 90}


def test_f140_r2_la_hipotesis_es_inmutable() -> None:
    h = construir_catalogo(_catalogo_valido())[0]
    with pytest.raises(AttributeError):
        h.codigo = "H99"  # type: ignore[misc]


def test_f140_r2_validar_no_modifica_las_filas() -> None:
    filas = _catalogo_valido()
    copia = copy.deepcopy(filas)
    validar_catalogo(filas)
    construir_catalogo(filas)
    assert filas == copia


# ===========================================================================
# R3 · los valores por obra
# ===========================================================================

def _obra(**cambios) -> dict:
    base = {"clave_obra": "1-0704", "codigo": "H01", "valor": 90,
            "motivo": "contrato marco", "fecha": date(2026, 10, 25)}
    base.update(cambios)
    return base


@pytest.fixture
def catalogo() -> dict[str, Hipotesis]:
    return {h.codigo: h for h in construir_catalogo(_catalogo_valido())}


def test_f140_r3_valor_de_obra_valido(catalogo) -> None:
    assert validar_valores_obra([_obra()], catalogo) == []
    assert validar_valores_obra([], catalogo) == []


def test_f140_r3_codigo_inexistente_en_el_catalogo(catalogo) -> None:
    errores = validar_valores_obra([_obra(codigo="H77")], catalogo)
    assert any("H77" in e and "1-0704" in e for e in errores), errores


def test_f140_r3_codigo_que_no_admite_obra(catalogo) -> None:
    errores = validar_valores_obra([_obra(codigo="H04", valor=False)], catalogo)
    assert any("H04" in e and "admite_obra" in e for e in errores), errores


@pytest.mark.parametrize("clave", ["0704", "1-", "-0704", "a-0704", "", None, 1704])
def test_f140_r3_clave_de_obra_mal_formada(catalogo, clave) -> None:
    errores = validar_valores_obra([_obra(clave_obra=clave)], catalogo)
    assert any("clave_obra" in e for e in errores), errores


def test_f140_r3_el_valor_se_valida_con_la_unidad_del_catalogo(catalogo) -> None:
    assert any("valor" in e for e in validar_valores_obra([_obra(valor=-5)], catalogo))
    assert any("valor" in e for e in validar_valores_obra(
        [_obra(codigo="H03", valor="OTRA")], catalogo))
    assert validar_valores_obra([_obra(codigo="H03", valor="SIGRID")], catalogo) == []


def test_f140_r3_valor_de_obra_repetido(catalogo) -> None:
    errores = validar_valores_obra([_obra(), _obra(valor=30)], catalogo)
    assert any("repetido" in e for e in errores), errores


def test_f140_r3_la_misma_hipotesis_en_dos_obras_no_se_repite(catalogo) -> None:
    assert validar_valores_obra([_obra(), _obra(clave_obra="31-0606")], catalogo) == []


@pytest.mark.parametrize("motivo", ["", "  ", None])
def test_f140_r3_sin_motivo_no_vale(catalogo, motivo) -> None:
    errores = validar_valores_obra([_obra(motivo=motivo)], catalogo)
    assert any("motivo" in e for e in errores), errores


@pytest.mark.parametrize("fecha", [None, "2026-10-25", 20261025])
def test_f140_r3_la_fecha_es_una_fecha(catalogo, fecha) -> None:
    errores = validar_valores_obra([_obra(fecha=fecha)], catalogo)
    assert any("fecha" in e for e in errores), errores


@pytest.mark.parametrize("falta", ["clave_obra", "codigo", "valor", "motivo", "fecha"])
def test_f140_r3_todos_los_campos_son_obligatorios(catalogo, falta) -> None:
    fila = _obra()
    del fila[falta]
    errores = validar_valores_obra([fila], catalogo)
    assert any(falta in e for e in errores), errores


def test_f140_r3_campo_desconocido_y_fila_que_no_es_un_mapa(catalogo) -> None:
    assert any("nivel" in e for e in validar_valores_obra([_obra(nivel="OBRA")], catalogo))
    assert validar_valores_obra(["1-0704"], catalogo)


# ===========================================================================
# R5 · resolver: MANUAL > SIGRID > DEFECTO
# ===========================================================================

def test_f140_r5_manual_gana_a_sigrid_y_al_defecto() -> None:
    assert resolver_hipotesis(60, 90, 120) == (120, "OBRA", "MANUAL")


def test_f140_r5_sigrid_gana_al_defecto() -> None:
    assert resolver_hipotesis(60, 90, None) == (90, "OBRA", "SIGRID")


def test_f140_r5_sin_nada_el_defecto() -> None:
    assert resolver_hipotesis(60, None, None) == (60, "DEFECTO", "DEFECTO")


@pytest.mark.parametrize("falsy", [0, False, "", 0.0])
def test_f140_r5_un_valor_falso_tambien_cuenta(falsy) -> None:
    """Un 0 % manual es un valor, no la ausencia de valor."""
    assert resolver_hipotesis(60, 90, falsy) == (falsy, "OBRA", "MANUAL")
    assert resolver_hipotesis(60, falsy, None) == (falsy, "OBRA", "SIGRID")


def test_f140_r5_el_orden_de_las_fuentes() -> None:
    """El `CASE` de `08_hipotesis_caja_obra.sql` sigue este orden (test del SQL)."""
    assert dom.ORDEN_FUENTES == ("MANUAL", "SIGRID", "DEFECTO")
    assert set(dom.ORDEN_FUENTES) == set(dom.FUENTES)


def test_f140_r5_los_codigos_que_lee_sigrid() -> None:
    """D18-A: H09-H11, de los contratos con el cliente."""
    assert dom.CODIGOS_SIGRID == ("H09", "H10", "H11")
