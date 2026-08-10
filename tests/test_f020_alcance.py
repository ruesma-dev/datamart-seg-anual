# tests/test_f020_alcance.py
"""F-020 · Alcance con subcarpetas de servicios (R11, R12).

Sin git de verdad: el diff es un texto de fixture y el ejecutor de git, una
función que lo devuelve.
"""

from __future__ import annotations

from harness.alcance import (
    DIRECTORIOS_EXCLUIDOS,
    alcance_de_feature,
    es_produccion,
    filtrar_produccion,
    parsear_diff,
)

DIFF_MONOREPO = """diff --git a/services/email/app/flujo.py b/services/email/app/flujo.py
--- a/services/email/app/flujo.py
+++ b/services/email/app/flujo.py
@@ -1,2 +1,4 @@
 # services/email/app/flujo.py
+def procesar(mensaje):
+    return mensaje.strip()
diff --git a/services/email/tests/test_flujo.py b/services/email/tests/test_flujo.py
--- a/services/email/tests/test_flujo.py
+++ b/services/email/tests/test_flujo.py
@@ -1,1 +1,2 @@
 # services/email/tests/test_flujo.py
+def test_procesar(): pass
diff --git a/services/web/docs/notas.py b/services/web/docs/notas.py
--- a/services/web/docs/notas.py
+++ b/services/web/docs/notas.py
@@ -1,1 +1,2 @@
 # services/web/docs/notas.py
+EJEMPLO = 1
diff --git a/harness/servicios.py b/harness/servicios.py
--- a/harness/servicios.py
+++ b/harness/servicios.py
@@ -1,1 +1,2 @@
 # harness/servicios.py
+SEPARADOR = "|"
"""


# --- R11: los directorios excluidos lo son en cualquier nivel ---------------


def test_f020_r11_tests_de_servicio_quedan_fuera() -> None:
    assert es_produccion("services/email/tests/test_flujo.py") is False
    assert es_produccion("services/email/specs/F-001/design.py") is False
    assert es_produccion("apps/api/progress/notas.py") is False
    assert es_produccion("services/web/docs/ejemplo.py") is False


def test_f020_r11_codigo_de_servicio_queda_dentro() -> None:
    assert es_produccion("services/email/app/flujo.py") is True
    assert es_produccion("services/email/app/flujo.py".replace("/", "\\")) is True
    # Un directorio que solo EMPIEZA como uno excluido no se excluye.
    assert es_produccion("services/email/testsuite/apoyo.py") is True
    assert es_produccion("services/email/documentacion/util.py") is True


def test_f020_r11_prefijos_de_raiz_siguen_excluidos() -> None:
    """No romper F-015: lo que se excluía en la raíz se sigue excluyendo."""
    for ruta in ("tests/test_x.py", "specs/a.py", "progress/b.py", "docs/c.py"):
        assert es_produccion(ruta) is False
    assert es_produccion("harness/alcance.py") is True
    assert es_produccion("main.py") is True
    # Lo que no es Python nunca entra.
    assert es_produccion("services/email/app/plantilla.html") is False
    # Un fichero llamado como un directorio excluido sí es producción.
    assert es_produccion("services/email/app/docs.py") is True


def test_f020_r11_la_constante_declara_segmentos_no_prefijos() -> None:
    assert set(DIRECTORIOS_EXCLUIDOS) == {"tests", "specs", "progress", "docs"}
    assert not any(nombre.endswith("/") for nombre in DIRECTORIOS_EXCLUIDOS)


# --- R12: las rutas del alcance son relativas a la raíz del repositorio -----


def test_f020_r12_alcance_conserva_rutas_de_subcarpetas() -> None:
    lineas = filtrar_produccion(parsear_diff(DIFF_MONOREPO))

    assert sorted(lineas) == ["harness/servicios.py", "services/email/app/flujo.py"]
    assert lineas["services/email/app/flujo.py"] == {2, 3}


def test_f020_r12_el_alcance_de_una_feature_no_recorta_las_rutas() -> None:
    def git_falso(args: list[str]) -> str:
        if args[0] == "rev-parse":
            return "abc123\n"
        if args[0] == "merge-base":
            return "base123\n"
        return DIFF_MONOREPO

    alcance = alcance_de_feature("F-020", rama="feature/F-020-x", git=git_falso)

    assert alcance.ficheros() == [
        "harness/servicios.py",
        "services/email/app/flujo.py",
    ]
    assert alcance.total_lineas() == 3
