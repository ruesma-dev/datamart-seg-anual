# tests/test_f063_capa_local.py
"""F-063: `harness/rigor.local.json`, la capa de rigor que el instalador no pisa.

Los tests usan el módulo por atributo (`modulo.fusionar`, no `from ... import`)
a propósito: así, en la fase RED, cada test cae por su causa y no todo el
fichero por un import.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from harness import rigor as modulo

RAIZ = Path(__file__).resolve().parents[1]
RIGOR_PUBLICADO = RAIZ / "harness" / "rigor.json"


def _base() -> dict:
    return json.loads(RIGOR_PUBLICADO.read_text(encoding="utf-8"))


def _escribir(directorio: Path, base: dict | None = None, local: object = None,
              local_crudo: str | None = None) -> Path:
    """`rigor.json` (el publicado si no se da otro) y, opcional, su capa local."""
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / "rigor.json"
    ruta.write_text(json.dumps(_base() if base is None else base), encoding="utf-8")
    if local_crudo is not None:
        (directorio / "rigor.local.json").write_text(local_crudo, encoding="utf-8")
    elif local is not None:
        (directorio / "rigor.local.json").write_text(json.dumps(local), encoding="utf-8")
    return ruta


def _features(directorio: Path) -> Path:
    ruta = directorio / "features.json"
    ruta.write_text(json.dumps({"features": []}), encoding="utf-8")
    return ruta


# --- R1: sin capa, nada cambia ----------------------------------------------


def test_f063_r1_sin_capa_devuelve_lo_mismo_que_el_fichero(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path)

    assert modulo.cargar_rigor(ruta) == _base()


def test_f063_r1_sin_capa_cargar_capas_no_declara_capa(tmp_path: Path) -> None:
    capas = modulo.cargar_capas(_escribir(tmp_path))

    assert capas.ruta_local is None
    assert capas.claves_locales == ()
    assert capas.rigor == _base()


# --- R3-R5: la capa local pisa clave a clave ---------------------------------


def test_f063_r3_r5_fusion_sube_un_umbral_sin_copiar_nada_mas(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, local={"niveles": {"critico": {"umbral_cobertura": 95}}})

    rigor = modulo.cargar_rigor(ruta)

    esperado = _base()
    esperado["niveles"]["critico"]["umbral_cobertura"] = 95
    assert rigor == esperado


def test_f063_r3_fusion_tambien_con_config_en_otro_directorio(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path / "otro" / "sitio",
                     local={"cobertura": {"umbral_lineas_cambiadas": 85}})

    assert modulo.cargar_rigor(str(ruta))["cobertura"]["umbral_lineas_cambiadas"] == 85


def test_f063_r4_fusion_recursiva_a_cualquier_profundidad() -> None:
    base = {"a": {"b": {"c": 1, "d": 2}, "e": 3}, "f": 4}
    local = {"a": {"b": {"c": 10}}}

    assert modulo.fusionar(base, local) == {"a": {"b": {"c": 10, "d": 2}, "e": 3}, "f": 4}


@pytest.mark.parametrize("valor", [[1], 7, "x", None, True],
                         ids=["lista", "entero", "texto", "null", "booleano"])
def test_f063_r4_fusion_lo_que_no_es_objeto_sustituye_entero(valor) -> None:
    base = {"a": {"b": 1}, "l": [1, 2, 3]}

    fusion = modulo.fusionar(base, {"a": valor, "l": valor})

    assert fusion == {"a": valor, "l": valor}


def test_f063_r4_fusion_objeto_local_sobre_escalar_base_sustituye() -> None:
    assert modulo.fusionar({"a": 1}, {"a": {"b": 2}}) == {"a": {"b": 2}}


def test_f063_r4_fusion_no_muta_las_entradas() -> None:
    base = {"a": {"b": {"c": 1}}, "l": [1]}
    local = {"a": {"b": {"d": 2}}, "n": {"x": [5]}}
    copia_base, copia_local = copy.deepcopy(base), copy.deepcopy(local)

    fusion = modulo.fusionar(base, local)
    fusion["a"]["b"]["c"] = 99
    fusion["n"]["x"].append(6)
    fusion["l"].append(2)

    assert base == copia_base
    assert local == copia_local


def test_f063_r5_fusion_limites_conserva_las_claves_hermanas(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, local={"niveles": {"express": {"limites": {"lineas": 200}}}})

    limites = modulo.cargar_rigor(ruta)["niveles"]["express"]["limites"]

    assert limites["lineas"] == 200
    assert limites["ficheros"] == 3
    assert limites["no_cuentan"] == _base()["niveles"]["express"]["limites"]["no_cuentan"]


def test_f063_r4_fusion_una_lista_sustituye_entera_en_la_carga(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, local={"niveles": {"estandar": {"informativas": ["mutacion"]}}})

    assert modulo.cargar_rigor(ruta)["niveles"]["estandar"]["informativas"] == ["mutacion"]


# --- R6: niveles nuevos, validados completos ---------------------------------


def test_f063_r6_fusion_anade_un_nivel_nuevo_completo(tmp_path: Path) -> None:
    nuevo = {"fase_red": True, "cobertura": True, "mutacion": True, "umbral_cobertura": 99}
    ruta = _escribir(tmp_path, local={"niveles": {"paranoico": nuevo}})

    rigor = modulo.cargar_rigor(ruta)

    assert rigor["niveles"]["paranoico"] == nuevo
    assert set(rigor["niveles"]) == set(_base()["niveles"]) | {"paranoico"}


def test_f063_r6_fusion_nivel_nuevo_incompleto_es_invalido(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, local={"niveles": {"paranoico": {"fase_red": True}}})

    with pytest.raises(modulo.CapaLocalInvalida, match="mutacion|cobertura"):
        modulo.cargar_rigor(ruta)


# --- R12: si la base está rota, el error es el de siempre ---------------------


def test_f063_r12_base_invalida_da_el_error_de_hoy_con_capa(tmp_path: Path) -> None:
    base = _base()
    base["niveles"]["critico"]["fase_red"] = "si"
    ruta = _escribir(tmp_path, base=base, local={"nivel_por_defecto": "critico"})

    with pytest.raises(ValueError) as error:
        modulo.cargar_rigor(ruta)

    assert type(error.value) is ValueError
    assert "fase_red" in str(error.value)


def test_f063_r12_base_invalida_con_capa_rota_sigue_dando_el_error_de_la_base(
    tmp_path: Path,
) -> None:
    ruta = _escribir(tmp_path, base={"niveles": {}}, local_crudo="{roto")

    with pytest.raises(ValueError) as error:
        modulo.cargar_rigor(ruta)

    assert type(error.value) is ValueError
    assert "niveles" in str(error.value)


# --- R8: la capa local rota nunca se ignora -----------------------------------


@pytest.mark.parametrize("crudo", ["{roto", "[1, 2]", '"texto"', ""],
                         ids=["json roto", "lista", "texto", "vacio"])
def test_f063_r8_invalida_json_roto_o_no_objeto(tmp_path: Path, crudo: str) -> None:
    ruta = _escribir(tmp_path, local_crudo=crudo)

    with pytest.raises(modulo.CapaLocalInvalida, match="rigor.local.json"):
        modulo.cargar_rigor(ruta)


def test_f063_r8_invalida_es_un_value_error() -> None:
    assert issubclass(modulo.CapaLocalInvalida, ValueError)


# --- R9: lista blanca de claves, con la ruta punteada --------------------------


@pytest.mark.parametrize(("local", "ruta_clave"), [
    ({"niveles": {"critico": {"umbral_cobertra": 95}}}, "niveles.critico.umbral_cobertra"),
    ({"nivel_por_defecta": "critico"}, "nivel_por_defecta"),
    ({"mutacion": {"incremental": {"control": 3}}}, "mutacion.incremental.control"),
    ({"niveles": {"express": {"limites": {"linea": 9}}}}, "niveles.express.limites.linea"),
    ({"tamano": {"spec": 9}}, "tamano.spec"),
    ({"niveles": {"critico": {"tamano": {"tasks": 9}}}}, "niveles.critico.tamano.tasks"),
], ids=["nivel", "raiz", "incremental", "limites", "tamano", "tamano del nivel"])
def test_f063_r9_invalida_clave_desconocida_con_ruta(tmp_path: Path, local, ruta_clave) -> None:
    ruta = _escribir(tmp_path, local=local)

    with pytest.raises(modulo.CapaLocalInvalida) as error:
        modulo.cargar_rigor(ruta)

    assert ruta_clave in str(error.value)
    assert "rigor.local.json" in str(error.value)


def test_f063_r9_doc_se_admite_en_todo_objeto(tmp_path: Path) -> None:
    local = {"$doc": "a", "cobertura": {"$doc": "b"}, "mutacion": {"$doc": "c",
             "incremental": {"$doc": "d"}}, "tamano": {"$doc": "e"},
             "niveles": {"critico": {"$doc": "g", "tamano": {"$doc": "i"}},
                         "express": {"limites": {"$doc": "h"}}}}
    ruta = _escribir(tmp_path, local=local)

    assert modulo.cargar_rigor(ruta)["niveles"]["critico"]["$doc"] == "g"


def test_f063_r9_doc_en_el_mapa_de_niveles_seria_un_nivel_y_se_rechaza(tmp_path: Path) -> None:
    """En `niveles` cada clave es un nivel: un `$doc` ahí lo tomaría por uno."""
    ruta = _escribir(tmp_path, local={"niveles": {"$doc": "f"}})

    with pytest.raises(modulo.CapaLocalInvalida, match=r"'niveles\.\$doc' debe ser un objeto"):
        modulo.cargar_rigor(ruta)


# --- R10: tipos y rangos estrictos --------------------------------------------


_TIPOS_ERRONEOS = [
    ({"niveles": {"critico": {"umbral_cobertura": True}}}, "niveles.critico.umbral_cobertura", "True"),
    ({"niveles": {"critico": {"umbral_cobertura": 101}}}, "niveles.critico.umbral_cobertura", "101"),
    ({"niveles": {"critico": {"umbral_cobertura": None}}}, "niveles.critico.umbral_cobertura", "None"),
    ({"niveles": {"critico": {"mutacion": "false"}}}, "niveles.critico.mutacion", "'false'"),
    ({"cobertura": {"umbral_lineas_cambiadas": -1}}, "cobertura.umbral_lineas_cambiadas", "-1"),
    ({"mutacion": {"timeout_por_mutante_s": True}}, "mutacion.timeout_por_mutante_s", "True"),
    ({"mutacion": {"workers": 0}}, "mutacion.workers", "0"),
    ({"mutacion": {"incremental": {"control_fraccion": 0}}}, "mutacion.incremental.control_fraccion", "0"),
    ({"mutacion": {"incremental": {"control_minimo": 0}}}, "mutacion.incremental.control_minimo", "0"),
    ({"tamano": {"impl": 0}}, "tamano.impl", "0"),
    ({"niveles": {"express": {"tamano": {"review": False}}}}, "niveles.express.tamano.review", "False"),
    ({"niveles": {"critico": {"informativas": ["red"]}}}, "niveles.critico.informativas", "['red']"),
    ({"niveles": {"critico": {"informativas": "e2e"}}}, "niveles.critico.informativas", "'e2e'"),
    ({"niveles": {"critico": {"supervivientes_maximos": -1}}}, "niveles.critico.supervivientes_maximos", "-1"),
    ({"niveles": {"critico": {"max_mutantes": 0}}}, "niveles.critico.max_mutantes", "0"),
    ({"niveles": {"critico": {"semilla": "1"}}}, "niveles.critico.semilla", "'1'"),
    ({"niveles": {"critico": {"semilla": True}}}, "niveles.critico.semilla", "True"),
    ({"niveles": {"critico": {"min_mutantes": None}}}, "niveles.critico.min_mutantes", "None"),
    ({"niveles": {"critico": {"fraccion_mutantes": 1.5}}}, "niveles.critico.fraccion_mutantes", "1.5"),
    ({"niveles": {"critico": {"un_mutante_por_linea": 1}}}, "niveles.critico.un_mutante_por_linea", "1"),
    ({"niveles": {"critico": {"spec": None}}}, "niveles.critico.spec", "None"),
    ({"niveles": {"critico": {"e2e": "si"}}}, "niveles.critico.e2e", "'si'"),
    ({"niveles": {"express": {"limites": {"lineas": True}}}}, "niveles.express.limites.lineas", "True"),
    ({"niveles": {"express": {"limites": {"no_cuentan": [1]}}}}, "niveles.express.limites.no_cuentan", "[1]"),
    ({"nivel_por_defecto": 3}, "nivel_por_defecto", "3"),
    ({"niveles": {"critico": {"limites": 5}}}, "niveles.critico.limites", "5"),
    ({"niveles": {"critico": 5}}, "niveles.critico", "5"),
    ({"niveles": None}, "niveles", "None"),
    ({"cobertura": 80}, "cobertura", "80"),
    ({"mutacion": {"incremental": []}}, "mutacion.incremental", "[]"),
    ({"niveles": {"critico": {"$doc": 5}}}, "niveles.critico.$doc", "5"),
]


@pytest.mark.parametrize(("local", "ruta_clave", "recibido"), _TIPOS_ERRONEOS,
                         ids=[f"{caso[1]}={caso[2]}" for caso in _TIPOS_ERRONEOS])
def test_f063_r10_invalida_tipo_o_rango(tmp_path: Path, local, ruta_clave, recibido) -> None:
    ruta = _escribir(tmp_path, local=local)

    with pytest.raises(modulo.CapaLocalInvalida) as error:
        modulo.cargar_rigor(ruta)

    mensaje = str(error.value)
    assert f"'{ruta_clave}'" in mensaje
    assert recibido in mensaje
    assert "debe ser" in mensaje


_LIMITES_VALIDOS = [
    {"niveles": {"critico": {"max_mutantes": None}}},
    {"niveles": {"critico": {"semilla": None}}},
    {"niveles": {"critico": {"semilla": 0}}},
    {"niveles": {"critico": {"supervivientes_maximos": None}}},
    {"niveles": {"critico": {"supervivientes_maximos": 0}}},
    {"niveles": {"critico": {"fraccion_mutantes": 1}}},
    {"niveles": {"critico": {"umbral_cobertura": 0}}},
    {"niveles": {"critico": {"umbral_cobertura": 100}}},
    {"niveles": {"critico": {"informativas": []}}},
    {"niveles": {"express": {"limites": {"ficheros": 1, "no_cuentan": []}}}},
    {"mutacion": {"incremental": {"control_fraccion": 0.25, "control_minimo": 1}}},
    {"mutacion": {"workers": 1, "timeout_por_mutante_s": 1}},
    {"cobertura": {"umbral_lineas_cambiadas": 100}, "tamano": {"impl": 1}},
]


@pytest.mark.parametrize("local", _LIMITES_VALIDOS,
                         ids=[json.dumps(caso) for caso in _LIMITES_VALIDOS])
def test_f063_r10_valores_limite_que_si_valen(tmp_path: Path, local) -> None:
    ruta = _escribir(tmp_path, local=local)

    assert modulo.cargar_rigor(ruta) == modulo.fusionar(_base(), local)


# --- R11: válidas por separado, inválida la fusión ----------------------------


@pytest.mark.parametrize("local", [
    {"niveles": {"critico": {"min_mutantes": 400}}},
    {"niveles": {"critico": {"informativas": ["mutacion"]}}},
    {"nivel_por_defecto": "inexistente"},
], ids=["min sobre max", "informativa exigida", "por defecto inexistente"])
def test_f063_r11_invalida_la_fusion_lo_dice(tmp_path: Path, local) -> None:
    ruta = _escribir(tmp_path, local=local)

    with pytest.raises(modulo.CapaLocalInvalida) as error:
        modulo.cargar_rigor(ruta)

    mensaje = str(error.value)
    assert "fusión" in mensaje
    assert "rigor.json + " in mensaje
    assert "rigor.local.json" in mensaje


# --- R14: la lista blanca cubre todo el rigor.json publicado -------------------


def _rutas(datos: dict, prefijo: str = "") -> list[str]:
    rutas = []
    for clave, valor in datos.items():
        if clave == "$doc":
            continue
        nombre = "*" if prefijo == "niveles." else clave
        ruta = f"{prefijo}{nombre}"
        if isinstance(valor, dict):
            rutas.extend(_rutas(valor, ruta + "."))
        else:
            rutas.append(ruta)
    return rutas


def _en_esquema(ruta: str) -> bool:
    nodo = modulo.ESQUEMA_LOCAL
    for parte in ruta.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return False
        nodo = nodo[parte]
    return not isinstance(nodo, dict)


def test_f063_r14_lista_blanca_cubre_cada_clave_del_publicado() -> None:
    fuera = [ruta for ruta in _rutas(_base()) if not _en_esquema(ruta)]

    assert fuera == [], f"claves de rigor.json fuera de ESQUEMA_LOCAL: {fuera}"


def test_f063_r14_lista_blanca_el_publicado_entero_vale_como_capa(tmp_path: Path) -> None:
    modulo.validar_capa_local(_base(), tmp_path / "rigor.local.json")


def test_f063_r14_lista_blanca_tamano_sale_de_claves_tamano() -> None:
    assert set(modulo.ESQUEMA_LOCAL["tamano"]) == set(modulo.CLAVES_TAMANO)
    assert set(modulo.ESQUEMA_LOCAL["niveles"]["*"]["tamano"]) == set(modulo.CLAVES_TAMANO)


# --- R13, R15, R16 y R1: lo que dice `--validar` -------------------------------

_LINEA_NIVELES = (
    "    niveles: critico, documental, estandar, express; por defecto estandar; "
    "umbral de cobertura 80%; pisan el global: critico 90%\n"
)


def _validar_en(tmp_path: Path, monkeypatch, capsys, local=None, local_crudo=None):
    monkeypatch.chdir(tmp_path)
    _escribir(tmp_path / "harness", local=local, local_crudo=local_crudo)
    _features(tmp_path / "harness")
    codigo = modulo.main(["--validar"])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def test_f063_r1_validar_sin_capa_salida_identica(tmp_path, monkeypatch, capsys) -> None:
    assert _validar_en(tmp_path, monkeypatch, capsys) == (0, _LINEA_NIVELES, "")


def test_f063_r15_validar_lista_las_claves_de_la_capa(tmp_path, monkeypatch, capsys) -> None:
    local = {"$doc": "afinado", "niveles": {"critico": {"umbral_cobertura": 95, "$doc": "x"},
                                            "express": {"limites": {"lineas": 200}}},
             "cobertura": {"umbral_lineas_cambiadas": 85}}

    codigo, salida, error = _validar_en(tmp_path, monkeypatch, capsys, local=local)

    assert (codigo, error) == (0, "")
    assert salida == _LINEA_NIVELES.replace("80%", "85%").replace("critico 90%", "critico 95%") + (
        "    capa local (harness/rigor.local.json): cobertura.umbral_lineas_cambiadas, "
        "niveles.critico.umbral_cobertura, niveles.express.limites.lineas\n"
    )


def test_f063_r15_validar_marca_el_nivel_nuevo_una_vez(tmp_path, monkeypatch, capsys) -> None:
    local = {"niveles": {"paranoico": {"fase_red": True, "cobertura": True, "mutacion": True,
                                       "limites": {"ficheros": 1, "lineas": 9}},
                         "estandar": {"informativas": ["mutacion"]}}}

    codigo, salida, _ = _validar_en(tmp_path, monkeypatch, capsys, local=local)

    assert codigo == 0
    assert salida.splitlines()[-1] == (
        "    capa local (harness/rigor.local.json): niveles.estandar.informativas, "
        "niveles.paranoico (nivel nuevo)"
    )


@pytest.mark.parametrize("local", [{}, {"$doc": "nada que afinar"}], ids=["vacia", "solo doc"])
def test_f063_r16_validar_capa_sin_claves(tmp_path, monkeypatch, capsys, local) -> None:
    codigo, salida, _ = _validar_en(tmp_path, monkeypatch, capsys, local=local)

    assert codigo == 0
    assert salida == _LINEA_NIVELES + "    capa local (harness/rigor.local.json): sin claves\n"


@pytest.mark.parametrize(("local", "crudo", "motivo"), [
    (None, "{roto", "no es JSON válido"),
    ({"niveles": {"critico": {"umbral_cobertra": 95}}}, None, "niveles.critico.umbral_cobertra"),
    ({"nivel_por_defecto": "nada"}, None, "fusión"),
], ids=["json", "clave", "fusion"])
def test_f063_r13_validar_capa_invalida_sale_con_1(tmp_path, monkeypatch, capsys,
                                                   local, crudo, motivo) -> None:
    codigo, salida, error = _validar_en(tmp_path, monkeypatch, capsys, local=local,
                                        local_crudo=crudo)

    assert codigo == 1
    assert salida == ""
    assert motivo in error
    assert "harness/rigor.local.json" in error


def test_f063_r15_claves_locales_funcion_pura() -> None:
    base = {"niveles": {"critico": {"fase_red": True}}, "tamano": {"impl": 1}}
    local = {"$doc": "x", "tamano": {"impl": 2, "$doc": "y"}, "cobertura": {},
             "niveles": {"critico": {"limites": {"no_cuentan": ["a"]}},
                         "nuevo": {"fase_red": True}}}

    assert modulo.claves_locales(local, base) == (
        "niveles.critico.limites.no_cuentan", "niveles.nuevo (nivel nuevo)", "tamano.impl",
    )


# --- R18: todo consumidor ve la fusión -----------------------------------------


def test_f063_r18_consumidor_ninguno_lee_rigor_json_por_su_cuenta() -> None:
    import re

    patron = re.compile(r"(json\.loads?|read_text|open)\([^)]*rigor", re.IGNORECASE)
    culpables = [
        f"{fichero.name}:{numero}"
        for fichero in sorted((RAIZ / "harness").glob("*.py"))
        if fichero.name != "rigor.py"
        for numero, linea in enumerate(fichero.read_text(encoding="utf-8").splitlines(), 1)
        if patron.search(linea)
    ]

    assert culpables == []


def _repo_con_capa(tmp_path: Path, local=None, local_crudo=None) -> Path:
    _escribir(tmp_path / "harness", local=local, local_crudo=local_crudo)
    (tmp_path / "harness" / "features.json").write_text(json.dumps({"features": [
        {"id": "F-900", "status": "in_progress", "rigor": "critico",
         "branch": "feature/F-900-x"}]}), encoding="utf-8")
    return tmp_path


def test_f063_r18_consumidor_tamano_aplica_el_tope_de_la_capa(tmp_path, capsys) -> None:
    from harness import tamano

    raiz = _repo_con_capa(tmp_path, local={"niveles": {"critico": {"tamano": {"impl": 2}}}})
    (raiz / "progress").mkdir()
    (raiz / "progress" / "impl_F-900.md").write_text("a\nb\nc\n", encoding="utf-8")

    assert tamano.main(["--feature", "F-900", "--raiz", str(raiz)]) == 1
    assert "3" in capsys.readouterr().err


def test_f063_r18_consumidor_tamano_ve_la_capa_invalida(tmp_path, capsys) -> None:
    from harness import tamano

    raiz = _repo_con_capa(tmp_path, local_crudo="{roto")

    assert tamano.main(["--feature", "F-900", "--raiz", str(raiz)]) == 2
    assert "rigor.local.json" in capsys.readouterr().out


@pytest.mark.parametrize("nombre", ["carril", "cobertura"])
def test_f063_r18_consumidor_con_config_ve_la_capa(tmp_path, capsys, nombre) -> None:
    import importlib

    consumidor = importlib.import_module(f"harness.{nombre}")
    raiz = _repo_con_capa(tmp_path, local={"niveles": {"critico": {"umbral_cobertra": 1}}})

    codigo = consumidor.main(["--config", str(raiz / "harness" / "rigor.json"),
                              "--features", str(raiz / "harness" / "features.json"),
                              "--raiz", str(raiz), "--base", "dev"])
    salida = capsys.readouterr()

    assert codigo != 0
    assert "niveles.critico.umbral_cobertra" in salida.out + salida.err


def test_f063_r18_consumidor_mutacion_ve_la_fusion(tmp_path, monkeypatch) -> None:
    from harness import mutacion

    local = {"mutacion": {"timeout_por_mutante_s": 7, "workers": 3},
             "niveles": {"critico": {"fraccion_mutantes": 0.5, "semilla": 11}}}
    monkeypatch.chdir(_repo_con_capa(tmp_path, local=local))

    regla, semilla, nivel = mutacion._regla_configurada("F-900")

    assert mutacion._timeout_configurado() == 7
    assert mutacion._workers_configurados() == 3
    assert (regla.fraccion, semilla, nivel) == (0.5, 11, "critico")
    assert mutacion._muestreo_configurado("F-900") == (300, 11, "critico")


# --- R19: la mutación no degrada con una capa inválida --------------------------


_LECTORES_DE_MUTACION = [
    ("_timeout_configurado", ()),
    ("_workers_configurados", ()),
    ("_regla_configurada", ("F-900",)),
    ("_muestreo_configurado", ("F-900",)),
]


@pytest.mark.parametrize(("lector", "argumentos"), _LECTORES_DE_MUTACION,
                         ids=[caso[0] for caso in _LECTORES_DE_MUTACION])
def test_f063_r19_mutacion_capa_invalida_no_degrada(tmp_path, monkeypatch, lector,
                                                     argumentos) -> None:
    from harness import mutacion

    monkeypatch.chdir(_repo_con_capa(tmp_path, local={"mutacion": {"workers": True}}))

    with pytest.raises(modulo.CapaLocalInvalida, match="mutacion.workers"):
        getattr(mutacion, lector)(*argumentos)


def test_f063_r19_mutacion_capa_invalida_no_degrada_el_control_incremental(
    tmp_path, monkeypatch,
) -> None:
    from harness import mutacion

    monkeypatch.chdir(_repo_con_capa(tmp_path, local_crudo="{roto"))
    monkeypatch.setattr(mutacion, "clasificar_delta", lambda raiz, sha: mutacion.DELTA_SOLO_TESTS)

    with pytest.raises(modulo.CapaLocalInvalida, match="rigor.local.json"):
        mutacion.decidir_incremental({"sha": "abc"}, ".", None, None, None, None)


def test_f063_r19_mutacion_otro_value_error_sigue_degradando(tmp_path, monkeypatch) -> None:
    from harness import mutacion

    monkeypatch.chdir(tmp_path)  # sin harness/rigor.json: ValueError de siempre

    assert mutacion._timeout_configurado() == mutacion.TIMEOUT_POR_DEFECTO
    assert mutacion._workers_configurados() is None
    assert mutacion._regla_configurada("F-900") == (None, None, None)
    assert mutacion._muestreo_configurado("F-900") == (None, None, None)


def test_f063_r19_mutacion_main_aborta_con_el_mensaje(tmp_path, monkeypatch, capsys) -> None:
    from harness import mutacion

    monkeypatch.chdir(_repo_con_capa(tmp_path, local={"niveles": {"critico": {"x": 1}}}))

    codigo = mutacion.main(["--feature", "F-900"])

    assert codigo == 2
    assert "niveles.critico.x" in capsys.readouterr().err


# --- T14: superviviente de la campaña de mutación -------------------------------


def test_f063_t14_capas_rigor_es_inmutable(tmp_path: Path) -> None:
    """Superviviente #3 (`frozen=True` -> `False`): el resultado de la carga no se
    reasigna por el camino; quien lo recibe no puede cambiar qué capa se leyó."""
    import dataclasses

    capas = modulo.cargar_capas(_escribir(tmp_path, local={}))

    with pytest.raises(dataclasses.FrozenInstanceError):
        capas.ruta_local = None  # type: ignore[misc]
