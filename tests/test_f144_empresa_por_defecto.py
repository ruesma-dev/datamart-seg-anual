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
    # F-147 acortó la regla a la orden (revision_reglas.md, fila 6): las frases
    # de explicación salieron; la orden, las excepciones y las columnas, no.
    for termino in (
        "CRITERIO GENERAL", "Construcciones Ruesma", "`empresa_id = 1`",
        # la obligacion de decirlo
        "la respuesta lo dice", "he supuesto Construcciones Ruesma",
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


# ---------------------------------------------------------------------------
# Pasada 2 del review: los objetos SIN empresa ni `obra_id`.
#
# La pasada 1 decía «la columna se llama `empresa_id` en `compras`, `retenciones`…»,
# y no es cierto: `compras.facturas` o `retenciones.v_pbi_retencion_resumen` no tienen
# empresa ni obra y mezclan las 38 empresas. Con aquel texto la IA no filtraba y aun así
# decía «he supuesto Construcciones Ruesma».
#
# F-147 (2026-10-22, decisión del humano): el inventario de la regla —tres listas que
# había que mantener exactas a mano— sale a las FICHAS. La regla dice el método (con
# empresa, por ella; con solo obra, por `maestro.obras`; sin nada, «mezcla las 38
# empresas») y cada ficha sin empresa ni obra lo dice de sí misma. Estos tests vigilan
# ahora eso: que la frase esté donde hace falta y que no mienta donde está.
# ---------------------------------------------------------------------------

#: Columnas que permiten aplicar el criterio sin cruzar con nada.
COLUMNAS_EMPRESA = ("empresa_id", "empresa")
FRASE_SIN_EMPRESA = "mezcla las 38 empresas"


def _fichas() -> dict[str, dict]:
    """`esquema.objeto` -> ficha, de los esquemas del `ambito`, sin las funciones."""
    fichas = {}
    for esquema in _reglas()[CODIGO]["ambito"]:
        datos = yaml.safe_load((DICC / f"{esquema}.yaml").read_text(encoding="utf-8"))
        for nombre, ficha in (datos.get("objetos") or {}).items():
            if ficha.get("tipo") != "funcion":
                fichas[f"{esquema}.{nombre}"] = ficha
    return fichas


def _columnas(ficha: dict) -> set[str]:
    return set((ficha.get("columnas") or {}).keys())


def _dice_que_mezcla(ficha: dict) -> bool:
    return FRASE_SIN_EMPRESA in _plano(str(ficha.get("descripcion", ""))).lower()


def test_f144_la_regla_dice_que_sin_empresa_no_se_puede_suponer_ruesma() -> None:
    texto = _plano(_reglas()[CODIGO]["regla"])
    for termino in (
        "sin empresa ni obra", FRASE_SIN_EMPRESA,
        "NO dice «he supuesto Construcciones Ruesma»",
        "cada ficha dice su caso",
    ):
        assert termino in texto, f"la regla no dice «{termino}»"


def test_f144_ya_no_afirma_que_todo_compras_tiene_empresa() -> None:
    texto = _plano(_reglas()[CODIGO]["regla"])
    assert "`empresa_id` en `maestro`, `compras`, `retenciones`" not in texto
    assert "los partes de `personal`" not in texto


@pytest.mark.parametrize(
    "objeto",
    ["compras.facturas", "compras.albaranes", "compras.vencimientos",
     "compras.v_facturas_pago", "compras.documento_alarmas",
     "compras_restringida.documento_alarmas", "personal.partes",
     "retenciones.v_pbi_retencion_entidad", "retenciones.v_pbi_retencion_resumen",
     "retenciones.v_pbi_retenciones_vivas", "retenciones.v_pbi_retenciones_vencidas"],
)
def test_f144_nombra_los_objetos_sin_empresa_que_cazo_el_review(objeto: str) -> None:
    assert _dice_que_mezcla(_fichas()[objeto]), (
        f"`{objeto}` no tiene empresa ni obra y su ficha no lo dice"
    )


def test_f144_lo_que_dice_que_mezcla_de_verdad_no_tiene_empresa_ni_obra() -> None:
    """El sentido contrario: una ficha con empresa u `obra_id` que dijese «mezcla las
    38 empresas» haría que la IA no filtrase pudiendo."""
    for nombre, ficha in _fichas().items():
        if _dice_que_mezcla(ficha):
            cols = _columnas(ficha) & {*COLUMNAS_EMPRESA, "obra_id"}
            assert not cols, f"`{nombre}` dice que mezcla y tiene {sorted(cols)}"


def test_f144_control_el_recorrido_lee_fichas_con_y_sin_empresa() -> None:
    fichas = _fichas()
    con_empresa = {n for n, f in fichas.items() if _columnas(f) & set(COLUMNAS_EMPRESA)}
    que_mezclan = {n for n, f in fichas.items() if _dice_que_mezcla(f)}
    assert len(con_empresa) >= 20, "el recorrido de fichas no lee nada"
    assert len(que_mezclan) >= 11, "el recorrido no ve la frase en las fichas"


def test_f144_el_ambito_alcanza_a_compras_restringida() -> None:
    assert "compras_restringida" in _reglas()[CODIGO]["ambito"]
