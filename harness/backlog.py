# harness/backlog.py
"""Proyecta `harness/features.json` en un `BACKLOG.md` legible: el tablero.

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
- Un tablero de siete columnas (`_COLUMNAS`), de arriba abajo: Review
  (`in_review` y `human_review` juntas), Blocked, In progress, Spec aprobada,
  To do, Backlog y Done: lo más avanzado arriba, salvo Done, que sigue abajo
  (F-070, humano 2026-11-12). Entre todas cubren `estados.ESTADOS` sin
  repetir ninguno (lo vigila un test). Las abiertas, por prioridad. Las
  terminadas, por `fecha_cierre` (AAAA-MM-DD, opcional) de la más nueva a la
  más vieja; las que no la tienen van al final, «sin fecha», por prioridad y
  luego por id.
- «La tiene» (In progress y Review) sale SOLO del estado (implementer,
  reviewer o humano): ningún campo de `features.json` la alimenta, así que no
  puede quedarse desfasada.
- Una fecha (`fecha_cierre`, `spec_aprobada`, `ok_humano`) mal formada o que
  no es una fecha real es un error que nombra la feature y el campo: no se
  escribe un BACKLOG.md engañoso.

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
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES = os.path.join(RAIZ, "harness", "features.json")
SALIDA = os.path.join(RAIZ, "BACKLOG.md")

# init.sh lo ejecuta como script (`python harness/backlog.py`), no con -m: sin
# esto, `harness.estados` no se encontraría.
if not __package__:  # pragma: no cover - solo al ejecutarlo como script
    sys.path.insert(0, RAIZ)

from harness.estados import CAMPOS_FECHA, ESTADOS, QUIEN_LA_TIENE, fecha

_ETIQUETA_ESTADO = {
    "blocked": "bloqueada",
    "pending": "pendiente",
    "todo": "to do (comprometida)",
    "spec_ready": "spec lista",
    "in_progress": "en curso",
    "in_review": "en QA / revisión",
    "human_review": "en revisión humana",
    "done": "terminada",
}

# Las columnas del tablero, de arriba abajo: (título, estados que recoge,
# texto si está vacía). Lo más avanzado arriba, para ver primero lo que espera
# a alguien; Done sigue abajo porque solo crece (F-070, humano 2026-11-12).
# Blocked va junto a In progress porque casi todo bloqueo nace trabajando;
# Review junta lo que espera al reviewer y lo que espera al humano, y «La
# tiene» las distingue. Que el líder atienda antes las bloqueadas es su orden
# de prioridad (leader.md), no el de este fichero.
_COLUMNAS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Review", ("in_review", "human_review"), "_Nada esperando revisión._"),
    ("Blocked", ("blocked",), "_Ninguna feature bloqueada._"),
    ("In progress", ("in_progress",), "_Ninguna feature en implementación._"),
    ("Spec aprobada", ("spec_ready",), "_Ninguna feature con la spec lista._"),
    ("To do", ("todo",), "_Nada comprometido._"),
    ("Backlog", ("pending",), "_El backlog está vacío._"),
    ("Done", ("done",), "_Todavía no hay features terminadas._"),
)

# Columnas con «La tiene» (y rama): las que alguien está trabajando.
_CON_LA_TIENE = ("In progress", "Review")

_SIN_FECHA = "sin fecha"
_SPEC_PENDIENTE = "pendiente de tu aprobación"
_OK_SIN_ANOTAR = "sin anotar"


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


def _fecha_o(feature: dict, campo: str, si_falta: str) -> str:
    valor = fecha(feature, campo)
    return valor.isoformat() if valor else si_falta


def _clave_cierre(feature: dict) -> tuple:
    """Terminadas: con fecha, de la más nueva a la más vieja; sin fecha, al final."""
    cierre = fecha(feature, "fecha_cierre")
    if cierre is None:
        return (1, 0) + _clave_orden(feature)
    return (0, -cierre.toordinal()) + _clave_orden(feature)


def _express_por_mes(features: list[dict]) -> str | None:
    """`Express cerradas por mes: 2026-10: 3 · 2026-11: 1`, o `None` si no hay.

    Va por el NOMBRE del nivel porque `construir` es pura y no lee `rigor.json`:
    acoplarla por una línea informativa no compensa. Sin reloj: el tablero no
    cambia solo al cambiar de mes.
    """
    meses = Counter(
        f"{cierre.year:04d}-{cierre.month:02d}"
        for f in features
        if f.get("status") == "done" and f.get("rigor") == "express"
        and (cierre := fecha(f, "fecha_cierre")) is not None
    )
    if not meses:
        return None
    cifras = " · ".join(f"{mes}: {meses[mes]}" for mes in sorted(meses))
    return f"Express cerradas por mes: {cifras}"


def _columnas_extra(titulo: str) -> list[tuple[str, object]]:
    """Columnas propias de la columna `titulo` del tablero, tras «Feature»."""
    if titulo in _CON_LA_TIENE:
        return [("La tiene", lambda f: QUIEN_LA_TIENE[f["status"]])]
    if titulo == "Spec aprobada":
        return [("Spec aprobada",
                 lambda f: _fecha_o(f, "spec_aprobada", _SPEC_PENDIENTE))]
    if titulo == "Done":
        return [
            ("Cierre", lambda f: _fecha_o(f, "fecha_cierre", _SIN_FECHA)),
            ("OK humano", lambda f: _fecha_o(f, "ok_humano", _OK_SIN_ANOTAR)),
        ]
    return []


def _tabla(
    features: list[dict],
    extra: list[tuple[str, object]] | None = None,
    con_estado: bool = False,
    con_rama: bool = True,
) -> list[str]:
    extra = extra or []
    columnas = ["#", "Feature"] + [nombre for nombre, _ in extra]
    columnas.append("Prioridad")
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
        celdas = [_celda(f.get("id")), _celda(f.get("title"))]
        celdas += [_celda(valor(f)) for _, valor in extra]
        celdas.append(_celda(f.get("priority")))
        if con_estado:
            celdas.append(_ETIQUETA_ESTADO.get(f.get("status"), _celda(f.get("status"))))
        celdas.append(_celda(f.get("rigor")))
        if con_rama:
            celdas.append("`%s`" % _celda(f["branch"]) if f.get("branch") else "")
        filas.append("| %s |" % " | ".join(celdas))
    return filas


def construir(datos: dict) -> str:
    """BACKLOG.md a partir de features.json. Función pura.

    Lanza ValueError si alguna fecha (`fecha_cierre`, `spec_aprobada`,
    `ok_humano`) está mal formada.
    """
    features = datos.get("features", [])
    for f in features:
        for campo in CAMPOS_FECHA:
            fecha(f, campo)
    # Una tabla por columna, las abiertas por PRIORIDAD, que es como las lee
    # el humano, y las terminadas por fecha de cierre. El orden entre estados
    # para elegir la siguiente tarea (blocked > human_review > in_review >
    # in_progress > spec_ready > todo) lo aplica el líder, no este fichero.
    por_columna = {
        titulo: sorted(
            (f for f in features if f.get("status") in de_la_columna),
            key=_clave_cierre if titulo == "Done" else _clave_orden,
        )
        for titulo, de_la_columna, _ in _COLUMNAS
    }
    # Un estado que no está en la lista no se pierde: sale en su propia tabla.
    otros = sorted(
        (f for f in features if f.get("status") not in ESTADOS), key=_clave_orden
    )
    hechas = por_columna["Done"]
    abiertas = sorted(
        (f for f in features if f.get("status") != "done"), key=_clave_orden
    )

    cifras = [f"{len(por_columna[titulo])} en {titulo}" for titulo, _, _ in _COLUMNAS]
    resumen = (
        f"Resumen: **{len(features)} features**, {len(abiertas)} abiertas y "
        f"{len(hechas)} terminadas. Por columna: {', '.join(cifras[:-1])} y "
        f"{cifras[-1]}."
    )
    if otros:
        resumen += f" Otros estados: {len(otros)}."

    lineas: list[str] = [
        "<!-- BACKLOG.md -->",
        "# Backlog",
        "",
        "**Fichero generado por `harness/backlog.py` a partir de "
        "`harness/features.json`. No lo edites a mano**: edita el JSON y "
        "vuelve a generarlo (lo hace solo `bash harness/init.sh`).",
        "",
        resumen,
        "",
    ]

    for titulo, _, vacio in _COLUMNAS:
        lineas += [f"## {titulo}", ""]
        grupo = por_columna[titulo]
        if grupo:
            lineas += _tabla(grupo, extra=_columnas_extra(titulo),
                             con_rama=titulo != "Done")
        else:
            lineas.append(vacio)
        lineas.append("")
        if titulo == "Done" and (express := _express_por_mes(features)):
            lineas += [express, ""]

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
        if f.get("status") == "done":
            cierre = fecha(f, "fecha_cierre")
            meta.append("cerrada el %s" % cierre.isoformat() if cierre
                        else "sin fecha de cierre")
        aprobada = fecha(f, "spec_aprobada")
        if aprobada:
            meta.append(f"spec aprobada el {aprobada.isoformat()}")
        ok_humano = fecha(f, "ok_humano")
        if ok_humano:
            meta.append(f"OK del humano el {ok_humano.isoformat()}")
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

    try:
        nuevo = construir(datos)
    except ValueError as exc:
        # Sin BACKLOG.md nuevo: uno con el orden mal calculado engañaría más
        # que el anterior. init.sh enseña este mensaje en su aviso.
        print("harness/features.json: %s" % exc, file=sys.stderr)
        return 1
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
