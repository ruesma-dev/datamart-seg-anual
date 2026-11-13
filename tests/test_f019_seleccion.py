# tests/test_f019_seleccion.py
"""F-019 · Selección de tests por mutante: cómo se juzga con el mapa.

Ejecutores dobles que apuntan QUÉ se corrió (suite entera, subconjunto sin
mutar, subconjunto con el mutante) y con qué fuente en disco, para comprobar
el bucle de juicio de `ejecutar_campania` sin lanzar ninguna suite real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.alcance import Alcance
from harness.mapa_tests import Degradado, MapaTests
from harness.mutacion import (
    FACTOR_HOLGURA_BASE,
    INDETERMINADO,
    MUERTO,
    SIN_EJECUTAR,
    SUPERVIVIENTE,
    TIMEOUT,
    EjecutorPytest,
    InformeMutacion,
    ResultadoSuite,
    _leer,
    clave_de_mapa,
    clave_de_orden,
    ejecutar_campania,
)

# --- T7 · R9: el ejecutor sabe correr un subconjunto -------------------------


class _Proceso:
    def __init__(self, codigo: int) -> None:
        self.returncode = codigo
        self.stdout = b""
        self.stderr = b""


class _Ordenes(list):
    """Órdenes lanzadas, y los códigos que devolverán las siguientes."""

    codigos: list[int]


@pytest.fixture
def ordenes(monkeypatch: pytest.MonkeyPatch) -> _Ordenes:
    vistas = _Ordenes()
    vistas.codigos = []

    def _run(orden: list[str], **_k: object) -> _Proceso:
        vistas.append(list(orden))
        return _Proceso(vistas.codigos.pop(0) if vistas.codigos else 0)

    monkeypatch.setattr("harness.mutacion.subprocess.run", _run)
    return vistas


IDS = ("tests/test_a.py::test_1", "tests/test_b.py::test_2[x]")


def test_f019_r9_el_subconjunto_va_sin_la_ruta_acotada_y_con_los_argumentos(
    ordenes: list[list[str]], tmp_path: Path
) -> None:
    ejecutor = EjecutorPytest(raiz=str(tmp_path), ejecutable="py", ruta="tests")

    ejecutor.juzgar_subconjunto(IDS, 10)

    assert ordenes[0] == ["py", "-m", "pytest", "-x", "-q", "--tb=no", "-p",
                          "no:cacheprovider", *IDS]


def test_f019_r9_sin_ids_la_suite_sigue_con_su_ruta(
    ordenes: list[list[str]], tmp_path: Path
) -> None:
    EjecutorPytest(raiz=str(tmp_path), ejecutable="py", ruta="tests").juzgar(10)

    assert ordenes[0][-1] == "tests"


@pytest.mark.parametrize(
    ("codigo", "veredicto"),
    [(0, SUPERVIVIENTE), (1, MUERTO), (2, INDETERMINADO), (5, INDETERMINADO)],
)
def test_f019_r9_juzgar_subconjunto_lee_el_codigo_como_juzgar(
    ordenes: list[list[str]], tmp_path: Path, codigo: int, veredicto: str
) -> None:
    ordenes.codigos.append(codigo)  # type: ignore[attr-defined]

    resultado = EjecutorPytest(raiz=str(tmp_path)).juzgar_subconjunto(IDS, 10)

    assert resultado == (veredicto, str(codigo))


def test_f019_r9_juzgar_subconjunto_con_reloj_agotado_es_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import subprocess

    def _run(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired("pytest", 1)

    monkeypatch.setattr("harness.mutacion.subprocess.run", _run)

    assert EjecutorPytest(raiz=str(tmp_path)).juzgar_subconjunto(IDS, 1)[0] == TIMEOUT


@pytest.mark.parametrize(("codigo", "verde"), [(0, True), (1, False), (4, False), (5, False)])
def test_f019_r13_subconjunto_verde_solo_con_codigo_cero(
    ordenes: list[list[str]], tmp_path: Path, codigo: int, verde: bool
) -> None:
    ordenes.codigos.append(codigo)  # type: ignore[attr-defined]

    assert EjecutorPytest(raiz=str(tmp_path), ruta="tests").subconjunto_verde(IDS, 10) is verde
    assert ordenes[0][-2:] == list(IDS)


# --- T8 · el bucle de juicio con el mapa -------------------------------------

FUENTE = """\
def a(x):
    y = x + 1
    return y * 3


def b(x):
    return x * 2


def c(x):
    return x - 3
"""

#: Líneas con mutante (dos por línea, `aritmetico` y `entero`): 2 y 3 las
#: ejecuta `t::a`; 7 solo sin test atribuible; 11 nadie.
LINEAS = {2, 3, 7, 11}
ORDEN = ("t::a", "t::b", "t::c")


def _mapa(sha: str = "", orden: tuple[str, ...] = ORDEN) -> MapaTests:
    sin_test = frozenset({""})
    return MapaTests(
        sha=sha,
        orden=orden,
        contextos={"pkg/mod.py": {
            1: sin_test, 6: sin_test, 10: sin_test,
            2: frozenset({"t::a"}), 3: frozenset({"t::a"}), 7: sin_test,
        }},
        segundos=4.5,
    )


class Doble:
    """Ejecutor que apunta qué corrió, con qué reloj y si había un mutante."""

    def __init__(self, raiz: Path, suite=None, sub=None, verde: bool = True) -> None:
        self.raiz = str(raiz)
        self.ejecutable = "py"
        self.ruta = "tests"
        self.registro: list[tuple[str, tuple[str, ...], int | None, int]] = []
        self._suite = suite or (lambda linea: (MUERTO, "1"))
        self._sub = sub or (lambda linea: (MUERTO, "1"))
        self._verde = verde
        self.mapas_pedidos: list[list[str]] = []

    def _mutada(self) -> int | None:
        """Línea mutada en disco ahora mismo, o `None` si el fichero está limpio."""
        actual = _leer(Path(self.raiz) / "pkg" / "mod.py").splitlines()
        for numero, (antes, ahora) in enumerate(zip(FUENTE.splitlines(), actual), start=1):
            if antes != ahora:
                return numero
        return None

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        self.registro.append(("base", (), self._mutada(), timeout_s))
        return ResultadoSuite(codigo=0)

    def juzgar(self, timeout_s: int) -> tuple[str, str]:
        linea = self._mutada()
        self.registro.append(("suite", (), linea, timeout_s))
        return self._suite(linea)

    def juzgar_subconjunto(self, ids: tuple[str, ...], timeout_s: int) -> tuple[str, str]:
        linea = self._mutada()
        self.registro.append(("sub", ids, linea, timeout_s))
        return self._sub(linea)

    def subconjunto_verde(self, ids: tuple[str, ...], timeout_s: int) -> bool:
        self.registro.append(("verde", ids, self._mutada(), timeout_s))
        return self._verde

    def medir_mapa(self, rutas: list[str], timeout_s: int) -> MapaTests:
        self.mapas_pedidos.append(list(rutas))
        self.registro.append(("mapa", (), self._mutada(), timeout_s))
        return _mapa()


@pytest.fixture
def arbol(tmp_path: Path) -> tuple[Alcance, Path]:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text(FUENTE, encoding="utf-8", newline="")
    alcance = Alcance(
        feature="F-019", origen="rama", ref_diff=("dev", "x"),
        lineas={"pkg/mod.py": set(LINEAS)},
    )
    return alcance, tmp_path


def _clave(doble: object, raiz: Path) -> tuple[str, str, str]:
    return clave_de_mapa(doble, str(raiz))


def _campania(alcance: Alcance, raiz: Path, doble: Doble, **extra: object) -> InformeMutacion:
    extra.setdefault("mapas", {_clave(doble, raiz): _mapa()})
    return ejecutar_campania(
        alcance, doble, timeout_s=7, raiz=str(raiz), comprobar_arbol=False, **extra
    )


def _de_linea(lista: list, linea: int) -> list:
    return [m for m in lista if m.linea == linea]


def test_f019_r8_sin_ejecucion_se_poda_sin_escribir_ni_correr(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    informe = _campania(alcance, raiz, doble)

    podado = _de_linea(informe.podados, 11)
    assert podado, "el mutante de la línea 11 no se podó"
    assert podado[0] in informe.supervivientes, "el PODADO es superviviente"
    assert informe.codigos[clave_de_orden(podado[0])] == SIN_EJECUTAR
    assert not [r for r in doble.registro if r[2] == 11], "se escribió o se corrió el podado"
    assert _leer(raiz / "pkg" / "mod.py") == FUENTE


def test_f019_r9_r13_r14_subconjunto_validado_sin_mutar_y_muerto_sin_revalidar(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: (MUERTO, "1"))

    informe = _campania(alcance, raiz, doble)

    verdes = [r for r in doble.registro if r[0] == "verde"]
    assert verdes == [("verde", ("t::a",), None, informe.timeout_efectivo)], (
        "el subconjunto se valida UNA vez y SIN mutar nada"
    )
    subs = [r[2] for r in doble.registro if r[0] == "sub"]
    assert subs == [2, 2, 3, 3], "cada mutante de la sentencia con tests, con su subconjunto"
    suites = [r[2] for r in doble.registro if r[0] == "suite"]
    assert 2 not in suites and 3 not in suites, "el MUERTO del subconjunto no se revalida"
    assert informe.revalidados == 0
    assert informe.tamanos_subconjunto == [1, 1, 1, 1]
    assert informe.muertos == 6


@pytest.mark.parametrize(
    "resultado",
    [(SUPERVIVIENTE, "0"), (TIMEOUT, "timeout"), (INDETERMINADO, "2"), (INDETERMINADO, "5")],
)
def test_f019_r15_lo_que_no_es_muerto_se_revalida_con_el_mutante_aplicado(
    arbol, resultado: tuple[str, str]
) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: resultado, suite=lambda linea: (MUERTO, "1"))

    informe = _campania(alcance, raiz, doble)

    suites = [r[2] for r in doble.registro if r[0] == "suite"]
    assert 2 in suites and 3 in suites, "la revalidación corre con el mutante aún aplicado"
    assert informe.revalidados == 4
    assert informe.muertos_al_revalidar == 4
    assert not _de_linea(informe.supervivientes, 2), "manda el veredicto de la suite entera"
    assert not _de_linea(informe.timeouts, 2)


def test_f019_r15_el_superviviente_del_subconjunto_y_de_la_suite_sobrevive(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: (SUPERVIVIENTE, "0"),
                  suite=lambda linea: (SUPERVIVIENTE, "0"))

    informe = _campania(alcance, raiz, doble)

    medidos = [m for m in informe.supervivientes if m not in informe.podados]
    assert {m.linea for m in medidos} == {2, 3, 7}
    assert informe.revalidados == 4
    assert informe.muertos_al_revalidar == 0


def test_f019_r15_el_indeterminado_de_la_suite_se_resuelve_como_hoy(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: (SUPERVIVIENTE, "0"),
                  suite=lambda linea: (INDETERMINADO, "2"))

    informe = _campania(alcance, raiz, doble)

    assert {m.linea for m in informe.indeterminados} == {2, 3, 7}
    bases = [r for r in doble.registro if r[0] == "base"]
    assert len(bases) > 1 and all(r[2] is None for r in bases), (
        "la resolución corre la base SIN mutar"
    )


def test_f019_r10_solo_sin_test_atribuible_va_directo_a_la_suite(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    _campania(alcance, raiz, doble)

    assert [r[0] for r in doble.registro if r[2] == 7] == ["suite", "suite"]


def test_f019_r13_subconjunto_rojo_sin_mutar_se_descarta_para_toda_la_campania(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, verde=False)

    informe = _campania(alcance, raiz, doble)

    assert [r for r in doble.registro if r[0] == "verde"] == [
        ("verde", ("t::a",), None, informe.timeout_efectivo)
    ], "descartado una vez, no se vuelve a probar"
    assert not [r for r in doble.registro if r[0] == "sub"]
    assert {r[2] for r in doble.registro if r[0] == "suite"} == {2, 3, 7}
    assert informe.subconjuntos_descartados == 1


def test_f019_r11_subconjunto_que_es_toda_la_suite_va_a_la_suite(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    _campania(alcance, raiz, doble, mapas={_clave(doble, raiz): _mapa(orden=("t::a",))})

    assert not [r for r in doble.registro if r[0] in ("sub", "verde")]


def test_f019_r16_r17_base_entera_sin_instrumentar_y_mismo_reloj(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: (SUPERVIVIENTE, "0"))

    informe = _campania(alcance, raiz, doble)

    assert doble.registro[0][:3] == ("base", (), None), "la base va primero, entera"
    relojes = {r[3] for r in doble.registro if r[0] in ("sub", "suite", "verde")}
    assert relojes == {informe.timeout_efectivo}, "subconjunto y revalidación, mismo reloj"


def test_f019_r6_sha_distinto_juzga_todo_con_la_suite_y_lo_avisa(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)
    dicho: list[str] = []

    informe = _campania(alcance, raiz, doble, eco=dicho.append,
                        mapas={_clave(doble, raiz): _mapa(sha="otro")})

    assert not [r for r in doble.registro if r[0] in ("sub", "verde")]
    assert not informe.podados, "sin mapa válido nunca se poda"
    assert informe.seleccion == "degradada"
    assert any("HEAD" in motivo for motivo in informe.motivos_degradado.values())
    assert any("HEAD" in linea for linea in dicho)


def test_f019_r18_ejecutor_degradado_juzga_todo_con_la_suite(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    informe = _campania(alcance, raiz, doble,
                        mapas={_clave(doble, raiz): Degradado("sin coverage")})

    assert {r[2] for r in doble.registro if r[0] == "suite"} == {2, 3, 7, 11}
    assert not informe.podados
    assert informe.seleccion == "degradada"
    assert list(informe.motivos_degradado.values()) == ["sin coverage"]


def test_f019_r1_con_seleccion_el_mapa_se_mide_antes_de_la_base(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    informe = _campania(alcance, raiz, doble, mapas=None, seleccion=True)

    assert doble.registro[0][0] == "mapa" and doble.registro[1][0] == "base"
    assert doble.mapas_pedidos == [["pkg/mod.py"]]
    assert doble.registro[0][3] == 7 * FACTOR_HOLGURA_BASE, "el mapa, con el reloj de la base"
    assert informe.seleccion == "activa"
    assert informe.segundos_mapa == {".": 4.5}
    assert informe.tests_en_suite == {".": 3}
    assert _de_linea(informe.podados, 11)


def test_f019_r19_sin_seleccion_no_hay_mapa_ni_poda_ni_subconjuntos(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    informe = _campania(alcance, raiz, doble, mapas=None, seleccion=False)

    assert not doble.mapas_pedidos
    assert not [r for r in doble.registro if r[0] in ("sub", "verde")]
    assert not informe.podados
    assert informe.seleccion == "desactivada"


def test_f019_sin_mapas_ni_seleccion_la_campania_es_la_de_la_1_9_0(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz)

    informe = _campania(alcance, raiz, doble, mapas=None)

    assert informe.seleccion is None
    assert {r[2] for r in doble.registro if r[0] == "suite"} == {2, 3, 7, 11}


def test_f019_un_ejecutor_sin_subconjuntos_juzga_con_la_suite(arbol) -> None:
    alcance, raiz = arbol

    class SoloSuite:
        def __init__(self) -> None:
            self.raiz = str(raiz)

        def linea_base(self, timeout_s: int) -> ResultadoSuite:
            return ResultadoSuite(codigo=0)

        def ejecutar(self, timeout_s: int) -> str:
            return MUERTO

    doble = SoloSuite()
    informe = ejecutar_campania(
        alcance, doble, timeout_s=7, raiz=str(raiz), comprobar_arbol=False,
        mapas={_clave(doble, raiz): _mapa()},
    )

    assert informe.muertos == 6, "sin juzgar_subconjunto, todo a la suite salvo el podado"
    assert len(informe.podados) == 2


def test_f019_r26_media_de_la_suite_entera_solo_con_lo_que_la_pago(arbol) -> None:
    alcance, raiz = arbol
    doble = Doble(raiz, sub=lambda linea: (MUERTO, "1"))

    informe = _campania(alcance, raiz, doble)

    assert informe.juzgados_suite_entera == 2, "solo los de la línea 7 pagaron la suite"
    assert informe.segundos_suite_entera >= 0


# --- T9 · R19: `--sin-seleccion` en la orden ----------------------------------

from harness import mutacion
from harness.mutacion import _analizar_argumentos, comando_de


def test_f019_r19_la_opcion_existe_y_no_se_marca_sola() -> None:
    assert _analizar_argumentos(["--feature", "F-019"]).sin_seleccion is False
    assert _analizar_argumentos(["--feature", "F-019", "--sin-seleccion"]).sin_seleccion


def test_f019_r19_el_comando_de_la_cabecera_incluye_la_opcion() -> None:
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"), lineas={})
    informe = InformeMutacion(feature="F-019", alcance=alcance, workers=2)

    # Opción «b» (pasada 2): apagada es el defecto; `--sin-seleccion` solo
    # aparece si la clave de rigor la encendía (R19).
    informe.seleccion = "desactivada"
    informe.seleccion_por_rigor = True
    assert comando_de(informe).endswith(" --workers 2 --sin-seleccion")
    informe.seleccion_por_rigor = False
    assert "seleccion" not in comando_de(informe)
    informe.seleccion = "activa"
    assert comando_de(informe).endswith(" --workers 2 --con-seleccion")
    informe.seleccion = None
    assert "--sin-seleccion" not in comando_de(informe)


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """El CLI con las dos campañas sustituidas por dobles que apuntan sus kwargs."""
    llamadas: list[tuple[str, dict]] = []
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"),
                      lineas={"harness/mutacion.py": {1}})

    def _doble(modo: str):
        def _campania(alc: Alcance, *_a: object, **kwargs: object) -> InformeMutacion:
            llamadas.append((modo, dict(kwargs)))
            return InformeMutacion(feature=alc.feature, alcance=alc, generados=1)
        return _campania

    monkeypatch.setattr("harness.mutacion.alcance_de_feature", lambda *_a, **_k: alcance)
    monkeypatch.setattr("harness.mutacion.ejecutar_campania", _doble("serie"))
    monkeypatch.setattr("harness.mutacion_paralela.ejecutar_campania_paralela",
                        _doble("paralela"))
    return llamadas


@pytest.mark.parametrize("workers", ["1", "2"])
def test_f019_r19_el_cli_la_apaga_por_defecto_y_la_enciende_con_la_opcion(
    cli: list[tuple[str, dict]], tmp_path: Path, workers: str
) -> None:
    mutacion.main(["--feature", "F-019", "--workers", workers,
                   "--salida", str(tmp_path / "a.md")])
    mutacion.main(["--feature", "F-019", "--workers", workers, "--con-seleccion",
                   "--salida", str(tmp_path / "b.md")])

    modo = "serie" if workers == "1" else "paralela"
    assert [(m, k["seleccion"]) for m, k in cli] == [(modo, False), (modo, True)]
