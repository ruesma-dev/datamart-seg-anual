# tests/test_f058_incremental.py
"""F-058 · R14–R19: repetir una campaña sin volver a juzgar lo ya muerto.

Repositorio git temporal y ejecutor falso que deduce qué mutante tiene delante
leyendo el fichero mutado: ni suite real ni red. La configuración de rigor se
escribe en el repositorio temporal, nunca se lee la del proyecto.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    MUERTO,
    PYTEST_OK,
    SUPERVIVIENTE,
    TIMEOUT,
    InformeMutacion,
    Mutante,
    ResultadoSuite,
    clasificar_delta,
    escribir_estado,
    generar_mutantes,
    leer_estado,
    plan_incremental,
    seleccionar,
)
from harness.rigor import ReglaMuestreo, cargar_rigor, control_incremental

FICHERO = "app/juguete.py"
LINEAS = 30
REGLA = ReglaMuestreo(por_linea=True, fraccion=0.6, suelo=5, techo=300, origen="nivel")
SEMILLA = 20261030


def _fuente(lineas: int = LINEAS) -> str:
    cuerpo = [f"# {FICHERO}"]
    for i in range(1, lineas + 1):
        cuerpo.append(f"v{i} = ({i} + 2 - 3) * 4 if {i} == 2 or {i} < 5 else 0")
    return "\n".join(cuerpo) + "\n"


def _generados() -> list[Mutante]:
    return generar_mutantes(_fuente(), set(range(2, LINEAS + 2)), FICHERO)


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(raiz: Path, mensaje: str = "cambio") -> str:
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", mensaje)
    return _git(raiz, "rev-parse", "HEAD")


def _escribir(raiz: Path, ruta: str, texto: str | bytes) -> None:
    destino = raiz / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(texto, bytes):
        destino.write_bytes(texto)
    else:
        destino.write_text(texto, encoding="utf-8", newline="")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    _escribir(raiz, FICHERO, _fuente())
    _escribir(raiz, "tests/test_juguete.py", "def test_a():\n    assert True\n")
    _commit(raiz, "base")
    return raiz


# --- R14: el estado de una campaña fiable --------------------------------------


def _informe(**campos) -> InformeMutacion:
    alcance = Alcance(feature="F-990", origen="ficheros", ref_diff=("", ""),
                      lineas={FICHERO: set(range(2, LINEAS + 2))})
    return InformeMutacion(feature="F-990", alcance=alcance, **campos)


def test_f058_r14_el_estado_guarda_sha_regla_y_cada_veredicto(tmp_path: Path) -> None:
    m = _generados()[:4]
    informe = _informe(generados=90, candidatos=30, regla=REGLA, semilla=SEMILLA,
                       nivel="critico", sha_head="abc123", mutantes_evaluados=m,
                       supervivientes=[m[1]], timeouts=[m[2]], muertos=1,
                       reutilizados=[_generados()[10]])
    ruta = tmp_path / "progress" / "mutacion_F-990.json"

    assert escribir_estado(informe, ruta) is True

    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert {k: estado[k] for k in ("version", "fiable", "feature", "sha", "nivel",
                                   "semilla", "generados", "candidatos")} == {
        "version": 1, "fiable": True, "feature": "F-990", "sha": "abc123",
        "nivel": "critico", "semilla": SEMILLA, "generados": 90, "candidatos": 30}
    assert estado["regla"] == {"por_linea": True, "fraccion": 0.6, "suelo": 5,
                               "techo": 300, "origen": "nivel"}
    veredictos = [(e["linea"], e["col"], e["operador"], e["veredicto"])
                  for e in estado["evaluados"]]
    assert veredictos == [
        (m[0].linea, m[0].col, m[0].operador, MUERTO),
        (m[1].linea, m[1].col, m[1].operador, SUPERVIVIENTE),
        (m[2].linea, m[2].col, m[2].operador, TIMEOUT),
        (m[3].linea, m[3].col, m[3].operador, MUERTO),
        (_generados()[10].linea, _generados()[10].col, _generados()[10].operador, MUERTO),
    ]
    assert set(estado["evaluados"][0]) == {"fichero", "linea", "col", "operador",
                                           "original", "mutado", "veredicto"}
    assert leer_estado(ruta) == estado


def test_f058_r14_una_campania_no_fiable_no_deja_estado(tmp_path: Path) -> None:
    ruta = tmp_path / "mutacion_F-990.json"

    assert escribir_estado(_informe(aviso_base="base rota"), ruta) is False
    assert not ruta.exists()


def test_f058_r14_un_estado_ilegible_es_como_no_tenerlo(tmp_path: Path) -> None:
    ruta = tmp_path / "mutacion_F-990.json"
    assert leer_estado(ruta) is None
    ruta.write_text("{roto", encoding="utf-8")
    assert leer_estado(ruta) is None
    ruta.write_text("[1, 2]", encoding="utf-8")
    assert leer_estado(ruta) is None


# --- R16, R17: qué ha cambiado desde el estado --------------------------------


def test_f058_r16_solo_papeleo_es_vigente(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    assert clasificar_delta(str(repo), sha) == "vigente"  # delta vacío
    for ruta in ("progress/notas.md", "specs/F-1/design.md", "BACKLOG.md",
                 "harness/features.json", "docs/algo.md"):
        _escribir(repo, ruta, "x\n")
    _commit(repo)

    assert clasificar_delta(str(repo), sha) == "vigente"


@pytest.mark.parametrize("ruta", ["tests/test_juguete.py", "tests/nuevo/test_b.py",
                                  "paquete/tests/ayuda.py", "otro/test_c.py",
                                  "conftest.py", "paquete/conftest.py"])
def test_f058_r15_tests_que_solo_crecen_son_solo_tests(repo: Path, ruta: str) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    previo = (repo / ruta).read_text(encoding="utf-8") if (repo / ruta).exists() else ""
    _escribir(repo, ruta, previo + "def test_nuevo():\n    assert 1\n")
    _escribir(repo, "progress/impl.md", "nota\n")
    _commit(repo)

    assert clasificar_delta(str(repo), sha) == "solo_tests"


def test_f058_r17_borrar_una_linea_de_test_es_codigo(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    _escribir(repo, "tests/test_juguete.py", "def test_a():\n    pass\n")
    _commit(repo)

    assert clasificar_delta(str(repo), sha) == "codigo"


def test_f058_r17_tocar_produccion_es_codigo(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    _escribir(repo, FICHERO, _fuente() + "extra = 1\n")
    _commit(repo)

    assert clasificar_delta(str(repo), sha) == "codigo"


def test_f058_r17_un_binario_es_codigo_aunque_viva_en_tests(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    _escribir(repo, "tests/datos.bin", bytes(range(256)))
    _commit(repo)

    assert clasificar_delta(str(repo), sha) == "codigo"


def test_f058_r17_un_sha_que_no_es_antepasado_es_codigo(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "otra")
    _escribir(repo, "progress/x.md", "x\n")
    ajeno = _commit(repo)
    _git(repo, "checkout", "-q", "dev")

    assert clasificar_delta(str(repo), ajeno) == "codigo"
    assert clasificar_delta(str(repo), "0" * 40) == "codigo"


# --- R15, R17, R18: el plan -----------------------------------------------------


def _estado(supervivientes: int = 2, timeouts: int = 1, **cambios) -> dict:
    elegidos, candidatos, _ = seleccionar(_generados(), REGLA, SEMILLA)
    evaluados = []
    for indice, m in enumerate(elegidos):
        veredicto = (SUPERVIVIENTE if indice < supervivientes else
                     TIMEOUT if indice < supervivientes + timeouts else MUERTO)
        evaluados.append({"fichero": m.fichero, "linea": m.linea, "col": m.col,
                          "operador": m.operador, "original": m.original,
                          "mutado": m.mutado, "veredicto": veredicto})
    estado = {"version": 1, "fiable": True, "feature": "F-990", "sha": "abc",
              "nivel": "critico", "regla": REGLA.como_dict(), "semilla": SEMILLA,
              "generados": len(_generados()), "candidatos": candidatos,
              "evaluados": evaluados}
    estado.update(cambios)
    return estado


def test_f058_r15_reevalua_supervivientes_timeouts_y_un_control(tmp_path: Path) -> None:
    elegidos, _, _ = seleccionar(_generados(), REGLA, SEMILLA)
    plan = plan_incremental(_estado(), REGLA, SEMILLA, "critico", _generados())

    assert not isinstance(plan, str), plan
    assert plan.reevaluar == elegidos[:3]
    assert plan.desde == "abc"
    muertos = elegidos[3:]
    assert len(elegidos) == 18                    # 60 % de 30 candidatos
    assert len(muertos) == 15
    assert len(plan.control) == 5                 # max(5, ceil(1,5))
    assert set(plan.control) <= set(muertos)
    assert sorted(plan.control + plan.reutilizados, key=mutacion.clave_de_orden) == muertos
    assert not set(plan.control) & set(plan.reutilizados)
    assert plan.control == plan_incremental(_estado(), REGLA, SEMILLA, "critico",
                                            _generados()).control


def test_f058_r15_el_control_crece_con_los_muertos() -> None:
    plan = plan_incremental(_estado(), REGLA, SEMILLA, "critico", _generados(),
                            control=(0.5, 2))

    assert len(plan.control) == 8                 # ceil(0,5 × 15)


def test_f058_r15_con_pocos_muertos_el_control_son_todos() -> None:
    plan = plan_incremental(_estado(supervivientes=10, timeouts=5), REGLA, SEMILLA,
                            "critico", _generados())

    assert len(plan.control) == 3 and plan.reutilizados == []


@pytest.mark.parametrize(
    ("cambios", "motivo"),
    [
        ({"nivel": "estandar"}, "nivel"),
        ({"semilla": 1}, "semilla"),
        ({"regla": {**REGLA.como_dict(), "techo": 200}}, "regla"),
        ({"fiable": False}, "fiable"),
        ({"version": 2}, "versión"),
    ],
)
def test_f058_r17_lo_que_no_cuadra_obliga_a_la_completa(cambios: dict, motivo: str) -> None:
    plan = plan_incremental(_estado(**cambios), REGLA, SEMILLA, "critico", _generados())

    assert isinstance(plan, str) and motivo in plan


def test_f058_r17_si_la_muestra_en_head_no_es_la_del_estado() -> None:
    otros = generar_mutantes(_fuente(31), set(range(2, 33)), FICHERO)

    plan = plan_incremental(_estado(), REGLA, SEMILLA, "critico", otros)

    assert isinstance(plan, str) and "muestra" in plan


def test_f058_r17_sin_semilla_no_hay_muestra_reproducible() -> None:
    plan = plan_incremental(_estado(semilla=None), REGLA, None, "critico", _generados())

    assert isinstance(plan, str) and "semilla" in plan


def test_f058_r15_la_muestra_de_control_se_lee_de_rigor_json(tmp_path: Path) -> None:
    base = {"nivel_por_defecto": "e", "cobertura": {"umbral_lineas_cambiadas": 80},
            "niveles": {"e": {"fase_red": True, "cobertura": True, "mutacion": True}}}
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(base), encoding="utf-8")
    assert control_incremental(cargar_rigor(ruta)) == (0.1, 5)

    base["mutacion"] = {"timeout_por_mutante_s": 1,
                        "incremental": {"control_fraccion": 0.25, "control_minimo": 3}}
    ruta.write_text(json.dumps(base), encoding="utf-8")
    assert control_incremental(cargar_rigor(ruta)) == (0.25, 3)


@pytest.mark.parametrize("bloque", [{"control_fraccion": 0}, {"control_fraccion": 1.2},
                                    {"control_fraccion": True}, {"control_minimo": 0},
                                    {"control_minimo": 2.5}, {"control_minimo": False},
                                    "no"])
def test_f058_r15_una_muestra_de_control_rara_es_error(bloque: object,
                                                      tmp_path: Path) -> None:
    datos = {"nivel_por_defecto": "e", "cobertura": {"umbral_lineas_cambiadas": 80},
             "mutacion": {"incremental": bloque},
             "niveles": {"e": {"fase_red": True, "cobertura": True, "mutacion": True}}}
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    with pytest.raises(ValueError, match="incremental"):
        cargar_rigor(ruta)


# --- R15–R19 de punta a punta: el CLI sobre un repositorio de juguete ---------

RIGOR = {
    "nivel_por_defecto": "critico",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "mutacion": {"timeout_por_mutante_s": 5,
                 "incremental": {"control_fraccion": 0.1, "control_minimo": 4}},
    "niveles": {"critico": {"fase_red": True, "cobertura": True, "mutacion": True,
                            "un_mutante_por_linea": True, "fraccion_mutantes": 0.6,
                            "min_mutantes": 5, "max_mutantes": 300,
                            "semilla": SEMILLA}},
}


class _Juez:
    """Decide el veredicto mirando qué línea del fichero está mutada."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.original = _fuente().split("\n")
        self.vivas: set[int] = set()
        self.juzgadas: list[int] = []

    def identidad(self) -> tuple[str, str]:
        return (str(self.raiz), "juez")

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        return ResultadoSuite(codigo=PYTEST_OK)

    def ejecutar(self, timeout_s: int) -> str:
        actual = (self.raiz / FICHERO).read_text(encoding="utf-8").split("\n")
        linea = next(i for i, (a, b) in enumerate(zip(actual, self.original,
                                                      strict=True), start=1) if a != b)
        self.juzgadas.append(linea)
        return SUPERVIVIENTE if linea in self.vivas else MUERTO


@pytest.fixture
def cli(repo: Path, monkeypatch: pytest.MonkeyPatch):
    _escribir(repo, "harness/rigor.json", json.dumps(RIGOR))
    _commit(repo, "rigor")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [{"id": "F-990"}])
    alcance = Alcance(feature="F-990", origen="rama", ref_diff=("dev", "feature/x"),
                      lineas={FICHERO: set(range(2, LINEAS + 2))})
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)
    juez = _Juez(repo)

    def lanzar(*extra: str) -> int:
        juez.juzgadas.clear()
        return mutacion.main(["--feature", "F-990", "--raiz", str(repo), "--workers", "1",
                              *extra], ejecutor=juez)

    return repo, juez, lanzar


def _primera(cli) -> tuple[Path, _Juez, object, list[Mutante]]:
    repo, juez, lanzar = cli
    elegidos, _, _ = seleccionar(_generados(), REGLA, SEMILLA)
    juez.vivas = {elegidos[0].linea, elegidos[1].linea}
    assert lanzar() == 1
    _commit(repo, "informe")
    return repo, juez, lanzar, elegidos


def test_f058_r14_el_cli_deja_el_estado_junto_al_informe(cli) -> None:
    repo, _, _, elegidos = _primera(cli)

    estado = leer_estado(repo / "progress" / "mutacion_F-990.json")
    assert estado["sha"] == _git(repo, "rev-parse", "HEAD~1")
    assert len(estado["evaluados"]) == len(elegidos) == 18


def test_f058_r15_r19_tras_cerrar_supervivientes_solo_se_reevaluan_ellos(cli) -> None:
    repo, juez, lanzar, elegidos = _primera(cli)
    desde = _git(repo, "rev-parse", "HEAD~1")
    _escribir(repo, "tests/test_juguete.py",
              "def test_a():\n    assert True\n\n\ndef test_b():\n    assert 2\n")
    _commit(repo, "tests nuevos")
    juez.vivas = set()

    assert lanzar("--incremental") == 0

    assert len(juez.juzgadas) == 2 + 4            # supervivientes + control
    assert {elegidos[0].linea, elegidos[1].linea} <= set(juez.juzgadas)
    texto = (repo / "progress" / "mutacion_F-990.md").read_text(encoding="utf-8")
    assert (f"| Modo | incremental desde `{desde}` — 12 reutilizados, 2 reevaluados, "
            "4 de control |") in texto
    assert "| Muertos | 18 |" in texto
    assert "| Mutantes evaluados | 6 (+ 12 veredictos reutilizados) |" in texto
    assert "| Muestreo | sí — 18 de 30 candidatos" in texto
    # F-019 (R24): la fila lleva el desglose de la selección detrás del total.
    assert "| Supervivientes | 0 (" in texto
    estado = leer_estado(repo / "progress" / "mutacion_F-990.json")
    assert estado["sha"] == _git(repo, "rev-parse", "HEAD")
    assert len(estado["evaluados"]) == 18
    assert {e["veredicto"] for e in estado["evaluados"]} == {MUERTO}


def test_f058_r16_si_solo_cambio_el_papeleo_la_campania_esta_vigente(
    cli, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, juez, lanzar, _ = _primera(cli)
    _escribir(repo, "progress/impl_F-990.md", "análisis\n")
    _commit(repo)
    capsys.readouterr()

    assert lanzar("--incremental") == 0

    assert juez.juzgadas == []
    assert "Campaña vigente" in capsys.readouterr().out


def test_f058_r17_si_cambia_la_produccion_hace_la_completa_y_dice_por_que(
    cli, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, juez, lanzar, _ = _primera(cli)
    _escribir(repo, "app/otro.py", "y = 1\n")
    _commit(repo)
    juez.vivas = set()
    capsys.readouterr()

    assert lanzar("--incremental") == 0

    assert len(juez.juzgadas) == 18
    salida = capsys.readouterr().out
    assert "Campaña completa" in salida and "toca producción" in salida


def test_f058_r17_sin_estado_hace_la_completa(cli, capsys) -> None:
    _, juez, lanzar = cli

    assert lanzar("--incremental") == 0
    assert len(juez.juzgadas) == 18
    assert "no hay estado" in capsys.readouterr().out


def test_f058_r18_si_un_control_sobrevive_se_descarta_todo(cli, capsys) -> None:
    repo, juez, lanzar, elegidos = _primera(cli)
    _escribir(repo, "tests/test_juguete.py",
              "def test_a():\n    assert True\n\n\ndef test_b():\n    return\n")
    _commit(repo, "un test que no comprueba nada")
    # El test nuevo «neutraliza» la suite: todo muerto revive.
    juez.vivas = {m.linea for m in elegidos}
    capsys.readouterr()

    assert lanzar("--incremental") == 1

    salida = capsys.readouterr().out
    assert "sobrevive" in salida and "campaña completa" in salida.lower()
    assert len(juez.juzgadas) == 2 + 4 + 18
    texto = (repo / "progress" / "mutacion_F-990.md").read_text(encoding="utf-8")
    assert "| Modo |" not in texto
    assert "| Supervivientes | 18 (" in texto


def test_f058_r27_sin_incremental_no_se_reutiliza_nada(cli) -> None:
    repo, juez, lanzar, _ = _primera(cli)
    _escribir(repo, "progress/impl_F-990.md", "análisis\n")
    _commit(repo)

    lanzar()

    assert len(juez.juzgadas) == 18


# --- T19: supervivientes de la campaña de F-058 ---------------------------------


def test_f058_t19_el_estado_crea_las_carpetas_que_falten(tmp_path: Path) -> None:
    informe = _informe(generados=1, candidatos=1, regla=REGLA, semilla=SEMILLA,
                       sha_head="abc", mutantes_evaluados=_generados()[:1], muertos=1)
    ruta = tmp_path / "otro" / "progress" / "mutacion_F-990.json"

    assert escribir_estado(informe, ruta) is True
    assert leer_estado(ruta)["sha"] == "abc"


def test_f058_t19_misma_cuenta_pero_otra_muestra_obliga_a_la_completa() -> None:
    estado = _estado()
    cambiado = dict(estado["evaluados"][-1], col=999)
    estado["evaluados"] = [*estado["evaluados"][:-1], cambiado]

    plan = plan_incremental(estado, REGLA, SEMILLA, "critico", _generados())

    assert plan == "la muestra que sale en HEAD no es la del estado"


def test_f058_t19_el_incremental_que_cubre_todo_no_es_muestra() -> None:
    m = _generados()[:4]
    plan = mutacion.PlanIncremental(desde="abc", reevaluar=m[:1], control=m[1:2],
                                    reutilizados=m[2:], generados=4, candidatos=4,
                                    limite=10)
    informe = _informe(mutantes_evaluados=m[:2], muertos=2)

    assert mutacion.componer_incremental(informe, plan).muestreado is False


@pytest.mark.parametrize("sha", ["", None, 7])
def test_f058_t19_un_sha_vacio_o_raro_es_campania_completa(tmp_path: Path, sha) -> None:
    alcance = Alcance(feature="F-990", origen="ficheros", ref_diff=("", ""), lineas={})

    decision = mutacion.decidir_incremental(_estado(sha=sha), str(tmp_path), alcance,
                                            REGLA, SEMILLA, "critico")

    assert decision == (mutacion.DELTA_CODIGO, None, "el estado no declara el SHA medido")


def test_f058_t19_el_aviso_de_r18_nombra_el_primer_control_que_revive(
    cli, capsys
) -> None:
    repo, juez, lanzar, elegidos = _primera(cli)
    estado = leer_estado(repo / "progress" / "mutacion_F-990.json")
    plan = plan_incremental(estado, REGLA, SEMILLA, "critico", _generados(), (0.1, 4))
    _escribir(repo, "tests/test_juguete.py",
              "def test_a():\n    assert True\n\n\ndef test_b():\n    return\n")
    _commit(repo, "un test que no comprueba nada")
    juez.vivas = {m.linea for m in elegidos}
    capsys.readouterr()

    lanzar("--incremental")

    salida = capsys.readouterr().out
    assert f"4 muerto(s) de la muestra de control sobrevive(n) ahora " \
           f"({plan.control[0].descripcion()})" in salida


class _Parada(Exception):
    """Corta `main` en cuanto se ve con qué argumentos lanza la campaña."""


@pytest.mark.parametrize(("servicios", "con_factoria"), [([object()], True), ([], False)])
def test_f058_t19_en_serie_la_factoria_solo_va_con_servicios_y_sin_ejecutor(
    cli, monkeypatch: pytest.MonkeyPatch, servicios: list, con_factoria: bool
) -> None:
    repo, _, _ = cli
    vistos: dict = {}

    def espia(*_args, **kwargs):
        vistos.update(kwargs)
        raise _Parada

    monkeypatch.setattr(mutacion, "cargar_servicios", lambda **_k: servicios)
    monkeypatch.setattr(mutacion, "ejecutar_campania", espia)

    with pytest.raises(_Parada):
        mutacion.main(["--feature", "F-990", "--raiz", str(repo), "--workers", "1"])

    assert (vistos["ejecutor_de"] is not None) is con_factoria
