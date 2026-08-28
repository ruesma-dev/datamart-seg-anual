# tests/test_f047_steps.py
"""
F-047 · Los dos steps nuevos: `build_compras` y `build_retenciones`.

Antes de esta feature su SQL se ejecutaba **en línea dentro del comando**, sin
step. La consecuencia no era estética: sin step no hay fila en
`_meta.etl_runs`, sin fila no hay `_meta.v_frescura`, y sin frescura la regla
dura del diccionario mandaba al agente a citar una fecha de build que nadie
podía consultar. Con los cuatro esquemas dentro de la carga nocturna eso dejó
de ser tolerable.

Ningún test toca red ni BBDD: se sustituye `build_postgres_client`, que es la
única puerta por la que el step sale del proceso.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.build_compras_step import BuildComprasStep
from etl_sigrid.application.steps.build_retenciones_step import BuildRetencionesStep
from etl_sigrid.domain.entities import StepStatus

#: Los dos steps con el módulo donde vive su `build_postgres_client`, para
#: poder sustituirlo, y los ficheros SQL que cada uno tiene que encadenar EN
#: ESTE ORDEN. La lista no es decoración: `01_movimientos.sql` lee lo que
#: `00_setup.sql` crea, y `03_views.sql` lee lo que `02_fact_linea.sql` deja.
STEPS = {
    "build_compras": (
        BuildComprasStep,
        "etl_sigrid.application.steps.build_compras_step",
        ["00_setup.sql", "01_documentos.sql", "02_fact_linea.sql", "03_views.sql"],
    ),
    "build_retenciones": (
        BuildRetencionesStep,
        "etl_sigrid.application.steps.build_retenciones_step",
        ["00_setup.sql", "01_movimientos.sql", "02_views.sql"],
    ),
}


class _PgFalso:
    """Anota qué ficheros se ejecutaron y en qué orden. Puede fallar a la orden."""

    def __init__(self, falla_en: str | None = None, filas: int = 11) -> None:
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []
        self._falla_en = falla_en
        self._filas = filas

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)
        if self._falla_en == path.name:
            raise RuntimeError("relation does not exist")

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return self._filas


@pytest.fixture
def pg(monkeypatch: pytest.MonkeyPatch):
    """Devuelve un ayudante que instala el doble para el step que se le pida."""

    def _instalar(nombre: str, doble: _PgFalso) -> _PgFalso:
        _clase, modulo, _archivos = STEPS[nombre]
        monkeypatch.setattr(f"{modulo}.build_postgres_client", lambda _s: doble)
        return doble

    return _instalar


def _step(nombre: str):
    return STEPS[nombre][0](SimpleNamespace())


# ---------------------------------------------------------------------------
# Contrato de `PipelineStep`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_nombre_stage_y_dependencias(nombre: str) -> None:
    """`stage` tiene que valer lo mismo que `name`: es la columna por la que se
    consulta la frescura, y si no coinciden el agente no encuentra su fila."""
    step = _step(nombre)

    assert step.name == nombre
    assert step.stage == nombre
    assert step.depends_on == ["ingest_raw"]


# ---------------------------------------------------------------------------
# El camino bueno
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_encadena_sus_sql_en_orden(nombre: str, pg) -> None:
    doble = pg(nombre, _PgFalso())

    resultado = _step(nombre).run()

    assert resultado.status == StepStatus.SUCCESS
    assert doble.ejecutados == STEPS[nombre][2]


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_cuenta_las_filas_de_sus_tablas_destino(nombre: str, pg) -> None:
    """`rows_processed` es lo que sale por pantalla y lo que queda en
    `_meta.etl_runs`: un cero ahí y nadie sabe si el build hizo algo."""
    doble = pg(nombre, _PgFalso(filas=11))

    resultado = _step(nombre).run()

    assert doble.contados, "no contó ninguna tabla"
    assert all(esquema == nombre.removeprefix("build_") for esquema, _ in doble.contados)
    assert resultado.rows_processed == 11 * len(doble.contados)


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_el_resultado_trae_sus_dos_marcas_de_tiempo(nombre: str, pg) -> None:
    pg(nombre, _PgFalso())

    resultado = _step(nombre).run()

    assert resultado.started_at is not None
    assert resultado.finished_at is not None
    assert resultado.finished_at >= resultado.started_at


# ---------------------------------------------------------------------------
# Los caminos malos, que son los que importan de noche
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_un_sql_que_revienta_da_failed_nombrando_el_sub_paso(
    nombre: str, pg
) -> None:
    """A las tres de la mañana, «falló el build» no sirve: hay que decir dónde."""
    primero = STEPS[nombre][2][0]
    doble = pg(nombre, _PgFalso(falla_en=primero))

    resultado = _step(nombre).run()

    assert resultado.status == StepStatus.FAILED
    assert "setup" in resultado.error_message
    assert "relation does not exist" in resultado.error_message
    assert resultado.finished_at is not None
    assert doble.ejecutados == [primero], "siguió ejecutando después de fallar"


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_falla_a_mitad_y_no_ejecuta_lo_que_venia_despues(
    nombre: str, pg
) -> None:
    archivos = STEPS[nombre][2]
    doble = pg(nombre, _PgFalso(falla_en=archivos[1]))

    resultado = _step(nombre).run()

    assert resultado.status == StepStatus.FAILED
    assert doble.ejecutados == archivos[:2]


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r4_un_sql_que_falta_da_failed_con_la_ruta(
    nombre: str, pg, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un directorio de SQL vacío tiene que ser un fallo ruidoso.

    Es el modo de fallo silencioso de este tipo de steps: si mañana cambia la
    ruta del SQL, `execute_sql_file` no se llama y el paso podría declararse
    SUCCESS sin haber construido nada.
    """
    doble = pg(nombre, _PgFalso())
    _clase, modulo, _archivos = STEPS[nombre]
    monkeypatch.setattr(f"{modulo}.Path", _PathQueApuntaA(tmp_path))

    resultado = _step(nombre).run()

    assert resultado.status == StepStatus.FAILED
    assert "SQL file no encontrado" in resultado.error_message
    assert doble.ejecutados == []
    assert resultado.finished_at is not None


class _PathQueApuntaA:
    """Sustituye a `Path` dentro del step para que `sql_dir` caiga en vacío."""

    def __init__(self, destino: Path) -> None:
        self._destino = destino

    def __call__(self, *_a: object, **_k: object) -> Path:
        return _RutaFalsa(self._destino)


class _RutaFalsa:
    """Lo mínimo de `Path` que usa el step: `.resolve().parents[2] / ... / ...`."""

    def __init__(self, destino: Path) -> None:
        self._destino = destino

    def resolve(self) -> _RutaFalsa:
        return self

    @property
    def parents(self) -> dict[int, Path]:
        return {2: self._destino}
