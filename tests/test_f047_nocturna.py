# tests/test_f047_nocturna.py
"""
F-047 (absorbe F-044) · Los cuatro build entran en la carga nocturna.

**El orden no es cosmético, y esta feature nace de eso.** El 2026-08-28 se
encontró la causa raíz de que `cierre.v_pbi_planif_vs_real` desapareciera de la
base: `sql/mart/03_agg_categoria.sql` hace `DROP TABLE IF EXISTS
mart.fact_seguimiento_categoria CASCADE`, y esa vista de `cierre` **cuelga** de
esa tabla. La nocturna no dejaba de crearla: **la destruía**, y `build-cierre`
no entraba en `run-all`, así que nadie la recreaba.

Por eso aquí no basta con comprobar que los cuatro pasos están: hay que fijar
que `build_cierre` corre **después** de `build_mart`. Un comentario en la lista
se borra; un `depends_on` lo obedece el orden topológico.

Ningún test de este fichero abre red ni BBDD: componer el pipeline solo
construye objetos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import main
from etl_sigrid.application.orchestrator import Orchestrator

#: Los cuatro que entran. `build_cierre` va aparte en varios tests porque es el
#: único con una dependencia real sobre `mart`.
LOS_CUATRO = ("build_maestros", "build_compras", "build_retenciones", "build_cierre")


def _settings_falso() -> SimpleNamespace:
    """Lo mínimo que miran los constructores de los steps del pipeline."""
    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )


def _pasos() -> list:
    return main.build_pipeline_steps(_settings_falso())


def _orden() -> list[str]:
    """El orden REAL de ejecución: el que resuelve el orquestador."""
    return [p.name for p in Orchestrator(_pasos())._topological_sort()]


# ---------------------------------------------------------------------------
# R1 · los cuatro forman parte de `run-all`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("paso", LOS_CUATRO)
def test_f047_r1_los_cuatro_build_estan_en_el_pipeline_nocturno(paso: str) -> None:
    """Se construían a mano y podían estar arbitrariamente desfasados.

    Cuatro de los seis casos de uso que el humano pidió al MCP —proveedores que
    más facturan, retenciones de una obra, facturado por contrato, albaranes
    pendientes— salen de estos esquemas.
    """
    assert paso in [p.name for p in _pasos()]


def test_f047_r1_la_composicion_nocturna_es_exactamente_esta() -> None:
    """Si esto cambia, cambia el veredicto de frescura del diccionario, y así
    debe ser: la lista de pasos nocturnos se inyecta desde la composición."""
    assert [p.name for p in _pasos()] == [
        "ingest_raw",
        "load_excel_aux",
        "build_stg",
        "build_mart",
        "build_maestros",
        "build_compras",
        "build_retenciones",
        "build_cierre",
        "publicar_diccionario",
        "apply_grants",
    ]


# ---------------------------------------------------------------------------
# R2 · `build_cierre` DESPUÉS de `build_mart`, y por escrito en el DAG
# ---------------------------------------------------------------------------


def test_f047_r2_build_cierre_corre_despues_de_build_mart() -> None:
    """LA CAUSA RAÍZ. `build_mart` destruye lo que `build_cierre` construye.

    `03_agg_categoria.sql` dropea `mart.fact_seguimiento_categoria` con
    `CASCADE`, y `cierre.v_pbi_planif_vs_real` cuelga de esa tabla. Invertir el
    orden reproduce el defecto: la vista se crearía y se borraría la misma
    noche.
    """
    orden = _orden()

    assert orden.index("build_cierre") > orden.index("build_mart")


def test_f047_r2_la_dependencia_esta_en_el_dag_y_no_en_el_orden_de_la_lista() -> None:
    """Un comentario se borra sin que nadie se entere; un `depends_on` no.

    Se comprueba contra el orquestador con la lista DESORDENADA a propósito: si
    la garantía dependiera de la posición en `build_pipeline_steps`, aquí
    saldría `build_cierre` antes que `build_mart`.
    """
    pasos = _pasos()
    del_reves = list(reversed(pasos))

    orden = [p.name for p in Orchestrator(del_reves)._topological_sort()]

    assert orden.index("build_cierre") > orden.index("build_mart")


def test_f047_r2_los_tres_que_solo_leen_de_raw_dependen_de_la_ingesta() -> None:
    """`maestro`, `compras` y `retenciones` leen SOLO de `raw` (barrido del
    diagnóstico, `progress/explore_F-047.md`): no deben depender de `stg`."""
    pasos = {p.name: p for p in _pasos()}

    for nombre in ("build_maestros", "build_compras", "build_retenciones"):
        assert pasos[nombre].depends_on == ["ingest_raw"], nombre


# ---------------------------------------------------------------------------
# R3 · publicar y grants siguen siendo los últimos, y en ese orden
# ---------------------------------------------------------------------------


def test_f047_r3_publicar_y_grants_van_despues_de_los_cuatro_build() -> None:
    """`apply_grants` es el último por un motivo medido: los cuatro build
    recrean vistas con DROP + CREATE, y un DROP se lleva los GRANT."""
    orden = _orden()

    for paso in LOS_CUATRO:
        assert orden.index(paso) < orden.index("publicar_diccionario"), paso
        assert orden.index(paso) < orden.index("apply_grants"), paso

    assert orden[-1] == "apply_grants"
    assert orden.index("publicar_diccionario") < orden.index("apply_grants")


# ---------------------------------------------------------------------------
# R4 · los cuatro registran paso en `_meta.etl_runs`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("paso", LOS_CUATRO)
def test_f047_r4_los_cuatro_son_steps_de_verdad_y_dejan_fila(paso: str) -> None:
    """`build-compras` y `build-retenciones` ejecutaban SQL en línea, sin step.

    Su fecha de build no era consultable por SQL, así que el aviso de frescura
    no les servía de nada: el agente no podía citar una fecha que no existía.
    """
    from etl_sigrid.application.steps.base import PipelineStep

    step = next(p for p in _pasos() if p.name == paso)

    assert isinstance(step, PipelineStep)
    assert step.stage == paso
