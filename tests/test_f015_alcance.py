# tests/test_f015_alcance.py
"""F-015 · Alcance de una feature calculado desde el diff de git (R2, R4).

Ningún test de este fichero ejecuta git de verdad: el diff es una fixture de
texto y el ejecutor de git se inyecta como doble.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.alcance import (
    alcance_de_feature,
    ejecutar_git,
    es_produccion,
    filtrar_produccion,
    git_en,
    parsear_diff,
    rama_de_feature,
    resolver_refs,
)

# --- Fixtures de texto (formato unificado de `git diff`) ---------------------

DIFF_MIXTO = """diff --git a/etl_x/util.py b/etl_x/util.py
index 1111111..2222222 100644
--- a/etl_x/util.py
+++ b/etl_x/util.py
@@ -8,6 +8,8 @@ def suma(a, b):
     total = a + b
-    return total
+    if total > 0:
+        return total
+    return 0


diff --git a/tests/test_util.py b/tests/test_util.py
index 3333333..4444444 100644
--- a/tests/test_util.py
+++ b/tests/test_util.py
@@ -1,2 +1,3 @@
 def test_suma():
+    assert suma(1, 2) == 3
     pass
diff --git a/docs/NOTAS.md b/docs/NOTAS.md
index 5555555..6666666 100644
--- a/docs/NOTAS.md
+++ b/docs/NOTAS.md
@@ -1,1 +1,2 @@
 # Notas
+Línea nueva de documentación.
diff --git a/infra/desplegar.ps1 b/infra/desplegar.ps1
index 7777777..8888888 100644
--- a/infra/desplegar.ps1
+++ b/infra/desplegar.ps1
@@ -3,1 +3,2 @@
 Write-Host "hola"
+Write-Host "adios"
"""

DIFF_FICHERO_NUEVO = """diff --git a/etl_x/nuevo.py b/etl_x/nuevo.py
new file mode 100644
index 0000000..9999999
--- /dev/null
+++ b/etl_x/nuevo.py
@@ -0,0 +1,4 @@
+# etl_x/nuevo.py
+def f(x):
+    return x + 1
+
"""

DIFF_BORRADO = """diff --git a/etl_x/viejo.py b/etl_x/viejo.py
deleted file mode 100644
index 9999999..0000000
--- a/etl_x/viejo.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def f():
-    pass
"""


class GitFalso:
    """Doble del ejecutor de git: devuelve respuestas guionizadas."""

    def __init__(self, respuestas: dict[str, str]) -> None:
        self.respuestas = respuestas
        self.llamadas: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.llamadas.append(list(args))
        for clave, valor in self.respuestas.items():
            if clave in " ".join(args):
                return valor
        return ""


# --- R2 ---------------------------------------------------------------------


def test_f015_r2_parser_de_diff_extrae_lineas_por_fichero() -> None:
    lineas = parsear_diff(DIFF_MIXTO)

    # Del fichero de producción entran SOLO las líneas añadidas, numeradas
    # sobre el fichero nuevo: el hunk empieza en 8, la línea de contexto es la
    # 8 y las tres añadidas son 9, 10 y 11.
    assert lineas["etl_x/util.py"] == {9, 10, 11}
    # El parser no filtra todavía: ve todos los ficheros del diff.
    assert lineas["tests/test_util.py"] == {2}
    assert lineas["docs/NOTAS.md"] == {2}
    assert lineas["infra/desplegar.ps1"] == {4}


def test_f015_r2_fichero_nuevo_entra_entero() -> None:
    lineas = filtrar_produccion(parsear_diff(DIFF_FICHERO_NUEVO))

    assert lineas == {"etl_x/nuevo.py": {1, 2, 3, 4}}


def test_f015_r2_tests_y_no_python_quedan_fuera() -> None:
    lineas = filtrar_produccion(parsear_diff(DIFF_MIXTO))

    assert set(lineas) == {"etl_x/util.py"}
    assert es_produccion("etl_x/util.py") is True
    assert es_produccion("harness/mutacion.py") is True
    for fuera in (
        "tests/test_util.py",
        "specs/F-001-x/design.md",
        "progress/current.md",
        "docs/CONVENTIONS.md",
        "infra/desplegar.ps1",
        "config/tablas.yaml",
    ):
        assert es_produccion(fuera) is False, fuera


def test_f015_r2_fichero_borrado_no_entra() -> None:
    assert filtrar_produccion(parsear_diff(DIFF_BORRADO)) == {}


def test_f015_r2_lineas_fuera_de_un_hunk_no_cuentan() -> None:
    # Sin cabecera `@@` no se sabe a qué línea corresponde lo añadido: se
    # ignora, en vez de inventarse un número.
    sin_hunk = "--- a/x.py\n+++ b/x.py\n+linea suelta\n"
    hunk_ilegible = "--- a/x.py\n+++ b/x.py\n@@ esto no es una cabecera @@\n+linea\n"

    assert parsear_diff(sin_hunk) == {}
    assert parsear_diff(hunk_ilegible) == {}


# --- R4 ---------------------------------------------------------------------


def test_f015_r4_resolucion_rama_luego_merge_luego_error() -> None:
    # 1) La rama existe: se usa la base común con `dev`.
    git = GitFalso({"rev-parse": "abc123\n", "merge-base": "base999\n"})
    assert resolver_refs("F-042", "feature/F-042-x", "dev", git=git) == (
        "base999",
        "feature/F-042-x",
        "rama",
    )

    # 2) La rama ya no existe: se cae al commit de merge.
    git = GitFalso({"log": "merge777\n"})
    assert resolver_refs("F-042", "feature/F-042-x", "dev", git=git) == (
        "merge777^1",
        "merge777",
        "merge",
    )

    # 3) Ni rama ni merge: aborta explícitamente, sin mutar nada.
    git = GitFalso({})
    with pytest.raises(SystemExit) as exc:
        resolver_refs("F-042", "feature/F-042-x", "dev", git=git)
    assert "F-042" in str(exc.value)
    assert "feature/F-042-x" in str(exc.value)

    # 4) Y si ni siquiera había rama declarada, el mensaje lo dice.
    with pytest.raises(SystemExit) as exc:
        resolver_refs("F-042", None, "dev", git=GitFalso({}))
    assert "(sin declarar)" in str(exc.value)


def test_f015_r4_diff_de_merge_usa_primer_padre() -> None:
    git = GitFalso({"log": "merge777\n", "diff": DIFF_FICHERO_NUEVO})

    alcance = alcance_de_feature("F-042", base="dev", rama="feature/F-042-x", git=git)

    assert alcance.origen == "merge"
    assert alcance.ref_diff == ("merge777^1", "merge777")
    assert alcance.lineas == {"etl_x/nuevo.py": {1, 2, 3, 4}}
    # El diff se pide entre el primer padre y el propio merge.
    diffs = [c for c in git.llamadas if c and c[0] == "diff"]
    assert diffs == [["diff", "merge777^1", "merge777"]]


def test_f015_r4_ejecutar_git_de_verdad_devuelve_vacio_si_git_falla() -> None:
    # git es de solo lectura y local: aquí no hay red ni BBDD.
    assert ejecutar_git(["rev-parse", "--verify", "--quiet", "rama-que-no-existe"]) == ""
    salida = ejecutar_git(["rev-parse", "--abbrev-ref", "HEAD"])
    # Texto, no bytes: el parser del diff trabaja con str.
    assert isinstance(salida, str)
    assert salida.strip() != ""
    assert git_en(".")(["rev-parse", "--verify", "--quiet", "HEAD"]).strip() != ""


def test_f015_r4_la_rama_sale_del_inventario_de_features(tmp_path: Path) -> None:
    inventario = tmp_path / "features.json"
    inventario.write_text(
        json.dumps(
            {"features": [{"id": "F-042", "branch": "feature/F-042-x"}, {"id": "F-043"}]}
        ),
        encoding="utf-8",
    )

    assert rama_de_feature("F-042", str(inventario)) == "feature/F-042-x"
    assert rama_de_feature("F-043", str(inventario)) is None
    assert rama_de_feature("F-999", str(inventario)) is None
    # Sin inventario (o con uno ilegible) no se revienta: se cae al merge.
    assert rama_de_feature("F-042", str(tmp_path / "no_existe.json")) is None
    roto = tmp_path / "roto.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    assert rama_de_feature("F-042", str(roto)) is None


def test_f015_r4_total_de_lineas_del_alcance() -> None:
    git = GitFalso({"log": "merge777\n", "diff": DIFF_MIXTO})

    alcance = alcance_de_feature("F-042", base="dev", rama="feature/F-042-x", git=git)

    assert alcance.total_lineas() == 3
    assert alcance.ficheros() == ["etl_x/util.py"]
    # La descripción dice de dónde sale el alcance, y en qué orden.
    descripcion = alcance.descripcion()
    assert descripcion.startswith("F-042: 1 fichero(s), 3 línea(s)")
    assert "merge777^1..merge777" in descripcion
