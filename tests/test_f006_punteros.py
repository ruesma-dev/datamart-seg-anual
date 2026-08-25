# tests/test_f006_punteros.py
"""
Ningún texto publicado puede citar un objeto que no existe (séptima pasada).

Todo el argumento de DA-2 —«no consultes `raw`, ve aguas abajo, y la ficha te
dice a dónde»— descansa en que el destino exista. Trece punteros de las fichas
de `raw` apuntaban a `compras.documentos` y `compras.fact_linea`, que **no
existen en ningún SQL del repositorio**: los reales son `compras.contratos`,
`compras.albaranes`, `compras.facturas` y `compras.fact_compras_linea`. Siete
`motivo_no_consumo` quedaban así vacíos de contenido — mandaban a un sitio
inexistente.

Escribir un nombre de objeto a mano en prosa es exactamente el caso en el que
hay una fuente comprobable al lado: **el propio diccionario**, que sabe qué
objetos existen porque los tiene fichados. Esto lo deriva.

Alcance: el texto **publicable**, no los comentarios. Un comentario YAML no
llega al MCP, y ya nos costó dos veces creer que sí.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest

from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

DIR_DICCIONARIO = pathlib.Path(__file__).resolve().parents[1] / "config" / "diccionario"

#: `esquema.objeto`, con el esquema entre los nueve del datamart. `_meta` lleva
#: guion bajo delante, así que el nombre admite ese primer carácter.
#: Un `*` detrás es un comodín («las vistas `compras.v_*`»), no un objeto.
_CITA = re.compile(
    r"(?<![\w./])(" + "|".join(re.escape(e) for e in sorted(ESQUEMAS_DEL_DATAMART))
    + r")\.([a-z_][a-z0-9_]*)(?![\w*])"
)

#: Rutas de fichero como `sql/stg/01_ddl.sql` o `mart/04_view.sql`: el nombre de
#: esquema es ahí un directorio, no un objeto. Se reconocen porque lo que sigue
#: es una extensión o porque delante va una barra (ya excluido en el `(?<!…)`).
_ES_FICHERO = re.compile(r"^\d|\.sql$|_sql$")


@lru_cache(maxsize=1)
def _diccionario():
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _textos_publicables(ficha) -> list[tuple[str, str]]:
    """Todo lo que de esta ficha acaba en `_meta.diccionario`, con su campo."""
    trozos: list[tuple[str, str]] = [
        ("descripcion", ficha.descripcion or ""),
        ("grano", ficha.grano or ""),
        ("motivo_no_consumo", ficha.motivo_no_consumo or ""),
    ]
    trozos += [(f"ejemplos_preguntas", e) for e in ficha.ejemplos_preguntas]
    for c in ficha.columnas:
        trozos.append((f"columnas.{c.nombre}.significado", c.significado or ""))
        trozos.append((f"columnas.{c.nombre}.nulo_significa", c.nulo_significa or ""))
    for r in ficha.relaciones:
        trozos.append((f"relaciones.{r.a}.porque", r.porque or ""))
    return trozos


def _citas(texto: str) -> set[str]:
    encontradas = set()
    for esquema, objeto in _CITA.findall(texto):
        if _ES_FICHERO.search(objeto):
            continue
        encontradas.add(f"{esquema}.{objeto}")
    return encontradas


def _nombres_de_objeto() -> set[str]:
    return {f.nombre for f in _diccionario().fichas}


@pytest.mark.parametrize(
    "nombre", sorted(f.nombre for f in cargar_diccionario(DIR_DICCIONARIO)[0].fichas)
)
def test_f006_r5_las_fichas_no_citan_objetos_inexistentes(nombre: str) -> None:
    """Un puntero roto vacía de contenido el campo que lo lleva."""
    ficha = next(f for f in _diccionario().fichas if f.nombre == nombre)
    existentes = _nombres_de_objeto()

    rotos: list[str] = []
    for campo, texto in _textos_publicables(ficha):
        for cita in sorted(_citas(texto)):
            # `esquema.objeto.columna`: nos quedamos con el objeto, que es lo
            # que tiene que existir; la columna la comprueban otros tests.
            if cita not in existentes:
                rotos.append(f"{campo} -> {cita}")

    assert rotos == [], (
        f"{nombre} cita objetos que no están en el diccionario: {rotos}. "
        f"Si el objeto existe pero no está fichado, es un hueco de cobertura; "
        f"si no existe, el puntero manda al agente a ninguna parte"
    )


def test_f006_r9_las_reglas_tampoco_citan_objetos_inexistentes() -> None:
    """Las reglas se sirven enteras y antes que nada: un puntero roto ahí pesa más."""
    existentes = _nombres_de_objeto()
    rotos: list[str] = []
    for regla in _diccionario().reglas:
        for campo, texto in (("regla", regla.regla), ("motivo", regla.motivo)):
            rotos += [
                f"{regla.codigo}.{campo} -> {c}"
                for c in sorted(_citas(texto))
                if c not in existentes
            ]
    assert rotos == []


def test_f006_r5_el_detector_de_punteros_reconoce_uno_roto() -> None:
    """Si el detector no detectase, los tests de arriba pasarían en falso."""
    assert _citas("ve a `compras.documentos` en vez de aquí") == {"compras.documentos"}
    assert "compras.documentos" not in _nombres_de_objeto()
    # y no confunde una ruta de fichero con un objeto
    assert _citas("verificado en `stg/08_plan_mensual.sql`") == set()
    assert _citas("ver `sql/mart/04_view_periodificado.sql`") == set()
    # ni un comodín con una familia de vistas
    assert _citas("las vistas `compras.v_*` ya lo cruzan") == set()
