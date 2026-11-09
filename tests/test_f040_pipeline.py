# tests/test_f040_pipeline.py
"""F-040 · `build_ventas` en el pipeline (R26), sin red ni BBDD.

Esquema MÓDULO como `postventa` y `contabilidad`: va en `run-all` tras
`build_retenciones`, depende solo de `ingest_raw`, nadie depende de él (si
falla, la noche sigue) y recrea tablas y vistas con DROP + CREATE (está en
`PASOS_CON_PERMISOS`). Construye dos esquemas: `ventas` y `ventas_restringida`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "ventas"
FICHEROS = [
    "00_setup.sql", "01_clientes.sql", "02_facturas.sql", "03_certificaciones.sql",
    "04_enlace.sql", "05_vistas.sql", "06_restringida.sql", "07_guardas.sql",
]
#: Lo que se cuenta tras cada sub-paso (setup, vistas y guardas no cuentan).
CONTADOS = [
    ("ventas", "clientes"), ("ventas", "facturas"), ("ventas", "certificaciones"),
    ("ventas", "certificacion_factura"), ("ventas_restringida", "clientes_contacto"),
]


def _pasos():
    import main

    ajustes = SimpleNamespace(
        postgres=SimpleNamespace(), sigrid=SimpleNamespace(), etl=SimpleNamespace(),
    )
    return main.build_pipeline_steps(ajustes)


# ===========================================================================
# El paso
# ===========================================================================


def test_f040_r26_nombre_stage_y_dependencias() -> None:
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep

    paso = BuildVentasStep(SimpleNamespace())
    assert paso.name == "build_ventas"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["ingest_raw"]


def test_f040_r26_los_ocho_sub_pasos_en_orden_y_existen() -> None:
    from etl_sigrid.application.steps import build_ventas_step

    assert [s.sql_file for s in build_ventas_step.SUB_PASOS] == FICHEROS
    assert sorted(p.name for p in DIR_SQL.glob("*.sql")) == FICHEROS
    assert build_ventas_step.DIR_SQL_VENTAS == DIR_SQL
    for sub in build_ventas_step.SUB_PASOS:
        assert (DIR_SQL / sub.sql_file).exists(), sub.sql_file


def test_f040_r26_cada_sub_paso_cuenta_en_su_esquema() -> None:
    from etl_sigrid.application.steps import build_ventas_step

    esquemas = {s.target_schema for s in build_ventas_step.SUB_PASOS if s.target_schema}
    assert esquemas == {"ventas", "ventas_restringida"}
    restringida = [s for s in build_ventas_step.SUB_PASOS if s.target_schema == "ventas_restringida"]
    assert [s.sql_file for s in restringida] == ["06_restringida.sql"]


class _PgFalso:
    def __init__(self, falla_en: str = "") -> None:
        self.falla_en = falla_en
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)
        if path.name == self.falla_en:
            raise RuntimeError("F-040 R25: ventas.facturas tiene 3 filas y raw.dvf 4")

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return 3


def test_f040_r26_el_paso_encadena_sus_ocho_sql_y_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_ventas_step
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso()
    monkeypatch.setattr(build_ventas_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildVentasStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS
    assert pg.contados == CONTADOS
    assert resultado.rows_processed == 3 * len(CONTADOS)
    assert resultado.finished_at is not None


@pytest.mark.parametrize(("fichero", "sub"), [("07_guardas.sql", "guardas"),
                                               ("02_facturas.sql", "facturas")])
def test_f040_r25_un_sql_que_revienta_da_failed_con_su_sub_paso_y_la_cifra(
    monkeypatch: pytest.MonkeyPatch, fichero: str, sub: str,
) -> None:
    from etl_sigrid.application.steps import build_ventas_step
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso(falla_en=fichero)
    monkeypatch.setattr(build_ventas_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildVentasStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith(f"Fallo en {sub}: ")
    assert "raw.dvf 4" in resultado.error_message, "la cifra de la guarda llega al log"
    assert pg.ejecutados[-1] == fichero, "no sigue tras el fallo"
    assert resultado.finished_at is not None


def test_f040_r26_un_sql_que_falta_da_failed_con_la_ruta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_ventas_step
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep, _SubStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso()
    monkeypatch.setattr(build_ventas_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(build_ventas_step, "SUB_PASOS",
                        (_SubStep(name="x", sql_file="99_no_existe.sql"),))
    resultado = BuildVentasStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert "99_no_existe.sql" in resultado.error_message and pg.ejecutados == []
    assert resultado.finished_at is not None


def test_f040_r26_solo_cuenta_con_esquema_y_tabla(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_ventas_step
    from etl_sigrid.application.steps.build_ventas_step import BuildVentasStep, _SubStep

    pg = _PgFalso()
    monkeypatch.setattr(build_ventas_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(build_ventas_step, "SUB_PASOS", (
        _SubStep(name="a", sql_file="00_setup.sql", target_schema="ventas"),
        _SubStep(name="b", sql_file="01_clientes.sql", target_table="clientes"),
    ))
    resultado = BuildVentasStep(SimpleNamespace()).run()
    assert pg.contados == [] and resultado.rows_processed == 0


# ===========================================================================
# run-all, permisos y CLI
# ===========================================================================


def test_f040_r26_en_run_all_tras_retenciones() -> None:
    nombres = [p.name for p in _pasos()]
    assert nombres.count("build_ventas") == 1
    i = nombres.index("build_ventas")
    assert nombres[i - 1] == "build_retenciones"
    assert nombres[i + 1] == "build_personal"
    assert i < nombres.index("publicar_diccionario") < nombres.index("apply_grants")


def test_f040_r26_run_all_son_diecisiete_pasos() -> None:
    assert len(_pasos()) == 17


def test_f040_r26_nadie_depende_de_build_ventas() -> None:
    for paso in _pasos():
        assert "build_ventas" not in paso.depends_on, paso.name


def test_f040_r26_en_pasos_con_permisos() -> None:
    import main

    assert "build_ventas" in main.PASOS_CON_PERMISOS


def test_f040_r26_la_frescura_conoce_el_paso() -> None:
    import main

    for paso in _pasos():
        if isinstance(paso, main.PublicarDiccionarioStep):
            assert "build_ventas" in paso.pasos_nocturnos
            break
    else:  # pragma: no cover
        pytest.fail("sin publicar_diccionario")


def test_f040_r26_comando_build_ventas(monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    import main

    assert "build-ventas" in main.cli.commands
    ejecutados: list[str] = []
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console")))
    monkeypatch.setattr(main, "_get_pg", lambda: object())
    monkeypatch.setattr(main, "_arrancar_ejecucion", lambda _pg: "lote")
    monkeypatch.setattr(main, "_ejecutar_paso",
                        lambda paso, _pg, _e: ejecutados.append(paso.name))
    salida = CliRunner().invoke(main.cli, ["build-ventas"])
    assert salida.exit_code == 0, salida.output
    assert ejecutados == ["build_ventas"]


def test_f040_r26_apply_grants_lo_nombra_entre_los_sueltos() -> None:
    import main

    assert "build-ventas" in (main.apply_grants.help or "")
    assert "build-ventas" in (main.__doc__ or "")


def test_f040_r26_lecturas_para_reanudar_no_cambia() -> None:
    """`build_ventas` no lee `stg` ni `mart`: no entra en la lista de F-148."""
    from etl_sigrid.domain.reanudacion import LECTURAS_PARA_REANUDAR

    assert "build_ventas" not in LECTURAS_PARA_REANUDAR
    assert set(LECTURAS_PARA_REANUDAR) == {"build_retenciones", "build_tesoreria"}
