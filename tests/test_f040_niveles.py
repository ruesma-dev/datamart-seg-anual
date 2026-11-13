# tests/test_f040_niveles.py
"""F-040: niveles con datos propios (`informativas`, `limites`, `tamano`, `spec`).

El mecanismo se activa por datos del nivel, no por el nombre `express`: por eso
casi todo se prueba con niveles inventados. Los valores que entrega el payload
solo se fijan en el taller (R42): en un proyecto, `rigor.json` es suyo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import rigor as modulo
from harness import tamano
from harness.rigor import cargar_rigor, topes_tamano, validar_features

RAIZ = Path(__file__).resolve().parents[1]

#: `harness/rigor.json` de la 1.7.16 (publicada el 2026-10-16), literal sin los
#: `$doc`: lo que tiene un proyecto que conserva el suyo (R37).
RIGOR_1_7_16 = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "mutacion": {"timeout_por_mutante_s": 120},
    "tamano": {"requirements": 150, "design": 250, "impl": 220, "review": 140},
    "niveles": {
        "documental": {
            "fase_red": False, "cobertura": False, "mutacion": False,
            "supervivientes_maximos": None, "max_mutantes": None, "semilla": None,
        },
        "estandar": {
            "fase_red": True, "cobertura": True, "mutacion": True,
            "supervivientes_maximos": None, "max_mutantes": 20, "semilla": 20260820,
        },
        "critico": {
            "fase_red": True, "cobertura": True, "mutacion": True,
            "supervivientes_maximos": 0, "max_mutantes": None, "semilla": None,
        },
    },
}


def _rigor(**nivel: object) -> dict:
    """Configuración mínima con un nivel `rapido` que no exige nada."""
    definicion = {"fase_red": False, "cobertura": False, "mutacion": False, **nivel}
    return {"nivel_por_defecto": "rapido", "niveles": {"rapido": definicion}}


def _cargar(tmp_path: Path, datos: dict) -> dict:
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return cargar_rigor(ruta)


def _rechaza(tmp_path: Path, datos: dict, *fragmentos: str) -> None:
    with pytest.raises(ValueError) as error:
        _cargar(tmp_path, datos)
    for fragmento in fragmentos:
        assert fragmento in str(error.value), str(error.value)


# --- R3: informativa ---------------------------------------------------------


def test_f040_r3_informativa_solo_si_el_nivel_la_nombra() -> None:
    rigor = _rigor(informativas=["cobertura"])

    assert modulo.informativa("rapido", "cobertura", rigor) is True
    assert modulo.informativa("rapido", "mutacion", rigor) is False


@pytest.mark.parametrize("rigor", [
    _rigor(),
    _rigor(informativas=None),
    _rigor(informativas="cobertura"),
], ids=["sin clave", "null", "texto"])
def test_f040_r3_sin_lista_no_es_informativa(rigor: dict) -> None:
    assert modulo.informativa("rapido", "cobertura", rigor) is False


def test_f040_r3_nivel_desconocido_no_es_informativa() -> None:
    assert modulo.informativa("otro", "cobertura", _rigor(informativas=["cobertura"])) is False


# --- R4: validación de `informativas` ----------------------------------------


@pytest.mark.parametrize("valor", ["cobertura", {"cobertura": True}, 3, ["fase_rojo"], [1]])
def test_f040_r4_informativas_que_no_son_puertas_es_error(tmp_path: Path, valor: object) -> None:
    _rechaza(tmp_path, _rigor(informativas=valor), "'rapido'", "'informativas'")


def test_f040_r4_informativa_y_exigida_a_la_vez_es_error(tmp_path: Path) -> None:
    datos = _rigor(cobertura=True, informativas=["cobertura"])

    _rechaza(tmp_path, datos, "'rapido'", "'informativas'", "cobertura")


@pytest.mark.parametrize("valor", [[], ["fase_red"], ["cobertura", "mutacion"]])
def test_f040_r4_informativas_validas_cargan(tmp_path: Path, valor: list[str]) -> None:
    assert _cargar(tmp_path, _rigor(informativas=valor))["niveles"]["rapido"]["informativas"] == valor


# --- R5: límites -------------------------------------------------------------


def test_f040_r5_limites_nivel_devuelve_los_declarados_o_none() -> None:
    limites = {"ficheros": 3, "lineas": 150, "no_cuentan": ["tests/**"]}

    assert modulo.limites_nivel("rapido", _rigor(limites=limites)) == limites
    assert modulo.limites_nivel("rapido", _rigor()) is None
    assert modulo.limites_nivel("otro", _rigor(limites=limites)) is None


def test_f040_r5_no_cuentan_es_opcional(tmp_path: Path) -> None:
    rigor = _cargar(tmp_path, _rigor(limites={"ficheros": 1, "lineas": 1}))

    assert modulo.limites_nivel("rapido", rigor) == {"ficheros": 1, "lineas": 1}


@pytest.mark.parametrize("clave", ["ficheros", "lineas"])
@pytest.mark.parametrize("valor", [0, -1, True, "3", 1.5, None])
def test_f040_r5_limite_que_no_es_entero_positivo_es_error(
    tmp_path: Path, clave: str, valor: object
) -> None:
    limites = {"ficheros": 3, "lineas": 150, clave: valor}

    _rechaza(tmp_path, _rigor(limites=limites), "'rapido'", f"'{clave}'")


@pytest.mark.parametrize("clave", ["ficheros", "lineas"])
def test_f040_r5_limite_ausente_es_error(tmp_path: Path, clave: str) -> None:
    limites = {"ficheros": 3, "lineas": 150}
    del limites[clave]

    _rechaza(tmp_path, _rigor(limites=limites), "'rapido'", f"'{clave}'")


@pytest.mark.parametrize("valor", ["tests/**", [1], None])
def test_f040_r5_no_cuentan_que_no_es_lista_de_textos_es_error(
    tmp_path: Path, valor: object
) -> None:
    limites = {"ficheros": 3, "lineas": 150, "no_cuentan": valor}

    _rechaza(tmp_path, _rigor(limites=limites), "'rapido'", "'no_cuentan'")


@pytest.mark.parametrize("valor", [3, "tres", [], None])
def test_f040_r5_limites_que_no_es_objeto_es_error(tmp_path: Path, valor: object) -> None:
    _rechaza(tmp_path, _rigor(limites=valor), "'rapido'", "'limites'")


def test_f040_r5_el_limite_de_uno_vale(tmp_path: Path) -> None:
    """El mínimo positivo es 1: la frontera de la validación."""
    assert _cargar(tmp_path, _rigor(limites={"ficheros": 1, "lineas": 1}))


# --- R6: sdd con un nivel sin spec -------------------------------------------


def test_f040_r6_sdd_true_con_nivel_sin_spec_es_error() -> None:
    errores = validar_features(
        [{"id": "F-001", "rigor": "rapido", "sdd": True}], _rigor(spec=False))

    assert len(errores) == 1
    assert "F-001" in errores[0] and "rapido" in errores[0] and "sdd" in errores[0]


@pytest.mark.parametrize(("ficha", "nivel"), [
    ({"sdd": False, "rigor": "rapido"}, {"spec": False}),
    ({"rigor": "rapido"}, {"spec": False}),
    ({"sdd": True, "rigor": "rapido"}, {"spec": True}),
    ({"sdd": True, "rigor": "rapido"}, {}),
    ({"sdd": True}, {"spec": False}),
], ids=["sdd false", "sin sdd", "spec true", "sin spec", "sin nivel declarado"])
def test_f040_r6_lo_demas_no_es_error(ficha: dict, nivel: dict) -> None:
    assert validar_features([{"id": "F-001", **ficha}], _rigor(**nivel)) == []


# --- R19: topes por nivel ----------------------------------------------------


def _con_topes() -> dict:
    rigor = _rigor(tamano={"impl": 40, "review": 60})
    rigor["tamano"] = {"requirements": 150, "impl": 220, "review": 140}
    return rigor


def test_f040_r19_el_nivel_pisa_clave_a_clave() -> None:
    assert topes_tamano(_con_topes(), "rapido") == {
        "requirements": 150, "impl": 40, "review": 60}


def test_f040_r19_sin_nivel_o_sin_bloque_los_globales() -> None:
    globales = {"requirements": 150, "impl": 220, "review": 140}

    assert topes_tamano(_con_topes()) == globales
    assert topes_tamano(_con_topes(), None) == globales
    assert topes_tamano(_con_topes(), "otro") == globales
    sin_bloque = _rigor()
    sin_bloque["tamano"] = globales
    assert topes_tamano(sin_bloque, "rapido") == globales


def test_f040_r19_el_nivel_filtra_igual_que_el_global() -> None:
    rigor = _rigor(tamano={"impl": 0, "review": True, "design": "9", "$doc": "x"})
    rigor["tamano"] = {"impl": 220, "review": 140}

    assert topes_tamano(rigor, "rapido") == {"impl": 220, "review": 140}


def test_f040_r19_un_bloque_de_nivel_que_no_es_objeto_se_ignora() -> None:
    rigor = _rigor(tamano="mucho")
    rigor["tamano"] = {"impl": 220}

    assert topes_tamano(rigor, "rapido") == {"impl": 220}


def test_f040_r19_solo_bloque_de_nivel_sin_global() -> None:
    assert topes_tamano(_rigor(tamano={"impl": 40}), "rapido") == {"impl": 40}


# --- R37, R38, R39: compatibilidad -------------------------------------------


def test_f040_r37_el_rigor_de_la_1_7_x_sigue_cargando(tmp_path: Path) -> None:
    rigor = _cargar(tmp_path, RIGOR_1_7_16)

    assert modulo.niveles_validos(rigor) == ["critico", "documental", "estandar"]
    for nivel in ("estandar", "critico"):
        for puerta in modulo.PUERTAS:
            assert modulo.exige(nivel, puerta, rigor) is True
            assert modulo.informativa(nivel, puerta, rigor) is False
    assert modulo.exige("documental", "mutacion", rigor) is False
    assert topes_tamano(rigor, "estandar") == RIGOR_1_7_16["tamano"]
    assert all(modulo.limites_nivel(n, rigor) is None for n in rigor["niveles"])


def test_f040_r38_express_sin_declarar_da_el_error_de_hoy(tmp_path: Path) -> None:
    rigor = _cargar(tmp_path, RIGOR_1_7_16)

    errores = validar_features([{"id": "F-001", "rigor": "express", "sdd": False}], rigor)

    assert errores == [
        "F-001: rigor 'express' no válido; usa uno de "
        "['critico', 'documental', 'estandar']"
    ]


def test_f040_r38_validar_sale_con_1(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    config = tmp_path / "rigor.json"
    config.write_text(json.dumps(RIGOR_1_7_16), encoding="utf-8")
    features = tmp_path / "features.json"
    features.write_text(
        json.dumps({"features": [{"id": "F-001", "rigor": "express"}]}), encoding="utf-8")

    assert modulo.main(["--validar", "--config", str(config), "--features", str(features)]) == 1
    assert "['critico', 'documental', 'estandar']" in capsys.readouterr().err


# --- R20: la puerta de tamaño usa los topes del nivel de la feature -----------


def _proyecto_tamano(tmp_path: Path, rigor_ficha: str | None, lineas: int) -> None:
    datos = _rigor(tamano={"impl": 40})
    datos["tamano"] = {"impl": 220}
    (tmp_path / "harness").mkdir()
    (tmp_path / "progress").mkdir()
    (tmp_path / "harness" / "rigor.json").write_text(json.dumps(datos), encoding="utf-8")
    fichas = [] if rigor_ficha is None else [{"id": "F-001", "rigor": rigor_ficha}]
    (tmp_path / "harness" / "features.json").write_text(
        json.dumps({"features": fichas}), encoding="utf-8")
    (tmp_path / "progress" / "impl_F-001.md").write_text("x\n" * lineas, encoding="utf-8")


def test_f040_r20_usa_el_tope_del_nivel_y_el_rojo_lo_nombra(tmp_path, capsys) -> None:
    _proyecto_tamano(tmp_path, "rapido", 41)

    assert tamano.main(["--feature", "F-001", "--raiz", str(tmp_path)]) == 1
    error = capsys.readouterr().err
    assert "tope 40" in error and "nivel rapido" in error


def test_f040_r20_en_el_tope_del_nivel_pasa(tmp_path, capsys) -> None:
    _proyecto_tamano(tmp_path, "rapido", 40)

    assert tamano.main(["--feature", "F-001", "--raiz", str(tmp_path)]) == 0
    assert "impl 40/40" in capsys.readouterr().out


def test_f040_r20_sin_ficha_usa_los_globales(tmp_path, capsys) -> None:
    _proyecto_tamano(tmp_path, None, 41)

    assert tamano.main(["--feature", "F-001", "--raiz", str(tmp_path)]) == 0
    assert "impl 41/220" in capsys.readouterr().out


def test_f040_r20_sin_features_json_usa_los_globales(tmp_path) -> None:
    _proyecto_tamano(tmp_path, None, 41)
    (tmp_path / "harness" / "features.json").unlink()

    assert tamano.main(["--feature", "F-001", "--raiz", str(tmp_path)]) == 0


@pytest.mark.parametrize("roto", ["{roto", "[]"], ids=["no es JSON", "no es objeto"])
def test_f040_r20_features_ilegible_usa_los_globales(tmp_path, roto: str) -> None:
    _proyecto_tamano(tmp_path, None, 41)
    (tmp_path / "harness" / "features.json").write_text(roto, encoding="utf-8")

    assert tamano.main(["--feature", "F-001", "--raiz", str(tmp_path)]) == 0


# --- R1, R2, R42: los valores del payload, solo en el taller ------------------

#: En un proyecto, `rigor.json` es suyo: uno sin `express` es válido (R42).
es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="harness/rigor.json es el del proyecto, no el del payload",
)


def _payload() -> dict:
    return cargar_rigor(RAIZ / "harness" / "rigor.json")


@es_el_taller
def test_f040_r1_el_payload_declara_express() -> None:
    nivel = _payload()["niveles"]["express"]

    assert (nivel["fase_red"], nivel["cobertura"], nivel["mutacion"]) == (False, False, False)
    assert nivel["informativas"] == ["cobertura"]
    assert nivel["spec"] is False
    assert nivel["limites"]["ficheros"] == 3 and nivel["limites"]["lineas"] == 150
    assert nivel["limites"]["no_cuentan"] == [
        "progress/**", "specs/**", "BACKLOG.md", "harness/features.json",
        "tests/**", "**/tests/**"]
    assert nivel["tamano"] == {"impl": 40, "review": 60}


@es_el_taller
def test_f040_r2_estandar_informa_de_la_mutacion_y_conserva_la_muestra() -> None:
    rigor = _payload()
    nivel = rigor["niveles"]["estandar"]

    # `e2e` en `informativas` es de F-059 y lo vigila `test_f059_rigor.py`.
    informativas = [puerta for puerta in nivel["informativas"] if puerta != "e2e"]
    assert nivel["mutacion"] is False and informativas == ["mutacion"]
    assert modulo.max_mutantes_nivel("estandar", rigor) == 20
    assert modulo.semilla_nivel("estandar", rigor) == 20260820
    assert nivel["fase_red"] is True and nivel["cobertura"] is True


#: Claves que F-058 cambió a propósito en `critico` (muestreo y umbral propio):
#: ese cambio lo vigila `test_f058_textos.py`, no este test de F-040.
CLAVES_DE_F058 = ("un_mutante_por_linea", "fraccion_mutantes", "min_mutantes",
                  "max_mutantes", "semilla", "umbral_cobertura")

#: Clave que F-059 añadió a `critico` (`informativas: ["e2e"]`): la vigila
#: `test_f059_rigor.py`.
CLAVES_DE_F059 = ("informativas",)


@es_el_taller
def test_f040_r2_lo_demas_no_cambia() -> None:
    rigor = _payload()

    assert rigor["nivel_por_defecto"] == "estandar"
    for nivel in ("documental", "critico"):
        declarado = {k: v for k, v in rigor["niveles"][nivel].items()
                     if k != "$doc" and k not in CLAVES_DE_F058 + CLAVES_DE_F059}
        esperado = {k: v for k, v in RIGOR_1_7_16["niveles"][nivel].items()
                    if k not in CLAVES_DE_F058 + CLAVES_DE_F059}
        assert declarado == esperado, nivel


@es_el_taller
def test_f040_r39_la_semilla_de_features_documenta_los_cuatro_niveles() -> None:
    datos = json.loads((RAIZ / "harness" / "features.json").read_text(encoding="utf-8"))

    for nivel in ("documental", "express", "estandar", "critico"):
        assert nivel in datos["$rigor_doc"], nivel


def test_f040_r39_un_features_json_existente_no_necesita_cambios() -> None:
    fichas = [
        {"id": "F-001", "status": "done", "sdd": True, "rigor": "critico"},
        {"id": "F-002", "status": "in_progress", "sdd": True},
        {"id": "F-003", "status": "pending", "sdd": False, "rigor": "documental"},
    ]
    rigor = {**RIGOR_1_7_16, "niveles": {
        **RIGOR_1_7_16["niveles"], "rapido": _rigor(spec=False)["niveles"]["rapido"]}}

    assert validar_features(fichas, rigor) == []


def test_f040_r42_un_rigor_sin_express_es_valido(tmp_path: Path) -> None:
    config = tmp_path / "rigor.json"
    config.write_text(json.dumps(RIGOR_1_7_16), encoding="utf-8")
    features = tmp_path / "features.json"
    features.write_text(
        json.dumps({"features": [{"id": "F-001", "rigor": "estandar"}]}), encoding="utf-8")

    assert modulo.main(["--validar", "--config", str(config), "--features", str(features)]) == 0
