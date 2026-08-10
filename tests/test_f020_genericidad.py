# tests/test_f020_genericidad.py
"""F-020 · Las herramientas del arnés son portables tal cual (R17).

Lo que esta feature toca es arnés genérico: se copia a `arnes-base` y de ahí a
cualquier repositorio. Si se cuela el nombre de un sistema, de una capa de
datos o de una aplicación concreta, deja de ser portable y el siguiente que lo
instale se encontrará con vocabulario que no es suyo.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HARNESS = RAIZ / "harness"

#: Herramientas que esta feature crea o modifica, y que viajan a `arnes-base`.
HERRAMIENTAS = ("servicios.py", "alcance.py", "cobertura.py", "mutacion.py")

#: Vocabulario que NO puede aparecer: sistemas de origen, capas de datos de
#: este repositorio, proveedores de nube y nombres de las aplicaciones del
#: ecosistema.
PROHIBIDOS = (
    "sigrid",
    "datamart",
    "etl",
    "stg",
    "mart",
    "cierre",
    "retenciones",
    "azure",
    "blob",
    "albaranes",
    "partes",
    "portal",
    "remesas",
    "ruesma",
)

PATRON = re.compile(r"\b(" + "|".join(PROHIBIDOS) + r")\b", re.IGNORECASE)


def menciones(texto: str) -> list[str]:
    return [
        f"{numero}: {linea.strip()}"
        for numero, linea in enumerate(texto.splitlines(), start=1)
        if PATRON.search(linea)
    ]


def test_f020_r17_herramientas_sin_menciones_especificas() -> None:
    for nombre in HERRAMIENTAS:
        texto = (HARNESS / nombre).read_text(encoding="utf-8")
        assert not menciones(texto), (nombre, menciones(texto))


def test_f020_r17_la_seccion_multiservicio_de_init_es_generica() -> None:
    # Del resto de `init.sh` no se dice nada: es el fichero que cada proyecto
    # adapta (aquí, por ejemplo, la lista de rutas que compila).
    from tests.test_f020_init_multiservicio import seccion_multiservicio

    assert not menciones(seccion_multiservicio())


def test_f020_r17_las_herramientas_no_dependen_del_codigo_del_proyecto() -> None:
    """Solo importan biblioteca estándar y el propio paquete `harness`."""
    for nombre in HERRAMIENTAS:
        texto = (HARNESS / nombre).read_text(encoding="utf-8")
        importados = re.findall(r"^(?:from|import) ([\w.]+)", texto, flags=re.MULTILINE)
        externos = [
            modulo
            for modulo in importados
            if not modulo.startswith("harness")
            and modulo
            not in {
                "__future__",
                "argparse",
                "ast",
                "collections.abc",
                "dataclasses",
                "datetime",
                "importlib.util",
                "json",
                "pathlib",
                "random",
                "re",
                "subprocess",
                "sys",
                "time",
            }
        ]
        assert not externos, (nombre, externos)


def test_f020_r17_este_repositorio_no_declara_servicios_ni_los_necesita() -> None:
    """La mejora se recibe sin configurar nada: la ausencia ES la configuración."""
    assert not (HARNESS / "servicios.json").exists()
