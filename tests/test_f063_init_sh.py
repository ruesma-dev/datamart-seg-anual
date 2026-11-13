# tests/test_f063_init_sh.py
"""F-063: la sección 3b de `harness/init.sh` con la capa local de rigor.

Se ejecuta la sección real con bash y Python real sobre un repositorio git
desechable (`tmp_path`): el paquete `harness` se importa del payload por
`PYTHONPATH`, y el `harness/` del repositorio desechable solo trae los datos.

Un proyecto que conserva un `init.sh` adaptado tiene fusión e informe (vienen
de `--validar`) pero no el WARN de R17: ahí estos tests se saltan con el motivo,
sin rojo, porque la guía da esa combinación por buena.
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
RIGOR_PUBLICADO = RAIZ / "harness" / "rigor.json"


def _bash() -> str | None:
    ruta = shutil.which("bash")
    if ruta is None:
        return None
    if os.name == "nt" and "system32" in ruta.lower():
        return None  # el bash de WSL no ve las rutas de Windows igual
    return ruta


BASH = _bash()


def _seccion_3b() -> str:
    texto = INIT_SH.read_text(encoding="utf-8")
    inicio = texto.index("# --- 3b.")
    return texto[inicio:texto.index("# --- 4.", inicio)]


#: `ARNES_F063_FORZAR=1` ejecuta los tests aunque el bloque falte: es como se
#: obtuvo la traza de la fase RED en el payload antes de escribir el bloque.
_SIN_WARN = ("rigor.local.json" not in _seccion_3b()
             and not os.environ.get("ARNES_F063_FORZAR"))
pytestmark = [
    pytest.mark.skipif(BASH is None, reason="sin bash utilizable"),
    pytest.mark.skipif(shutil.which("git") is None, reason="sin git"),
    pytest.mark.skipif(_SIN_WARN, reason=(
        "harness/init.sh adaptado sin el aviso de la capa local de rigor (F-063): "
        "la fusión funciona igual; para el aviso, acepta el bloque de la sección "
        "3b del diff de harness/init.sh"
    )),
]

_PRELUDIO = (
    "set -u\nFALLOS=0\nRAMA_BASE=dev\n"
    'ok()   { printf "[OK] %s\\n" "$1"; }\n'
    'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
    'ko()   { printf "[KO] %s\\n" "$1"; FALLOS=$((FALLOS + 1)); }\n'
)


def _git(cwd: Path, *argumentos: str) -> None:
    subprocess.run(["git", *argumentos], cwd=cwd, check=True, capture_output=True)


def _repo(tmp_path: Path, git: bool = True) -> Path:
    """Repositorio desechable en `dev` con `rigor.json` y `features.json`."""
    (tmp_path / "harness").mkdir()
    shutil.copy(RIGOR_PUBLICADO, tmp_path / "harness" / "rigor.json")
    (tmp_path / "harness" / "features.json").write_text(
        json.dumps({"features": []}), encoding="utf-8")
    if git:
        _git(tmp_path, "init", "-q", "-b", "dev")
        _git(tmp_path, "config", "user.email", "prueba@example.invalid")
        _git(tmp_path, "config", "user.name", "prueba")
        _git(tmp_path, "config", "core.autocrlf", "false")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "base")
        _git(tmp_path, "checkout", "-q", "-b", "feature/F-900-x")
    return tmp_path


def _capa(repo: Path, datos: dict, commit: bool = False) -> None:
    (repo / "harness" / "rigor.local.json").write_text(json.dumps(datos), encoding="utf-8")
    if commit:
        _git(repo, "add", "harness/rigor.local.json")
        _git(repo, "commit", "-q", "-m", "capa")


def _ejecutar(cwd: Path, rama_base: str = "dev") -> str:
    fichero = cwd / "seccion.sh"
    guion = (_PRELUDIO.replace("RAMA_BASE=dev", f"RAMA_BASE={rama_base}")
             + f'PY="{Path(sys.executable).as_posix()}"\n'
             + _seccion_3b() + 'echo "FALLOS=$FALLOS"\n')
    fichero.write_text(guion, encoding="utf-8", newline="\n")
    proceso = subprocess.run(
        [BASH, fichero.name], cwd=cwd, capture_output=True, timeout=escalar_timeout(120), check=False,
        env={**os.environ, "PYTHONPATH": str(RAIZ)},
    )
    fichero.unlink()
    return (proceso.stdout + proceso.stderr).decode("utf-8", errors="replace")


_OK = "[OK] harness/rigor.json y niveles declarados: válidos"
_AVISO = "[AVISO] CAPA LOCAL DE RIGOR"


# --- R1 y R13 -----------------------------------------------------------------


def test_f063_r1_sin_capa_el_ok_de_siempre_y_ningun_aviso(tmp_path: Path) -> None:
    salida = _ejecutar(_repo(tmp_path))

    assert _OK in salida, salida
    assert "FALLOS=0" in salida
    assert "[AVISO]" not in salida
    assert "capa local" not in salida


def test_f063_r13_capa_invalida_pone_la_3b_en_rojo(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _capa(repo, {"niveles": {"critico": {"umbral_cobertra": 95}}}, commit=True)

    salida = _ejecutar(repo)

    assert "[KO] harness/rigor.json o el campo 'rigor'" in salida, salida
    assert "niveles.critico.umbral_cobertra" in salida
    assert "FALLOS=1" in salida


# --- R17: aviso si la capa cambia en la rama ------------------------------------


def test_f063_r17_capa_versionada_que_difiere_de_la_base_avisa(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _capa(repo, {"niveles": {"critico": {"umbral_cobertura": 50}}}, commit=True)

    salida = _ejecutar(repo)

    assert _OK in salida, salida
    assert "capa local (harness/rigor.local.json): niveles.critico.umbral_cobertura" in salida
    assert _AVISO in salida
    assert "cambia en esta rama respecto a dev" in salida
    assert "OK explícito del humano" in salida
    assert "FALLOS=0" in salida


def test_f063_r17_capa_sin_versionar_avisa(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _capa(repo, {})

    salida = _ejecutar(repo)

    assert _AVISO in salida, salida
    assert "FALLOS=0" in salida


def test_f063_r17_capa_modificada_sin_commit_avisa(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "dev")
    _capa(repo, {}, commit=True)
    _git(repo, "checkout", "-q", "feature/F-900-x")
    _git(repo, "merge", "-q", "dev")
    _capa(repo, {"cobertura": {"umbral_lineas_cambiadas": 90}})

    assert _AVISO in _ejecutar(repo)


def test_f063_r17_capa_igual_que_la_de_la_base_no_avisa(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "dev")
    _capa(repo, {"cobertura": {"umbral_lineas_cambiadas": 90}}, commit=True)
    _git(repo, "checkout", "-q", "feature/F-900-x")
    _git(repo, "merge", "-q", "dev")

    salida = _ejecutar(repo)

    assert _OK in salida, salida
    assert "capa local (harness/rigor.local.json)" in salida
    assert "[AVISO]" not in salida


def test_f063_r17_sin_rama_base_no_avisa(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _capa(repo, {}, commit=True)

    salida = _ejecutar(repo, rama_base="no-existe")

    assert _OK in salida, salida
    assert "[AVISO]" not in salida


def test_f063_r17_sin_git_no_avisa(tmp_path: Path) -> None:
    suelto = tmp_path / "suelto"
    suelto.mkdir()
    repo = _repo(suelto, git=False)
    _capa(repo, {})

    salida = _ejecutar(repo, rama_base="dev")

    assert _OK in salida, salida
    assert "[AVISO]" not in salida
