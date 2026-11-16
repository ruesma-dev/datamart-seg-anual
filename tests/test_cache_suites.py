# tests/test_cache_suites.py
"""Caché de suites de los servicios: la clave, la decisión, la CLI y los
escenarios de punta a punta.

La clave reúne todo lo que puede cambiar el resultado de la suite sin cambiar
el árbol del servicio: sus dependencias declaradas, el intérprete, la ruta real
de los módulos que importa y la huella de los ficheros locales (`.env`). Si algo
de eso no se puede fijar, no hay clave y la suite se ejecuta.

Git de verdad, siempre sobre repositorios diminutos en `tmp_path` y sin las
variables `GIT_*` del entorno. La sonda es falsa (inyectada) salvo en los
escenarios y la CLI, donde corre la real con el intérprete del test.

Origen: albaranes F-072 (requisitos R7–R22 y R31–R33), portado en la 1.7.16.
"""

from __future__ import annotations

import builtins
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness import cache_suites
from harness.cache_suites import (
    Decision,
    ErrorDeSonda,
    Sondeo,
    _dentro_de,
    clave_de,
    decidir,
    hash_en_head,
    hay_cambios,
    huella_local,
    lineas_de_salida,
    main,
    raiz_del_repositorio,
    sondear,
    texto_de_clave,
)
from harness.servicios import Servicio

PY = sys.executable


@pytest.fixture(autouse=True)
def _sin_variables_git(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in list(os.environ):
        if variable.startswith("GIT_"):
            monkeypatch.delenv(variable, raising=False)


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Arnes", "-c", "user.email=arnes@ejemplo.invalid",
         "-C", str(raiz), *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    ).stdout


def _escribir(raiz: Path, ruta: str, texto: str) -> Path:
    fichero = raiz / ruta
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(texto, encoding="utf-8")
    return fichero


def _commit(raiz: Path, mensaje: str = "cambio") -> None:
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", mensaje)


@pytest.fixture(scope="module")
def _plantilla(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Se crea una vez por módulo: en Windows, cada proceso git cuesta."""
    raiz = tmp_path_factory.mktemp("plantilla_cache") / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _escribir(raiz, ".gitignore", ".env\n__pycache__/\nlocal/\n")
    _escribir(raiz, "services/svc/app.py", "X = 1\n")
    _escribir(raiz, "services/comun/pkg/__init__.py", "Y = 1\n")
    _escribir(raiz, "services/otro/otro.py", "Z = 1\n")
    _commit(raiz, "inicial")
    return raiz


@pytest.fixture
def repo(_plantilla: Path, tmp_path: Path) -> Path:
    """Repositorio con `services/svc`, `services/comun` y `services/otro`."""
    raiz = tmp_path / "repo"
    shutil.copytree(_plantilla, raiz)
    return raiz


def _svc(**extra: object) -> Servicio:
    datos: dict = {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"}
    datos.update(extra)
    return Servicio(**datos)


def _sondeo(**origenes: str | None) -> Sondeo:
    return Sondeo(origenes=dict(origenes), tiene_coverage=False)


def _clave(repo: Path, servicio: Servicio, sondeo: Sondeo | None = None,
           interprete: str = PY) -> str | None:
    clave, _ = clave_de(servicio, str(repo), interprete, sondeo or _sondeo())
    return clave


# --- Piezas de git -----------------------------------------------------------


def test_r7_hash_en_head_de_carpeta_fichero_y_ausente(repo: Path) -> None:
    arbol = _git(repo, "rev-parse", "HEAD:services/svc").strip()

    assert hash_en_head("services/svc", str(repo)) == arbol
    assert hash_en_head(".gitignore", str(repo)) == _git(
        repo, "rev-parse", "HEAD:.gitignore").strip()
    assert hash_en_head("services/no-existe", str(repo)) is None


def test_r11_hay_cambios_ve_modificados_y_no_rastreados(repo: Path) -> None:
    assert hay_cambios(["services/svc", "services/comun"], str(repo)) is False

    _escribir(repo, "services/comun/nuevo.py", "")
    assert hay_cambios(["services/svc"], str(repo)) is False
    assert hay_cambios(["services/svc", "services/comun"], str(repo)) is True


def test_r11_hay_cambios_fuera_de_un_repositorio_es_cambio(tmp_path: Path) -> None:
    """Si git no responde, lo seguro es «no sé»: no hay clave."""
    assert hay_cambios(["x"], str(tmp_path)) is True


def test_r13_raiz_del_repositorio_resuelta(repo: Path) -> None:
    (repo / "services/svc/sub").mkdir()

    assert raiz_del_repositorio(str(repo / "services/svc/sub")) == repo.resolve()


# --- R7 y R8: qué entra en la clave ------------------------------------------


def test_r7_misma_entrada_misma_clave_de_64_hex(repo: Path) -> None:
    servicio = _svc(depende_de=("services/comun",))

    primera = _clave(repo, servicio)

    assert primera == _clave(repo, servicio)
    assert primera is not None and len(primera) == 64
    int(primera, 16)


def test_r7_la_clave_es_el_sha256_del_texto(repo: Path) -> None:
    servicio = _svc()
    texto, _ = texto_de_clave(servicio, str(repo), PY, _sondeo())

    assert texto is not None
    assert _clave(repo, servicio) == hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_r7_texto_canonico(repo: Path) -> None:
    origen = repo / "services/comun/pkg/__init__.py"
    servicio = _svc(depende_de=("services/comun",), importa=("pkg",))

    texto, avisos = texto_de_clave(servicio, str(repo), PY, _sondeo(pkg=str(origen)))

    assert avisos == []
    hash_svc = _git(repo, "rev-parse", "HEAD:services/svc").strip()
    hash_comun = _git(repo, "rev-parse", "HEAD:services/comun").strip()
    assert texto == "\n".join([
        "formato=cache-suites/2",
        f"servicio=services/svc@{hash_svc}",
        f"depende=services/comun@{hash_comun}",
        f"interprete={os.path.normcase(str(Path(PY).resolve()))}",
        f"modulo=pkg@{os.path.normcase(str(origen.resolve()))}",
        "local=.env@ausente",
        "local=services/svc/.env@ausente",
    ])


def test_r7_un_commit_en_el_servicio_cambia_la_clave(repo: Path) -> None:
    antes = _clave(repo, _svc())
    _escribir(repo, "services/svc/app.py", "X = 2\n")
    _commit(repo)

    assert _clave(repo, _svc()) not in (None, antes)


def test_r7_un_commit_en_la_dependencia_cambia_la_clave(repo: Path) -> None:
    servicio = _svc(depende_de=("services/comun",))
    antes = _clave(repo, servicio)
    _escribir(repo, "services/comun/pkg/__init__.py", "Y = 2\n")
    _commit(repo)

    assert _clave(repo, servicio) not in (None, antes)


def test_r7_un_commit_ajeno_no_cambia_la_clave(repo: Path) -> None:
    servicio = _svc(depende_de=("services/comun",))
    antes = _clave(repo, servicio)
    _escribir(repo, "services/otro/otro.py", "Z = 2\n")
    _escribir(repo, "progress/notas.md", "x\n")
    _commit(repo)

    assert _clave(repo, servicio) == antes


def test_r7_otro_interprete_cambia_la_clave(repo: Path, tmp_path: Path) -> None:
    otro = _escribir(tmp_path, "venv/python.exe", "")

    assert _clave(repo, _svc(), interprete=str(otro)) != _clave(repo, _svc())


def test_r7_otro_origen_del_modulo_cambia_la_clave(repo: Path) -> None:
    servicio = _svc(depende_de=("services/comun",), importa=("pkg",))
    uno = repo / "services/comun/pkg/__init__.py"
    otro = repo / "services/comun/pkg"

    assert _clave(repo, servicio, _sondeo(pkg=str(uno))) != _clave(
        repo, servicio, _sondeo(pkg=str(otro)))


def test_r7_la_huella_de_una_entrada_declarada_cambia_la_clave(repo: Path) -> None:
    servicio = _svc(entradas_no_versionadas=("local/config.ini",))
    antes = _clave(repo, servicio)
    _escribir(repo, "local/config.ini", "a=1\n")

    assert _clave(repo, servicio) not in (None, antes)


# --- R8: el orden de declaración no importa -----------------------------------


def test_r8_clave_independiente_del_orden(repo: Path) -> None:
    _escribir(repo, "services/otro/__init__.py", "")
    _commit(repo)
    origen_pkg = str(repo / "services/comun/pkg/__init__.py")
    origen_otro = str(repo / "services/otro/__init__.py")
    sondeo = _sondeo(pkg=origen_pkg, otro=origen_otro)
    a = _svc(depende_de=("services/comun", "services/otro"), importa=("pkg", "otro"),
             entradas_no_versionadas=("local/b.ini", "local/a.ini"))
    b = _svc(depende_de=("services/otro", "services/comun"), importa=("otro", "pkg"),
             entradas_no_versionadas=("local/a.ini", "local/b.ini"))

    assert _clave(repo, a, sondeo) == _clave(repo, b, sondeo)


# --- R9 y R10: entradas locales por metadatos, nunca por contenido -----------


def test_r9_huella_local_es_nombre_tamano_y_mtime(repo: Path) -> None:
    fichero = _escribir(repo, "services/svc/.env", "CLAVE=1\n")
    os.utime(fichero, ns=(1_700_000_000_000_000_000, 1_700_000_000_123_456_700))

    assert huella_local("services/svc/.env", str(repo)) == (
        f"services/svc/.env@{fichero.stat().st_size}:1700000000123456700")
    assert huella_local("services/svc/no.env", str(repo)) == "services/svc/no.env@ausente"


def test_r9_env_de_la_raiz_y_del_servicio_entran_por_defecto(repo: Path) -> None:
    servicio = _svc()
    antes = _clave(repo, servicio)
    raiz_env = _escribir(repo, ".env", "A=1\n")
    con_raiz = _clave(repo, servicio)
    _escribir(repo, "services/svc/.env", "B=1\n")
    con_los_dos = _clave(repo, servicio)
    os.utime(raiz_env, ns=(1, 1))

    assert len({antes, con_raiz, con_los_dos, _clave(repo, servicio)}) == 4


def test_r9_una_entrada_declarada_igual_que_la_de_defecto_no_se_duplica(
    repo: Path,
) -> None:
    texto, _ = texto_de_clave(_svc(entradas_no_versionadas=(".env",)), str(repo), PY,
                              _sondeo())

    assert texto is not None and texto.count("local=.env@") == 1


def test_r10_el_contenido_del_env_no_esta_en_el_texto_de_la_clave(repo: Path) -> None:
    secreto = "SECRETO=no-me-leas-1234"
    _escribir(repo, ".env", secreto + "\n")
    _escribir(repo, "services/svc/.env", secreto + "\n")

    texto, _ = texto_de_clave(_svc(), str(repo), PY, _sondeo())

    assert texto is not None
    assert "SECRETO" not in texto and "no-me-leas" not in texto
    for algoritmo in ("sha256", "sha1", "md5"):
        for contenido in (secreto, secreto + "\n"):
            digest = hashlib.new(algoritmo, contenido.encode("utf-8")).hexdigest()
            assert digest not in texto


def test_r10_huella_local_nunca_abre_el_fichero(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _escribir(repo, "services/svc/.env", "SECRETO=1\n")

    def _prohibido(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"se intentó abrir {args[:1]}")

    monkeypatch.setattr(builtins, "open", _prohibido)
    monkeypatch.setattr(io, "open", _prohibido)
    monkeypatch.setattr(os, "open", _prohibido)

    assert huella_local("services/svc/.env", str(repo)).startswith("services/svc/.env@")


# --- R11 y R12: sin clave ------------------------------------------------------


def test_r11_servicio_sucio_sin_clave_ni_aviso(repo: Path) -> None:
    _escribir(repo, "services/svc/app.py", "X = 99\n")

    assert texto_de_clave(_svc(), str(repo), PY, _sondeo()) == (None, [])


def test_r11_dependencia_con_no_rastreado_sin_clave_ni_aviso(repo: Path) -> None:
    _escribir(repo, "services/comun/suelto.py", "")

    assert texto_de_clave(_svc(depende_de=("services/comun",)), str(repo), PY,
                          _sondeo()) == (None, [])


def test_r12_servicio_fuera_de_head_sin_clave_ni_aviso(repo: Path) -> None:
    servicio = Servicio(nombre="nuevo", ruta="local/nuevo", lenguaje="python")
    _escribir(repo, "local/nuevo/app.py", "")

    assert texto_de_clave(servicio, str(repo), PY, _sondeo()) == (None, [])


def test_r12_dependencia_fuera_de_head_avisa_y_no_da_clave(repo: Path) -> None:
    _escribir(repo, "local/datos.csv", "a\n")

    texto, avisos = texto_de_clave(_svc(depende_de=("local/datos.csv",)), str(repo), PY,
                                   _sondeo())

    assert texto is None
    assert len(avisos) == 1
    assert "local/datos.csv" in avisos[0]
    assert "no está versionada" in avisos[0]
    assert "entradas_no_versionadas" in avisos[0]


# --- R13–R15: dónde resuelve cada módulo vigilado -------------------------------


def test_r13_modulo_fuera_del_repositorio_avisa_y_no_da_clave(
    repo: Path, tmp_path: Path
) -> None:
    fuera = _escribir(tmp_path, "arbol_principal/pkg/__init__.py", "")

    texto, avisos = texto_de_clave(_svc(importa=("pkg",)), str(repo), PY,
                                   _sondeo(pkg=str(fuera)))

    assert texto is None
    assert len(avisos) == 1
    assert "pkg" in avisos[0] and "svc" in avisos[0]
    assert str(fuera) in avisos[0]
    assert "fuera de este repositorio" in avisos[0]
    assert "ESA copia" in avisos[0] and "no la de este árbol" in avisos[0]


@pytest.mark.parametrize("origen", ["built-in", "frozen"])
def test_r13_origen_que_no_es_ruta_cuenta_como_de_fuera(
    repo: Path, origen: str
) -> None:
    texto, avisos = texto_de_clave(_svc(importa=("pkg",)), str(repo), PY,
                                   _sondeo(pkg=origen))

    assert texto is None
    assert len(avisos) == 1 and origen in avisos[0] and "fuera" in avisos[0]


def test_r13_repositorio_vecino_con_prefijo_comun_es_de_fuera(
    repo: Path, tmp_path: Path
) -> None:
    """`repo-worktree` empieza como `repo`, pero es otro árbol (el caso worktree)."""
    vecino = _escribir(tmp_path, "repo-worktree/services/comun/pkg/__init__.py", "")

    texto, avisos = texto_de_clave(_svc(importa=("pkg",)), str(repo), PY,
                                   _sondeo(pkg=str(vecino)))

    assert texto is None and "fuera de este repositorio" in avisos[0]


def test_r14_modulo_dentro_pero_no_declarado_pide_depende_de(repo: Path) -> None:
    origen = repo / "services/comun/pkg/__init__.py"

    texto, avisos = texto_de_clave(_svc(importa=("pkg",)), str(repo), PY,
                                   _sondeo(pkg=str(origen)))

    assert texto is None
    assert len(avisos) == 1
    assert "services/comun/pkg/__init__.py" in avisos[0]
    assert "depende_de" in avisos[0]


def test_r14_modulo_dentro_de_la_propia_ruta_vale(repo: Path) -> None:
    origen = repo / "services/svc/app.py"

    texto, avisos = texto_de_clave(_svc(importa=("app",)), str(repo), PY,
                                   _sondeo(app=str(origen)))

    assert avisos == [] and texto is not None


def test_r15_modulo_no_encontrado_avisa_y_no_da_clave(repo: Path) -> None:
    texto, avisos = texto_de_clave(_svc(importa=("pkg", "falta")), str(repo), PY,
                                   _sondeo(pkg=None))

    assert texto is None
    assert len(avisos) == 2
    assert all("no se encuentra" in aviso and "svc" in aviso for aviso in avisos)
    assert "`pkg`" in avisos[0] or "`pkg`" in avisos[1]
    assert "`falta`" in avisos[0] or "`falta`" in avisos[1]


def test_r15_sonda_con_salida_ilegible(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path) -> None:
    def _falso(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 0, stdout="esto no es json\n", stderr="")

    monkeypatch.setattr(cache_suites.subprocess, "run", _falso)

    with pytest.raises(ErrorDeSonda, match="ilegible"):
        sondear(PY, ("pkg",), tmp_path)


def test_r15_sonda_que_sale_con_error(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path) -> None:
    def _falso(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 3, stdout="", stderr="Traceback\nBoom\n")

    monkeypatch.setattr(cache_suites.subprocess, "run", _falso)

    with pytest.raises(ErrorDeSonda) as error:
        sondear(PY, ("pkg",), tmp_path)

    assert "3" in str(error.value) and "Boom" in str(error.value)


def test_r15_sonda_que_tarda_demasiado(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    vistos: dict = {}

    def _lento(*args: object, **kwargs: object) -> None:
        vistos.update(kwargs)
        raise subprocess.TimeoutExpired(cmd="sonda", timeout=kwargs["timeout"])

    monkeypatch.setattr(cache_suites.subprocess, "run", _lento)

    with pytest.raises(ErrorDeSonda, match="7 s"):
        sondear(PY, ("pkg",), tmp_path, limite_s=7)
    assert vistos["timeout"] == 7


def test_r15_limite_de_la_sonda_por_defecto() -> None:
    assert cache_suites.LIMITE_SONDA_S == 30


def test_r15_interprete_inexistente(tmp_path: Path) -> None:
    with pytest.raises(ErrorDeSonda):
        sondear(str(tmp_path / "no-hay-python.exe"), ("pkg",), tmp_path)


def test_r16_sonda_con_el_interprete_y_la_carpeta_del_servicio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vistos: dict = {}

    def _falso(orden: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        vistos["orden"] = orden
        vistos.update(kwargs)
        return subprocess.CompletedProcess(
            orden, 0, stdout='{"origenes": {"pkg": "/x/pkg", "otro.sub": null}, "coverage": true}\n',
            stderr="")

    monkeypatch.setattr(cache_suites.subprocess, "run", _falso)

    sondeo = sondear("/ruta/del/python", ("pkg", "otro.sub"), tmp_path)

    assert sondeo == Sondeo(origenes={"pkg": "/x/pkg", "otro.sub": None},
                            tiene_coverage=True)
    assert vistos["orden"][0] == "/ruta/del/python"
    assert vistos["orden"][1] == "-c"
    assert "-I" not in vistos["orden"]
    assert vistos["orden"][-2:] == ["pkg", "otro.sub"]
    assert Path(vistos["cwd"]) == tmp_path
    assert vistos["stdin"] is subprocess.DEVNULL
    assert vistos["timeout"] == cache_suites.LIMITE_SONDA_S
    # Un código de salida distinto de 0 lo traduce `sondear` (ErrorDeSonda);
    # con check=True escaparía un CalledProcessError que nadie captura.
    assert vistos["check"] is False


def test_r15_sonda_real_que_sale_con_error_da_error_de_sonda(tmp_path: Path) -> None:
    """Un padre que sale del intérprete al importarse (SystemExit no es Exception)
    hace que la sonda real termine con código 3: ErrorDeSonda, no otra excepción."""
    (tmp_path / "sale").mkdir()
    (tmp_path / "sale" / "__init__.py").write_text("raise SystemExit(3)\n", encoding="utf-8")

    with pytest.raises(ErrorDeSonda, match="código 3"):
        sondear(PY, ("sale.hijo",), tmp_path)


def test_r12_git_que_falla_aunque_imprima_algo_no_da_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un `git rev-parse` que sale con error no da hash, imprima lo que imprima."""
    def _git_falso(args: list[str], raiz: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 128, stdout="a" * 40 + "\n", stderr="")

    monkeypatch.setattr(cache_suites, "_git", _git_falso)

    assert hash_en_head("services/svc", str(tmp_path)) is None


def test_r12_git_que_sale_bien_sin_hash_no_da_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _git_falso(args: list[str], raiz: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, 0, stdout="\n", stderr="")

    monkeypatch.setattr(cache_suites, "_git", _git_falso)

    assert hash_en_head("services/svc", str(tmp_path)) is None


def test_r7_el_sondeo_es_inmutable() -> None:
    """La clave se deriva del sondeo: nadie puede retocarlo a medio cálculo."""
    sondeo = Sondeo(origenes={}, tiene_coverage=False)

    with pytest.raises(dataclasses.FrozenInstanceError):
        sondeo.tiene_coverage = True  # type: ignore[misc]


# --- R17: comparación de rutas ---------------------------------------------------


def test_r17_dentro_de_basico(tmp_path: Path) -> None:
    base = tmp_path / "repo"

    assert _dentro_de(str(base), str(base)) is True
    assert _dentro_de(str(base / "a" / "b.py"), str(base)) is True
    assert _dentro_de(str(tmp_path / "repo2" / "b.py"), str(base)) is False
    assert _dentro_de(str(tmp_path), str(base)) is False


def test_r17_dentro_de_con_rutas_sin_resolver(tmp_path: Path) -> None:
    base = tmp_path / "repo"

    assert _dentro_de(str(base / "x" / ".." / "y.py"), str(base)) is True
    assert _dentro_de(str(base / ".." / "fuera.py"), str(base)) is False


@pytest.mark.skipif(os.name != "nt", reason="mayúsculas y contrabarras: solo Windows")
def test_r17_dentro_de_ignora_mayusculas_y_separadores_en_windows(
    tmp_path: Path,
) -> None:
    base = tmp_path / "Repo"
    ruta = str(base / "Services" / "pkg.py").upper().replace("\\", "/")

    assert _dentro_de(ruta, str(base).lower()) is True


# === Decisión y CLI (R18–R22) ===============================================


SVC = Servicio(nombre="svc", ruta="services/svc", lenguaje="python")


@pytest.fixture(scope="module")
def _plantilla_decision(tmp_path_factory: pytest.TempPathFactory) -> Path:
    raiz = tmp_path_factory.mktemp("plantilla_cache_decision") / "repo"
    (raiz / "services" / "svc").mkdir(parents=True)
    (raiz / "services" / "web").mkdir(parents=True)
    (raiz / "harness").mkdir()
    _git(raiz, "init", "-q")
    (raiz / ".gitignore").write_text(
        ".env\n.arnes_cache/\ncoverage.json\n", encoding="utf-8")
    (raiz / "services" / "svc" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (raiz / "services" / "web" / "index.js").write_text("", encoding="utf-8")
    (raiz / "harness" / "servicios.json").write_text(json.dumps({"servicios": [
        {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python"},
        {"nombre": "web", "ruta": "services/web", "lenguaje": "otro"},
    ]}), encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


@pytest.fixture
def repo_decision(_plantilla_decision: Path, tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    shutil.copytree(_plantilla_decision, raiz)
    return raiz


def _sonda(coverage: bool = False):
    def _falsa(interprete: str, modulos: tuple[str, ...], cwd: Path) -> Sondeo:
        return Sondeo(origenes={}, tiene_coverage=coverage)
    return _falsa


def _clave_decision(repo_decision: Path, coverage: bool = False) -> str:
    clave, _ = clave_de(SVC, str(repo_decision), PY, Sondeo(origenes={}, tiene_coverage=coverage))
    assert clave is not None
    return clave


def _guardar(repo_decision: Path, contenido: str, nombre: str = "svc") -> Path:
    fichero = repo_decision / ".arnes_cache" / f"suite_{nombre}.ok"
    fichero.parent.mkdir(exist_ok=True)
    fichero.write_text(contenido, encoding="utf-8")
    return fichero


# --- R18: servir -------------------------------------------------------------


def test_r18_sirve_con_la_clave_guardada_y_sin_coverage(repo_decision: Path) -> None:
    fichero = _guardar(repo_decision, _clave_decision(repo_decision))
    os.utime(fichero, (1_760_000_000, 1_760_000_000))

    decision = decidir(SVC, str(repo_decision), sondear=_sonda(coverage=False))

    esperada = time.strftime("%Y-%m-%d %H:%M", time.localtime(1_760_000_000))
    assert decision == Decision(servir=True, clave=_clave_decision(repo_decision), fecha_verde=esperada,
                                avisos=())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", decision.fecha_verde)


def test_r18_tolera_espacios_y_salto_de_linea_en_el_fichero(repo_decision: Path) -> None:
    _guardar(repo_decision, f"  {_clave_decision(repo_decision)}\n")

    assert decidir(SVC, str(repo_decision), sondear=_sonda()).servir is True


def test_r18_con_coverage_hace_falta_su_coverage_json(repo_decision: Path) -> None:
    _guardar(repo_decision, _clave_decision(repo_decision, coverage=True))

    sin_json = decidir(SVC, str(repo_decision), sondear=_sonda(coverage=True))
    (repo_decision / "services" / "svc" / "coverage.json").write_text("{}", encoding="utf-8")
    con_json = decidir(SVC, str(repo_decision), sondear=_sonda(coverage=True))

    assert sin_json.servir is False and sin_json.clave == _clave_decision(repo_decision, coverage=True)
    assert sin_json.fecha_verde is None
    assert con_json.servir is True


def test_r18_el_coverage_json_de_la_raiz_no_cuenta(repo_decision: Path) -> None:
    _guardar(repo_decision, _clave_decision(repo_decision, coverage=True))
    (repo_decision / "coverage.json").write_text("{}", encoding="utf-8")

    assert decidir(SVC, str(repo_decision), sondear=_sonda(coverage=True)).servir is False


# --- R19 y R20: ejecutar --------------------------------------------------------


def test_r19_sin_fichero_de_cache_ejecuta_y_devuelve_la_clave(repo_decision: Path) -> None:
    decision = decidir(SVC, str(repo_decision), sondear=_sonda())

    assert decision == Decision(servir=False, clave=_clave_decision(repo_decision), fecha_verde=None,
                                avisos=())


def test_r19_clave_distinta_ejecuta(repo_decision: Path) -> None:
    _guardar(repo_decision, "0" * 64)

    decision = decidir(SVC, str(repo_decision), sondear=_sonda())

    assert decision.servir is False and decision.clave == _clave_decision(repo_decision)


def test_r19_la_cache_de_otro_servicio_no_vale(repo_decision: Path) -> None:
    _guardar(repo_decision, _clave_decision(repo_decision), nombre="otro")

    assert decidir(SVC, str(repo_decision), sondear=_sonda()).servir is False


def test_r19_sin_clave_ejecuta_con_clave_vacia(repo_decision: Path) -> None:
    _guardar(repo_decision, _clave_decision(repo_decision))
    (repo_decision / "services" / "svc" / "app.py").write_text("X = 2\n", encoding="utf-8")

    decision = decidir(SVC, str(repo_decision), sondear=_sonda())

    assert decision == Decision(servir=False, clave=None, fecha_verde=None, avisos=())


def test_r19_sonda_fallida_avisa_y_ejecuta_sin_clave(repo_decision: Path) -> None:
    def _rota(interprete: str, modulos: tuple[str, ...], cwd: Path) -> Sondeo:
        raise ErrorDeSonda("la sonda tardó más de 30 s")

    _guardar(repo_decision, _clave_decision(repo_decision))

    decision = decidir(SVC, str(repo_decision), sondear=_rota)

    assert decision.servir is False and decision.clave is None
    assert len(decision.avisos) == 1
    assert "la sonda tardó más de 30 s" in decision.avisos[0]


def test_r16_decidir_sondea_con_el_interprete_y_la_carpeta_del_servicio(
    repo_decision: Path,
) -> None:
    vistos: dict = {}

    def _espia(interprete: str, modulos: tuple[str, ...], cwd: Path) -> Sondeo:
        vistos.update(interprete=interprete, modulos=modulos, cwd=cwd)
        return Sondeo(origenes={}, tiene_coverage=False)

    decidir(Servicio(nombre="svc", ruta="services/svc", lenguaje="python"),
            str(repo_decision), sondear=_espia)

    assert vistos["interprete"] == PY
    assert vistos["modulos"] == ()
    assert Path(vistos["cwd"]).resolve() == (repo_decision / "services" / "svc").resolve()


def test_r20_cache_del_formato_anterior_nunca_coincide(repo_decision: Path) -> None:
    arbol = subprocess.run(["git", "-C", str(repo_decision), "rev-parse", "HEAD:services/svc"],
                           capture_output=True, text=True, check=True).stdout.strip()
    _guardar(repo_decision, arbol)

    decision = decidir(SVC, str(repo_decision), sondear=_sonda())

    assert len(arbol) == 40
    assert decision.servir is False and decision.clave == _clave_decision(repo_decision)


# --- R21: --sin-cache ------------------------------------------------------------


def test_r21_sin_cache_nunca_sirve_pero_devuelve_la_clave(repo_decision: Path) -> None:
    _guardar(repo_decision, _clave_decision(repo_decision))

    decision = decidir(SVC, str(repo_decision), sin_cache=True, sondear=_sonda())

    assert decision == Decision(servir=False, clave=_clave_decision(repo_decision), fecha_verde=None,
                                avisos=())


# --- R22: protocolo de líneas y CLI -----------------------------------------------


def test_r22_sin_servicio_es_un_error_de_uso(
    repo_decision: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--servicio` es obligatorio: sin él, argparse corta con su código de uso (2)."""
    with pytest.raises(SystemExit) as salida:
        main(["--raiz", str(repo_decision)])

    assert salida.value.code == 2
    assert "--servicio" in capsys.readouterr().err


def test_r22_la_decision_es_inmutable() -> None:
    """Lo que se imprime es lo que se decidió: nadie lo retoca por el camino."""
    decision = Decision(False, None, None, ())

    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.servir = True  # type: ignore[misc]


def test_r22_lineas_de_salida() -> None:
    assert lineas_de_salida(Decision(True, "a" * 64, "2026-10-15 09:30", ())) == [
        "SERVIR|2026-10-15 09:30"]
    assert lineas_de_salida(Decision(False, "b" * 64, None, ("uno", "dos"))) == [
        "AVISO|uno", "AVISO|dos", f"EJECUTAR|{'b' * 64}"]
    assert lineas_de_salida(Decision(False, None, None, ())) == ["EJECUTAR|"]


def test_r22_un_aviso_con_saltos_de_linea_sigue_siendo_una_linea() -> None:
    lineas = lineas_de_salida(Decision(False, None, None, ("uno\ndos\r\ntres",)))

    assert lineas == ["AVISO|uno dos tres", "EJECUTAR|"]


def test_r22_main_ejecutar_con_clave(repo_decision: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision)])

    salida = capsys.readouterr()
    assert codigo == 0
    assert re.fullmatch(r"EJECUTAR\|[0-9a-f]{64}\n", salida.out)
    assert salida.err == ""


def test_r22_main_servir(repo_decision: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--servicio", "svc", "--raiz", str(repo_decision)])
    clave = capsys.readouterr().out.strip().split("|")[1]
    _guardar(repo_decision, clave)
    (repo_decision / "services" / "svc" / "coverage.json").write_text("{}", encoding="utf-8")

    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision)])

    assert codigo == 0
    assert re.fullmatch(r"SERVIR\|\d{4}-\d{2}-\d{2} \d{2}:\d{2}\n", capsys.readouterr().out)


def test_r22_main_sin_cache(repo_decision: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--servicio", "svc", "--raiz", str(repo_decision)])
    clave = capsys.readouterr().out.strip().split("|")[1]
    _guardar(repo_decision, clave)
    (repo_decision / "services" / "svc" / "coverage.json").write_text("{}", encoding="utf-8")

    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision), "--sin-cache"])

    assert codigo == 0
    assert capsys.readouterr().out == f"EJECUTAR|{clave}\n"


def test_r22_main_imprime_avisos_antes_de_la_decision(
    repo_decision: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _rota(interprete: str, modulos: tuple[str, ...], cwd: Path,
              limite_s: int = 30) -> Sondeo:
        raise ErrorDeSonda("motivo de prueba")

    monkeypatch.setattr(cache_suites, "sondear", _rota)

    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision)])

    lineas = capsys.readouterr().out.splitlines()
    assert codigo == 0
    assert len(lineas) == 2
    assert lineas[0].startswith("AVISO|") and "motivo de prueba" in lineas[0]
    assert lineas[1] == "EJECUTAR|"


@pytest.mark.parametrize(
    ("argumentos", "trozo"),
    [
        (["--servicio", "no-existe"], "no-existe"),
        (["--servicio", "web"], "python"),
    ],
)
def test_r22_main_servicio_desconocido_o_no_python_sale_con_1(
    repo_decision: Path, capsys: pytest.CaptureFixture[str], argumentos: list[str], trozo: str
) -> None:
    codigo = main([*argumentos, "--raiz", str(repo_decision)])

    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert trozo in salida.err


def test_r22_main_declaracion_invalida_sale_con_1(
    repo_decision: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo_decision / "harness" / "servicios.json").write_text(json.dumps({"servicios": [
        {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python",
         "depende_de": ["services/no-existe"]}]}), encoding="utf-8")

    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision)])

    salida = capsys.readouterr()
    assert codigo == 1 and salida.out == "" and "services/no-existe" in salida.err


def test_r22_main_sin_declaracion_sale_con_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main(["--servicio", "svc", "--raiz", str(tmp_path)])

    assert codigo == 1 and "svc" in capsys.readouterr().err


def test_r22_main_venv_declarado_que_no_existe_sale_con_1(
    repo_decision: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo_decision / "harness" / "servicios.json").write_text(json.dumps({"servicios": [
        {"nombre": "svc", "ruta": "services/svc", "lenguaje": "python",
         "venv": "services/svc/.venv"}]}), encoding="utf-8")

    codigo = main(["--servicio", "svc", "--raiz", str(repo_decision)])

    salida = capsys.readouterr()
    assert codigo == 1 and salida.out == "" and "venv" in salida.err


def test_r22_modulo_ejecutable_con_python_m(repo_decision: Path) -> None:
    """La forma exacta en que lo llama init.sh, en un proceso aparte."""
    raiz_arnes = Path(__file__).resolve().parents[1]
    proceso = subprocess.run(
        [PY, "-m", "harness.cache_suites", "--servicio", "svc", "--raiz", str(repo_decision)],
        cwd=raiz_arnes, capture_output=True, text=True, encoding="utf-8",
        stdin=subprocess.DEVNULL, check=False,
    )

    assert proceso.returncode == 0, proceso.stderr
    assert re.fullmatch(r"EJECUTAR\|[0-9a-f]{64}\n", proceso.stdout)


# === Escenarios de punta a punta (R31–R33) ===================================


@pytest.fixture(scope="module")
def _plantilla_escenarios(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Se crea una vez por módulo: en Windows, cada proceso git cuesta."""
    raiz = tmp_path_factory.mktemp("plantilla_cache_escenarios") / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _escribir(raiz, ".gitignore", ".env\n__pycache__/\n")
    _escribir(raiz, "services/app/main.py", "import comunlib\n")
    _escribir(raiz, "services/comun/comunlib/__init__.py", "VALOR = 1\n")
    _escribir(raiz, "services/solo/main.py", "X = 1\n")
    _commit(raiz)
    return raiz


@pytest.fixture
def repo_escenarios(_plantilla_escenarios: Path, tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    shutil.copytree(_plantilla_escenarios, raiz)
    return raiz


APP = Servicio(nombre="app", ruta="services/app", lenguaje="python",
               depende_de=("services/comun",))
SOLO = Servicio(nombre="solo", ruta="services/solo", lenguaje="python")


# --- R31: escenario (a) -------------------------------------------------------


def test_r31_commit_en_la_dependencia_cambia_la_clave_del_dependiente(
    repo_escenarios: Path,
) -> None:
    app_antes = decidir(APP, str(repo_escenarios)).clave
    solo_antes = decidir(SOLO, str(repo_escenarios)).clave

    _escribir(repo_escenarios, "services/comun/comunlib/__init__.py", "VALOR = 2  # comentario\n")
    _commit(repo_escenarios)

    app_despues = decidir(APP, str(repo_escenarios)).clave
    assert app_antes is not None and app_despues is not None
    assert app_despues != app_antes
    assert solo_antes is not None
    assert decidir(SOLO, str(repo_escenarios)).clave == solo_antes


# --- R32: escenario (b), el worktree que importa la comun de otro árbol --------


def test_r32_modulo_de_fuera_del_repositorio_ejecuta_sin_clave_y_avisa(
    repo_escenarios: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fuera = tmp_path / "fuera"
    _escribir(fuera, "comunlib/__init__.py", "VALOR = 'del arbol principal'\n")
    monkeypatch.setenv("PYTHONPATH", str(fuera))
    servicio = Servicio(nombre="app", ruta="services/app", lenguaje="python",
                        depende_de=("services/comun",), importa=("comunlib",))
    (repo_escenarios / ".arnes_cache").mkdir()
    (repo_escenarios / ".arnes_cache" / "suite_app.ok").write_text("x" * 64, encoding="utf-8")

    decision = decidir(servicio, str(repo_escenarios))
    lineas = lineas_de_salida(decision)

    assert decision.servir is False and decision.clave is None
    assert lineas[-1] == "EJECUTAR|"
    assert len(lineas) == 2 and lineas[0].startswith("AVISO|")
    assert "comunlib" in lineas[0]
    assert "fuera de este repositorio" in lineas[0]
    assert os.path.normcase(str(fuera.resolve())) in os.path.normcase(lineas[0])


# --- R33: el encargo 1.7.12, el .env que cambia y el __pycache__ que no cuenta --


def test_r33_tocar_el_env_del_servicio_cambia_la_clave(repo_escenarios: Path) -> None:
    env = _escribir(repo_escenarios, "services/solo/.env", "A=1\n")
    os.utime(env, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    antes = decidir(SOLO, str(repo_escenarios)).clave

    os.utime(env, ns=(1_600_000_000_000_000_000, 1_600_000_100_000_000_000))

    despues = decidir(SOLO, str(repo_escenarios)).clave
    assert antes is not None and despues is not None and despues != antes


def test_r33_tocar_el_pycache_del_servicio_no_cambia_la_clave(repo_escenarios: Path) -> None:
    antes = decidir(SOLO, str(repo_escenarios)).clave

    _escribir(repo_escenarios, "services/solo/__pycache__/main.cpython-312.pyc", "basura")

    assert antes is not None
    assert decidir(SOLO, str(repo_escenarios)).clave == antes


# --- R16: la sonda localiza sin importar --------------------------------------


def test_r16_la_sonda_real_no_ejecuta_el_modulo_vigilado(tmp_path: Path) -> None:
    marcador = tmp_path / "importado.txt"
    carpeta = tmp_path / "servicio"
    _escribir(carpeta, "vigilado/__init__.py",
              f"open({str(marcador)!r}, 'w').write('importado')\n")

    sondeo = sondear(PY, ("vigilado",), carpeta)

    assert not marcador.exists(), "la sonda ejecutó el __init__ del módulo vigilado"
    assert sondeo.origenes["vigilado"] is not None
    assert Path(sondeo.origenes["vigilado"]).resolve() == (
        carpeta / "vigilado" / "__init__.py").resolve()


def test_r16_la_sonda_real_resuelve_desde_la_carpeta_del_servicio(
    tmp_path: Path,
) -> None:
    """El módulo solo es alcanzable desde la carpeta del servicio (su cwd)."""
    _escribir(tmp_path / "a", "solo_en_a.py", "")
    _escribir(tmp_path / "b", "otra.py", "")

    assert sondear(PY, ("solo_en_a",), tmp_path / "a").origenes["solo_en_a"] is not None
    assert sondear(PY, ("solo_en_a",), tmp_path / "b").origenes["solo_en_a"] is None


def test_r16_la_sonda_real_paquete_de_espacio_de_nombres_y_submodulo(
    tmp_path: Path,
) -> None:
    _escribir(tmp_path, "espacio/modulo.py", "")
    _escribir(tmp_path, "pkg/__init__.py", "")
    _escribir(tmp_path, "pkg/sub.py", "")

    sondeo = sondear(PY, ("espacio", "pkg.sub", "pkg.falta", "nada.de.nada"), tmp_path)

    assert Path(sondeo.origenes["espacio"]).resolve() == (tmp_path / "espacio").resolve()
    assert Path(sondeo.origenes["pkg.sub"]).resolve() == (tmp_path / "pkg/sub.py").resolve()
    assert sondeo.origenes["pkg.falta"] is None
    assert sondeo.origenes["nada.de.nada"] is None


def test_r16_la_sonda_real_dice_si_hay_coverage(tmp_path: Path) -> None:
    try:
        import coverage  # noqa: F401

        esperado = True
    except ImportError:
        esperado = False

    assert sondear(PY, (), tmp_path).tiene_coverage is esperado


def test_r16_la_sonda_ignora_lo_que_imprima_un_paquete_padre(tmp_path: Path) -> None:
    _escribir(tmp_path, "ruidoso/__init__.py", "print('hola desde el padre')\n")
    _escribir(tmp_path, "ruidoso/hijo.py", "")

    sondeo = sondear(PY, ("ruidoso.hijo",), tmp_path)

    assert Path(sondeo.origenes["ruidoso.hijo"]).name == "hijo.py"
