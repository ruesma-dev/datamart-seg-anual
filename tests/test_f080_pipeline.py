# tests/test_f080_pipeline.py
"""
F-080 · Los tres sub-pasos nuevos de `build_compras`, declarados y en orden.

UN FICHERO `.sql` EN SU CARPETA NO SE EJECUTA SOLO. Si el sub-paso no está en
`SUB_PASOS`, la tabla no existe en la base, el diccionario la declara igual y
la discrepancia la destapa `check-diccionario` semanas después. Ya pasó el
2026-09-09, y es el motivo de que `tests/test_f073_pipeline.py` exista.

EL ORDEN NO ES DECORATIVO: `05_vencimientos.sql` necesita el esquema y las
funciones de `00_setup.sql`; `06_pago_factura.sql` lee `compras.vencimientos`
(05), `compras.formas_pago` (04) y `compras.facturas` (01); `07_texto.sql` solo
necesita `raw.con`, pero va detrás porque su numeración lo dice. Cambiar el
orden rompe el build, no el estilo.

Ningún test toca red ni BBDD: se sustituye `build_postgres_client`, que es la
única puerta por la que el step sale del proceso. Mismo doble y mismo criterio
que `tests/test_f073_pipeline.py`.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps import build_compras_step
from etl_sigrid.application.steps.build_compras_step import BuildComprasStep
from etl_sigrid.domain.entities import StepStatus

DIRECTORIO_COMPRAS = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
)

#: Los OCHO ficheros de `build_compras` tras F-080, en orden de numeración.
FICHEROS_COMPRAS = [
    "00_setup.sql",
    "01_documentos.sql",
    "02_fact_linea.sql",
    "03_views.sql",
    "04_formas_pago.sql",
    "05_vencimientos.sql",
    "06_pago_factura.sql",
    "07_texto.sql",
]

#: Lo que cada sub-paso nuevo declara como objeto a contar.
#:
#: `texto` construye DOS tablas y declara la de comentarios: es la que puede
#: salir vacía sin que nada falle —si el corte del memo no partiera, quedaría
#: una fila por documento en vez de una por comentario— y contarla cubre
#: también a `documento_texto`, porque sin memos no hay comentarios.
SUB_PASOS_NUEVOS = [
    ("vencimientos", "05_vencimientos.sql", "compras", "vencimientos"),
    ("pago_factura", "06_pago_factura.sql", "compras", "v_facturas_pago"),
    ("texto", "07_texto.sql", "compras", "documento_comentarios"),
]


class _PgFalso:
    """Anota qué ficheros se ejecutaron, en qué orden, y qué se contó."""

    def __init__(self, filas: int = 11) -> None:
        self.ejecutados: list[str] = []
        self.contados: list[tuple[str, str]] = []
        self._filas = filas

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)

    def count_rows(self, schema: str, table: str) -> int:
        self.contados.append((schema, table))
        return self._filas


@pytest.fixture
def pg_falso(monkeypatch: pytest.MonkeyPatch) -> _PgFalso:
    pg = _PgFalso()
    monkeypatch.setattr(build_compras_step, "build_postgres_client", lambda _s: pg)
    return pg


# ---------------------------------------------------------------------------
# Los tres sub-pasos están declarados, y detrás de F-073
# ---------------------------------------------------------------------------


def test_f080_los_ocho_sub_pasos_van_en_el_orden_de_sus_ficheros() -> None:
    assert [sub.sql_file for sub in build_compras_step.SUB_PASOS] == FICHEROS_COMPRAS


@pytest.mark.parametrize(("nombre", "fichero", "esquema", "tabla"), SUB_PASOS_NUEVOS)
def test_f080_cada_sub_paso_nuevo_declara_su_fichero_y_su_objeto(
    nombre: str, fichero: str, esquema: str, tabla: str
) -> None:
    """Sin `target_schema`/`target_table` el sub-paso no aporta a
    `rows_processed`, y un cero en `_meta.etl_runs` no distingue «construida
    vacía» de «no construida»."""
    sub = next((s for s in build_compras_step.SUB_PASOS if s.name == nombre), None)

    assert sub is not None, f"falta el sub-paso {nombre} en SUB_PASOS"
    assert sub.sql_file == fichero
    assert (sub.target_schema, sub.target_table) == (esquema, tabla)
    assert (DIRECTORIO_COMPRAS / sub.sql_file).exists(), (
        f"{sub.sql_file} está declarado y no existe en disco"
    )


def test_f080_los_tres_van_detras_de_la_dimension_de_f073() -> None:
    """`06_pago_factura.sql` lee `compras.formas_pago`: si se construyera antes,
    la vista no existiría todavía y el build fallaría la primera noche."""
    nombres = [sub.name for sub in build_compras_step.SUB_PASOS]

    assert nombres.index("formas_pago") < nombres.index("vencimientos")
    assert nombres.index("vencimientos") < nombres.index("pago_factura"), (
        "`v_facturas_pago` agrega `compras.vencimientos`: primero la tabla"
    )
    assert nombres.index("pago_factura") < nombres.index("texto")


def test_f080_build_compras_sigue_dependiendo_solo_de_la_ingesta() -> None:
    """Los tres objetos nuevos leen de `raw` y de su propio esquema: no hay
    motivo para meter `build_stg` en el DAG, y meterlo encadenaría la nocturna
    sin necesidad."""
    assert BuildComprasStep(SimpleNamespace()).depends_on == ["ingest_raw"]


# ---------------------------------------------------------------------------
# El step, ejecutado de verdad contra el doble
# ---------------------------------------------------------------------------


def test_f080_build_compras_encadena_sus_ocho_sql(pg_falso: _PgFalso) -> None:
    resultado = BuildComprasStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg_falso.ejecutados == FICHEROS_COMPRAS


@pytest.mark.parametrize(("nombre", "fichero", "esquema", "tabla"), SUB_PASOS_NUEVOS)
def test_f080_el_step_cuenta_las_filas_de_los_objetos_nuevos(
    pg_falso: _PgFalso, nombre: str, fichero: str, esquema: str, tabla: str
) -> None:
    BuildComprasStep(SimpleNamespace()).run()

    assert (esquema, tabla) in pg_falso.contados, (
        f"el sub-paso {nombre} no cuenta filas: su construcción no se nota en "
        "`_meta.etl_runs`"
    )
