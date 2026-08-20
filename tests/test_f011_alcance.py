# tests/test_f011_alcance.py
"""
F-011 · Tests de ALCANCE: lo que esta feature tenía prohibido hacer (R22) y el
barrido de secretos sobre lo que añade (R24).

R22 no es una preferencia de organización. El bloque C original de F-011
—acotar el build a una «ventana de negocio»— salió entero a **F-025** el
2026-08-18 porque depende de una decisión que Negocio **no ha tomado** (DA-1:
qué es una obra abierta). Acotar el build cambia **qué ve Power BI**, no solo
cuánto tarda, así que exige su propia prueba de equivalencia, como hizo F-019
con el troceado. Estos tests son la barrera que impide que eso se cuele aquí
por el camino, que es exactamente como se cuelan esas cosas.

Ninguno abre red ni BBDD.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import main
from tests.test_f005_grants import buscar_secretos

REPO = Path(__file__).resolve().parents[1]

#: Todo lo que F-011 añade al árbol. La lista se mantiene a mano a propósito:
#: si la feature crece, hay que venir aquí, y venir aquí es lo que recuerda que
#: el barrido de secretos y la barrera de alcance existen.
FICHEROS_DE_LA_FEATURE = (
    "etl_sigrid/domain/perfil_carga.py",
    "etl_sigrid/domain/extraccion.py",
    "etl_sigrid/domain/tiemod.py",
    "etl_sigrid/infrastructure/sigrid/bench_extraccion.py",
    "tests/test_f011_perfil.py",
    "tests/test_f011_bench.py",
    "tests/test_f011_tiemod.py",
    "tests/test_f011_cli.py",
    # `tests/test_f011_alcance.py` NO se barre a sí mismo: contiene claves
    # falsas a propósito, como control negativo del afinado de abajo. Barrerlo
    # obligaría a debilitar el filtro justo donde tiene que ser estricto.
    "specs/F-011-carga-incremental/requirements.md",
    "specs/F-011-carga-incremental/design.md",
    "specs/F-011-carga-incremental/tasks.md",
    "progress/medicion_F-011.md",
    "progress/impl_F-011.md",
)

#: Directorios de SQL de negocio que esta feature no puede tocar (R22).
SQL_INTOCABLE = (
    "etl_sigrid/infrastructure/postgres/sql/stg/",
    "etl_sigrid/infrastructure/postgres/sql/mart/",
)


def _ficheros_cambiados(base: str = "dev") -> list[str]:
    """Ficheros que la rama cambia respecto de `base`, o `None` si no hay git.

    Se hace con `git diff --name-only base...HEAD`, que es la misma pregunta
    que responde la puerta de cobertura del arnés. Si git no está disponible o
    la referencia base no existe, el test se salta en vez de ponerse rojo: un
    falso rojo aquí mandaría a alguien a buscar un cambio que no existe.
    """
    try:
        salida = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:  # pragma: no cover
        pytest.skip(f"git no disponible: {e}")

    if salida.returncode != 0:  # pragma: no cover
        pytest.skip(f"no se pudo comparar con '{base}': {salida.stderr.strip()}")

    return [linea.strip() for linea in salida.stdout.splitlines() if linea.strip()]


# ---------------------------------------------------------------------------
# R22 · F-011 no acota el build ni se acerca a la ventana de negocio
# ---------------------------------------------------------------------------


def test_f011_r22_el_sql_de_stg_y_mart_no_se_toca() -> None:
    """Ni una línea del SQL de negocio en esta rama.

    Es la barrera de F-025: acotar el build cambia qué datos ve Power BI y
    necesita decisión de Negocio (DA-1, sin decidir) y prueba de equivalencia.
    F-011 mide; no toca.
    """
    cambiados = [f.replace("\\", "/") for f in _ficheros_cambiados()]

    intrusos = [
        f for f in cambiados if any(f.startswith(d) for d in SQL_INTOCABLE)
    ]

    assert intrusos == [], (
        f"F-011 ha tocado SQL de negocio: {intrusos}. Acotar el build es F-025 "
        f"(specs/F-025-ventana-negocio-build/), y exige su prueba de "
        f"equivalencia antes de cambiar lo que ve Power BI."
    )


def test_f011_r22_tampoco_se_toca_el_troceado_de_f019() -> None:
    """`build_stg_step.py` y `domain/tramos.py` se quedan como están.

    El troceado por tramos es lo que impide repetir el incidente del disco del
    2026-08-09, y es la pieza sobre la que F-025 se apoyará. F-011 no la mueve.
    """
    cambiados = [f.replace("\\", "/") for f in _ficheros_cambiados()]

    for intocable in (
        "etl_sigrid/domain/tramos.py",
        "etl_sigrid/application/steps/build_stg_step.py",
        "etl_sigrid/domain/coherencia.py",
    ):
        assert intocable not in cambiados, (
            f"F-011 ha modificado {intocable}, que el diseño declara intocable "
            f"(design.md §4). Si hizo falta tocarlo, el diseño se torció."
        )


def test_f011_r22_sin_bloque_ventana_ni_perfil_ventana() -> None:
    """Nada de la ventana de negocio existe todavía: eso es F-025."""
    reglas = yaml.safe_load(
        (REPO / "config" / "business_rules.yaml").read_text(encoding="utf-8")
    )
    assert "ventana" not in (reglas or {}), (
        "config/business_rules.yaml tiene un bloque `ventana:`: es de F-025 y "
        "depende de DA-1, que sigue sin decidir."
    )

    assert "perfil-ventana" not in main.cli.commands, (
        "el comando `perfil-ventana` es de F-025, no de F-011"
    )

    # Y `fetch_peso_ventana` no está en ninguna parte del código.
    for fuente in (REPO / "etl_sigrid").rglob("*.py"):
        assert "fetch_peso_ventana" not in fuente.read_text(encoding="utf-8"), (
            f"{fuente} define o usa fetch_peso_ventana, que es de F-025"
        )


def test_f011_r22_la_spec_de_f025_existe_y_es_donde_vive_el_bloque_c() -> None:
    """El bloque C no se ha perdido: tiene casa, y esta feature la nombra."""
    f025 = REPO / "specs" / "F-025-ventana-negocio-build"

    assert f025.is_dir(), "specs/F-025-ventana-negocio-build/ no existe"
    for fichero in ("requirements.md", "design.md", "tasks.md"):
        assert (f025 / fichero).is_file(), f"falta {fichero} en la spec de F-025"


def test_f011_r22_los_comandos_nuevos_son_exactamente_tres() -> None:
    """Los tres de medición y ninguno más: el bloque B no ha empezado.

    Si algún día aparece aquí un comando de ingesta incremental sin que el
    humano haya firmado la puerta de R8, este test lo dice.
    """
    nuevos = {"perfil-carga", "bench-sigrid", "diagnostico-tiemod"}

    assert nuevos <= set(main.cli.commands)
    assert "ingesta-watermark" not in main.cli.commands
    # `ingest` no ha ganado todavía la opción del bloque B (R16, T16).
    assert "--solo-altas" not in {
        opcion.opts[0] for opcion in main.cli.commands["ingest"].params if opcion.opts
    }


# ---------------------------------------------------------------------------
# R24 · Ni un secreto en lo que añade la feature
# ---------------------------------------------------------------------------


def _es_falso_positivo(candidato: str) -> bool:
    """¿El candidato es un nombre de clase o un trozo de ruta, y no una clave?

    Dos falsos positivos más del barrido de F-005, de la misma familia que el
    de las rutas que arregló F-016. El patrón de base64 caza 24 caracteres
    seguidos de `[A-Za-z0-9+/]`, y en este árbol eso lo cumplen:

      * `SigridApiPageSizeTooLargeError` — 30 **letras** seguidas.
      * `incremental/requirements` — trozo de la ruta de la spec: una sola
        barra, y el filtro de F-016 exige dos.
      * `/c/Users/pgris/PycharmProjects/azure` — la ruta del comando que
        `requirements.md` deja para reproducir el recuento del diccionario:
        tres barras, pero con mayúsculas, y F-016 exige minúsculas.

    Los tres criterios son estrechos a propósito. Una clave generada de 24
    caracteres sin un solo dígito ni símbolo, o sin una sola mayúscula, o con
    dos barras dentro, es un suceso de probabilidad muy baja; un nombre de
    clase en CamelCase y una ruta del árbol son la norma en este repositorio.

    El afinado vive aquí y no en `buscar_secretos`, que es de F-005: esta
    feature no toca los tests de otra (la única excepción autorizada fue F-016).
    """
    if candidato.isalpha():
        return True
    if candidato.count("/") >= 2:
        return True
    return "/" in candidato and candidato == candidato.lower()


def test_f011_r24_el_afinado_del_barrido_no_deja_pasar_una_clave() -> None:
    """Control negativo del filtro de arriba: sin él, esto pasaría inadvertido.

    Es la lección de F-016: un afinado sin control negativo se ensancha solo,
    hasta que el barrido deja de cazar nada y nadie se entera.
    """
    assert _es_falso_positivo("SigridApiPageSizeTooLargeError") is True
    assert _es_falso_positivo("incremental/requirements") is True
    assert _es_falso_positivo("/c/Users/pgris/PycharmProjects/azure") is True

    # Una clave de verdad lleva mayúsculas y dígitos: no se filtra.
    for clave in (
        "aG9sYTEyMzQ1Njc4OTBhYmNkZWY=",
        "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5",
        "AbCd/efGh1234567890ijklmnop",
    ):
        assert _es_falso_positivo(clave) is False
        hallazgos = buscar_secretos(f"clave: {clave}")
        assert [h for h in hallazgos if not _es_falso_positivo(h)] != [], (
            f"el barrido afinado ya no caza {clave}"
        )


def test_f011_r24_sin_secretos_en_lo_nuevo() -> None:
    """Barrido de secretos sobre cada fichero que F-011 añade o cambia.

    Se reutiliza el barrido afinado de F-016 en vez de escribir otro: dos
    barridos distintos divergen, y el bueno es el que ya tiene control
    negativo (`test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta`).
    """
    revisados = 0
    for relativo in FICHEROS_DE_LA_FEATURE:
        ruta = REPO / relativo
        if not ruta.is_file():
            continue  # los informes se escriben al final de la feature
        revisados += 1
        hallazgos = [
            h
            for h in buscar_secretos(ruta.read_text(encoding="utf-8"))
            if not _es_falso_positivo(h)
        ]
        assert hallazgos == [], f"{relativo} parece contener un secreto: {hallazgos}"

    assert revisados >= 8, (
        "el barrido no encontró los ficheros de la feature: ¿se han movido?"
    )


def test_f011_r24_los_csv_de_medicion_no_se_versionan() -> None:
    """Las huellas y los bench son salida de una ejecución, no fuente.

    Mismo criterio que las huellas de F-019: caducan con cada carga y pueden
    llevar agregados de negocio. El `.gitignore` es lo que impide que un
    `git add .` de madrugada los suba.
    """
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")

    assert "huella_*.csv" in gitignore
