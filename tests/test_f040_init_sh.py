# tests/test_f040_init_sh.py
"""F-040: la §7 quinquies y la §7b de `harness/init.sh`, ejecutadas con bash.

Dos clases de ejecución, y hacen falta las dos (lección de F-028): un intérprete
FALSO que escribe CRLF, como Python en Windows, para fijar cada veredicto; y
Python REAL sobre un repositorio de verdad, porque un doble que alimenta a bash
se compara con la salida real o no demuestra nada.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
INIT_SH = RAIZ / "harness" / "init.sh"
RAMA = "feature/F-900-x"


def _texto() -> str:
    return INIT_SH.read_text(encoding="utf-8")


def _bash() -> str | None:
    ruta = shutil.which("bash")
    if ruta is None:
        return None
    if os.name == "nt" and "system32" in ruta.lower():
        return None  # el bash de WSL no ve las rutas de Windows igual
    return ruta


BASH = _bash()
necesita_bash = pytest.mark.skipif(BASH is None, reason="sin bash utilizable")

_INSTRUCCION = (
    "harness/init.sh no ejecuta la puerta de carril de F-040 (sección 7 quinquies) "
    "o no avisa de la cobertura informativa (sección 7b): un nivel con límites se "
    "quedaría sin vigilar. Al actualizar el arnés, acepta esos bloques del diff "
    "de harness/init.sh"
)


def _motivo_init_sh_viejo(texto: str) -> str | None:
    """El rojo de R40 si este init.sh es de antes de F-040; None si no lo es."""
    partes = ("# --- 7 quinquies.", "-m harness.carril", '"PUERTA COBERTURA: AVISO"*)')
    return None if all(parte in texto for parte in partes) else _INSTRUCCION


#: Patrón de F-055: con un init.sh conservado, los tests de comportamiento se
#: saltan con la instrucción y el test de abajo queda como el único rojo.
_MOTIVO_INIT_SH_VIEJO = _motivo_init_sh_viejo(_texto())
init_sh_de_f040 = pytest.mark.skipif(
    _MOTIVO_INIT_SH_VIEJO is not None, reason=_MOTIVO_INIT_SH_VIEJO or "")


def test_f040_r40_el_init_sh_instalado_trae_la_puerta_de_carril() -> None:
    motivo = _motivo_init_sh_viejo(_texto())

    assert motivo is None, motivo


_PRELUDIO = (
    "set -u\nFALLOS=0\nRAMA_BASE=dev\n"
    'ok()   { printf "[OK] %s\\n" "$1"; }\n'
    'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
    'ko()   { printf "[KO] %s\\n" "$1"; FALLOS=$((FALLOS + 1)); }\n'
)

#: Intérprete falso: anota sus argumentos, escribe el texto pedido tal cual
#: (con el CRLF de Python en Windows) y sale con el código pedido.
_FALSO = (
    "#!/bin/bash\n"
    'echo "$@" > args.txt\n'
    "printf '%b' \"$SALIDA_FALSA\"\n"
    'exit "$CODIGO_FALSO"\n'
)


def _seccion_carril() -> str:
    texto = _texto()
    inicio = texto.index("# --- 7 quinquies.")
    return texto[inicio:texto.index("# --- 8.", inicio)]


def _seccion_7b() -> str:
    texto = _texto()
    inicio = texto.index("# --- 7b.")
    return texto[inicio:texto.index("# --- 7 ter.", inicio)]


def _ejecutar(cwd: Path, guion: str, entorno: dict | None = None) -> bytes:
    fichero = cwd / "seccion.sh"
    fichero.write_text(_PRELUDIO + guion + 'echo "FALLOS=$FALLOS"\n',
                       encoding="utf-8", newline="\n")
    proceso = subprocess.run(
        [BASH, fichero.name], cwd=cwd, capture_output=True,
        env={**os.environ, **(entorno or {})}, timeout=escalar_timeout(120), check=False,
    )
    fichero.unlink()
    return proceso.stdout + proceso.stderr


def _con_falso(tmp_path: Path, seccion: str, salida: str, codigo: int) -> str:
    (tmp_path / "harness").mkdir(exist_ok=True)
    (tmp_path / "harness" / "carril.py").write_text("", encoding="utf-8")
    (tmp_path / "pyfalso").write_text(_FALSO, encoding="utf-8", newline="\n")
    guion = 'ES_PYTHON=1\nSALTAR_SUITES=0\nPY="bash ./pyfalso"\n' + seccion
    crudo = _ejecutar(tmp_path, guion,
                      {"SALIDA_FALSA": salida, "CODIGO_FALSO": str(codigo)})
    return crudo.decode("utf-8", errors="replace")


# --- R17: orden, tres códigos, y las ramas sin medición ----------------------


@init_sh_de_f040
def test_f040_r17_va_tras_la_7_quater_y_antes_de_las_marcas() -> None:
    texto = _texto()

    assert (texto.index("# --- 7 quater.") < texto.index("# --- 7 quinquies.")
            < texto.index("# --- 8."))


@init_sh_de_f040
def test_f040_r17_no_depende_del_portero_ligero() -> None:
    assert "SALTAR_SUITES" not in _seccion_carril()


@necesita_bash
@init_sh_de_f040
@pytest.mark.parametrize(("codigo", "marca", "fallos"), [
    (0, "[OK]", 0), (1, "[KO]", 1), (2, "[AVISO]", 0), (3, "[AVISO]", 0),
])
def test_f040_r17_cada_codigo_da_su_veredicto(tmp_path, codigo, marca, fallos) -> None:
    salida = _con_falso(tmp_path, _seccion_carril(), "PUERTA CARRIL: texto\\n", codigo)

    assert f"{marca} PUERTA CARRIL: texto" in salida, salida
    assert f"FALLOS={fallos}" in salida, salida


@necesita_bash
@init_sh_de_f040
def test_f040_r17_llama_a_la_puerta_con_la_base_configurada(tmp_path) -> None:
    _con_falso(tmp_path, _seccion_carril(), "x\\n", 0)

    assert (tmp_path / "args.txt").read_text().strip() == "-m harness.carril --base dev"


@necesita_bash
@init_sh_de_f040
@pytest.mark.parametrize(("variables", "fichero", "motivo"), [
    ('ES_PYTHON=1\nPY=""\n', True, "no hay intérprete de Python"),
    ('ES_PYTHON=0\nPY="python"\n', True, "proyecto sin Python"),
    ('ES_PYTHON=1\nPY="python"\n', False, "no existe harness/carril.py"),
], ids=["sin interprete", "proyecto sin python", "sin carril.py"])
def test_f040_r17_sin_medir_avisa_con_el_motivo(tmp_path, variables, fichero, motivo) -> None:
    if fichero:
        (tmp_path / "harness").mkdir()
        (tmp_path / "harness" / "carril.py").write_text("", encoding="utf-8")

    salida = _ejecutar(tmp_path, variables + _seccion_carril()).decode("utf-8")

    assert f"[AVISO] PUERTA CARRIL: N/A ({motivo}" in salida, salida
    assert "FALLOS=0" in salida


# --- R18: bash no usa ningún valor de Python; el CRLF no cambia nada ---------


@necesita_bash
@init_sh_de_f040
@pytest.mark.parametrize(("codigo", "marca"), [(0, "[OK]"), (1, "[KO]"), (2, "[AVISO]")])
def test_f040_r18_con_crlf_el_mismo_veredicto_y_la_linea_entera(tmp_path, codigo, marca) -> None:
    texto = "PUERTA CARRIL: F-900 dentro de los límites (1/3 ficheros)\\r\\n"

    salida = _con_falso(tmp_path, _seccion_carril(), texto, codigo)

    assert f"{marca} PUERTA CARRIL: F-900 dentro de los límites (1/3 ficheros)\n" in salida
    assert "\r" not in salida, repr(salida)


@necesita_bash
@init_sh_de_f040
def test_f040_r18_un_rojo_de_varias_lineas_con_crlf_sale_sin_cr(tmp_path) -> None:
    texto = "PUERTA CARRIL: F-900 se sale:\\r\\n    4 ficheros > tope 3\\r\\n"

    salida = _con_falso(tmp_path, _seccion_carril(), texto, 1)

    assert "[KO] PUERTA CARRIL: F-900 se sale:\n    4 ficheros > tope 3\n" in salida
    assert "\r" not in salida, repr(salida)


@init_sh_de_f040
def test_f040_r18_decide_por_el_codigo_de_salida_sin_heredoc() -> None:
    seccion = _seccion_carril()

    assert 'case "$CODIGO_CARRIL" in' in seccion
    assert "<<" not in seccion


# --- R23: §7b con el aviso de la cobertura informativa -----------------------


@necesita_bash
@init_sh_de_f040
@pytest.mark.parametrize(("texto", "codigo", "marca", "fallos"), [
    ("PUERTA COBERTURA: AVISO (no bloquea, nivel x): 50%\\n", 0, "[AVISO]", 0),
    ("PUERTA COBERTURA: AVISO (no bloquea, nivel x): 50%\\r\\n", 0, "[AVISO]", 0),
    ("PUERTA COBERTURA: 90% de 10 líneas\\n", 0, "[OK]", 0),
    ("PUERTA COBERTURA: N/A (AVISO en el motivo)\\n", 0, "[OK]", 0),
    ("PUERTA COBERTURA: AVISO con codigo 1\\n", 1, "[KO]", 1),
], ids=["aviso", "aviso crlf", "ok", "aviso dentro del texto", "codigo 1 manda"])
def test_f040_r23_la_7b_distingue_el_aviso_por_el_prefijo(
    tmp_path, texto, codigo, marca, fallos
) -> None:
    salida = _con_falso(tmp_path, _seccion_7b(), texto, codigo)

    assert f"{marca} PUERTA COBERTURA:" in salida, salida
    assert f"FALLOS={fallos}" in salida, salida


# --- Python real sobre un repositorio de verdad -------------------------------


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def proyecto(tmp_path: Path) -> Path:
    """Un repositorio con el harness real y una feature de nivel con límites."""
    raiz = tmp_path / "proyecto"
    shutil.copytree(RAIZ / "harness", raiz / "harness",
                    ignore=shutil.ignore_patterns("__pycache__", "*.json"))
    rigor = {
        "nivel_por_defecto": "rapido",
        "cobertura": {"umbral_lineas_cambiadas": 80},
        "niveles": {"rapido": {
            "fase_red": False, "cobertura": False, "mutacion": False,
            "limites": {"ficheros": 1, "lineas": 2, "no_cuentan": ["harness/**"]},
        }},
    }
    features = {"features": [{"id": "F-900", "title": "T", "status": "in_progress",
                              "sdd": False, "rigor": "rapido", "branch": RAMA}]}
    (raiz / "harness" / "rigor.json").write_text(json.dumps(rigor), encoding="utf-8")
    (raiz / "harness" / "features.json").write_text(json.dumps(features), encoding="utf-8")
    _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicio")
    _git(raiz, "checkout", "-q", "-b", RAMA)
    return raiz


def _commit(raiz: Path, nombre: str, lineas: int) -> None:
    (raiz / nombre).write_text("x\n" * lineas, encoding="utf-8", newline="\n")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "F-900: cambio")


def _con_python_real(raiz: Path) -> str:
    py = Path(sys.executable).as_posix()
    variables = f'ES_PYTHON=1\nPY="{py}"\n'
    return _ejecutar(raiz, variables + _seccion_carril()).decode("utf-8", errors="replace")


@necesita_bash
@init_sh_de_f040
def test_f040_r17_punta_a_punta_dentro_del_carril_con_python_real(proyecto) -> None:
    _commit(proyecto, "a.txt", 2)

    salida = _con_python_real(proyecto)

    assert "[OK] PUERTA CARRIL: F-900 dentro de los" in salida, salida
    assert "(1/1 ficheros, 2/2 " in salida, salida
    assert "FALLOS=0" in salida
    assert "\r" not in salida, repr(salida)


@necesita_bash
@init_sh_de_f040
def test_f040_r17_punta_a_punta_fuera_del_carril_con_python_real(proyecto) -> None:
    _commit(proyecto, "a.txt", 3)

    salida = _con_python_real(proyecto)

    assert "[KO] PUERTA CARRIL: F-900 (nivel rapido) se sale del carril:\n" in salida, salida
    assert "tope 2\n" in salida, repr(salida)
    assert "FALLOS=1" in salida
    assert "\r" not in salida, repr(salida)


@necesita_bash
@init_sh_de_f040
def test_f040_r18_el_doble_escribe_lo_que_escribe_python_real(proyecto) -> None:
    """Sin esto, el intérprete falso podría estar probando otro mundo."""
    _commit(proyecto, "a.txt", 2)

    proceso = subprocess.run(
        [sys.executable, "-m", "harness.carril", "--base", "dev"],
        cwd=proyecto, capture_output=True, timeout=escalar_timeout(60), check=True)

    assert proceso.stdout.endswith(b"\r\n" if os.name == "nt" else b"\n")
    assert proceso.stdout.count(b"\n") == 1
    assert proceso.stdout.startswith(b"PUERTA CARRIL: F-900 dentro de los")


# --- R40, R41: un proyecto que conserva sus ficheros adaptados ------------------


_DEPENDIENTES = ("test_f040_r17_", "test_f040_r18_", "test_f040_r23_",
                 "test_f040_r31_", "test_f040_r32_", "test_f040_r33_",
                 "test_f040_r41_un_checkpoints_")
_ROJOS = {
    "test_f040_r40_el_init_sh_instalado_trae_la_puerta_de_carril":
        "acepta esos bloques del diff de harness/init.sh",
    "test_f040_r41_el_checkpoints_instalado_trae_los_carriles":
        "acepta esos bloques del diff de CHECKPOINTS.md",
}


def _init_sh_viejo() -> str:
    """El init.sh del payload devuelto a antes de F-040."""
    texto = _texto()
    inicio = texto.index("# --- 7 quinquies.")
    texto = texto[:inicio] + texto[texto.index("# --- 8.", inicio):]
    return texto.replace('"PUERTA COBERTURA: AVISO"*)', '"OTRA COSA"*)')


def _checkpoints_viejo() -> str:
    return ((RAIZ / "CHECKPOINTS.md").read_text(encoding="utf-8")
            .replace("| **express** |", "| **rapido** |")
            .replace("**Puertas informativas.**", "**Otra cosa.**")
            .replace("**Mutación** (niveles que la exigen)",
                     "**Mutación** (niveles `estandar` y `critico`)"))


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


#: Los que dan por hecho el init.sh de F-040.
_DE_INIT_SH = ("test_f040_r17_", "test_f040_r18_", "test_f040_r23_")


def test_f040_r40_los_dependientes_llevan_la_marca_y_el_rojo_no() -> None:
    funciones = {n: f for n, f in globals().items()
                 if n.startswith(_DE_INIT_SH) and callable(f)}

    assert len(funciones) >= 9, sorted(funciones)
    for nombre, funcion in funciones.items():
        assert init_sh_de_f040.mark in getattr(funcion, "pytestmark", []), nombre
    rojo = test_f040_r40_el_init_sh_instalado_trae_la_puerta_de_carril
    assert init_sh_de_f040.mark not in getattr(rojo, "pytestmark", [])


@init_sh_de_f040
def test_f040_r40_un_init_sh_viejo_da_el_motivo_con_instrucciones() -> None:
    assert _motivo_init_sh_viejo(_init_sh_viejo()) == _INSTRUCCION
    assert _motivo_init_sh_viejo("") == _INSTRUCCION
    assert _motivo_init_sh_viejo(_texto()) is None


es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="los ficheros adaptados son los del proyecto, no los del payload",
)


@es_el_taller
def test_f040_r40_r41_con_init_sh_y_checkpoints_viejos_dos_rojos(tmp_path: Path) -> None:
    """Sobre una copia sin `politica_ficheros.json` al lado: como en un proyecto.

    Lleva además un `rigor.json` sin `express`, que no puede dar rojo (R42).
    """
    proyecto = tmp_path / "proyecto"
    for carpeta in ("harness", ".claude", "specs"):
        shutil.copytree(RAIZ / carpeta, proyecto / carpeta, ignore=shutil.ignore_patterns(
            "__pycache__", "settings.local.json"))
    (proyecto / "tests").mkdir()
    ficheros = ("test_f040_init_sh.py", "test_f040_textos.py", "test_f040_niveles.py")
    for nombre in ficheros:
        shutil.copy2(RAIZ / "tests" / nombre, proyecto / "tests" / nombre)
    (proyecto / "harness" / "init.sh").write_text(
        _init_sh_viejo(), encoding="utf-8", newline="\n")
    (proyecto / "CHECKPOINTS.md").write_text(
        _checkpoints_viejo(), encoding="utf-8", newline="\n")
    rigor = json.loads((proyecto / "harness" / "rigor.json").read_text(encoding="utf-8"))
    del rigor["niveles"]["express"]
    (proyecto / "harness" / "rigor.json").write_text(json.dumps(rigor), encoding="utf-8")
    informe = tmp_path / "junit.xml"

    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         f"--junitxml={informe}", *(f"tests/{nombre}" for nombre in ficheros)],
        cwd=proyecto, capture_output=True, text=True, timeout=escalar_timeout(300), check=False,
    )

    casos = _junit(informe)
    rojos = {n: m for n, (r, m) in casos.items() if r in ("failure", "error")}
    assert sorted(rojos) == sorted(_ROJOS), rojos
    for nombre, instruccion in _ROJOS.items():
        assert instruccion in rojos[nombre]
    dependientes = {n: v for n, v in casos.items() if n.startswith(_DEPENDIENTES)}
    assert len(dependientes) >= 14, sorted(casos)
    for nombre, (resultado, mensaje) in dependientes.items():
        assert resultado == "skipped", (nombre, resultado)
        assert "acepta esos bloques del diff" in mensaje, (nombre, mensaje)
