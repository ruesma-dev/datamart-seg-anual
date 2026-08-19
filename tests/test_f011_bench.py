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

from pathlib import Path

import pytest

from etl_sigrid.domain.extraccion import (
    MedicionPagina,
    comparar_cap,
    es_sentencia_de_lectura,
    format_bench,
    resumen_bench,
)
from etl_sigrid.infrastructure.sigrid.bench_extraccion import (
    barrer_paginas,
    escribir_csv_bench,
)
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
    SigridApiPageSizeTooLargeError,
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


# ---------------------------------------------------------------------------
# R4 · El adaptador: barre tamaños de página contra sigrid-api, sin Postgres
#
# El doble de API no habla HTTP: recibe el SQL ya construido y devuelve filas.
# Es lo que permite comprobar el caso que de verdad importa —un 400 con el cap
# a mitad del barrido— sin lanzar una sola petición al SQL Server de producción.
# ---------------------------------------------------------------------------


class ApiFalsa:
    """Doble de `SigridApiClient` para el banco: cuenta peticiones y consume
    tiempo de un reloj de mentira."""

    def __init__(
        self,
        cap: int | None = None,
        segundos_por_peticion: float = 1.0,
        filas_disponibles: int = 1_000_000,
    ) -> None:
        self.cap = cap
        self.segundos_por_peticion = segundos_por_peticion
        self.filas_disponibles = filas_disponibles
        self.sql_enviado: list[str] = []
        self.max_rows_pedidos: list[int | None] = []
        self.reloj = 0.0

    def leer_sql(
        self,
        sql: str,
        parameters: list | None = None,
        max_rows: int | None = None,
    ) -> dict:
        self.sql_enviado.append(sql)
        self.max_rows_pedidos.append(max_rows)
        if self.cap is not None and max_rows is not None and max_rows > self.cap:
            raise SigridApiPageSizeTooLargeError(requested=max_rows, cap=self.cap)

        self.reloj += self.segundos_por_peticion
        desde = int(parameters[0]) if parameters else 0
        cuantas = max(0, min(max_rows or 0, self.filas_disponibles - desde))
        filas = [[desde + i + 1, 46_200.5] for i in range(cuantas)]
        return {"columns": ["ide", "tiemod"], "rows": filas, "row_count": cuantas}


def test_f011_r4_bench_mide_cada_tamano_de_pagina(monkeypatch) -> None:
    """Una petición por tamaño, con su tiempo y sus filas."""
    api = ApiFalsa(segundos_por_peticion=2.0)

    mediciones = barrer_paginas(
        api,
        "obrparpre",
        columnas=["ide", "tiemod"],
        tamanos=[1_000, 10_000],
        reloj=lambda: api.reloj,
    )

    assert [m.page_size for m in mediciones] == [1_000, 10_000]
    assert [m.filas for m in mediciones] == [1_000, 10_000]
    assert [m.peticiones for m in mediciones] == [1, 1]
    assert all(m.segundos == pytest.approx(2.0) for m in mediciones)
    assert all(m.latencia_max_s == pytest.approx(2.0) for m in mediciones)
    assert not any(m.rechazada for m in mediciones)


def test_f011_r4_el_sql_del_bench_es_el_mismo_que_usa_la_ingesta() -> None:
    """`SELECT TOP n ... WHERE [ide] > ? ORDER BY [ide] ASC`, keyset como el ETL.

    Medir con otra forma de consulta mediría otra cosa: el objeto del barrido
    es saber qué haría la ingesta real con páginas más grandes.
    """
    api = ApiFalsa()

    barrer_paginas(
        api, "obrparpre", columnas=["ide", "tiemod"], tamanos=[5_000],
        reloj=lambda: api.reloj,
    )

    sql = api.sql_enviado[0]
    assert sql.startswith("SELECT TOP 5000 ")
    assert "[ide], [tiemod]" in sql
    assert "FROM [dbo].[obrparpre]" in sql
    assert "WHERE [ide] > ?" in sql
    assert "ORDER BY [ide] ASC" in sql
    assert api.max_rows_pedidos == [5_000]


def test_f011_r4_varias_repeticiones_avanzan_el_cursor() -> None:
    """Repetir no es pedir la misma página: avanza por keyset, como la ingesta.

    Si repitiera la misma página, la segunda mediría la caché del SQL Server y
    el número saldría bonito y falso.
    """
    api = ApiFalsa(segundos_por_peticion=1.5)

    (medicion,) = barrer_paginas(
        api, "con", columnas=["ide"], tamanos=[1_000], repeticiones=3,
        reloj=lambda: api.reloj,
    )

    assert medicion.peticiones == 3
    assert medicion.filas == 3_000
    assert medicion.segundos == pytest.approx(4.5)
    assert medicion.latencia_media_s == pytest.approx(1.5)


def test_f011_r4_una_tabla_que_se_acaba_corta_las_repeticiones() -> None:
    """Página corta = no queda más tabla: deja de pedir en vez de girar en vacío."""
    api = ApiFalsa(filas_disponibles=1_500)

    (medicion,) = barrer_paginas(
        api, "cen", columnas=["ide"], tamanos=[1_000], repeticiones=5,
        reloj=lambda: api.reloj,
    )

    assert medicion.peticiones == 2
    assert medicion.filas == 1_500


def test_f011_r5_cap_rechazado_no_aborta_el_bench() -> None:
    """El 400 de la API se anota con su cap y el barrido continúa (R5).

    Es el requisito con más valor operativo del bloque A: sin él, medir hasta
    20.000 contra una API capada a 10.000 no devolvería ningún dato, solo una
    excepción.
    """
    api = ApiFalsa(cap=10_000)

    mediciones = barrer_paginas(
        api,
        "obrparpre",
        columnas=["ide"],
        tamanos=[1_000, 10_000, 20_000],
        reloj=lambda: api.reloj,
    )

    assert len(mediciones) == 3
    assert [m.rechazada for m in mediciones] == [False, False, True]
    assert mediciones[2].cap_devuelto == 10_000
    assert mediciones[2].peticiones == 0
    assert resumen_bench(mediciones).cap_medido == 10_000


def test_f011_r23_el_bench_no_manda_a_sigrid_nada_que_no_sea_select() -> None:
    """El SQL del bench pasa por el validador antes de salir.

    Se comprueba desde fuera: si alguien cambiara el constructor de la
    consulta por algo que no empiece por SELECT, `barrer_paginas` tiene que
    negarse en vez de enviarlo.
    """
    api = ApiFalsa()

    with pytest.raises(ValueError, match="lectura"):
        barrer_paginas(
            api,
            "obrparpre; DROP TABLE dbo.con --",
            columnas=["ide"],
            tamanos=[1_000],
            reloj=lambda: api.reloj,
        )

    assert api.sql_enviado == []


def test_f011_r4_bench_no_escribe_en_postgres() -> None:
    """Barrido de imports: el adaptador del bench no conoce Postgres.

    No es un detalle de estilo. `bench-sigrid` se lanza contra el SQL Server de
    producción para medir; si de paso pudiera escribir en el datamart, dejaría
    de ser un comando de diagnóstico.
    """
    import ast

    ruta = (
        Path(__file__).resolve().parents[1]
        / "etl_sigrid" / "infrastructure" / "sigrid" / "bench_extraccion.py"
    )
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))

    # Se miran los IMPORTS y los identificadores, no el texto entero: el propio
    # docstring del módulo explica que no toca Postgres y un `in fuente` daría
    # un falso positivo con su propia explicación.
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.append(nodo.module or "")
            modulos.extend(alias.name for alias in nodo.names)

    assert modulos, "el módulo no importa nada: ¿se ha vaciado el fichero?"
    for modulo in modulos:
        assert "postgres" not in modulo.lower(), (
            f"bench_extraccion.py importa '{modulo}': el banco de extracción "
            f"no toca el datamart"
        )
        assert "psycopg" not in modulo.lower(), (
            f"bench_extraccion.py importa '{modulo}': el banco de extracción "
            f"no toca el datamart"
        )

    identificadores = {
        nodo.id for nodo in ast.walk(arbol) if isinstance(nodo, ast.Name)
    }
    assert "PostgresClient" not in identificadores


def test_f011_r4_el_csv_del_bench_sigue_la_convencion_de_ruesma(tmp_path) -> None:
    """UTF-8 con BOM y `;` como separador, como el resto de CSV del proyecto."""
    salida = tmp_path / "bench.csv"
    escribir_csv_bench(
        [medicion(1_000, 1.0, 1_000), medicion(20_000, 0.0, 0, peticiones=0,
                                                rechazada=True, cap_devuelto=10_000)],
        salida,
    )

    crudo = salida.read_bytes()
    assert crudo.startswith(b"\xef\xbb\xbf")

    texto = salida.read_text(encoding="utf-8-sig")
    assert texto.splitlines()[0].startswith("page_size;")
    assert ";1000;" in texto.replace("\r", "") or "1000;" in texto
    assert "10000" in texto


def test_f011_r4_un_barrido_sin_columnas_es_un_error_de_programa() -> None:
    """Sin columnas no hay consulta que medir: falla antes de tocar la red."""
    api = ApiFalsa()

    with pytest.raises(ValueError, match="columnas"):
        barrer_paginas(api, "con", columnas=[], tamanos=[1_000], reloj=lambda: api.reloj)

    assert api.sql_enviado == []


def test_f011_r23_la_puerta_del_cliente_rechaza_lo_que_no_es_lectura() -> None:
    """`SigridApiClient.leer_sql` valida ANTES de enviar (R23).

    Se comprueba sobre el cliente de verdad, no sobre un doble: es la única
    puerta pública por la que sale SQL que el propio cliente no ha construido,
    y si no validara, el validador del dominio sería decorativo. No se abre
    ninguna conexión: la excepción salta antes de llegar al `_post_sql`.
    """
    from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
        SigridApiClient,
        SigridApiSentenciaNoDeLecturaError,
    )

    cliente = SigridApiClient(
        base_url="https://sigrid-api.example",
        function_key="clave-de-mentira",  # nunca una credencial real en un test
        database="sigrid",
    )

    enviado: list[dict] = []
    cliente._post_sql = lambda **kwargs: enviado.append(kwargs) or {"ok": True}  # type: ignore[method-assign]

    with pytest.raises(SigridApiSentenciaNoDeLecturaError) as excinfo:
        cliente.leer_sql("DROP TABLE dbo.con")

    assert "SELECT" in str(excinfo.value)
    assert excinfo.value.sql == "DROP TABLE dbo.con"
    assert enviado == [], "la sentencia rechazada llegó a enviarse"

    # Control negativo: una lectura legítima SÍ pasa. Sin esto, un validador
    # que dijera «no» a todo pasaría el test de arriba tan ricamente.
    cliente.leer_sql("SELECT TOP 1 [ide] FROM [dbo].[con]", parameters=[0], max_rows=1)

    assert len(enviado) == 1
    assert enviado[0]["max_rows"] == 1
    cliente.close()


# ---------------------------------------------------------------------------
# Bordes que la campaña de mutación dejó al descubierto
# ---------------------------------------------------------------------------


def test_f011_r4_las_mediciones_son_inmutables() -> None:
    """Las tres piezas del banco son datos cerrados: nadie las retoca."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        medicion(1_000, 1.0, 1_000).filas = 2  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        resumen_bench([]).mejor_page_size = 1  # type: ignore[misc]

    divergencia = comparar_cap(medido=20_000, documentado=1_000)
    assert divergencia is not None
    with pytest.raises(FrozenInstanceError):
        divergencia.medido = 1  # type: ignore[misc]


def test_f011_r4_una_peticion_de_un_segundo_exacto_si_tiene_ritmo() -> None:
    """1 s y 1 fila no son «sin medir»: las guardias comparan con 0, no con 1."""
    assert medicion(1_000, 1.0, 1_000).filas_por_segundo == pytest.approx(1_000.0)
    assert medicion(1_000, 2.0, 1).filas_por_segundo == pytest.approx(0.5)


def test_f011_r4_una_sola_peticion_tiene_latencia_media() -> None:
    """Con una petición, la media es el tiempo de esa petición."""
    assert medicion(1_000, 6.0, 3_000, peticiones=1).latencia_media_s == pytest.approx(6.0)


def test_f011_r5_solo_los_rechazos_aportan_cap() -> None:
    """Un tamaño admitido no aporta cap aunque traiga el campo relleno.

    Es lo que separa «la API me dijo su límite» de «alguien dejó un número
    ahí»: solo el 400 acredita el cap.
    """
    resumen = resumen_bench(
        [medicion(10_000, 5.0, 10_000, rechazada=False, cap_devuelto=20_000)]
    )

    assert resumen.caps_rechazados == ()
    assert resumen.cap_medido is None


def test_f011_r5bis_el_aviso_salta_justo_en_el_umbral() -> None:
    """Al 80 % exacto del timeout ya hay aviso: el corte es `>=`, no `>`."""
    justo = resumen_bench([medicion(20_000, 184.0, 20_000, latencia_max_s=184.0)])
    debajo = resumen_bench([medicion(20_000, 183.9, 20_000, latencia_max_s=183.9)])

    assert "AVISO" in format_bench(justo, timeout_s=230.0)
    assert "AVISO" not in format_bench(debajo, timeout_s=230.0)


def test_f011_r5bis_el_aviso_dice_qué_porcentaje_del_timeout_se_consumio() -> None:
    """210 s de 230 son el 91 %, y el número tiene que salir escrito."""
    resumen = resumen_bench([medicion(20_000, 210.0, 20_000, latencia_max_s=210.0)])

    assert "91 % del timeout" in format_bench(resumen, timeout_s=230.0)


def test_f011_r4_medir_pagina_pide_una_sola_pagina_por_defecto() -> None:
    """El valor por defecto es UNA petición: medir es barato salvo que se pida más."""
    from etl_sigrid.infrastructure.sigrid.bench_extraccion import medir_pagina

    api = ApiFalsa(segundos_por_peticion=1.0)
    m = medir_pagina(
        api, "con", columnas=["ide"], page_size=1_000, reloj=lambda: api.reloj
    )

    assert m.peticiones == 1
    assert len(api.sql_enviado) == 1


def test_f011_r4_el_csv_del_bench_crea_los_directorios_que_falten(tmp_path) -> None:
    """`--out informes/2026/bench.csv` no puede fallar por una carpeta ausente."""
    salida = tmp_path / "informes" / "2026" / "bench.csv"

    escribir_csv_bench([medicion(1_000, 1.0, 1_000)], salida)

    assert salida.is_file()


def test_f011_r4_el_log_del_banco_no_vuelca_nueve_decimales() -> None:
    """La latencia se registra con milisegundos, no con la basura del reloj.

    `perf_counter` da del orden de 1e-7 s de resolución; volcarla entera al log
    llena la línea de dígitos que no significan nada y hace ilegible la salida
    del job, que es donde después se lee la medición. Tres decimales = un
    milisegundo, que es de sobra para medir peticiones HTTP.
    """
    from structlog.testing import capture_logs

    from etl_sigrid.infrastructure.sigrid.bench_extraccion import medir_pagina

    api = ApiFalsa()
    tiempos = iter([0.0, 0.123456789])

    with capture_logs() as capturado:
        medir_pagina(
            api,
            "con",
            columnas=["ide"],
            page_size=1_000,
            reloj=lambda: next(tiempos),
        )

    paginas = [linea for linea in capturado if linea.get("event") == "bench_pagina"]

    assert len(paginas) == 1
    assert paginas[0]["segundos"] == 0.123


def test_f011_r23_el_error_no_vuelca_la_consulta_entera() -> None:
    """Una sentencia larga se trunca en el mensaje: el log no es un volcado.

    El SQL rechazado puede ser de miles de caracteres —una consulta generada—,
    y el mensaje va a un log que alguien tiene que leer.
    """
    from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
        LONGITUD_SQL_EN_ERROR,
        SigridApiSentenciaNoDeLecturaError,
    )

    largo = "DROP TABLE dbo." + "x" * 1_000
    mensaje = str(SigridApiSentenciaNoDeLecturaError(largo))

    assert LONGITUD_SQL_EN_ERROR == 200
    assert largo[:LONGITUD_SQL_EN_ERROR] in mensaje
    assert largo[: LONGITUD_SQL_EN_ERROR + 1] not in mensaje
