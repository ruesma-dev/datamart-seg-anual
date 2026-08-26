# tests/test_f006_constantes_de_contrato.py
"""
Las constantes y los valores por defecto de F-006, fijados por su EFECTO.

La 2ª campaña de mutación dejó vivos nueve mutantes que solo cambiaban un
número o un booleano: `TIMEOUT_POR_CONSULTA_S`, `TAMANO_MUESTRA`, los decimales
de la cobertura, el `orden` por defecto de una `Regla`, el `solo_consumo=True`
de los barridos y los rangos `range(1, 10)` de `com{i}`/`lpt{i}`. Sobreviven
todos por el mismo motivo: **el valor se usa, pero nadie comprueba cuál es**.
Un test que llegara a la constante y la comparase consigo misma seguiría sin
cazarlos —se movería con ella—, y de hecho eso es justo lo que ya pasa con
`DISPOSITIVOS_RESERVADOS`: `tests/test_f006_nombres_fichero.py` lleva su
**propia copia** del conjunto, así que cambiar el del cargador no rompe nada.

Por eso aquí cada constante se fija por lo que produce:

* el timeout, por el `SET LOCAL` literal que se emite;
* la muestra, por el `LIMIT` que aparece en el SQL generado;
* los decimales, por un porcentaje que los necesita (un tercio);
* el `orden` por defecto, por el sitio en que sale la regla al servirla;
* el `solo_consumo` por defecto, por qué objetos se saltan al llamar SIN el
  argumento, que es lo que hace el comando cuando no se le pasa `--todos`;
* los rangos, por `nombre_de_fichero("com9")` y `nombre_de_fichero("com10")`,
  que son los dos bordes que distinguen COM1–COM9 de cualquier otra cosa.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.diccionario import Columna, Diccionario, Ficha, Regla, Relacion
from etl_sigrid.infrastructure.diccionario.cargador_yaml import nombre_de_fichero
from etl_sigrid.infrastructure.postgres.diccionario_sql import (
    cobertura_columnas,
    filas_reglas,
)
from etl_sigrid.infrastructure.postgres.relaciones_sql import (
    consultas_de_relaciones,
    relaciones_saltadas,
)
from etl_sigrid.infrastructure.postgres.unicidad_sql import (
    consultas_de_unicidad,
    objetos_saltados,
    sentencias_previas,
)

MOTIVO_FUERA_DE_CONSUMO = "fuera de la superficie de consumo (usa `--todos`)"


def _ficha(**kwargs) -> Ficha:
    base = dict(
        esquema="mart",
        objeto="ejemplo",
        tipo="tabla",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano="Una fila por obra y mes, que es su clave.",
        clave_negocio=("obra_id",),
        paso_etl="build_mart",
        refresco="nocturno",
        columnas=(Columna(nombre="obra_id", significado="S" * 40),),
        relaciones=(),
        ejemplos_preguntas=("Cuanto llevo certificado en la obra X",),
    )
    base.update(kwargs)
    return Ficha(**base)


def _dicc(*fichas: Ficha, reglas: tuple[Regla, ...] = ()) -> Diccionario:
    return Diccionario(
        version="1",
        base="sigrid_dm",
        fichas=fichas,
        reglas=reglas,
        esquemas={},
        pendientes=(),
        global_raw={},
    )


# ---------------------------------------------------------------------------
# `Regla.orden = 0`: el orden en que se sirven las reglas duras al agente
# ---------------------------------------------------------------------------


def _regla(codigo: str, **kwargs) -> Regla:
    base = dict(
        codigo=codigo,
        titulo="T" * 20,
        severidad="critica",
        ambito=("mart",),
        regla="R" * 40,
        motivo="M" * 40,
    )
    base.update(kwargs)
    return Regla(**base)


def test_f006_una_regla_sin_orden_se_sirve_antes_que_una_con_orden_1() -> None:
    """El `orden` por defecto tiene que ser MENOR que cualquiera explícito.

    Se comprueba con los códigos al revés del alfabeto a propósito: si el
    defecto dejara de ser 0 y empatara con el 1, el desempate alfabético
    cambiaría el orden y el agente leería primero la regla equivocada. Es un
    fallo mudo: las reglas se sirven igual, solo que en otra prioridad.
    """
    sin_orden = _regla("R-ZZZ-SIN-ORDEN")
    con_orden = _regla("R-AAA-CON-ORDEN", orden=1)
    servidas = [fila[0] for fila in filas_reglas(_dicc(reglas=(con_orden, sin_orden)))]
    assert servidas == ["R-ZZZ-SIN-ORDEN", "R-AAA-CON-ORDEN"], (
        "una regla que no declara `orden` tiene que ir por delante de una que "
        "declara `orden: 1`; si no, el defecto ha dejado de ser 0"
    )


def test_f006_el_orden_por_defecto_se_publica_como_cero() -> None:
    """Es el valor que acaba en `_meta` y que el MCP sirve tal cual."""
    (fila,) = filas_reglas(_dicc(reglas=(_regla("R-UNA"),)))
    assert fila[-1] == 0


# ---------------------------------------------------------------------------
# `TIMEOUT_POR_CONSULTA_S = 30`: lo que se emite antes de cada consulta
# ---------------------------------------------------------------------------


def test_f006_las_sentencias_previas_llevan_el_timeout_y_el_solo_lectura() -> None:
    """Esto corre contra un Postgres COMPARTIDO con `albaranes` y `partes`.

    Las dos garantías van en el literal: treinta segundos de tope por consulta
    y transacción de solo lectura. Fijar el texto exacto es lo que impide que
    el tope suba sin que nadie lo vea, que es como se deja sin CPU un servidor
    de producción con una consulta perfectamente correcta.
    """
    assert sentencias_previas() == (
        "SET LOCAL statement_timeout = '30s'",
        "SET LOCAL transaction_read_only = on",
    )


# ---------------------------------------------------------------------------
# `TAMANO_MUESTRA = 500`: lo que se lee de la tabla de la izquierda
# ---------------------------------------------------------------------------


def _par_con_relacion(**kwargs) -> Diccionario:
    """Una ficha con UNA relación y su destino fichado. `kwargs` va al origen."""
    origen = _ficha(
        objeto="origen",
        relaciones=(
            Relacion(
                de="obra_id", a="maestro.obras.obra_id", cardinalidad="N:1", porque="P" * 40
            ),
        ),
        **kwargs,
    )
    destino = _ficha(esquema="maestro", objeto="obras", tipo="vista")
    return _dicc(origen, destino)


def test_f006_la_muestra_de_una_relacion_son_quinientos_valores() -> None:
    """El `LIMIT` va en el SQL que se ejecuta, no en un comentario.

    La cota existe para no barrer tablas de decenas de millones de filas en un
    servidor compartido en producción. Si sube sin querer, el chequeo pasa de
    barato a caro sin que ninguna prueba lo note.
    """
    (consulta,) = consultas_de_relaciones(_par_con_relacion())
    assert consulta.muestra == 500
    assert "LIMIT 500\n" in consulta.sql


# ---------------------------------------------------------------------------
# `round(..., 2)`: los decimales de la cobertura de columnas
# ---------------------------------------------------------------------------


def test_f006_la_cobertura_de_columnas_se_redondea_a_dos_decimales() -> None:
    """Un tercio es el caso que distingue 2 decimales de 3.

    Con una de cada tres columnas documentada, la cobertura real es
    33,3333…: a dos decimales sale 33.33 y a tres, 33.333. Cualquier reparto
    «redondo» —la mitad, un cuarto— pasaría con los dos, que es por lo que
    ningún test lo cazaba.
    """
    ficha = _ficha(
        columnas=(
            Columna(nombre="obra_id", significado="S" * 40),
            Columna(nombre="sin_uno", significado=""),
            Columna(nombre="sin_dos", significado="   "),
        )
    )
    assert cobertura_columnas(_dicc(ficha)) == 33.33


# ---------------------------------------------------------------------------
# `solo_consumo: bool = True`: a qué mira la puerta cuando no se le dice nada
# ---------------------------------------------------------------------------


def _fuera_de_consumo(**kwargs) -> Ficha:
    return _ficha(consumo_recomendado=False, motivo_no_consumo="M" * 40, **kwargs)


def test_f006_por_defecto_la_unicidad_solo_mira_lo_recomendado() -> None:
    """Sin `--todos`, un objeto fuera de la superficie de consumo se SALTA.

    Y se salta **diciéndolo**: el motivo tiene que aparecer en la lista de
    saltados. Un barrido que se calla lo que no miró invita a leer «todo
    correcto» como «todo comprobado», que ya pasó dos veces en esta feature.
    """
    dicc = _dicc(_fuera_de_consumo())
    assert consultas_de_unicidad(dicc) == []
    assert dict(objetos_saltados(dicc)) == {"mart.ejemplo": MOTIVO_FUERA_DE_CONSUMO}


def test_f006_con_todos_la_unicidad_si_mira_lo_no_recomendado() -> None:
    """La otra mitad del contrato: `--todos` levanta el filtro, no lo invierte."""
    dicc = _dicc(_fuera_de_consumo())
    assert [c.objeto for c in consultas_de_unicidad(dicc, solo_consumo=False)] == [
        "mart.ejemplo"
    ]
    assert MOTIVO_FUERA_DE_CONSUMO not in dict(
        objetos_saltados(dicc, solo_consumo=False)
    ).values()


def test_f006_por_defecto_las_relaciones_solo_miran_lo_recomendado() -> None:
    """Mismo defecto y mismo motivo en el barrido de relaciones.

    Una relación falsa dentro de la superficie de consumo produce un JOIN vacío
    en una respuesta de negocio; fuera de ella el objeto no debería consultarse.
    Ese es el criterio que fija el defecto, y `--todos` lo levanta.
    """
    dicc = _par_con_relacion(consumo_recomendado=False, motivo_no_consumo="M" * 40)
    assert consultas_de_relaciones(dicc) == []
    assert dict(relaciones_saltadas(dicc)) == {
        "mart.origen.obra_id": MOTIVO_FUERA_DE_CONSUMO
    }
    assert len(consultas_de_relaciones(dicc, solo_consumo=False)) == 1


# ---------------------------------------------------------------------------
# `range(1, 10)`: los dispositivos reservados son COM1–COM9 y LPT1–LPT9
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "esquema",
    ["con", "prn", "aux", "nul", "com1", "com9", "lpt1", "lpt9", "AUX", "Com1"],
)
def test_f006_un_esquema_con_nombre_reservado_lleva_sufijo(esquema: str) -> None:
    """`com1` y `lpt1` son los bordes de abajo: MS-DOS numeró desde el UNO.

    Si el rango empezara en 2, `com1.yaml` se crearía con su nombre real y git
    no podría indexarlo —el fallo que costó un `git add` con `aux.yaml`—, con
    el agravante de que el fichero existe y el ETL lo carga: rompe solo al
    salir del puesto donde se escribió.
    """
    assert nombre_de_fichero(esquema) == f"{esquema}_.yaml"


@pytest.mark.parametrize("esquema", ["com0", "com10", "lpt0", "lpt10", "mart", "stg"])
def test_f006_un_esquema_normal_no_lleva_sufijo(esquema: str) -> None:
    """`com10` y `lpt10` son los bordes de arriba: la familia acaba en el NUEVE.

    Escapar de más no rompe git, pero sí el cargador: exige que el nombre del
    fichero case con el esquema, y `com10_.yaml` no casaría con `com10`. La
    excepción es para lo que el sistema operativo impone, no un colchón.
    """
    assert nombre_de_fichero(esquema) == f"{esquema}.yaml"
