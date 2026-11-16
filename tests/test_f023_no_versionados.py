# tests/test_f023_no_versionados.py
"""F-023 · Lo no versionado que la suite necesita llega a los worktrees (R16–R20).

Un worktree solo trae lo versionado. Hasta F-023 solo el `.env` llegaba, y como
variables: cualquier otro fichero ignorado (datos locales, certificados, una
fixture generada) dejaba la línea base del worker en rojo. Con
`mutacion.ficheros_no_versionados` el proyecto declara qué más hace falta: se
copia a cada worktree, y si falta en el árbol principal la campaña aborta
antes de tocar nada, nombrándolo. El `.env` sigue sin copiarse nunca.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import mutacion, mutacion_paralela, rigor
from harness.alcance import Alcance
from harness.mutacion import FaltanFicheros, comprobar_ficheros_no_versionados
from harness.mutacion_paralela import copiar_no_versionados, ejecutar_campania_paralela
from harness.rigor import CapaLocalInvalida, cargar_rigor
from harness.tiempos import escalar_timeout

TIMEOUT_S = escalar_timeout(240)

APP = """# app.py
def doble(x):
    return x * 2


def siguiente(x):
    return x + 1
"""

#: Suite que necesita un fichero y una carpeta que git ignora.
TEST_APP = """# test_app.py
from pathlib import Path

import app

RAIZ = Path(__file__).resolve().parent


def test_hay_datos_locales():
    assert (RAIZ / "datos.local").read_text(encoding="utf-8") == "dato\\n"
    assert (RAIZ / "fixtures" / "sub" / "x.txt").is_file()


def test_doble():
    assert app.doble(3) == 6


def test_siguiente():
    assert app.siguiente(3) == 4
"""

RIGOR_BASE = {
    "nivel_por_defecto": "e",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "mutacion": {"timeout_por_mutante_s": 5},
    "niveles": {"e": {"fase_red": True, "cobertura": True, "mutacion": True}},
}


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def _repositorio(destino: Path) -> Path:
    destino.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "dev", str(destino)], check=True, capture_output=True
    )
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    (destino / "app.py").write_text(APP, encoding="utf-8", newline="")
    (destino / "test_app.py").write_text(TEST_APP, encoding="utf-8", newline="")
    (destino / ".gitignore").write_text("datos.local\nfixtures/\n.env\n", encoding="utf-8")
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")
    (destino / "datos.local").write_text("dato\n", encoding="utf-8", newline="")
    (destino / "fixtures" / "sub").mkdir(parents=True)
    (destino / "fixtures" / "sub" / "x.txt").write_text("x\n", encoding="utf-8")
    (destino / ".env").write_text("ARNES_F023_NO_COPIAR=1\n", encoding="utf-8")
    return destino


def _alcance() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/x"),
                   lineas={"app.py": {3, 7}})


def _aritmeticos() -> list:
    return [m for m in mutacion.generar_mutantes(APP, {3, 7}, "app.py")
            if m.operador == "aritmetico"]


# --- R16 · la copia llega a cada worktree ------------------------------------


def test_f023_r16_lo_declarado_llega_a_cada_worktree_y_la_base_sale_verde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio = _repositorio(tmp_path / "juguete")
    vistos: list[str] = []
    copiar = mutacion_paralela.copiar_no_versionados

    def espia(raiz, rutas, ficheros):
        copiar(raiz, rutas, ficheros)
        for ruta in rutas:
            vistos.extend(sorted(p.relative_to(ruta).as_posix()
                                 for p in Path(ruta).rglob("*")
                                 if p.is_file() and ".git" not in p.parts))

    monkeypatch.setattr(mutacion_paralela, "copiar_no_versionados", espia)

    informe = ejecutar_campania_paralela(
        _alcance(), [], timeout_s=TIMEOUT_S, raiz=str(repositorio), workers=2,
        mutantes=_aritmeticos(), ficheros=["datos.local", "fixtures", ".env"],
    )

    assert informe.timeouts == []
    assert informe.muertos == 2, "con la copia, la base del worker está verde"
    assert vistos.count("datos.local") == 2
    assert vistos.count("fixtures/sub/x.txt") == 2
    assert ".env" not in vistos, "el .env nunca se copia"


# --- R17, R18 · sin la clave, como hoy; el .env, solo variables --------------


def test_f023_r17_sin_clave_no_se_declara_nada() -> None:
    assert rigor.ficheros_no_versionados(RIGOR_BASE) == []
    assert rigor.ficheros_no_versionados(
        {**RIGOR_BASE, "mutacion": {"ficheros_no_versionados": ["a"]}}
    ) == ["a"]


def test_f023_r17_sin_ficheros_la_paralela_no_copia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repositorio = _repositorio(tmp_path / "juguete")
    llamadas: list[object] = []
    monkeypatch.setattr(mutacion_paralela, "copiar_no_versionados",
                        lambda *a: llamadas.append(a))
    monkeypatch.setattr(mutacion_paralela, "ejecutar_campania",
                        lambda *a, **k: mutacion.InformeMutacion("F-999", _alcance()))

    ejecutar_campania_paralela(_alcance(), [], raiz=str(repositorio), workers=2,
                               mutantes=_aritmeticos())

    assert all(not a[2] for a in llamadas), "sin la clave no se copia nada"


def test_f023_r18_el_env_declarado_es_obligatorio_pero_no_se_copia(tmp_path: Path) -> None:
    origen, destino = tmp_path / "origen", tmp_path / "destino"
    origen.mkdir()
    destino.mkdir()
    (origen / ".env").write_text("A=1\n", encoding="utf-8")
    (origen / "datos.local").write_text("d\n", encoding="utf-8")

    comprobar_ficheros_no_versionados(str(origen), [".env", "datos.local"])
    copiar_no_versionados(str(origen), [str(destino)], [".env", "datos.local"])

    assert (destino / "datos.local").read_text(encoding="utf-8") == "d\n"
    assert not (destino / ".env").exists()
    (origen / ".env").unlink()
    with pytest.raises(FaltanFicheros, match=r"\.env"):
        comprobar_ficheros_no_versionados(str(origen), [".env"])


def test_f023_r16_carpeta_que_el_worktree_ya_trae_a_medias(tmp_path: Path) -> None:
    """La carpeta declarada existe en el worktree con su parte versionada
    (un `.gitkeep`): la copia completa lo no versionado sin fallar."""
    origen, destino = tmp_path / "origen", tmp_path / "destino"
    (origen / "datos").mkdir(parents=True)
    (destino / "datos").mkdir(parents=True)
    (origen / "datos" / ".gitkeep").write_text("", encoding="utf-8")
    (destino / "datos" / ".gitkeep").write_text("", encoding="utf-8")
    (origen / "datos" / "local.csv").write_text("a;b\n", encoding="utf-8")

    copiar_no_versionados(str(origen), [str(destino)], ["datos"])

    assert (destino / "datos" / "local.csv").read_text(encoding="utf-8") == "a;b\n"


# --- R19 · lo que falta aborta antes de tocar nada ---------------------------


def test_f023_r19_la_comprobacion_nombra_cada_ruta_que_falta(tmp_path: Path) -> None:
    (tmp_path / "hay.txt").write_text("x", encoding="utf-8")

    with pytest.raises(FaltanFicheros) as caido:
        comprobar_ficheros_no_versionados(str(tmp_path), ["hay.txt", "falta.txt", "otra/sub"])

    assert "falta.txt" in str(caido.value)
    assert "otra/sub" in str(caido.value)
    assert "hay.txt" not in str(caido.value).split("\n", 1)[-1]
    assert isinstance(caido.value, mutacion.CampaniaAbortada)


@pytest.mark.parametrize("workers", ["1", "2"])
def test_f023_r19_main_aborta_con_3_sin_crear_worktrees_ni_mutar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    workers: str,
) -> None:
    repositorio = _repositorio(tmp_path / "juguete")
    (repositorio / "harness").mkdir()
    (repositorio / "harness" / "rigor.json").write_text(json.dumps(
        {**RIGOR_BASE, "mutacion": {"timeout_por_mutante_s": 5,
                                    "ficheros_no_versionados": ["datos.local", "falta.txt",
                                                                "otra/sub"]}}),
        encoding="utf-8")
    monkeypatch.chdir(repositorio)
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [{"id": "F-999"}])
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: _alcance())

    def prohibido(*a, **k):
        pytest.fail("la campaña no debía arrancar")

    monkeypatch.setattr(mutacion, "ejecutar_campania", prohibido)
    monkeypatch.setattr(mutacion_paralela, "ejecutar_campania_paralela", prohibido)
    monkeypatch.setattr(mutacion_paralela, "Worktrees", prohibido)

    codigo = mutacion.main(["--feature", "F-999", "--raiz", str(repositorio),
                            "--workers", workers])

    assert codigo == 3
    error = capsys.readouterr().err
    assert "falta.txt" in error and "otra/sub" in error
    assert not (repositorio / ".arnes_cache" / "mutacion_en_curso.json").exists()
    assert (repositorio / "app.py").read_text(encoding="utf-8") == APP


# --- R20 · rutas inválidas ----------------------------------------------------


@pytest.mark.parametrize("valor", ["/abs/x", "../fuera", "a/../../b", "C:/x", "C:x", 3,
                                   "\\\\servidor\\x"])
def test_f023_r20_una_ruta_invalida_en_la_capa_local_falla_nombrandola(
    tmp_path: Path, valor: object
) -> None:
    (tmp_path / "rigor.json").write_text(json.dumps(RIGOR_BASE), encoding="utf-8")
    (tmp_path / "rigor.local.json").write_text(
        json.dumps({"mutacion": {"ficheros_no_versionados": ["bien.txt", valor]}}),
        encoding="utf-8")

    with pytest.raises(CapaLocalInvalida) as caido:
        cargar_rigor(tmp_path / "rigor.json")

    assert "mutacion.ficheros_no_versionados" in str(caido.value)
    assert repr(valor) in str(caido.value) or str(valor) in str(caido.value)


@pytest.mark.parametrize("valor", ["../fuera", "", "   ", 3])
def test_f023_r20_una_ruta_invalida_en_rigor_json_falla(tmp_path: Path, valor: object) -> None:
    """En `rigor.json` no hay esquema de tipos por delante: el vacío y el que no
    es texto los para solo `_ruta_relativa_valida`."""
    (tmp_path / "rigor.json").write_text(json.dumps(
        {**RIGOR_BASE, "mutacion": {"ficheros_no_versionados": [valor]}}),
        encoding="utf-8")

    with pytest.raises(ValueError, match=r"mutacion\.ficheros_no_versionados"):
        cargar_rigor(tmp_path / "rigor.json")


def test_f023_r20_rutas_validas_se_aceptan(tmp_path: Path) -> None:
    (tmp_path / "rigor.json").write_text(json.dumps(RIGOR_BASE), encoding="utf-8")
    (tmp_path / "rigor.local.json").write_text(
        json.dumps({"mutacion": {"ficheros_no_versionados": ["datos.local", "a/b", ".env"]}}),
        encoding="utf-8")

    datos = cargar_rigor(tmp_path / "rigor.json")

    assert rigor.ficheros_no_versionados(datos) == ["datos.local", "a/b", ".env"]
