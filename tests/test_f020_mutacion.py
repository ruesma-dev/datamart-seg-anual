# tests/test_f020_mutacion.py
"""F-020 · Mutación en un monorepo (R15, R16, R2).

Ningún test de este fichero lanza pytest de verdad: `subprocess.run` se
sustituye siempre por un doble que devuelve el código de salida que interesa.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    INDETERMINADO,
    MUERTO,
    PYTEST_SIN_TESTS,
    SUPERVIVIENTE,
    TIMEOUT,
    EjecutorPytest,
    Mutante,
    ejecutar_campania,
    ejecutor_para,
)
from harness.servicios import Servicio

SERVICIOS = [
    Servicio(
        nombre="email",
        ruta="services/email",
        lenguaje="python",
        venv="services/email/.venv",
    ),
    Servicio(nombre="web", ruta="services/web", lenguaje="otro"),
]


class RunFalso:
    """Doble de `subprocess.run` que anota la llamada y devuelve un código."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.llamadas: list[dict] = []

    def __call__(self, orden: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        self.llamadas.append({"orden": orden, **kwargs})
        return subprocess.CompletedProcess(orden, self.returncode)


def falso_venv(raiz: Path, ruta: str) -> Path:
    destino = raiz / ruta / "Scripts" / "python.exe"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("", encoding="utf-8")
    return destino


def repositorio(raiz: Path) -> Path:
    """Deja `raiz` como repositorio git con todo lo que hay ya commiteado.

    El arnés 1.6.0 añadió `guardia_arbol_limpio`: la campaña se niega a arrancar
    si git no puede declarar limpios los ficheros que va a mutar, así que un
    `tmp_path` suelto ya no vale como árbol de trabajo.
    """

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(raiz), *args], check=True, capture_output=True
        )

    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(raiz)], check=True, capture_output=True
    )
    git("config", "user.email", "arnes@example.invalid")
    git("config", "user.name", "Arnes")
    git("add", "-A")
    git("commit", "-q", "-m", "inicial")
    return raiz


# --- R16: una suite que no recoge tests no caza nada ------------------------


def test_f020_r16_exit_5_es_superviviente(monkeypatch: pytest.MonkeyPatch) -> None:
    # pytest devuelve 5 cuando no recoge NINGÚN test. Darlo por «muerto» sería
    # dar por cazado un mutante que nadie ha comprobado.
    monkeypatch.setattr(subprocess, "run", RunFalso(PYTEST_SIN_TESTS))

    assert EjecutorPytest().ejecutar(10) == SUPERVIVIENTE
    assert PYTEST_SIN_TESTS == 5


def test_f020_r16_exit_1_sigue_siendo_muerto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", RunFalso(1))

    assert EjecutorPytest().ejecutar(10) == MUERTO


def test_f020_r16_exit_0_sigue_siendo_superviviente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", RunFalso(0))

    assert EjecutorPytest().ejecutar(10) == SUPERVIVIENTE


def test_f020_r16_otros_codigos_de_error_no_juzgan_nada_y_son_indeterminado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # El arnés 1.6.0 rompe el veredicto binario: el 2 (recolección
    # interrumpida), el 3 (error interno) y el 4 (mal uso) dicen que la suite ni
    # llegó a juzgar, así que ya no son MUERTO sino INDETERMINADO, y quien lo
    # resuelve es la campaña corriendo la línea base ahí mismo.
    for codigo in (2, 3, 4, 6):
        monkeypatch.setattr(subprocess, "run", RunFalso(codigo))
        veredicto = EjecutorPytest().ejecutar(10)

        assert veredicto == INDETERMINADO, codigo
        # Y sigue sin ser ninguna de las tres respuestas que cierran una
        # feature: dar por cazado lo que nadie comprobó era el defecto.
        assert veredicto not in (MUERTO, SUPERVIVIENTE, TIMEOUT), codigo


def test_f020_r16_el_timeout_sigue_siendo_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reventar(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(subprocess, "run", reventar)

    assert EjecutorPytest().ejecutar(1) == TIMEOUT


# --- R15: cada mutante se juzga con la suite de su servicio -----------------


def test_f020_r15_el_ejecutor_usa_su_cwd_y_su_interprete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doble = RunFalso(0)
    monkeypatch.setattr(subprocess, "run", doble)

    EjecutorPytest(raiz="services/email", ejecutable="/venv/bin/python").ejecutar(10)

    (llamada,) = doble.llamadas
    assert llamada["orden"][:3] == ["/venv/bin/python", "-m", "pytest"]
    assert llamada["cwd"] == "services/email"


def test_f020_r15_mutante_de_servicio_usa_su_suite(tmp_path: Path) -> None:
    interprete = falso_venv(tmp_path, "services/email/.venv")

    ejecutor = ejecutor_para(
        "services/email/app/flujo.py", SERVICIOS, raiz=str(tmp_path)
    )

    assert Path(ejecutor.raiz) == tmp_path / "services" / "email"
    assert ejecutor.ejecutable == interprete.resolve().as_posix()


def test_f020_r15_mutante_fuera_de_servicios_usa_la_raiz(tmp_path: Path) -> None:
    ejecutor = ejecutor_para("harness/alcance.py", SERVICIOS, raiz=str(tmp_path))

    assert ejecutor.raiz == str(tmp_path)
    assert ejecutor.ejecutable == sys.executable


def test_f020_r15_mutante_de_servicio_no_python_usa_la_raiz(tmp_path: Path) -> None:
    # Un `.py` suelto dentro de un servicio declarado de otro lenguaje (scripts
    # de infraestructura, por ejemplo): no hay suite propia que ejecutar.
    ejecutor = ejecutor_para("services/web/tooling.py", SERVICIOS, raiz=str(tmp_path))

    assert ejecutor.raiz == str(tmp_path)
    assert ejecutor.ejecutable == sys.executable


def test_f020_r15_venv_inexistente_no_cae_al_interprete_global(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"services/email/\.venv"):
        ejecutor_para("services/email/app/flujo.py", SERVICIOS, raiz=str(tmp_path))


class EjecutorDoble:
    """Ejecutor de mentira que recuerda cuántas veces lo llamaron."""

    def __init__(self, veredicto: str = SUPERVIVIENTE) -> None:
        self.veredicto = veredicto
        self.llamadas = 0

    def ejecutar(self, timeout_s: int) -> str:
        self.llamadas += 1
        return self.veredicto


def alcance_de(ficheros: dict[str, set[int]]) -> Alcance:
    return Alcance(
        feature="F-042", origen="rama", ref_diff=("base", "rama"), lineas=ficheros
    )


def test_f020_r15_la_campania_pide_un_ejecutor_por_fichero(tmp_path: Path) -> None:
    (tmp_path / "services" / "email" / "app").mkdir(parents=True)
    (tmp_path / "services" / "email" / "app" / "flujo.py").write_text(
        "def f(a, b):\n    return a == b\n", encoding="utf-8"
    )
    (tmp_path / "raiz.py").write_text("def g(a, b):\n    return a > b\n", encoding="utf-8")
    # El arnés 1.6.0 exige un árbol que git pueda declarar limpio antes de mutar
    # nada: sin repositorio, la campaña aborta con `ArbolSucio` y no reparte.
    repositorio(tmp_path)
    del_servicio = EjecutorDoble(MUERTO)
    de_la_raiz = EjecutorDoble(SUPERVIVIENTE)
    pedidos: list[str] = []

    def factoria(fichero: str) -> EjecutorDoble:
        pedidos.append(fichero)
        return del_servicio if fichero.startswith("services/") else de_la_raiz

    informe = ejecutar_campania(
        alcance_de({"services/email/app/flujo.py": {2}, "raiz.py": {2}}),
        EjecutorDoble(TIMEOUT),
        raiz=str(tmp_path),
        ejecutor_de=factoria,
    )

    assert sorted(set(pedidos)) == ["raiz.py", "services/email/app/flujo.py"]
    assert del_servicio.llamadas == 1
    assert de_la_raiz.llamadas == 1
    assert informe.muertos == 1
    assert len(informe.supervivientes) == 1
    assert not informe.timeouts, "el ejecutor único no debe usarse si hay factoría"
    # La garantía de F-015 sigue en pie: el árbol queda como estaba.
    assert (tmp_path / "raiz.py").read_text(encoding="utf-8") == (
        "def g(a, b):\n    return a > b\n"
    )


def test_f020_r15_la_restauracion_aguanta_aunque_la_factoria_falle(
    tmp_path: Path,
) -> None:
    fuente = "def g(a, b):\n    return a > b\n"
    (tmp_path / "raiz.py").write_text(fuente, encoding="utf-8")
    repositorio(tmp_path)
    pedidos: list[str] = []

    def factoria(fichero: str) -> EjecutorDoble:
        pedidos.append(fichero)
        raise ValueError("venv declarado inexistente")

    with pytest.raises(ValueError):
        ejecutar_campania(
            alcance_de({"raiz.py": {2}}),
            EjecutorDoble(),
            raiz=str(tmp_path),
            ejecutor_de=factoria,
        )

    # La avería es la de la factoría y no otra: se la pidió y reventó ella.
    assert pedidos == ["raiz.py"]
    assert (tmp_path / "raiz.py").read_text(encoding="utf-8") == fuente


# --- R2: sin declaración, el camino de siempre ------------------------------


def test_f020_r2_mutacion_sin_servicios_camino_actual(tmp_path: Path) -> None:
    ejecutor = ejecutor_para("cualquiera.py", [], raiz=str(tmp_path))

    assert ejecutor.raiz == str(tmp_path)
    assert ejecutor.ejecutable == sys.executable


def test_f020_r2_la_campania_sin_factoria_usa_el_ejecutor_unico(tmp_path: Path) -> None:
    (tmp_path / "raiz.py").write_text("def g(a, b):\n    return a > b\n", encoding="utf-8")
    repositorio(tmp_path)
    unico = EjecutorDoble(MUERTO)

    informe = ejecutar_campania(
        alcance_de({"raiz.py": {2}}), unico, raiz=str(tmp_path)
    )

    assert unico.llamadas == 1
    assert informe.muertos == 1


def test_f020_r2_main_sin_declaracion_no_construye_factoria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El `main` mono-proyecto sigue pasando un solo ejecutor a la campaña."""
    (tmp_path / "raiz.py").write_text("def g(a, b):\n    return a > b\n", encoding="utf-8")
    repositorio(tmp_path)
    monkeypatch.setattr(
        mutacion, "alcance_de_feature", lambda *a, **k: alcance_de({"raiz.py": {2}})
    )
    unico = EjecutorDoble(MUERTO)

    codigo = mutacion.main(
        [
            "--feature",
            "F-042",
            "--raiz",
            str(tmp_path),
            "--salida",
            str(tmp_path / "informe.md"),
        ],
        ejecutor=unico,
    )

    assert codigo == 0
    assert unico.llamadas == 1


def test_f020_r15_main_con_servicios_respeta_el_ejecutor_inyectado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con declaración, un ejecutor inyectado sigue mandando sobre la factoría.

    Es lo que evita que un test o una herramienta que pasa su propio doble
    acabe lanzando suites de verdad, servicio por servicio.
    """
    (tmp_path / "harness").mkdir()
    (tmp_path / "services" / "email").mkdir(parents=True)
    (tmp_path / "harness" / "servicios.json").write_text(
        '{"servicios": [{"nombre": "email", "ruta": "services/email",'
        ' "lenguaje": "python"}]}',
        encoding="utf-8",
    )
    fichero = tmp_path / "services" / "email" / "flujo.py"
    fichero.write_text("def g(a, b):\n    return a > b\n", encoding="utf-8")
    repositorio(tmp_path)
    monkeypatch.setattr(
        mutacion,
        "alcance_de_feature",
        lambda *a, **k: alcance_de({"services/email/flujo.py": {2}}),
    )
    unico = EjecutorDoble(MUERTO)

    codigo = mutacion.main(
        [
            "--feature",
            "F-042",
            "--raiz",
            str(tmp_path),
            "--salida",
            str(tmp_path / "informe.md"),
        ],
        ejecutor=unico,
    )

    assert codigo == 0
    assert unico.llamadas == 1


def test_f020_r3_main_con_declaracion_rota_no_muta_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "servicios.json").write_text("{roto", encoding="utf-8")
    monkeypatch.setattr(
        mutacion, "alcance_de_feature", lambda *a, **k: alcance_de({"raiz.py": {2}})
    )

    # `--salida` dentro de tmp_path: ningún test escribe en progress/ del repo.
    codigo = mutacion.main(
        [
            "--feature",
            "F-042",
            "--raiz",
            str(tmp_path),
            "--salida",
            str(tmp_path / "informe.md"),
        ]
    )

    assert codigo == 2
    assert "no es JSON válido" in capsys.readouterr().err
    assert not (tmp_path / "informe.md").exists(), "no se muta nada si la declaración está rota"


def test_f020_r15_generar_mutantes_no_cambia_con_las_rutas_de_servicio() -> None:
    """El mutador es indiferente a la profundidad de la ruta."""
    mutantes = mutacion.generar_mutantes(
        "def f(a, b):\n    return a == b\n", {2}, "services/email/app/flujo.py"
    )

    assert [m.mutado for m in mutantes] == ["return a != b"]
    assert all(isinstance(m, Mutante) for m in mutantes)
    assert mutantes[0].fichero == "services/email/app/flujo.py"
