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


# ===========================================================================
# R5 · el guardián corre AL FINAL de `run-all`
#
# El incidente de F-047 no fue una noche en rojo: fue una noche EN VERDE que
# había destruido `cierre.v_pbi_planif_vs_real`. Mientras nadie contraste lo
# que el repositorio declara contra lo que la base tiene, un build puede dejar
# de crear un objeto y la carga seguirá diciendo que todo fue bien.
#
# Se reutilizan los dobles de F-024 —el mismo `PgFalso` y el mismo `cli`— en
# vez de montar otros: son los que ya ejercitan `run-all` entero.
# ===========================================================================

from click.testing import CliRunner  # noqa: E402

from tests.test_f024_cli import (  # noqa: E402
    STEPS_POR_COMANDO,
    PgFalso,
    paso_falso,
    settings_falsos,
)


def _run_all(monkeypatch, pg) -> object:
    """Invoca `run-all` con los dobles de F-024 y sin red ni BBDD.

    Se replican aquí las cinco líneas de la fixture `cli` de F-024 en vez de
    importarla: importar una fixture de otro módulo de test la redefine en el
    espacio de nombres y ruff lo marca (F811) en cada test que la use.
    """
    monkeypatch.setattr(main, "get_settings", lambda: settings_falsos())
    monkeypatch.setattr(main, "configure_logging", lambda **_k: None)
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    for atributo, nombre, stage in STEPS_POR_COMANDO.values():
        monkeypatch.setattr(main, atributo, paso_falso(nombre, stage))
    return CliRunner().invoke(main.cli, ["run-all"])


def _catalogo_completo() -> list[tuple[str, str, str]]:
    """Lo que la base tendría tras una noche que sí construyó todo."""
    from etl_sigrid.infrastructure.inventario_repositorio import (
        inventario_del_repositorio,
    )

    return [(o.esquema, o.objeto, o.tipo) for o in inventario_del_repositorio()]


def test_f047_r5_run_all_con_todo_construido_termina_en_verde(monkeypatch) -> None:
    """Control: sin esto, el test de abajo pasaría aunque `run-all` fallara
    siempre por cualquier otro motivo."""
    resultado = _run_all(monkeypatch, PgFalso(catalogo=_catalogo_completo()))

    assert resultado.exit_code == 0, resultado.output
    assert "declarados" in resultado.output


def test_f047_r5_run_all_sale_con_uno_si_falta_lo_que_el_repositorio_declara(
    monkeypatch,
) -> None:
    """LA REGRESIÓN DE F-047, reproducida de punta a punta.

    Todos los pasos terminan en SUCCESS —la noche «fue bien»— y aun así falta
    en la base la vista que `cierre/06_views_planif_vs_real.sql` declara. Antes
    esto salía con código 0 y nadie se enteraba durante semanas.
    """
    catalogo = [f for f in _catalogo_completo() if f[1] != "v_pbi_planif_vs_real"]

    resultado = _run_all(monkeypatch, PgFalso(catalogo=catalogo))

    assert resultado.exit_code == 1
    assert "DECLARADO Y NO CONSTRUIDO" in resultado.output
    assert "cierre.v_pbi_planif_vs_real" in resultado.output


def test_f047_r5_run_all_no_se_traga_un_fallo_al_leer_el_catalogo(
    monkeypatch,
) -> None:
    """Si el guardián no puede comprobar nada, la noche NO puede darse por
    buena: sería exactamente el agujero que viene a tapar."""

    class PgQueNoSabeMirar(PgFalso):
        def list_objetos_catalogo(self, schemas: object):
            raise RuntimeError("permission denied for schema _meta")

    resultado = _run_all(monkeypatch, PgQueNoSabeMirar())

    assert resultado.exit_code == 1
    assert "no se pudo comprobar lo declarado" in resultado.output


def test_f047_r5_el_guardian_corre_despues_del_ultimo_paso(monkeypatch) -> None:
    """Antes de `apply_grants` no probaría nada: los grants no crean objetos,
    pero los cuatro build sí, y el guardián tiene que ver el resultado de todos.
    """
    resultado = _run_all(monkeypatch, PgFalso(catalogo=_catalogo_completo()))

    salida = resultado.output
    assert salida.index("apply_grants") < salida.index("declarados"), salida
