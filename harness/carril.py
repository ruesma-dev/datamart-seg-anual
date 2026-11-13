# harness/carril.py
"""Puerta de CARRIL: una feature no se sale de los límites de su nivel.

Un nivel de `harness/rigor.json` que declara `limites` promete un cambio
pequeño y sin riesgo; a cambio se le exige menos. Esta puerta comprueba esa
promesa contra el diff comprometido: ficheros, líneas y rutas sensibles.

Se activa por DATOS del nivel, no por su nombre: un `rigor.json` sin `limites`
deja la puerta en N/A sin una sola rama de compatibilidad.

Dos reglas que explican la forma de `main`:

- **Lo que no se puede medir no pasa.** Al revés que la cobertura, una base
  rezagada, una declaración rota o un diff incalculable son rojo: el carril
  rebaja la vigilancia, y hacerlo a ciegas sería peor que no tenerlo.
- **El arnés no reescribe `features.json`.** El rojo dice la salida (subir de
  nivel y volver a la PARADA 1); la ejecuta el líder.

`init.sh` decide por el código de salida (0, 1, otro) y solo imprime el texto.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from harness.alcance import (
    EjecutorGit,
    _existe,
    diagnosticar_base,
    git_en,
    rama_base_configurada,
    resolver_refs,
)
from harness.cobertura import rama_actual
from harness.rigor import (
    RUTA_FEATURES,
    RUTA_RIGOR,
    cargar_features,
    cargar_rigor,
    feature_de_rama,
    limites_nivel,
    nivel_de_feature,
)
from harness.rutas_sensibles import (
    ErrorDeclaracion,
    _casa,
    cargar_declaracion,
    rutas_tocadas,
)

ETIQUETA = "PUERTA CARRIL"
SALIDA_DEL_CARRIL = (
    "Salida: sube el nivel de la feature y vuelve a la PARADA 1; nunca edites "
    "los límites."
)


@dataclass(frozen=True)
class Medida:
    """Lo que toca la feature frente a su merge-base."""

    ficheros: tuple[str, ...]  # los que cuentan para los límites
    lineas: int
    tocados: tuple[str, ...]  # todos, para las rutas sensibles


def parsear_numstat(texto: str) -> list[tuple[str, int]]:
    """(ruta, añadidas + borradas) de cada entrada de `git diff --numstat -z`.

    Con `--no-renames` cada entrada son tres campos. El `-` de un binario vale 0.
    """
    entradas: list[tuple[str, int]] = []
    for entrada in texto.split("\0"):
        if not entrada:
            continue
        anadidas, borradas, ruta = entrada.split("\t", 2)
        entradas.append((ruta, sum(int(n) for n in (anadidas, borradas) if n != "-")))
    return entradas


def medir(ref_a: str, ref_b: str, no_cuentan: list[str], git: EjecutorGit) -> Medida:
    """Mide el diff comprometido entre dos referencias."""
    entradas = parsear_numstat(
        git(["diff", "--no-renames", "--numstat", "-z", ref_a, ref_b])
    )
    cuentan = [
        (ruta, lineas)
        for ruta, lineas in entradas
        if not any(_casa(ruta, patron) for patron in no_cuentan)
    ]
    return Medida(
        ficheros=tuple(ruta for ruta, _ in cuentan),
        lineas=sum(lineas for _, lineas in cuentan),
        tocados=tuple(ruta for ruta, _ in entradas),
    )


def excesos(medida: Medida, limites: dict) -> list[str]:
    """Una descripción por cada límite superado; igualarlo no es superarlo."""
    detalle: list[str] = []
    if len(medida.ficheros) > limites["ficheros"]:
        detalle.append(f"{len(medida.ficheros)} ficheros > tope {limites['ficheros']}")
    if medida.lineas > limites["lineas"]:
        detalle.append(f"{medida.lineas} líneas > tope {limites['lineas']}")
    return detalle


def _na(motivo: str) -> int:
    print(f"{ETIQUETA}: N/A ({motivo})")
    return 0


def _ko(motivo: str) -> int:
    print(f"{ETIQUETA}: {motivo}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Puerta de carril: 0 si cabe o no aplica, 1 si se sale, 2 sin configuración."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.carril",
        description="Comprueba que la feature cabe en los límites de su nivel.",
    )
    analizador.add_argument(
        "--base",
        default=None,
        help="Rama de integración (por defecto, RAMA_BASE de harness/init.sh)",
    )
    analizador.add_argument("--config", default=str(RUTA_RIGOR))
    analizador.add_argument("--features", default=str(RUTA_FEATURES))
    analizador.add_argument("--raiz", default=".")
    opciones = analizador.parse_args(argv)

    try:
        rigor = cargar_rigor(opciones.config)
        features = cargar_features(opciones.features)
    except ValueError as error:
        print(f"{ETIQUETA}: {error}", file=sys.stderr)
        return 2

    base = opciones.base or rama_base_configurada(opciones.raiz)
    rama = rama_actual(opciones.raiz)
    if not rama or rama in (base, "main", "master"):
        return _na(f"rama {rama or '(detached)'}: solo aplica en ramas de feature")

    feature = feature_de_rama(rama, features)
    if feature is None:
        return _na(f"la rama {rama} no corresponde a ninguna feature declarada")
    identificador = feature.get("id")
    if feature.get("status") == "done":
        return _na(f"{identificador} está cerrada")

    nivel = nivel_de_feature(feature, rigor)
    limites = limites_nivel(nivel, rigor)
    if limites is None:
        return _na(f"{identificador} es de nivel {nivel}: no declara límites")

    git = git_en(opciones.raiz)
    motivo = diagnosticar_base(base, rama, git=git)
    if motivo:
        return _ko(motivo)

    try:
        verificaciones = cargar_declaracion(raiz=opciones.raiz)
    except ErrorDeclaracion as error:
        return _ko(str(error))

    try:
        ref_a, ref_b, _ = resolver_refs(identificador or "", rama, base, git=git)
    except SystemExit as parada:
        return _ko(str(parada))

    # `ejecutar_git` devuelve "" al fallar: sin esto, un diff que no se pudo
    # calcular se leería como un diff vacío, y pasaría.
    if not (_existe(ref_a, git) and _existe(ref_b, git)):
        return _ko(f"no se pudo calcular el diff {ref_a}..{ref_b}")

    medida = medir(ref_a, ref_b, limites.get("no_cuentan", []), git)
    detalle = excesos(medida, limites)
    for verificacion in verificaciones:
        for coincidencia in rutas_tocadas(verificacion, list(medida.tocados)):
            detalle.append(
                f"ruta sensible {coincidencia.fichero} ({coincidencia.motivo})"
            )

    if detalle:
        lineas = "\n".join(f"    {linea}" for linea in [*detalle, SALIDA_DEL_CARRIL])
        return _ko(f"{identificador} (nivel {nivel}) se sale del carril:\n{lineas}")

    total = sum(len(verificacion.rutas) for verificacion in verificaciones)
    declaradas = (
        f"{total} rutas sensibles declaradas"
        if verificaciones
        else "sin rutas sensibles declaradas"
    )
    print(
        f"{ETIQUETA}: {identificador} dentro de los límites "
        f"({len(medida.ficheros)}/{limites['ficheros']} ficheros, "
        f"{medida.lineas}/{limites['lineas']} líneas; {declaradas})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
