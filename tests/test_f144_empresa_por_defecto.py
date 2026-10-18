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


# ---------------------------------------------------------------------------
# Pasada 2 del review: los objetos SIN empresa ni `obra_id`.
#
# La pasada 1 decía «la columna se llama `empresa_id` en `compras`, `retenciones`…»,
# y no es cierto: `compras.facturas` o `retenciones.v_pbi_retencion_resumen` no tienen
# empresa ni obra y mezclan las 38 empresas. Con aquel texto la IA no filtraba y aun así
# decía «he supuesto Construcciones Ruesma». Estos tests fijan la frase de los objetos
# sin empresa y recorren las fichas para que la lista de la regla sea exacta: el
# siguiente objeto publicado con empresa u `obra_id` tiene que entrar en ella.
# ---------------------------------------------------------------------------

#: Columnas que permiten aplicar el criterio sin cruzar con nada.
COLUMNAS_EMPRESA = ("empresa_id", "empresa")
#: Marcadores que parten la regla en sus tres listas (el orden importa).
MARCA_CON_EMPRESA = "La columna de empresa la tienen exactamente estos objetos:"
MARCA_SOLO_OBRA = "Solo llevan `obra_id`"
MARCA_SIN_EMPRESA = "NO tienen empresa ni `obra_id`"

_NOMBRE = re.compile(r"`([a-z_]+\.[a-z_]+)`")


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


def _tramos() -> tuple[set[str], set[str], set[str]]:
    """Los objetos que la regla nombra en cada una de sus tres listas."""
    texto = _plano(_reglas()[CODIGO]["regla"])
    for marca in (MARCA_CON_EMPRESA, MARCA_SOLO_OBRA, MARCA_SIN_EMPRESA):
        assert marca in texto, f"la regla perdió el marcador «{marca}»"
    a = texto.index(MARCA_CON_EMPRESA)
    b = texto.index(MARCA_SOLO_OBRA)
    c = texto.index(MARCA_SIN_EMPRESA)
    assert a < b < c, "las tres listas van en orden: con empresa, solo obra, sin nada"
    cuantos = lambda t: set(_NOMBRE.findall(t))  # noqa: E731
    return cuantos(texto[a:b]), cuantos(texto[b:c]), cuantos(texto[c:])


def test_f144_la_regla_dice_que_sin_empresa_no_se_puede_suponer_ruesma() -> None:
    texto = _plano(_reglas()[CODIGO]["regla"])
    for termino in (
        MARCA_SIN_EMPRESA,
        "NO se puede aplicar el criterio",
        "mezcla todas las empresas",
        "la cifra es de todas las empresas",
        "NO dice «he supuesto Construcciones Ruesma»",
    ):
        assert termino in texto, f"la regla no dice «{termino}»"


def test_f144_ya_no_afirma_que_todo_compras_tiene_empresa() -> None:
    texto = _plano(_reglas()[CODIGO]["regla"])
    assert "`empresa_id` en `maestro`, `compras`, `retenciones`" not in texto
    assert "los partes de `personal`" not in texto
    assert "`personal.partes_lineas`" in texto


@pytest.mark.parametrize(
    "objeto",
    ["compras.facturas", "compras.albaranes", "compras.vencimientos",
     "compras.v_facturas_pago", "compras.documento_alarmas",
     "compras_restringida.documento_alarmas", "personal.partes",
     "retenciones.v_pbi_retencion_entidad", "retenciones.v_pbi_retencion_resumen",
     "retenciones.v_pbi_retenciones_vivas", "retenciones.v_pbi_retenciones_vencidas"],
)
def test_f144_nombra_los_objetos_sin_empresa_que_cazo_el_review(objeto: str) -> None:
    _, _, sin_empresa = _tramos()
    assert objeto in sin_empresa, f"`{objeto}` no tiene empresa ni obra y la regla no lo dice"


def test_f144_la_lista_con_empresa_es_exacta() -> None:
    fichas = _fichas()
    con_empresa, _, _ = _tramos()
    reales = {n for n, f in fichas.items() if _columnas(f) & set(COLUMNAS_EMPRESA)}
    assert con_empresa == reales, (
        f"faltan en la regla: {sorted(reales - con_empresa)}; "
        f"sobran (sin columna de empresa): {sorted(con_empresa - reales)}"
    )


def test_f144_la_lista_de_solo_obra_es_exacta() -> None:
    fichas = _fichas()
    _, solo_obra, _ = _tramos()
    reales = {
        n for n, f in fichas.items()
        if "obra_id" in _columnas(f) and not _columnas(f) & set(COLUMNAS_EMPRESA)
    }
    # `maestro.obras` se nombra en el tramo como destino del cruce, no como hecho
    assert solo_obra - {"maestro.obras"} == reales, (
        f"faltan en la regla: {sorted(reales - solo_obra)}; "
        f"sobran: {sorted(solo_obra - reales - {'maestro.obras'})}"
    )


def test_f144_lo_que_nombra_sin_empresa_de_verdad_no_la_tiene() -> None:
    fichas = _fichas()
    _, _, sin_empresa = _tramos()
    # los cruces citados en el tramo (destinos con empresa) no son objetos sin empresa
    destinos = {"tesoreria.efectos", "retenciones.movimientos", "maestro.obras",
                "personal.partes_lineas", "compras.fact_compras_linea",
                "compras.factura_lineas", "compras.albaran_lineas"}
    for nombre in sin_empresa - destinos:
        assert nombre in fichas, f"`{nombre}` no es un objeto publicado de los esquemas del ámbito"
        cols = _columnas(fichas[nombre])
        assert not cols & {"empresa_id", "empresa", "obra_id"}, (
            f"`{nombre}` sí tiene {sorted(cols & {'empresa_id', 'empresa', 'obra_id'})}"
        )


def test_f144_control_el_recorrido_ve_un_objeto_con_empresa_sin_nombrar() -> None:
    fichas = _fichas()
    con_empresa, _, _ = _tramos()
    reales = {n for n, f in fichas.items() if _columnas(f) & set(COLUMNAS_EMPRESA)}
    assert len(reales) >= 20, "el recorrido de fichas no lee nada"
    plantado = reales | {"compras.objeto_plantado"}
    assert con_empresa != plantado


def test_f144_el_ambito_alcanza_a_compras_restringida() -> None:
    assert "compras_restringida" in _reglas()[CODIGO]["ambito"]
