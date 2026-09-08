# tests/test_f066_tolerancia_recuentos.py
"""
F-066 · `check-raw-recuentos` con **tolerancia con dirección** (R15, R16, R17).

**El criterio que había era inalcanzable por diseño.** El comando salía con
código 1 en cuanto una sola tabla no cuadraba al alma, y eso no puede pasar
nunca: Sigrid es un ERP vivo que se sigue usando mientras el datamart es una
foto de un instante. Medido el 2026-09-08, con la ingesta de las 11:16-11:57
UTC y el verificador pasado unas cinco horas después:

    31 iguales · 25 distintas · 0 ausentes · 0 sin medir      -> código 1

Las 25 «distintas» eran trabajo real en el origen y no un fallo, y se sabe por
la **firma**: 25 de 25 con Sigrid POR ENCIMA de `raw` y ninguna al revés, con
4.883 filas sobre 25.287.500 (0,0193 %) y una peor tabla, `obrparpre`, en
+3.969 sobre 13.884.933 (0,0286 %). Un guardián que se pone rojo todas las
noches se deja de mirar, y entonces no guarda nada.

**La regla nueva mira la dirección antes que la magnitud:**

* Sigrid con **más** filas que `raw` es la deriva normal, y se acepta mientras
  quede por debajo de la tolerancia **relativa de cada tabla**.
* Sigrid con **menos** filas que `raw` es alarma **inmediata**, sea de una
  fila: eso no es deriva. Es un borrado en origen, una ingesta duplicada o una
  carga que metió lo que no era, y hasta hoy se confundía con lo demás.
* `ausentes` y `sin_medir` siguen siendo fallo, como siempre.

Sin red ni BBDD: dominio puro y dobles.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.recuentos import (
    ESTADO_AUSENTE,
    ESTADO_DERIVA,
    ESTADO_FALTAN,
    ESTADO_OK,
    ESTADO_SIN_MEDIR,
    ESTADO_SOBRAN,
    TOLERANCIA_DERIVA_PCT,
    comparar_recuentos,
    formatear,
)

# ---------------------------------------------------------------------------
# El caso real del 2026-09-08, con sus cifras
# ---------------------------------------------------------------------------

#: Las cinco tablas cuya desviación se midió una a una ese día:
#: `(tabla, filas en Sigrid, filas de más en Sigrid)`.
_MEDIDAS = (
    ("obrparpre", 13_884_933, 3_969),  # la peor: 0,0286 %
    ("con", 2_192_308, 171),           # 0,0078 %
    ("apu", 2_154_543, 151),
    ("dcfpro", 1_700_000, 170),
    ("dcapro", 1_600_000, 159),
)

#: Las otras veinte que también derivaron, con desviaciones más pequeñas.
_RESTO = (*[(f"t{i:02d}", 186_235, 13) for i in range(19)], ("t19", 186_251, 16))

#: Y las treinta y una que cuadraron al alma.
_IGUALES = tuple((f"q{i:02d}", 1_000, 0) for i in range(31))


def _caso_real() -> tuple[list[str], dict[str, int], dict[str, int]]:
    """Las 56 tablas de aquella pasada: 31 iguales y 25 con deriva."""
    filas = _MEDIDAS + _RESTO + _IGUALES
    declaradas = [t for t, _, _ in filas]
    sigrid = {t: n for t, n, _ in filas}
    raw = {t: n - d for t, n, d in filas}
    return declaradas, sigrid, raw


def test_f066_r15_el_caso_real_del_2026_09_08_tiene_las_cifras_que_se_midieron() -> None:
    """Control del fixture: si estos números no son los medidos, los tests de
    abajo no demuestran nada sobre el día que motivó el cambio."""
    _, sigrid, raw = _caso_real()
    total_sigrid = sum(sigrid.values())
    desviadas = sum(1 for t in sigrid if sigrid[t] != raw[t])
    total_diferencia = sum(sigrid[t] - raw[t] for t in sigrid)

    assert (len(sigrid), desviadas) == (56, 25)
    assert total_sigrid == 25_287_500
    assert total_diferencia == 4_883
    assert round(100 * total_diferencia / total_sigrid, 4) == 0.0193
    assert all(sigrid[t] >= raw[t] for t in sigrid), "ninguna al revés, ese día"


# ---------------------------------------------------------------------------
# R15 · la deriva normal está conforme; la dirección contraria, nunca
# ---------------------------------------------------------------------------


def test_f066_r15_el_dia_real_con_25_tablas_derivadas_sale_conforme() -> None:
    """0,0193 % global y 0,0286 % la peor tabla: es una foto de un ERP vivo."""
    informe = comparar_recuentos(*_caso_real())

    assert informe.ok, "el criterio de antes ponía rojo un día perfectamente normal"
    assert len(informe.toleradas) == 25
    assert len(informe.iguales) == 31
    assert informe.faltantes == ()
    assert informe.sobrantes == ()


def test_f066_r15_una_sola_tabla_con_menos_filas_en_sigrid_lo_tumba_todo() -> None:
    """Mismo día, misma deriva diminuta, y UNA fila de menos en Sigrid.

    Una sola fila sobre 2,15 millones es 0,00005 %: por magnitud pasaría
    cualquier umbral. Por dirección, no pasa ninguno.
    """
    declaradas, sigrid, raw = _caso_real()
    raw["apu"] = sigrid["apu"] + 1

    informe = comparar_recuentos(declaradas, sigrid, raw)

    assert not informe.ok
    assert informe.sobrantes == (("apu", 2_154_543, 2_154_544),)
    assert informe.faltantes == (), "no es «faltan filas»: es que sobran en raw"


def test_f066_r15_la_direccion_manda_sobre_la_magnitud() -> None:
    """La misma fila, en un lado y en el otro, da dos veredictos distintos."""
    grande = 13_884_933

    de_mas = comparar_recuentos(["obrparpre"], {"obrparpre": grande}, {"obrparpre": grande - 1})
    de_menos = comparar_recuentos(["obrparpre"], {"obrparpre": grande}, {"obrparpre": grande + 1})

    assert de_mas.ok, "una fila nueva en Sigrid es que alguien está trabajando"
    assert not de_menos.ok, "una fila que raw tiene y Sigrid no, no se explica sola"


@pytest.mark.parametrize("raw_filas", [0, 1, 999_999])
def test_f066_r15_sigrid_con_menos_filas_es_alarma_sea_cual_sea_la_magnitud(raw_filas) -> None:
    informe = comparar_recuentos(["dcf"], {"dcf": 0}, {"dcf": raw_filas})

    assert informe.ok == (raw_filas == 0)
    assert (informe.sobrantes != ()) == (raw_filas > 0)


# ---------------------------------------------------------------------------
# R16 · la tolerancia es relativa y por tabla, y su frontera está donde dice
# ---------------------------------------------------------------------------


def test_f066_r16_la_desviacion_se_mide_contra_la_cifra_de_sigrid() -> None:
    """`obrparpre` el 2026-09-08: 3.969 sobre 13.884.933."""
    informe = comparar_recuentos(
        ["obrparpre"], {"obrparpre": 13_884_933}, {"obrparpre": 13_880_964}
    )
    (recuento,) = informe.recuentos

    assert recuento.diferencia == 3_969
    assert round(recuento.desviacion_pct, 4) == 0.0286


def test_f066_r16_la_desviacion_justo_en_el_umbral_esta_dentro() -> None:
    """La frontera es inclusiva: 0,05 % de 1.000.000 son 500 filas."""
    informe = comparar_recuentos(
        ["t"], {"t": 1_000_000}, {"t": 999_500}, tolerancia_pct=0.05
    )

    assert informe.ok
    assert informe.toleradas == (("t", 1_000_000, 999_500),)


def test_f066_r16_una_fila_mas_alla_del_umbral_ya_no_esta_dentro() -> None:
    informe = comparar_recuentos(
        ["t"], {"t": 1_000_000}, {"t": 999_499}, tolerancia_pct=0.05
    )

    assert not informe.ok
    assert informe.faltantes == (("t", 1_000_000, 999_499),)
    assert informe.toleradas == ()


def test_f066_r16_el_umbral_es_relativo_a_cada_tabla_y_no_al_total() -> None:
    """El motivo de que sea relativo y por tabla: 50 filas no significan lo
    mismo en una tabla de 13 millones que en un catálogo de 200."""
    informe = comparar_recuentos(
        ["obrparpre", "conest"],
        {"obrparpre": 13_884_933, "conest": 200},
        {"obrparpre": 13_884_883, "conest": 150},
    )

    assert informe.toleradas == (("obrparpre", 13_884_933, 13_884_883),)
    assert informe.faltantes == (("conest", 200, 150),)
    assert not informe.ok, "el 25 % de un catálogo no se pierde por deriva"


def test_f066_r16_con_tolerancia_cero_vuelve_a_exigirse_exactitud() -> None:
    """La regla de antes sigue disponible, y es un valor de la opción."""
    informe = comparar_recuentos(
        *_caso_real(), tolerancia_pct=0.0
    )

    assert not informe.ok
    assert len(informe.faltantes) == 25
    assert informe.toleradas == ()


def test_f066_r16_la_tolerancia_por_defecto_cae_en_la_unica_ventana_util() -> None:
    """El valor por defecto no es un número redondo elegido a ojo.

    Por abajo tiene que dejar pasar el peor día medido (`obrparpre`, 0,0286 %)
    con margen; por arriba tiene que seguir cazando una **página perdida** de
    la ingesta —10.000 filas, el `page_size` de sigrid-api— en la tabla más
    grande del YAML, que son 10.000/13.884.933 = 0,072 %. Entre esos dos
    números no cabe casi nada, y ahí está el defecto.
    """
    peor_dia_medido = 100 * 3_969 / 13_884_933
    pagina_perdida = 100 * 10_000 / 13_884_933

    umbral = TOLERANCIA_DERIVA_PCT

    assert umbral >= peor_dia_medido * 1.5, "se pondría rojo un día normal"
    assert umbral < pagina_perdida, "no vería una página perdida"


def test_f066_r16_una_pagina_perdida_de_la_ingesta_no_pasa_la_tolerancia() -> None:
    """El mismo argumento, pero comprobado sobre el veredicto y no sobre el
    número: 10.000 filas menos en la tabla más grande tienen que salir rojas."""
    informe = comparar_recuentos(
        ["obrparpre"], {"obrparpre": 13_884_933}, {"obrparpre": 13_874_933}
    )

    assert not informe.ok
    assert informe.faltantes == (("obrparpre", 13_884_933, 13_874_933),)


# ---------------------------------------------------------------------------
# R17 · lo que la tolerancia NO tapa
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sigrid, raw, campo",
    [
        ({"t": 1_000}, {"t": None}, "ausentes"),
        ({"t": None}, {"t": 1_000}, "sin_medir"),
    ],
)
def test_f066_r17_una_tolerancia_enorme_no_tapa_un_ausente_ni_un_sin_medir(
    sigrid, raw, campo
) -> None:
    informe = comparar_recuentos(["t"], sigrid, raw, tolerancia_pct=100.0)

    assert not informe.ok
    assert getattr(informe, campo) == ("t",)


def test_f066_r17_la_tabla_que_nace_vacia_en_raw_no_es_deriva() -> None:
    """`raw` a cero contra 193 filas en Sigrid es el 100 % de desviación."""
    informe = comparar_recuentos(["conest"], {"conest": 193}, {"conest": 0})

    assert informe.faltantes == (("conest", 193, 0),)
    assert not informe.ok


# ---------------------------------------------------------------------------
# El estado de cada tabla, que es lo que se lee en la línea
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sigrid, raw, estado",
    [
        (1_000_000, 1_000_000, ESTADO_OK),
        (1_000_000, 999_800, ESTADO_DERIVA),
        (1_000_000, 990_000, ESTADO_FALTAN),
        (1_000_000, 1_000_001, ESTADO_SOBRAN),
        (1_000_000, None, ESTADO_AUSENTE),
        (None, 1_000_000, ESTADO_SIN_MEDIR),
    ],
)
def test_f066_r16_cada_tabla_lleva_su_estado(sigrid, raw, estado) -> None:
    informe = comparar_recuentos(["t"], {"t": sigrid}, {"t": raw})

    assert informe.recuentos[0].estado == estado


def test_f066_r16_los_seis_estados_son_textos_distintos() -> None:
    """Si dos coincidieran, la salida mentiría sin que ningún test lo notara."""
    estados = [
        ESTADO_OK, ESTADO_DERIVA, ESTADO_FALTAN,
        ESTADO_SOBRAN, ESTADO_AUSENTE, ESTADO_SIN_MEDIR,
    ]

    assert len(set(estados)) == len(estados)


# ---------------------------------------------------------------------------
# R15 · lo que se lee a las tres de la mañana
# ---------------------------------------------------------------------------


def test_f066_r15_la_salida_separa_lo_tolerado_de_lo_que_no_lo_esta() -> None:
    informe = comparar_recuentos(
        ["a", "b", "c"],
        {"a": 1_000_000, "b": 1_000_000, "c": 1_000_000},
        {"a": 999_800, "b": 990_000, "c": 1_000_050},
    )

    texto = formatear(informe)

    assert "1 con deriva tolerada" in texto
    assert "1 con filas que faltan" in texto
    assert "1 con filas que sobran" in texto


def test_f066_r15_la_salida_dice_el_umbral_que_ha_aplicado() -> None:
    """Sin el umbral en la salida, un verde no se puede interpretar."""
    texto = formatear(comparar_recuentos(["a"], {"a": 10}, {"a": 10}, tolerancia_pct=0.25))

    assert "0,2500 %" in texto


def test_f066_r15_la_salida_grita_cuando_sigrid_tiene_menos_filas() -> None:
    """El caso grave no puede quedarse en una línea más de la tabla."""
    informe = comparar_recuentos(["apu"], {"apu": 2_154_543}, {"apu": 2_154_544})

    texto = formatear(informe)

    assert "SIGRID TIENE MENOS FILAS QUE raw" in texto
    assert "NO CONFORME" in texto


def test_f066_r15_un_dia_normal_lo_dice_sin_rodeos() -> None:
    texto = formatear(comparar_recuentos(*_caso_real()))

    assert "CONFORME" in texto
    assert "NO CONFORME" not in texto
    assert "SIGRID TIENE MENOS FILAS QUE raw" not in texto


def test_f066_r15_la_linea_de_cada_tabla_lleva_su_desviacion() -> None:
    informe = comparar_recuentos(
        ["obrparpre"], {"obrparpre": 13_884_933}, {"obrparpre": 13_880_964}
    )

    linea = next(ln for ln in formatear(informe).splitlines() if ln.startswith("  "))

    assert "0,0286 %" in linea
    assert ESTADO_DERIVA in linea


def test_f066_r16_una_tabla_vaciada_en_origen_se_lee_al_cien_por_cien() -> None:
    """Sigrid a cero y `raw` con 193 filas: la desviación es del 100 %.

    Es el único sitio donde no se puede dividir por la cifra de Sigrid, y la
    respuesta correcta no es «0 %» ni un error: sobra la tabla entera.
    """
    informe = comparar_recuentos(["conest"], {"conest": 0}, {"conest": 193})

    linea = next(ln for ln in formatear(informe).splitlines() if ln.startswith("  "))

    assert informe.recuentos[0].desviacion_pct == 100.0
    assert "100,0000 %" in linea
    assert ESTADO_SOBRAN in linea


def test_f066_r16_dos_ceros_son_iguales_y_no_una_division_por_cero() -> None:
    """Una tabla vacía en los dos lados cuadra, y su desviación es cero."""
    informe = comparar_recuentos(["t"], {"t": 0}, {"t": 0})

    assert informe.iguales == ("t",)
    assert informe.recuentos[0].desviacion_pct == 0.0
    assert informe.peor is None, "sin desviación no hay «peor tabla» que enseñar"


def test_f066_r15_la_salida_dice_cuanto_hace_de_la_ultima_ingesta() -> None:
    """La deriva esperable es proporcional al tiempo: 0,03 % cinco horas
    después de la ingesta es normal; cinco minutos después, no."""
    informe = comparar_recuentos(["a"], {"a": 10}, {"a": 10})

    assert "4,6 h" in formatear(informe, horas_desde_ingesta=4.62)
    assert "desconocido" in formatear(informe, horas_desde_ingesta=None)


# ---------------------------------------------------------------------------
# El comando: dobles de solo lectura (R18 sigue en pie)
# ---------------------------------------------------------------------------


class FrescuraDoble:
    """Una fila de `_meta.v_frescura`, con lo poco que se le mira."""

    def __init__(self, paso: str, horas: float | None) -> None:
        self.paso = paso
        self.horas_desde_ultimo_ok = horas


class PgDoble:
    """Solo lo que un comando de lectura puede pedir. Lo demás, revienta."""

    def __init__(self, filas: dict[str, int | None], frescura=None) -> None:
        self._filas = filas
        self._frescura = frescura
        self.consultadas: list[str] = []

    def table_exists(self, schema: str, table: str) -> bool:
        return self._filas.get(table) is not None

    def count_rows(self, schema: str, table: str) -> int:
        self.consultadas.append(table)
        return int(self._filas[table])

    def fetch_frescura(self):
        if isinstance(self._frescura, Exception):
            raise self._frescura
        return self._frescura or []

    def __getattr__(self, nombre: str):
        raise AssertionError(f"solo lectura, y ha llamado a pg.{nombre}")


class ApiDoble:
    def __init__(self, filas: dict[str, int | None]) -> None:
        self._filas = filas

    def leer_sql(self, sql: str, parameters=None, max_rows=None) -> dict:
        tabla = sql.split("[dbo].[", 1)[1].split("]", 1)[0]
        return {"ok": True, "columns": ["n"], "rows": [[self._filas.get(tabla)]], "row_count": 1}

    def __enter__(self) -> ApiDoble:
        return self

    def __exit__(self, *args) -> None:
        return None

    def __getattr__(self, nombre: str):
        raise AssertionError(f"solo lectura, y ha llamado a api.{nombre}")


class LoggingDoble:
    log_level = "WARNING"
    log_format = "console"


class SettingsDoble:
    def __init__(self, tablas: list[dict]) -> None:
        self.tables_sigrid = {"tables": tablas}
        self.logging = LoggingDoble()


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(sigrid: dict, raw: dict, frescura=None):
        tablas = [
            {"source_table": t, "target_table": t, "where": None, "exclude_columns": []}
            for t in sigrid
        ]
        pg = PgDoble(raw, frescura)
        monkeypatch.setattr(main, "get_settings", lambda: SettingsDoble(tablas))
        monkeypatch.setattr(main, "_get_api", lambda: ApiDoble(sigrid))
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner(), pg

    return _con


def test_f066_r15_el_dia_real_sale_con_codigo_0(cli) -> None:
    _, sigrid, raw = _caso_real()
    runner, _ = cli(sigrid, raw)

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 0, resultado.output
    assert "CONFORME" in resultado.output


def test_f066_r15_una_tabla_con_menos_filas_en_sigrid_sale_con_codigo_1(cli) -> None:
    _, sigrid, raw = _caso_real()
    raw["apu"] = sigrid["apu"] + 1
    runner, _ = cli(sigrid, raw)

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 1
    assert ESTADO_SOBRAN in resultado.output


def test_f066_r15_la_tolerancia_se_puede_apretar_desde_la_linea_de_ordenes(cli) -> None:
    """Mismo día, mismo dato, y el veredicto cambia porque lo pide quien mira."""
    _, sigrid, raw = _caso_real()
    runner, _ = cli(sigrid, raw)

    apretado = runner.invoke(main.cli, ["check-raw-recuentos", "--tolerancia-pct", "0"])
    holgado = runner.invoke(main.cli, ["check-raw-recuentos", "--tolerancia-pct", "1"])

    assert apretado.exit_code == 1
    assert holgado.exit_code == 0, holgado.output


def test_f066_r15_el_comando_cuenta_las_horas_desde_la_ultima_ingesta(cli) -> None:
    runner, _ = cli({"a": 10}, {"a": 10}, frescura=[FrescuraDoble("ingest_raw", 4.62)])

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 0, resultado.output
    assert "4,6 h" in resultado.output


def test_f066_r15_si_no_se_puede_leer_la_frescura_el_veredicto_no_cambia(cli) -> None:
    """El contexto es contexto: que falte no puede volver rojo un día bueno,
    ni verde uno malo."""
    runner, _ = cli({"a": 10}, {"a": 10}, frescura=RuntimeError("no existe la vista"))

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 0, resultado.output
    assert "desconocido" in resultado.output
