# tests/test_f157_step.py
"""
F-157 · El sub-paso `build_plan_mensual_fase0` de `build_stg` (R12-R17).

Con el doble de `PostgresClient` de F-025 (`tests/test_f025_build.py`): ni red
ni BBDD. Lo que se prueba es la conducta del step: dónde va, qué borra, cuándo
no escribe y cómo se para.
"""

from __future__ import annotations

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    MARCADOR_FILTRO_FASE0,
    componer_sql_fase0,
)
from etl_sigrid.domain.entities import StepStatus
from tests.test_f025_build import DOMINGO_DE_COMPLETA, PgVentana, ejecutar

PASO = "build_stg.build_plan_mensual_fase0"


class PgFase0(PgVentana):
    """El doble de F-025 con lo que este sub-paso necesita observar."""

    def __init__(self, *, disco_tras: int | None = None, disco: object = 95.0, **kw):
        super().__init__(**kw)
        self._disco_tras = disco_tras
        self._disco = disco
        self.mediciones = 0

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        self.mediciones += 1
        if self._disco_tras is not None and self.mediciones > self._disco_tras:
            if isinstance(self._disco, Exception):
                raise self._disco
            return float(self._disco)  # type: ignore[arg-type]
        return 10.0

    def count_rows(self, schema: str, table: str) -> int:
        return 1234 if table == "plan_mensual_fase0" else 0


def _sql_fase0(pg: PgVentana) -> list[str]:
    return [s for s in pg.sql_ejecutado if "stg.plan_mensual_fase0" in s]


def _cierre_del_paso(pg: PgVentana) -> tuple:
    run_id = pg.pasos_registrados.index(PASO) + 1
    return next(c for c in pg.cierres if c[0] == run_id)


# --- componer_sql_fase0 (R13) -----------------------------------------------


def test_f157_r13_compone_borrado_y_filtro_con_la_misma_lista() -> None:
    sql = componer_sql_fase0("INSERT ... WHERE x = ANY (/*F157_FILTRO_OBRAS*/)", [4, 8])
    assert sql.startswith("DELETE FROM stg.plan_mensual_fase0 WHERE obra_id = ANY")
    assert sql.count("ARRAY[4, 8]::BIGINT[]") == 2
    assert MARCADOR_FILTRO_FASE0 not in sql
    assert sql.index("DELETE") < sql.index("INSERT")


@pytest.mark.parametrize("texto", ["INSERT ... WHERE 1=1", "A /*F157_FILTRO_OBRAS*/ B /*F157_FILTRO_OBRAS*/"])
def test_f157_r13_sin_marcador_o_doble_no_se_compone(texto: str) -> None:
    with pytest.raises(ValueError, match="F157_FILTRO_OBRAS"):
        componer_sql_fase0(texto, [3])


def test_f157_r13_no_admite_otra_cosa_que_enteros() -> None:
    with pytest.raises(TypeError):
        componer_sql_fase0("x /*F157_FILTRO_OBRAS*/", [True])
    with pytest.raises(ValueError):
        componer_sql_fase0("x /*F157_FILTRO_OBRAS*/", [])


def test_f157_r13_el_09_real_se_compone() -> None:
    from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG

    texto = (DIRECTORIO_SQL_STG / "09_plan_mensual_fase0.sql").read_text(encoding="utf-8")
    sql = componer_sql_fase0(texto, [2817778])
    assert "ARRAY[2817778]::BIGINT[]" in sql
    assert MARCADOR_FILTRO_FASE0 not in sql


# --- R12 · dónde va ----------------------------------------------------------


def test_f157_r12_va_despues_de_plan_mensual_y_es_el_ultimo(monkeypatch) -> None:
    pg = PgFase0()
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    pasos = [p for p in pg.pasos_registrados if p.count(".") == 1]
    assert pasos.index(PASO) == pasos.index("build_stg.build_plan_mensual") + 1
    assert pasos[-1] == PASO


def test_f157_r12_r13_una_sola_pasada_borra_e_inserta_las_obras_del_plan(monkeypatch) -> None:
    pg = PgFase0()
    ejecutar(pg, monkeypatch)

    sentencias = _sql_fase0(pg)
    assert len(sentencias) == 1
    sql = sentencias[0]
    assert sql.startswith("DELETE FROM stg.plan_mensual_fase0")
    assert "INSERT INTO stg.plan_mensual_fase0" in sql
    # Jueves: solo la obra viva (la 1) entra en el plan.
    assert sql.count("ARRAY[1]::BIGINT[]") == 2


def test_f157_r12_el_domingo_entran_todas(monkeypatch) -> None:
    pg = PgFase0()
    ejecutar(pg, monkeypatch, ahora=DOMINGO_DE_COMPLETA)

    assert _sql_fase0(pg)[0].count("ARRAY[1, 2, 3]::BIGINT[]") == 2
    assert "plan_mensual_fase0" in pg.obras_sobrantes_pedidas


# --- R14 · sin obras no se toca ----------------------------------------------


def test_f157_r14_plan_sin_obras_no_toca_la_tabla(monkeypatch) -> None:
    pg = PgFase0(censo=[], pesos={})
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.SUCCESS
    assert _sql_fase0(pg) == []
    assert _cierre_del_paso(pg)[1] == "SUCCESS"


# --- R15 · la puerta de disco ------------------------------------------------


def test_f157_r15_disco_por_encima_del_limite_para_sin_escribir(monkeypatch) -> None:
    pg = PgFase0(disco_tras=1, disco=95.0)  # la 1.ª medición es la del tramo
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.FAILED
    assert resultado.metadata["failed_at"] == "build_plan_mensual_fase0"
    assert _sql_fase0(pg) == []
    cierre = _cierre_del_paso(pg)
    assert cierre[1] == "FAILED"
    assert "95" in (cierre[3] or "")


def test_f157_r15_disco_sin_medir_para_sin_escribir(monkeypatch) -> None:
    pg = PgFase0(disco_tras=1, disco=RuntimeError("sin permiso en pg_database_size"))
    resultado = ejecutar(pg, monkeypatch)

    assert resultado.status is StepStatus.FAILED
    assert _sql_fase0(pg) == []
    assert "no se pudo medir" in (_cierre_del_paso(pg)[3] or "")


# --- R17 · su fila en _meta.etl_runs -----------------------------------------


def test_f157_r17_registra_las_filas_de_la_tabla(monkeypatch) -> None:
    pg = PgFase0()
    resultado = ejecutar(pg, monkeypatch)

    assert _cierre_del_paso(pg)[1:3] == ("SUCCESS", 1234)
    assert resultado.metadata["table_stats"]["stg.plan_mensual_fase0"] == 1234


def test_f157_r16_entra_en_la_higiene(monkeypatch) -> None:
    pg = PgFase0()
    ejecutar(pg, monkeypatch)
    assert ("stg", "plan_mensual_fase0") in pg.vacuums
