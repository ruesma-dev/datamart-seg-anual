# tests/test_f156_pipeline.py
"""F-156 · `build_postventa` en el pipeline (R32), sin red ni BBDD.

Esquema MÓDULO como `personal` y `contabilidad`: va tras `build_contabilidad`
y antes de `ingest_descompuestos`, depende solo de `ingest_raw`, nadie depende
de él (si falla, la noche sigue) y recrea tablas con DROP + CREATE (está en
`PASOS_CON_PERMISOS`).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "postventa"
FICHEROS = [
    "00_setup.sql", "01_unidades.sql", "02_incidencias.sql", "03_tareas.sql",
    "04_procesos.sql", "05_estado.sql", "06_adjuntos.sql", "07_restringida.sql",
    "08_coste_obra.sql",
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


def test_f156_r32_nombre_stage_y_dependencias() -> None:
    from etl_sigrid.application.steps.build_postventa_step import BuildPostventaStep

    paso = BuildPostventaStep(SimpleNamespace())
    assert paso.name == "build_postventa"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["ingest_raw"]


def test_f156_r32_los_sub_pasos_en_el_orden_de_sus_ficheros_y_existen() -> None:
    from etl_sigrid.application.steps import build_postventa_step

    assert [s.sql_file for s in build_postventa_step.SUB_PASOS] == FICHEROS
    assert sorted(p.name for p in DIR_SQL.glob("*.sql")) == FICHEROS
    for sub in build_postventa_step.SUB_PASOS:
        assert (DIR_SQL / sub.sql_file).exists(), sub.sql_file


class _PgFalso:
    def __init__(self, falla_en: str = "") -> None:
        self.falla_en = falla_en
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)
        if path.name == self.falla_en:
            raise RuntimeError("F-156 R12: guarda")

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return 3


def test_f156_r32_el_paso_encadena_sus_nueve_sql_y_cuenta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_postventa_step
    from etl_sigrid.application.steps.build_postventa_step import BuildPostventaStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso()
    monkeypatch.setattr(build_postventa_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildPostventaStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS
    assert pg.contados == [
        ("postventa", "unidades"), ("postventa", "incidencias"), ("postventa", "tareas"),
        ("postventa", "incidencia_procesos"), ("postventa", "documento_adjuntos"),
        ("postventa_restringida", "contactos_incidencia"),
        ("postventa", "partida_obra_origen"),
    ]
    assert resultado.rows_processed == 21
    assert resultado.finished_at is not None


@pytest.mark.parametrize(("fichero", "sub"), [("02_incidencias.sql", "incidencias"),
                                               ("06_adjuntos.sql", "adjuntos")])
def test_f156_r32_un_sql_que_revienta_da_failed_con_su_sub_paso(
    monkeypatch: pytest.MonkeyPatch, fichero: str, sub: str,
) -> None:
    from etl_sigrid.application.steps import build_postventa_step
    from etl_sigrid.application.steps.build_postventa_step import BuildPostventaStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso(falla_en=fichero)
    monkeypatch.setattr(build_postventa_step, "build_postgres_client", lambda _s: pg)
    resultado = BuildPostventaStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith(f"Fallo en {sub}: ")
    assert "F-156 R12" in resultado.error_message
    assert pg.ejecutados[-1] == fichero, "no sigue tras el fallo"
    assert resultado.finished_at is not None


def test_f156_r32_un_sql_que_falta_da_failed_con_la_ruta(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_postventa_step
    from etl_sigrid.application.steps.build_postventa_step import BuildPostventaStep, _SubStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgFalso()
    monkeypatch.setattr(build_postventa_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(build_postventa_step, "SUB_PASOS",
                        (_SubStep(name="x", sql_file="99_no_existe.sql"),))
    resultado = BuildPostventaStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert "99_no_existe.sql" in resultado.error_message and pg.ejecutados == []


def test_f156_r32_solo_cuenta_con_esquema_y_tabla(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import build_postventa_step
    from etl_sigrid.application.steps.build_postventa_step import BuildPostventaStep, _SubStep

    pg = _PgFalso()
    monkeypatch.setattr(build_postventa_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(build_postventa_step, "SUB_PASOS", (
        _SubStep(name="a", sql_file="00_setup.sql", target_schema="postventa"),
        _SubStep(name="b", sql_file="01_unidades.sql", target_table="unidades"),
    ))
    resultado = BuildPostventaStep(SimpleNamespace()).run()
    assert pg.contados == [] and resultado.rows_processed == 0


# ===========================================================================
# run-all, permisos y CLI
# ===========================================================================


def test_f156_r32_en_run_all_tras_contabilidad_y_antes_de_descompuestos() -> None:
    nombres = [p.name for p in _pasos()]
    assert nombres.count("build_postventa") == 1
    i = nombres.index("build_postventa")
    assert nombres[i - 1] == "build_contabilidad"
    assert nombres[i + 1] == "ingest_descompuestos"
    assert i < nombres.index("publicar_diccionario") < nombres.index("apply_grants")


def test_f156_r32_nadie_depende_de_build_postventa() -> None:
    for paso in _pasos():
        assert "build_postventa" not in paso.depends_on, paso.name


def test_f156_r32_en_pasos_con_permisos() -> None:
    import main

    assert "build_postventa" in main.PASOS_CON_PERMISOS


def test_f156_r32_la_frescura_conoce_el_paso() -> None:
    """El validador de frescura recibe los pasos nocturnos de la composición."""
    import main

    for paso in _pasos():
        if isinstance(paso, main.PublicarDiccionarioStep):
            assert "build_postventa" in paso.pasos_nocturnos
            break
    else:  # pragma: no cover
        pytest.fail("sin publicar_diccionario")


def test_f156_r32_comando_build_postventa(monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    import main

    assert "build-postventa" in main.cli.commands
    ejecutados: list[str] = []
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console")))
    monkeypatch.setattr(main, "_get_pg", lambda: object())
    monkeypatch.setattr(main, "_arrancar_ejecucion", lambda _pg: "lote")
    monkeypatch.setattr(main, "_ejecutar_paso",
                        lambda paso, _pg, _e: ejecutados.append(paso.name))
    salida = CliRunner().invoke(main.cli, ["build-postventa"])
    assert salida.exit_code == 0, salida.output
    assert ejecutados == ["build_postventa"]


def test_f156_r32_apply_grants_lo_nombra_entre_los_sueltos() -> None:
    import main

    assert "build-postventa" in (main.apply_grants.help or "")
    assert "build-postventa" in (main.__doc__ or "")
