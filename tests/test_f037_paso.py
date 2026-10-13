# tests/test_f037_paso.py
"""
F-037 · El paso `build_tesoreria` y su sitio en la nocturna (R17, R18).

Ningún test toca red ni BBDD: se sustituye `build_postgres_client`, la única
puerta por la que el paso sale del proceso.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps import build_tesoreria_step as modulo
from etl_sigrid.application.steps.build_tesoreria_step import (
    SUB_PASOS,
    BuildTesoreriaStep,
)
from etl_sigrid.domain.entities import StepStatus

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria"


class _PgFalso:
    """Anota qué ficheros se ejecutaron y qué tablas se contaron."""

    def __init__(self, falla_en: str | None = None, filas: int = 7) -> None:
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []
        self._falla_en = falla_en
        self._filas = filas

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)
        assert path.parent == DIR_SQL, "los SQL se leen del directorio de tesoreria"
        if self._falla_en == path.name:
            raise RuntimeError("efectos_general: 3 efectos de personal; no se publica")

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return self._filas


@pytest.fixture
def instalar(monkeypatch: pytest.MonkeyPatch):
    def _instalar(doble: _PgFalso) -> _PgFalso:
        monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: doble)
        return doble
    return _instalar


def _paso() -> BuildTesoreriaStep:
    return BuildTesoreriaStep(SimpleNamespace())


# ===========================================================================
# R17 · identidad del paso
# ===========================================================================

def test_f037_r17_nombre_stage_y_dependencias() -> None:
    paso = _paso()
    assert paso.name == "build_tesoreria"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["ingest_raw"]


def test_f037_r17_los_cuatro_sub_pasos_en_orden_con_su_tabla() -> None:
    assert [(s.name, s.sql_file, s.target_schema, s.target_table) for s in SUB_PASOS] == [
        ("setup", "00_setup.sql", None, None),
        ("efectos_completo", "01_efectos_completo.sql", "tesoreria_restringida", "efectos"),
        ("efectos_general", "02_efectos_general.sql", "tesoreria", "efectos"),
        ("efectos_restringidos_mes", "03_efectos_restringidos_mes.sql",
         "tesoreria", "efectos_restringidos_mes"),
    ]


def test_f037_r17_los_ficheros_existen_y_no_sobra_ninguno() -> None:
    assert sorted(p.name for p in DIR_SQL.glob("*.sql")) == [s.sql_file for s in SUB_PASOS]


# ===========================================================================
# El camino bueno
# ===========================================================================

def test_f037_r17_encadena_los_sql_y_cuenta_sus_tablas(instalar) -> None:
    pg = instalar(_PgFalso(filas=7))
    resultado = _paso().run()
    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == [s.sql_file for s in SUB_PASOS]
    assert pg.contados == [
        ("tesoreria_restringida", "efectos"),
        ("tesoreria", "efectos"),
        ("tesoreria", "efectos_restringidos_mes"),
    ]
    assert resultado.rows_processed == 21
    assert resultado.finished_at is not None
    assert resultado.finished_at >= resultado.started_at
    assert resultado.error_message is None


# ===========================================================================
# R18 · un fallo sale con el nombre del sub-paso y no sigue
# ===========================================================================

@pytest.mark.parametrize("sub", SUB_PASOS, ids=lambda s: s.name)
def test_f037_r18_un_sql_que_revienta_da_failed_con_su_nombre(instalar, sub) -> None:
    pg = instalar(_PgFalso(falla_en=sub.sql_file))
    resultado = _paso().run()
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith(f"Fallo en {sub.name}: ")
    assert "efectos de personal" in resultado.error_message, "el mensaje del SQL viaja"
    assert pg.ejecutados[-1] == sub.sql_file, "lo que venía detrás no se ejecuta"
    assert resultado.finished_at is not None


def test_f037_r18_un_fallo_no_cuenta_la_tabla_del_que_fallo(instalar) -> None:
    pg = instalar(_PgFalso(falla_en="02_efectos_general.sql"))
    _paso().run()
    assert pg.contados == [("tesoreria_restringida", "efectos")]


def test_f037_r18_un_sql_que_falta_da_failed_con_la_ruta(instalar, monkeypatch) -> None:
    pg = instalar(_PgFalso())
    falso = modulo._SubStep(name="fantasma", sql_file="99_no_existe.sql")
    monkeypatch.setattr(modulo, "SUB_PASOS", (*SUB_PASOS[:1], falso, *SUB_PASOS[1:]))
    resultado = _paso().run()
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith("Fallo en fantasma: SQL file no encontrado: ")
    assert "99_no_existe.sql" in resultado.error_message
    assert pg.ejecutados == ["00_setup.sql"]
    assert resultado.finished_at is not None


def test_f037_r18_el_fallo_se_registra_con_su_traza(instalar, monkeypatch) -> None:
    eventos: list[tuple[str, dict]] = []

    class _Espia:
        def error(self, evento: str, **kw) -> None:
            eventos.append((evento, kw))

        def info(self, evento: str, **kw) -> None:
            eventos.append((evento, kw))

    monkeypatch.setattr(modulo, "logger", _Espia())
    instalar(_PgFalso(falla_en="01_efectos_completo.sql"))
    _paso().run()
    errores = [kw for ev, kw in eventos if ev == "tesoreria_substep_failed"]
    assert len(errores) == 1
    assert errores[0]["sub_step"] == "efectos_completo"
    assert errores[0]["exc_info"] is True
    assert errores[0]["duration_s"] >= 0


def test_f037_r18_el_log_dice_las_filas_de_cada_sub_paso(instalar, monkeypatch) -> None:
    eventos: list[tuple[str, dict]] = []

    class _Espia:
        def error(self, evento: str, **kw) -> None:
            eventos.append((evento, kw))

        def info(self, evento: str, **kw) -> None:
            eventos.append((evento, kw))

    monkeypatch.setattr(modulo, "logger", _Espia())
    instalar(_PgFalso(filas=5))
    _paso().run()
    hechos = [kw for ev, kw in eventos if ev == "tesoreria_substep_done"]
    assert [(h["sub_step"], h["rows"]) for h in hechos] == [
        ("setup", 0), ("efectos_completo", 5), ("efectos_general", 5),
        ("efectos_restringidos_mes", 5),
    ]
    assert all(isinstance(h["duration_s"], float) for h in hechos)


# ===========================================================================
# R17 · la nocturna: delante de compras, y nadie depende de él (D9)
# ===========================================================================

def _pasos():
    import main
    return main.build_pipeline_steps(SimpleNamespace(), full_refresh=False)


def test_f037_r17_va_entre_maestros_y_compras() -> None:
    nombres = [p.name for p in _pasos()]
    i = nombres.index("build_tesoreria")
    assert nombres[i - 1] == "build_maestros"
    assert nombres[i + 1] == "build_compras"


def test_f037_r17_ningun_paso_depende_de_build_tesoreria() -> None:
    """D9: si falla, la nocturna sigue y compras lee la cartera de ayer."""
    for paso in _pasos():
        assert "build_tesoreria" not in paso.depends_on, paso.name


def test_f037_r17_el_comando_build_tesoreria_existe() -> None:
    import main
    assert "build-tesoreria" in main.cli.commands
    texto = (RAIZ / "main.py").read_text(encoding="utf-8")
    assert "_ejecutar_paso(BuildTesoreriaStep(settings), pg, ejecucion)" in texto


def test_f037_r17_el_paso_esta_en_su_fichero_con_su_ruta() -> None:
    ruta = RAIZ / "etl_sigrid" / "application" / "steps" / "build_tesoreria_step.py"
    assert ruta.read_text(encoding="utf-8").splitlines()[0] == (
        "# etl_sigrid/application/steps/build_tesoreria_step.py"
    )
