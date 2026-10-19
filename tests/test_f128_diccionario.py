# tests/test_f128_diccionario.py
"""F-128 · R25-R31 y R34: el diccionario y la documentación de la cabecera.

Las fichas son lo que lee un agente que no puede preguntar: aquí se fija que
cada columna nueva dice qué es y cuánto cubre, que las fichas de facturas y
albaranes dicen qué NO se publica y por qué (contrastado con el inventario del
dominio, no con una lista copiada), que las trampas medidas (`RETESP`, los AGR,
la retención del albarán y la de su factura) están donde se van a leer, y que
la cuenta del proveedor se anuncia como lo que es: solo del perfil total.
Sin red ni BBDD.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain import cabecera_compra as cc
from tests.test_f128_restringida import COLUMNAS as COLUMNAS_CUENTA
from tests.test_f128_sql import (
    ALBARANES_NUEVAS,
    COLUMNAS_CUADRE_OBRA,
    COLUMNAS_RECARGOS,
    COLUMNAS_RETENCION_FACTURA,
    FACTURAS_NUEVAS,
)

RAIZ = Path(__file__).resolve().parents[1]
DICC = RAIZ / "config" / "diccionario"
GLOBAL = DICC / "00_global.yaml"
VERSION_F128 = 56


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DICC / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"][objeto]


def _columna(esquema: str, objeto: str, columna: str) -> dict:
    valor = _ficha(esquema, objeto)["columnas"][columna]
    return valor if isinstance(valor, dict) else {"significado": valor}


def _plano(texto: str | None) -> str:
    return re.sub(r"\s+", " ", texto or "")


def _reglas() -> dict[str, dict]:
    return {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}


IMPORTES = {
    "importe_bruto", "importe_neto", "importe_descuentos", "importe_recargos",
    "base_imponible", "cuota_iva", "total_factura", "total_documento",
    "importe_retenciones", "importe_retencion_garantia", "importe_retencion_fiscal",
    "total_a_pagar",
}

DOCUMENTOS = [
    ("facturas", FACTURAS_NUEVAS, "dcf", "total_factura"),
    ("albaranes", ALBARANES_NUEVAS, "dca", "total_documento"),
]


# --- R25 · una ficha por columna nueva -----------------------------------------------

@pytest.mark.parametrize(("objeto", "nuevas", "tabla", "total"), DOCUMENTOS)
def test_f128_r25_cada_columna_nueva_tiene_ficha(objeto, nuevas, tabla, total):
    columnas = _ficha("compras", objeto)["columnas"]
    for col in nuevas:
        assert col in columnas, col
        ficha = _columna("compras", objeto, col)
        assert _plano(ficha.get("significado")).strip(), col
        if col in IMPORTES:
            assert ficha.get("agregacion") == "suma", col
            assert ficha.get("unidad") == "EUR", col
        if col.endswith("_id") or col.startswith("fecha_"):
            assert ficha.get("agregacion") == "no_sumable", col


@pytest.mark.parametrize(("objeto", "nuevas", "tabla", "total"), DOCUMENTOS)
def test_f128_r25_las_que_salen_de_sigrid_dicen_su_cobertura(objeto, nuevas, tabla, total):
    """Las columnas que publican una de Sigrid dicen cuánto se informa (§5)."""
    directas = set(cc.publicadas(cc.INVENTARIOS[tabla], f"compras.{objeto}")) & set(nuevas)
    assert len(directas) >= 20
    sin_cobertura = [
        c for c in sorted(directas)
        if "%" not in _plano(_columna("compras", objeto, c).get("significado"))
    ]
    assert sin_cobertura == []


@pytest.mark.parametrize(("objeto", "nuevas", "tabla", "total"), DOCUMENTOS)
def test_f128_r25_las_frases_que_no_pueden_faltar(objeto, nuevas, tabla, total):
    s = lambda c: _plano(_columna("compras", objeto, c)["significado"])  # noqa: E731
    assert "CON IVA" in s(total) and "ANTES de retenciones" in s(total)
    assert "SIN IVA" in s("base_imponible")
    assert "garantia" in s("importe_retenciones") and "fiscal" in s("importe_retenciones")
    assert "manda la obra de la LINEA" in s("obra_cabecera_id")


def test_f128_r25_el_contrato_de_la_factura_es_el_de_cabecera():
    texto = _plano(_columna("compras", "facturas", "contrato_id")["significado"])
    assert "CABECERA" in texto and "6.991" in texto and "86.664" in texto


# --- R26 · lo que NO se publica, por motivo ---------------------------------------------

@pytest.mark.parametrize(("objeto", "nuevas", "tabla", "total"), DOCUMENTOS)
def test_f128_r26_la_ficha_dice_lo_no_publicado_por_motivo(objeto, nuevas, tabla, total):
    descripcion = _plano(_ficha("compras", objeto)["descripcion"])
    inventario = cc.INVENTARIOS[tabla]
    faltan = [
        c for c, (motivo, _) in inventario.items()
        if motivo != cc.PUBLICADO and f"`{c}`" not in descripcion
    ]
    assert faltan == []
    for motivo in {m for m, _ in inventario.values()} - {cc.PUBLICADO}:
        assert motivo in descripcion, motivo
    assert "`compras_restringida.documento_cuenta_bancaria`" in descripcion
    assert "perfil total" in descripcion


def test_f128_r26_albaranes_cifras_por_tipo_y_no_sumar():
    descripcion = _plano(_ficha("compras", "albaranes")["descripcion"])
    for cifra in ("310.907", "2.856", "278", "OTRO 1"):
        assert cifra in descripcion, cifra
    assert "NO se suman" in descripcion


# --- R27 · fichas nuevas y relaciones -----------------------------------------------------

@pytest.mark.parametrize(
    ("esquema", "objeto", "tipo"),
    [
        ("compras", "factura_recargos", "tabla"),
        ("compras", "albaran_recargos", "tabla"),
        ("compras", "fn_clase_recargo", "funcion"),
        ("compras", "fn_es_retencion_garantia", "funcion"),
        ("compras_restringida", "documento_cuenta_bancaria", "tabla"),
        ("retenciones", "retencion_factura", "tabla"),
        ("retenciones", "v_cuadre_factura_obra", "vista"),
        ("retenciones", "fn_es_retencion_garantia", "funcion"),
    ],
)
def test_f128_r27_fichas_nuevas(esquema, objeto, tipo):
    ficha = _ficha(esquema, objeto)
    assert ficha["tipo"] == tipo
    assert ficha["paso_etl"] == ("build_retenciones" if esquema == "retenciones" else "build_compras")
    assert ficha["refresco"] == "nocturno"


@pytest.mark.parametrize(
    ("esquema", "objeto", "columnas"),
    [
        ("compras", "factura_recargos", [c.format(doc="factura") for c in COLUMNAS_RECARGOS]),
        ("compras", "albaran_recargos", [c.format(doc="albaran") for c in COLUMNAS_RECARGOS]),
        ("compras_restringida", "documento_cuenta_bancaria", COLUMNAS_CUENTA),
        ("retenciones", "retencion_factura", COLUMNAS_RETENCION_FACTURA),
        ("retenciones", "v_cuadre_factura_obra", COLUMNAS_CUADRE_OBRA),
    ],
)
def test_f128_r27_las_fichas_documentan_las_columnas_del_sql(esquema, objeto, columnas):
    assert list(_ficha(esquema, objeto)["columnas"]) == columnas


def _relaciones(esquema: str, objeto: str) -> set[tuple[str, str]]:
    return {(r["de"], r["a"]) for r in _ficha(esquema, objeto).get("relaciones") or []}


def test_f128_r27_relaciones():
    assert ("factura_id", "compras.factura_recargos.factura_id") in _relaciones("compras", "facturas")
    assert ("albaran_id", "compras.albaran_recargos.albaran_id") in _relaciones("compras", "albaranes")
    assert ("factura_id", "compras.facturas.factura_id") in _relaciones("compras", "factura_recargos")
    assert ("albaran_id", "compras.albaranes.albaran_id") in _relaciones("compras", "albaran_recargos")
    assert ("proveedor_id", "retenciones.retencion_factura.proveedor_id") in _relaciones(
        "retenciones", "v_cuadre_proveedor"
    )
    assert ("factura_id", "compras.facturas.factura_id") in _relaciones(
        "retenciones", "retencion_factura"
    )


def test_f128_r27_ninguna_ficha_general_apunta_a_la_cuenta():
    """La relación va DESDE la restringida: una ficha que lee el estándar no
    invita a leer lo que le devolvería «permission denied»."""
    for esquema in ("compras", "retenciones"):
        for nombre, ficha in _yaml(f"{esquema}.yaml")["objetos"].items():
            for rel in ficha.get("relaciones") or []:
                assert not rel["a"].startswith("compras_restringida."), f"{esquema}.{nombre}"


# --- R28 · las preguntas de Juan y los AGR --------------------------------------------------

def test_f128_r28_la_pregunta_del_descuadre():
    preguntas = _ficha("retenciones", "retencion_factura")["ejemplos_preguntas"]
    assert "Que facturas explican el descuadre de retenciones del proveedor X" in preguntas


def test_f128_r28_v_cuadre_proveedor_avisa_de_los_agr():
    descripcion = _plano(_ficha("retenciones", "v_cuadre_proveedor")["descripcion"])
    assert "AGR" in descripcion and "2.454" in descripcion and "0,82 M" in descripcion
    assert "`retenciones.retencion_factura`" in descripcion


# --- R29 · el aviso RETESP donde se va a leer ----------------------------------------------

@pytest.mark.parametrize(
    ("esquema", "objeto", "columna"),
    [
        ("compras", "facturas", "importe_retencion_garantia"),
        ("compras", "facturas", "importe_descuentos"),
        ("compras", "factura_recargos", "clase_recargo"),
        ("compras", "albaran_recargos", "clase_recargo"),
    ],
)
def test_f128_r29_retesp_en_las_columnas(esquema, objeto, columna):
    texto = _plano(_columna(esquema, objeto, columna)["significado"])
    assert "`RETESP`" in texto
    assert "DESCUENTO" in texto


def test_f128_r29_retesp_cifras_y_retencion_factura():
    descuentos = _plano(_columna("compras", "facturas", "importe_descuentos")["significado"])
    assert "44 facturas" in descuentos and "871.193" in descuentos and "42 de las 44" in descuentos
    descripcion = _plano(_ficha("retenciones", "retencion_factura")["descripcion"])
    assert "`RETESP`" in descripcion and "SOLO_CONTABLE" in descripcion and "42 de las 175" in descripcion


# --- R30 · la cuenta del proveedor --------------------------------------------------------

def test_f128_r30_la_ficha_empieza_por_el_aviso():
    descripcion = _ficha("compras_restringida", "documento_cuenta_bancaria")["descripcion"]
    assert descripcion.startswith("**ACCESO RESTRINGIDO: solo el perfil total del MCP.**")


def test_f128_r30_cobertura_formato_y_que_es_la_del_documento():
    d = _plano(_ficha("compras_restringida", "documento_cuenta_bancaria")["descripcion"])
    for frase in ("10,6 %", "5,7 %", "IBAN", "44 %", "68 %", "CCC", "31 %", "72 %",
                  "no la ficha actual del proveedor"):
        assert frase in d, frase
    rel = _relaciones("compras_restringida", "documento_cuenta_bancaria")
    assert ("documento_id", "compras.facturas.factura_id") in rel
    assert ("documento_id", "compras.albaranes.albaran_id") in rel


def test_f128_r30_la_regla_la_nombra_sin_cambiar_su_ambito():
    regla = _reglas()["R-COMPRAS-RESTRINGIDA"]
    assert "`compras_restringida.documento_cuenta_bancaria`" in _plano(regla["regla"])
    assert "no tienen version general" in _plano(regla["regla"])
    assert regla["ambito"] == ["compras.documento_alarmas", "compras_restringida"]


def test_f128_r30_ningun_numero_de_cuenta_en_las_fichas():
    from tests.test_f128_restringida import cuentas_en

    for nombre in ("compras.yaml", "compras_restringida.yaml", "retenciones.yaml", "00_global.yaml"):
        assert cuentas_en((DICC / nombre).read_text(encoding="utf-8")) == [], nombre


# --- R31 · la versión ----------------------------------------------------------------------

def _version_de_main() -> tuple[int, str] | None:
    try:
        r = subprocess.run(
            ["git", "show", "main:config/diccionario/00_global.yaml"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return int(yaml.safe_load(r.stdout)["version"]), r.stdout


def test_f128_r31_version_la_siguiente_a_la_de_main():
    """Antes del merge, la de `main` + 1. Después del merge `main` YA es esta
    versión (lleva la entrada de F-128): entonces basta con no bajar de ella.
    Es la lección de F-141/F-144: el «+ 1» a secas pone `main` en rojo el día
    que la feature se fusiona."""
    de_main = _version_de_main()
    if de_main is None:
        pytest.skip("sin git o sin rama main: no se puede comparar")
    version_main, texto_main = de_main
    actual = int(_yaml("00_global.yaml")["version"])
    if "(F-128, " in texto_main:
        assert actual >= version_main
    else:
        assert actual >= version_main + 1


def test_f128_r31_historia_de_versiones():
    assert int(_yaml("00_global.yaml")["version"]) >= VERSION_F128
    assert f"# version {VERSION_F128} (F-128, " in GLOBAL.read_text(encoding="utf-8")


# --- R34 · la documentación de fuera del diccionario ---------------------------------------

ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
CLAUDE_MD = RAIZ / "CLAUDE.md"
AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"


def test_f128_r34_architecture_explica_la_semantica():
    texto = _plano(ARQUITECTURA.read_text(encoding="utf-8"))
    for frase in ("`totdoc`", "`tot`", "`totpag`", "`reccla`", "`RETESP`", "(F-128)",
                  "`compras_restringida.documento_cuenta_bancaria`"):
        assert frase in texto, frase


def test_f128_r34_el_mapa_de_claude_md():
    texto = _plano(CLAUDE_MD.read_text(encoding="utf-8"))
    assert "F-128" in texto
    assert "`compras_restringida.documento_cuenta_bancaria`" in texto
    assert "`retenciones.retencion_factura`" in texto


def test_f128_r34_azure_apps_describe_lo_expuesto():
    if not AZURE_APPS.is_file():
        pytest.skip("azure-apps no está junto a este repositorio")
    texto = _plano(AZURE_APPS.read_text(encoding="utf-8"))
    assert "(F-128, 2026-10-18)" in texto
    for objeto in ("compras.factura_recargos", "compras.albaran_recargos",
                   "compras_restringida.documento_cuenta_bancaria",
                   "retenciones.retencion_factura", "retenciones.v_cuadre_factura_obra"):
        assert f"`{objeto}`" in texto, objeto


# --- Pasada 2 del review: R-EMPRESA-POR-DEFECTO no afirma de más -------------------------

def test_f128_r_empresa_no_atribuye_a_empide_la_empresa():
    """`empide` en `dcf`/`dca` es «Empleado» (índice a `emp`), no la empresa del
    documento; qué es exactamente es de F-134. La regla no puede presentarlo
    como la empresa."""
    texto = _plano(_reglas()["R-EMPRESA-POR-DEFECTO"]["regla"])
    assert "empide" not in texto
