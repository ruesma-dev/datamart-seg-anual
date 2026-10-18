# tests/test_f144_empresa_por_defecto.py
"""
F-144 · Si la pregunta no indica empresa, es Construcciones Ruesma (`empresa_id = 1`).

Orden del humano (2026-10-18): «en general si no se indica empresa es construcciones
ruesma. es criterio general». Regla dura nueva `R-EMPRESA-POR-DEFECTO` en
`config/diccionario/00_global.yaml`, junto a `R-CODIGO-POR-EMPRESA`, que remite a ella. La
IA DICE en su respuesta que ha supuesto Construcciones Ruesma (sugerencia de `mcp-bbdd`).

Ningún test abre red ni BBDD: solo leen el árbol. El `empresa_id = 1` y los nombres de
columna se comprobaron en Azure en solo lectura (`progress/impl_F-144.md`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DICC = RAIZ / "config" / "diccionario"
CODIGO = "R-EMPRESA-POR-DEFECTO"


def _global() -> dict:
    return yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))


def _reglas() -> dict[str, dict]:
    return {r["codigo"]: r for r in _global()["reglas"]}


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def test_f144_la_regla_existe_y_es_bloqueante() -> None:
    regla = _reglas()[CODIGO]
    assert regla["severidad"] == "bloqueante"
    assert len(regla["titulo"]) <= 87, "no más largo que el título más largo ya publicado"
    assert "Construcciones Ruesma" in regla["titulo"]
    assert regla["motivo"].strip()


def test_f144_la_regla_va_junto_a_la_del_codigo_por_empresa() -> None:
    codigos = [r["codigo"] for r in _global()["reglas"]]
    assert codigos.index(CODIGO) == codigos.index("R-CODIGO-POR-EMPRESA") + 1


def test_f144_la_regla_dice_lo_que_decidio_el_humano() -> None:
    texto = _plano(_reglas()[CODIGO]["regla"])
    for termino in (
        "CRITERIO GENERAL", "Construcciones Ruesma", "`empresa_id = 1`",
        "no solo para los codigos de obra o de recurso",
        # la obligacion de decirlo
        "DICE en la respuesta", "he supuesto Construcciones Ruesma",
        # las excepciones
        "otra empresa", "varias", "el grupo", "una UTE",
        "Nunca se suman empresas sin decirlo",
        # los nombres reales de la columna (medidos en Azure el 2026-10-18)
        "`maestro.centros_coste.empresa`", "`clave_obra`", "`maestro.obras`",
        "`R-CODIGO-POR-EMPRESA`", "`R-UNIVERSO-OBRA`",
    ):
        assert termino in texto, f"la regla no dice «{termino}»"


def test_f144_el_motivo_cita_la_orden_del_humano() -> None:
    texto = _plano(_reglas()[CODIGO]["motivo"])
    assert "2026-10-18" in texto and "criterio general" in texto
    assert "CONSTRUCCIONES RUESMA" in texto, "el nombre medido en `maestro.obras`"


@pytest.mark.parametrize(
    "destino",
    ["maestro", "compras", "retenciones", "personal", "contabilidad",
     "contabilidad_restringida", "tesoreria", "tesoreria_restringida"],
)
def test_f144_el_ambito_alcanza_a_todo_esquema_con_empresa(destino: str) -> None:
    assert destino in _reglas()[CODIGO]["ambito"]


def test_f144_el_codigo_por_empresa_remite_a_la_nueva() -> None:
    texto = _plano(_reglas()["R-CODIGO-POR-EMPRESA"]["regla"])
    assert f"`{CODIGO}`" in texto


def test_f144_version_55_y_su_entrada_de_cabecera() -> None:
    assert int(_global()["version"]) >= 55, "F-144 sube la versión a 55"
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 55 (F-144, 2026-10-18): " in texto
