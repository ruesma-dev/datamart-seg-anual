# tests/test_f006_supervivientes_mensajes.py
"""
Los cinco supervivientes de MENSAJES de la campaña de mutación de F-006.

Los cinco están en `_detalle_yaml`, la función que convierte un
`yaml.ScannerError` crudo en algo que le diga a una persona qué abrir y dónde
mirar. Sobrevivieron porque **nadie comprobaba el contenido del mensaje**: los
tests existentes se conformaban con que se levantara `DiccionarioIlegible`.

Un mensaje de diagnóstico no es decoración, y este menos: es lo que aparece
cuando el ETL se cae de madrugada y el diccionario entero deja de publicarse.
Los dos defectos que los mutantes destapan:

* **`getattr(exc, "problem", None) or "YAML mal formado"` → `and`.** Con `and`
  se tira el detalle real del parser y **todos** los errores de YAML pasan a
  decir lo mismo. La diferencia entre «mapping values are not allowed here» y
  un texto genérico es la diferencia entre arreglarlo en un minuto y abrir el
  fichero a ciegas.
* **`marca.line + 1` y `marca.column + 1` movidos** (`-1`, `+2` en cada uno).
  PyYAML cuenta desde 0 y las personas y los editores desde 1: ese `+1` es toda
  la traducción. Un mensaje que señala la línea equivocada es **peor que no
  señalar ninguna**, porque manda a mirar código sano; con un fichero de
  ochocientas líneas eso es una tarde.

Cómo se fijan los dos números sin que el test se limite a repetir la fórmula:
se rompe un YAML en una línea y una columna **conocidas**, se extraen del
mensaje los dos números y se hace el **viaje de vuelta** —restarles uno e
indexar el texto original— para comprobar que caen exactamente sobre el
carácter que el parser no supo leer. Eso es lo que significa «1-based», y es lo
que ninguna de las cuatro mutaciones puede seguir cumpliendo.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
    DiccionarioIlegible,
    _detalle_yaml,
    cargar_diccionario,
)

#: `el YAML no parsea en la linea N, columna M: <problema>`
_POSICION = re.compile(r"linea (\d+), columna (\d+)")


# Dos YAML rotos, cada uno en un sitio distinto y con un carácter culpable
# inequívoco. Se usan dos y no uno para que ningún número pueda coincidir por
# casualidad con el del otro caso.
#
#   (identificador, texto, línea 1-based, columna 1-based, carácter culpable)
YAML_ROTOS = [
    pytest.param(
        "version: 1\nbase: sigrid_dm\nclave: valor: otro\n",
        3,
        13,
        ":",
        "mapping values are not allowed here",
        id="segundos_dos_puntos_en_la_linea_3",
    ),
    pytest.param(
        "version: 1\n"
        "base: sigrid_dm\n"
        "titulo: uno\n"
        "esquemas:\n"
        "  mart: [a, b\n"
        "  stg: c\n",
        6,
        6,
        ":",
        "expected ',' or ']'",
        id="lista_sin_cerrar_que_estalla_en_la_6",
    ),
]


def _detalle_de(tmp_path: pathlib.Path, texto: str) -> str:
    """Rompe el diccionario con `texto` y devuelve el detalle del error."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "00_global.yaml").write_text(texto, encoding="utf-8")

    with pytest.raises(DiccionarioIlegible) as capturado:
        cargar_diccionario(tmp_path)

    (error,) = capturado.value.errores
    assert error.fichero == "00_global.yaml", "hay que decir qué fichero abrir"
    return error.detalle


@pytest.mark.parametrize(
    ("texto", "linea_esperada", "columna_esperada", "culpable", "_problema"),
    YAML_ROTOS,
)
def test_f006_r1_el_error_de_yaml_senala_la_linea_y_la_columna_del_editor(
    tmp_path: pathlib.Path,
    texto: str,
    linea_esperada: int,
    columna_esperada: int,
    culpable: str,
    _problema: str,
) -> None:
    """Los dos números tienen que caer sobre el carácter que el parser rechazó.

    No basta con que el mensaje traiga «una línea»: tiene que traer LA línea,
    contada como la cuenta el editor en el que se va a abrir el fichero. Así que
    el test no compara la fórmula, hace el viaje de vuelta: coge los números del
    mensaje, les resta uno y comprueba que ahí está el carácter culpable.

    Con `line - 1` o `line + 2` el viaje de vuelta aterriza en otra línea del
    fichero —una línea sana, que es lo peligroso—; con `column ± n` aterriza en
    otro carácter de la buena. Ninguna de las cuatro sobrevive a esto.
    """
    detalle = _detalle_de(tmp_path, texto)

    posicion = _POSICION.search(detalle)
    assert posicion is not None, (
        f"el mensaje tiene que decir en qué línea y columna está el problema, y "
        f"dice: {detalle!r}"
    )
    linea, columna = int(posicion.group(1)), int(posicion.group(2))

    assert (linea, columna) == (linea_esperada, columna_esperada)

    lineas = texto.splitlines()
    assert 1 <= linea <= len(lineas), (
        f"la línea {linea} ni siquiera existe en un fichero de {len(lineas)}: "
        f"el mensaje manda a mirar fuera del fichero"
    )
    contenido = lineas[linea - 1]
    assert 1 <= columna <= len(contenido), (
        f"la columna {columna} se sale de la línea {linea} ({contenido!r})"
    )
    assert contenido[columna - 1] == culpable, (
        f"la posición {linea}:{columna} del mensaje cae sobre "
        f"{contenido[columna - 1]!r} y el carácter que el parser rechazó es "
        f"{culpable!r}. Un mensaje que señala mal manda a revisar código sano"
    )


@pytest.mark.parametrize(
    ("texto", "_linea", "_columna", "_culpable", "problema"),
    YAML_ROTOS,
)
def test_f006_r1_el_error_de_yaml_conserva_el_detalle_real_del_parser(
    tmp_path: pathlib.Path,
    texto: str,
    _linea: int,
    _columna: int,
    _culpable: str,
    problema: str,
) -> None:
    """Lo que dijo PyYAML, no un texto genérico igual para todos los errores.

    Se comprueba con los DOS ficheros rotos a propósito: cada uno tiene que
    producir su propio diagnóstico. Si el detalle se perdiera, los dos mensajes
    serían indistinguibles y quien los lea no sabría si le falta un corchete o
    le sobran dos puntos.
    """
    detalle = _detalle_de(tmp_path, texto)

    assert problema in detalle
    assert "YAML mal formado" not in detalle, (
        "el texto de reserva solo vale cuando el parser NO dice qué pasó; aquí "
        "sí lo dice y hay que servirlo"
    )


def test_f006_r1_los_dos_yaml_rotos_no_dan_el_mismo_mensaje(
    tmp_path: pathlib.Path,
) -> None:
    """Dos fallos distintos, dos mensajes distintos. Es todo el propósito.

    Sin esto, «trae el detalle» se podría cumplir con un mensaje que trae
    siempre el mismo detalle. Aquí se ve que el mensaje discrimina.
    """
    primero = _detalle_de(tmp_path / "a", YAML_ROTOS[0].values[0])
    segundo = _detalle_de(tmp_path / "b", YAML_ROTOS[1].values[0])

    assert primero != segundo


def test_f006_r1_sin_detalle_del_parser_se_usa_el_texto_de_reserva() -> None:
    """La otra rama del `or`: un `YAMLError` pelado no puede dejar el hueco.

    `yaml.YAMLError` es la base de la jerarquía y no promete ni `problem` ni
    `problem_mark`. Cuando no los trae, el mensaje tiene que decir «YAML mal
    formado» —que es poco, pero es cierto— y no arrastrar un `None` hasta la
    salida del ETL.
    """
    detalle = _detalle_yaml(yaml.YAMLError("una subclase cualquiera sin marca"))

    assert detalle == "el YAML no parsea: YAML mal formado"
