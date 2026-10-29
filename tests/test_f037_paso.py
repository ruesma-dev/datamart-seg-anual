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

    def cargar_hipotesis_caja(self, catalogo, obras) -> int:
        """F-140: la carga del YAML, sin SQL; devuelve las filas escritas."""
        if self._falla_en == "hipotesis_carga":
            raise RuntimeError("efectos de personal: la carga no llega a escribir")
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


def test_f037_r17_los_sub_pasos_en_orden_con_su_tabla() -> None:
    """Los cuatro de F-037, detrás los seis de F-140 (R20) y, al final, el de los
    albaranes netos de F-150 (N11): lee las obras de `devengo_corte_obra`."""
    assert [(s.name, s.sql_file, s.target_schema, s.target_table) for s in SUB_PASOS] == [
        ("setup", "00_setup.sql", None, None),
        ("efectos_completo", "01_efectos_completo.sql", "tesoreria_restringida", "efectos"),
        ("efectos_general", "02_efectos_general.sql", "tesoreria", "efectos"),
        ("efectos_restringidos_mes", "03_efectos_restringidos_mes.sql",
         "tesoreria", "efectos_restringidos_mes"),
        ("plazos_forma_pago", "04_plazos_forma_pago.sql", None, None),
        ("condiciones_compra", "05_condiciones_contrato_compra.sql",
         "tesoreria", "condiciones_contrato_compra"),
        ("condiciones_cliente", "06_condiciones_contrato_cliente.sql",
         "tesoreria", "condiciones_contrato_cliente"),
        ("devengo_pendiente", "07_devengo_pendiente.sql",
         "tesoreria", "devengo_pendiente_partida"),
        ("hipotesis_carga", None, None, None),
        ("hipotesis_obra", "08_hipotesis_caja_obra.sql", "tesoreria", "hipotesis_caja_obra"),
        ("albaranes_pendientes", "09_albaranes_pendientes.sql",
         "tesoreria", "albaranes_pendientes_neto"),
    ]


#: Los sub-pasos con fichero SQL (la carga de hipótesis de F-140 no lo tiene).
FICHEROS = [s.sql_file for s in SUB_PASOS if s.sql_file is not None]


def test_f037_r17_los_ficheros_existen_y_no_sobra_ninguno() -> None:
    assert sorted(p.name for p in DIR_SQL.glob("*.sql")) == FICHEROS


# ===========================================================================
# El camino bueno
# ===========================================================================

def test_f037_r17_encadena_los_sql_y_cuenta_sus_tablas(instalar) -> None:
    pg = instalar(_PgFalso(filas=7))
    resultado = _paso().run()
    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS
    assert pg.contados == [
        ("tesoreria_restringida", "efectos"),
        ("tesoreria", "efectos"),
        ("tesoreria", "efectos_restringidos_mes"),
        ("tesoreria", "condiciones_contrato_compra"),
        ("tesoreria", "condiciones_contrato_cliente"),
        ("tesoreria", "devengo_pendiente_partida"),
        ("tesoreria", "hipotesis_caja_obra"),
        ("tesoreria", "albaranes_pendientes_neto"),
    ]
    assert resultado.rows_processed == 7 * 9, "ocho tablas contadas y la carga"
    assert resultado.finished_at is not None
    assert resultado.finished_at >= resultado.started_at
    assert resultado.error_message is None


# ===========================================================================
# R18 · un fallo sale con el nombre del sub-paso y no sigue
# ===========================================================================

@pytest.mark.parametrize("sub", SUB_PASOS, ids=lambda s: s.name)
def test_f037_r18_un_sql_que_revienta_da_failed_con_su_nombre(instalar, sub) -> None:
    pg = instalar(_PgFalso(falla_en=sub.sql_file or sub.name))
    resultado = _paso().run()
    assert resultado.status == StepStatus.FAILED
    assert resultado.error_message.startswith(f"Fallo en {sub.name}: ")
    assert "efectos de personal" in resultado.error_message, "el mensaje del SQL viaja"
    hasta = SUB_PASOS[: SUB_PASOS.index(sub) + 1]
    assert pg.ejecutados == [s.sql_file for s in hasta if s.sql_file], (
        "lo que venía detrás no se ejecuta"
    )
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
        ("efectos_restringidos_mes", 5), ("plazos_forma_pago", 0),
        ("condiciones_compra", 5), ("condiciones_cliente", 5), ("devengo_pendiente", 5),
        ("hipotesis_carga", 5), ("hipotesis_obra", 5), ("albaranes_pendientes", 5),
    ]
    assert all(isinstance(h["duration_s"], float) for h in hechos)


class _Espia:
    """Logger de mentira: apunta cada evento con sus campos."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def error(self, evento: str, **kw) -> None:
        self.eventos.append((evento, kw))

    def info(self, evento: str, **kw) -> None:
        self.eventos.append((evento, kw))

    def de(self, evento: str) -> list[dict]:
        return [kw for ev, kw in self.eventos if ev == evento]


def test_f037_r18_un_sub_paso_con_esquema_y_sin_tabla_no_cuenta(instalar, monkeypatch) -> None:
    """El guardián `target_schema AND target_table`, ejercitado (mutación).

    Los sub-pasos reales declaran los dos campos o ninguno, así que con `or` el
    paso haría lo mismo: hace falta uno a medias para ver la diferencia. Con
    `or`, contaría `tesoreria.None`.
    """
    pg = instalar(_PgFalso(filas=9))
    espia = _Espia()
    monkeypatch.setattr(modulo, "logger", espia)
    monkeypatch.setattr(modulo, "SUB_PASOS", (
        modulo._SubStep(name="a_medias", sql_file="00_setup.sql", target_schema="tesoreria"),
        modulo._SubStep(name="a_medias_2", sql_file="00_setup.sql", target_table="efectos"),
    ))
    resultado = _paso().run()
    assert resultado.status == StepStatus.SUCCESS
    assert pg.contados == []
    assert resultado.rows_processed == 0
    assert [h["rows"] for h in espia.de("tesoreria_substep_done")] == [0, 0]


class _RelojFalso:
    """Un reloj que avanza 1,23456 s por lectura, para fijar el redondeo."""

    instante = None

    @classmethod
    def utcnow(cls):
        from datetime import datetime as _dt
        from datetime import timedelta

        if cls.instante is None:
            cls.instante = _dt(2026, 10, 13, 2, 0, 0)
        valor = cls.instante
        cls.instante = cls.instante + timedelta(seconds=1.23456)
        return valor


def test_f037_r18_la_duracion_va_con_dos_decimales(instalar, monkeypatch) -> None:
    """Con un reloj real la diferencia entre round(x, 2) y round(x, 3) no se ve."""
    instalar(_PgFalso())
    espia = _Espia()
    monkeypatch.setattr(modulo, "logger", espia)
    _RelojFalso.instante = None
    monkeypatch.setattr(modulo, "datetime", _RelojFalso)
    _paso().run()
    duraciones = [h["duration_s"] for h in espia.de("tesoreria_substep_done")]
    assert duraciones and all(d == round(d, 2) for d in duraciones)
    assert 1.23 in duraciones, duraciones


def test_f037_r18_la_duracion_del_fallo_es_la_del_sub_paso(instalar, monkeypatch) -> None:
    """La duración registrada al fallar es t_fallo - t0, positiva y exacta."""
    instalar(_PgFalso(falla_en="00_setup.sql"))
    espia = _Espia()
    monkeypatch.setattr(modulo, "logger", espia)
    _RelojFalso.instante = None
    monkeypatch.setattr(modulo, "datetime", _RelojFalso)
    _paso().run()
    fallo = espia.de("tesoreria_substep_failed")
    assert len(fallo) == 1
    assert fallo[0]["duration_s"] == pytest.approx(1.23456)


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
