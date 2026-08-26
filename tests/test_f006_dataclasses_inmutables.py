# tests/test_f006_dataclasses_inmutables.py
"""
Barrido: TODA dataclass de `etl_sigrid` es inmutable y usa `slots` (F-006).

Este fichero nace de la lección número uno de F-006, repetida dos veces. La
primera campaña de mutación dejó vivos `frozen=True -> frozen=False` en
`Columna` y `Relacion`; se escribió `tests/test_f006_supervivientes.py` con un
`parametrize` de **dos casos, a mano**, y la campaña siguiente sacó **veinte
supervivientes de la misma clase** en las doce dataclasses de al lado:
`Ficha`, `Regla`, `Diccionario`, `ErrorValidacion`, `ObjetoPublicado`,
`InformeCobertura`, `Discrepancia`, `InformeCatalogo`, `ConsultaRelacion` y
`ConsultaUnicidad`.

*El defecto sobrevive en el campo de al lado; corregir donde te lo señalan no
es corregir.* Por eso aquí no hay lista de clases: el barrido **descubre** las
dataclasses recorriendo el paquete, así que una que se añada mañana entra sola.
La única lista escrita a mano es la de **excepciones**, y tiene su propio test
para que no envejezca: una excepción que deje de hacer falta rompe la suite.

Qué se comprueba y por qué, no como decoración:

* **`frozen`**: estas entidades se comparten entre el validador, el cargador,
  los constructores de SQL y la publicación. Que la misma `Columna` que se está
  publicando pueda cambiarse desde otro sitio significa que lo publicado no es
  lo validado.
* **`slots`**: sin `__slots__` la instancia lleva un `__dict__`, y entonces
  `object.__setattr__` mete atributos que NO son campos —un `descripciom` mal
  escrito se traga en silencio— además del coste en memoria de instancias que
  se crean por millares al construir el diccionario.

Las dos comprobaciones son **de comportamiento**, no de bandera: se construye
la instancia sin `__init__` y se intenta la escritura que cada opción tiene que
impedir. Comprobar `cls.__dataclass_params__.frozen` sería repetir el
decorador; esto ejercita lo que el decorador produce.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

import etl_sigrid

#: Dataclasses **anteriores a F-006** que hoy son mutables, con su porqué.
#:
#: `etl_sigrid/domain/entities.py` es el dominio del ETL original: `StepResult`
#: se rellena por fases mientras el step corre —arranca vacío y acumula filas y
#: errores—, y `TableSpec`/`ColumnSpec` se construyen a trozos desde
#: `config/tables_sigrid.yaml`. Congelarlas es un cambio de producción que no
#: cabe en el cierre de F-006: no es una decisión de tests.
#:
#: `slots` SÍ lo tienen las tres, así que la excepción es solo para `frozen`.
#:
#: La lista es de EXCEPCIONES, no de cobertura: lo que no está aquí se exige.
MUTABLES_HEREDADAS = frozenset(
    {
        "etl_sigrid.domain.entities.StepResult",
        "etl_sigrid.domain.entities.TableSpec",
        "etl_sigrid.domain.entities.ColumnSpec",
    }
)


def _nombre(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _dataclases_del_paquete() -> list[type]:
    """Todas las dataclasses DEFINIDAS en `etl_sigrid`, descubiertas al vuelo.

    El filtro `obj.__module__ == mod.__name__` deja fuera las importadas: cada
    clase se comprueba una vez, en el módulo donde vive.
    """
    encontradas: dict[str, type] = {}
    for info in pkgutil.walk_packages(etl_sigrid.__path__, f"{etl_sigrid.__name__}."):
        modulo = importlib.import_module(info.name)
        for objeto in vars(modulo).values():
            if (
                inspect.isclass(objeto)
                and dataclasses.is_dataclass(objeto)
                and objeto.__module__ == modulo.__name__
            ):
                encontradas[_nombre(objeto)] = objeto
    return [encontradas[nombre] for nombre in sorted(encontradas)]


DATACLASES = _dataclases_del_paquete()
IDS = [_nombre(cls) for cls in DATACLASES]


# ---------------------------------------------------------------------------
# El barrido tiene que ver de verdad lo que hay
# ---------------------------------------------------------------------------


def _modulos_con_dataclass_en_el_fuente() -> set[str]:
    """Módulos cuyo TEXTO usa `@dataclass`, leídos del árbol.

    Es el contraste que impide el fallo silencioso del barrido: si
    `walk_packages` dejara de ver una carpeta, la lista de arriba se quedaría
    corta y todos los `parametrize` seguirían en verde sobre lo que sí ve.
    Comparar contra el fuente lo denuncia.
    """
    raiz = Path(etl_sigrid.__file__).resolve().parent
    modulos: set[str] = set()
    for ruta in raiz.rglob("*.py"):
        if "@dataclass" not in ruta.read_text(encoding="utf-8"):
            continue
        relativa = ruta.relative_to(raiz).with_suffix("")
        partes = [p for p in relativa.parts if p != "__init__"]
        modulos.add(".".join([etl_sigrid.__name__, *partes]))
    return modulos


def test_f006_el_barrido_ve_todos_los_modulos_que_declaran_dataclasses() -> None:
    """Sin esto, un barrido que no encuentra nada pasa por barrido limpio."""
    vistos = {cls.__module__ for cls in DATACLASES}
    en_el_fuente = _modulos_con_dataclass_en_el_fuente()
    assert en_el_fuente - vistos == set(), (
        f"estos modulos declaran `@dataclass` en su fuente y el barrido no ha "
        f"visto ninguna clase en ellos: {sorted(en_el_fuente - vistos)}. O el "
        f"recorrido del paquete se ha roto, o la clase se define de una forma "
        f"que este fichero no reconoce; en ambos casos hay clases sin vigilar"
    )


# ---------------------------------------------------------------------------
# Las dos garantías, comprobadas por comportamiento
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", DATACLASES, ids=IDS)
def test_f006_toda_dataclass_del_paquete_es_inmutable(cls: type) -> None:
    """Nadie puede reasignar un campo despues de construida la instancia."""
    if _nombre(cls) in MUTABLES_HEREDADAS:
        pytest.skip("excepcion documentada en MUTABLES_HEREDADAS")
    campos = dataclasses.fields(cls)
    assert campos, f"{_nombre(cls)} es un dataclass sin campos: nada que fijar"
    instancia = object.__new__(cls)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instancia, campos[0].name, "lo que sea")


@pytest.mark.parametrize("cls", DATACLASES, ids=IDS)
def test_f006_toda_dataclass_del_paquete_usa_slots(cls: type) -> None:
    """Sin `slots` la instancia acepta atributos que no son campos.

    Se usa `object.__setattr__` a propósito: salta por encima del `frozen`, que
    si no lo taparia, y deja a la vista si hay `__dict__` debajo.
    """
    instancia = object.__new__(cls)
    with pytest.raises(AttributeError):
        object.__setattr__(instancia, "_atributo_que_no_es_un_campo", 1)


def test_f006_la_lista_de_excepciones_no_envejece() -> None:
    """Una excepcion que ya no hace falta tiene que quitarse, no quedarse.

    Es la diferencia entre una lista de excepciones y una alfombra: si alguien
    congela `StepResult` y nadie borra la entrada, la exencion sigue viva para
    la siguiente clase que se llame igual.
    """
    por_nombre = {_nombre(cls): cls for cls in DATACLASES}
    for nombre in sorted(MUTABLES_HEREDADAS):
        cls = por_nombre.get(nombre)
        assert cls is not None, (
            f"{nombre} esta exento de `frozen` y ya no existe: quita la entrada "
            f"de MUTABLES_HEREDADAS"
        )
        instancia = object.__new__(cls)
        campo = dataclasses.fields(cls)[0].name
        try:
            setattr(instancia, campo, "lo que sea")
        except dataclasses.FrozenInstanceError:  # pragma: no cover - la buena
            pytest.fail(
                f"{nombre} ya es inmutable: quita la entrada de "
                f"MUTABLES_HEREDADAS para que quede vigilada como el resto"
            )
