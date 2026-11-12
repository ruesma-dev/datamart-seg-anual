# tests/test_f019_paralelo.py
"""F-019 · Selección de tests en la campaña paralela (R5, R6, R29).

El mapa se mide UNA vez, en `wk_0` y antes de arrancar los hilos; todos los
workers y el repaso de timeouts juzgan con ese mismo mapa, cada uno tras
comprobar que su HEAD es el del mapa; y `fusionar` y `reemplazar_timeouts`
conservan podados, revalidados y contadores. Repositorio git de juguete y
ejecutores dobles: aquí no se corre ninguna suite.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from harness import mutacion, mutacion_paralela
from harness.alcance import Alcance
from harness.mapa_tests import MapaTests
from harness.mutacion import (
    MUERTO,
    SUPERVIVIENTE,
    TIMEOUT,
    InformeMutacion,
    Mutante,
    ResultadoSuite,
    _leer,
)
from harness.mutacion_paralela import ejecutar_campania_paralela, fusionar, reemplazar_timeouts

FUENTE = """\
def a(x):
    y = x + 1
    return y * 3


def b(x):
    return x * 2


def c(x):
    return x - 3
"""

ORDEN = ("t::a", "t::b", "t::c")


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(raiz), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    (raiz / "pkg").mkdir(parents=True)
    (raiz / "pkg" / "mod.py").write_text(FUENTE, encoding="utf-8", newline="")
    subprocess.run(["git", "init", "-q", "-b", "dev", str(raiz)], check=True,
                   capture_output=True)
    _git(raiz, "config", "user.email", "arnes@ruesma.es")
    _git(raiz, "config", "user.name", "Arnes")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicial")
    return raiz


def _alcance() -> Alcance:
    return Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"),
                   lineas={"pkg/mod.py": {2, 3, 7, 11}})


class Registro:
    def __init__(self) -> None:
        self.cerrojo = threading.Lock()
        self.eventos: list[tuple[str, str]] = []
        self.timeouts_pendientes = {7}

    def anotar(self, tipo: str, raiz: str) -> None:
        with self.cerrojo:
            self.eventos.append((tipo, Path(raiz).name))


class Doble:
    def __init__(self, raiz: str, registro: Registro) -> None:
        self.raiz = raiz
        self.ejecutable = "py"
        self.ruta = "tests"
        self.registro = registro

    def _mutada(self) -> int | None:
        actual = _leer(Path(self.raiz) / "pkg" / "mod.py").splitlines()
        for numero, (antes, ahora) in enumerate(zip(FUENTE.splitlines(), actual), 1):
            if antes != ahora:
                return numero
        return None

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        self.registro.anotar("base", self.raiz)
        return ResultadoSuite(codigo=0)

    def medir_mapa(self, rutas: list[str], timeout_s: int) -> MapaTests:
        self.registro.anotar("mapa", self.raiz)
        sin = frozenset({""})
        return MapaTests(
            sha=_git(Path(self.raiz), "rev-parse", "HEAD"), orden=ORDEN,
            contextos={"pkg/mod.py": {2: frozenset({"t::a"}), 3: frozenset({"t::a"}),
                                      7: sin, 1: sin, 6: sin, 10: sin}},
            segundos=2.0,
        )

    def subconjunto_verde(self, ids: tuple[str, ...], timeout_s: int) -> bool:
        return True

    def juzgar_subconjunto(self, ids: tuple[str, ...], timeout_s: int) -> tuple[str, str]:
        return (SUPERVIVIENTE, "0")

    def juzgar(self, timeout_s: int) -> tuple[str, str]:
        linea = self._mutada()
        with self.registro.cerrojo:
            if linea in self.registro.timeouts_pendientes:
                self.registro.timeouts_pendientes.discard(linea)
                return (TIMEOUT, "timeout")
        return (MUERTO, "1")


@pytest.fixture
def capturadas(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    llamadas: list[dict] = []
    real = mutacion_paralela.ejecutar_campania

    def _espia(*args: object, **kwargs: object) -> InformeMutacion:
        llamadas.append(dict(kwargs))
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(mutacion_paralela, "ejecutar_campania", _espia)
    return llamadas


def _paralela(repo: Path, registro: Registro, **extra: object) -> InformeMutacion:
    return ejecutar_campania_paralela(
        _alcance(), [], timeout_s=5, raiz=str(repo), workers=2,
        fabrica=lambda fichero, raiz_worker: Doble(raiz_worker, registro), **extra,
    )


def test_f019_r5_un_mapa_medido_en_wk_0_antes_de_los_hilos_para_todos(
    repo: Path, capturadas: list[dict]
) -> None:
    registro = Registro()

    informe = _paralela(repo, registro, seleccion=True)

    mapas = [e for e in registro.eventos if e[0] == "mapa"]
    assert mapas == [("mapa", "wk_0")], "un solo mapa, en el primer worktree"
    assert registro.eventos[0] == ("mapa", "wk_0"), "antes de cualquier línea base"
    vistos = [id(k["mapas"]) for k in capturadas]
    assert len(capturadas) == 3, "dos workers y el repaso"
    assert len(set(vistos)) == 1, "todos con el MISMO mapa, el repaso incluido (R29)"
    assert capturadas[-1]["workers"] == 1, "la última es el repaso en serie"
    assert informe.seleccion == "activa"
    assert {m.linea for m in informe.podados} == {11}
    assert informe.revalidados == 4
    assert informe.timeouts_repasados == 1 and not informe.timeouts
    assert _leer(repo / "pkg" / "mod.py") == FUENTE


def test_f019_r6_un_worker_con_otro_head_juzga_con_la_suite_y_degrada(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = mutacion.sha_de_head

    def _sha(raiz: str = ".") -> str | None:
        return "otro" if Path(raiz).name == "wk_1" else real(raiz)

    monkeypatch.setattr(mutacion, "sha_de_head", _sha)
    registro = Registro()

    informe = _paralela(repo, registro, seleccion=True)

    assert informe.seleccion == "degradada"
    assert any("HEAD" in motivo for motivo in informe.motivos_degradado.values())


def test_f019_r19_paralela_sin_seleccion_no_mide_nada(repo: Path) -> None:
    registro = Registro()

    informe = _paralela(repo, registro, seleccion=False)

    assert not [e for e in registro.eventos if e[0] == "mapa"]
    assert informe.seleccion == "desactivada"
    assert not informe.podados


# --- fusionar y reemplazar_timeouts ------------------------------------------


def _m(linea: int) -> Mutante:
    return Mutante(fichero="pkg/mod.py", linea=linea, col=0, operador="aritmetico",
                   original="a", mutado="b")


def _parcial(**campos: object) -> InformeMutacion:
    informe = InformeMutacion(feature="F-019", alcance=_alcance())
    for clave, valor in campos.items():
        setattr(informe, clave, valor)
    return informe


def test_f019_r29_fusionar_conserva_podados_y_suma_contadores() -> None:
    uno = _parcial(supervivientes=[_m(11)], podados=[_m(11)], seleccion="activa",
                   sha_mapa="s", segundos_mapa={".": 2.0}, tests_en_suite={".": 3},
                   tamanos_subconjunto=[1, 2], revalidados=2, muertos_al_revalidar=1,
                   subconjuntos_descartados=1, segundos_suite_entera=3.0,
                   juzgados_suite_entera=1)
    dos = _parcial(supervivientes=[_m(12)], podados=[_m(12)], seleccion="degradada",
                   motivos_degradado={".": "otro HEAD"}, tamanos_subconjunto=[4],
                   revalidados=1, segundos_suite_entera=5.0, juzgados_suite_entera=2)

    informe = fusionar(_alcance(), [uno, dos], generados=2, segundos=1.0)

    assert [m.linea for m in informe.podados] == [11, 12]
    assert informe.seleccion == "degradada"
    assert informe.motivos_degradado == {".": "otro HEAD"}
    assert informe.sha_mapa == "s"
    assert informe.segundos_mapa == {".": 2.0} and informe.tests_en_suite == {".": 3}
    assert sorted(informe.tamanos_subconjunto) == [1, 2, 4]
    assert (informe.revalidados, informe.muertos_al_revalidar) == (3, 1)
    assert informe.subconjuntos_descartados == 1
    assert (informe.segundos_suite_entera, informe.juzgados_suite_entera) == (8.0, 3)


def test_f019_r29_fusionar_sin_seleccion_la_deja_sin_declarar() -> None:
    informe = fusionar(_alcance(), [_parcial(), _parcial()], generados=0, segundos=0.0)

    assert informe.seleccion is None


def test_f019_r29_reemplazar_timeouts_conserva_y_suma_lo_de_la_seleccion() -> None:
    campania = _parcial(supervivientes=[_m(11)], podados=[_m(11)], timeouts=[_m(7)],
                        seleccion="activa", revalidados=2, tamanos_subconjunto=[1],
                        segundos_suite_entera=4.0, juzgados_suite_entera=1,
                        mutantes_evaluados=[_m(7), _m(11)])
    repaso = _parcial(muertos=1, revalidados=1, muertos_al_revalidar=1,
                      tamanos_subconjunto=[2], subconjuntos_descartados=1,
                      segundos_suite_entera=6.0, juzgados_suite_entera=1)

    informe = reemplazar_timeouts(campania, repaso)

    assert [m.linea for m in informe.podados] == [11]
    assert informe.seleccion == "activa"
    assert (informe.revalidados, informe.muertos_al_revalidar) == (3, 1)
    assert informe.tamanos_subconjunto == [1, 2]
    assert informe.subconjuntos_descartados == 1
    assert (informe.segundos_suite_entera, informe.juzgados_suite_entera) == (10.0, 2)


def test_f019_r29_fusionar_toma_el_modo_del_unico_parcial_que_lo_declara() -> None:
    # Superviviente de la campaña de T15 (`modos[0]` → `modos[1]`): con un solo
    # parcial que declara modo —el otro worker no juzgó nada— el modo es el suyo.
    informe = fusionar(_alcance(), [_parcial(seleccion="activa"), _parcial()],
                       generados=0, segundos=0.0)

    assert informe.seleccion == "activa"


def test_f019_r29_un_repaso_degradado_degrada_la_campania() -> None:
    campania = _parcial(timeouts=[_m(7)], seleccion="activa", mutantes_evaluados=[_m(7)])
    repaso = _parcial(muertos=1, seleccion="degradada",
                      motivos_degradado={".": "otro HEAD"})

    informe = reemplazar_timeouts(campania, repaso)

    assert informe.seleccion == "degradada"
    assert informe.motivos_degradado == {".": "otro HEAD"}


def test_f019_r1_un_ejecutor_sin_raiz_es_el_arbol_entero() -> None:
    from types import SimpleNamespace

    from harness.mutacion import clave_de_mapa, ruta_para_ejecutor

    sin_raiz = SimpleNamespace(ejecutable="py", ruta=None)

    assert clave_de_mapa(sin_raiz, ".") == (".", "py", "")
    assert ruta_para_ejecutor("pkg/mod.py", sin_raiz, ".") == "pkg/mod.py"


# --- T18 · R20: la base de CIERRE se ancla a la de apertura medida (§8 de la spec) ---


class DobleReloj(Doble):
    """Doble que apunta el reloj concedido a cada línea base."""

    def __init__(self, raiz: str, registro: Registro, relojes: list[int]) -> None:
        super().__init__(raiz, registro)
        self.relojes = relojes

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        self.relojes.append(timeout_s)
        return ResultadoSuite(codigo=0)


def test_f019_r20_cierre_max_de_suelo_y_apertura_por_margen() -> None:
    from harness.mutacion import MARGEN_TIMEOUT, timeout_de_base_de_cierre

    assert MARGEN_TIMEOUT == 2.0
    assert timeout_de_base_de_cierre(1200, {"wk_0": 806.6, "wk_1": 857.9}) == 1716
    assert timeout_de_base_de_cierre(1200, {"wk_0": 100.0}) == 1200
    assert timeout_de_base_de_cierre(1200, {}) == 1200


@pytest.mark.parametrize("workers", [1, 2])
def test_f019_r20_la_base_de_cierre_recibe_el_reloj_anclado(
    repo: Path, monkeypatch: pytest.MonkeyPatch, workers: int
) -> None:
    # La apertura «tardó» 858 s con la carga real; la de cierre corre con la
    # misma carga y no puede tener solo los 1200 s del suelo (T15: expiró).
    monkeypatch.setattr(mutacion, "comprobar_linea_base",
                        lambda implicados, *_a, **_k: {etiqueta: 858.0 for etiqueta, _ in implicados})
    relojes: list[int] = []
    registro = Registro()
    registro.timeouts_pendientes = set()
    fabrica = lambda fichero, raiz_worker: DobleReloj(raiz_worker, registro, relojes)

    if workers == 1:
        mutacion.ejecutar_campania(
            _alcance(), DobleReloj(str(repo), registro, relojes), timeout_s=5,
            raiz=str(repo), timeout_base_s=1200, seleccion=False,
        )
    else:
        ejecutar_campania_paralela(
            _alcance(), [], timeout_s=5, raiz=str(repo), workers=2, fabrica=fabrica,
            timeout_base_s=1200, seleccion=False,
        )

    assert relojes, "ninguna línea base de cierre"
    assert set(relojes) == {1716}, "apertura 858 s × MARGEN_TIMEOUT 2,0 = 1716 > 1200"
