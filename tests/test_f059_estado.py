# tests/test_f059_estado.py
"""F-059 · R15–R17: `python -m harness.e2e --estado` y la sección 7 sexies.

`--estado` no ejecuta tests: mira el diff de la feature (repositorio git
temporal, patrón de `test_f040_carril.py`) y lee el resumen. La 7 sexies de
`init.sh` se ejecuta con bash con un intérprete falso y con Python real.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness import e2e
from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
INIT_SH = RAIZ / "harness" / "init.sh"
RAMA = "feature/F-900-x"

RIGOR = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": False,
                     "informativas": ["e2e"]},
        "exigente": {"fase_red": True, "cobertura": True, "mutacion": True, "e2e": True},
        "express": {"fase_red": False, "cobertura": False, "mutacion": False},
    },
}
SERVICIO_WEB = {"nombre": "web", "ruta": "web", "lenguaje": "python",
                "e2e": {"url_base": "http://localhost:8000", "rutas_ui": ["ui/**", "*.html"]}}


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    )


def _escribir(raiz: Path, relativa: str, texto: str) -> None:
    fichero = raiz / relativa
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(texto, encoding="utf-8", newline="\n")


def _proyecto(tmp_path: Path, servicios: list | None = None, rigor: str = "estandar",
              status: str = "in_progress") -> Path:
    raiz = tmp_path / "proyecto"
    features = {"features": [{"id": "F-900", "title": "t", "status": status, "sdd": True,
                              "rigor": rigor, "branch": RAMA}]}
    _escribir(raiz, "harness/features.json", json.dumps(features))
    _escribir(raiz, "harness/rigor.json", json.dumps(RIGOR))
    if servicios is not None:
        _escribir(raiz, "harness/servicios.json", json.dumps({"servicios": servicios}))
    _escribir(raiz, "web/app.py", "x = 1\n")
    _escribir(raiz, "otro/ui/fuera.html", "<p>\n")
    _git(raiz, "init", "-q", "-b", "dev")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicio")
    _git(raiz, "checkout", "-q", "-b", RAMA)
    return raiz


def _cambiar(raiz: Path, *relativas: str, spec: str | None = None) -> None:
    for relativa in relativas:
        _escribir(raiz, relativa, "cambio\n")
    if spec is not None:
        _escribir(raiz, "specs/F-900-x/requirements.md", spec)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "F-900: cambio")


def _resumen(raiz: Path, global_: str) -> None:
    _escribir(raiz, "progress/e2e_F-900.md",
              f"# F-900 · Capa e2e\n\n| Dato | Valor |\n|---|---|\n"
              f"| Resultado global | {global_} |\n")


def _estado(raiz: Path, capsys) -> tuple[int, str]:
    codigo = e2e.main(["--estado", "--base", "dev", "--raiz", str(raiz)])
    salida = capsys.readouterr()
    return codigo, salida.out + salida.err


# --- R15: N/A con su motivo, en orden ------------------------------------------


@pytest.mark.parametrize(("servicios", "rigor", "status", "motivo"), [
    ([SERVICIO_WEB], "estandar", "done", "sin feature en curso"),
    (None, "estandar", "in_progress", "declara el proyecto como servicio"),
    ([{"nombre": "web", "ruta": "web", "lenguaje": "python"}], "estandar", "in_progress",
     "ningún servicio declara el bloque e2e"),
    ([SERVICIO_WEB], "express", "in_progress", "nivel express: la capa no aplica"),
], ids=["done", "sin servicios", "sin bloque", "nivel"])
def test_f059_r15_na_con_motivo(tmp_path, capsys, servicios, rigor, status, motivo) -> None:
    raiz = _proyecto(tmp_path, servicios, rigor=rigor, status=status)
    _cambiar(raiz, "web/ui/pagina.html")

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 0
    assert salida.startswith("CAPA E2E: N/A (") and motivo in salida, salida
    assert salida.count("\n") == 1


def test_f059_r15_na_si_ni_toca_ui_ni_hay_requisitos(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/app.py", "otro/ui/fuera.html")

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 0
    assert "N/A (F-900 ni toca rutas_ui ni su spec marca requisitos (capa: e2e))" in salida


def test_f059_r15_informativa_sin_resumen_es_aviso(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/ui/pagina.html")

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 3
    assert salida.startswith("CAPA E2E: AVISO (informativa, no bloquea)"), salida
    assert "no existe progress/e2e_F-900.md" in salida
    assert "python -m harness.e2e --feature F-900" in salida
    assert salida.count("\n") == 1


def test_f059_r15_exigida_sin_resumen_es_ko(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB], rigor="exigente")
    _cambiar(raiz, "web/ui/pagina.html")

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 1 and salida.startswith("CAPA E2E: KO ("), salida


@pytest.mark.parametrize(("global_", "rigor", "codigo"), [
    ("VERDE", "estandar", 0), ("VERDE", "exigente", 0),
    ("ROJO", "estandar", 3), ("TIMEOUT", "exigente", 1),
])
def test_f059_r15_con_resumen(tmp_path, capsys, global_, rigor, codigo) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB], rigor=rigor)
    _cambiar(raiz, "web/ui/pagina.html")
    _resumen(raiz, global_)

    obtenido, salida = _estado(raiz, capsys)

    assert obtenido == codigo, salida
    assert global_ in salida
    if codigo == 0:
        assert salida.startswith("CAPA E2E: OK (")


def test_f059_r15_los_requisitos_e2e_bastan_para_que_aplique(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/app.py", spec="- **R2.** La pantalla debe listar. (capa: e2e)\n")

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 3 and "requisitos e2e: R2" in salida, salida


def test_f059_r15_una_declaracion_rota_es_ko(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [{**SERVICIO_WEB, "e2e": {"url_base": "x", "rutas_ui": ["*"]}}])

    codigo, salida = _estado(raiz, capsys)

    assert codigo == 1 and salida.startswith("CAPA E2E: KO (") and "url_base" in salida


def test_f059_r15_estado_no_ejecuta_nada(tmp_path, capsys, monkeypatch) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/ui/pagina.html")
    monkeypatch.setattr(e2e, "ejecutar_servicio", lambda *a, **k: pytest.fail("ejecutó"))

    _estado(raiz, capsys)

    assert not (raiz / ".arnes_cache").exists()


# --- R16: «toca UI» por los globs prefijados con la ruta del servicio ----------


def test_f059_r16_nombra_el_primer_fichero_y_cuantos_mas(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/ui/b.js", "web/ui/a.css", "web/index.html", "web/app.py",
             "otro/ui/fuera.html")

    _, salida = _estado(raiz, capsys)

    assert "toca UI: web/index.html y 2 más" in salida, salida


def test_f059_r16_un_solo_fichero_sin_y_mas(tmp_path, capsys) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    _cambiar(raiz, "web/ui/a.css")

    _, salida = _estado(raiz, capsys)

    assert "toca UI: web/ui/a.css)" in salida or "toca UI: web/ui/a.css;" in salida, salida


def test_f059_r16_toca_ui_unidad() -> None:
    from harness.servicios import BloqueE2E, Servicio

    web = Servicio("web", "web", "python", e2e=BloqueE2E("http://x", ("ui/**", "*.html")))
    raiz_svc = Servicio("app", ".", "python", e2e=BloqueE2E("http://x", ("static/**",)))

    assert e2e.ficheros_de_ui(["web/ui/x/y.js", "ui/z.js", "web/a.html", "web/b.py"],
                              [web]) == ["web/a.html", "web/ui/x/y.js"]
    assert e2e.ficheros_de_ui(["static/a.css", "src/a.py"], [raiz_svc]) == ["static/a.css"]


# --- R17: la sección 7 sexies de init.sh ----------------------------------------


def _texto() -> str:
    return INIT_SH.read_text(encoding="utf-8")


def _bash() -> str | None:
    ruta = shutil.which("bash")
    if ruta is None or (os.name == "nt" and "system32" in ruta.lower()):
        return None
    return ruta


BASH = _bash()
necesita_bash = pytest.mark.skipif(BASH is None, reason="sin bash utilizable")

_INSTRUCCION_INIT_SH = (
    "harness/init.sh no trae la sección 7 sexies de F-059 (CAPA E2E): el portero no "
    "diría si la capa e2e aplica a la feature. Al actualizar el arnés, acepta ese "
    "bloque del diff de harness/init.sh"
)


def _motivo_init_sh_viejo(texto: str) -> str | None:
    """El rojo de R34 si este init.sh es de antes de F-059; None si no lo es."""
    partes = ("# --- 7 sexies.", "-m harness.e2e --estado")
    return None if all(parte in texto for parte in partes) else _INSTRUCCION_INIT_SH


_MOTIVO_INIT_SH = _motivo_init_sh_viejo(_texto())
init_sh_de_f059 = pytest.mark.skipif(_MOTIVO_INIT_SH is not None, reason=_MOTIVO_INIT_SH or "")


def test_f059_r34_el_init_sh_instalado_trae_la_capa_e2e() -> None:
    motivo = _motivo_init_sh_viejo(_texto())

    assert motivo is None, motivo


def _seccion() -> str:
    texto = _texto()
    inicio = texto.index("# --- 7 sexies.")
    return texto[inicio:texto.index("# --- 8.", inicio)]


_PRELUDIO = (
    "set -u\nFALLOS=0\nRAMA_BASE=dev\n"
    'ok()   { printf "[OK] %s\\n" "$1"; }\n'
    'warn() { printf "[AVISO] %s\\n" "$1"; }\n'
    'ko()   { printf "[KO] %s\\n" "$1"; FALLOS=$((FALLOS + 1)); }\n'
)
_FALSO = (
    "#!/bin/bash\n"
    'echo "$@" > args.txt\n'
    "printf '%b' \"$SALIDA_FALSA\"\n"
    'exit "$CODIGO_FALSO"\n'
)


def _ejecutar(cwd: Path, guion: str, entorno: dict | None = None) -> str:
    fichero = cwd / "seccion.sh"
    fichero.write_text(_PRELUDIO + guion + 'echo "FALLOS=$FALLOS"\n',
                       encoding="utf-8", newline="\n")
    proceso = subprocess.run([BASH, fichero.name], cwd=cwd, capture_output=True,
                             env={**os.environ, **(entorno or {})}, timeout=escalar_timeout(120), check=False)
    fichero.unlink()
    return (proceso.stdout + proceso.stderr).decode("utf-8", errors="replace")


def _con_falso(tmp_path: Path, salida: str, codigo: int) -> str:
    (tmp_path / "harness").mkdir(exist_ok=True)
    (tmp_path / "harness" / "e2e.py").write_text("", encoding="utf-8")
    (tmp_path / "pyfalso").write_text(_FALSO, encoding="utf-8", newline="\n")
    guion = 'ES_PYTHON=1\nSALTAR_SUITES=0\nPY="bash ./pyfalso"\n' + _seccion()
    return _ejecutar(tmp_path, guion, {"SALIDA_FALSA": salida, "CODIGO_FALSO": str(codigo)})


@init_sh_de_f059
def test_f059_r17_va_tras_la_7_quinquies_y_no_ejecuta_la_capa() -> None:
    texto = _texto()
    codigo = "\n".join(li for li in _seccion().splitlines() if not li.lstrip().startswith("#"))

    assert texto.index("# --- 7 quinquies.") < texto.index("# --- 7 sexies.") < texto.index(
        "# --- 8.")
    assert "--feature" not in codigo and "SALTAR_SUITES" not in codigo
    assert "-m harness.e2e --estado" in codigo


@necesita_bash
@init_sh_de_f059
@pytest.mark.parametrize(("codigo", "marca", "fallos"), [
    (0, "[OK]", 0), (3, "[AVISO]", 0), (1, "[KO]", 1), (2, "[KO]", 1),
])
def test_f059_r17_cada_codigo_da_su_veredicto(tmp_path, codigo, marca, fallos) -> None:
    salida = _con_falso(tmp_path, "CAPA E2E: texto\\r\\n", codigo)

    assert f"{marca} CAPA E2E: texto\n" in salida, salida
    assert f"FALLOS={fallos}" in salida and "\r" not in salida
    assert (tmp_path / "args.txt").read_text().strip() == "-m harness.e2e --estado --base dev"


@necesita_bash
@init_sh_de_f059
@pytest.mark.parametrize(("variables", "fichero", "motivo"), [
    ('ES_PYTHON=1\nPY=""\n', True, "no hay intérprete de Python"),
    ('ES_PYTHON=0\nPY="python"\n', True, "proyecto sin Python"),
    ('ES_PYTHON=1\nPY="python"\n', False, "no existe harness/e2e.py"),
], ids=["sin interprete", "proyecto sin python", "sin e2e.py"])
def test_f059_r17_sin_medir_dice_na_con_el_motivo(tmp_path, variables, fichero, motivo) -> None:
    if fichero:
        (tmp_path / "harness").mkdir()
        (tmp_path / "harness" / "e2e.py").write_text("", encoding="utf-8")

    salida = _ejecutar(tmp_path, variables + _seccion())

    assert f"CAPA E2E: N/A ({motivo}" in salida, salida
    assert "FALLOS=0" in salida


@necesita_bash
@init_sh_de_f059
def test_f059_r17_punta_a_punta_con_python_real(tmp_path) -> None:
    raiz = _proyecto(tmp_path, [SERVICIO_WEB])
    shutil.copytree(RAIZ / "harness", raiz / "harness", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.json"))
    _cambiar(raiz, "web/ui/pagina.html")
    py = Path(sys.executable).as_posix()

    salida = _ejecutar(raiz, f'ES_PYTHON=1\nPY="{py}"\n' + _seccion())

    assert "[AVISO] CAPA E2E: AVISO (informativa, no bloquea)" in salida, salida
    assert "FALLOS=0" in salida and "\r" not in salida


# --- R34: un init.sh conservado de antes de F-059 --------------------------------


def _init_sh_viejo() -> str:
    """El init.sh del payload devuelto a antes de F-059 (sin la 7 sexies)."""
    texto = _texto()
    inicio = texto.index("# --- 7 sexies.")
    return texto[:inicio] + texto[texto.index("# --- 8.", inicio):]


@init_sh_de_f059
def test_f059_r34_un_init_sh_viejo_da_el_motivo_con_instrucciones() -> None:
    assert _motivo_init_sh_viejo(_init_sh_viejo()) == _INSTRUCCION_INIT_SH
    assert _motivo_init_sh_viejo("") == _INSTRUCCION_INIT_SH
    assert "acepta ese bloque del diff de harness/init.sh" in _INSTRUCCION_INIT_SH


def test_f059_r34_los_dependientes_del_init_sh_llevan_la_marca() -> None:
    dependientes = {n: f for n, f in globals().items()
                    if n.startswith(("test_f059_r17_", "test_f059_r34_un_init_sh_"))
                    and callable(f)}

    assert len(dependientes) >= 5, sorted(dependientes)
    for nombre, funcion in dependientes.items():
        assert init_sh_de_f059.mark in getattr(funcion, "pytestmark", []), nombre
    rojo = test_f059_r34_el_init_sh_instalado_trae_la_capa_e2e
    assert init_sh_de_f059.mark not in getattr(rojo, "pytestmark", [])
