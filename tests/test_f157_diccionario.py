# tests/test_f157_diccionario.py
"""F-157 · Diccionario y documentación de la fase 0 repartida (R23, R24, R27).

Sin red ni BBDD. La fase 0 es el PRESUPUESTO VIVO de hoy de la obra (el coste y
la venta reales de hoy), y así tiene que decirlo cada texto: corrección del
humano a la redacción de la spec («no escribas que no es real»).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICC = RAIZ / "config" / "diccionario"
AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

VERSION_ANTERIOR = 72


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _stg() -> dict:
    return _yaml("stg.yaml")["objetos"]


def _plano(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto))


def _regla(codigo: str) -> dict:
    return next(r for r in _yaml("00_global.yaml")["reglas"] if r["codigo"] == codigo)


# --- R23 · la ficha de la tabla ----------------------------------------------


def test_f157_r23_ficha_de_la_tabla_existe_y_se_consume() -> None:
    ficha = _stg()["plan_mensual_fase0"]
    assert ficha["tipo"] == "tabla"
    assert ficha["consumo_recomendado"] is True
    assert ficha["clave_negocio"] == ["obra_id", "ambito_id", "partida_id", "anio_mes"]
    assert ficha["paso_etl"] == "build_stg"
    assert ficha["refresco"] == "nocturno"


def test_f157_r23_es_el_presupuesto_vivo_de_hoy_repartido_en_el_tiempo() -> None:
    d = _plano(_stg()["plan_mensual_fase0"]["descripcion"])
    assert "el presupuesto vivo de hoy (fase 0), repartido en el tiempo" in d.lower()
    assert "Planificacion en el tiempo (por partidas)" in d


def test_f157_r23_no_dice_que_no_sea_real() -> None:
    for nombre in ("plan_mensual_fase0", "v_plan_mensual_fase0_cobertura"):
        texto = _plano(_stg()[nombre]).lower()
        assert "no es real" not in texto, nombre
        assert "no es el real" not in texto, nombre


def test_f157_r23_no_se_suma_con_los_cierres_ni_con_el_master_y_se_compara() -> None:
    d = _plano(_stg()["plan_mensual_fase0"]["descripcion"])
    assert "stg.plan_mensual" in d
    assert "NO SE SUMA" in d
    assert "Coste Real" in d and "Venta Real" in d
    assert "fases 1 a N" in d
    assert "planificacion del master" in d
    assert "se COMPARA" in d


def test_f157_r23_solo_partidas_planificadas_y_el_resto_en_la_vista() -> None:
    d = _plano(_stg()["plan_mensual_fase0"]["descripcion"])
    assert "stg.v_plan_mensual_fase0_cobertura" in d
    assert "importe_origen" in d and "ultimo mes" in d
    assert "_meta.v_frescura_obra" in d


def test_f157_r23_las_dos_preguntas_que_enrutan_van_primero() -> None:
    preguntas = _stg()["plan_mensual_fase0"]["ejemplos_preguntas"]
    assert "0726" in preguntas[0] and "venta" in preguntas[0]
    assert "master vigente" in preguntas[1]


def test_f157_r23_agregacion_de_importes_y_porcentajes() -> None:
    columnas = _stg()["plan_mensual_fase0"]["columnas"]
    assert columnas["importe_mes"]["agregacion"] == "suma_solo_dentro_del_mes"
    for nombre in ("importe_origen", "importe_partida", "can_origen", "importe_origen_raw"):
        assert columnas[nombre]["agregacion"] != "suma", nombre
    for nombre in ("pct_acumulado", "pct_mes"):
        assert columnas[nombre]["agregacion"] != "suma", nombre


def test_f157_r23_ficha_de_la_vista() -> None:
    ficha = _stg()["v_plan_mensual_fase0_cobertura"]
    assert ficha["tipo"] == "vista"
    assert "obra_id" in _plano(ficha["grano"]) and "ambito_id" in _plano(ficha["grano"])
    assert "importe_sin_planificar" in ficha["columnas"]


# --- R24 · plan_mensual, R-IMPORTE-MES y la versión ---------------------------


def test_f157_r24_plan_mensual_ya_no_dice_que_guarda_la_fase_0() -> None:
    ficha = _stg()["plan_mensual"]
    version = _plano(ficha["columnas"]["version"]["significado"])
    assert 'con `fas = 0` como el "Previsto" vivo' not in version
    assert "stg.plan_mensual_fase0" in version
    assert "stg.plan_mensual_fase0" in _plano(ficha["descripcion"])


def test_f157_r24_r_importe_mes_la_incluye() -> None:
    assert "stg.plan_mensual_fase0" in _regla("R-IMPORTE-MES")["ambito"]


def test_f157_r24_la_version_sube_a_la_73() -> None:
    assert _yaml("00_global.yaml")["version"] >= VERSION_ANTERIOR + 1, "F-159 la sube a 74"
    texto = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 73 (F-157, 2026-11-" in texto.split("\nversion:", 1)[0]


# --- R27 · documentación ------------------------------------------------------


def test_f157_r27_architecture_describe_la_fase_0() -> None:
    texto = _plano((RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8"))
    assert "stg.plan_mensual_fase0" in texto
    assert "presupuesto vivo" in texto
    assert "planif NO explosionada" not in texto
    assert "no es real" not in texto.lower()


def test_f157_r27_claude_md_mapa() -> None:
    assert "plan_mensual_fase0" in (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
