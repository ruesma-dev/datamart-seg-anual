# tests/test_f052_huella_dimension.py
"""
F-052 · La huella de DIMENSIÓN de `stg.partidas` (huella 3, T28, R11).

**Es la que responde al miedo concreto del humano.** Al eximir la campaña de
mutación el 2026-08-31 dijo: *«con respecto a la B es crucial que no cambie o
rompa lo que se está construyendo ahora que está bien; prefiero que se haga una
revisión de datos antes y después que tantos mutation test»*. Las huellas de
dinero no cubren ese miedo entero: una partida que **cambie de sitio en el
árbol sin cambiar de importe** —otro padre, otro nivel, otra ruta— no mueve ni
un euro y sale distinta en Power BI, porque el «Árbol Presupuesto» se dibuja con
`ruta_capitulos` y `nivel`.

Esta huella resume por obra las seis columnas que definen ese sitio
—`codigo_partida`, `capitulo_padre_id`, `capitulo_raiz_id`, `categoria`, `nivel`
y `ruta_capitulos`— en un `md5` sobre las filas ordenadas. Si una sola partida
se mueve, el resumen de su obra cambia y la comparación lo denuncia. Es barata:
390.000 filas resumidas en una por obra.

Sin red ni BBDD: el cliente es un doble que sirve filas enlatadas.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain.huella_ampliada import (
    FORMATO_DIMENSION,
    FilaAmpliada,
    comparar_ampliada,
    formato_de,
    veredicto_ampliado,
)
from etl_sigrid.infrastructure.postgres.cierres_sql import PALABRAS_DE_ESCRITURA
from etl_sigrid.infrastructure.postgres.huella_ampliada import (
    construir_huella_ampliada,
    escribir_csv_ampliada,
    leer_csv_ampliada,
    sql_huella_dimension,
)

#: Las seis columnas que definen dónde está una partida dentro del árbol. Son
#: exactamente las que enumera `design.md` §7, huella 3.
COLUMNAS_DEL_SITIO = (
    "codigo_partida",
    "capitulo_padre_id",
    "capitulo_raiz_id",
    "categoria",
    "nivel",
    "ruta_capitulos",
)

#: Una fila por obra tal y como la devuelve la consulta.
FILA_0599 = (1442383, "0599", 1440, 3, 7, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
FILA_0613 = (1500000, "0613", 3210, 4, 5, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")


class PgFalso:
    """Sirve filas enlatadas y estalla si le piden cualquier otra cosa."""

    def __init__(self, filas):
        self._filas = list(filas)
        self.consultas: list[str] = []
        self.timeouts: list[int] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        self.timeouts.append(timeout_s)
        return self._filas

    def __getattr__(self, nombre: str):
        raise AssertionError(f"la huella es de solo lectura y ha llamado a pg.{nombre}")


# ---------------------------------------------------------------------------
# La consulta
# ---------------------------------------------------------------------------


def test_f052_t28_la_huella_resume_las_seis_columnas_del_sitio():
    """Si faltara una, un movimiento en esa columna sería invisible."""
    sql = sql_huella_dimension()

    for columna in COLUMNAS_DEL_SITIO:
        assert columna in sql, (
            f"la huella de dimensión no mira `{columna}`, así que una partida "
            f"que cambie sólo esa columna pasaría desapercibida"
        )


def test_f052_t28_el_resumen_es_estable_ante_el_orden_de_las_filas():
    """`string_agg(... ORDER BY partida_id)`: sin el `ORDER BY`, Postgres puede
    devolver las filas en otro orden entre dos ejecuciones y el `md5` cambiaría
    sin que se haya movido nada. Una huella que da falsos positivos se acaba
    ignorando, que es peor que no tenerla."""
    sql = sql_huella_dimension()

    assert re.search(r"string_agg\(", sql, re.I)
    assert re.search(r"ORDER\s+BY\s+p\.partida_id", sql, re.I), (
        "el resumen se agrega sin orden estable"
    )
    assert re.search(r"md5\(", sql, re.I)


def test_f052_t28_el_grano_es_la_obra():
    """390.501 filas resumidas en una por obra: es lo que la hace barata."""
    sql = sql_huella_dimension()

    assert "FROM stg.partidas" in sql
    assert re.search(r"GROUP\s+BY\s+p\.obra_id", sql, re.I)


def test_f052_t28_un_nulo_no_puede_tragarse_la_fila_entera():
    """`capitulo_padre_id` es NULL en las raíces. Sin `COALESCE`, concatenar un
    NULL en Postgres devuelve NULL y el resumen de esa obra sería NULL: una
    huella que no compara nada y que parece verde."""
    sql = sql_huella_dimension()

    assert sql.upper().count("COALESCE") >= 5


def test_f052_t28_la_huella_de_dimension_no_escribe():
    texto = sql_huella_dimension().upper()

    for palabra in PALABRAS_DE_ESCRITURA:
        assert not re.search(rf"\b{palabra}\b", texto), f"la huella contiene {palabra}"
    assert "TEMP" not in texto


def test_f052_t28_la_huella_de_dimension_no_filtra_por_obra():
    """Se compara el árbol ENTERO: acotarla a las seis obras afectadas
    convertiría la prueba en una tautología."""
    sql = sql_huella_dimension()

    assert "WHERE" not in sql.upper() or "obra_id = ANY" not in sql


# ---------------------------------------------------------------------------
# La lectura y el CSV
# ---------------------------------------------------------------------------


def test_f052_t28_la_huella_se_lee_de_una_pasada_y_solo_lee():
    pg = PgFalso([FILA_0599, FILA_0613])

    filas = construir_huella_ampliada(pg, FORMATO_DIMENSION, timeout_s=120)

    assert len(pg.consultas) == 1, "una sola consulta: son 390.000 filas agregadas"
    assert pg.timeouts == [120]
    assert [f.codigo_obra for f in filas] == ["0599", "0613"]
    assert filas[0].clave == ("1442383",)


def test_f052_t28_el_csv_va_y_vuelve_sin_perder_nada(tmp_path):
    destino = tmp_path / "huella_dimension.csv"
    filas = construir_huella_ampliada(PgFalso([FILA_0599, FILA_0613]), FORMATO_DIMENSION)

    escribir_csv_ampliada(FORMATO_DIMENSION, filas, destino)
    formato, leidas = leer_csv_ampliada(destino)

    assert formato is FORMATO_DIMENSION
    assert leidas == filas


def test_f052_t28_el_csv_es_el_de_la_casa(tmp_path):
    """UTF-8 con BOM y `;` de separador: convención de Ruesma, se abre en Excel
    ES sin tocar nada."""
    destino = tmp_path / "huella_dimension.csv"
    escribir_csv_ampliada(
        FORMATO_DIMENSION,
        construir_huella_ampliada(PgFalso([FILA_0599]), FORMATO_DIMENSION),
        destino,
    )

    crudo = destino.read_bytes()
    assert crudo.startswith(b"\xef\xbb\xbf")
    cabecera = crudo.decode("utf-8-sig").splitlines()[0]
    assert cabecera.split(";") == list(FORMATO_DIMENSION.cabecera)


def test_f052_t28_una_huella_con_otra_cabecera_se_rechaza(tmp_path):
    """Leer mal un CSV en una prueba de no-regresión es la peor forma posible de
    dar verde."""
    destino = tmp_path / "otra_cosa.csv"
    destino.write_text("a;b;c\n1;2;3\n", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="cabecera"):
        leer_csv_ampliada(destino)


def test_f052_t28_el_formato_se_reconoce_por_su_cabecera():
    assert formato_de(FORMATO_DIMENSION.cabecera) is FORMATO_DIMENSION
    assert formato_de(("obra_id", "lo_que_sea")) is None


# ---------------------------------------------------------------------------
# R11 · la comparación, con tolerancia CERO
# ---------------------------------------------------------------------------


def _fila(codigo_obra: str, resumen: str, partidas: str = "100") -> FilaAmpliada:
    return FilaAmpliada(
        codigo_obra=codigo_obra,
        clave=(codigo_obra,),
        valores=(
            ("codigo_obra", codigo_obra),
            ("partidas", partidas),
            ("raices", "3"),
            ("nivel_max", "5"),
            ("resumen", resumen),
        ),
    )


def test_f052_r11_dos_huellas_identicas_no_producen_ninguna_diferencia():
    filas = (_fila("0599", "aaa"), _fila("0613", "bbb"))

    comparacion = comparar_ampliada(FORMATO_DIMENSION, filas, filas)

    assert comparacion.diferencias == ()
    assert veredicto_ampliado(comparacion, ["0599"])[0] == 0


def test_f052_r11_una_partida_que_se_mueve_sin_cambiar_de_importe_se_caza():
    """**La razón de ser de esta huella.** El importe no aparece por ningún
    lado: lo único que cambia es el resumen del árbol."""
    antes = (_fila("0599", "aaa"), _fila("0613", "bbb"))
    despues = (_fila("0599", "aaa"), _fila("0613", "OTRO"))

    comparacion = comparar_ampliada(FORMATO_DIMENSION, antes, despues)
    codigo, informe = veredicto_ampliado(comparacion, ["0599"])

    assert codigo != 0, "la 0613 se ha movido y no está en la lista esperada"
    assert "0613" in informe
    assert "resumen" in informe


def test_f052_r11_no_hay_umbral_ni_tolerancia():
    """Una sola celda de una obra fuera de la lista detiene la feature. No hay
    porcentaje, no hay «menos de N», no hay redondeo."""
    antes = (_fila("0599", "aaa"), _fila("0613", "bbb", partidas="3210"),)
    despues = (_fila("0599", "aaa"), _fila("0613", "bbb", partidas="3211"),)

    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_DIMENSION, antes, despues), ["0599"]
    )

    assert codigo != 0
    assert "3210" in informe and "3211" in informe


def test_f052_r11_una_obra_esperada_si_puede_moverse():
    antes = (_fila("0599", "aaa"), _fila("0613", "bbb"))
    despues = (_fila("0599", "DISTINTO", partidas="1440"), _fila("0613", "bbb"))

    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_DIMENSION, antes, despues), ["0599"]
    )

    assert codigo == 0
    assert "0599" in informe, "el informe tiene que decir qué se movió, aunque valga"


def test_f052_r11_una_obra_que_aparece_o_desaparece_es_un_cambio():
    """Si sólo se mirara la intersección, una obra que se cae entera pasaría por
    «sin diferencias», que es exactamente el fallo que hay que cazar."""
    antes = (_fila("0599", "aaa"), _fila("0613", "bbb"))
    despues = (_fila("0599", "aaa"),)

    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_DIMENSION, antes, despues), ["0599"]
    )

    assert codigo != 0
    assert "0613" in informe


def test_f052_r11_dos_huellas_vacias_no_pueden_salir_verdes():
    """«0 diferencias» sobre dos ficheros vacíos es indistinguible de «0
    diferencias» sobre 390.501 partidas, y sólo uno de los dos prueba algo."""
    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_DIMENSION, (), ()), ["0599"]
    )

    assert codigo != 0
    assert "vacía" in informe or "vacia" in informe


def test_f052_r11_el_informe_lleva_la_lista_entera_y_no_una_muestra():
    antes = tuple(_fila(f"07{i:02d}", "aaa") for i in range(1, 31))
    despues = tuple(_fila(f"07{i:02d}", f"cambiada-{i}") for i in range(1, 31))

    _codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_DIMENSION, antes, despues), []
    )

    for i in range(1, 31):
        assert f"07{i:02d}" in informe


def test_f052_t28_un_formato_con_una_clave_fuera_de_su_cabecera_se_rechaza():
    """La clave se lee de la cabecera: si nombra una columna que no existe, la
    huella se partiría al leer el primer CSV, y en mitad de una verificación
    manual de 3 h 45."""
    from etl_sigrid.domain.huella_ampliada import FormatoHuella

    with pytest.raises(ValueError, match="clave"):
        FormatoHuella(
            nombre="roto",
            cabecera=("obra_id", "codigo_obra"),
            columnas_clave=("no_existe",),
            proposito="x",
        )


def test_f052_t28_un_formato_sin_codigo_obra_se_rechaza():
    """Sin `codigo_obra` no se puede decidir si la obra que se movió estaba en
    `--obras-esperadas`, que es TODO el criterio de R11."""
    from etl_sigrid.domain.huella_ampliada import FormatoHuella

    with pytest.raises(ValueError, match="codigo_obra"):
        FormatoHuella(
            nombre="roto",
            cabecera=("obra_id", "resumen"),
            columnas_clave=("obra_id",),
            proposito="x",
        )


def test_f052_t28_una_consulta_que_devuelve_otras_columnas_se_rechaza():
    """Si alguien toca el SQL y se deja una columna, es preferible que reviente
    aquí a que la huella se escriba desplazada una posición."""
    pg = PgFalso([(1442383, "0599", 1440)])

    with pytest.raises(ValueError, match="columna"):
        construir_huella_ampliada(pg, FORMATO_DIMENSION)


def test_f052_t28_un_csv_sin_ni_cabecera_se_rechaza(tmp_path):
    destino = tmp_path / "vacio.csv"
    destino.write_text("", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="vacio"):
        leer_csv_ampliada(destino)


def test_f052_t28_un_nulo_de_la_base_se_escribe_como_vacio_y_no_como_None(tmp_path):
    """`None` convertido con `str()` daría la cadena 'None' en el CSV, que en
    una comparación de texto es un valor más y en Excel es basura."""
    from datetime import datetime

    filas = construir_huella_ampliada(
        PgFalso([(1442383, None, 1440, 3, 7, "aaa")]), FORMATO_DIMENSION
    )

    assert filas[0].codigo_obra == ""
    assert "None" not in str(filas[0].valores)

    # Y un `timestamp` se escribe como su fecha, no con la hora pegada.
    from etl_sigrid.infrastructure.postgres.huella_ampliada import _texto

    assert _texto(datetime(2022, 12, 1, 3, 45)) == "2022-12-01"
