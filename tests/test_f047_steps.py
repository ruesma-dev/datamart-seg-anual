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


# ===========================================================================
# Lo que el paso DEJA DICHO · nacido de la campaña de mutación
#
# Ocho mutantes sobrevivieron a la primera pasada, cuatro por fichero, y los
# cuatro eran del mismo tipo: **nadie comprobaba lo que el step registra**.
# Un `logger.info` que miente no rompe ningún test y es lo único que queda de
# una noche a las tres de la mañana, así que aquí se fija.
#
#   · `exc_info=True` en el fallo   -> sin traza no hay post mortem
#   · `rows = 0` cuando no hay tabla destino
#   · `if target_schema AND target_table` -> con `or` se llamaría a
#     `count_rows(esquema, None)`
#   · `duration_s` redondeado a DOS decimales
# ===========================================================================


class _LoggerEspia:
    """Anota cada evento estructurado con sus campos, sin escribir nada."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, dict(campos)))

    def error(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, dict(campos)))

    def campos_de(self, evento: str) -> list[dict]:
        return [c for e, c in self.eventos if e == evento]


@pytest.fixture
def espia(monkeypatch: pytest.MonkeyPatch):
    """Sustituye el logger del módulo del step que se le pida."""

    def _instalar(nombre: str) -> _LoggerEspia:
        doble = _LoggerEspia()
        monkeypatch.setattr(f"{STEPS[nombre][1]}.logger", doble)
        return doble

    return _instalar


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r9_un_subpaso_sin_tabla_destino_no_cuenta_filas(
    nombre: str, pg, espia, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EL GUARDIÁN de `target_schema` **y** `target_table`, ejercitado.

    Con `or` en vez de `and`, un sub-paso que declare esquema y no tabla
    llamaría a `count_rows(esquema, None)`, que contra Postgres es un
    `SELECT COUNT(*) FROM esquema.None`. No pasa hoy porque los sub-pasos
    reales declaran los dos campos o ninguno, y por eso hace falta sustituir la
    lista: la condición no era comprobable con los datos de producción.
    """
    modulo = STEPS[nombre][1]
    sub_step = __import__(modulo, fromlist=["_SubStep"])._SubStep
    doble = pg(nombre, _PgFalso())
    registro = espia(nombre)
    monkeypatch.setattr(
        f"{modulo}.SUB_PASOS",
        (
            sub_step(
                name="a_medias",
                sql_file="00_setup.sql",
                target_schema=nombre.removeprefix("build_"),
                target_table=None,
            ),
        ),
    )

    resultado = _step(nombre).run()

    assert resultado.status == StepStatus.SUCCESS
    assert doble.contados == [], "contó filas de una tabla que no se declaró"
    assert resultado.rows_processed == 0
    assert registro.campos_de(f"{nombre.removeprefix('build_')}_substep_done")[0][
        "rows"
    ] == 0


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r9_el_log_dice_cuantas_filas_dejo_cada_subpaso(
    nombre: str, pg, espia
) -> None:
    """Un `rows` inventado en el log es peor que no tenerlo: se cita."""
    pg(nombre, _PgFalso(filas=11))
    registro = espia(nombre)

    _step(nombre).run()

    filas = [
        campos["rows"]
        for campos in registro.campos_de(f"{nombre.removeprefix('build_')}_substep_done")
    ]
    assert filas, "el step no registró ningún sub-paso"
    assert set(filas) <= {0, 11}
    assert 0 in filas, "los sub-pasos sin tabla destino tienen que registrar 0"
    assert 11 in filas


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r9_un_fallo_se_registra_con_su_traza(nombre: str, pg, espia) -> None:
    """`exc_info=True` es lo que convierte el log en un post mortem.

    Sin él queda el mensaje de la excepción y ni una línea de dónde saltó, que
    es justo lo que hace falta a las tres de la mañana.
    """
    pg(nombre, _PgFalso(falla_en=STEPS[nombre][2][0]))
    registro = espia(nombre)

    _step(nombre).run()

    fallos = registro.campos_de(f"{nombre.removeprefix('build_')}_substep_failed")
    assert len(fallos) == 1
    assert fallos[0]["exc_info"] is True
    assert fallos[0]["sub_step"] == "setup"


class _RelojFalso:
    """Un reloj que avanza 1,23456 s por lectura impar, para fijar el redondeo."""

    _instantes = None

    @classmethod
    def utcnow(cls):
        from datetime import datetime as _dt
        from datetime import timedelta

        if cls._instantes is None:
            cls._instantes = _dt(2026, 8, 28, 2, 0, 0)
        valor = cls._instantes
        cls._instantes = cls._instantes + timedelta(seconds=1.23456)
        return valor


@pytest.mark.parametrize("nombre", list(STEPS))
def test_f047_r9_la_duracion_se_registra_con_dos_decimales(
    nombre: str, pg, espia, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dos decimales, no tres ni doce.

    No es cosmética: `duration_s` sale por el log de la carga nocturna y se lee
    junto a los tiempos de `_meta.etl_runs`. Con un reloj real la diferencia
    entre `round(x, 2)` y `round(x, 3)` no se ve —las duraciones de un doble son
    0,0—, así que el reloj se fija.
    """
    pg(nombre, _PgFalso())
    registro = espia(nombre)
    _RelojFalso._instantes = None
    monkeypatch.setattr(f"{STEPS[nombre][1]}.datetime", _RelojFalso)

    _step(nombre).run()

    duraciones = [
        campos["duration_s"]
        for campos in registro.campos_de(f"{nombre.removeprefix('build_')}_substep_done")
    ]
    assert duraciones, "no se registró ninguna duración"
    for valor in duraciones:
        assert valor == round(valor, 2), f"{valor} trae más de dos decimales"
    assert 1.23 in duraciones, f"esperaba 1.23 y salió {duraciones}"
