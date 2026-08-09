# tests/test_f015_rigor.py
"""F-015 · Niveles de rigor (R11, R14, R15, R16, R17, R19).

Sin red y sin BBDD: se leen ficheros del repositorio y estructuras en memoria.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from harness.rigor import (
    PUERTAS,
    cargar_features,
    cargar_rigor,
    exige,
    feature_de_rama,
    nivel_de_feature,
    supervivientes_maximos,
    timeout_mutacion,
    umbral_cobertura,
    validar_features,
)
from harness.rigor import main as rigor_main

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RIGOR = RAIZ / "harness" / "rigor.json"


@pytest.fixture
def rigor() -> dict:
    return cargar_rigor(RUTA_RIGOR)


# --- R11: el umbral vive en rigor.json, no cableado -------------------------


def test_f015_r11_umbral_solo_en_rigor_json(rigor: dict) -> None:
    umbral = umbral_cobertura(rigor)

    assert isinstance(umbral, int)
    assert 0 < umbral <= 100
    # Está en el fichero de configuración, no en el código.
    crudo = json.loads(RUTA_RIGOR.read_text(encoding="utf-8"))
    assert crudo["cobertura"]["umbral_lineas_cambiadas"] == umbral

    # Y no hay valor por defecto escondido en el código: si falta, se para.
    with pytest.raises(ValueError, match="umbral_lineas_cambiadas"):
        umbral_cobertura({"cobertura": {}})


def test_f015_r11_el_umbral_no_esta_en_el_codigo_del_arnes(rigor: dict) -> None:
    umbral = str(umbral_cobertura(rigor))
    modulos = sorted((RAIZ / "harness").glob("*.py"))

    assert modulos, "el arnés debe tener herramientas en harness/"
    for modulo in modulos:
        texto = modulo.read_text(encoding="utf-8")
        assert f"= {umbral}" not in texto, modulo.name


def test_f015_r11_configuracion_invalida_se_rechaza(tmp_path: Path) -> None:
    roto = tmp_path / "rigor.json"
    roto.write_text('{"nivel_por_defecto": "inexistente"}', encoding="utf-8")

    with pytest.raises(ValueError):
        cargar_rigor(roto)


def test_f015_r11_timeout_de_mutacion_tambien_es_configuracion(rigor: dict) -> None:
    assert timeout_mutacion(rigor) > 0
    # Un segundo es absurdo pero legítimo; cero o negativo, no.
    assert timeout_mutacion({"mutacion": {"timeout_por_mutante_s": 1}}) == 1
    with pytest.raises(ValueError, match="timeout_por_mutante_s"):
        timeout_mutacion({"mutacion": {"timeout_por_mutante_s": 0}})
    with pytest.raises(ValueError, match="timeout_por_mutante_s"):
        timeout_mutacion({"mutacion": {"timeout_por_mutante_s": -5}})


@pytest.mark.parametrize(
    "contenido",
    [
        "{esto no es json",
        "[1, 2, 3]",
        '{"nivel_por_defecto": "critico"}',
        '{"nivel_por_defecto": "critico", "niveles": {"critico": "no soy objeto"}}',
        '{"nivel_por_defecto": "critico", "niveles": {"critico": {"fase_red": "si"}}}',
        '{"nivel_por_defecto": "critico", "niveles": {}}',
    ],
)
def test_f015_r11_toda_configuracion_incoherente_para_el_arnes(
    tmp_path: Path, contenido: str
) -> None:
    roto = tmp_path / "rigor.json"
    roto.write_text(contenido, encoding="utf-8")

    with pytest.raises(ValueError):
        cargar_rigor(roto)


def test_f015_r11_sin_fichero_de_configuracion_tambien_para(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No existe"):
        cargar_rigor(tmp_path / "no_existe.json")


# --- R14 y R17: los niveles y las puertas nuevas en CHECKPOINTS.md ----------


def checkpoints() -> str:
    return (RAIZ / "CHECKPOINTS.md").read_text(encoding="utf-8")


def test_f015_r14_checkpoints_define_los_tres_niveles_y_sus_exigencias(
    rigor: dict,
) -> None:
    texto = checkpoints()
    minusculas = texto.lower()

    assert "niveles de rigor" in minusculas
    # Los tres niveles, con los mismos nombres que usa la configuración.
    for nivel in rigor["niveles"]:
        assert nivel in minusculas, nivel
    # Y qué exige exactamente cada uno.
    for exigencia in ("trazable", "red", "cobertura", "mutaci", "manual"):
        assert exigencia in minusculas, exigencia
    # El nivel más exigente se aplica por omisión.
    assert rigor["nivel_por_defecto"] in minusculas
    # Existe el bloque que comprueba que el rigor declarado se cumple.
    assert "C4 bis" in texto


def test_f015_r14_una_feature_documental_no_puede_requerir_mutacion() -> None:
    texto = checkpoints()
    bloque = texto[texto.lower().index("niveles de rigor") :][:2000].lower()
    fila = next(
        linea for linea in bloque.splitlines() if linea.startswith("| **documental**")
    )

    assert "sin" in fila and "mutaci" in fila


def test_f015_r17_na_sin_justificacion_prohibido_tambien_en_puertas_nuevas() -> None:
    minusculas = checkpoints().lower()

    # La nota de N/A tiene que cubrir las puertas nuevas por su nombre.
    assert "n/a" in minusculas
    for puerta in ("mutaci", "fase red", "cobertura"):
        assert puerta in minusculas, puerta
    assert "justificar" in minusculas or "justificaci" in minusculas
    # Y decir qué pasa con un N/A sin motivo.
    assert "checkbox vac" in minusculas


# --- R16: el reviewer valida contra el nivel declarado ----------------------


def test_f015_r16_reviewer_valida_contra_el_nivel_de_rigor(rigor: dict) -> None:
    protocolo = re.sub(
        r"\s+",
        " ",
        (RAIZ / ".claude" / "agents" / "reviewer.md").read_text(encoding="utf-8").lower(),
    )

    # Resuelve el nivel de la feature antes de juzgar nada.
    assert "nivel de rigor" in protocolo
    assert "features.json" in protocolo
    assert rigor["nivel_por_defecto"] in protocolo
    # Y exige las evidencias que ese nivel pida.
    assert "progress/mutacion_f-xxx.md" in protocolo
    assert "fase red" in protocolo
    assert "evidencias" in protocolo
    assert "c4 bis" in protocolo
    # Ningún N/A sin justificación escrita.
    assert "n/a" in protocolo
    assert "justificaci" in protocolo


# --- R19: las herramientas del arnés son genéricas --------------------------

#: Nada de esto puede aparecer en las herramientas: se portan tal cual a
#: cualquier repositorio, y una mención al proyecto de origen las ata a él.
PALABRAS_DEL_PROYECTO = (
    r"sigrid",
    r"datamart",
    r"ruesma",
    r"azure",
    r"postgres",
    r"psql",
    r"power\s*bi",
    r"\betl\b",
    r"\bstg\b",
    r"\bmart\b",
    r"\bcierre\b",
    r"\bobra\b",
    r"\bobras\b",
    r"\bamb\b",
    r"\bfas\b",
    r"f-0\d\d",
)


def test_f015_r19_herramientas_del_arnes_sin_menciones_especificas() -> None:
    ficheros = [*sorted((RAIZ / "harness").glob("*.py")), RUTA_RIGOR]

    assert len(ficheros) >= 5, "faltan herramientas que revisar"
    for fichero in ficheros:
        texto = fichero.read_text(encoding="utf-8").lower()
        for patron in PALABRAS_DEL_PROYECTO:
            assert not re.search(patron, texto), f"{fichero.name} menciona {patron}"


# --- R15: resolución del nivel ----------------------------------------------


def test_f015_r15_sin_rigor_declarado_se_aplica_el_mas_exigente(rigor: dict) -> None:
    por_defecto = rigor["nivel_por_defecto"]

    # No declarar nivel NO es la vía fácil: cae en el más exigente.
    assert nivel_de_feature({"id": "F-042"}, rigor) == por_defecto
    assert nivel_de_feature({"id": "F-042", "rigor": None}, rigor) == por_defecto
    # Un valor inválido tampoco relaja nada.
    assert nivel_de_feature({"id": "F-042", "rigor": "flojito"}, rigor) == por_defecto
    # Y el más exigente exige las tres puertas.
    for puerta in PUERTAS:
        assert exige(por_defecto, puerta, rigor) is True
    assert supervivientes_maximos(por_defecto, rigor) == 0


def test_f015_r15_cada_nivel_declara_lo_que_exige(rigor: dict) -> None:
    assert nivel_de_feature({"id": "F-008", "rigor": "documental"}, rigor) == "documental"

    # Una feature documental no puede requerir mutación (R14).
    assert exige("documental", "mutacion", rigor) is False
    assert exige("documental", "cobertura", rigor) is False
    assert exige("documental", "fase_red", rigor) is False

    # El nivel estándar sí, pero admite supervivientes documentados.
    for puerta in PUERTAS:
        assert exige("estandar", puerta, rigor) is True
    assert supervivientes_maximos("estandar", rigor) is None


def test_f015_r15_lo_desconocido_se_considera_exigido(rigor: dict) -> None:
    # Ni una puerta que no está en la tabla...
    assert exige("documental", "puerta_que_no_existe", rigor) is True
    # ...ni un nivel inventado relajan nada.
    assert exige("nivel_que_no_existe", "mutacion", rigor) is True
    assert supervivientes_maximos("nivel_que_no_existe", rigor) is None


def test_f015_r15_validacion_detecta_niveles_invalidos(rigor: dict) -> None:
    features = [
        {"id": "F-001", "rigor": "estandar"},
        {"id": "F-002"},  # sin declarar: legítimo, se aplica el más exigente
        {"id": "F-003", "rigor": "flojito"},
        {"id": "F-004", "rigor": 7},
    ]

    errores = validar_features(features, rigor)

    assert len(errores) == 2
    assert any("F-003" in e and "flojito" in e for e in errores)
    assert any("F-004" in e for e in errores)


def test_f015_r15_las_features_del_repositorio_declaran_niveles_validos(
    rigor: dict,
) -> None:
    datos = json.loads((RAIZ / "harness" / "features.json").read_text(encoding="utf-8"))

    assert validar_features(datos["features"], rigor) == []


def test_f015_r15_init_valida_valores_de_rigor(tmp_path: Path) -> None:
    # (a) El portero del arnés llama a la validación.
    guion = (RAIZ / "harness" / "init.sh").read_text(encoding="utf-8")
    assert "harness.rigor" in guion
    assert "--validar" in guion

    # (b) Y esa validación rechaza de verdad un features.json con rigor inválido.
    features = tmp_path / "features.json"
    features.write_text(
        json.dumps({"features": [{"id": "F-042", "rigor": "flojito"}]}),
        encoding="utf-8",
    )

    codigo = rigor_main(
        ["--validar", "--config", str(RUTA_RIGOR), "--features", str(features)]
    )

    assert codigo == 1


def test_f015_r15_la_validacion_para_si_la_configuracion_es_ilegible(
    tmp_path: Path,
) -> None:
    assert rigor_main(["--validar", "--config", str(tmp_path / "no_existe.json")]) == 1


def test_f015_r15_sin_inventario_no_hay_features_que_validar(tmp_path: Path) -> None:
    assert cargar_features(tmp_path / "no_existe.json") == []
    raro = tmp_path / "raro.json"
    raro.write_text('{"features": "no soy una lista"}', encoding="utf-8")
    assert cargar_features(raro) == []


def test_f015_r15_la_feature_en_curso_se_localiza_por_rama() -> None:
    features = [
        {"id": "F-042", "branch": "feature/F-042-x", "status": "done"},
        {"id": "F-043", "branch": "feature/F-043-y", "status": "in_progress"},
    ]

    assert feature_de_rama("feature/F-042-x", features)["id"] == "F-042"
    # Una rama que no está declarada cae en la feature en curso...
    assert feature_de_rama("feature/F-999-z", features)["id"] == "F-043"
    # ...y si tampoco la hay, no se inventa ninguna.
    assert feature_de_rama("feature/F-999-z", [features[0]]) is None
    assert feature_de_rama("", []) is None


def test_f015_r15_la_validacion_pasa_con_el_inventario_real() -> None:
    codigo = rigor_main(
        [
            "--validar",
            "--config",
            str(RUTA_RIGOR),
            "--features",
            str(RAIZ / "harness" / "features.json"),
        ]
    )

    assert codigo == 0
