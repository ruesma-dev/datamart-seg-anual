# tests/test_f094_retenciones_obra.py
"""
F-094 (ampliación H6, aprobada el 2026-09-22): `obra_id` de retenciones es la OBRA.

Hasta aquí `retenciones.movimientos.obra_id` era `COALESCE(p.cenide, obra de
las líneas)`: mezclaba DOS entidades, el `ide` del CENTRO DE COSTE (casi
siempre) y el de la obra (solo en el respaldo por líneas, cuyo `obride` sí es
una obra: 575 de 575 en `raw.obr`, medido el 2026-09-22). Por eso casaba 0 de
261 contra `maestro.obras`. Es el resto de F-045, que F-094 absorbe.

El arreglo usa el puente publicado por F-073, `maestro.centros_coste`
(centro -> obra por empresa y código), y publica el centro tal cual en
`centro_coste_id`. Se fija sobre el TEXTO del SQL, como el resto del módulo.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "retenciones"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


@cache
def _texto(nombre: str) -> str:
    return (DIR_SQL / nombre).read_text(encoding="utf-8")


def _compacto(texto: str) -> str:
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in texto.splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


def _mitades() -> tuple[str, str]:
    partes = _compacto(_texto("01_movimientos.sql")).split(" UNION ALL ")
    assert len(partes) == 2
    return partes[0], partes[1]


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


# ===========================================================================
# SQL
# ===========================================================================


def test_f094_obra_se_publica_el_centro_tal_cual() -> None:
    proveedor, cliente = _mitades()
    assert "NULLIF(p.cenide, 0) AS centro_coste_id" in proveedor
    assert "NULLIF(c.cenide, 0) AS centro_coste_id" in cliente


def test_f094_obra_se_traduce_por_el_puente_de_f073() -> None:
    for mitad, alias in zip(_mitades(), ("p", "c")):
        assert re.search(
            rf"LEFT JOIN maestro\.centros_coste cc ON cc\.centro_coste_id = NULLIF\({alias}\.cenide, 0\)",
            mitad,
        ), f"la mitad `{alias}` no traduce el centro a obra con maestro.centros_coste"


def test_f094_obra_id_ya_no_mezcla_centro_y_obra() -> None:
    """Con centro, manda el puente (y si el centro no es obra, queda NULL: es
    estructura y no se imputa a obra); sin centro, las líneas del documento."""
    for mitad, alias in zip(_mitades(), ("p", "c")):
        esperado = (
            f"CASE WHEN NULLIF({alias}.cenide, 0) IS NOT NULL THEN cc.obra_id "
            "WHEN od.num_obras = 1 THEN od.obra_unica END AS obra_id"
        )
        assert esperado in mitad, f"obra_id inesperado en la mitad `{alias}`"
        assert f"COALESCE(NULLIF({alias}.cenide, 0)," not in mitad, (
            "el COALESCE de centro y obra es justo la mezcla que se arregla"
        )


def test_f094_obra_codigo_y_nombre_son_de_la_obra() -> None:
    for mitad, alias in zip(_mitades(), ("p", "c")):
        assert (
            f"CASE WHEN NULLIF({alias}.cenide, 0) IS NOT NULL THEN cc.codigo_obra "
            "ELSE obr_con.cod END AS codigo_obra"
        ) in mitad
        assert (
            f"CASE WHEN NULLIF({alias}.cenide, 0) IS NOT NULL THEN cc.nombre_obra "
            "ELSE obr_con.res END AS nombre_obra"
        ) in mitad
        assert "cen_con" not in mitad, "el nombre del CENTRO ya no se publica como obra"


def test_f094_obra_maestros_corre_antes_que_retenciones() -> None:
    """`maestro.centros_coste` es una VISTA sobre `raw` que existe desde F-073, y
    el DFS del orquestador visita `build_maestros` antes por su posición. NO se
    declara `depends_on`: si `build_stg` fallara, `build_maestros` saldría
    SKIPPED y arrastraría a `build_retenciones`, que hoy sobrevive a eso."""
    import main
    from etl_sigrid.application.orchestrator import Orchestrator

    ajustes = SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )
    pasos = main.build_pipeline_steps(ajustes)
    orden = [p.name for p in Orchestrator(pasos)._topological_sort()]
    assert orden.index("build_maestros") < orden.index("build_retenciones")
    retenciones = next(p for p in pasos if p.name == "build_retenciones")
    assert "build_maestros" not in retenciones.depends_on


# ===========================================================================
# DICCIONARIO
# ===========================================================================


def _relaciones(objeto: str) -> dict[str, dict]:
    ficha = _yaml("retenciones.yaml")["objetos"][objeto]
    return {f"{r['de']}->{r['a']}": r for r in ficha["relaciones"]}


def test_f094_obra_la_ficha_declara_el_cruce_real_con_obras() -> None:
    columnas = _yaml("retenciones.yaml")["objetos"]["movimientos"]["columnas"]
    assert "centro_coste_id" in columnas

    mov = _relaciones("movimientos")
    assert "obra_id->maestro.obras.obra_id" in mov
    assert "centro_coste_id->maestro.centros_coste.centro_coste_id" in mov
    assert "obra_id->cierre.v_pbi_cierre_cabecera.centro_coste_ide" not in mov

    obra = _relaciones("v_pbi_retencion_obra")
    assert "obra_id->maestro.obras.obra_id" in obra
    assert "obra_id->cierre.v_pbi_cierre_cabecera.centro_coste_ide" not in obra
