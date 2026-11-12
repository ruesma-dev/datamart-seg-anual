# tests/test_f028_reviewer_sin_cache.py
"""F-028: el reviewer no aprueba sobre un verde servido de caché (R1–R5, R24).

Contrato estático de cuatro textos que tienen que decir lo mismo: el prompt del
reviewer lo ordena, C1 lo exige, `CLAUDE.md` lo admite como forma literal y la
allowlist de `.claude/settings.json` lo deja ejecutar sin pedir permiso. Si uno
de los cuatro escribe el comando distinto, la allowlist no cubre lo que el
prompt ordena y el reviewer acaba pidiendo permiso o ejecutando otra cosa.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
REVIEWER = RAIZ / ".claude" / "agents" / "reviewer.md"
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
SETTINGS = RAIZ / ".claude" / "settings.json"
CLAUDE_MD = RAIZ / "CLAUDE.md"
EJEMPLO = RAIZ / "harness" / "servicios.ejemplo.json"

COMANDO = "ARNES_SIN_CACHE=1 bash harness/init.sh"

#: Cualquier forma de escribir «init.sh con una variable delante»: lo que R5
#: compara entre los cuatro ficheros.
CON_VARIABLE = re.compile(r"[A-Z_]+=\S*\s+bash\s+harness/init\.sh")


def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _paso_1_del_protocolo() -> str:
    protocolo = _texto(REVIEWER).split("## Protocolo", 1)[1]
    return protocolo.split("\n2. ", 1)[0]


def _parrafo_dos_limites() -> str:
    texto = _texto(REVIEWER)
    inicio = texto.index("Dos límites que no relaja lo incremental")
    return texto[inicio:texto.index("\n\n", inicio)]


def _texto_o_vacio(ruta: Path) -> str:
    """Para los motivos, que se calculan al recoger la suite: nunca la rompen."""
    try:
        return _texto(ruta)
    except OSError:
        return ""


def _c1(texto: str | None = None) -> str:
    texto = _texto(CHECKPOINTS) if texto is None else texto
    return texto.split("## C1", 1)[1].split("\n## ", 1)[0]


def _primera_casilla_de_c1(texto: str | None = None) -> str:
    return _c1(texto).split("- [ ]", 2)[1]


def _regla_tal_cual(texto: str | None = None) -> str:
    parrafos = (_texto(CLAUDE_MD) if texto is None else texto).split("\n- ")
    return next(p for p in parrafos if "tal cual" in p)


def _allow(texto: str | None = None) -> list[str]:
    return json.loads(_texto(SETTINGS) if texto is None else texto)["permissions"]["allow"]


# --- Desviación 1 con el patrón de F-055 ------------------------------------------
# CHECKPOINTS.md, CLAUDE.md y .claude/settings.json son `adaptado`: un proyecto
# puede conservar los suyos al actualizar. Cada uno da UN rojo, el de su test
# (R2, R3, R4), que dice qué bloque aceptar de qué fichero; R5, que compara los
# cuatro, se salta con el mismo mensaje.

_INSTRUCCION_C1 = (
    "C1 de CHECKPOINTS.md no exige el portero sin caché de F-028: al actualizar "
    "el arnés, acepta ese bloque del diff de CHECKPOINTS.md (C1)"
)
_INSTRUCCION_SETTINGS = (
    "la allowlist de .claude/settings.json no cubre el portero sin caché de "
    "F-028: al actualizar el arnés, acepta esa línea del diff de settings.json"
)
_INSTRUCCION_CLAUDE_MD = (
    "CLAUDE.md no admite el portero sin caché de F-028: al actualizar el arnés, "
    "acepta ese bloque del diff de CLAUDE.md (la regla «tal cual»)"
)


def _motivo_c1(texto: str) -> str | None:
    """El rojo de R2 si C1 no exige el portero sin caché; None si lo exige."""
    try:
        casilla = _primera_casilla_de_c1(texto)
    except IndexError:
        return _INSTRUCCION_C1
    partes = (f"`{COMANDO}`", "exit code 0", "(caché: …)")
    return None if all(parte in casilla for parte in partes) else _INSTRUCCION_C1


def _motivo_settings(texto: str) -> str | None:
    """El rojo de R3: los dos porteros en la allowlist, el sin caché justo detrás."""
    try:
        allow = _allow(texto)
        siguiente = allow.index("Bash(bash harness/init.sh)") + 1
    except (ValueError, KeyError, TypeError, AttributeError):
        return _INSTRUCCION_SETTINGS
    if allow[siguiente:siguiente + 1] == [f"Bash({COMANDO})"]:
        return None
    return _INSTRUCCION_SETTINGS


def _motivo_claude_md(texto: str) -> str | None:
    """El rojo de R4 si la regla «tal cual» no admite la segunda forma."""
    try:
        regla = _regla_tal_cual(texto)
    except StopIteration:
        return _INSTRUCCION_CLAUDE_MD
    partes = ("`bash harness/init.sh` tal cual", f"`{COMANDO}`", "allowlist")
    return None if all(parte in regla for parte in partes) else _INSTRUCCION_CLAUDE_MD


def _motivos_de_los_textos() -> list[str]:
    motivos = (_motivo_c1(_texto_o_vacio(CHECKPOINTS)),
               _motivo_settings(_texto_o_vacio(SETTINGS)),
               _motivo_claude_md(_texto_o_vacio(CLAUDE_MD)))
    return [motivo for motivo in motivos if motivo is not None]


_MOTIVOS_TEXTOS_VIEJOS = _motivos_de_los_textos()
textos_de_f028 = pytest.mark.skipif(
    bool(_MOTIVOS_TEXTOS_VIEJOS), reason=" · ".join(_MOTIVOS_TEXTOS_VIEJOS))


# --- R1: reviewer.md ----------------------------------------------------------


def test_f028_r1_el_paso_1_ordena_el_portero_sin_cache() -> None:
    paso = _paso_1_del_protocolo()

    assert f"`{COMANDO}`" in paso
    assert "caché" in paso
    assert "CHANGES_REQUESTED" in paso


def test_f028_r1_el_paso_1_ya_no_ordena_el_portero_a_secas() -> None:
    assert "Ejecuta `bash harness/init.sh`" not in _paso_1_del_protocolo()


def test_f028_r1_los_dos_limites_nombran_el_mismo_comando() -> None:
    assert f"`{COMANDO}`" in _parrafo_dos_limites()


# --- R2: CHECKPOINTS.md C1 ----------------------------------------------------


def test_f028_r2_c1_exige_exit_0_sin_cache_de_suites() -> None:
    motivo = _motivo_c1(_texto(CHECKPOINTS))

    assert motivo is None, motivo


# --- R3: la allowlist -----------------------------------------------------------


def test_f028_r3_la_allowlist_cubre_los_dos_porteros() -> None:
    motivo = _motivo_settings(_texto(SETTINGS))

    assert motivo is None, motivo


# --- R4: CLAUDE.md --------------------------------------------------------------


def test_f028_r4_la_regla_tal_cual_admite_la_segunda_forma() -> None:
    motivo = _motivo_claude_md(_texto(CLAUDE_MD))

    assert motivo is None, motivo


# --- R5: la misma grafía en los cuatro ------------------------------------------


@textos_de_f028
def test_f028_r5_los_cuatro_ficheros_escriben_el_comando_igual() -> None:
    fuentes = {
        "reviewer.md": _texto(REVIEWER),
        "CHECKPOINTS.md": _c1(),
        "CLAUDE.md": _regla_tal_cual(),
        "settings.json": "\n".join(_allow()),
    }

    formas = {nombre: set(CON_VARIABLE.findall(texto)) for nombre, texto in fuentes.items()}

    assert formas == {nombre: {COMANDO} for nombre in fuentes}


# --- R24: el ejemplo de servicios.json ---------------------------------------------


def test_f028_r24_el_ejemplo_documenta_ejecutar_siempre_y_el_punto() -> None:
    datos = json.loads(_texto(EJEMPLO))
    doc = datos["$doc"]

    assert "'ejecutar_siempre'" in doc
    assert "depende_de: [\".\"]" in doc
    assert "cualquier cambio" in doc


def test_f028_r24_el_ejemplo_declara_ejecutar_siempre_en_un_servicio_python() -> None:
    declarados = [s for s in json.loads(_texto(EJEMPLO))["servicios"]
                  if "ejecutar_siempre" in s]

    assert declarados and all(s["lenguaje"] == "python" for s in declarados)


def test_f028_r24_el_ejemplo_avisa_de_que_sin_cache_solo_corre_lo_que_pytest_colecta(
) -> None:
    doc = json.loads(_texto(EJEMPLO))["$doc"]

    assert "Sin cache que servir" in doc
    assert "colecta por defecto" in doc


# --- Desviación 1 (patrón de F-055): un rojo por fichero conservado ----------------


def _checkpoints_viejo() -> str:
    return _texto(CHECKPOINTS).replace(f"`{COMANDO}`", "`bash harness/init.sh`")


def _claude_md_viejo() -> str:
    return _texto(CLAUDE_MD).replace(f"`{COMANDO}`", "`bash harness/init.sh`")


def _settings_viejo() -> str:
    datos = json.loads(_texto(SETTINGS))
    datos["permissions"]["allow"].remove(f"Bash({COMANDO})")
    return json.dumps(datos, indent=2, ensure_ascii=False)


@pytest.mark.parametrize(("motivo", "viejo", "instruccion"), [
    (_motivo_c1, _checkpoints_viejo, _INSTRUCCION_C1),
    (_motivo_settings, _settings_viejo, _INSTRUCCION_SETTINGS),
    (_motivo_claude_md, _claude_md_viejo, _INSTRUCCION_CLAUDE_MD),
], ids=["CHECKPOINTS.md", "settings.json", "CLAUDE.md"])
@textos_de_f028
def test_f028_r23_un_fichero_conservado_da_el_motivo_con_instrucciones(
    motivo: Callable[[str], str | None], viejo: Callable[[], str], instruccion: str,
) -> None:
    assert motivo(viejo()) == instruccion
    assert "acepta es" in instruccion and "del diff de" in instruccion
    assert motivo("") == instruccion


@textos_de_f028
def test_f028_r23_settings_con_el_comando_fuera_de_su_sitio_tambien_es_viejo() -> None:
    datos = json.loads(_texto(SETTINGS))
    allow = datos["permissions"]["allow"]
    allow.append(allow.pop(allow.index(f"Bash({COMANDO})")))

    assert _motivo_settings(json.dumps(datos)) == _INSTRUCCION_SETTINGS
    assert _motivo_settings("{no es json") == _INSTRUCCION_SETTINGS


def test_f028_r23_r5_lleva_la_marca_y_los_rojos_con_instrucciones_no() -> None:
    """R5 y los que fabrican un fichero viejo a partir del nuevo se saltan."""
    for dependiente in (test_f028_r5_los_cuatro_ficheros_escriben_el_comando_igual,
                        test_f028_r23_un_fichero_conservado_da_el_motivo_con_instrucciones,
                        test_f028_r23_settings_con_el_comando_fuera_de_su_sitio_tambien_es_viejo):
        assert textos_de_f028.mark in getattr(dependiente, "pytestmark", []), (
            dependiente.__name__)
    for rojo in (test_f028_r2_c1_exige_exit_0_sin_cache_de_suites,
                 test_f028_r3_la_allowlist_cubre_los_dos_porteros,
                 test_f028_r4_la_regla_tal_cual_admite_la_segunda_forma):
        assert textos_de_f028.mark not in getattr(rojo, "pytestmark", []), rojo.__name__


#: En el taller los cuatro ficheros son los del payload; en un proyecto instalado,
#: los que conservó (y entonces el rojo ya lo dan R2–R4 y R23 del init.sh).
es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="los ficheros adaptados son los del proyecto, no los del payload",
)


@es_el_taller
def test_f028_r23_con_los_ficheros_del_payload_no_se_salta_nada_por_esa_causa() -> None:
    assert _motivos_de_los_textos() == []
    assert _MOTIVOS_TEXTOS_VIEJOS == []


def _junit(ruta: Path) -> dict[str, tuple[str, str]]:
    """{test: (resultado, mensaje)} de un informe junit de pytest."""
    import xml.etree.ElementTree as ET

    casos: dict[str, tuple[str, str]] = {}
    for caso in ET.parse(ruta).iter("testcase"):
        resultado, mensaje = "passed", ""
        for hijo in caso:
            if hijo.tag in ("failure", "error", "skipped"):
                resultado, mensaje = hijo.tag, hijo.get("message", "")
        casos[caso.get("name", "")] = (resultado, mensaje)
    return casos


#: Los tests de F-028 que dependen de un fichero adaptado y se saltan si el
#: proyecto lo conservó: R5 y los que fabrican un fichero viejo a partir del
#: nuevo, aquí; en la §7 bis, los de comportamiento y su fabricado.
_DEPENDIENTES = ("test_f028_r5_", "test_f028_r12_", "test_f028_r13_", "test_f028_r14_",
                 "test_f028_r21_postventa_", "test_f028_r23_un_fichero_conservado_",
                 "test_f028_r23_settings_con_el_comando_",
                 "test_f028_r23_un_init_sh_de_la_1_7_16_")
_ROJOS_CON_INSTRUCCIONES = {
    "test_f028_r2_c1_exige_exit_0_sin_cache_de_suites": "CHECKPOINTS.md (C1)",
    "test_f028_r3_la_allowlist_cubre_los_dos_porteros": "settings.json",
    "test_f028_r4_la_regla_tal_cual_admite_la_segunda_forma": "CLAUDE.md",
    "test_f028_r23_el_init_sh_instalado_reconoce_las_lineas_siempre": "harness/init.sh",
}


@es_el_taller
def test_f028_r23_con_los_cuatro_ficheros_viejos_un_rojo_por_fichero(
    tmp_path: Path,
) -> None:
    """Los tests de F-028, en otro proceso, sobre una copia con los cuatro viejos."""
    proyecto = tmp_path / "proyecto"
    shutil.copytree(RAIZ / "harness", proyecto / "harness",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(RAIZ / ".claude", proyecto / ".claude",
                    ignore=shutil.ignore_patterns("settings.local.json"))
    (proyecto / "tests").mkdir()
    ficheros = ("test_f028_reviewer_sin_cache.py", "test_cache_suites_init_sh.py")
    for nombre in ficheros:
        shutil.copy2(RAIZ / "tests" / nombre, proyecto / "tests" / nombre)
    init = (RAIZ / "harness" / "init.sh").read_text(encoding="utf-8")
    viejos = {
        "harness/init.sh": init.replace('SIEMPRE)  SIEMPRE_SRV+=("$VALOR") ;;', ""),
        "CHECKPOINTS.md": _checkpoints_viejo(),
        "CLAUDE.md": _claude_md_viejo(),
        ".claude/settings.json": _settings_viejo(),
    }
    for ruta, texto in viejos.items():
        (proyecto / ruta).write_text(texto, encoding="utf-8", newline="\n")
    informe = tmp_path / "junit.xml"

    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-k", "f028",
         f"--junitxml={informe}", *(f"tests/{nombre}" for nombre in ficheros)],
        cwd=proyecto, capture_output=True, text=True, timeout=escalar_timeout(600), check=False,
    )

    casos = _junit(informe)
    rojos = {n: m for n, (r, m) in casos.items() if r in ("failure", "error")}
    assert sorted(rojos) == sorted(_ROJOS_CON_INSTRUCCIONES), rojos
    for nombre, fichero in _ROJOS_CON_INSTRUCCIONES.items():
        assert "acepta es" in rojos[nombre] and f"del diff de {fichero}" in rojos[nombre]
    dependientes = {n: v for n, v in casos.items() if n.startswith(_DEPENDIENTES)}
    assert len(dependientes) >= 12, sorted(casos)
    for nombre, (resultado, mensaje) in dependientes.items():
        assert resultado == "skipped", (nombre, resultado)
        assert "acepta es" in mensaje and "del diff de" in mensaje, (nombre, mensaje)
