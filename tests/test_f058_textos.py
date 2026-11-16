# tests/test_f058_textos.py
"""F-058 · R23–R35: valores del payload y lo que dicen los documentos.

Los valores de `rigor.json` son los del PAYLOAD: en un proyecto el fichero es
suyo (`es_el_taller`). `CHECKPOINTS.md` es `adaptado`: un proyecto que
conserve el suyo ve un único rojo que dice qué aceptar, y sus dependientes se
saltan (patrón de F-055 y F-040). Los textos se comparan aplanados: el
documento va envuelto y una frase puede partirse en dos líneas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.rigor import cargar_rigor, regla_nivel, umbral_cobertura_con_origen

RAIZ = Path(__file__).resolve().parents[1]
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
LEADER = RAIZ / ".claude" / "agents" / "leader.md"
SPEC_AUTHOR = RAIZ / ".claude" / "agents" / "spec-author.md"
REVIEWER = RAIZ / ".claude" / "agents" / "reviewer.md"
IMPLEMENTER = RAIZ / ".claude" / "agents" / "implementer.md"
GUIA = RAIZ.parent / "GUIA_INSTALACION.md"

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="harness/rigor.json y la guía son del taller, no del proyecto",
)


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _plano(texto_o_ruta: str | Path) -> str:
    texto = _crudo(texto_o_ruta) if isinstance(texto_o_ruta, Path) else texto_o_ruta
    return " ".join(texto.split())


def _payload() -> dict:
    return cargar_rigor(RAIZ / "harness" / "rigor.json")


# --- R23–R25: rigor.json del payload ------------------------------------------


@es_el_taller
def test_f058_r23_critico_lleva_la_regla_proporcional() -> None:
    rigor = _payload()
    critico = rigor["niveles"]["critico"]

    assert critico["un_mutante_por_linea"] is True
    assert critico["fraccion_mutantes"] == 0.6
    assert (critico["min_mutantes"], critico["max_mutantes"]) == (100, 300)
    assert critico["semilla"] == 20261030
    assert umbral_cobertura_con_origen(rigor, "critico") == (90, "nivel")
    assert regla_nivel("critico", rigor).tope(1000) == 300


@es_el_taller
def test_f058_r24_estandar_veinte_fijos_uno_por_linea_y_umbral_global() -> None:
    rigor = _payload()
    estandar = rigor["niveles"]["estandar"]

    assert estandar["un_mutante_por_linea"] is True
    assert (estandar["max_mutantes"], estandar["semilla"]) == (20, 20260820)
    assert "fraccion_mutantes" not in estandar
    assert umbral_cobertura_con_origen(rigor, "estandar") == (80, "global")


@es_el_taller
def test_f058_r24_documental_y_express_no_cambian() -> None:
    publicado = cargar_rigor(Path(__file__).with_name("f058_rigor_publicado.json"))
    rigor = _payload()

    for nivel in ("documental", "express"):
        assert rigor["niveles"][nivel] == publicado["niveles"][nivel], nivel


@es_el_taller
def test_f058_r25_el_doc_explica_la_regla_y_como_pedir_la_entera() -> None:
    rigor = _payload()
    documentos = _plano(rigor["$doc"] + " " + rigor["niveles"]["critico"]["$doc"])

    formula = "min(max_mutantes, max(min_mutantes, ceil(fraccion_mutantes * C)))"
    for frase in ("un_mutante_por_linea", formula, "campana completa",
                  "--max-mutantes 0", "max_mutantes: null"):
        assert frase in documentos, frase


# --- R34: el rojo único de un CHECKPOINTS.md anterior a F-058 -----------------

_INSTRUCCION_CHECKPOINTS = (
    "CHECKPOINTS.md no trae lo de F-058 (criterio para declarar `critico` y "
    "campaña `critico` con la regla del nivel en vez de «entera y exigida»): al "
    "actualizar el arnés, acepta esos bloques del diff de CHECKPOINTS.md"
)


def _fila_critico(texto: str) -> str:
    return next((li for li in texto.splitlines() if li.startswith("| **critico** |")), "")


def _motivo_checkpoints_viejo(texto: str) -> str | None:
    """El rojo de R34 si este CHECKPOINTS.md es de antes de F-058; o None."""
    viejo = ("entera y exigida" in _fila_critico(texto)
             or "**Criterio para declarar `critico`.**" not in texto)
    return _INSTRUCCION_CHECKPOINTS if viejo else None


_MOTIVO = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))
checkpoints_de_f058 = pytest.mark.skipif(_MOTIVO is not None, reason=_MOTIVO or "")


def test_f058_r34_el_checkpoints_instalado_acepta_la_muestra() -> None:
    motivo = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))

    assert motivo is None, motivo


# --- R28–R30: criterio de `critico` y sus punteros -----------------------------


def _criterio() -> str:
    texto = _plano(CHECKPOINTS)
    return texto.split("**Criterio para declarar `critico`.**", 1)[1].split("## ", 1)[0]


@checkpoints_de_f058
def test_f058_r28_los_cinco_disparadores() -> None:
    criterio = _criterio()

    for disparador in ("**dinero**", "que se factura, paga o contabiliza",
                       "**Escribe** en producción", "**compartido**",
                       "**Seguridad**", "**contrato público**", "**puerta**"):
        assert disparador in criterio, disparador
    assert "al menos uno" in criterio and "ruta o recurso" in criterio


@checkpoints_de_f058
def test_f058_r28_lo_que_no_lo_justifica_y_la_duda() -> None:
    criterio = _criterio()
    no_justifican = criterio.split("NO lo justifican", 1)[1]

    for motivo in ("el tamaño", "lecturas de producción", "solo lectura",
                   "refactors sin cambio de contrato"):
        assert motivo in no_justifican, motivo
    assert "**Ante la duda, `estandar`.**" in criterio


def test_f058_r29_el_leader_pide_el_disparador_con_puntero() -> None:
    bloque = _plano(LEADER).split("## Carril de rigor (PARADA 1)", 1)[1].split(" ## ", 1)[0]

    assert "Proponer `critico`" in bloque and "disparador" in bloque
    assert "«Niveles de rigor» de `CHECKPOINTS.md`" in bloque
    assert "que se factura, paga o contabiliza" not in _plano(LEADER)


def test_f058_r30_el_spec_author_declara_nivel_y_disparador() -> None:
    texto = _plano(SPEC_AUTHOR)

    assert "`design.md` declara el nivel de rigor" in texto
    assert "si es `critico`, qué disparador" in texto
    assert "«Niveles de rigor» de `CHECKPOINTS.md`" in texto
    assert "que se factura, paga o contabiliza" not in texto


# --- R31–R33: la muestra y el incremental en CHECKPOINTS y agentes ------------


@checkpoints_de_f058
def test_f058_r31_la_fila_critico_acepta_la_muestra() -> None:
    fila = _fila_critico(_crudo(CHECKPOINTS))

    assert "campaña de mutación" in fila.lower()
    assert "con la regla del nivel" in fila and "uno por línea" in fila
    assert "**en la muestra**" in fila
    assert "entera y exigida" not in fila


@checkpoints_de_f058
def test_f058_r31_c4_bis_dice_que_comprobar_de_la_muestra_y_del_incremental() -> None:
    bloque = _plano(CHECKPOINTS).split("## C4 bis", 1)[1].split("## C4 ter", 1)[0]
    mutacion = bloque.split("**Mutación** (niveles que la exigen)", 1)[1].split("- [ ]")[0]

    assert "candidatos, evaluados y motivo" in mutacion
    assert "«0 supervivientes sin justificar en la muestra» cumple" in mutacion
    assert "la campaña entera la pide el humano" in mutacion
    assert "fila «Modo»" in mutacion and "antepasado" in mutacion
    assert "muestra de control" in mutacion


def test_f058_r32_el_reviewer_acepta_muestra_e_incremental() -> None:
    texto = _plano(REVIEWER)
    carril = texto.split("## Recorrido por carril", 1)[1].split(" ## ", 1)[0]
    punto_4 = texto.split("4. Si el nivel exige **mutación**", 1)[1].split(" 5. ", 1)[0]

    assert "`critico`" in carril and "como siempre" in carril
    assert "regla del nivel" in carril
    assert "vale la muestra" in punto_4 and "informe incremental" in punto_4
    assert "candidatos, evaluados y motivo" in punto_4 and "`harness/rigor.json`" in punto_4


def test_f058_r33_el_implementer_repite_con_incremental() -> None:
    texto = _plano(IMPLEMENTER)

    assert "tras cerrar supervivientes" in texto and "`--incremental`" in texto


# --- R34: el motivo y las marcas -----------------------------------------------


def _checkpoints_viejo() -> str:
    """El CHECKPOINTS.md del payload devuelto a antes de F-058."""
    return (_crudo(CHECKPOINTS)
            .replace("**Criterio para declarar `critico`.**", "**Otra cosa.**"))


@checkpoints_de_f058
def test_f058_r34_un_checkpoints_viejo_da_el_motivo_con_instrucciones() -> None:
    assert _motivo_checkpoints_viejo(_checkpoints_viejo()) == _INSTRUCCION_CHECKPOINTS
    fila_vieja = ("| **critico** | X | Todo lo de `estandar` + **campaña de mutación** "
                  "entera y exigida |\n**Criterio para declarar `critico`.**")
    assert _motivo_checkpoints_viejo(fila_vieja) == _INSTRUCCION_CHECKPOINTS
    assert _motivo_checkpoints_viejo("") == _INSTRUCCION_CHECKPOINTS
    assert "acepta esos bloques del diff de CHECKPOINTS.md" in _INSTRUCCION_CHECKPOINTS


def test_f058_r34_los_dependientes_llevan_la_marca_y_el_rojo_no() -> None:
    dependientes = [f for n, f in globals().items()
                    if n.startswith(("test_f058_r28_", "test_f058_r31_",
                                     "test_f058_r34_un_checkpoints_")) and callable(f)]

    assert len(dependientes) >= 5
    for funcion in dependientes:
        assert checkpoints_de_f058.mark in getattr(funcion, "pytestmark", []), funcion.__name__
    rojo = test_f058_r34_el_checkpoints_instalado_acepta_la_muestra
    assert checkpoints_de_f058.mark not in getattr(rojo, "pytestmark", [])


# --- R35: la guía -------------------------------------------------------------


def _seccion_de_la_guia() -> str:
    texto = _plano(GUIA)
    return texto.split("### Mutación proporcional al rigor y al tamaño (F-058", 1)[1].split(
        " ### Mutación", 1)[0]


@es_el_taller
def test_f058_r35_la_guia_avisa_de_que_rigor_json_se_pisa() -> None:
    seccion = _seccion_de_la_guia()

    assert "AVISO" in seccion and "`arnes_puro`" in seccion
    assert "uno por línea" in seccion and "`critico`" in seccion
    assert "--max-mutantes 0" in seccion and "max_mutantes: null" in seccion


@es_el_taller
def test_f058_r35_la_guia_dice_que_aceptar_y_lo_que_queda_fuera() -> None:
    seccion = _seccion_de_la_guia()

    assert "`CHECKPOINTS.md`" in seccion and "`adaptado`" in seccion
    assert "test_f058_r34_el_checkpoints_instalado_acepta_la_muestra" in seccion
    assert "`--incremental`" in seccion
    assert "F-063" in seccion
    assert "`politica_ficheros.json` no cambia" in seccion
