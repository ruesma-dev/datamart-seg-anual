# tests/test_f011_perfil.py
"""
F-011 · Tests del perfil de carga: desglose por paso y por tabla (R1), techo de
mejora por paso (R2) y las tablas que acumulan el 80 % de la ingesta (R3).

Ningún test de este fichero abre red ni BBDD: todo lo que se prueba son
funciones puras sobre fixtures. Es deliberado y es el motivo de que el cálculo
viva en el dominio y no dentro del comando de la CLI. La feature entera existe
para responder «¿dónde se va el tiempo?» con un número, así que los números de
estos tests están escritos a mano y comprobados a mano: si el cálculo cambia,
falla el test, no la interpretación de quien lea la tabla.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from etl_sigrid.domain.perfil_carga import (
    PCT_ACUMULADO_OBJETIVO,
    FilaPerfil,
    PerfilCarga,
    format_perfil,
    perfil_de_carga,
    tablas_que_acumulan,
    techo_de_mejora,
)

BATCH = "20260819T020016Z-327ef0"


def fila(step: str, segundos: float, filas: int = 0, stage: str = "ingest") -> FilaPerfil:
    return FilaPerfil(
        stage=stage, step=step, segundos=segundos, filas=filas, status="SUCCESS"
    )


#: La carga real del 2026-08-19 redondeada a minutos exactos, que es la que
#: decide la puerta de R8: ingesta 33 min, build_stg 111 min, build_mart 21 min.
CARGA_REAL = (
    fila("ingest_raw", 33 * 60, 20_050_000),
    fila("build_stg", 111 * 60, 29_590_000, stage="stage"),
    fila("build_mart", 21 * 60, 5_290_000, stage="build_mart"),
)


# ---------------------------------------------------------------------------
# R1 · Desglose por paso de pipeline y por tabla de la ingesta
# ---------------------------------------------------------------------------


def test_f011_r1_desglosa_pasos_y_tablas() -> None:
    """Los pasos de pipeline y las tablas de la ingesta van por separado.

    El criterio de «paso de pipeline» es el mismo que usa `_meta.v_frescura`:
    el `step` no lleva punto. Sin esa separación, sumar la columna de duración
    contaría dos veces el mismo tiempo —el del paso y el de sus sub-pasos— y el
    porcentaje del total saldría mal para todos.
    """
    filas = [
        *CARGA_REAL,
        fila("ingest_raw.obrparpre", 900, 13_760_000),
        fila("ingest_raw.con", 60, 500_000),
        # Sub-paso que NO es de la ingesta: ni paso de pipeline ni tabla.
        fila("build_plan_mensual.tramo_01", 120, 400_000, stage="stage"),
    ]

    perfil = perfil_de_carga(filas, batch_id=BATCH)

    assert perfil.batch_id == BATCH
    assert [p.step for p in perfil.pasos] == ["ingest_raw", "build_stg", "build_mart"]
    assert [t.tabla for t in perfil.tablas] == ["obrparpre", "con"]
    # El total es la suma de los PASOS, no de todas las filas.
    assert perfil.total_segundos == pytest.approx((33 + 111 + 21) * 60)


def test_f011_r1_filas_por_segundo_y_porcentaje_del_total() -> None:
    """Las cuatro cifras de R1: segundos, filas, filas/s y % del total."""
    perfil = perfil_de_carga(CARGA_REAL, batch_id=BATCH)
    ingesta = perfil.pasos[0]

    assert ingesta.filas_por_segundo == pytest.approx(20_050_000 / (33 * 60))
    assert perfil.pct_del_total(ingesta) == pytest.approx(20.0, abs=0.05)
    assert perfil.pct_del_total(perfil.pasos[1]) == pytest.approx(67.3, abs=0.05)
    assert perfil.pct_del_total(perfil.pasos[2]) == pytest.approx(12.7, abs=0.05)


def test_f011_r1_un_paso_sin_cerrar_no_divide_por_cero() -> None:
    """Duración 0 (paso abortado o sin `finished_at`): filas/s es 0, no un error."""
    abortada = FilaPerfil(
        stage="ingest", step="ingest_raw", segundos=0.0, filas=1_000, status="ABORTED"
    )
    perfil = perfil_de_carga([abortada])

    assert abortada.filas_por_segundo == 0.0
    assert perfil.total_segundos == 0.0
    assert perfil.pct_del_total(abortada) == 0.0


def test_f011_r1_sin_filas_el_perfil_esta_vacio_y_lo_dice() -> None:
    """Una base sin `_meta.etl_runs` útil no es un error, es un perfil vacío."""
    perfil = perfil_de_carga([])

    assert perfil.pasos == ()
    assert perfil.tablas == ()
    assert perfil.total_segundos == 0.0
    assert "Sin mediciones" in format_perfil(perfil)


def test_f011_r1_la_fila_de_perfil_es_inmutable() -> None:
    """Un perfil es una medición: nadie lo retoca después de leerlo."""
    with pytest.raises(FrozenInstanceError):
        fila("ingest_raw", 1).segundos = 2  # type: ignore[misc]


def test_f011_r1_solo_el_prefijo_de_ingesta_cuenta_como_tabla() -> None:
    """`tabla` es None en todo lo que no sea `ingest_raw.<tabla>`."""
    assert fila("ingest_raw.con", 1).tabla == "con"
    assert fila("ingest_raw", 1).tabla is None
    assert fila("build_plan_mensual.tramo_01", 1).tabla is None
    # Y el nombre se extrae por longitud del prefijo, no por partir en el
    # primer punto: una tabla con punto en el nombre seguiría entera.
    assert fila("ingest_raw.raro.con", 1).tabla == "raro.con"


# ---------------------------------------------------------------------------
# R2 · Techo de mejora por paso
# ---------------------------------------------------------------------------


def test_f011_r2_techo_de_mejora_por_paso() -> None:
    """Cuánto duraría la carga si cada paso costase cero. Es el número de DA-7.

    Con la carga real del 19-ago: quitar la ingesta entera deja 132 min y
    ahorra 33 (20 %); quitar `build_stg` deja 54 min y ahorra 111 (67 %). Es
    exactamente la aritmética que refuta la sospecha que abrió la feature.
    """
    perfil = perfil_de_carga(CARGA_REAL, batch_id=BATCH)
    techos = {t.paso: t for t in techo_de_mejora(perfil)}

    ingesta = techos["ingest_raw"]
    assert ingesta.total_si_cero_s == pytest.approx(132 * 60)
    assert ingesta.ahorro_min == pytest.approx(33.0)
    assert ingesta.ahorro_pct == pytest.approx(20.0, abs=0.05)

    stg = techos["build_stg"]
    assert stg.total_si_cero_s == pytest.approx(54 * 60)
    assert stg.ahorro_min == pytest.approx(111.0)
    assert stg.ahorro_pct == pytest.approx(67.3, abs=0.05)


def test_f011_r2_el_techo_viene_ordenado_por_ahorro_descendente() -> None:
    """El paso que más cuesta va primero: es la respuesta a «qué ataco»."""
    techos = techo_de_mejora(perfil_de_carga(CARGA_REAL, batch_id=BATCH))

    assert [t.paso for t in techos] == ["build_stg", "ingest_raw", "build_mart"]


def test_f011_r2_sin_tiempo_medido_el_techo_no_revienta() -> None:
    """Total 0 → ahorro 0 %, sin ZeroDivisionError."""
    perfil = perfil_de_carga([fila("ingest_raw", 0.0, 10)])
    techos = techo_de_mejora(perfil)

    assert len(techos) == 1
    assert techos[0].ahorro_pct == 0.0
    assert techos[0].total_si_cero_s == 0.0


def test_f011_r2_los_sub_pasos_no_entran_en_el_techo() -> None:
    """El techo es por PASO. Un tramo de `build_stg` no es un paso."""
    perfil = perfil_de_carga(
        [*CARGA_REAL, fila("ingest_raw.obrparpre", 900, 13_760_000)]
    )

    assert [t.paso for t in techo_de_mejora(perfil)] == [
        "build_stg",
        "ingest_raw",
        "build_mart",
    ]


# ---------------------------------------------------------------------------
# R3 · Cuántas tablas acumulan el 80 % del tiempo de ingesta
# ---------------------------------------------------------------------------


def test_f011_r3_tablas_que_acumulan_el_80_pct() -> None:
    """Si dos tablas se llevan el 80 %, atacar las 31 es trabajo tirado."""
    perfil = perfil_de_carga(
        [
            fila("ingest_raw", 100),
            fila("ingest_raw.obrparpre", 50, 13_760_000),
            fila("ingest_raw.dcapro", 30, 1_130_000),
            fila("ingest_raw.dcfpro", 15, 1_080_000),
            fila("ingest_raw.con", 5, 500_000),
        ]
    )

    # 50 + 30 = 80, que es exactamente el 80 % de los 100 s de ingesta: para
    # ahí. El límite se toma inclusivo a propósito.
    assert tablas_que_acumulan(perfil, 80.0) == ("obrparpre", "dcapro")
    assert tablas_que_acumulan(perfil, 50.0) == ("obrparpre",)
    assert tablas_que_acumulan(perfil, 100.0) == (
        "obrparpre",
        "dcapro",
        "dcfpro",
        "con",
    )


def test_f011_r3_las_tablas_van_ordenadas_por_duracion_descendente() -> None:
    """R3 lo pide explícitamente: la más lenta primero."""
    perfil = perfil_de_carga(
        [
            fila("ingest_raw.con", 5),
            fila("ingest_raw.obrparpre", 50),
            fila("ingest_raw.dcapro", 30),
        ]
    )

    assert [t.tabla for t in perfil.tablas] == ["obrparpre", "dcapro", "con"]


def test_f011_r3_sin_tablas_no_acumula_ninguna() -> None:
    """Perfil sin filas de tabla: tupla vacía, no una excepción."""
    assert tablas_que_acumulan(perfil_de_carga(CARGA_REAL), 80.0) == ()


def test_f011_r3_tablas_a_cero_segundos_no_acumulan_nada() -> None:
    """Ingesta que no llegó a medir: no se puede acumular sobre 0 s."""
    perfil = perfil_de_carga(
        [fila("ingest_raw.con", 0.0), fila("ingest_raw.obr", 0.0)]
    )

    assert tablas_que_acumulan(perfil, 80.0) == ()


@pytest.mark.parametrize("pct", [0.0, -1.0, 100.1, 200.0])
def test_f011_r3_un_porcentaje_imposible_es_un_error_de_programa(pct: float) -> None:
    """El umbral es un porcentaje entre 0 (excluido) y 100. Fuera de ahí, error.

    Es una guardia contra el error de pasar 0,8 creyendo que es «el 80 %»:
    devolvería una sola tabla y nadie lo notaría.
    """
    with pytest.raises(ValueError, match="porcentaje"):
        tablas_que_acumulan(perfil_de_carga(CARGA_REAL), pct)


def test_f011_r3_el_objetivo_por_defecto_es_el_80_por_ciento() -> None:
    """La constante es la del requisito, no una elección del formateador."""
    assert PCT_ACUMULADO_OBJETIVO == 80.0


# ---------------------------------------------------------------------------
# Formato (lo que el humano lee en la consola)
# ---------------------------------------------------------------------------


def test_f011_format_perfil_trae_las_tres_respuestas() -> None:
    """Pasos, tablas y techo, con el número de tablas del 80 % escrito."""
    perfil = perfil_de_carga(
        [
            *CARGA_REAL,
            fila("ingest_raw.obrparpre", 1_600, 13_760_000),
            fila("ingest_raw.con", 380, 500_000),
        ],
        batch_id=BATCH,
    )

    texto = format_perfil(perfil)

    assert BATCH in texto
    assert "obrparpre" in texto
    assert "build_stg" in texto
    # R2: el techo, en minutos y en porcentaje.
    assert "111.0" in texto or "111,0" in texto
    # R3: cuántas tablas acumulan el 80 %.
    assert "1 tabla" in texto and "80" in texto


def test_f011_format_perfil_es_puro_y_no_depende_del_reloj() -> None:
    """Dos llamadas seguidas dan exactamente el mismo texto."""
    perfil = perfil_de_carga(CARGA_REAL, batch_id=BATCH)

    assert format_perfil(perfil) == format_perfil(perfil)


def test_f011_el_perfil_es_inmutable_y_con_tuplas() -> None:
    """`PerfilCarga` es un dato cerrado: nadie le añade pasos después."""
    perfil = perfil_de_carga(CARGA_REAL, batch_id=BATCH)

    assert isinstance(perfil, PerfilCarga)
    assert isinstance(perfil.pasos, tuple)
    assert isinstance(perfil.tablas, tuple)
    with pytest.raises(FrozenInstanceError):
        perfil.total_segundos = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Bordes que la campaña de mutación dejó al descubierto
#
# Los tests de arriba fijaban el comportamiento; estos fijan los LÍMITES. Cada
# uno nació de un mutante que sobrevivió a la primera campaña: el valor 1 donde
# el código compara con 0, el `and` donde hay un `or`, el signo de una suma
# acumulada. No son casos rebuscados: son justo los que separan «funciona» de
# «funciona por casualidad».
# ---------------------------------------------------------------------------


def test_f011_r1_un_paso_de_un_segundo_exacto_si_tiene_ritmo() -> None:
    """1 s no es «sin medir»: la guardia es `<= 0`, no `<= 1`."""
    assert fila("ingest_raw", 1.0, 500).filas_por_segundo == pytest.approx(500.0)


def test_f011_r1_una_carga_de_un_segundo_tiene_porcentajes() -> None:
    """Igual con el total: una carga de 1 s reparte el 100 %, no el 0 %."""
    perfil = perfil_de_carga([fila("ingest_raw", 1.0, 10)])

    assert perfil.pct_del_total(perfil.pasos[0]) == pytest.approx(100.0)


def test_f011_r2_el_techo_de_una_carga_de_un_segundo_no_es_cero() -> None:
    perfil = perfil_de_carga([fila("ingest_raw", 1.0, 10)])

    assert techo_de_mejora(perfil)[0].ahorro_pct == pytest.approx(100.0)


def test_f011_r2_el_techo_es_inmutable() -> None:
    """`TechoPaso` también es una medición cerrada."""
    techo = techo_de_mejora(perfil_de_carga(CARGA_REAL))[0]

    with pytest.raises(FrozenInstanceError):
        techo.ahorro_min = 0.0  # type: ignore[misc]


def test_f011_r3_un_uno_por_ciento_es_un_porcentaje_valido() -> None:
    """El rango válido empieza justo por encima de 0, no de 1."""
    perfil = perfil_de_carga(
        [fila("ingest_raw.obrparpre", 60), fila("ingest_raw.con", 40)]
    )

    assert tablas_que_acumulan(perfil, 1.0) == ("obrparpre",)


def test_f011_r3_una_ingesta_de_un_segundo_sigue_teniendo_cabeza() -> None:
    """Objetivo por debajo de 1 s: sigue habiendo tablas que acumulan."""
    perfil = perfil_de_carga(
        [fila("ingest_raw.obrparpre", 0.6), fila("ingest_raw.con", 0.4)]
    )

    # 80 % de 1,0 s = 0,8 s: con 0,6 no basta, hacen falta las dos.
    assert tablas_que_acumulan(perfil, 80.0) == ("obrparpre", "con")


def test_f011_format_perfil_con_tablas_pero_sin_pasos_no_dice_sin_mediciones() -> None:
    """`perfil-carga` sobre una carga a medias: hay tablas y no hay pasos.

    Pasa de verdad —una ingesta que murió antes de cerrar su fila de paso— y el
    desglose por tabla sigue siendo justo lo que se ha ido a mirar.
    """
    perfil = perfil_de_carga([fila("ingest_raw.obrparpre", 900, 13_760_000)])

    texto = format_perfil(perfil)

    assert "Sin mediciones" not in texto
    assert "obrparpre" in texto


def test_f011_format_perfil_escribe_el_nombre_pelado_de_la_tabla() -> None:
    """En el bloque de tablas va `obrparpre`, no `ingest_raw.obrparpre`.

    La columna es «tabla»: repetir el prefijo del paso en las 31 filas sobra, y
    además rompería el ancho de la columna.
    """
    perfil = perfil_de_carga(
        [fila("ingest_raw", 100), fila("ingest_raw.obrparpre", 100, 13_760_000)]
    )

    lineas = [linea for linea in format_perfil(perfil).splitlines()]
    fila_tabla = [linea for linea in lineas if linea.startswith("obrparpre")]

    assert fila_tabla, f"ninguna línea empieza por el nombre pelado: {lineas}"
    assert not any(linea.startswith("ingest_raw.obrparpre") for linea in lineas)


def test_f011_r3_el_pie_nombra_las_tablas_de_la_cabeza() -> None:
    """La línea de R3 dice CUÁLES son, no solo cuántas."""
    perfil = perfil_de_carga(
        [
            fila("ingest_raw", 100),
            fila("ingest_raw.obrparpre", 50),
            fila("ingest_raw.dcapro", 30),
            fila("ingest_raw.con", 20),
        ]
    )

    pie = [
        linea for linea in format_perfil(perfil).splitlines() if linea.startswith("R3:")
    ]

    assert len(pie) == 1
    assert "obrparpre, dcapro" in pie[0]
    assert pie[0].startswith("R3: 2 tablas de 3 acumulan el 80 %")


def test_f011_r3_el_singular_solo_se_usa_con_una_tabla() -> None:
    """«1 tabla» y «2 tablas»: el plural se comprueba en los dos sentidos."""
    una = perfil_de_carga(
        [
            fila("ingest_raw", 100),
            fila("ingest_raw.obrparpre", 90),
            fila("ingest_raw.con", 10),
        ]
    )
    dos = perfil_de_carga(
        [
            fila("ingest_raw", 100),
            fila("ingest_raw.obrparpre", 50),
            fila("ingest_raw.dcapro", 30),
            fila("ingest_raw.con", 20),
        ]
    )

    assert "R3: 1 tabla de 2 acumulan" in format_perfil(una)
    assert "R3: 2 tablas de 3 acumulan" in format_perfil(dos)


def test_f011_format_perfil_acumula_hasta_el_cien_por_cien() -> None:
    """La columna `%_acum` suma hacia arriba y cierra en 100,0.

    Si acumulara restando —o si el porcentaje se calculara con división
    entera— la última fila no daría 100,0 y la tabla mentiría en silencio.
    """
    perfil = perfil_de_carga(
        [
            fila("ingest_raw", 100),
            fila("ingest_raw.obrparpre", 75),
            fila("ingest_raw.con", 25),
        ]
    )

    lineas = format_perfil(perfil).splitlines()
    obrparpre = next(x for x in lineas if x.startswith("obrparpre"))
    con = next(x for x in lineas if x.startswith("con "))

    # 75 % y 25 % de la ingesta; acumulado 75 % y 100 %.
    assert obrparpre.split()[-2:] == ["75.0", "75.0"] or "75.0" in obrparpre
    assert "100.0" in con, f"la última fila no cierra en 100 %: {con}"
    assert "25.0" in con


def test_f011_format_perfil_con_ingesta_de_un_segundo_reparte_de_verdad() -> None:
    """Ingesta total de 1 s: los porcentajes siguen siendo 100 %, no 0 %."""
    perfil = perfil_de_carga(
        [fila("ingest_raw", 1.0), fila("ingest_raw.con", 1.0)]
    )

    con = next(x for x in format_perfil(perfil).splitlines() if x.startswith("con "))

    assert "100.0" in con


def test_f011_format_perfil_con_tablas_a_cero_no_divide_por_cero() -> None:
    """Ingesta que no llegó a medir: 0 % en vez de una excepción."""
    perfil = perfil_de_carga(
        [fila("ingest_raw", 10), fila("ingest_raw.con", 0.0)]
    )

    texto = format_perfil(perfil)

    assert "con" in texto
    assert "R3: 0 tablas" in texto
