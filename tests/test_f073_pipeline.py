# tests/test_f073_pipeline.py
"""
F-073 · Los dos steps que publican los objetos nuevos, y la dependencia (R27).

Tres cosas que no se ven leyendo el SQL:

1. Un fichero `.sql` en su carpeta **no se ejecuta solo**. Si el sub-paso no
   está declarado en su step, la vista no existe en la base y el diccionario
   la declara igual: es exactamente la discrepancia que `check-diccionario`
   destapó el 2026-09-09.
2. `build_maestros` pasa a leer de `stg` —las dos marcas de `maestro.obras`—,
   así que tiene que DECLARARLO en `depends_on` (R27, DA-3). El DAG es donde
   eso se dice; la posición en la lista de `main.py` solo es legible.
3. `build_compras` NO cambia su dependencia: `compras.formas_pago` sigue
   leyendo solo de `raw`.

Ningún test toca red ni BBDD: se sustituye `build_postgres_client`, que es la
única puerta por la que estos steps salen del proceso. Mismo doble y mismo
criterio que `tests/test_f047_steps.py`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps import build_compras_step, build_maestros_step
from etl_sigrid.application.steps.build_compras_step import BuildComprasStep
from etl_sigrid.application.steps.build_maestros_step import BuildMaestrosStep
from etl_sigrid.domain.entities import StepStatus

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)

#: Los ficheros de cada step, EN ORDEN. El orden es el de la numeración: cada
#: uno puede leer lo que dejó el anterior, y `00_setup.sql` crea el esquema.
FICHEROS_MAESTRO = [
    "00_setup.sql",
    "01_obras.sql",
    "02_proveedores.sql",
    "03_proveedores_obra.sql",
    "04_centros_coste.sql",
    "05_estados_documento.sql",
]
FICHEROS_COMPRAS = [
    "00_setup.sql",
    "01_documentos.sql",
    "02_fact_linea.sql",
    "03_views.sql",
    "04_formas_pago.sql",
]


class _PgFalso:
    """Anota qué ficheros se ejecutaron y en qué orden."""

    def __init__(self, filas: int = 7) -> None:
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []
        self._filas = filas

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return self._filas


@pytest.fixture
def doble(monkeypatch: pytest.MonkeyPatch):
    def _instalar(modulo) -> _PgFalso:
        pg = _PgFalso()
        monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)
        return pg

    return _instalar


# ---------------------------------------------------------------------------
# R27 · la dependencia que cambia, y la que no
# ---------------------------------------------------------------------------


def test_f073_r27_build_maestros_declara_que_lee_de_stg() -> None:
    """`maestro.obras` sonda `stg.presupuesto` y `stg.plan_mensual` (R14)."""
    dependencias = BuildMaestrosStep(SimpleNamespace()).depends_on

    assert "ingest_raw" in dependencias, "sigue necesitando la ingesta"
    assert "build_stg" in dependencias, (
        "las marcas de maestro.obras leen de stg: si build_stg no está en el "
        "DAG, un build-maestros contra una base sin stg revienta al crear la "
        "vista y nadie lo había declarado (R27)"
    )


def test_f073_r27_build_compras_no_cambia_de_dependencias() -> None:
    """`compras.formas_pago` lee solo de `raw`: no hay motivo para tocar su DAG."""
    assert BuildComprasStep(SimpleNamespace()).depends_on == ["ingest_raw"]


# ---------------------------------------------------------------------------
# Los sub-pasos nuevos están declarados, y en el orden de sus ficheros
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("modulo", "esperados"),
    [
        (build_maestros_step, FICHEROS_MAESTRO),
        (build_compras_step, FICHEROS_COMPRAS),
    ],
)
def test_f073_los_sub_pasos_van_en_el_orden_de_sus_ficheros(
    modulo, esperados: list[str]
) -> None:
    assert [sub.sql_file for sub in modulo.SUB_PASOS] == esperados


@pytest.mark.parametrize(
    ("modulo", "carpeta"),
    [(build_maestros_step, "maestro"), (build_compras_step, "compras")],
)
def test_f073_cada_sub_paso_declarado_existe_en_disco(modulo, carpeta: str) -> None:
    """Un nombre mal escrito aquí sale como FAILED a las tres de la mañana."""
    for sub in modulo.SUB_PASOS:
        assert (DIRECTORIO_SQL / carpeta / sub.sql_file).exists(), (
            f"{carpeta}/{sub.sql_file} está declarado y no existe"
        )


@pytest.mark.parametrize(
    ("modulo", "nombre", "esquema", "tabla"),
    [
        (build_maestros_step, "centros_coste", "maestro", "centros_coste"),
        (build_maestros_step, "estados_documento", "maestro", "estados_documento"),
        (build_compras_step, "formas_pago", "compras", "formas_pago"),
    ],
)
def test_f073_el_sub_paso_nuevo_cuenta_las_filas_de_su_vista(
    modulo, nombre: str, esquema: str, tabla: str
) -> None:
    """Sin `target_schema`/`target_table` el sub-paso no aporta a
    `rows_processed`, y un cero en `_meta.etl_runs` no distingue «construida
    vacía» de «no construida»."""
    sub = next((s for s in modulo.SUB_PASOS if s.name == nombre), None)

    assert sub is not None, f"falta el sub-paso {nombre}"
    assert (sub.target_schema, sub.target_table) == (esquema, tabla)


# ---------------------------------------------------------------------------
# El step, ejecutado de verdad contra el doble
# ---------------------------------------------------------------------------


def test_f073_build_maestros_encadena_sus_seis_sql(doble) -> None:
    pg = doble(build_maestros_step)

    resultado = BuildMaestrosStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS_MAESTRO
    assert ("maestro", "centros_coste") in pg.contados
    assert ("maestro", "estados_documento") in pg.contados


def test_f073_build_compras_encadena_sus_cinco_sql(doble) -> None:
    pg = doble(build_compras_step)

    resultado = BuildComprasStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS_COMPRAS
    assert ("compras", "formas_pago") in pg.contados


# ---------------------------------------------------------------------------
# El docstring que ya no es cierto
# ---------------------------------------------------------------------------


def test_f073_el_docstring_de_maestros_ya_no_dice_que_solo_lee_de_raw() -> None:
    """Decía «Solo lee de raw.*» y «NO forma parte de run-all». Las dos son
    falsas desde F-047 y F-073: un comentario falso es peor que ninguno."""
    documentacion = (build_maestros_step.__doc__ or "").lower()

    assert "solo lee de raw" not in documentacion
    assert "no forma parte de run-all" not in documentacion
    assert "stg" in documentacion, "tiene que decir de dónde lee ahora"
