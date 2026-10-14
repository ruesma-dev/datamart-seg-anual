# -*- coding: utf-8 -*-
"""Proyecta `harness/features.json` en un `BACKLOG.md` legible.

`features.json` es la fuente de verdad del backlog, pero es JSON: nadie lo
lee de un vistazo y el humano acaba pidiendo por chat "dame la tabla de
features". Este generador escribe esa tabla en el repositorio, para que esté
siempre disponible sin preguntar y para que el propio historial de git
enseñe cómo evolucionó el backlog.

REGLAS DE DISEÑO (importan si lo tocas):

- `BACKLOG.md` es **generado**: nunca se edita a mano. Lo que se edita es
  `features.json`.
- La salida es **función pura de `features.json`**: no lleva fecha de
  generación ni mira el árbol de trabajo. Así el fichero solo cambia cuando
  cambia el backlog de verdad, y arrancar el portero no ensucia `git status`.
- No inventa estados ni fases: lo que no está en `features.json`, no sale.

Uso:

    python harness/backlog.py              # regenera BACKLOG.md
    python harness/backlog.py --comprobar  # no escribe; código 1 si difiere

`harness/init.sh` lo llama en cada arranque y avisa si el fichero cambió.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES = os.path.join(RAIZ, "harness", "features.json")
SALIDA = os.path.join(RAIZ, "BACKLOG.md")

_ETIQUETA_ESTADO = {
    "blocked": "bloqueada",
    "in_progress": "en curso",
    "spec_ready": "spec lista",
    "pending": "pendiente",
    "done": "terminada",
}


def _celda(texto: object) -> str:
    """Escapa lo que rompería una tabla Markdown."""
    if texto is None:
        return ""
    return str(texto).replace("|", "\\|").replace("\n", " ").strip()


def _clave_orden(feature: dict) -> tuple:
    prioridad = feature.get("priority")
    if not isinstance(prioridad, int):
        prioridad = 999
    return (prioridad, feature.get("id", ""))


# Una sección por estado, en el orden en que se leen: lo que se está
# haciendo, lo que está listo para empezar, lo que espera algo, el backlog y
# lo terminado. Cada sección va ordenada por prioridad.
_SECCIONES = (
    ("in_progress", "En curso", "_Ninguna feature en curso._"),
    ("spec_ready", "Spec lista", "_Ninguna feature con la spec lista._"),
    ("blocked", "Bloqueadas", "_Ninguna feature bloqueada._"),
    ("pending", "Backlog", "_El backlog está vacío._"),
    ("done", "Terminadas", "_Todavía no hay features terminadas._"),
)


def _tabla(features: list[dict], con_estado: bool = False, con_rama: bool = True) -> list[str]:
    columnas = ["#", "Feature", "Prioridad"]
    if con_estado:
        columnas.append("Estado")
    columnas.append("Rigor")
    if con_rama:
        columnas.append("Rama")
    filas = [
        "| %s |" % " | ".join(columnas),
        "|%s" % ("---|" * len(columnas)),
    ]
    for f in features:
        celdas = [_celda(f.get("id")), _celda(f.get("title")), _celda(f.get("priority"))]
        if con_estado:
            celdas.append(_ETIQUETA_ESTADO.get(f.get("status"), _celda(f.get("status"))))
        celdas.append(_celda(f.get("rigor")))
        if con_rama:
            celdas.append("`%s`" % _celda(f["branch"]) if f.get("branch") else "")
        filas.append("| %s |" % " | ".join(celdas))
    return filas


def construir(datos: dict) -> str:
    features = datos.get("features", [])
    # Una tabla por estado, cada una por PRIORIDAD, que es como las lee el
    # humano. El orden entre estados para elegir la siguiente tarea
    # (blocked > in_progress > spec_ready > pending) lo aplica el líder, no
    # este fichero.
    por_estado = {
        estado: sorted(
            (f for f in features if f.get("status") == estado), key=_clave_orden
        )
        for estado, _, _ in _SECCIONES
    }
    conocidos = {estado for estado, _, _ in _SECCIONES}
    # Un estado que no está en la lista no se pierde: sale en su propia tabla.
    otros = sorted(
        (f for f in features if f.get("status") not in conocidos), key=_clave_orden
    )
    hechas = por_estado["done"]
    abiertas = sorted(
        (f for f in features if f.get("status") != "done"), key=_clave_orden
    )

    lineas: list[str] = [
        "<!-- BACKLOG.md -->",
        "# Backlog",
        "",
        "**Fichero generado por `harness/backlog.py` a partir de "
        "`harness/features.json`. No lo edites a mano**: edita el JSON y "
        "vuelve a generarlo (lo hace solo `bash harness/init.sh`).",
        "",
        "Resumen: **%d features**, %d abiertas (%d en curso, %d con la spec "
        "lista, %d bloqueadas y %d en backlog) y %d terminadas."
        % (
            len(features),
            len(abiertas),
            len(por_estado["in_progress"]),
            len(por_estado["spec_ready"]),
            len(por_estado["blocked"]),
            len(por_estado["pending"]),
            len(hechas),
        ),
        "",
    ]

    for estado, titulo, vacio in _SECCIONES:
        lineas += ["## %s" % titulo, ""]
        grupo = por_estado[estado]
        if grupo:
            lineas += _tabla(grupo, con_rama=estado != "done")
        else:
            lineas.append(vacio)
        lineas.append("")

    if otros:
        lineas += ["## Otros estados", ""]
        lineas += _tabla(otros, con_estado=True)
        lineas.append("")

    lineas += ["## Detalle", ""]
    for f in abiertas + hechas:
        lineas.append("### %s · %s" % (_celda(f.get("id")), _celda(f.get("title"))))
        lineas.append("")
        meta = [
            "estado **%s**" % _ETIQUETA_ESTADO.get(f.get("status"), f.get("status")),
        ]
        if f.get("priority") is not None:
            meta.append("prioridad %s" % f["priority"])
        if f.get("rigor"):
            meta.append("rigor `%s`" % f["rigor"])
        if f.get("sdd") is not None:
            meta.append("SDD %s" % ("sí" if f["sdd"] else "no"))
        if f.get("branch"):
            meta.append("rama `%s`" % f["branch"])
        lineas.append(" · ".join(meta))
        lineas.append("")
        descripcion = (f.get("description") or "").strip()
        lineas.append(descripcion if descripcion else "_Sin descripción._")
        lineas.append("")

    return "\n".join(lineas).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera BACKLOG.md desde harness/features.json."
    )
    parser.add_argument(
        "--comprobar",
        action="store_true",
        help="no escribe; devuelve 1 si BACKLOG.md no está al día",
    )
    args = parser.parse_args(argv)

    try:
        with io.open(FEATURES, encoding="utf-8") as fh:
            datos = json.load(fh)
    except FileNotFoundError:
        print("harness/features.json no existe: nada que generar", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print("harness/features.json inválido: %s" % exc, file=sys.stderr)
        return 1

    nuevo = construir(datos)
    actual = None
    if os.path.exists(SALIDA):
        with io.open(SALIDA, encoding="utf-8") as fh:
            actual = fh.read()

    if actual == nuevo:
        return 0

    if args.comprobar:
        print("BACKLOG.md no está al día (regenera con: python harness/backlog.py)")
        return 1

    with io.open(SALIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(nuevo)
    print("BACKLOG.md regenerado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
