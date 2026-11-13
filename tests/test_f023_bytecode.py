# tests/test_f023_bytecode.py
"""F-023 · El bytecode no decide ningún veredicto (R14, R15, R23, R24).

Dos defensas distintas, cada una con su prueba:

- **Prefijo por campaña (R23, R24).** `EjecutorPytest.correr` lanza la suite
  con `PYTHONPYCACHEPREFIX` apuntando a un directorio vacío, uno por raíz. Con
  él, CPython no lee NINGÚN `__pycache__` del árbol: ni el que dejó una campaña
  anterior ni el que una purga no pudo borrar. La prueba no espera a que el
  reloj regale la coincidencia (tamaño, mtime): la FABRICA, dejando en el
  `__pycache__` del árbol un `.pyc` del código ORIGINAL marcado como
  «unchecked-hash» (PEP 552), que CPython da por válido para cualquier fuente
  que haya en disco. Sin prefijo, el mutante se juzga con ese bytecode y sale
  superviviente; con prefijo, muere, que es lo que dice el fuente.
- **Purga avisada (R14, R15).** Lo que `_purgar_bytecode` no pudo borrar ya no
  se traga: se avisa y consta en el informe.
"""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    EjecutorPytest,
    ejecutar_campania,
    generar_mutantes,
)
from harness.mutacion_paralela import ejecutar_campania_paralela
from harness.tiempos import escalar_timeout

#: Reloj de los pytest anidados: solo para que un cuelgue no cuelgue la suite.
TIMEOUT_S = escalar_timeout(240)

#: Dos funciones, cada una con su test: los dos mutantes aritméticos MUEREN
#: si se juzga el fuente que hay en disco.
PRODUCTO = """# producto.py
def doble(x):
    return x * 2


def siguiente(x):
    return x + 1
"""

TEST_PRODUCTO = """# test_producto.py
import producto


def test_doble():
    assert producto.doble(3) == 6


def test_siguiente():
    assert producto.siguiente(3) == 4
"""

LINEAS = {3, 7}


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def _repositorio_con_cache_forjada(destino: Path) -> Path:
    """Repositorio de juguete con un `.pyc` previo que miente sobre el fuente.

    El `.pyc` se compila desde el fuente ORIGINAL en modo `UNCHECKED_HASH`:
    CPython lo carga sin compararlo con el `.py`, así que cualquier mutante
    escrito en disco se ejecutaría como el original. Se versiona, para que
    llegue también a los worktrees de la campaña paralela, que nacen de HEAD.
    """
    destino.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(destino)], check=True, capture_output=True
    )
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    (destino / "producto.py").write_text(PRODUCTO, encoding="utf-8", newline="")
    (destino / "test_producto.py").write_text(TEST_PRODUCTO, encoding="utf-8", newline="")
    cache = destino / "__pycache__"
    cache.mkdir()
    py_compile.compile(
        str(destino / "producto.py"),
        cfile=str(cache / f"producto.{sys.implementation.cache_tag}.pyc"),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial con caché forjada")
    return destino


def _alcance() -> Alcance:
    return Alcance(
        feature="F-999",
        origen="rama",
        ref_diff=("dev", "feature/F-999-juguete"),
        lineas={"producto.py": set(LINEAS)},
    )


def _aritmeticos() -> list:
    """Los dos mutantes aritméticos (`*`→`//`, `+`→`-`): los tests los cazan."""
    return [
        m
        for m in generar_mutantes(PRODUCTO, LINEAS, "producto.py")
        if m.operador == "aritmetico"
    ]


@pytest.fixture
def sin_purga(monkeypatch: pytest.MonkeyPatch) -> None:
    """La purga borraría el `.pyc` forjado: aquí se mide el prefijo, no ella."""
    monkeypatch.setattr(mutacion, "_purgar_bytecode", lambda ruta: [])


@pytest.fixture(autouse=True)
def _prefijos_retirados():
    yield
    retirar = getattr(mutacion, "retirar_prefijos", None)
    if retirar is not None:
        retirar()


# --- R23 · el entorno del subproceso ----------------------------------------


def _capturar_entornos(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    entornos: list[dict] = []

    def falso_run(orden, **opciones):
        entorno = opciones["env"]
        prefijo = entorno.get("PYTHONPYCACHEPREFIX")
        entornos.append(
            {
                **entorno,
                "_vacio": prefijo is not None
                and Path(prefijo).is_dir()
                and not os.listdir(prefijo),
            }
        )
        return subprocess.CompletedProcess(orden, 1, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", falso_run)
    return entornos


def test_f023_r23_prefijo_vacio_y_sin_escribir_bytecode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PYTHONPYCACHEPREFIX", str(tmp_path / "el_del_entorno"))
    entornos = _capturar_entornos(monkeypatch)

    EjecutorPytest(raiz=str(tmp_path)).correr(timeout_s=60)

    entorno = entornos[0]
    assert entorno["PYTHONDONTWRITEBYTECODE"] == "1"
    assert entorno.get("PYTHONPYCACHEPREFIX"), "sin prefijo, CPython lee __pycache__"
    assert entorno["PYTHONPYCACHEPREFIX"] != str(tmp_path / "el_del_entorno"), (
        "el prefijo del entorno no se respeta: apuntaría a una caché ya poblada"
    )
    assert entorno["_vacio"], "el prefijo tiene que existir y estar vacío"


def test_f023_r23_prefijo_igual_en_base_y_mutante_y_distinto_por_raiz(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entornos = _capturar_entornos(monkeypatch)
    uno, otro = tmp_path / "uno", tmp_path / "otro"
    uno.mkdir()
    otro.mkdir()

    EjecutorPytest(raiz=str(uno)).linea_base(60)
    EjecutorPytest(raiz=str(uno), ruta="tests").ejecutar(60)
    EjecutorPytest(raiz=str(otro)).ejecutar(60)

    prefijos = [e.get("PYTHONPYCACHEPREFIX") for e in entornos]
    assert prefijos[0] and prefijos[0] == prefijos[1], "misma raíz, mismo prefijo"
    assert prefijos[2] and prefijos[2] != prefijos[0], "un worktree, un prefijo"


def test_f023_r23_prefijos_retirados_al_final(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entornos = _capturar_entornos(monkeypatch)
    EjecutorPytest(raiz=str(tmp_path)).correr(timeout_s=60)
    prefijo = Path(entornos[0]["PYTHONPYCACHEPREFIX"])
    assert prefijo.is_dir()

    mutacion.retirar_prefijos()

    assert not prefijo.exists()


def test_f023_r23_retirar_un_prefijo_que_ya_no_existe_no_rompe_la_salida(
    tmp_path: Path,
) -> None:
    prefijo = Path(mutacion.prefijo_pycache(str(tmp_path)))
    prefijo.rmdir()  # alguien lo borró antes (limpieza del temporal, otra sesión)

    mutacion.retirar_prefijos()  # va en el `finally` de `main`: no puede lanzar

    assert mutacion.prefijo_pycache(str(tmp_path)) != str(prefijo), "el registro quedó vacío"
    mutacion.retirar_prefijos()


def test_f023_r23_main_retira_los_prefijos_pase_lo_que_pase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas: list[str] = []
    monkeypatch.setattr(mutacion, "retirar_prefijos", lambda: llamadas.append("r"))

    monkeypatch.setattr(mutacion, "_main", lambda argv, ejecutor: 0)
    assert mutacion.main([]) == 0

    def revienta(argv, ejecutor):
        raise RuntimeError("boom")

    monkeypatch.setattr(mutacion, "_main", revienta)
    with pytest.raises(RuntimeError):
        mutacion.main([])

    assert llamadas == ["r", "r"]


# --- R24 · la caché previa forjada no decide el veredicto -------------------


def test_f023_r24_prefijo_la_cache_forjada_no_salva_al_mutante_en_serie(
    tmp_path: Path, sin_purga: None
) -> None:
    repositorio = _repositorio_con_cache_forjada(tmp_path / "juguete")

    informe = ejecutar_campania(
        _alcance(),
        EjecutorPytest(raiz=str(repositorio)),
        timeout_s=TIMEOUT_S,
        raiz=str(repositorio),
        mutantes=_aritmeticos(),
    )

    assert informe.timeouts == []
    assert informe.supervivientes == [], (
        "el mutante se juzgó con el .pyc forjado y no con el fuente en disco: "
        f"{[m.descripcion() for m in informe.supervivientes]}"
    )
    assert informe.muertos == 2
    assert informe.fiable


def test_f023_r24_prefijo_la_cache_forjada_no_salva_al_mutante_en_paralelo(
    tmp_path: Path, sin_purga: None
) -> None:
    repositorio = _repositorio_con_cache_forjada(tmp_path / "juguete")

    informe = ejecutar_campania_paralela(
        _alcance(),
        [],
        timeout_s=TIMEOUT_S,
        raiz=str(repositorio),
        workers=2,
        mutantes=_aritmeticos(),
    )

    assert informe.timeouts == []
    assert informe.supervivientes == [], (
        "en paralelo, el worktree trae el .pyc forjado y decide el veredicto: "
        f"{[m.descripcion() for m in informe.supervivientes]}"
    )
    assert informe.muertos == 2


# --- R14, R15 · la purga que falla avisa ------------------------------------

FUENTE_APP = "# app.py\ndef bandera():\n    return True\n"


class _Doble:
    """Ejecutor sin suite: todo mutante muere, la base siempre está verde."""

    raiz = "."

    def identidad(self) -> tuple[str, str]:
        return (".", "doble")

    def ejecutar(self, timeout_s: int) -> str:
        return "muerto"

    def linea_base(self, timeout_s: int):
        return mutacion.ResultadoSuite(codigo=0)


@pytest.fixture
def arbol_con_pyc(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "dev", str(tmp_path)], check=True)
    for clave, valor in (("user.email", "arnes@ruesma.es"), ("user.name", "Arnes")):
        subprocess.run(["git", "-C", str(tmp_path), "config", clave, valor], check=True)
    (tmp_path / "app.py").write_text(FUENTE_APP, encoding="utf-8", newline="")
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "i"], check=True)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"viejo")
    return tmp_path


@pytest.fixture
def unlink_que_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.unlink

    def unlink(self: Path, *args, **kwargs):
        if self.suffix == ".pyc":
            raise PermissionError("en uso por otro proceso")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)


def _alcance_app() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/x"),
                   lineas={"app.py": {3}})


def test_f023_r14_aviso_la_purga_devuelve_lo_que_no_pudo_borrar(
    arbol_con_pyc: Path, unlink_que_falla: None
) -> None:
    restos = mutacion._purgar_bytecode(arbol_con_pyc / "app.py")

    assert len(restos) == 1
    assert "app.cpython-312.pyc" in restos[0]
    assert "en uso por otro proceso" in restos[0]


def test_f023_r14_aviso_por_eco_y_en_el_informe(
    arbol_con_pyc: Path, unlink_que_falla: None, tmp_path_factory: pytest.TempPathFactory
) -> None:
    eco: list[str] = []

    informe = ejecutar_campania(_alcance_app(), _Doble(), raiz=str(arbol_con_pyc),
                                eco=eco.append)

    avisos = [linea for linea in eco if linea.startswith("AVISO: no se pudo borrar")]
    assert avisos, eco
    assert "app.cpython-312.pyc" in avisos[0]
    assert "si el ejecutor no aísla el bytecode" in avisos[0]
    assert len(informe.pyc_no_borrados) == 1, "un resto se cuenta una vez"
    ruta = tmp_path_factory.mktemp("informe") / "mutacion_F-999.md"
    mutacion.escribir_informe(informe, ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert "## Bytecode que no se pudo borrar" in texto
    assert "app.cpython-312.pyc" in texto.split("## Bytecode que no se pudo borrar")[1]


def test_f023_r14_aviso_sin_eco_va_a_stderr(
    arbol_con_pyc: Path, unlink_que_falla: None, capsys: pytest.CaptureFixture[str]
) -> None:
    ejecutar_campania(_alcance_app(), _Doble(), raiz=str(arbol_con_pyc))

    assert "AVISO: no se pudo borrar" in capsys.readouterr().err


def test_f023_r15_aviso_ausente_si_todo_se_borra(
    arbol_con_pyc: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    eco: list[str] = []
    informe = ejecutar_campania(_alcance_app(), _Doble(), raiz=str(arbol_con_pyc),
                                eco=eco.append)
    ruta = tmp_path_factory.mktemp("informe") / "mutacion_F-999.md"
    mutacion.escribir_informe(informe, ruta)

    assert informe.pyc_no_borrados == []
    assert not any(linea.startswith("AVISO") for linea in eco)
    assert "## Bytecode que no se pudo borrar" not in ruta.read_text(encoding="utf-8")
