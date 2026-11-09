# tests/test_f040_frontera.py
"""F-040 · La frontera con retenciones y tesorería (R30), sin red ni BBDD.

F-040 no toca el SQL de `sql/retenciones/` ni de `sql/tesoreria/`: el lado de
ingresos se construye aparte y las vistas de `ventas` LEEN `tesoreria` al
consultar. `retenciones.v_src_lineas_venta` pasa a leer `raw.dvfpro` solo
porque la tabla existe ya (su `00_setup.sql` la busca en el catálogo), sin
cambiar una línea. La conciliación cliente es de F-104.

El diff se mide contra la base común con `main` (`git merge-base`): lo que
`main` haya cambiado después no es de esta rama. Sin git, o sin `main`, el test
salta con aviso en vez de dar un verde que no ha mirado nada.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
INTOCABLES = (SQL / "retenciones", SQL / "tesoreria")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=False,
    )


def _base_comun() -> str:
    if shutil.which("git") is None:
        pytest.skip("R30: sin git en el entorno, no se puede medir el diff")
    base = _git("merge-base", "main", "HEAD")
    if base.returncode != 0 or not base.stdout.strip():
        pytest.skip(f"R30: sin rama `main` con la que comparar ({base.stderr.strip()})")
    return base.stdout.strip()


def test_f040_r30_las_carpetas_existen() -> None:
    for carpeta in INTOCABLES:
        assert carpeta.is_dir(), carpeta
        assert list(carpeta.glob("*.sql")), carpeta


def test_f040_r30_sin_diff_en_retenciones_ni_tesoreria() -> None:
    """Ni commits de la rama ni cambios sin confirmar en el árbol de trabajo."""
    base = _base_comun()
    rutas = [str(c.relative_to(RAIZ)).replace("\\", "/") for c in INTOCABLES]
    diff = _git("diff", "--name-only", base, "--", *rutas)
    assert diff.returncode == 0, diff.stderr
    assert diff.stdout.strip() == "", f"F-040 no toca este SQL (R30): {diff.stdout}"
    sin_seguimiento = _git("ls-files", "--others", "--exclude-standard", "--", *rutas)
    assert sin_seguimiento.stdout.strip() == "", sin_seguimiento.stdout


def test_f040_r30_retenciones_lee_dvfpro_solo_si_existe() -> None:
    """La lectura de `raw.dvfpro` ya estaba condicionada al catálogo: por eso no hay que tocarla."""
    setup = (SQL / "retenciones" / "00_setup.sql").read_text(encoding="utf-8")
    assert "table_schema = 'raw' AND table_name = 'dvfpro'" in setup
    assert "FROM raw.dvfpro" in setup


def test_f040_r30_ventas_no_escribe_en_retenciones_ni_tesoreria() -> None:
    """El SQL de `ventas` LEE `tesoreria` (vistas) pero no crea nada fuera de sus dos esquemas."""
    import re

    vistos = 0
    for fichero in sorted((SQL / "ventas").glob("*.sql")):
        texto = fichero.read_text(encoding="utf-8")
        destinos = re.findall(
            r"\b(?:CREATE(?:\s+OR\s+REPLACE)?\s+(?:TABLE|VIEW|FUNCTION|SCHEMA(?:\s+IF\s+NOT\s+EXISTS)?)"
            r"|DROP\s+(?:TABLE|VIEW|FUNCTION)(?:\s+IF\s+EXISTS)?|INSERT\s+INTO|UPDATE|DELETE\s+FROM"
            r"|TRUNCATE)\s+(\w+)",
            texto, re.IGNORECASE,
        )
        ajenos = {d for d in destinos if d.lower() not in ("ventas", "ventas_restringida")}
        assert not ajenos, f"{fichero.name}: escribe en {sorted(ajenos)}"
        vistos += len(destinos)
    assert vistos > 20, "el patrón tiene que ver los CREATE/DROP del módulo"
