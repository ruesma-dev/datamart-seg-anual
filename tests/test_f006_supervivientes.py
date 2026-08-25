# tests/test_f006_supervivientes.py
"""
Los cuatro supervivientes que el timeout de la campaña estaba disfrazando (T25).

La campaña de mutación cerró con «166 mutantes, 162 muertos, **0
supervivientes**, 4 timeouts». Leído deprisa, eso es una campaña limpia. No lo
era: los cuatro timeouts fueron consecutivos, coincidieron con otra suite
corriendo en la misma máquina, y al reevaluarlos de uno en uno **sobrevivieron
los cuatro**.

Deja una lección que vale más que los cuatro tests: **un timeout no es un
mutante muerto, es un mutante sin evaluar**, y un informe que los cuenta aparte
del recuento de supervivientes invita a leerlos como ruido.

Los cuatro son de dos clases, y ninguna es un mutante equivalente:

* **`frozen=True` → `frozen=False`** en `Columna` y `Relacion`. Nada rompía al
  volverlas mutables, y la inmutabilidad no es decoración aquí: estas entidades
  se comparten entre el validador, el cargador y los constructores de SQL, y se
  publican tal cual. Que la misma `Columna` que se está publicando pueda
  cambiarse desde otro sitio es exactamente el fallo que `frozen` impide. La
  hermana `Ficha` (línea 277) SÍ tenía quien la cazara; estas dos no.
* **Los mínimos de longitud subidos en uno** (`grano` y `ejemplo_pregunta`, de
  20 a 21). Sobreviven porque **ningún caso ejercita el borde**: si ninguna
  ficha ni ningún test tiene un texto de exactamente 20 caracteres, mover el
  umbral no cambia ningún veredicto. El límite se comprueba por dentro, con un
  texto del largo exacto, que es lo que fija el contrato.
"""

from __future__ import annotations

import dataclasses

import pytest

from etl_sigrid.domain.diccionario import (
    MINIMOS_TEXTO,
    Columna,
    Ficha,
    Relacion,
    validar,
)


# ---------------------------------------------------------------------------
# Clase 1 · las entidades no se pueden modificar después de construidas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("clase", "instancia", "campo", "valor"),
    [
        (
            Columna,
            Columna(nombre="importe_mes", significado="Importe de ese mes."),
            "significado",
            "otra cosa",
        ),
        (
            Relacion,
            Relacion(de="obra_id", a="stg.obras.obra_id", cardinalidad="N:1", porque="x"),
            "cardinalidad",
            "1:1",
        ),
    ],
    ids=["Columna", "Relacion"],
)
def test_f006_r2_las_entidades_del_diccionario_son_inmutables(
    clase: type, instancia: object, campo: str, valor: str
) -> None:
    """Se comparten entre validador, cargador y publicación: nadie las retoca.

    Sin esto, una `Columna` podría cambiar entre que se valida y que se publica,
    y lo publicado no sería lo validado.
    """
    assert dataclasses.fields(clase), "sigue siendo un dataclass"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instancia, campo, valor)


# ---------------------------------------------------------------------------
# Clase 2 · los mínimos de longitud, comprobados EN EL BORDE
# ---------------------------------------------------------------------------


def _ficha_con(grano: str, ejemplo: str) -> Ficha:
    """Una ficha válida salvo por lo que se quiera romper."""
    return Ficha(
        esquema="mart",
        objeto="ejemplo",
        tipo="tabla",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano=grano,
        clave_negocio=("obra_id",),
        paso_etl="build_mart",
        refresco="nocturno",
        columnas=(Columna(nombre="obra_id", significado="S" * 40),),
        relaciones=(),
        ejemplos_preguntas=(ejemplo,),
    )


#: Los mínimos que este fichero fija, **escritos a mano y a propósito**.
#:
#: El primer intento los leía de `MINIMOS_TEXTO`, y así el test no comprobaba
#: nada: al subir la constante, el texto de prueba subía con ella y el borde
#: seguía pasando. Los dos mutantes que suben el umbral en uno sobrevivieron
#: igual. Un test que se mueve con lo que vigila no vigila.
#:
#: Escribirlos aquí los convierte en contrato: cambiar `MINIMOS_TEXTO` obliga a
#: cambiar también esta línea, y entonces se ve en el diff.
MINIMOS_FIJADOS = {"grano": 20, "ejemplo_pregunta": 20}


def test_f006_r2_los_minimos_fijados_son_los_que_usa_el_dominio() -> None:
    """Une las dos listas: si divergen, es que alguien movió el umbral."""
    for campo, valor in MINIMOS_FIJADOS.items():
        assert MINIMOS_TEXTO[campo] == valor, (
            f"`MINIMOS_TEXTO[{campo!r}]` vale {MINIMOS_TEXTO[campo]} y este "
            f"fichero fija {valor}. Si el cambio es deliberado, cámbialo aquí "
            f"también; si no lo es, acabas de mover un umbral sin querer"
        )


@pytest.mark.parametrize("campo", ["grano", "ejemplo_pregunta"])
def test_f006_r2_el_minimo_de_longitud_admite_el_largo_exacto(campo: str) -> None:
    """Un texto del largo justo PASA. Es el borde de abajo del umbral."""
    minimo = MINIMOS_FIJADOS[campo]
    justo = "x" * minimo
    ficha = (
        _ficha_con(grano=justo, ejemplo="e" * MINIMOS_FIJADOS["ejemplo_pregunta"])
        if campo == "grano"
        else _ficha_con(grano="g" * MINIMOS_FIJADOS["grano"], ejemplo=justo)
    )
    errores = [e for e in validar(_dicc(ficha), ["build_mart"]) if e.objeto == "mart.ejemplo"]
    assert errores == [], (
        f"un `{campo}` de exactamente {minimo} caracteres tiene que valer: "
        f"si no, el mínimo real es {minimo + 1} y la constante miente"
    )


@pytest.mark.parametrize("campo", ["grano", "ejemplo_pregunta"])
def test_f006_r2_el_minimo_de_longitud_rechaza_un_caracter_menos(campo: str) -> None:
    """Uno menos NO pasa. Con el de arriba, deja el umbral clavado."""
    minimo = MINIMOS_FIJADOS[campo]
    corto = "x" * (minimo - 1)
    ficha = (
        _ficha_con(grano=corto, ejemplo="e" * MINIMOS_FIJADOS["ejemplo_pregunta"])
        if campo == "grano"
        else _ficha_con(grano="g" * MINIMOS_FIJADOS["grano"], ejemplo=corto)
    )
    errores = [e for e in validar(_dicc(ficha), ["build_mart"]) if e.objeto == "mart.ejemplo"]
    assert errores, f"un `{campo}` de {minimo - 1} caracteres tiene que fallar"


def _dicc(ficha: Ficha):
    from etl_sigrid.domain.diccionario import Diccionario

    return Diccionario(
        version="1",
        base="d",
        fichas=(ficha,),
        reglas=(),
        esquemas={"mart": {}},
        pendientes=(),
        global_raw={},
    )
