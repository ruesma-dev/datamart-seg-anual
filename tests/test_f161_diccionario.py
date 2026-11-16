# tests/test_f161_diccionario.py
"""F-161 · Diccionario y documentos del catálogo completo (R20, R21).

Sin red ni BBDD. Lo que cada ficha tiene que decir, porque quien la lee es un
agente que no puede preguntar:

- el catálogo tiene TODAS las versiones con líneas, y solo las de
  `tiene_reparto` rigen el mensual (D4);
- el último cierre (importe) y la temporal se publican al lado, sin sumarse ni
  reescalarse (D1, D3);
- `stg.plan_mensual` SÍ tiene versión 0 en los ámbitos master (en 4 obras).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICC = RAIZ / "config" / "diccionario"

VERSION_ANTERIOR = 76


def _azure_apps() -> Path | None:
    """`azure-apps/` es hermano del repositorio; desde un worktree, de un ancestro."""
    for padre in RAIZ.parents:
        candidato = padre / "azure-apps" / "datamart_seg_anual.md"
        if candidato.exists():
            return candidato
    return None


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"][objeto]


def _plano(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto))


def _regla(codigo: str) -> dict:
    return next(r for r in _yaml("00_global.yaml")["reglas"] if r["codigo"] == codigo)


# --- R20 · stg -----------------------------------------------------------------


def test_f161_r20_ficha_de_stg_master_versiones() -> None:
    ficha = _ficha("stg", "master_versiones")
    assert ficha["tipo"] == "tabla"
    assert ficha["clave_negocio"] == ["obra_id", "ambito_id", "version"]
    assert ficha["paso_etl"] == "build_stg"
    assert ficha["refresco"] == "nocturno"
    d = _plano(ficha["descripcion"])
    assert "mart.master_versiones_tipadas" in d
    assert ficha["columnas"]["reparto"]["valores"] == ["NINGUNO", "COMPLETO", "PARCIAL"]


def test_f161_r20_ficha_de_stg_v_master_lineas() -> None:
    ficha = _ficha("stg", "v_master_lineas")
    assert ficha["tipo"] == "vista"
    assert "tiene_reparto" in ficha["columnas"]
    assert "mart.v_master_version_partida" in _plano(ficha["descripcion"])


def test_f161_r20_plan_mensual_ya_no_niega_la_version_0() -> None:
    ficha = _ficha("stg", "plan_mensual")
    version = _plano(ficha["columnas"]["version"]["significado"])
    assert "Aqui NO hay filas de la fase 0" not in version
    assert "version 0" in version
    assert "stg.plan_mensual_fase0" in version, "lo exige F-157 (R24)"
    assert "stg.master_versiones" in _plano(ficha["descripcion"])


# --- R20 · mart ----------------------------------------------------------------

NUEVAS = (
    "tiene_reparto", "reparto", "n_lineas", "n_lineas_con_reparto", "importe_total",
    "importe_con_reparto", "importe_sin_reparto", "tiene_cabecera", "tiene_ancla",
)


@pytest.mark.parametrize("objeto", ["master_versiones_tipadas", "v_master_versiones_tipadas"])
def test_f161_r20_el_catalogo_dice_su_grano_verdadero(objeto: str) -> None:
    ficha = _ficha("mart", objeto)
    grano = _plano(ficha["grano"])
    assert "todas las versiones con lineas" in grano
    assert "solo las de `tiene_reparto` rigen" in grano
    assert "solo versiones con fecha efectiva resuelta" not in grano
    for columna in NUEVAS:
        assert columna in ficha["columnas"], f"{objeto}.{columna}"


def test_f161_r20_ficha_del_coste_por_partida() -> None:
    ficha = _ficha("mart", "v_master_version_partida")
    assert ficha["tipo"] == "vista"
    d = _plano(ficha["descripcion"])
    assert "filtra por obra" in d.lower()
    assert "R-VENTA-COEFICIENTES" in d, "la venta de aquí es sin coeficientes"
    assert ficha["columnas"]["importe"]["agregacion"] == "suma"


def test_f161_r20_ficha_del_planificado_de_importe() -> None:
    ficha = _ficha("mart", "master_importe_mensual")
    assert ficha["tipo"] == "tabla"
    assert ficha["clave_negocio"] == ["obra_id", "ambito_id", "anio_mes"]
    d = _plano(ficha["descripcion"])
    assert "NO se suman" in d
    assert "sin reescalar" in d
    columnas = ficha["columnas"]
    for nombre in ("importe_total_importe", "importe_total_temporal", "diferencia_importe"):
        assert columnas[nombre]["agregacion"] != "suma", f"{nombre}: es una foto por mes"


# --- R20 · reglas y versión ------------------------------------------------------


def test_f161_r20_r_version_master_alcanza_los_objetos_nuevos() -> None:
    regla = _regla("R-VERSION-MASTER")
    for objeto in (
        "stg.master_versiones", "stg.v_master_lineas", "mart.v_master_version_partida",
        "mart.master_importe_mensual",
    ):
        assert objeto in regla["ambito"], objeto
    resumen = _plano(regla["resumen"])
    assert "tiene_reparto" in resumen
    assert "master_importe_mensual" in resumen
    assert 40 <= len(regla["resumen"].strip()) <= 250


def test_f161_r20_p18_reconoce_la_version_sin_reparto() -> None:
    p18 = next(p for p in _yaml("00_global.yaml")["preguntas_aceptacion"] if p["id"] == "P18")
    assert "reparto = 'NINGUNO'" in _plano(p18["respuesta_correcta"])


def test_f161_r20_la_version_sube() -> None:
    assert _yaml("00_global.yaml")["version"] >= VERSION_ANTERIOR + 1
    texto = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 77 (F-161, 2026-11-" in texto.split("\nversion:", 1)[0]


def test_f161_r20_ningun_objeto_nuevo_queda_pendiente() -> None:
    pendientes = _yaml("00_global.yaml").get("pendientes") or []
    nombres = {p.get("objeto") if isinstance(p, dict) else p for p in pendientes}
    for objeto in (
        "stg.master_versiones", "stg.v_master_lineas", "mart.v_master_version_partida",
        "mart.master_importe_mensual",
    ):
        assert objeto not in nombres


# --- R21 · documentos ------------------------------------------------------------

OBJETOS = (
    "stg.master_versiones", "stg.v_master_lineas", "mart.v_master_version_partida",
    "mart.master_importe_mensual",
)


def test_f161_r21_architecture_nombra_los_objetos() -> None:
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for objeto in OBJETOS:
        assert objeto in texto, objeto


def test_f161_r21_claude_md_mapa() -> None:
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    assert "F-161" in texto
    for objeto in ("master_versiones", "master_importe_mensual", "v_master_version_partida"):
        assert objeto in texto, objeto


def test_f161_r21_azure_apps_nombra_los_objetos() -> None:
    ruta = _azure_apps()
    if ruta is None:
        pytest.skip("azure-apps no está al lado del repositorio")
    texto = ruta.read_text(encoding="utf-8")
    for objeto in OBJETOS:
        assert objeto in texto, objeto
