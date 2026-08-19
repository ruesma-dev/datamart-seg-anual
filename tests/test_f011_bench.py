# tests/test_f011_bench.py
"""
F-011 · Tests del banco de extracción: resumen de las mediciones por tamaño de
página (R4), cap rechazado sin abortar (R5), latencia máxima frente al timeout
(R5-bis) y el validador que impide mandar a Sigrid algo que no sea un `SELECT`
(R23).

Ninguno abre red: el cliente HTTP va sustituido por un doble que cuenta
peticiones y devuelve filas de mentira. Es lo que permite comprobar el
comportamiento ante un 400 de la API —el caso que más importa y el más difícil
de provocar a mano— sin tocar el SQL Server de producción.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.extraccion import (
    MedicionPagina,
    comparar_cap,
    es_sentencia_de_lectura,
    format_bench,
    resumen_bench,
)


def medicion(
    page_size: int,
    segundos: float,
    filas: int,
    peticiones: int = 1,
    latencia_max_s: float | None = None,
    rechazada: bool = False,
    cap_devuelto: int | None = None,
) -> MedicionPagina:
    return MedicionPagina(
        page_size=page_size,
        peticiones=peticiones,
        filas=filas,
        segundos=segundos,
        latencia_max_s=segundos if latencia_max_s is None else latencia_max_s,
        rechazada=rechazada,
        cap_devuelto=cap_devuelto,
    )


# ---------------------------------------------------------------------------
# R4 · Resumen del barrido: filas/s y mejor tamaño de página
# ---------------------------------------------------------------------------


def test_f011_r4_resumen_calcula_filas_por_segundo_y_el_mejor_tamano() -> None:
    """El mejor tamaño de página es el de más filas/s, no el más grande.

    La distinción es el objeto del barrido: si 20.000 no rinde más que 10.000,
    el coste no está en el transporte y subir `page_size` no compra nada
    (DA-6).
    """
    mediciones = [
        medicion(1_000, 1.0, 1_000),  # 1.000 filas/s
        medicion(10_000, 5.0, 10_000),  # 2.000 filas/s
        medicion(20_000, 20.0, 20_000),  # 1.000 filas/s
    ]

    resumen = resumen_bench(mediciones)

    assert resumen.mejor_page_size == 10_000
    assert resumen.mejor_filas_por_segundo == pytest.approx(2_000.0)
    assert [m.page_size for m in resumen.mediciones] == [1_000, 10_000, 20_000]


def test_f011_r4_las_filas_por_segundo_de_una_medicion_vacia_son_cero() -> None:
    """Una medición sin tiempo (o sin filas) no divide por cero."""
    assert medicion(1_000, 0.0, 1_000).filas_por_segundo == 0.0
    assert medicion(1_000, 2.0, 0).filas_por_segundo == 0.0


def test_f011_r4_la_latencia_media_es_por_peticion() -> None:
    """Con varias repeticiones, la media reparte el tiempo entre peticiones."""
    m = medicion(1_000, 6.0, 3_000, peticiones=3)

    assert m.latencia_media_s == pytest.approx(2.0)


def test_f011_r4_sin_peticiones_la_latencia_media_es_cero() -> None:
    """Un tamaño que la API rechazó de entrada no tiene latencia media."""
    m = medicion(50_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=20_000)

    assert m.latencia_media_s == 0.0
    assert m.filas_por_segundo == 0.0


def test_f011_r4_un_barrido_vacio_no_tiene_mejor_tamano() -> None:
    """Sin mediciones no hay recomendación, y no es una excepción."""
    resumen = resumen_bench([])

    assert resumen.mediciones == ()
    assert resumen.mejor_page_size is None
    assert resumen.mejor_filas_por_segundo == 0.0
    assert "Sin mediciones" in format_bench(resumen, timeout_s=230.0)


# ---------------------------------------------------------------------------
# R5 · Un tamaño rechazado no aborta el barrido, y su cap queda registrado
# ---------------------------------------------------------------------------


def test_f011_r5_los_tamanos_rechazados_no_compiten_por_el_mejor() -> None:
    """Un rechazo no es un resultado de 0 filas/s: queda fuera del ranking."""
    mediciones = [
        medicion(10_000, 5.0, 10_000),
        medicion(50_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=20_000),
    ]

    resumen = resumen_bench(mediciones)

    assert resumen.mejor_page_size == 10_000
    assert resumen.caps_rechazados == (20_000,)
    assert resumen.cap_medido == 20_000


def test_f011_r5_sin_rechazos_no_hay_cap_medido() -> None:
    """Si la API no rechazó nada, el cap real sigue sin acreditar."""
    resumen = resumen_bench([medicion(10_000, 5.0, 10_000)])

    assert resumen.caps_rechazados == ()
    assert resumen.cap_medido is None


def test_f011_r5_el_cap_medido_es_el_menor_de_los_rechazos() -> None:
    """Dos rechazos con caps distintos: manda el más restrictivo."""
    resumen = resumen_bench(
        [
            medicion(30_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=20_000),
            medicion(40_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=15_000),
        ]
    )

    assert resumen.cap_medido == 15_000


# ---------------------------------------------------------------------------
# R5 y DA-6 · El cap documentado y el real no coinciden: hay que decirlo
# ---------------------------------------------------------------------------


def test_f011_r5_el_informe_marca_el_tamano_rechazado_y_su_cap() -> None:
    """El barrido sigue y el rechazo queda escrito, que es lo que pide R5.

    Un tamaño rechazado tiene que verse en la tabla: si se omitiera, quien lea
    el informe creería que solo se probaron los que salieron.
    """
    resumen = resumen_bench(
        [
            medicion(10_000, 5.0, 10_000),
            medicion(50_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=20_000),
        ]
    )

    texto = format_bench(resumen, timeout_s=230.0)

    assert "RECHAZADA" in texto
    assert "50,000" in texto
    assert "cap 20,000" in texto
    # R5: el cap acreditado, en el veredicto y no solo en la fila.
    assert "acredita un cap de 20,000" in texto


def test_f011_r5_un_rechazo_sin_cap_legible_se_dice_asi() -> None:
    """Si el 400 no traía el cap, se escribe «desconocido», no un 0 inventado."""
    resumen = resumen_bench(
        [medicion(50_000, 0.0, 0, peticiones=0, rechazada=True, cap_devuelto=None)]
    )

    texto = format_bench(resumen, timeout_s=230.0)

    assert "cap desconocido" in texto
    assert "acredita un cap" not in texto


def test_f011_r5_comparar_cap_detecta_la_divergencia_de_da6() -> None:
    """`sigrid_api.md` documenta 1.000; el humano confirmó 20.000."""
    divergencia = comparar_cap(medido=20_000, documentado=1_000)

    assert divergencia is not None
    assert divergencia.medido == 20_000
    assert divergencia.documentado == 1_000
    # El mensaje tiene que nombrar al dueño del documento: este proyecto NO lo
    # edita (T8-bis).
    assert "sigrid-api" in divergencia.mensaje


def test_f011_r5_sin_divergencia_no_hay_nada_que_avisar() -> None:
    """Cap medido igual al documentado: `None`, no un objeto vacío."""
    assert comparar_cap(medido=1_000, documentado=1_000) is None


def test_f011_r5_sin_cap_medido_no_se_puede_comparar() -> None:
    """No medir no es lo mismo que coincidir."""
    assert comparar_cap(medido=None, documentado=1_000) is None


# ---------------------------------------------------------------------------
# R5-bis · Latencia máxima observada frente al timeout configurado
# ---------------------------------------------------------------------------


def test_f011_r5bis_registra_latencia_maxima_por_pagina() -> None:
    """La máxima, no la media: el balanceador corta por una petición sola."""
    mediciones = [
        medicion(10_000, 6.0, 30_000, peticiones=3, latencia_max_s=4.0),
        medicion(20_000, 10.0, 40_000, peticiones=2, latencia_max_s=210.0),
    ]

    resumen = resumen_bench(mediciones)

    assert resumen.latencia_max_s == pytest.approx(210.0)


def test_f011_r5bis_el_informe_avisa_si_la_latencia_roza_el_timeout() -> None:
    """210 s con timeout 230 es el aviso que R5-bis existe para dar."""
    resumen = resumen_bench(
        [medicion(20_000, 210.0, 20_000, latencia_max_s=210.0)]
    )

    texto = format_bench(resumen, timeout_s=230.0)

    assert "210" in texto
    assert "230" in texto
    assert "AVISO" in texto


def test_f011_r5bis_con_latencia_holgada_no_hay_aviso() -> None:
    """Sin margen consumido, ni un AVISO: el ruido gratuito no se lee."""
    resumen = resumen_bench([medicion(10_000, 1.0, 10_000, latencia_max_s=1.0)])

    assert "AVISO" not in format_bench(resumen, timeout_s=230.0)


# ---------------------------------------------------------------------------
# R23 · Contra Sigrid, solo SELECT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentencia",
    [
        "SELECT 1",
        "select ide from dbo.obrparpre",
        "  SELECT TOP 100 [ide] FROM [dbo].[con] WHERE [ide] > ? ORDER BY [ide] ASC",
        "-- comentario previo\nSELECT 1",
        "/* comentario */ SELECT 1",
        "SELECT 1;",
        "SELECT 1;   \n  ",
    ],
)
def test_f011_r23_solo_select_contra_sigrid_acepta_lecturas(sentencia: str) -> None:
    """Lo que sí puede salir de aquí hacia `/api/sql/read`."""
    assert es_sentencia_de_lectura(sentencia) is True


@pytest.mark.parametrize(
    "sentencia",
    [
        "",
        "   ",
        "UPDATE dbo.con SET res = 'x'",
        "DELETE FROM dbo.con",
        "INSERT INTO dbo.con (ide) VALUES (1)",
        "TRUNCATE TABLE dbo.con",
        "DROP TABLE dbo.con",
        "ALTER TABLE dbo.con ADD x INT",
        "EXEC sp_who",
        "MERGE dbo.con AS d USING dbo.con AS o ON 1=1",
        "GRANT SELECT ON dbo.con TO publico",
        # Dos sentencias: la segunda escribe. El punto y coma no es una excusa.
        "SELECT 1; DROP TABLE dbo.con",
        "SELECT 1;DELETE FROM dbo.con",
        # SELECT ... INTO crea una tabla en SQL Server: es una ESCRITURA.
        "SELECT * INTO dbo.copia FROM dbo.con",
        # Empieza por algo que no es SELECT aunque acabe leyendo.
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECTX 1",
        "-- solo un comentario",
    ],
)
def test_f011_r23_solo_select_contra_sigrid_rechaza_lo_demas(sentencia: str) -> None:
    """Todo lo que NO puede salir. La lista es el requisito."""
    assert es_sentencia_de_lectura(sentencia) is False


def test_f011_r23_un_nombre_de_columna_no_es_una_palabra_prohibida() -> None:
    """El validador mira palabras completas: `updated_at` no es un UPDATE.

    Control negativo: sin él, el validador podría estar rechazándolo todo y los
    tests de arriba pasarían igual.
    """
    assert es_sentencia_de_lectura(
        "SELECT updated_at, deleted, insertado FROM dbo.con"
    ) is True
