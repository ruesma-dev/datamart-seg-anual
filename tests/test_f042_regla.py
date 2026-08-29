# tests/test_f042_regla.py
"""
F-042 · La regla «un solo cierre por mes», contra las 24 colisiones reales.

Dominio puro: `etl_sigrid.domain.cierres` no importa infraestructura y estos
tests no abren ni red ni BBDD. Lo que se comprueba es el **oráculo**: dado el
acumulado a origen de cada fase de una (obra, ámbito), qué cierre manda cada mes
y con qué orden interno se queda el superviviente.

## De dónde salen los números

De `progress/explore_F-042.md`, medido el 2026-08-28 contra la base real en solo
lectura. Tres avisos para que nadie confunda dato con relleno:

1. **Los acumulados exactos solo existen para las 7 obras del conjunto C** y
   para el coste de 0606 (§4.2 y §8 del informe). Se usan tal cual: el
   «publicado hoy» es la suma de las dos fases y el «correcto» es el
   superviviente, así que la fase descartada sale por diferencia.
2. **Para las obras sin cifra medida** —las 13 del conjunto A y la 0433— el
   informe no publica euros. Aquí se usa un valor simbólico y se dice: la regla
   no mira cuánto vale un cierre, solo si su acumulado es **cero o no** y qué
   número de fase tiene. Poner una cifra inventada como si fuera medida sería
   fabricar evidencia; poner una simbólica y decirlo, no.
3. **Las 13 obras del conjunto A no llegan a colisionar en `plan_mensual`**:
   una de sus dos fases no tiene ni una línea de presupuesto (Q4), así que no
   produce ninguna fila y nunca llega a ser un `Cierre`. Cuál de las dos está
   vacía **no está en la línea base**, así que el test se hace con las dos
   variantes: mande la que mande, el resultado tiene que ser «un solo cierre,
   cero descartes».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.cierres import Cierre, plan_de_cierres

# El acumulado de una fase que la línea base no cuantifica. Positivo y distinto
# de los demás para que un test que se apoyara en su VALOR fallara a la vista.
SIMBOLICO = Decimal("1000.00")

#: La fase existe en Sigrid pero **no tiene ni una línea de presupuesto**, así
#: que no produce ninguna fila en `stg.plan_mensual` y no es un cierre.
SIN_PRESUPUESTO = None


@dataclass(frozen=True)
class Colision:
    """Un mes con dos o más fases en la misma (obra, ámbito 3 · Coste Real)."""

    codigo: str
    obra: str
    mes: date
    #: (numero_fase, acumulado) con `SIN_PRESUPUESTO` para la fase sin líneas.
    fases: tuple[tuple[int, Decimal | None], ...]
    #: La fase que debe sobrevivir, o `None` si el conjunto no lo fija.
    vigente: int | None
    conjunto: str


# ---------------------------------------------------------------------------
# Las 24 colisiones de progress/explore_F-042.md §2, ordenadas por año.
# ---------------------------------------------------------------------------
COLISIONES: tuple[Colision, ...] = (
    Colision(
        "0246", "C.R.A. EL ENCINAR", date(2010, 6, 1),
        ((12, Decimal("754631.04")), (13, Decimal("753433.05"))), 13, "C",
    ),
    Colision(
        "0310", "O.C. CASETA BOMBAS J.DEERE", date(2011, 5, 1),
        ((3, Decimal("57833.12")), (4, Decimal("59220.45"))), 4, "C",
    ),
    Colision(
        "0422", "DOMINO'S SALVADOR MADARIAGA", date(2014, 9, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0425", "DOMINO'S AVDA. FINISTERRE", date(2014, 10, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0433", "DOMINO'S PALMA DE MALLORCA", date(2014, 11, 1),
        ((1, SIMBOLICO), (2, Decimal("0.00"))), 1, "B",
    ),
    Colision(
        "0435", "DOMINO'S AVDA VALLADOLID", date(2014, 11, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0462", "REFUERZO TERRAZAS RETAMAR", date(2015, 12, 1),
        ((6, Decimal("197654.80")), (7, Decimal("197654.52"))), 7, "C",
    ),
    Colision(
        "0464", "DOMINO'S CASTELLO", date(2015, 9, 1),
        ((2, SIMBOLICO), (3, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0471", "AHORRAMAS LAS TABLAS", date(2016, 3, 1),
        ((5, Decimal("401158.12")), (6, Decimal("903517.44"))), 6, "C",
    ),
    Colision(
        "0471", "AHORRAMAS LAS TABLAS", date(2016, 4, 1),
        ((7, Decimal("903517.44")), (8, Decimal("1070081.64"))), 8, "C",
    ),
    Colision(
        "0472", "DOMINO'S AVILES", date(2015, 11, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0473", "DOMINO'S MIRACRUZ", date(2015, 11, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0499", "C.U. VILLANUEVA", date(2018, 1, 1),
        ((18, Decimal("3608280.89")), (19, Decimal("4712823.94"))), 19, "C",
    ),
    Colision(
        "0499", "C.U. VILLANUEVA", date(2018, 2, 1),
        ((20, Decimal("5065310.42")), (21, Decimal("5688073.92"))), 21, "C",
    ),
    Colision(
        "0505", "DOMINOS BENIDORM", date(2016, 8, 1),
        ((2, SIMBOLICO), (3, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0509", "DOMINOS ALFAFAR", date(2016, 10, 1),
        ((2, SIMBOLICO), (3, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0514", "DOMINOS EL EJIDO", date(2016, 11, 1),
        ((2, SIMBOLICO), (3, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0515", "DOMINOS PRETER", date(2016, 12, 1),
        ((3, SIMBOLICO), (4, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0516", "DOMINOS HUESCA", date(2016, 11, 1),
        ((2, SIMBOLICO), (3, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0521", "DOMINOS LA PESETA", date(2016, 12, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0545", "J. DEERE NAVE 01", date(2017, 12, 1),
        ((5, Decimal("152246.65")), (6, Decimal("156704.75"))), 6, "C",
    ),
    Colision(
        "0559", "DOMINO'S VALLADOLID", date(2017, 12, 1),
        ((1, SIMBOLICO), (2, SIN_PRESUPUESTO)), None, "A",
    ),
    Colision(
        "0571", "PZA. DEL CAMPILLO", date(2020, 5, 1),
        ((21, Decimal("4591339.39")), (22, Decimal("4591393.06"))), 22, "C",
    ),
    Colision(
        # El caso de R11: el cierre MODERNO está a cero y el bueno es el 14.
        "0606", "PUY DU FOU LOTE 7", date(2021, 2, 1),
        ((14, Decimal("9053263.61")), (16, Decimal("0.00"))), 14, "B",
    ),
)

COLISIONES_CON_VIGENTE = tuple(c for c in COLISIONES if c.vigente is not None)
COLISIONES_CONJUNTO_A = tuple(c for c in COLISIONES if c.conjunto == "A")


def _cierres(colision: Colision) -> list[Cierre]:
    """Los cierres que la colisión hace llegar de verdad a `plan_mensual`."""
    return [
        Cierre(numero_fase=numero, anio_mes=colision.mes, acumulado=acumulado)
        for numero, acumulado in colision.fases
        if acumulado is not SIN_PRESUPUESTO
    ]


def _ident(colision: Colision) -> str:
    return f"{colision.codigo}-{colision.mes:%Y-%m}"


# ---------------------------------------------------------------------------
# R1 · manda el cierre más moderno del mes con acumulado distinto de cero
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "colision", COLISIONES_CON_VIGENTE, ids=[_ident(c) for c in COLISIONES_CON_VIGENTE]
)
def test_f042_r1_manda_el_cierre_vigente_de_cada_colision_real(colision: Colision):
    """Las colisiones medidas eligen exactamente el cierre que dice la evidencia."""
    plan = plan_de_cierres(_cierres(colision))

    assert plan.vigente_por_mes[colision.mes] == colision.vigente, (
        f"{colision.codigo} {colision.mes:%m-%Y}: manda la fase "
        f"{plan.vigente_por_mes[colision.mes]} y la evidencia dice "
        f"{colision.vigente}"
    )


@pytest.mark.parametrize(
    "colision", COLISIONES_CON_VIGENTE, ids=[_ident(c) for c in COLISIONES_CON_VIGENTE]
)
def test_f042_r1_solo_sobrevive_un_cierre_por_mes(colision: Colision):
    """Después de la regla, el mes tiene UNA fase. Es el objetivo de la feature."""
    plan = plan_de_cierres(_cierres(colision))

    vivas = [f for f in plan.orden if f not in plan.descartadas]
    assert len(vivas) == 1, f"{_ident(colision)} deja {len(vivas)} cierres vivos"


def test_f042_r1_el_moderno_gana_aunque_su_acumulado_sea_menor():
    """0246: la fase 13 acumula MENOS que la 12 y aun así manda.

    La regla es por número de fase, no por importe. Si alguien la reescribiera
    como «gana el mayor acumulado», esta obra lo delata.
    """
    plan = plan_de_cierres(
        [
            Cierre(12, date(2010, 6, 1), Decimal("754631.04")),
            Cierre(13, date(2010, 6, 1), Decimal("753433.05")),
        ]
    )

    assert plan.vigente_por_mes[date(2010, 6, 1)] == 13
    assert plan.descartadas == (12,)


# ---------------------------------------------------------------------------
# R11 · el acumulado a cero se descarta aunque sea el más moderno
# ---------------------------------------------------------------------------


def test_f042_r11_se_descarta_el_cierre_a_cero_aunque_sea_el_moderno():
    """0606 · PUY DU FOU, feb-2021. Sin R11 esta obra pasaría a publicar CERO.

    Es la obra más grande del defecto por número de filas (3.336 claves
    duplicadas, el 38 % del total) y su error en euros es CERO: la regla ingenua
    «manda siempre el número mayor» la rompería por 18,24 M€.
    """
    plan = plan_de_cierres(
        [
            Cierre(14, date(2021, 2, 1), Decimal("9053263.61")),
            Cierre(16, date(2021, 2, 1), Decimal("0.00")),
        ]
    )

    assert plan.vigente_por_mes[date(2021, 2, 1)] == 14
    assert plan.descartadas == (16,)


def test_f042_r11_un_acumulado_negativo_cuenta_como_distinto_de_cero():
    """`<> 0`, no `> 0` (riesgo 5 del diseño).

    El humano fijó «acumulado cero»; su complemento exacto es «distinto de
    cero». Un acumulado negativo no existe hoy en la base, y precisamente por eso
    la regla no debe inventarle un trato: se comporta como cualquier otro
    cierre con dato.
    """
    plan = plan_de_cierres(
        [
            Cierre(1, date(2019, 3, 1), Decimal("500.00")),
            Cierre(2, date(2019, 3, 1), Decimal("-120.00")),
        ]
    )

    assert plan.vigente_por_mes[date(2019, 3, 1)] == 2
    assert plan.descartadas == (1,)


# ---------------------------------------------------------------------------
# R2 · si todos los cierres del mes están a cero, manda el mayor
# ---------------------------------------------------------------------------


def test_f042_r2_si_todos_estan_a_cero_manda_el_de_numero_mayor():
    plan = plan_de_cierres(
        [
            Cierre(4, date(2017, 7, 1), Decimal("0.00")),
            Cierre(5, date(2017, 7, 1), Decimal("0.00")),
            Cierre(6, date(2017, 7, 1), Decimal("0.00")),
        ]
    )

    assert plan.vigente_por_mes[date(2017, 7, 1)] == 6
    assert plan.descartadas == (4, 5)


# ---------------------------------------------------------------------------
# R5 · el orden interno se desplaza SOLO por descartes
# ---------------------------------------------------------------------------


def test_f042_r5_la_0499_recupera_el_lag_consecutivo():
    """0499 · VILLANUEVA: dos colisiones seguidas, ene y feb de 2018.

    Descartadas la 18 y la 20, la 19 pasa a orden 18 y la 21 a orden 19: el
    `LAG` vuelve a ser consecutivo y el movimiento de febrero sale
    5.688.073,92 − 4.712.823,94 = 975.249,98 en vez de los 5.688.073,92 que
    daría borrar sin renumerar.
    """
    plan = plan_de_cierres(
        [
            Cierre(17, date(2017, 12, 1), Decimal("3000000.00")),
            Cierre(18, date(2018, 1, 1), Decimal("3608280.89")),
            Cierre(19, date(2018, 1, 1), Decimal("4712823.94")),
            Cierre(20, date(2018, 2, 1), Decimal("5065310.42")),
            Cierre(21, date(2018, 2, 1), Decimal("5688073.92")),
            Cierre(22, date(2018, 3, 1), Decimal("7400000.00")),
        ]
    )

    assert plan.descartadas == (18, 20)
    assert plan.orden == {17: 17, 19: 18, 21: 19, 22: 20}
    # Lo que de verdad importa: los supervivientes quedan consecutivos.
    assert sorted(plan.orden.values()) == [17, 18, 19, 20]


def test_f042_r5_el_desplazamiento_solo_cuenta_los_descartes_anteriores():
    """Una fase anterior a cualquier descarte no se mueve ni una posición."""
    plan = plan_de_cierres(
        [
            Cierre(1, date(2016, 1, 1), Decimal("100.00")),
            Cierre(2, date(2016, 2, 1), Decimal("200.00")),
            Cierre(3, date(2016, 3, 1), Decimal("300.00")),
            Cierre(4, date(2016, 3, 1), Decimal("350.00")),
            Cierre(5, date(2016, 4, 1), Decimal("400.00")),
        ]
    )

    assert plan.descartadas == (3,)
    assert plan.orden[1] == 1
    assert plan.orden[2] == 2
    assert plan.orden[4] == 3
    assert plan.orden[5] == 4


# ---------------------------------------------------------------------------
# R4 · la regla vale para N cierres en un mes, no solo para dos
# ---------------------------------------------------------------------------


def test_f042_r4_tres_cierres_en_un_mes_dejan_uno_y_descartan_dos():
    """Hoy las 24 colisiones son todas de dos, pero la regla no depende de eso."""
    plan = plan_de_cierres(
        [
            Cierre(7, date(2015, 5, 1), Decimal("10.00")),
            Cierre(8, date(2015, 5, 1), Decimal("20.00")),
            Cierre(9, date(2015, 5, 1), Decimal("30.00")),
            Cierre(10, date(2015, 6, 1), Decimal("40.00")),
        ]
    )

    assert plan.vigente_por_mes[date(2015, 5, 1)] == 9
    assert plan.descartadas == (7, 8)
    assert plan.orden == {9: 7, 10: 8}


def test_f042_r4_con_cuatro_cierres_y_los_dos_modernos_a_cero_gana_el_ultimo_con_dato():
    """R11 y R4 a la vez: se saltan DOS ceros modernos para llegar al que tiene dato."""
    plan = plan_de_cierres(
        [
            Cierre(1, date(2015, 5, 1), Decimal("10.00")),
            Cierre(2, date(2015, 5, 1), Decimal("25.00")),
            Cierre(3, date(2015, 5, 1), Decimal("0.00")),
            Cierre(4, date(2015, 5, 1), Decimal("0.00")),
        ]
    )

    assert plan.vigente_por_mes[date(2015, 5, 1)] == 2
    assert plan.descartadas == (1, 3, 4)
    # La 1 se descarta y está POR DEBAJO de la 2, así que la 2 baja a orden 1:
    # queda como primera fase de la serie y su `LAG` es nulo, que es justo lo
    # que corresponde a un mes sin cierre anterior.
    assert plan.orden == {2: 1}


# ---------------------------------------------------------------------------
# R3 · un mes con un solo cierre no se toca
# ---------------------------------------------------------------------------


def test_f042_r3_una_obra_sin_colisiones_no_cambia_nada():
    """El caso de casi todas las obras: ni un descarte, ni un desplazamiento."""
    cierres = [
        Cierre(n, date(2019, n, 1), Decimal(n * 100)) for n in range(1, 7)
    ]

    plan = plan_de_cierres(cierres)

    assert plan.descartadas == ()
    assert plan.orden == {n: n for n in range(1, 7)}


def test_f042_r3_un_mes_con_un_unico_cierre_a_cero_sobrevive():
    """Sin competencia, el cero no se descarta: no hay «otro» que lo sustituya."""
    plan = plan_de_cierres([Cierre(1, date(2019, 1, 1), Decimal("0.00"))])

    assert plan.descartadas == ()
    assert plan.orden == {1: 1}
    assert plan.vigente_por_mes[date(2019, 1, 1)] == 1


@pytest.mark.parametrize(
    "colision", COLISIONES_CONJUNTO_A, ids=[_ident(c) for c in COLISIONES_CONJUNTO_A]
)
@pytest.mark.parametrize("vacia", ("la primera", "la segunda"))
def test_f042_r10_las_obras_del_conjunto_a_no_pierden_ninguna_fase(
    colision: Colision, vacia: str
):
    """Las 13 obras cuya fase gemela no tiene ni una línea de presupuesto.

    Esa fase no produce filas en `plan_mensual`, así que el mes llega con UN
    cierre y la regla no tiene nada que decidir. Cuál de las dos está vacía no
    lo fija la línea base: se prueban las dos variantes.
    """
    numeros = [numero for numero, _ in colision.fases]
    viva = numeros[1] if vacia == "la primera" else numeros[0]

    plan = plan_de_cierres([Cierre(viva, colision.mes, SIMBOLICO)])

    assert plan.descartadas == ()
    assert plan.orden == {viva: viva}


# ---------------------------------------------------------------------------
# R6 · los huecos que ya trae Sigrid se preservan
# ---------------------------------------------------------------------------


def test_f042_r6_un_hueco_de_origen_sigue_siendo_un_hueco():
    """Fases 1, 2 y 4 sin ningún descarte: la 4 NO pasa a 3.

    Es el motivo por el que el diseño descarta `dense_rank()`. Cerrar este hueco
    cambiaría `importe_mes` de la fase 4 de «acumulado entero» a «diferencia»,
    en una obra que hoy está bien.
    """
    plan = plan_de_cierres(
        [
            Cierre(1, date(2016, 1, 1), Decimal("100.00")),
            Cierre(2, date(2016, 2, 1), Decimal("200.00")),
            Cierre(4, date(2016, 4, 1), Decimal("400.00")),
        ]
    )

    assert plan.descartadas == ()
    assert plan.orden == {1: 1, 2: 2, 4: 4}


def test_f042_r6_un_hueco_de_origen_y_un_descarte_conviven():
    """El hueco se conserva y el descarte desplaza: las dos cosas a la vez.

    Fases 1, 2, 4 y 5 con 4 y 5 en el mismo mes. Se descarta la 4, la 5 baja una
    posición y queda en 4: el hueco entre la 2 y la 4 sigue exactamente donde
    estaba.
    """
    plan = plan_de_cierres(
        [
            Cierre(1, date(2016, 1, 1), Decimal("100.00")),
            Cierre(2, date(2016, 2, 1), Decimal("200.00")),
            Cierre(4, date(2016, 4, 1), Decimal("400.00")),
            Cierre(5, date(2016, 4, 1), Decimal("450.00")),
        ]
    )

    assert plan.descartadas == (4,)
    assert plan.orden == {1: 1, 2: 2, 5: 4}


# ---------------------------------------------------------------------------
# Contrato de la función
# ---------------------------------------------------------------------------


def test_f042_sin_cierres_el_plan_esta_vacio():
    plan = plan_de_cierres([])

    assert plan.descartadas == ()
    assert plan.orden == {}
    assert plan.vigente_por_mes == {}


def test_f042_dos_veces_la_misma_fase_es_un_error_de_quien_llama():
    """Una fase pertenece a UN mes en `stg.fases`. Si llegan dos, el que llamó
    mezcló ámbitos u obras, y seguir adelante daría un orden silenciosamente
    falso."""
    with pytest.raises(ValueError, match="4"):
        plan_de_cierres(
            [
                Cierre(4, date(2016, 1, 1), Decimal("100.00")),
                Cierre(4, date(2016, 2, 1), Decimal("200.00")),
            ]
        )


def test_f042_un_acumulado_ausente_se_trata_como_cero():
    """`COALESCE(SUM(importe_origen_round), 0)`: el oráculo hace lo mismo que el SQL.

    Si todas las líneas de una fase tuvieran importe nulo, `SUM` devolvería NULL
    y en el `ORDER BY ... DESC` de Postgres los nulos van primero: esa fase
    ganaría el mes sin tener dato. El `COALESCE` del SQL lo impide y aquí se
    exige lo mismo.
    """
    plan = plan_de_cierres(
        [
            Cierre(1, date(2016, 1, 1), Decimal("100.00")),
            Cierre(2, date(2016, 1, 1), None),
        ]
    )

    assert plan.vigente_por_mes[date(2016, 1, 1)] == 1
    assert plan.descartadas == (2,)


def test_f042_el_plan_es_inmutable():
    """`PlanCierres` es un valor: nadie puede reescribir el veredicto."""
    from dataclasses import FrozenInstanceError

    plan = plan_de_cierres([Cierre(1, date(2016, 1, 1), Decimal("1.00"))])

    with pytest.raises(FrozenInstanceError):
        plan.descartadas = (1,)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# R8 y R16 · lo que el desplazamiento tiene que dejar intacto
#
# El oráculo no calcula `importe_mes` —eso lo hace el SQL—, pero sí permite
# simularlo, y esa simulación es la que demuestra que renumerar es necesario y
# suficiente. La fórmula es la del fichero: si el orden anterior es el
# consecutivo, diferencia; si no, el acumulado entero.
# ---------------------------------------------------------------------------


def _movimientos(plan, acumulados: dict[int, Decimal]) -> dict[int, Decimal]:
    """`importe_mes` de cada superviviente, tal y como lo calcularía el `LAG`."""
    vivas = sorted(plan.orden)
    movimientos: dict[int, Decimal] = {}
    anterior: int | None = None
    for fase in vivas:
        if anterior is not None and plan.orden[anterior] == plan.orden[fase] - 1:
            movimientos[fase] = acumulados[fase] - acumulados[anterior]
        else:
            movimientos[fase] = acumulados[fase]
        anterior = fase
    return movimientos


#: La serie de la 0499 · VILLANUEVA alrededor de sus dos colisiones.
_0499 = {
    17: Decimal("3000000.00"),
    18: Decimal("3608280.89"),
    19: Decimal("4712823.94"),
    20: Decimal("5065310.42"),
    21: Decimal("5688073.92"),
    22: Decimal("7400000.00"),
}
_CIERRES_0499 = [
    Cierre(17, date(2017, 12, 1), _0499[17]),
    Cierre(18, date(2018, 1, 1), _0499[18]),
    Cierre(19, date(2018, 1, 1), _0499[19]),
    Cierre(20, date(2018, 2, 1), _0499[20]),
    Cierre(21, date(2018, 2, 1), _0499[21]),
    Cierre(22, date(2018, 3, 1), _0499[22]),
]


def test_f042_r8_el_movimiento_del_mes_es_la_suma_de_los_dos_cierres_de_hoy():
    """0499 feb-2018: 352.486,48 + 622.763,50 = 975.249,98.

    Hoy la obra publica DOS filas de febrero, con esos dos movimientos. R8 exige
    que el superviviente publique su suma, y eso es exactamente lo que sale al
    renumerar. Es el número que la ficha de la feature verificó a mano.
    """
    hoy_fase_20 = _0499[20] - _0499[19]
    hoy_fase_21 = _0499[21] - _0499[20]
    assert hoy_fase_20 + hoy_fase_21 == Decimal("975249.98")

    plan = plan_de_cierres(_CIERRES_0499)

    assert _movimientos(plan, _0499)[21] == Decimal("975249.98")


def test_f042_r5_sin_renumerar_el_movimiento_de_febrero_se_multiplica_por_seis():
    """El contrafactual, que es lo que justifica la feature entera.

    Descartando la fase 20 **sin** desplazar el orden, la 21 deja de tener `LAG`
    consecutivo (19 no es 21−1) y febrero pasa de 975.249,98 € a 5.688.073,92 €:
    casi seis veces lo real. Se arreglaría el acumulado y se reventaría el
    movimiento.
    """
    plan = plan_de_cierres(_CIERRES_0499)
    sin_renumerar = type(plan)(
        vigente_por_mes=plan.vigente_por_mes,
        descartadas=plan.descartadas,
        orden={fase: fase for fase in plan.orden},
    )

    assert _movimientos(sin_renumerar, _0499)[21] == Decimal("5688073.92")
    assert _movimientos(plan, _0499)[21] == Decimal("975249.98")


def test_f042_r16_el_telescopio_se_cumple_tras_renumerar():
    """`SUM(importe_mes)` = último `importe_origen` de la serie.

    Es la propiedad que F-006 midió 200/200 y que un desplazamiento mal hecho
    rompería. Vale sin excepción cuando la serie de supervivientes queda
    consecutiva, que es el caso de las 22 obras: sus huecos los crea la regla y
    la regla los cierra.
    """
    plan = plan_de_cierres(_CIERRES_0499)
    movimientos = _movimientos(plan, _0499)

    assert sum(movimientos.values()) == _0499[22]


def test_f042_r6_con_un_hueco_de_origen_el_telescopio_suma_por_tramos():
    """El caso honesto: con un hueco que NO crea la regla, `SUM(importe_mes)` no
    es el último acumulado, y **tampoco lo era antes** de esta feature.

    La serie 1, 2, 4 se parte en dos tramos consecutivos —(1, 2) y (4)— y la suma
    de movimientos es el acumulado del último de cada tramo. Lo que R16 exige es
    que la feature no cambie esto, no que lo arregle: arreglarlo sería
    `dense_rank()`, y eso movería obras que hoy están bien.
    """
    acumulados = {
        1: Decimal("100.00"),
        2: Decimal("200.00"),
        4: Decimal("400.00"),
    }
    plan = plan_de_cierres(
        [Cierre(n, date(2016, n, 1), a) for n, a in acumulados.items()]
    )
    movimientos = _movimientos(plan, acumulados)

    assert sum(movimientos.values()) == acumulados[2] + acumulados[4]
    assert sum(movimientos.values()) != acumulados[4]


# ---------------------------------------------------------------------------
# Invariantes, barridos sobre todas las formas pequeñas
# ---------------------------------------------------------------------------

#: Todas las repartos de 5 fases consecutivas en meses, como cadena de meses:
#: "11223" = fases 1 y 2 en el mes 1, 3 y 4 en el 2, 5 en el 3. Cubre de una
#: pasada el mes único, la pareja, el trío y el cuarteto.
_REPARTOS = (
    "12345", "11234", "12234", "12334", "12344",
    "11123", "11223", "12223", "11233", "12333",
    "11112", "11222", "12222", "11111",
)


@pytest.mark.parametrize("reparto", _REPARTOS)
def test_f042_r5_el_orden_nunca_sube_y_los_supervivientes_quedan_consecutivos(
    reparto: str,
):
    """Dos invariantes que ningún reparto puede romper.

    1. El orden de una fase **nunca es mayor** que su número: se desplaza hacia
       abajo o se queda, jamás hacia arriba.
    2. Si la serie de entrada no tenía huecos, la de supervivientes queda
       consecutiva desde 1. Es la condición que necesita el `LAG`.
    """
    cierres = [
        Cierre(numero, date(2016, int(mes), 1), Decimal(numero * 100))
        for numero, mes in enumerate(reparto, start=1)
    ]

    plan = plan_de_cierres(cierres)

    assert all(plan.orden[f] <= f for f in plan.orden)
    assert sorted(plan.orden.values()) == list(range(1, len(plan.orden) + 1))
    assert len(plan.orden) == len(set(reparto))
    assert len(plan.orden) + len(plan.descartadas) == len(cierres)


@pytest.mark.parametrize("reparto", _REPARTOS)
def test_f042_r1_de_cada_mes_sobrevive_el_de_numero_mayor_cuando_todos_tienen_dato(
    reparto: str,
):
    """Con todos los acumulados distintos de cero, R11 no interviene y el
    criterio queda desnudo: manda el número mayor de cada mes."""
    cierres = [
        Cierre(numero, date(2016, int(mes), 1), Decimal(numero * 100))
        for numero, mes in enumerate(reparto, start=1)
    ]

    plan = plan_de_cierres(cierres)

    for mes, vigente in plan.vigente_por_mes.items():
        del_mes = [c.numero_fase for c in cierres if c.anio_mes == mes]
        assert vigente == max(del_mes)
