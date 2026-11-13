# tests/test_f040_textos.py
"""F-040: lo que los carriles de rigor le piden por escrito a cada agente.

`leader.md`, `reviewer.md`, `implementer.md` y `SPECS.md` son `arnes_puro`: viajan
siempre. `CHECKPOINTS.md` es `adaptado`: un proyecto que conserve el suyo ve un
único rojo que dice qué aceptar, y sus dependientes se saltan (patrón de F-055).
Los textos se comparan con los saltos de línea aplanados: el documento va
envuelto y una frase puede partirse en dos líneas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
LEADER = RAIZ / ".claude" / "agents" / "leader.md"
REVIEWER = RAIZ / ".claude" / "agents" / "reviewer.md"
IMPLEMENTER = RAIZ / ".claude" / "agents" / "implementer.md"
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
SPECS = RAIZ / "specs" / "SPECS.md"


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _plano(ruta: Path) -> str:
    return " ".join(_crudo(ruta).split())


def _seccion(ruta: Path, titulo: str) -> str:
    resto = _crudo(ruta).split(f"## {titulo}", 1)[1]
    return " ".join(resto.split("\n## ", 1)[0].split())


_INSTRUCCION_CHECKPOINTS = (
    "CHECKPOINTS.md no trae los carriles de F-040 (fila `express`, `estandar` sin "
    "mutación obligatoria y «Puertas informativas» en C4 bis): al actualizar el "
    "arnés, acepta esos bloques del diff de CHECKPOINTS.md"
)


def _motivo_checkpoints_viejo(texto: str) -> str | None:
    """El rojo de R41 si este CHECKPOINTS.md es de antes de F-040; o None."""
    partes = ("| **express** |", "**Puertas informativas.**",
              "**Mutación** (niveles que la exigen)")
    return None if all(parte in texto for parte in partes) else _INSTRUCCION_CHECKPOINTS


_MOTIVO_CHECKPOINTS_VIEJO = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))
checkpoints_de_f040 = pytest.mark.skipif(
    _MOTIVO_CHECKPOINTS_VIEJO is not None, reason=_MOTIVO_CHECKPOINTS_VIEJO or "")


def test_f040_r41_el_checkpoints_instalado_trae_los_carriles() -> None:
    motivo = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))

    assert motivo is None, motivo


# --- R26–R30: leader.md ------------------------------------------------------


def test_f040_r26_la_lista_de_comprobacion_tiene_sus_cuatro_preguntas() -> None:
    bloque = _seccion(LEADER, "Carril de rigor (PARADA 1)")

    for pregunta in ("producción, dinero, seguridad o un recurso compartido",
                     "ficheros y líneas", "`limites`",
                     "contrato público (API, esquema, formato de fichero)", "UI"):
        assert pregunta in bloque, pregunta


def test_f040_r26_que_descarta_el_carril() -> None:
    bloque = _seccion(LEADER, "Carril de rigor (PARADA 1)")

    assert "Un «sí» a la primera o a la tercera, o pasarse" in bloque
    assert "descarta `express`" in bloque


def test_f040_r27_parada_1_agrupada_y_de_una_en_una() -> None:
    bloque = _seccion(LEADER, "Carril de rigor (PARADA 1)")

    assert "en un solo mensaje" in bloque and "una fila por feature" in bloque
    assert "de una en una" in bloque
    assert "máximo de una feature activa no cambia" in bloque


def test_f040_r28_sube_solo_baja_solo_el_humano() -> None:
    bloque = _seccion(LEADER, "Carril de rigor (PARADA 1)")

    assert "sube solo, baja solo el humano" in bloque.lower()
    assert "PUERTA CARRIL" in bloque and "vuelves a la PARADA 1" in bloque
    assert "orden del humano" in bloque


def test_f040_r29_salta_el_estado_con_pasada_unica() -> None:
    texto = _plano(LEADER)
    vineta = texto.split("**El carril `express` salta `in_review`, pero nunca `human_review`.**")[1]
    vineta = vineta.split(" - **")[0]

    assert "pasada única" in vineta and "antes de la PARADA 2" in vineta
    assert "CHANGES_REQUESTED" in vineta and "sube de nivel" in vineta
    assert "sin segunda pasada" in vineta


def test_f040_r30_condicionado_a_que_rigor_json_lo_declare() -> None:
    bloque = _seccion(LEADER, "Carril de rigor (PARADA 1)")

    assert "si `harness/rigor.json` lo declara" in bloque


# --- R31–R33: CHECKPOINTS.md -------------------------------------------------


def _tabla_de_niveles(texto: str | None = None) -> dict[str, str]:
    texto = _crudo(CHECKPOINTS) if texto is None else texto
    return {li.split("**")[1]: li for li in texto.splitlines() if li.startswith("| **")}


@checkpoints_de_f040
def test_f040_r31_la_tabla_trae_express_y_estandar_sin_mutacion_obligatoria() -> None:
    filas = _tabla_de_niveles()

    assert "express" in filas
    assert "informativa" in filas["estandar"].lower()
    assert "supervivientes documentados y analizados" not in filas["estandar"]
    assert "campaña de mutación" in filas["critico"].lower()


@checkpoints_de_f040
def test_f040_r31_el_nivel_por_defecto_ya_no_promete_mutacion() -> None:
    texto = _plano(CHECKPOINTS)

    assert "con puertas de fase RED, cobertura y mutación" not in texto


@checkpoints_de_f040
def test_f040_r31_c4_bis_define_lo_informativo() -> None:
    bloque = _seccion(CHECKPOINTS, "C4 bis — El rigor declarado se cumple")
    definicion = bloque.split("**Puertas informativas.**")[1].split("- [ ]")[0]

    assert "se lanza" in definicion and "su resultado consta" in definicion
    assert "ni el resultado ni su ausencia bloquean" in definicion
    assert "- [ ] **Mutación** (niveles que la exigen)" in bloque


@checkpoints_de_f040
def test_f040_r31_rm5_ya_no_menciona_estandar() -> None:
    bloque = _seccion(CHECKPOINTS, "C4 bis — El rigor declarado se cumple")
    rm5 = bloque.split("**RM5")[1].split("- [ ]")[0]

    assert "`estandar`" not in rm5 and "`critico`" in rm5


@checkpoints_de_f040
def test_f040_r32_lo_que_recorre_el_reviewer_en_express() -> None:
    texto = _plano(CHECKPOINTS)

    assert ("C1, C2, C3, C5, un test por criterio `acceptance`, y C3 bis / C3 ter "
            "si aplican") in texto
    assert "C4 bis es N/A por nivel, sin más motivo" in texto


@checkpoints_de_f040
def test_f040_r33_fase_red_de_una_feature_que_subio_de_carril() -> None:
    bloque = _seccion(CHECKPOINTS, "C4 bis — El rigor declarado se cumple")
    fase_red = bloque.split("**Fase RED**")[1].split("- [ ]")[0]

    assert "subió de carril a medias" in fase_red
    assert "ruptura deliberada" in fase_red


# --- R34: reviewer.md --------------------------------------------------------


def test_f040_r34_recorrido_por_carril() -> None:
    bloque = _seccion(REVIEWER, "Recorrido por carril")

    assert "`express`" in bloque and "C1, C2, C3, C5" in bloque
    assert "sin RM1–RM7" in bloque and "sin análisis de supervivientes" in bloque
    assert "observación" in bloque
    assert "`critico`" in bloque and "como siempre" in bloque


def test_f040_r34_el_paso_6_remite_al_carril() -> None:
    paso = _plano(REVIEWER).split("6. Recorre", 1)[1].split(" 7. ", 1)[0]

    assert "Recorrido por carril" in paso


def test_f040_r34_el_punto_4_dice_que_hacer_con_lo_informativo() -> None:
    texto = _plano(REVIEWER).split("Validación contra el nivel de rigor", 1)[1]

    assert "Si la mutación es **informativa**" in texto
    assert "nada de eso bloquea" in texto


# --- R35: implementer.md -----------------------------------------------------


def test_f040_r35_plantilla_express_que_cabe_en_su_tope() -> None:
    bloque = _crudo(IMPLEMENTER).split("## Informe del carril `express`", 1)[1]
    plantilla = bloque.split("```")[1]

    for apartado in ("Hecho", "Ficheros", "Tests por `acceptance`",
                     "Salida de `init.sh`", "Pendiente"):
        assert apartado in plantilla, apartado
    assert len(plantilla.strip().splitlines()) <= 40


def test_f040_r35_el_tope_es_el_de_tu_nivel() -> None:
    assert "o el de tu nivel en `harness/rigor.json`" in _plano(IMPLEMENTER)


def test_f040_r35_la_campana_informativa_va_sin_analizar_supervivientes() -> None:
    texto = _plano(IMPLEMENTER)

    assert "Si es **informativa**" in texto
    assert "sin analizar supervivientes" in texto


# --- R36: SPECS.md -----------------------------------------------------------


def test_f040_r36_specs_dice_que_un_nivel_puede_declarar_topes_sin_numeros() -> None:
    frase = next(p for p in _plano(SPECS).split(". ") if "topes propios" in p)

    assert "nivel" in frase
    assert not any(caracter.isdigit() for caracter in frase), frase


# --- Mecanismo por datos, no por nombre --------------------------------------


@pytest.mark.parametrize("modulo", ["carril.py", "rigor.py", "tamano.py", "cobertura.py"])
def test_f040_ningun_modulo_decide_por_el_nombre_del_nivel(modulo: str) -> None:
    assert "express" not in _crudo(RAIZ / "harness" / modulo)


# --- R41: el motivo --------------------------------------------------------------


def _checkpoints_viejo() -> str:
    """El CHECKPOINTS.md del payload devuelto a antes de F-040."""
    return (_crudo(CHECKPOINTS)
            .replace("| **express** |", "| **rapido** |")
            .replace("**Puertas informativas.**", "**Otra cosa.**")
            .replace("**Mutación** (niveles que la exigen)",
                     "**Mutación** (niveles `estandar` y `critico`)"))


@checkpoints_de_f040
def test_f040_r41_un_checkpoints_viejo_da_el_motivo_con_instrucciones() -> None:
    assert _motivo_checkpoints_viejo(_checkpoints_viejo()) == _INSTRUCCION_CHECKPOINTS
    assert "acepta esos bloques del diff de CHECKPOINTS.md" in _INSTRUCCION_CHECKPOINTS
    assert _motivo_checkpoints_viejo("") == _INSTRUCCION_CHECKPOINTS


def test_f040_r41_los_dependientes_llevan_la_marca_y_el_rojo_no() -> None:
    dependientes = [f for n, f in globals().items()
                    if n.startswith(("test_f040_r31_", "test_f040_r32_", "test_f040_r33_",
                                     "test_f040_r41_un_checkpoints_")) and callable(f)]

    assert len(dependientes) >= 6
    for funcion in dependientes:
        assert checkpoints_de_f040.mark in getattr(funcion, "pytestmark", []), funcion.__name__
    rojo = test_f040_r41_el_checkpoints_instalado_trae_los_carriles
    assert checkpoints_de_f040.mark not in getattr(rojo, "pytestmark", [])
