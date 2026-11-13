# tests/test_f059_textos.py
"""F-059 · R23–R35: el agente `qa-e2e` y lo que dicen los documentos del arnés.

`CHECKPOINTS.md` es `adaptado`: un proyecto que conserve el suyo ve un único
rojo con lo que aceptar, y sus dependientes se saltan (patrón F-058 R34). La
guía es del taller. Los textos se comparan aplanados: el documento va envuelto
y una frase puede partirse en dos líneas.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = RAIZ / ".claude" / "agents"
QA = AGENTES / "qa-e2e.md"
LEADER = AGENTES / "leader.md"
SPEC_AUTHOR = AGENTES / "spec-author.md"
IMPLEMENTER = AGENTES / "implementer.md"
REVIEWER = AGENTES / "reviewer.md"
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
SPECS = RAIZ / "specs" / "SPECS.md"
CLAUDE_MD = RAIZ / "CLAUDE.md"
GUIA = RAIZ.parent / "GUIA_INSTALACION.md"

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="la guía es del taller, no del proyecto",
)


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _plano(texto_o_ruta: str | Path) -> str:
    texto = _crudo(texto_o_ruta) if isinstance(texto_o_ruta, Path) else texto_o_ruta
    return " ".join(texto.split())


def _frontmatter(ruta: Path) -> dict[str, str]:
    bloque = _crudo(ruta).split("---", 2)[1]
    campos = {}
    for linea in bloque.strip().splitlines():
        clave, _, valor = linea.partition(":")
        campos[clave.strip()] = valor.strip()
    return campos


# --- R23–R26: el agente qa-e2e --------------------------------------------------


def test_f059_r23_frontmatter_del_agente() -> None:
    campos = _frontmatter(QA)

    assert campos["name"] == "qa-e2e"
    assert campos["model"] == "claude-opus-5-5"
    assert campos["effort"] == "medium"
    assert [t.strip() for t in campos["tools"].split(",")] == [
        "Read", "Grep", "Glob", "Write", "Edit", "Bash"]


def test_f059_r24_solo_tests_e2e_y_lo_que_falta_al_implementer() -> None:
    texto = _plano(QA)

    assert "**solo tests e2e**" in texto
    assert "`(capa: e2e)`" in texto and "`rutas_ui`" in texto
    assert "**Nunca** código de producción ni specs" in texto
    assert "`data-testid`" in texto and "**lo anotas en el resumen para el implementer**" in texto


def test_f059_r25_las_reglas_de_los_tests() -> None:
    texto = _plano(QA)

    for regla in ("**Selectores por rol o por `data-testid`**",
                  "**Esperas por estado, nunca `sleep`**",
                  "**Fixtures o datos propios**", "**Nunca contra producción**",
                  "**Un test por flujo**", "`test_fXXX_rN_<flujo>`",
                  "**Tiempo máximo en cada espera**"):
        assert regla in texto, regla


def test_f059_r26_un_rojo_se_repite_una_vez() -> None:
    texto = _plano(QA)

    assert "**Un ROJO se repite una vez**" in texto
    assert "rojo en las dos ejecuciones → defecto: responde `E2E_ROJO -> progress/e2e_F-XXX.md`" in texto
    assert "rojo y luego verde → consta como **inestable**" in texto
    assert "responde `done -> progress/e2e_F-XXX.md`" in texto


# --- R27–R28: la marca de capa en la spec ---------------------------------------


def test_f059_r27_specs_pide_la_capa_por_requisito() -> None:
    seccion = _plano(SPECS).split("## 1. requirements.md", 1)[1].split("## 2.", 1)[0]

    assert "**Capa del test.**" in seccion
    for marca in ("`(capa: unit)`", "`(capa: integración)`", "`(capa: e2e)`"):
        assert marca in seccion, marca
    assert "Sin marca, cuenta como unit" in seccion
    assert "las specs anteriores siguen valiendo" in seccion
    assert "solo vale si el servicio declara el bloque `e2e`" in seccion


def test_f059_r28_el_spec_author_apunta_a_specs_sin_copiar_la_regla() -> None:
    texto = _plano(SPEC_AUTHOR)

    assert "termina con su capa" in texto and "«Capa del test» de `specs/SPECS.md`" in texto
    assert "Sin marca, cuenta como unit" not in texto
    assert "`(capa: integración)`" not in texto


# --- R29–R31: el flujo en leader, implementer y reviewer ------------------------


def _seccion_qa() -> str:
    # F-070: la sección se llama «Orden de fases en `in_review`».
    return _plano(LEADER).split("## Orden de fases en `in_review`", 1)[1].split(" ## ", 1)[0]


def test_f059_r29_el_leader_fija_el_orden_en_in_review() -> None:
    seccion = _seccion_qa()
    fila = next(li for li in _crudo(LEADER).splitlines() if li.startswith("| `in_review` |"))

    assert "reviewer principal → `qa-e2e` (si la capa aplica) → campaña" in fila
    assert "la línea `CAPA E2E`" in seccion and "no es N/A" in seccion
    assert "requisitos `(capa: e2e)`" in seccion
    assert seccion.index("**reviewer principal**") < seccion.index("**`qa-e2e`**") < seccion.index(
        "**Pasada de campaña**") < seccion.index("**reviewer de evidencias**")


def test_f059_r29_rojo_express_documental_y_parada_2() -> None:
    seccion = _seccion_qa()

    assert "`E2E_ROJO -> progress/e2e_F-XXX.md`" in seccion
    assert "devuelve la feature a `in_progress` y **cuenta en los 2 ciclos**" in seccion
    assert "`express` y `documental`: **sin `qa-e2e`" in seccion  # F-070 añade más fases
    assert "**«e2e N/N»**" in seccion and "PARADA 2" in seccion
    assert "`E2E_ROJO -> progress/e2e_F-XXX.md`" in _plano(LEADER).split(
        "## Regla anti-teléfono", 1)[1]


def test_f059_r30_el_implementer_no_escribe_los_e2e_y_lanza_en_la_pasada() -> None:
    texto = _plano(IMPLEMENTER)
    bloque = texto.split("**Capa e2e.**", 1)[1].split(" > ", 1)[0]

    assert "No escribes los tests de los requisitos `(capa: e2e)`" in bloque
    # F-070: la campaña va siempre en la pasada, tras el reviewer principal.
    assert "tras el APPROVED del reviewer principal" in bloque
    assert "**pasada de campaña**" in bloque and "tras el verde de `qa-e2e`" in bloque
    assert "| **Capa e2e** |" in _crudo(IMPLEMENTER)


def test_f059_r31_el_reviewer_reejecuta_fuera_de_progress() -> None:
    punto_5 = _plano(REVIEWER).split("5. El informe del implementer", 1)[1].split(" 6. ", 1)[0]

    assert "**reejecuta** `python -m harness.e2e --feature F-XXX --salida <ruta fuera de progress/>`" in punto_5
    assert "cada requisito e2e → su test → PASA" in punto_5
    assert "**informativa**" in punto_5 and "solo rechazas por un **ROJO reproducido**" in punto_5


# --- R32–R33: CHECKPOINTS.md y CLAUDE.md ----------------------------------------

_INSTRUCCION_CHECKPOINTS = (
    "CHECKPOINTS.md no trae lo de F-059 (punto «Capa e2e» de C4 bis, comando "
    "`python -m harness.e2e` y orden «`qa-e2e` antes de la campaña de mutación»): "
    "al actualizar el arnés, acepta esos bloques del diff de CHECKPOINTS.md"
)


def _c4_bis(texto: str) -> str:
    return texto.split("## C4 bis", 1)[1].split("## C4 ter", 1)[0] if "## C4 bis" in texto else ""


def _motivo_checkpoints_viejo(texto: str) -> str | None:
    """El rojo de R34 si este CHECKPOINTS.md es de antes de F-059; o None."""
    plano = _plano(texto)
    nuevo = ("- [ ] **Capa e2e**" in _c4_bis(texto)
             and "python -m harness.e2e --feature F-XXX" in texto
             and "**`qa-e2e` antes de la campaña de mutación**" in plano)
    return None if nuevo else _INSTRUCCION_CHECKPOINTS


_MOTIVO = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))
checkpoints_de_f059 = pytest.mark.skipif(_MOTIVO is not None, reason=_MOTIVO or "")


def test_f059_r34_el_checkpoints_instalado_trae_la_capa_e2e() -> None:
    motivo = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))

    assert motivo is None, motivo


@checkpoints_de_f059
def test_f059_r32_c4_bis_trae_el_punto_capa_e2e() -> None:
    punto = _plano(_c4_bis(_crudo(CHECKPOINTS))).split("- [ ] **Capa e2e**", 1)[1].split(
        "- [ ]", 1)[0]

    assert "`CAPA E2E`" in punto and "`(capa: e2e)`" in punto
    assert "existe `progress/e2e_F-XXX.md`" in punto
    assert "cada requisito e2e tiene su test en PASA" in punto
    assert "reejecutó con `--salida` fuera de `progress/`" in punto
    assert "**informativa**" in punto and "un ROJO reproducido, sí" in punto
    assert "ni su ausencia, ni un TIMEOUT" in punto


@checkpoints_de_f059
def test_f059_r32_comandos_y_orden() -> None:
    texto = _crudo(CHECKPOINTS)
    comandos = texto.split("Comandos de las puertas:", 1)[1].split("```", 2)[1]

    assert "python -m harness.e2e --feature F-XXX" in comandos
    assert "**`qa-e2e` antes de la campaña de mutación**" in _plano(texto)


def test_f059_r33_claude_md_nombra_qa_e2e_entre_los_subagentes() -> None:
    seccion = _plano(CLAUDE_MD).split("## Autorización permanente de subagentes", 1)[1].split(
        " ## ", 1)[0]

    assert "`qa-e2e`" in seccion and "`spec-author`" in seccion, (
        "CLAUDE.md no nombra `qa-e2e` entre los subagentes autorizados (F-059): al "
        "actualizar el arnés, acepta ese bloque del diff de CLAUDE.md")


# --- R34: el motivo y las marcas -------------------------------------------------


@checkpoints_de_f059
def test_f059_r34_un_checkpoints_viejo_da_el_motivo_con_instrucciones() -> None:
    actual = _crudo(CHECKPOINTS)
    viejos = (actual.replace("- [ ] **Capa e2e**", "- [ ] **Otra**"),
              actual.replace("python -m harness.e2e --feature F-XXX", "x"),
              _plano(actual).replace("**`qa-e2e` antes de la campaña de mutación**", "y"), "")

    for viejo in viejos:
        assert _motivo_checkpoints_viejo(viejo) == _INSTRUCCION_CHECKPOINTS
    assert "acepta esos bloques del diff de CHECKPOINTS.md" in _INSTRUCCION_CHECKPOINTS


def test_f059_r34_los_dependientes_llevan_la_marca_y_el_rojo_no() -> None:
    dependientes = [f for n, f in globals().items()
                    if n.startswith(("test_f059_r32_", "test_f059_r34_un_checkpoints_"))
                    and callable(f)]

    assert len(dependientes) >= 3
    for funcion in dependientes:
        assert checkpoints_de_f059.mark in getattr(funcion, "pytestmark", []), funcion.__name__
    rojo = test_f059_r34_el_checkpoints_instalado_trae_la_capa_e2e
    assert checkpoints_de_f059.mark not in getattr(rojo, "pytestmark", [])


# --- R34 punta a punta: un proyecto que conserva sus ficheros adaptados ----------

_ROJOS = {
    "test_f059_r34_el_checkpoints_instalado_trae_la_capa_e2e":
        "acepta esos bloques del diff de CHECKPOINTS.md",
    "test_f059_r34_el_init_sh_instalado_trae_la_capa_e2e":
        "acepta ese bloque del diff de harness/init.sh",
}
_DEPENDIENTES = ("test_f059_r17_", "test_f059_r32_", "test_f059_r34_un_")


def _checkpoints_viejo() -> str:
    """El CHECKPOINTS.md del payload sin nada de F-059."""
    texto = _crudo(CHECKPOINTS)
    inicio = texto.index("- [ ] **Capa e2e**")
    texto = texto[:inicio] + texto[texto.index("- [ ] Ningún punto de este bloque", inicio):]
    return texto.replace("python -m harness.e2e --feature F-XXX", "")


def _casos(ruta: Path) -> dict[str, tuple[str, str]]:
    casos = {}
    for caso in ET.parse(ruta).iter("testcase"):
        resultado, mensaje = "passed", ""
        for hijo in caso:
            if hijo.tag in ("failure", "error", "skipped"):
                resultado, mensaje = hijo.tag, hijo.get("message", "")
        casos[caso.get("name", "")] = (resultado, mensaje)
    return casos


@es_el_taller
def test_f059_r34_con_init_sh_y_checkpoints_viejos_un_rojo_por_fichero(tmp_path: Path) -> None:
    """Sobre una copia sin `politica_ficheros.json` al lado: como en un proyecto."""
    proyecto = tmp_path / "proyecto"
    for carpeta in ("harness", ".claude", "specs"):
        shutil.copytree(RAIZ / carpeta, proyecto / carpeta, ignore=shutil.ignore_patterns(
            "__pycache__", "settings.local.json"))
    shutil.copy2(CLAUDE_MD, proyecto / "CLAUDE.md")
    (proyecto / "tests").mkdir()
    ficheros = ("test_f059_textos.py", "test_f059_estado.py")
    for nombre in ficheros:
        shutil.copy2(RAIZ / "tests" / nombre, proyecto / "tests" / nombre)
    init_sh = _crudo(RAIZ / "harness" / "init.sh")
    inicio = init_sh.index("# --- 7 sexies.")
    (proyecto / "harness" / "init.sh").write_text(
        init_sh[:inicio] + init_sh[init_sh.index("# --- 8.", inicio):],
        encoding="utf-8", newline="\n")
    (proyecto / "CHECKPOINTS.md").write_text(
        _checkpoints_viejo(), encoding="utf-8", newline="\n")
    informe = tmp_path / "junit.xml"

    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         f"--junitxml={informe}", *(f"tests/{nombre}" for nombre in ficheros)],
        cwd=proyecto, capture_output=True, text=True, timeout=escalar_timeout(600), check=False,
    )

    casos = _casos(informe)
    rojos = {n: m for n, (r, m) in casos.items() if r in ("failure", "error")}
    assert sorted(rojos) == sorted(_ROJOS), rojos
    for nombre, instruccion in _ROJOS.items():
        assert instruccion in rojos[nombre]
    dependientes = {n: v for n, v in casos.items() if n.startswith(_DEPENDIENTES)}
    assert len(dependientes) >= 8, sorted(casos)
    for nombre, (resultado, mensaje) in dependientes.items():
        assert resultado == "skipped", (nombre, resultado)
        assert "acepta es" in mensaje and "bloque" in mensaje, (nombre, mensaje)


# --- R35: la guía ---------------------------------------------------------------


def _seccion_de_la_guia() -> str:
    texto = _plano(GUIA)
    return texto.split("### Capa e2e y agente `qa-e2e` (F-059", 1)[1].split(" ## ", 1)[0]


@es_el_taller
def test_f059_r35_la_guia_dice_que_aceptar() -> None:
    seccion = _seccion_de_la_guia()

    for fichero in ("`CHECKPOINTS.md`", "`harness/init.sh`", "`CLAUDE.md`"):
        assert "Acepta" in seccion and fichero in seccion, fichero
    assert "test_f059_r34_el_checkpoints_instalado_trae_la_capa_e2e" in seccion
    assert "test_f059_r34_el_init_sh_instalado_trae_la_capa_e2e" in seccion


@es_el_taller
def test_f059_r35_como_declarar_instalar_plantilla_e_informativa() -> None:
    seccion = _seccion_de_la_guia()

    assert "**Cómo declarar `e2e`.**" in seccion and "`hosts_prohibidos`" in seccion
    assert "**Playwright lo instala el proyecto**" in seccion
    assert "python -m harness.e2e --plantilla --servicio NOMBRE" in seccion
    assert "**informativa**" in seccion and "F-047" in seccion
    assert "`politica_ficheros.json` e `instalar_arnes.ps1` no cambian" in seccion
