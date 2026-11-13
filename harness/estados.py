# harness/estados.py
"""Fuente única de los estados del flujo de una feature.

Estados, en orden de flujo: `pending` -> `todo` -> `spec_ready` ->
`in_progress` -> `in_review` -> `human_review` -> `done`; y `blocked`, fuera
del flujo.

`todo` es **comprometida**: el humano ha decidido que se haga. Nada sale de
`pending` sin pasar por `todo` (norma de `leader.md`, no puerta), y `todo` NO
es activa: se pueden comprometer varias a la vez (una fase entera del plan).

**Activos** son los tres en que alguien está trabajando la feature o
esperando el OK del humano. Como mucho puede haber UNA feature activa (lo
valida `harness/init.sh`): mientras el humano no da el OK, no arranca otra
implementación.

Los validadores de `init.sh` repiten la lista (node y jq no pueden importar
este módulo, y la sección 3 tiene que funcionar sin Python). Que coincidan
lo vigila la suite (`tests/test_init_sh_estados.py`).

Aquí NO se validan transiciones (de qué estado se viene): solo valores y la
coherencia entre el estado y los campos de fecha de la feature de la rama.
La regla de transiciones vive en `.claude/agents/leader.md`.

Uso:

    python -m harness.estados --avisos [--rama R] [--features RUTA]

Imprime un aviso por línea y sale siempre con 0: son avisos, no puertas.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

#: Los ocho estados, en orden de flujo; `blocked` al final, fuera del flujo.
ESTADOS: tuple[str, ...] = (
    "pending",
    "todo",
    "spec_ready",
    "in_progress",
    "in_review",
    "human_review",
    "done",
    "blocked",
)

#: Los estados que cuentan para «máximo una feature activa».
ACTIVOS: frozenset[str] = frozenset({"in_progress", "in_review", "human_review"})

#: Quién tiene la feature en cada estado activo. Sale SOLO del estado: no hay
#: un campo `agente` en `features.json` que pueda quedarse desfasado.
QUIEN_LA_TIENE: dict[str, str] = {
    "in_progress": "implementer",
    "in_review": "reviewer",
    "human_review": "humano",
}

#: Campos opcionales de fecha de una feature, todos con formato AAAA-MM-DD.
CAMPOS_FECHA: tuple[str, ...] = ("fecha_cierre", "spec_aprobada", "ok_humano")

#: AAAA-MM-DD con dígitos ASCII. `date.fromisoformat` sola no basta: desde
#: Python 3.11 acepta también `20260927` o `2026-W39-6`.
_FORMATO_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

RUTA_FEATURES = Path("harness/features.json")


def fecha(feature: dict, campo: str) -> datetime.date | None:
    """El valor de `campo` como fecha, o None si la feature no lo declara.

    Lanza ValueError, nombrando la feature y el campo, si no es una fecha
    real con formato AAAA-MM-DD.
    """
    valor = feature.get(campo)
    if valor is None:
        return None
    if isinstance(valor, str) and _FORMATO_FECHA.fullmatch(valor):
        try:
            return datetime.date.fromisoformat(valor)
        except ValueError:
            pass
    raise ValueError(
        f"{feature.get('id', '?')}: {campo} inválida ({valor!r}); tiene que "
        "ser una fecha real con formato AAAA-MM-DD"
    )


def feature_activa(features: list[dict]) -> dict | None:
    """La primera feature activa, por orden del fichero; None si no hay."""
    for feature in features:
        if feature.get("status") in ACTIVOS:
            return feature
    return None


def avisos(features: list[dict], rama: str) -> list[str]:
    """Incoherencias entre el estado y las fechas de la feature de la rama.

    Solo mira la feature que resuelve `rigor.feature_de_rama` (la que declara
    `rama`; si ninguna, la activa). Las `done` de otras ramas no avisan,
    lleven o no `ok_humano`: es la amnistía de lo cerrado antes de que
    existiera el campo, igual que la puerta de tamaño.
    """
    # Dentro de la función: `rigor` importa de este módulo.
    from harness.rigor import feature_de_rama

    ficha = feature_de_rama(rama, features)
    if ficha is None:
        return []
    fid = ficha.get("id", "?")
    estado = ficha.get("status")
    lineas: list[str] = []
    if estado == "done" and not ficha.get("ok_humano"):
        lineas.append(
            f"{fid} está done sin ok_humano: anota en harness/features.json "
            "el día en que el humano dio el OK al resumen (AAAA-MM-DD)"
        )
    implementandose = estado in ACTIVOS or estado == "done"
    if ficha.get("sdd") is True and implementandose and not ficha.get("spec_aprobada"):
        lineas.append(
            f"{fid} tiene sdd: true y estado {estado} sin spec_aprobada: anota "
            "en harness/features.json el día en que el humano aprobó la spec"
        )
    return lineas


def main(argv: list[str] | None = None) -> int:
    """`python -m harness.estados --avisos`: un aviso por línea, código 0."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.estados",
        description="Estados del flujo: avisos de la feature de la rama.",
    )
    analizador.add_argument("--avisos", action="store_true")
    analizador.add_argument("--rama", default=None)
    analizador.add_argument("--features", default=str(RUTA_FEATURES))
    opciones = analizador.parse_args(argv)

    if not opciones.avisos:
        analizador.print_usage(sys.stderr)
        return 2

    from harness import alcance
    from harness.rigor import cargar_features

    rama = opciones.rama
    if rama is None:
        rama = alcance.ejecutar_git(["branch", "--show-current"]).strip()
    try:
        features = cargar_features(opciones.features)
    except ValueError as error:
        # La sección 3 de init.sh ya pone el fichero roto en rojo; aquí basta
        # con no callar.
        print(f"no se pueden calcular los avisos de estado: {error}")
        return 0
    for linea in avisos(features, rama):
        print(linea)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
