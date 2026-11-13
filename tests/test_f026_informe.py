# tests/test_f026_informe.py
"""F-026 · R15–R21: el cero de UN fichero ya no pasa en silencio.

El cero de la campaña entera aborta desde hace tiempo («CERO MUTANTES»). El de
un fichero no: un fichero con lógica en alcance y 0 mutantes se sumaba al
resto y el informe no lo decía. Ahora la tabla «Alcance» da los mutantes por
fichero, el que da 0 sale señalado y pide una declaración escrita, que se
conserva al reescribir el informe igual que el análisis de un superviviente.

Informes construidos a mano, repositorios git temporales y ejecutores falsos:
ni suite real ni red.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    CABECERA_PENDIENTE,
    NADA_JUZGADO,
    PYTEST_OK,
    InformeMutacion,
    Mutante,
    PlanIncremental,
    ResultadoSuite,
    analisis_escritos,
    componer_incremental,
    ejecutar_campania,
    escribir_estado,
    escribir_informe,
    generar_mutantes,
    leer_estado,
    lineas_comparables,
    mutantes_del_alcance,
    plan_incremental,
)
from harness.mutacion_paralela import ejecutar_campania_paralela, fusionar
from harness.rigor import ReglaMuestreo

LOGICA = "app/logica.py"
DECLARATIVO = "app/constantes.py"
FUENTE_LOGICA = "# app/logica.py\ndef f(a, b):\n    return a + b if a < b else a - b\n"
FUENTE_DECLARATIVO = '# app/constantes.py\nNOMBRE = "arnes"\nOTRO = "base"\n'
LINEAS_LOGICA = {2, 3}
LINEAS_DECLARATIVO = {2, 3}
REGLA = ReglaMuestreo(por_linea=True, fraccion=None, suelo=None, techo=None, origen="nivel")
SEMILLA = 7

DECLARACION = (
    "#### Declaración (completada por el implementer)\n"
    "\n"
    "> Solo constantes de texto: lo cubre `test_constantes_publicadas`."
)


def _alcance(con_logica: bool = True) -> Alcance:
    lineas = {DECLARATIVO: set(LINEAS_DECLARATIVO)}
    if con_logica:
        lineas[LOGICA] = set(LINEAS_LOGICA)
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/F-999-x"),
                   lineas=lineas)


def _generados() -> list[Mutante]:
    return generar_mutantes(FUENTE_LOGICA, LINEAS_LOGICA, LOGICA)


def _informe(por_fichero: dict[str, int] | None, supervivientes: list[Mutante] | None = None
             ) -> InformeMutacion:
    generados = len(_generados())
    return InformeMutacion(
        feature="F-999", alcance=_alcance(), generados=generados,
        muertos=generados - len(supervivientes or []),
        supervivientes=list(supervivientes or []), mutantes_evaluados=_generados(),
        por_fichero=por_fichero,
    )


def _texto(informe: InformeMutacion, ruta: Path) -> str:
    escribir_informe(informe, ruta)
    return ruta.read_text(encoding="utf-8")


def _por_fichero() -> dict[str, int]:
    return {DECLARATIVO: 0, LOGICA: len(_generados())}


# --- R15: la columna y su total ------------------------------------------------


def test_f026_r15_mutantes_por_fichero_cuenta_tambien_el_cero() -> None:
    assert mutacion.mutantes_por_fichero(_alcance(), _generados()) == _por_fichero()
    assert _por_fichero()[LOGICA] > 0


def test_f026_r15_la_tabla_alcance_trae_la_columna_y_su_total(tmp_path: Path) -> None:
    texto = _texto(_informe(_por_fichero()), tmp_path / "mutacion_F-999.md")
    n = len(_generados())

    assert "| Fichero | Líneas en alcance | Mutantes generados |" in texto
    assert f"| `{LOGICA}` | 2 | {n} |" in texto
    assert f"| **Total** | **4** | **{n}** |" in texto
    assert f"| Mutantes generados | {n} |" in texto


def test_f026_r15_sin_dato_por_fichero_dice_nd(tmp_path: Path) -> None:
    texto = _texto(_informe(None), tmp_path / "mutacion_F-999.md")

    assert f"| `{LOGICA}` | 2 | n/d |" in texto
    assert "## Ficheros sin mutantes" not in texto


# --- R17, R18: el fichero sin mutantes, señalado -------------------------------


def test_f026_r17_el_fichero_sin_mutantes_sale_señalado_y_pide_declaracion(
    tmp_path: Path,
) -> None:
    texto = _texto(_informe(_por_fichero()), tmp_path / "mutacion_F-999.md")

    assert f"| `{DECLARATIVO}` | 2 | 0 — sin mutantes |" in texto
    seccion = texto[texto.index("## Ficheros sin mutantes"):]
    assert f"### `{DECLARATIVO}` — 2 líneas en alcance, 0 mutantes" in seccion
    assert mutacion.CABECERA_DECLARACION_PENDIENTE in seccion
    assert "> Por qué no hay nada que mutar, o qué test lo cubre: PENDIENTE." in seccion
    assert "\n## " not in seccion[3:], "la sección va al final del informe"
    assert f"`{LOGICA}`" not in seccion


def test_f026_r18_sin_ficheros_a_cero_no_hay_seccion(tmp_path: Path) -> None:
    informe = _informe({LOGICA: len(_generados())})
    informe.alcance = Alcance(feature="F-999", origen="rama", ref_diff=("dev", "x"),
                              lineas={LOGICA: set(LINEAS_LOGICA)})

    texto = _texto(informe, tmp_path / "mutacion_F-999.md")

    assert "0 — sin mutantes" not in texto
    assert "## Ficheros sin mutantes" not in texto
    # Sin fichas, el bucle recorre el informe entero: un índice que retrocede
    # (`indice -= 1`) cae aquí por IndexError en vez de colgar en el test de R19.
    assert mutacion.declaraciones_escritas(texto) == {}


# --- R19, R21: la declaración se conserva, y no toca los análisis --------------


def _redactar(ruta: Path) -> None:
    texto = ruta.read_text(encoding="utf-8")
    pendiente = (
        f"{mutacion.CABECERA_DECLARACION_PENDIENTE}\n\n"
        "> Por qué no hay nada que mutar, o qué test lo cubre: PENDIENTE."
    )
    assert pendiente in texto
    ruta.write_text(texto.replace(pendiente, DECLARACION), encoding="utf-8")


def test_f026_r19_la_declaracion_redactada_se_conserva(tmp_path: Path) -> None:
    ruta = tmp_path / "mutacion_F-999.md"
    _texto(_informe(_por_fichero()), ruta)
    _redactar(ruta)

    assert mutacion.declaraciones_escritas(ruta.read_text(encoding="utf-8")) == {
        DECLARATIVO: DECLARACION
    }
    texto = _texto(_informe(_por_fichero()), ruta)

    assert DECLARACION in texto
    assert mutacion.CABECERA_DECLARACION_PENDIENTE not in texto


def test_f026_r19_la_plantilla_pendiente_no_cuenta_como_declaracion(tmp_path: Path) -> None:
    texto = _texto(_informe(_por_fichero()), tmp_path / "mutacion_F-999.md")

    assert mutacion.declaraciones_escritas(texto) == {}


def test_f026_r21_los_analisis_se_reponen_igual_con_la_seccion(tmp_path: Path) -> None:
    ruta = tmp_path / "mutacion_F-999.md"
    superviviente = _generados()[0]
    _texto(_informe(_por_fichero(), [superviviente]), ruta)
    _redactar(ruta)
    analisis = "#### Análisis (completado)\n\n> Equivalente: el test cubre el otro lado."
    texto = ruta.read_text(encoding="utf-8").replace(
        f"{CABECERA_PENDIENTE}\n\n> Por qué ningún test lo caza: PENDIENTE.\n"
        "> Decisión: ¿test nuevo o mutante equivalente justificado?",
        analisis,
    )
    ruta.write_text(texto, encoding="utf-8")

    escritos = analisis_escritos(texto)
    texto = _texto(_informe(_por_fichero(), [superviviente]), ruta)

    assert list(escritos.values()) == [analisis]
    assert analisis in texto
    assert DECLARACION in texto
    assert DECLARACION not in "".join(escritos.values())


# --- R16: la misma cifra en serie, en paralelo y en incremental ----------------


class _Doble:
    """Ejecutor falso con línea base verde: todo mutante muere."""

    def __init__(self, raiz: str = ".") -> None:
        self.raiz = raiz

    def identidad(self) -> tuple[str, str]:
        return (self.raiz, "doble")

    def ejecutar(self, timeout_s: int) -> str:
        return "muerto"

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        return ResultadoSuite(codigo=PYTEST_OK)


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _repo(raiz: Path) -> Path:
    raiz.mkdir(parents=True, exist_ok=True)
    _git(raiz, "init", "-q", "-b", "dev")
    for ruta, texto in ((LOGICA, FUENTE_LOGICA), (DECLARATIVO, FUENTE_DECLARATIVO),
                        ("tests/test_app.py", "def test_a():\n    assert True\n")):
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_text(texto, encoding="utf-8", newline="")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    return raiz


def test_f026_r16_serie_y_paralela_dan_la_misma_cifra_por_fichero(tmp_path: Path) -> None:
    raiz = _repo(tmp_path / "repo")

    serie = ejecutar_campania(_alcance(), _Doble(str(raiz)), raiz=str(raiz),
                              regla=REGLA, semilla=SEMILLA)
    paralela = ejecutar_campania_paralela(
        _alcance(), servicios=[], timeout_s=5, raiz=str(raiz), workers=2,
        regla=REGLA, semilla=SEMILLA, fabrica=lambda _f, r: _Doble(r),
    )

    assert serie.por_fichero == paralela.por_fichero == _por_fichero()
    assert sum(serie.por_fichero.values()) == serie.generados == paralela.generados


def test_f026_r16_la_paralela_con_lista_dada_cuenta_la_lista(tmp_path: Path) -> None:
    raiz = _repo(tmp_path / "repo")
    dados = _generados()[:2]

    paralela = ejecutar_campania_paralela(
        _alcance(), servicios=[], timeout_s=5, raiz=str(raiz), workers=2,
        mutantes=dados, fabrica=lambda _f, r: _Doble(r),
    )

    assert paralela.por_fichero == {DECLARATIVO: 0, LOGICA: 2}


def test_f026_r16_fusionar_copia_la_cifra_del_coordinador() -> None:
    parcial = _informe({LOGICA: 1})

    fundido = fusionar(_alcance(), [parcial], generados=5, segundos=0.0,
                       por_fichero=_por_fichero())

    assert fundido.por_fichero == _por_fichero()
    assert fusionar(_alcance(), [parcial], generados=5, segundos=0.0).por_fichero is None


def test_f026_r16_incremental_da_la_cifra_de_head(tmp_path: Path) -> None:
    raiz = _repo(tmp_path / "repo")
    serie = ejecutar_campania(_alcance(), _Doble(str(raiz)), raiz=str(raiz),
                              regla=REGLA, semilla=SEMILLA)
    serie.nivel = "critico"
    assert escribir_estado(serie, tmp_path / "estado.json")

    plan = plan_incremental(leer_estado(tmp_path / "estado.json"), REGLA, SEMILLA,
                            "critico", mutantes_del_alcance(_alcance(), str(raiz)))
    assert isinstance(plan, PlanIncremental)
    corta = ejecutar_campania(_alcance(), _Doble(str(raiz)), raiz=str(raiz),
                              mutantes=plan.reevaluar + plan.control)
    compuesto = componer_incremental(corta, plan)

    assert plan.por_fichero == {LOGICA: len(_generados())}, "el plan no sabe del alcance"
    assert compuesto.por_fichero == serie.por_fichero == _por_fichero()


def test_f026_r16_un_plan_de_antes_sin_cifra_no_rompe_el_informe(tmp_path: Path) -> None:
    plan = PlanIncremental(desde="abc", reevaluar=[], control=[], reutilizados=[],
                           generados=3, candidatos=3, limite=None)
    informe = componer_incremental(_informe(None), plan)

    assert informe.por_fichero is None
    assert f"| `{LOGICA}` | 2 | n/d |" in _texto(informe, tmp_path / "m.md")


RIGOR = {
    "nivel_por_defecto": "critico",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "mutacion": {"timeout_por_mutante_s": 5,
                 "incremental": {"control_fraccion": 0.5, "control_minimo": 1}},
    "niveles": {"critico": {"fase_red": True, "cobertura": True, "mutacion": True,
                            "un_mutante_por_linea": True, "semilla": SEMILLA}},
}


@pytest.fixture
def cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = _repo(tmp_path / "repo")
    (raiz / "harness").mkdir()
    (raiz / "harness" / "rigor.json").write_text(json.dumps(RIGOR), encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "rigor")
    monkeypatch.chdir(raiz)
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [{"id": "F-999"}])
    alcances = {"actual": _alcance()}
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcances["actual"])

    def lanzar(*extra: str) -> int:
        return mutacion.main(["--feature", "F-999", "--raiz", str(raiz), "--workers", "1",
                              *extra], ejecutor=_Doble(str(raiz)))

    return raiz, alcances, lanzar


def _filas_alcance(texto: str) -> list[str]:
    inicio = texto.index("## Alcance")
    return [linea for linea in texto[inicio:texto.index("## Totales")].splitlines()
            if linea.startswith("| ")]


def test_f026_r16_el_cli_da_la_misma_tabla_en_serie_y_en_incremental(cli) -> None:
    raiz, _, lanzar = cli
    informe = raiz / "progress" / "mutacion_F-999.md"

    assert lanzar() == 0
    completa = informe.read_text(encoding="utf-8")
    (raiz / "tests" / "test_otro.py").write_text("def test_b():\n    assert True\n",
                                                 encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "solo tests")
    assert lanzar("--incremental") == 0
    incremental = informe.read_text(encoding="utf-8")

    assert "| Modo | incremental desde" in incremental
    assert _filas_alcance(incremental) == _filas_alcance(completa)
    assert f"| `{DECLARATIVO}` | 2 | 0 — sin mutantes |" in _filas_alcance(incremental)


# --- R20: el cero de la campaña entera sigue abortando -------------------------


def test_f026_r20_sin_mutantes_en_ningun_fichero_aborta_sin_informe(
    cli, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz, alcances, lanzar = cli
    alcances["actual"] = _alcance(con_logica=False)

    assert lanzar() == NADA_JUZGADO
    assert "CERO MUTANTES" in capsys.readouterr().err
    assert not (raiz / "progress" / "mutacion_F-999.md").exists()


def test_f026_r20_con_otro_fichero_con_mutantes_hay_informe_y_ficha(cli) -> None:
    raiz, _, lanzar = cli

    assert lanzar() == 0
    texto = (raiz / "progress" / "mutacion_F-999.md").read_text(encoding="utf-8")

    assert f"### `{DECLARATIVO}` — 2 líneas en alcance, 0 mutantes" in texto
    assert lineas_comparables(texto)


def test_f026_r19_una_ficha_en_la_primera_linea_tambien_se_lee() -> None:
    """Mutación de la campaña de F-026 (`indice = 0` → `1`): la primera línea cuenta."""
    texto = f"### `{DECLARATIVO}` — 2 líneas en alcance, 0 mutantes\n\n{DECLARACION}\n"

    assert mutacion.declaraciones_escritas(texto) == {DECLARATIVO: DECLARACION}


def test_f026_r17_un_fichero_ausente_de_la_cifra_cuenta_como_cero(tmp_path: Path) -> None:
    """Mutación de la campaña de F-026 (`.get(fichero, 0)` → `1`).

    Un `por_fichero` que no nombra un fichero del alcance (un informe compuesto
    a mano, un plan antiguo) no tiene mutantes de ese fichero: es un cero.
    """
    texto = _texto(_informe({LOGICA: len(_generados())}), tmp_path / "mutacion_F-999.md")

    assert f"| `{DECLARATIVO}` | 2 | 0 — sin mutantes |" in texto
    assert f"### `{DECLARATIVO}` — 2 líneas en alcance, 0 mutantes" in texto
