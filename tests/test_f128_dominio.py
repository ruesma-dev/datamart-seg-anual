# tests/test_f128_dominio.py
"""F-128 · R1-R4: el oráculo puro de la cabecera de compra.

`etl_sigrid/domain/cabecera_compra.py` fija dos contratos que el SQL tiene que
cumplir: la clase de cada recargo (`reccla`) y qué es retención de garantía
(D2-B: SOLO las clases 4 y 5, el `RETESP` de clase 1 NO), y el INVENTARIO de
las columnas de `dcf` y `dca`: dónde se publica cada una o por qué no.
Sin red ni BBDD.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain import cabecera_compra as cc

RAIZ = Path(__file__).resolve().parents[1]
MODULO = RAIZ / "etl_sigrid" / "domain" / "cabecera_compra.py"
TABLAS = RAIZ / "config" / "tables_sigrid.yaml"

#: Columnas de `dcf` y `dca` en Sigrid, leídas de `INFORMATION_SCHEMA.COLUMNS`
#: por `sigrid-api` el 2026-10-18 (solo lectura): 145 en cada una. `raw` tiene
#: 134 y 132 (más `_ingested_at` y `_source_tiemod`); el resto son las
#: excluidas de `tables_sigrid.yaml` que existen en Sigrid.
COLUMNAS_SIGRID = {"dcf": 145, "dca": 145}


# --- R1 · la clase del recargo ------------------------------------------------

def test_f128_r1_clases_recargo_exactas():
    assert cc.CLASES_RECARGO == {
        0: "RECARGO",
        1: "DESCUENTO",
        3: "RETENCION_FISCAL",
        4: "RETENCION_GARANTIA_TOTAL",
        5: "RETENCION_GARANTIA_BASE",
    }


@pytest.mark.parametrize(
    ("reccla", "esperado"),
    [
        (0, "RECARGO"),
        (1, "DESCUENTO"),
        (2, "OTRA"),
        (3, "RETENCION_FISCAL"),
        (4, "RETENCION_GARANTIA_TOTAL"),
        (5, "RETENCION_GARANTIA_BASE"),
        (6, "OTRA"),
        (-1, "OTRA"),
        (None, "OTRA"),
    ],
)
def test_f128_r1_clase_recargo(reccla, esperado):
    assert cc.clase_recargo(reccla) == esperado


# --- R2 · garantía = clases 4 y 5 (D2-B) ---------------------------------------

@pytest.mark.parametrize(
    ("reccla", "garantia", "fiscal"),
    [
        (0, False, False),
        (1, False, False),  # el RETESP es de clase 1: NO es garantía (D2-B)
        (2, False, False),
        (3, False, True),
        (4, True, False),
        (5, True, False),
        (6, False, False),
        (None, False, False),
    ],
)
def test_f128_r2_garantia_y_fiscal(reccla, garantia, fiscal):
    assert cc.es_retencion_garantia(reccla) is garantia
    assert cc.es_retencion_fiscal(reccla) is fiscal


def test_f128_r2_garantia_no_mira_el_concepto():
    """D2-B: la función tiene UN parámetro; no hay forma de pasarle el código
    del concepto para que el `RETESP` cuente como garantía."""
    import inspect

    assert list(inspect.signature(cc.es_retencion_garantia).parameters) == ["reccla"]


# --- R3 · el inventario ----------------------------------------------------------

def test_f128_r3_motivos_son_los_siete():
    assert cc.MOTIVOS == frozenset(
        {"VACIO", "RESIDUAL", "INTERNO", "REDUNDANTE", "OTRA_FEATURE",
         "CATALOGO_NO_INGERIDO", "NO_INGERIDO"}
    )


@pytest.mark.parametrize("tabla", ["dcf", "dca"])
def test_f128_r3_inventario_una_entrada_por_columna_de_sigrid(tabla):
    inventario = cc.INVENTARIOS[tabla]
    assert len(inventario) == COLUMNAS_SIGRID[tabla]
    assert not [c for c in inventario if c.startswith("_")]


def _excluidas(tabla: str) -> set[str]:
    datos = yaml.safe_load(TABLAS.read_text(encoding="utf-8"))
    for t in datos["tables"]:
        if t["source_table"] == tabla:
            return set(t.get("exclude_columns") or [])
    raise AssertionError(f"{tabla} no está en tables_sigrid.yaml")


@pytest.mark.parametrize("tabla", ["dcf", "dca"])
def test_f128_r3_no_ingerido_es_exactamente_lo_excluido(tabla):
    """NO_INGERIDO solo para las columnas que `tables_sigrid.yaml` excluye, y
    toda columna del inventario que se excluye es NO_INGERIDO."""
    inventario = cc.INVENTARIOS[tabla]
    excluidas = _excluidas(tabla)
    no_ingeridas = {c for c, (m, _) in inventario.items() if m == "NO_INGERIDO"}
    assert no_ingeridas == excluidas & set(inventario)


def test_f128_r3_bancarias_segun_d4b():
    """§5 del diseño: las bancarias van a `compras_restringida`, salvo
    `bantipide` (catálogo no ingerido) y `dca.banide` (interno)."""
    destino = "compras_restringida.documento_cuenta_bancaria."
    for tabla, columnas in {
        "dcf": ("ban", "bancue", "bandig", "banban", "bansuc"),
        "dca": ("ban", "bancue", "bandig", "banban", "bansuc"),
    }.items():
        for col in columnas:
            motivo, nota = cc.INVENTARIOS[tabla][col]
            assert motivo == "PUBLICADO", (tabla, col)
            assert destino in nota, (tabla, col)
    assert cc.INVENTARIO_DCF["banban"][1] == (
        "compras.v_facturas_pago.banco + "
        "compras_restringida.documento_cuenta_bancaria.banco_id"
    )
    assert cc.INVENTARIO_DCF["bantipide"][0] == "CATALOGO_NO_INGERIDO"
    assert cc.INVENTARIO_DCA["bantipide"][0] == "CATALOGO_NO_INGERIDO"
    assert cc.INVENTARIO_DCA["banide"][0] == "INTERNO"
    # Ninguna columna bancaria publicada en un objeto de `compras`, salvo el
    # banco y la sucursal de la factura que `v_facturas_pago` ya daba (F-080).
    for tabla in ("dcf", "dca"):
        for col in ("ban", "bancue", "bandig"):
            assert "compras." not in cc.INVENTARIOS[tabla][col][1].replace(
                "compras_restringida.", ""
            )


def test_f128_r3_decisiones_reflejadas():
    """D1-A (`empide`/`hor` a F-134), D3-A (`dca.pagfor`/`pagtex` no
    ingeridas), D5-A (`cocide`, `eioide`, `almide` sin catálogo), `tot`
    redundante con `totpag`."""
    for tabla in ("dcf", "dca"):
        inv = cc.INVENTARIOS[tabla]
        assert inv["empide"][0] == "OTRA_FEATURE" and "F-134" in inv["empide"][1]
        assert inv["hor"][0] == "OTRA_FEATURE" and "F-134" in inv["hor"][1]
        assert inv["cocide"][0] == "CATALOGO_NO_INGERIDO" and "F-143" in inv["cocide"][1]
        assert inv["eioide"][0] == "CATALOGO_NO_INGERIDO"
        assert inv["almide"][0] == "CATALOGO_NO_INGERIDO"
        assert inv["tot"][0] == "REDUNDANTE"
    assert cc.INVENTARIO_DCA["pagfor"][0] == "NO_INGERIDO"
    assert cc.INVENTARIO_DCA["pagtex"][0] == "NO_INGERIDO"
    assert cc.INVENTARIO_DCF["pagfor"][0] == "PUBLICADO"


def test_f128_r3_publicadas_por_objeto():
    fac = cc.publicadas(cc.INVENTARIO_DCF, "compras.facturas")
    # `importe_retenciones` = totdoc - totpag no es la ruta de UNA columna.
    assert "total_factura" in fac and "importe_retenciones" not in fac
    assert fac[:2] == ["factura_id", "proveedor_id"]
    assert "total_a_pagar" in fac
    dcb = cc.publicadas(cc.INVENTARIO_DCA, "compras_restringida.documento_cuenta_bancaria")
    assert set(dcb) >= {"documento_id", "proveedor_id", "cuenta_bancaria", "numero_cuenta"}
    # Una ruta con ` + ` cuenta en los dos objetos.
    assert "banco" in cc.publicadas(cc.INVENTARIO_DCF, "compras.v_facturas_pago")
    assert "banco_id" in cc.publicadas(
        cc.INVENTARIO_DCF, "compras_restringida.documento_cuenta_bancaria"
    )
    assert cc.publicadas(cc.INVENTARIO_DCF, "compras.no_existe") == []
    assert "totdoc" in cc.columnas_origen(cc.INVENTARIO_DCF, "compras.facturas")
    assert "ban" not in cc.columnas_origen(cc.INVENTARIO_DCF, "compras.facturas")


# --- R4 · el inventario mal hecho se caza -----------------------------------------

def test_f128_r4_inventarios_reales_sin_errores():
    for tabla, inventario in cc.INVENTARIOS.items():
        assert cc.errores_inventario(list(inventario.items())) == [], tabla


def test_f128_r4_motivo_fuera_de_motivos():
    errores = cc.errores_inventario([("x", ("INVENTADO", "nota"))])
    assert errores and "x" in errores[0]


def test_f128_r4_nota_vacia():
    assert cc.errores_inventario([("x", ("VACIO", "  "))])
    assert cc.errores_inventario([("x", ("PUBLICADO", ""))])


def test_f128_r4_publicado_con_ruta_mal_formada():
    assert cc.errores_inventario([("x", ("PUBLICADO", "facturas"))])
    assert cc.errores_inventario([("x", ("PUBLICADO", "compras.facturas.a +"))])
    assert not cc.errores_inventario(
        [("x", ("PUBLICADO", "compras.facturas.a + compras_restringida.t.b"))]
    )


def test_f128_r4_columna_repetida():
    errores = cc.errores_inventario([("x", ("VACIO", "n")), ("x", ("VACIO", "n"))])
    assert errores and "repet" in errores[0]


def _claves_literales(nombre: str) -> list[str]:
    """Las claves del literal `nombre` tal como están ESCRITAS en el fuente: un
    `dict` de Python se traga en silencio una clave repetida."""
    arbol = ast.parse(MODULO.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        destino = None
        if isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            destino, valor = nodo.target.id, nodo.value
        elif isinstance(nodo, ast.Assign) and isinstance(nodo.targets[0], ast.Name):
            destino, valor = nodo.targets[0].id, nodo.value
        if destino == nombre and isinstance(valor, ast.Dict):
            return [k.value for k in valor.keys]
    raise AssertionError(f"{nombre} no es un literal de diccionario en {MODULO.name}")


@pytest.mark.parametrize("nombre", ["INVENTARIO_DCF", "INVENTARIO_DCA"])
def test_f128_r4_sin_claves_repetidas_en_el_fuente(nombre):
    claves = _claves_literales(nombre)
    repetidas = sorted({c for c in claves if claves.count(c) > 1})
    assert repetidas == []
    assert len(claves) == len(getattr(cc, nombre))
