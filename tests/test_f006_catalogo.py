# tests/test_f006_catalogo.py
"""
El contraste contra el catalogo real de Postgres (F-006, R28, bloque H).

La primera vez que se hizo, el 2026-08-21, **no lo produjo ningun comando**: la
huerfana `cierre.v_pbi_planif_vs_real` aparecio de rebote, por un
`except UndefinedTable` del chequeo de unicidad. Eso solo recorre la superficie
de consumo, o sea **47 de 102 objetos**, y solo detecta una de las tres clases
de discrepancia.

Aqui esta hecho de frente: los 102, en las tres direcciones, y con el aviso de
que **lo publicado ya no sea lo del arbol**, que es como `_meta` acabo sirviendo
un grano que T26 habia demostrado falso.

Sin conexion: se compara contra filas de catalogo fabricadas.
"""

from __future__ import annotations

import pathlib
from functools import lru_cache

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from etl_sigrid.infrastructure.postgres.catalogo import (
    comparar,
    formatear,
    normalizar_tipo,
)

DIR_DICCIONARIO = pathlib.Path(__file__).resolve().parents[1] / "config" / "diccionario"


@lru_cache(maxsize=1)
def _dicc():
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _catalogo_completo():
    """Lo que devolveria la base si tuviera exactamente lo fichado."""
    tipos = {"tabla": "BASE TABLE", "vista": "VIEW", "funcion": "funcion"}
    return [
        (f.esquema, f.objeto, tipos[f.tipo]) for f in _dicc().fichas
    ]


def test_f006_r28_la_biyeccion_perfecta_no_da_discrepancias() -> None:
    informe = comparar(_dicc(), _catalogo_completo())
    assert informe.ok
    # Derivados: el recuento cableado se quedó atrás en cuanto el contrato
    # creció con `_meta.diccionario_contexto`.
    assert informe.comprobados == len(_dicc().fichas)
    assert informe.en_catalogo == len(_dicc().fichas)
    assert "biyeccion exacta" in formatear(informe)


def test_f006_r28_alcanza_a_los_102_no_a_los_47_de_consumo() -> None:
    """El motivo de que exista este comando.

    El hallazgo de la primera vez salio de un chequeo que solo mira la
    superficie de consumo. Si esto se acotara igual, volveria a ver la mitad.
    """
    informe = comparar(_dicc(), _catalogo_completo())
    de_consumo = sum(1 for f in _dicc().fichas if f.consumo_recomendado)
    assert de_consumo < informe.comprobados, "el consumo es un subconjunto"
    assert informe.comprobados == len(_dicc().fichas)


def test_f006_r28_detecta_un_objeto_publicado_sin_ficha() -> None:
    catalogo = _catalogo_completo() + [("mart", "v_pbi_inventada", "VIEW")]
    informe = comparar(_dicc(), catalogo)

    (d,) = [x for x in informe.discrepancias if x.clase == "sin_ficha"]
    assert d.objeto == "mart.v_pbi_inventada"
    assert "no documenta" in d.detalle
    assert "PUBLICADO Y SIN FICHA" in formatear(informe)


def test_f006_r28_detecta_una_ficha_sin_objeto() -> None:
    """El caso real: `cierre.v_pbi_planif_vs_real`."""
    catalogo = [f for f in _catalogo_completo() if f[1] != "v_pbi_planif_vs_real"]
    informe = comparar(_dicc(), catalogo)

    (d,) = [x for x in informe.discrepancias if x.clase == "huerfana"]
    assert d.objeto == "cierre.v_pbi_planif_vs_real"
    assert "NO existe en la base" in d.detalle
    assert "falta lanzar el build de `cierre`" in d.detalle


def test_f006_r28_detecta_un_tipo_que_no_casa() -> None:
    catalogo = [
        (e, o, "BASE TABLE" if o == "v_pbi_fact" else t)
        for e, o, t in _catalogo_completo()
    ]
    informe = comparar(_dicc(), catalogo)

    (d,) = [x for x in informe.discrepancias if x.clase == "tipo_distinto"]
    assert d.objeto == "mart.v_pbi_fact"
    assert "`vista`" in d.detalle and "`tabla`" in d.detalle


def test_f006_r28_las_tres_clases_a_la_vez() -> None:
    """Un informe con las tres no puede perder ninguna."""
    catalogo = [
        (e, o, "BASE TABLE" if o == "v_pbi_fact" else t)
        for e, o, t in _catalogo_completo()
        if o != "v_pbi_planif_vs_real"
    ] + [("mart", "v_pbi_inventada", "VIEW")]
    informe = comparar(_dicc(), catalogo)

    clases = sorted({d.clase for d in informe.discrepancias})
    assert clases == ["huerfana", "sin_ficha", "tipo_distinto"]
    texto = formatear(informe)
    for titulo in ("PUBLICADO Y SIN FICHA", "FICHADO Y NO EXISTE", "TIPO QUE NO CASA"):
        assert titulo in texto


def test_f006_r28_normaliza_el_vocabulario_del_catalogo() -> None:
    """`information_schema` habla en ingles y en mayusculas; la ficha, no."""
    assert normalizar_tipo("BASE TABLE") == "tabla"
    assert normalizar_tipo("VIEW") == "vista"
    assert normalizar_tipo("funcion") == "funcion"


def test_f006_r28_control_el_detector_no_pasa_en_vacio() -> None:
    """Si `comparar` dejara de comparar, los tests de arriba seguirian verdes."""
    informe = comparar(_dicc(), [])
    assert len(informe.discrepancias) == len(_dicc().fichas), (
        "con el catalogo vacio TODAS las fichas tienen que salir como huerfanas"
    )
    assert all(d.clase == "huerfana" for d in informe.discrepancias)
