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
        "paso_receta": "PLAZO",  # F-150 (R1): obligatorio
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
    # F-150 (R25) suma `PERFIL_MESES`, el reparto de un importe entero en varios meses
    assert dom.UNIDADES == (
        "DIAS", "MESES", "PORCENTAJE", "BOOLEANO", "OPCION", "MAPA_DIAS", "PERFIL_MESES",
    )
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


@pytest.mark.parametrize("codigo", ["", 9, ["H01"]])
def test_f140_r2_sin_codigo_legible_el_error_dice_la_fila(codigo) -> None:
    """Superviviente de la campaña de mutación de F-140 (`and` -> `or` en la
    etiqueta): con un código vacío o que no es texto, el error se señala por el
    número de fila, nunca por el valor ilegible."""
    errores = validar_catalogo([_fila(codigo=codigo)])
    assert errores and all(e.startswith("fila 1: ") for e in errores), errores


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
    """D18-A: H09-H11, de los contratos con el cliente; F-150 (N2) suma H12,
    de la ficha de la obra."""
    assert dom.CODIGOS_SIGRID == ("H09", "H10", "H11", "H12")


# ===========================================================================
# R1 · el YAML real y su lector (T3)
# ===========================================================================

from etl_sigrid.infrastructure.config import hipotesis_caja_yaml as lector  # noqa: E402

#: Los defectos de `design.md` §6, código por código (unidad, valor).
DEFECTOS_DEL_DISENO = {
    "H01": ("OPCION", "CONTRATO"),
    # F-150 (N12, 29-10): el coste proporcional (CP) no es caja de la obra: sale
    # del mapa de plazos (va a F-154) y la receta lo excluye por `categoria`.
    "H02": ("MAPA_DIAS", {"CD": 120, "CI": 120, "OTRO": 120}),
    "H03": ("PERFIL_MESES", [[0, 100]]),  # F-150 (R26)
    "H04": ("BOOLEANO", True),
    "H05": ("DIAS", 0),
    "H06": ("PORCENTAJE", 0),
    "H07": ("OPCION", "FIN_OBRA"),
    "H08": ("PERFIL_MESES", [[1, 100]]),  # F-150 (R26)
    "H09": ("DIAS", 60),
    "H10": ("PORCENTAJE", 0),
    "H11": ("MESES", 12),
    "H12": ("PORCENTAJE", 21),
    "H13": ("PORCENTAJE", 5.5),
    "H14": ("OPCION", "MENSUAL"),  # F-150 (R28)
    "H15": ("OPCION", "PARTES_IGUALES"),
    "H16": ("OPCION", "PRIMER_MES"),
    "H17": ("BOOLEANO", True),
    "H18": ("OPCION", "POR_PARTIDA"),
    "H19": ("OPCION", "PRIMER_MES"),
    "H20": ("OPCION", "FIN_MES_ALBARAN"),  # F-150 (R28, N8)
    "H21": ("OPCION", "DESCONTAR"),
    "H22": ("PORCENTAJE", 0),
    "H23": ("OPCION", "FIN_DE_MES"),
    # F-150 (R24, R26): las cuatro nuevas
    "H24": ("PERFIL_MESES", [[0, 100]]),
    "H25": ("PERFIL_MESES", [[0, 100]]),
    "H26": ("OPCION", "INCLUIR"),
    "H27": ("MESES", 6),
}

#: Las alternativas que el diseño nombra (§6): son las `opciones` de la OPCION.
ALTERNATIVAS_DEL_DISENO = {
    "H07": {"SIGRID"},
    "H14": {"TRIMESTRAL", "NO_MODELAR"},  # F-150: el defecto pasa a MENSUAL
    "H16": {"EXCLUIR"},
    "H18": {"SOLO_MESES_CERRADOS"},
    "H19": {"REPARTIR", "EXCLUIR"},
    "H20": {"EXCLUIR"},
    "H23": {"MITAD_DE_MES"},
    "H26": {"NO_INCLUIR"},  # F-150
}


def test_f140_r1_yaml_real_pasa_la_validacion() -> None:
    leido = lector.cargar_hipotesis_caja(RUTA_YAML)
    assert leido.errores == []
    # F-150 suma H24-H27 y (N14) H28-H29: son 29
    assert [h.codigo for h in leido.catalogo] == [f"H{n:02d}" for n in range(1, 30)]


def test_f140_r1_yaml_los_defectos_son_los_del_diseno() -> None:
    catalogo = {h.codigo: h for h in lector.cargar_hipotesis_caja(RUTA_YAML).catalogo}
    for codigo, (unidad, valor) in DEFECTOS_DEL_DISENO.items():
        assert (catalogo[codigo].unidad, catalogo[codigo].valor_defecto) == (unidad, valor), codigo


def test_f140_r1_yaml_las_alternativas_son_opciones() -> None:
    catalogo = {h.codigo: h for h in lector.cargar_hipotesis_caja(RUTA_YAML).catalogo}
    for codigo, alternativas in ALTERNATIVAS_DEL_DISENO.items():
        assert alternativas <= set(catalogo[codigo].opciones), codigo
    for h in catalogo.values():
        if h.unidad == "OPCION":
            assert h.opciones[0] == h.valor_defecto, f"{h.codigo}: el defecto va primero"


def test_f140_r1_yaml_nada_esta_validado_todavia() -> None:
    """D17-A: los defectos son PROPUESTAS hasta que Negocio los valide."""
    for h in lector.cargar_hipotesis_caja(RUTA_YAML).catalogo:
        assert h.validado is False and h.fecha_validacion is None, h.codigo


def test_f140_r1_yaml_solo_h17_no_admite_obra() -> None:
    catalogo = lector.cargar_hipotesis_caja(RUTA_YAML).catalogo
    assert [h.codigo for h in catalogo if not h.admite_obra] == ["H17"]


def test_f140_r1_yaml_la_seccion_obras_nace_vacia() -> None:
    assert lector.cargar_hipotesis_caja(RUTA_YAML).obras == []


def test_f140_r1_yaml_el_sentido_de_cada_hipotesis() -> None:
    catalogo = {h.codigo: h for h in lector.cargar_hipotesis_caja(RUTA_YAML).catalogo}
    pagos = {"H01", "H02", "H03", "H04", "H05", "H06", "H07", "H13", "H20",
             "H24", "H27", "H29"}  # F-150
    cobros = {"H08", "H09", "H10", "H11", "H12", "H22", "H25", "H26"}  # F-150
    for codigo, h in catalogo.items():
        esperado = "PAGO" if codigo in pagos else "COBRO" if codigo in cobros else "AMBOS"
        assert h.sentido == esperado, codigo


def test_f140_r1_yaml_los_sigrid_admiten_obra() -> None:
    catalogo = {h.codigo: h for h in lector.cargar_hipotesis_caja(RUTA_YAML).catalogo}
    for codigo in dom.CODIGOS_SIGRID:
        assert catalogo[codigo].admite_obra, codigo


def test_f140_yaml_ruta_por_defecto_es_la_del_repositorio() -> None:
    assert lector.RUTA_POR_DEFECTO == RUTA_YAML
    assert lector.cargar_hipotesis_caja().errores == []


def _escribir(tmp_path: Path, texto: str) -> Path:
    ruta = tmp_path / "hipotesis.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_f140_yaml_sin_seccion_hipotesis_es_un_error(tmp_path) -> None:
    leido = lector.cargar_hipotesis_caja(_escribir(tmp_path, "obras: []\n"))
    assert leido.catalogo == () and any("hipotesis" in e for e in leido.errores)


def test_f140_yaml_que_no_es_un_mapa_es_un_error(tmp_path) -> None:
    leido = lector.cargar_hipotesis_caja(_escribir(tmp_path, "- H01\n"))
    assert leido.errores and leido.catalogo == ()


@pytest.mark.parametrize("texto", ["", "hipotesis: H01\n", "hipotesis: []\nobras: 3\n"])
def test_f140_yaml_mal_formado_da_errores(tmp_path, texto) -> None:
    assert lector.cargar_hipotesis_caja(_escribir(tmp_path, texto)).errores


def test_f140_yaml_sin_obras_es_lista_vacia(tmp_path) -> None:
    texto = RUTA_YAML.read_text(encoding="utf-8").replace("\nobras: []", "\n")
    leido = lector.cargar_hipotesis_caja(_escribir(tmp_path, texto))
    assert leido.errores == [] and leido.obras == []


def test_f140_yaml_un_valor_de_obra_se_valida_contra_el_catalogo(tmp_path) -> None:
    texto = RUTA_YAML.read_text(encoding="utf-8").replace(
        "\nobras: []",
        "\nobras:\n  - clave_obra: 1-0704\n    codigo: H09\n    valor: 90\n"
        "    motivo: contrato\n    fecha: 2026-10-25\n"
        "  - clave_obra: 1-0704\n    codigo: H99\n    valor: 1\n"
        "    motivo: x\n    fecha: 2026-10-25\n",
    )
    leido = lector.cargar_hipotesis_caja(_escribir(tmp_path, texto))
    assert len(leido.obras) == 2
    assert leido.errores and all("H99" in e for e in leido.errores), leido.errores


def test_f140_yaml_un_catalogo_roto_no_valida_las_obras(tmp_path) -> None:
    """Sin catálogo válido no se sabe contra qué validar: un solo bloque de errores."""
    texto = RUTA_YAML.read_text(encoding="utf-8").replace("unidad: DIAS", "unidad: HORAS", 1)
    leido = lector.cargar_hipotesis_caja(_escribir(tmp_path, texto))
    assert leido.catalogo == () and any("HORAS" in e for e in leido.errores)


def test_f140_yaml_un_fichero_que_no_existe_falla(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        lector.cargar_hipotesis_caja(tmp_path / "no_existe.yaml")
