# tests/test_f112_base_de_la_puerta.py
"""F-112 · La puerta de cobertura mide contra la rama donde de verdad se integra.

Hallazgo del reviewer de F-109: `harness/init.sh` fijaba `RAMA_BASE=dev`, y
`dev` llevaba parada desde el 2026-09-03 mientras todo se integraba en `main`.
La puerta de cobertura calculaba el diff `merge-base(dev, HEAD)..HEAD`, que
arrastraba semanas de features ya cerradas: F-110 y F-109 dieron la MISMA cifra
(95,1 % de 1.106 líneas) y ninguna de esas líneas era de F-109. La puerta
imprimía verde sin medir lo que dice medir.

Lo que se fija aquí:

- La base de las puertas es el merge-base de la rama con la rama de
  integración CONFIGURADA (`RAMA_BASE` de `harness/init.sh`), y las
  herramientas la leen de ahí cuando no se les pasa `--base`.
- Si con esa base la puerta mediría commits que ya viven en otra rama de larga
  vida (la base se ha quedado por detrás), la puerta sale en ROJO diciendo
  cuántos y dónde, en vez de medir líneas ajenas.
- Una rama ya integrada se mide por el merge que la integró, no por un diff
  vacío (sirve para remedir features cerradas y para su campaña de mutación).

Ningún test toca red ni base de datos: repositorios git de juguete bajo
`tmp_path` y, en los dos tests del propio repositorio, solo lecturas de git.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from harness import cobertura, rutas_sensibles
from harness.alcance import (
    RAMAS_DE_LARGA_VIDA,
    alcance_de_feature,
    diagnosticar_base,
    git_en,
    rama_base_configurada,
    resolver_refs,
)
from harness.rutas_sensibles import RutaSensible, Verificacion

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RIGOR = RAIZ / "harness" / "rigor.json"
INIT_SH = RAIZ / "harness" / "init.sh"

RAMA = "feature/F-900-x"


# --- Repositorio de juguete -------------------------------------------------


def _git(raiz: Path, *args: str) -> str:
    salida = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "user.name=Arnes",
            "-c",
            "user.email=arnes@ejemplo.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return salida.stdout.strip()


def _commit(raiz: Path, ruta: str, texto: str, mensaje: str) -> None:
    fichero = raiz / ruta
    fichero.parent.mkdir(parents=True, exist_ok=True)
    fichero.write_text(texto, encoding="utf-8", newline="\n")
    _git(raiz, "add", ruta)
    _git(raiz, "commit", "-q", "-m", mensaje)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """`dev` parada en el primer commit, `main` avanzada y la feature desde `main`.

    Es la forma exacta del repositorio el día del hallazgo: el trabajo de otras
    features (`app/ajeno.py`, `app/otro_ajeno.py`) está en `main` y no en `dev`.
    """
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "main")
    _commit(raiz, "app/base.py", "# app/base.py\nX = 1\n", "inicio")
    _git(raiz, "branch", "dev")
    _commit(
        raiz,
        "app/ajeno.py",
        "# app/ajeno.py\ndef ajeno():\n    return 2\n",
        "F-800: trabajo de otra feature, ya integrado en main",
    )
    _commit(
        raiz,
        "app/otro_ajeno.py",
        "# app/otro_ajeno.py\ndef otro():\n    return 4\n",
        "F-801: mas trabajo ya integrado en main",
    )
    _git(raiz, "checkout", "-q", "-b", RAMA)
    _commit(
        raiz,
        "app/nuevo.py",
        "# app/nuevo.py\ndef nuevo():\n    return 3\n",
        "F-900 T1: lo unico que escribe esta feature",
    )
    return raiz


def _entorno_de_puerta(raiz: Path, rama_base: str | None = None) -> list[str]:
    """features.json y coverage.json de la puerta; opcionalmente, un init.sh.

    El coverage.json da por EJECUTADAS también las líneas ajenas: así, contra
    la base rezagada, la puerta de antes salía en verde (100 % de 6 líneas)
    habiendo medido cuatro líneas que no eran de la rama.
    """
    features = {
        "features": [
            {
                "id": "F-900",
                "title": "Feature de juguete",
                "status": "in_progress",
                "sdd": False,
                "rigor": "estandar",
                "branch": RAMA,
            }
        ]
    }
    cov = {
        "files": {
            "app/nuevo.py": {"executed_lines": [2, 3], "missing_lines": []},
            "app/ajeno.py": {"executed_lines": [2, 3], "missing_lines": []},
            "app/otro_ajeno.py": {"executed_lines": [2, 3], "missing_lines": []},
        }
    }
    fuera = raiz.parent
    (fuera / "features.json").write_text(json.dumps(features), encoding="utf-8")
    (fuera / "coverage.json").write_text(json.dumps(cov), encoding="utf-8")
    if rama_base is not None:
        (raiz / "harness").mkdir(exist_ok=True)
        (raiz / "harness" / "init.sh").write_text(
            f"#!/usr/bin/env bash\nRAMA_BASE={rama_base}            # comentario\n",
            encoding="utf-8",
            newline="\n",
        )
    return [
        "--config",
        str(RUTA_RIGOR),
        "--features",
        str(fuera / "features.json"),
        "--cov",
        str(fuera / "coverage.json"),
        "--raiz",
        str(raiz),
    ]


# --- R1 · la base es el merge-base con la rama de integración ---------------


def test_f112_r1_contra_dev_parada_el_alcance_arrastra_lineas_ajenas(repo: Path) -> None:
    # Caracterización del defecto: con la base rezagada, el «qué cambió» de la
    # feature incluye el trabajo de F-800 y F-801, que no es suyo.
    alcance = alcance_de_feature("F-900", base="dev", rama=RAMA, raiz=str(repo))

    assert set(alcance.lineas) == {"app/ajeno.py", "app/otro_ajeno.py", "app/nuevo.py"}


def test_f112_r1_contra_main_el_alcance_es_solo_de_la_rama(repo: Path) -> None:
    alcance = alcance_de_feature("F-900", base="main", rama=RAMA, raiz=str(repo))

    assert alcance.lineas == {"app/nuevo.py": {1, 2, 3}}
    assert alcance.ref_diff[0] == _git(repo, "merge-base", "main", RAMA)


def test_f112_r1_diagnostico_base_rezagada(repo: Path) -> None:
    git = git_en(str(repo))

    motivo = diagnosticar_base("dev", RAMA, git=git)

    assert motivo is not None
    # Dice cuántos commits ajenos mediría, de cuántos, y dónde viven ya.
    assert "2 de los 3" in motivo
    assert "main" in motivo and "dev" in motivo
    assert "RAMA_BASE" in motivo


def test_f112_r1_diagnostico_base_sana(repo: Path) -> None:
    assert diagnosticar_base("main", RAMA, git=git_en(str(repo))) is None
    # La rama recién creada y sin commits propios tampoco es un problema.
    _git(repo, "branch", "feature/F-901-vacia", "main")
    assert diagnosticar_base("main", "feature/F-901-vacia", git=git_en(str(repo))) is None


def test_f112_r1_diagnostico_base_inexistente(repo: Path) -> None:
    motivo = diagnosticar_base("trunk", RAMA, git=git_en(str(repo)))

    assert motivo is not None and "trunk" in motivo and "no existe" in motivo


def test_f112_r1_fuera_de_un_repositorio_no_diagnostica(tmp_path: Path) -> None:
    # Sin repositorio no hay nada que diagnosticar: las puertas ya declaran
    # N/A con su motivo por su lado, y este chequeo no debe tumbarlas.
    assert diagnosticar_base("main", RAMA, git=git_en(str(tmp_path))) is None


# --- R2 · las puertas se ponen en rojo si mediría líneas ajenas -------------


def test_f112_r2_puerta_cobertura_ko_con_la_base_rezagada(
    repo: Path, capsys: pytest.CaptureFixture
) -> None:
    codigo = cobertura.main(["--base", "dev", *_entorno_de_puerta(repo)])

    salida = capsys.readouterr()
    assert codigo == 1, salida.out
    assert "PUERTA COBERTURA" in salida.err
    assert "main" in salida.err and "dev" in salida.err


def test_f112_r2_puerta_cobertura_mide_solo_la_rama_contra_main(
    repo: Path, capsys: pytest.CaptureFixture
) -> None:
    codigo = cobertura.main(["--base", "main", *_entorno_de_puerta(repo)])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "de 2 líneas cambiadas" in salida
    # Y dice contra qué midió: sin eso, dos features con la misma cifra no
    # levantaban ninguna sospecha.
    base = _git(repo, "merge-base", "main", RAMA)
    assert base[:10] in salida


def test_f112_r2_sin_base_explicita_se_usa_la_de_init_sh(
    repo: Path, capsys: pytest.CaptureFixture
) -> None:
    codigo = cobertura.main(_entorno_de_puerta(repo, rama_base="main"))

    assert codigo == 0
    assert "de 2 líneas cambiadas" in capsys.readouterr().out


def test_f112_r2_puerta_rutas_sensibles_ko_con_la_base_rezagada(repo: Path) -> None:
    verificacion = Verificacion(
        nombre="prompts",
        comando="echo {feature}",
        informe="progress/verif_{feature}.md",
        exigencia="bloqueo",
        rutas=(RutaSensible(patron="app/ajeno.py", motivo="prompt de IA"),),
    )

    rezagada = rutas_sensibles.evaluar_puerta(
        [verificacion], feature="F-900", rama=RAMA, base="dev", raiz=repo
    )
    sana = rutas_sensibles.evaluar_puerta(
        [verificacion], feature="F-900", rama=RAMA, base="main", raiz=repo
    )

    assert rezagada.codigo == 1
    assert "main" in rezagada.mensaje and "dev" in rezagada.mensaje
    # Contra main la feature no toca la ruta sensible (es de F-800): N/A.
    assert sana.codigo == 0 and "N/A" in sana.mensaje


def test_f112_r2_rama_base_configurada_sale_de_init_sh(tmp_path: Path) -> None:
    assert rama_base_configurada(str(tmp_path)) == "dev"  # sin init.sh: histórico
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "init.sh").write_text(
        'X=1\nRAMA_BASE="trunk"   # rama de integración\n', encoding="utf-8"
    )
    assert rama_base_configurada(str(tmp_path)) == "trunk"


def test_f112_r2_este_repositorio_integra_en_main() -> None:
    # Decisión de este proyecto: `main` es la rama de integración (leader.md,
    # sección «Ramas»); `dev` está parada desde el 2026-09-03.
    assert rama_base_configurada(str(RAIZ)) == "main"


def test_f112_r2_init_sh_pasa_la_base_configurada_a_las_dos_puertas() -> None:
    guion = INIT_SH.read_text(encoding="utf-8")

    assert re.search(r"harness\.cobertura --base \"\$RAMA_BASE\"", guion)
    assert re.search(r"harness\.rutas_sensibles --puerta --base \"\$RAMA_BASE\"", guion)


def test_f112_r2_en_este_repositorio_la_base_no_esta_rezagada() -> None:
    """El test que habría cazado el hallazgo: HEAD contra la base configurada.

    Falla si la puerta, en la rama donde se ejecuta la suite, mediría commits
    que ya están en otra rama de larga vida: exactamente lo que pasaba con
    `dev` parada y el trabajo integrándose en `main`.
    """
    git = git_en(str(RAIZ))
    if not git(["rev-parse", "--git-dir"]).strip():
        pytest.skip("sin git no hay historial contra el que comparar")
    rama = git(["branch", "--show-current"]).strip()
    if rama in RAMAS_DE_LARGA_VIDA:
        # En una rama de integración la puerta no aplica (se declara N/A), y
        # allí el diagnóstico compararía una rama de larga vida con otra.
        pytest.skip(f"en '{rama}' la puerta de cobertura no aplica")
    base = rama_base_configurada(str(RAIZ))
    if not git(["rev-parse", "--verify", "--quiet", base]).strip():
        pytest.skip(f"este clon no tiene la rama base '{base}'")

    assert diagnosticar_base(base, "HEAD", git=git) is None


# --- R5 · una rama ya integrada se mide por su merge ------------------------


def test_f112_r5_rama_integrada_se_mide_por_el_merge_que_la_integro(repo: Path) -> None:
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", RAMA, "-m", "Merge de F-900")
    merge = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "app/despues.py", "# app/despues.py\nY = 2\n", "F-902: posterior")

    ref_a, ref_b, origen = resolver_refs("F-900", RAMA, "main", git=git_en(str(repo)))
    alcance = alcance_de_feature("F-900", base="main", rama=RAMA, raiz=str(repo))

    assert (ref_a, ref_b, origen) == (f"{merge}^1", merge, "merge")
    assert alcance.lineas == {"app/nuevo.py": {1, 2, 3}}


def test_f112_r5_rama_sin_commits_propios_no_busca_merge(repo: Path) -> None:
    _git(repo, "branch", "feature/F-903-recien-creada", "main")

    alcance = alcance_de_feature(
        "F-903", base="main", rama="feature/F-903-recien-creada", raiz=str(repo)
    )

    assert alcance.origen == "rama" and alcance.lineas == {}
