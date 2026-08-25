# tests/test_f020_genericidad.py
"""F-020 · Las herramientas del arnés son portables tal cual (R17).

Lo que esta feature toca es arnés genérico: se copia a `arnes-base` y de ahí a
cualquier repositorio. Si se cuela el nombre de un sistema, de una capa de
datos o de una aplicación concreta, deja de ser portable y el siguiente que lo
instale se encontrará con vocabulario que no es suyo.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from tests.test_f015_rigor import codigo_ejecutable

RAIZ = Path(__file__).resolve().parents[1]
HARNESS = RAIZ / "harness"

#: Herramientas del arnés que viajan a `arnes-base` tal cual. Las tres últimas
#: llegaron con la actualización a la v1.5.0 (mutación en paralelo, BACKLOG.md
#: generado y puerta de rutas sensibles) y se vigilan igual que las demás.
HERRAMIENTAS = (
    "servicios.py",
    "alcance.py",
    "cobertura.py",
    "mutacion.py",
    "mutacion_paralela.py",
    "backlog.py",
    "rutas_sensibles.py",
)

#: Vocabulario que NO puede aparecer: sistemas de origen, capas de datos de
#: este repositorio, proveedores de nube y nombres de las aplicaciones del
#: ecosistema.
PROHIBIDOS = (
    "sigrid",
    "datamart",
    "etl",
    "stg",
    "mart",
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

#: `cierre` sale de la lista de arriba y entra aquí cualificado: el arnés usa la
#: palabra en castellano llano («la línea base de cierre EXPIRÓ») y el esquema de
#: este repositorio se cita `cierre.algo`. Mismo criterio que R19.
PATRON_CUALIFICADO = re.compile(r"cierre\.\w", re.IGNORECASE)


def menciones(texto: str) -> list[str]:
    return [
        f"{numero}: {linea.strip()}"
        for numero, linea in enumerate(texto.splitlines(), start=1)
        if PATRON.search(linea) or PATRON_CUALIFICADO.search(linea)
    ]


def sin_comentarios_shell(texto: str) -> str:
    """El shell sin sus líneas de comentario: solo lo que ejecuta."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("#")
    )


def test_f020_r17_herramientas_sin_menciones_especificas() -> None:
    """El barrido mira el CÓDIGO, no la prosa (decisión del humano, 2026-08-25).

    Desde la 1.6.0 el arnés documenta en sus docstrings de dónde salió cada
    mejora («esto nació en `albaranes` F-038»), y `mutacion_paralela.py` cita a
    este mismo repositorio como su origen. Nada de eso lo hace menos portable:
    lo que ata es un `import`, una ruta o un literal usado en la lógica, y eso
    se sigue vigilando aquí y en `test_f015_rigor.py`.
    """
    for nombre in HERRAMIENTAS:
        texto = codigo_ejecutable((HARNESS / nombre).read_text(encoding="utf-8"))
        assert not menciones(texto), (nombre, menciones(texto))


def test_f020_r17_la_seccion_multiservicio_de_init_es_generica() -> None:
    # Del resto de `init.sh` no se dice nada: es el fichero que cada proyecto
    # adapta (aquí, por ejemplo, la lista de rutas que compila).
    from tests.test_f020_init_multiservicio import seccion_multiservicio

    assert not menciones(sin_comentarios_shell(seccion_multiservicio()))


def modulos_importados(fuente: str) -> list[str]:
    """Los módulos que importa una fuente, por su raíz (`os.path` -> `os`)."""
    raices = []
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            raices += [alias.name.split(".")[0] for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0:
            raices.append((nodo.module or "").split(".")[0])
    return raices


def test_f020_r17_las_herramientas_no_dependen_del_codigo_del_proyecto() -> None:
    """Solo importan biblioteca estándar y el propio paquete `harness`.

    Se pregunta a `sys.stdlib_module_names` en vez de mantener a mano una lista
    blanca de módulos permitidos. La lista envejecía con cada versión del arnés
    —la 1.7.x trajo `math`, `signal` y `contextlib`, los tres estándar— y cada
    envejecimiento se leía como una violación de R17 que no lo era. Preguntar
    por la biblioteca estándar de verdad es además MÁS estricto: caza cualquier
    dependencia de terceros, incluidas las que nadie pensó en prohibir.
    """
    for nombre in HERRAMIENTAS:
        texto = (HARNESS / nombre).read_text(encoding="utf-8")
        externos = [
            modulo
            for modulo in modulos_importados(texto)
            if modulo != "harness" and modulo not in sys.stdlib_module_names
        ]
        assert not externos, (nombre, externos)


def test_f020_r17_este_repositorio_no_declara_servicios_ni_los_necesita() -> None:
    """La mejora se recibe sin configurar nada: la ausencia ES la configuración."""
    assert not (HARNESS / "servicios.json").exists()
