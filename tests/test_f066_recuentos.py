# tests/test_f066_recuentos.py
"""
F-066 · `check-raw-recuentos`: ¿está en `raw` lo mismo que hay en Sigrid?
(R15 a R18).

**Por qué hace falta un comando y no una consulta a mano.** Una ingesta puede
terminar «en verde» y dejar media tabla: un `COPY` cortado, un timeout del
balanceador a los 230 s, una página perdida. `check-coherencia` mira de qué
carga viene cada tabla y `check-frescura` cuánto hace que no hay build; ninguno
compara el **número de filas** con el origen. Con 56 tablas, esa comparación a
mano no se hace nunca.

**La lección que hereda de `check-cobertura` (2026-09-02)**: si Sigrid rechaza o
corta un `COUNT(*)`, esa tabla queda `sin_medir` y el comando **sale con código
1**. «No he podido mirar» no es «está bien», y un guardián que confunde las dos
cosas es peor que no tenerlo, porque se le cree.

Aquí no se abre ninguna conexión ni sale un solo byte a la red: los dos clientes
son dobles que sirven cifras enlatadas y **estallan si alguien les pide algo que
un comando de solo lectura no debería pedir** —`record_run_start` el primero—.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.recuentos import (
    ESTADO_AUSENTE,
    ESTADO_DISTINTA,
    ESTADO_OK,
    ESTADO_SIN_MEDIR,
    InformeRecuentos,
    comparar_recuentos,
    formatear,
)
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiBusinessError

# ---------------------------------------------------------------------------
# R16 · el veredicto es dominio puro: los cuatro casos
# ---------------------------------------------------------------------------


def test_f066_r16_todo_cuadra_y_el_informe_esta_conforme() -> None:
    informe = comparar_recuentos(
        ["apu", "res"], {"apu": 2_154_543, "res": 2_610}, {"apu": 2_154_543, "res": 2_610}
    )

    assert informe.ok
    assert informe.iguales == ("apu", "res")
    assert informe.distintas == ()
    assert informe.ausentes == ()
    assert informe.sin_medir == ()


def test_f066_r16_una_tabla_a_medias_sale_en_distintas_con_las_dos_cifras() -> None:
    """El caso que motiva el comando: la ingesta terminó y faltan 43 filas."""
    informe = comparar_recuentos(["dcf"], {"dcf": 165_391}, {"dcf": 165_348})

    assert not informe.ok
    assert informe.distintas == (("dcf", 165_391, 165_348),)
    assert informe.iguales == ()


def test_f066_r16_una_tabla_que_no_existe_en_raw_sale_en_ausentes() -> None:
    """Distinto de «tiene 0 filas»: la tabla no se ha creado nunca."""
    informe = comparar_recuentos(["conest"], {"conest": 193}, {"conest": None})

    assert not informe.ok
    assert informe.ausentes == ("conest",)
    assert informe.distintas == ()


def test_f066_r16_una_tabla_vacia_en_raw_no_es_una_tabla_ausente() -> None:
    """Cero filas es una cifra, y se compara como tal."""
    informe = comparar_recuentos(["conest"], {"conest": 193}, {"conest": 0})

    assert informe.ausentes == ()
    assert informe.distintas == (("conest", 193, 0),)


def test_f066_r16_el_informe_respeta_el_orden_del_yaml() -> None:
    """No alfabético: el orden en que están declaradas, que es como se leen."""
    declaradas = ["con", "obr", "apu", "asi"]
    filas = dict.fromkeys(declaradas, 1)

    informe = comparar_recuentos(declaradas, filas, filas)

    assert informe.iguales == tuple(declaradas)
    assert [r.tabla for r in informe.recuentos] == declaradas


def test_f066_r16_una_tabla_declarada_sin_dato_en_ninguno_de_los_dos_lados() -> None:
    """Si Sigrid no respondió, no se sabe nada de `raw`: manda `sin_medir`."""
    informe = comparar_recuentos(["apu"], {"apu": None}, {"apu": None})

    assert informe.sin_medir == ("apu",)
    assert informe.ausentes == ()


def test_f066_r16_una_tabla_que_no_esta_en_los_mapas_queda_sin_medir() -> None:
    """Un mapa incompleto no puede pasar por «todo cuadra»."""
    informe = comparar_recuentos(["apu", "apa"], {"apu": 10}, {"apu": 10})

    assert informe.sin_medir == ("apa",)
    assert not informe.ok


# ---------------------------------------------------------------------------
# R17 · «no he podido mirar» no es «está bien»
# ---------------------------------------------------------------------------


def test_f066_r17_una_tabla_sin_medir_deja_el_informe_no_conforme() -> None:
    informe = comparar_recuentos(
        ["apu", "res"], {"apu": None, "res": 2_610}, {"apu": 1, "res": 2_610}
    )

    assert informe.sin_medir == ("apu",)
    assert informe.iguales == ("res",)
    assert not informe.ok, (
        "un COUNT(*) que Sigrid no contestó no puede contar como cuadrado: es "
        "la lección de `check-cobertura` del 2026-09-02"
    )


@pytest.mark.parametrize(
    "sigrid, raw",
    [
        ({"t": 1}, {"t": 2}),      # distinta
        ({"t": 1}, {"t": None}),   # ausente
        ({"t": None}, {"t": 1}),   # sin medir
    ],
)
def test_f066_r17_cualquier_hallazgo_rompe_la_conformidad(sigrid, raw) -> None:
    assert not comparar_recuentos(["t"], sigrid, raw).ok


def test_f066_r17_un_informe_vacio_esta_conforme() -> None:
    """Control del `ok`: sin tablas declaradas no hay nada que denunciar."""
    informe = comparar_recuentos([], {}, {})

    assert informe.ok
    assert informe.recuentos == ()


# ---------------------------------------------------------------------------
# R15 · una línea por tabla, con las dos cifras
# ---------------------------------------------------------------------------


def test_f066_r15_el_formato_saca_una_linea_por_tabla_en_orden() -> None:
    informe = comparar_recuentos(
        ["apu", "dcf", "conest", "apa"],
        {"apu": 2_154_543, "dcf": 165_391, "conest": 193, "apa": None},
        {"apu": 2_154_543, "dcf": 165_348, "conest": None, "apa": 1},
    )

    texto = formatear(informe)
    cuerpo = [ln for ln in texto.splitlines() if ln.startswith("  ")]

    assert [ln.split()[0] for ln in cuerpo] == ["apu", "dcf", "conest", "apa"]


def test_f066_r15_cada_linea_dice_su_veredicto_y_sus_cifras() -> None:
    informe = comparar_recuentos(
        ["apu", "dcf", "conest", "apa"],
        {"apu": 2_154_543, "dcf": 165_391, "conest": 193, "apa": None},
        {"apu": 2_154_543, "dcf": 165_348, "conest": None, "apa": 1},
    )

    lineas = {ln.split()[0]: ln for ln in formatear(informe).splitlines() if ln.startswith("  ")}

    assert ESTADO_OK in lineas["apu"]
    assert ESTADO_DISTINTA in lineas["dcf"]
    assert "165391" in lineas["dcf"].replace(".", "")
    assert "165348" in lineas["dcf"].replace(".", "")
    assert ESTADO_AUSENTE in lineas["conest"]
    assert ESTADO_SIN_MEDIR in lineas["apa"]


def test_f066_r15_el_resumen_final_cuenta_las_cuatro_categorias() -> None:
    informe = comparar_recuentos(
        ["a", "b", "c", "d"],
        {"a": 1, "b": 1, "c": 1, "d": None},
        {"a": 1, "b": 2, "c": None, "d": 1},
    )

    texto = formatear(informe)

    assert "1 iguales" in texto
    assert "1 distintas" in texto
    assert "1 ausentes" in texto
    assert "1 sin medir" in texto


def test_f066_r15_un_informe_conforme_lo_dice_sin_rodeos() -> None:
    texto = formatear(comparar_recuentos(["a"], {"a": 1}, {"a": 1}))

    assert "4 iguales" not in texto
    assert "1 iguales" in texto


# ---------------------------------------------------------------------------
# Los dobles: solo lectura, y lo demuestran estallando
# ---------------------------------------------------------------------------


class ApiDoble:
    """Sirve un `COUNT(*)` enlatado por tabla. Cualquier otra llamada revienta."""

    def __init__(self, filas: dict[str, int | None]) -> None:
        self._filas = filas
        self.consultas: list[str] = []
        self.max_rows: list[int | None] = []

    def leer_sql(self, sql: str, parameters=None, max_rows=None) -> dict:
        self.consultas.append(sql)
        self.max_rows.append(max_rows)
        tabla = sql.split("[dbo].[", 1)[1].split("]", 1)[0]
        valor = self._filas.get(tabla)
        if isinstance(valor, Exception):
            raise valor
        return {"ok": True, "columns": ["n"], "rows": [[valor]], "row_count": 1}

    def __enter__(self) -> ApiDoble:
        return self

    def __exit__(self, *args) -> None:
        return None

    def __getattr__(self, nombre: str):
        raise AssertionError(
            f"`check-raw-recuentos` es de solo lectura y ha llamado a api.{nombre}"
        )


class PgDoble:
    """Solo `table_exists` y `count_rows`. `record_run_start` revienta (R18)."""

    def __init__(self, filas: dict[str, int | None]) -> None:
        self._filas = filas
        self.consultadas: list[str] = []

    def table_exists(self, schema: str, table: str) -> bool:
        assert schema == "raw", f"solo se mira `raw`, no `{schema}`"
        return self._filas.get(table) is not None

    def count_rows(self, schema: str, table: str) -> int:
        self.consultadas.append(table)
        return int(self._filas[table])

    def __getattr__(self, nombre: str):
        raise AssertionError(
            f"`check-raw-recuentos` es de solo lectura y ha llamado a pg.{nombre}"
        )


class LoggingDoble:
    """Lo que el grupo `cli` mira antes de despachar el subcomando."""

    log_level = "WARNING"
    log_format = "console"


class SettingsDoble:
    def __init__(self, tablas: list[dict]) -> None:
        self.tables_sigrid = {"tables": tablas}
        self.logging = LoggingDoble()


def _tabla(source: str, where: str | None = None) -> dict:
    return {
        "source_table": source,
        "target_table": source,
        "id_column": "ide",
        "incremental_column": None,
        "where": where,
        "exclude_columns": [],
    }


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(tablas: list[dict], sigrid: dict, raw: dict):
        api, pg = ApiDoble(sigrid), PgDoble(raw)
        monkeypatch.setattr(main, "get_settings", lambda: SettingsDoble(tablas))
        monkeypatch.setattr(main, "_get_api", lambda: api)
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner(), api, pg

    return _con


# ---------------------------------------------------------------------------
# R15, R18 · el comando
# ---------------------------------------------------------------------------


def test_f066_r15_el_comando_esta_registrado() -> None:
    resultado = CliRunner().invoke(main.cli, ["check-raw-recuentos", "--help"])

    assert resultado.exit_code == 0
    assert "raw" in resultado.output.lower()


def test_f066_r15_todo_cuadrado_sale_con_codigo_0(cli) -> None:
    runner, _, _ = cli([_tabla("apu"), _tabla("res")], {"apu": 10, "res": 3},
                       {"apu": 10, "res": 3})

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 0, resultado.output
    assert "apu" in resultado.output
    assert "res" in resultado.output


def test_f066_r15_una_tabla_a_medias_sale_con_codigo_1(cli) -> None:
    runner, _, _ = cli([_tabla("apu")], {"apu": 10}, {"apu": 9})

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 1
    assert ESTADO_DISTINTA in resultado.output


def test_f066_r15_una_tabla_que_falta_en_raw_sale_con_codigo_1(cli) -> None:
    runner, _, pg = cli([_tabla("conest")], {"conest": 193}, {"conest": None})

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 1
    assert ESTADO_AUSENTE in resultado.output
    assert pg.consultadas == [], "no se cuenta una tabla que no existe"


def test_f066_r15_el_count_lleva_el_where_declarado(cli) -> None:
    """Comparar el universo entero de Sigrid contra un `raw` filtrado daría
    siempre distinto, y el guardián se volvería ruido que nadie mira."""
    runner, api, _ = cli([_tabla("con", where="tip = 16")], {"con": 5}, {"con": 5})

    runner.invoke(main.cli, ["check-raw-recuentos"])

    assert any("WHERE tip = 16" in c for c in api.consultas), api.consultas


def test_f066_r15_sin_where_no_se_inventa_un_where(cli) -> None:
    runner, api, _ = cli([_tabla("apu")], {"apu": 1}, {"apu": 1})

    runner.invoke(main.cli, ["check-raw-recuentos"])

    assert api.consultas and all("WHERE" not in c for c in api.consultas)


def test_f066_r17_si_sigrid_rechaza_un_count_el_barrido_sigue_y_sale_1(cli) -> None:
    """La tabla que falló queda `sin_medir` y las de después se miden igual."""
    runner, api, _ = cli(
        [_tabla("apu"), _tabla("res")],
        {"apu": SigridApiBusinessError("consulta rechazada"), "res": 3},
        {"apu": 10, "res": 3},
    )

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 1
    assert ESTADO_SIN_MEDIR in resultado.output
    assert len(api.consultas) == 2, "el barrido se paró en la primera que falló"


def test_f066_r18_el_comando_no_registra_ninguna_ejecucion(cli) -> None:
    """El doble de Postgres estalla ante cualquier método que no sea
    `table_exists` o `count_rows`, `record_run_start` incluido."""
    runner, _, pg = cli([_tabla("apu")], {"apu": 10}, {"apu": 10})

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert resultado.exit_code == 0, resultado.output
    assert pg.consultadas == ["apu"]


def test_f066_r18_el_comando_solo_manda_selects_a_sigrid(cli) -> None:
    runner, api, _ = cli([_tabla("apu")], {"apu": 1}, {"apu": 1})

    runner.invoke(main.cli, ["check-raw-recuentos"])

    for consulta in api.consultas:
        assert consulta.strip().upper().startswith("SELECT")
        assert "COUNT(*)" in consulta.upper()


def test_f066_r18_control_el_doble_de_postgres_muerde() -> None:
    """Sin esto, el test de R18 pasaría aunque el doble no vigilara nada."""
    pg = PgDoble({"apu": 1})

    with pytest.raises(AssertionError, match="record_run_start"):
        pg.record_run_start("ingest", "x", "y")


def test_f066_r18_control_el_doble_de_sigrid_muerde() -> None:
    api = ApiDoble({"apu": 1})

    with pytest.raises(AssertionError, match="fetch_table_schema"):
        api.fetch_table_schema("apu")


# ---------------------------------------------------------------------------
# El informe es inmutable: nadie lo retoca después de emitido
# ---------------------------------------------------------------------------


def test_f066_r16_el_informe_es_inmutable() -> None:
    informe = comparar_recuentos(["apu"], {"apu": 1}, {"apu": 1})

    assert isinstance(informe, InformeRecuentos)
    with pytest.raises((AttributeError, TypeError)):
        informe.iguales = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Los dos supervivientes de la campaña de mutación (2026-09-06)
# ---------------------------------------------------------------------------
#
# La campaña dejó vivos tres mutantes sobre el comando. Dos eran huecos de
# verdad y los cierran estas dos comprobaciones; el tercero —`bold=True` del
# título— es decoración y se justifica en `progress/impl_F-066.md`.


def test_f066_r18_el_count_no_pide_a_sigrid_mas_de_una_fila(cli) -> None:
    """Superviviente `max_rows=1 -> max_rows=2`.

    Un `COUNT(*)` devuelve una fila y solo una. Pedir más no cambia el
    resultado hoy, pero Sigrid **corta por filas y por tiempo** —tope duro de
    10.000 filas por petición y 230 s de balanceador—, y este comando manda 56
    consultas seguidas: el tope de una fila es lo que garantiza que ninguna de
    ellas pueda traerse un resultado grande por accidente.
    """
    runner, api, _ = cli([_tabla("apu")], {"apu": 1}, {"apu": 1})

    runner.invoke(main.cli, ["check-raw-recuentos"])

    assert api.max_rows == [1], (
        f"el COUNT(*) pidió {api.max_rows} filas; un recuento pide una"
    )


def test_f066_r15_el_aviso_de_una_tabla_sin_medir_no_ensucia_el_informe(cli) -> None:
    """Superviviente `err=True -> err=False`.

    El aviso de que Sigrid no contestó va a **stderr**, y no por gusto: la
    salida estándar es el informe tabla a tabla, que alguien puede redirigir a
    un fichero o pegar en un parte. Un aviso suelto en medio de la tabla la
    rompe justo la noche en que hay algo que mirar.
    """
    runner, _, _ = cli(
        [_tabla("apu")],
        {"apu": SigridApiBusinessError("consulta rechazada")},
        {"apu": 10},
    )

    resultado = runner.invoke(main.cli, ["check-raw-recuentos"])

    assert "Sigrid no contestó" in resultado.stderr
    assert "Sigrid no contestó" not in resultado.stdout, (
        "el aviso se ha colado en el informe, que es lo que se lee y se comparte"
    )
    assert ESTADO_SIN_MEDIR in resultado.stdout, "el informe sí va a la salida estándar"
