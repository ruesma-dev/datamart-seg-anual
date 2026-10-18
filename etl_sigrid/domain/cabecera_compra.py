# etl_sigrid/domain/cabecera_compra.py
"""
La CABECERA de la factura y del albarán de compra (F-128): la clase de cada
recargo y el inventario de las columnas de `dcf` y `dca`.

DOS CONTRATOS QUE EL SQL TIENE QUE CUMPLIR, escritos aquí una sola vez:

1. **La clase del recargo** (`dcfrec.reccla` / `dcarec.reccla`, = `rec.cla` del
   concepto). Medido el 2026-10-17: 0 recargo (→ `imprec`), 1 descuento
   (→ `impdes`), 3 retención fiscal (IRPF, arrendamientos, notarías), 4
   retención de garantía sobre el TOTAL, 5 retención de garantía sobre la BASE.
   `compras.fn_clase_recargo` y `compras.fn_es_retencion_garantia`
   (`sql/compras/00_setup.sql`) llevan el mismo `CASE`; lo fija
   `tests/test_f128_sql.py`.

   **D2-B (humano, 2026-10-17): garantía = clases 4 y 5 y NADA MÁS.** El
   concepto `RETESP` («Retención 5 % garantía (sin IVA)», 44 facturas, 871.193 €)
   está dado de alta en Sigrid como clase 1, DESCUENTO: baja la base y NO entra
   en `totdoc − totpag`, aunque su asiento vaya a la cuenta de retención del
   proveedor en 42 de las 44. Aquí NO es garantía, y por eso la función no
   recibe el código del concepto: no hay forma de colárselo.

2. **El inventario** de las columnas de `dcf` y `dca` en Sigrid (las de `raw`
   más las que `tables_sigrid.yaml` excluye y existen allí): dónde se publica
   cada una (`PUBLICADO`, con la ruta `<esquema>.<objeto>.<columna>` y, si va a
   dos sitios, las dos unidas por ` + `) o por qué no (uno de `MOTIVOS`, con la
   nota que lo explica). Es DATO medido el 2026-10-17/18 (informe
   `progress/spec_F-128.md`, §5 y §7) y es el contrato que los tests contrastan
   con el SQL: una columna que el SQL lea de `dcf` sin estar aquí como
   publicada, o al revés, pone un test en rojo. Una columna NUEVA de `raw.dcf`
   no la detecta ningún test offline: se ve con la consulta MANUAL del diseño
   (§11, paso 2).

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

# ---------------------------------------------------------------------------
# 1 · La clase del recargo
# ---------------------------------------------------------------------------

#: `reccla` → su literal. El 2 no existe en los datos (medido); lo que no esté
#: aquí, o venga a NULL, es `OTRA`.
CLASES_RECARGO: Final[dict[int, str]] = {
    0: "RECARGO",
    1: "DESCUENTO",
    3: "RETENCION_FISCAL",
    4: "RETENCION_GARANTIA_TOTAL",
    5: "RETENCION_GARANTIA_BASE",
}

#: Las clases que son retención de garantía (D2-B). El `RETESP`, de clase 1, no.
CLASES_GARANTIA: Final[frozenset[int]] = frozenset({4, 5})

#: La clase de la retención fiscal.
CLASE_FISCAL: Final[int] = 3


def clase_recargo(reccla: int | None) -> str:
    """El literal de la clase de un recargo; `OTRA` si no está o es None."""
    if reccla is None:
        return "OTRA"
    return CLASES_RECARGO.get(reccla, "OTRA")


def es_retencion_garantia(reccla: int | None) -> bool:
    """Verdadero SOLO para las clases 4 y 5 (D2-B). Falso para None."""
    return reccla is not None and reccla in CLASES_GARANTIA


def es_retencion_fiscal(reccla: int | None) -> bool:
    """Verdadero solo para la clase 3 (IRPF, arrendamientos, notarías)."""
    return reccla == CLASE_FISCAL


# ---------------------------------------------------------------------------
# 2 · El inventario de `dcf` y `dca`
# ---------------------------------------------------------------------------

#: Por qué una columna de la cabecera NO se publica.
MOTIVOS: Final[frozenset[str]] = frozenset(
    {
        "VACIO",  # 0 % de cobertura (no nulo, no 0, no vacío) en `raw`
        "RESIDUAL",  # cobertura marginal, sin uso que la justifique
        "INTERNO",  # dato interno de Sigrid sin catálogo ni significado medible
        "REDUNDANTE",  # repite otra columna que ya se publica
        "OTRA_FEATURE",  # lo publica (o lo decide) otra feature
        "CATALOGO_NO_INGERIDO",  # es un id de un catálogo que no se ingiere (D5-A)
        "NO_INGERIDO",  # excluida en `tables_sigrid.yaml`: no llega a `raw`
    }
)

#: El literal de una columna publicada.
PUBLICADO: Final[str] = "PUBLICADO"

#: Separador de las rutas de una columna publicada en dos objetos.
SEPARADOR_RUTAS: Final[str] = " + "

_RUTA: Final[re.Pattern[str]] = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z0-9_]+$")

_FAC: Final[str] = "compras.facturas."
_ALB: Final[str] = "compras.albaranes."
_PAGO: Final[str] = "compras.v_facturas_pago."
_DCB: Final[str] = "compras_restringida.documento_cuenta_bancaria."
_RET: Final[str] = "retenciones.retencion_factura."

_VACIO: Final[tuple[str, str]] = ("VACIO", "0 % en dcf y en dca (medido el 2026-10-17)")
_VACIO_DCF: Final[tuple[str, str]] = (
    "VACIO",
    "0 % en dcf; en dca sí se informa (es dato del albarán)",
)
_DIV: Final[tuple[str, str]] = ("VACIO", "importe en divisa: 0 % (todo se factura en euros)")
_CAD: Final[tuple[str, str]] = ("VACIO", "cadena logística (cad*): 0 % en dcf y en dca")
_CPA: Final[tuple[str, str]] = (
    "VACIO",
    "cuenta de pago alternativa (cpa*): 0 % en dcf y en dca",
)
_RESIDUAL: Final[tuple[str, str]] = ("RESIDUAL", "≤ 1 fila en dcf y en dca")
_COPIA: Final[tuple[str, str]] = (
    "INTERNO",
    "copia/paso de documentos (docori*, pas*): ≤ 1,6 %, sin uso de negocio",
)
_F134: Final[tuple[str, str]] = (
    "OTRA_FEATURE",
    "F-134: qué es exige leer `dbo.log` (D1-A); ni se lee ni se publica aquí",
)

#: `dcf` (factura de compra): 134 columnas en `raw` + 11 excluidas = las 145 de
#: Sigrid (`INFORMATION_SCHEMA.COLUMNS`, 2026-10-18). Coberturas: informe §5.
INVENTARIO_DCF: Final[dict[str, tuple[str, str]]] = {
    "ide": (PUBLICADO, f"{_FAC}factura_id + {_DCB}documento_id + {_RET}factura_id"),
    "cla": ("INTERNO", "clase interna (1001 o 0, 74 %) sin catálogo ni significado medible"),
    "entide": (PUBLICADO, f"{_FAC}proveedor_id + {_DCB}proveedor_id + {_RET}proveedor_id"),
    "entcod": (PUBLICADO, f"{_FAC}proveedor_codigo"),
    "entres": (PUBLICADO, f"{_FAC}proveedor_nombre_documento"),
    "entref": (PUBLICADO, f"{_FAC}referencia_proveedor"),
    "entcif": (PUBLICADO, f"{_FAC}proveedor_cif"),
    "ivareq": _VACIO,
    "facper": _VACIO,
    "fecdoc": (PUBLICADO, f"{_FAC}fecha_factura + {_DCB}fecha_documento + {_RET}fecha_factura"),
    "fecpag": _VACIO,
    "hor": _F134,
    "eioide": ("CATALOGO_NO_INGERIDO", "`auxeio` no se ingiere (D5-A); 31,7 %, 5 valores"),
    "eitide": _VACIO,
    "pagide": (PUBLICADO, f"{_PAGO}forma_pago_id"),
    "efeide": (PUBLICADO, f"{_PAGO}medio_pago_id"),
    "cueide": (PUBLICADO, f"{_PAGO}cuenta_contable"),
    "impbru": (PUBLICADO, f"{_FAC}importe_bruto"),
    "impnet": (PUBLICADO, f"{_FAC}importe_neto"),
    "impdes": (PUBLICADO, f"{_FAC}importe_descuentos"),
    "imprec": (PUBLICADO, f"{_FAC}importe_recargos"),
    "totbas": (PUBLICADO, f"{_FAC}base_imponible"),
    "totiva": (PUBLICADO, f"{_FAC}cuota_iva"),
    "totdoc": (PUBLICADO, f"{_FAC}total_factura"),
    "tot": ("REDUNDANTE", "= `totpag` en el 100 % de las facturas: se publica `total_a_pagar`"),
    "totpag": (PUBLICADO, f"{_FAC}total_a_pagar"),
    "cenide": (PUBLICADO, f"{_FAC}centro_coste_cabecera_id"),
    "caaide": (PUBLICADO, f"{_FAC}cuenta_analitica_cabecera_id"),
    "almide": ("CATALOGO_NO_INGERIDO", "`alm` no se ingiere (D5-A); 95,2 %"),
    "ivaide": _VACIO,
    "bul": _VACIO,
    "pes": _VACIO,
    "volum": _VACIO,
    "empide": _F134,
    "ageide": _VACIO,
    "ageimp": _VACIO,
    "obride": (PUBLICADO, f"{_FAC}obra_cabecera_id + {_RET}obra_id"),
    "ctride": (PUBLICADO, f"{_FAC}contrato_id"),
    "fecent": (PUBLICADO, f"{_FAC}fecha_entrega_prevista"),
    "feclim": (PUBLICADO, f"{_FAC}fecha_limite"),
    "fecrec": _VACIO,
    "diremp1": ("REDUNDANTE", "= `entres` (nombre en el documento) en el 99,95 %"),
    "diremp2": (
        "RESIDUAL",
        "línea 2 de la dirección del documento: 1,3 % (medido el 2026-10-18; "
        "el informe §5 no la recogía); la dirección del proveedor no se publica",
    ),
    "diremp3": (
        "RESIDUAL",
        "línea 3 de la dirección del documento: 1,0 % (medido el 2026-10-18; "
        "el informe §5 no la recogía); la dirección del proveedor no se publica",
    ),
    "estser": _VACIO,
    "estfac": _VACIO_DCF,
    "antestser": _VACIO,
    "antestfac": _VACIO_DCF,
    "ivadif": (PUBLICADO, f"{_FAC}iva_diferido"),
    "docoritip": _COPIA,
    "docoriide": _COPIA,
    "comide": ("VACIO", "0 % en dcf (el comparativo va en el albarán y el contrato)"),
    "pasdeside": _COPIA,
    "pasori": _COPIA,
    "divcod": _DIV,
    "divcam": _DIV,
    "emppreide": _RESIDUAL,
    "empconide": _VACIO,
    "docrelide": _VACIO,
    "cocide": (
        "CATALOGO_NO_INGERIDO",
        "tipo de contrato de compra; `auxobrcoc` no se ingiere (D5-A): F-143; 9,4 %",
    ),
    "paclis": _VACIO,
    "tipsininv": _VACIO_DCF,
    "prmide": _VACIO,
    "estped": _VACIO,
    "antestped": _VACIO,
    "empcif": _VACIO,
    "cveide": _VACIO,
    "alqide": _VACIO,
    "alqfec": _VACIO,
    "pexide": _VACIO,
    "divcamfec": _DIV,
    "ctdide": _VACIO,
    "totbasdiv": _DIV,
    "totivadiv": _DIV,
    "totdocdiv": _DIV,
    "totdiv": _DIV,
    "totpagdiv": _DIV,
    "cypnatide": (PUBLICADO, f"{_PAGO}naturaleza_pago"),
    "refarc": _VACIO,
    "horlim": _RESIDUAL,
    "pdpide": _VACIO,
    "ano": _VACIO,
    "mes": _VACIO,
    "refcom": _VACIO,
    "emnet": _VACIO,
    "eg3w": _VACIO,
    "dtumID": ("INTERNO", "dos valores, 14 %, sin catálogo ni significado medible"),
    "cptide": _VACIO,
    "eleenvio": _RESIDUAL,
    "tipisp": (PUBLICADO, f"{_FAC}inversion_sujeto_pasivo"),
    "delide": _VACIO,
    "banide": (PUBLICADO, f"{_PAGO}cuenta_transferencia_id"),
    "banban": (PUBLICADO, f"{_PAGO}banco + {_DCB}banco_id"),
    "bansuc": (PUBLICADO, f"{_PAGO}sucursal + {_DCB}sucursal_id"),
    "bandig": (PUBLICADO, f"{_DCB}digitos_control"),
    "bancue": (PUBLICADO, f"{_DCB}numero_cuenta"),
    "ban": (PUBLICADO, f"{_DCB}cuenta_bancaria"),
    "bantipide": (
        "CATALOGO_NO_INGERIDO",
        "tipo de cuenta; `auxcueban` no se ingiere y no predice el formato (D4-B)",
    ),
    "entciftip": (PUBLICADO, f"{_FAC}proveedor_tipo_identificacion"),
    "entcifpai": (PUBLICADO, f"{_FAC}proveedor_pais_identificacion"),
    "aoside": _VACIO,
    "PFID": _VACIO,
    "cadcod1": _CAD,
    "caddir1": _CAD,
    "cadcod2": _CAD,
    "caddir2": _CAD,
    "cadcod3": _CAD,
    "caddir3": _CAD,
    "cadcod4": _CAD,
    "caddir4": _CAD,
    "cpapai": _CPA,
    "cpaban": _CPA,
    "cpasuc": _CPA,
    "cpaswi": _CPA,
    "cpatip": _CPA,
    "cpadiv": _CPA,
    "cpacue1": _CPA,
    "cpacue2": _CPA,
    "ppoide": _VACIO,
    "fecfac": _VACIO_DCF,
    "horfac": _VACIO_DCF,
    "idefac": _VACIO_DCF,
    "clabieser": _VACIO,
    "facoriide": _VACIO,
    "duaide": _VACIO,
    "numregcon": _VACIO,
    "fas": _VACIO,
    "periodo": _VACIO,
    "tipctr": _VACIO,
    "tipgar": (
        "INTERNO",
        "−1/0; no predice la retención (15.035 frente a 11.813 facturas con garantía)",
    ),
    "impavr": _VACIO,
    "synckey": _VACIO,
    "pagtex": (PUBLICADO, f"{_PAGO}condiciones_pago"),
    "pagfor": (PUBLICADO, f"{_PAGO}formula_pago_documento"),
    # Excluidas en `tables_sigrid.yaml` (medidas en Sigrid el 2026-10-17).
    "eiotex": ("NO_INGERIDO", "0 documentos con texto"),
    "eittra": ("NO_INGERIDO", "0 documentos con texto"),
    "tex": ("NO_INGERIDO", "475 documentos; el memo de verdad es `con.tex` (F-080)"),
    "dircon1": ("NO_INGERIDO", "6.086 documentos; dirección de contacto"),
    "dirdir1": ("NO_INGERIDO", "164.465 documentos; dirección del proveedor (53 bytes)"),
    "dircon2": ("NO_INGERIDO", "< 5.500 documentos; dirección de contacto"),
    "dirdir2": ("NO_INGERIDO", "< 5.500 documentos; dirección del proveedor"),
    "dircon3": ("NO_INGERIDO", "< 5.500 documentos; dirección de contacto"),
    "dirdir3": ("NO_INGERIDO", "< 5.500 documentos; dirección del proveedor"),
    "emptex": ("NO_INGERIDO", "0 documentos con texto"),
    "texent": ("NO_INGERIDO", "7 documentos"),
}

#: `dca` (albarán, proforma y nota): 132 columnas en `raw` + 13 excluidas = las
#: 145 de Sigrid. Coberturas: informe §5.
INVENTARIO_DCA: Final[dict[str, tuple[str, str]]] = {
    "ide": (PUBLICADO, f"{_ALB}albaran_id + {_DCB}documento_id"),
    "cla": ("INTERNO", "clase interna (0,9 %, casi solo proformas) sin catálogo"),
    "entide": (PUBLICADO, f"{_ALB}proveedor_id + {_DCB}proveedor_id"),
    "entcod": (PUBLICADO, f"{_ALB}proveedor_codigo"),
    "entres": (PUBLICADO, f"{_ALB}proveedor_nombre_documento"),
    "entref": (PUBLICADO, f"{_ALB}referencia_proveedor"),
    "entcif": (PUBLICADO, f"{_ALB}proveedor_cif"),
    "ivareq": _VACIO,
    "facper": _VACIO,
    "fecdoc": (PUBLICADO, f"{_ALB}fecha_documento + {_DCB}fecha_documento"),
    "fecpag": _VACIO,
    "hor": _F134,
    "eioide": ("CATALOGO_NO_INGERIDO", "`auxeio` no se ingiere (D5-A); 36,6 %, 5 valores"),
    "eitide": _VACIO,
    "pagide": (PUBLICADO, f"{_ALB}forma_pago_id"),
    "efeide": (PUBLICADO, f"{_ALB}medio_pago_id"),
    "cueide": (PUBLICADO, f"{_ALB}cuenta_contable"),
    "impbru": (PUBLICADO, f"{_ALB}importe_bruto"),
    "impnet": (PUBLICADO, f"{_ALB}importe_neto"),
    "impdes": (PUBLICADO, f"{_ALB}importe_descuentos"),
    "imprec": (PUBLICADO, f"{_ALB}importe_recargos"),
    "totbas": (PUBLICADO, f"{_ALB}base_imponible"),
    "totiva": (PUBLICADO, f"{_ALB}cuota_iva"),
    "totdoc": (PUBLICADO, f"{_ALB}total_documento"),
    "tot": ("REDUNDANTE", "= `totpag` en el 100 %: se publica `total_a_pagar`"),
    "totpag": (PUBLICADO, f"{_ALB}total_a_pagar"),
    "cenide": (PUBLICADO, f"{_ALB}centro_coste_cabecera_id"),
    "caaide": (PUBLICADO, f"{_ALB}cuenta_analitica_cabecera_id"),
    "almide": ("CATALOGO_NO_INGERIDO", "`alm` no se ingiere (D5-A); 99,99 %"),
    "ivaide": _VACIO,
    "bul": _VACIO,
    "pes": _VACIO,
    "volum": _VACIO,
    "empide": _F134,
    "ageide": _VACIO,
    "ageimp": _VACIO,
    "obride": (PUBLICADO, f"{_ALB}obra_cabecera_id"),
    "ctride": (PUBLICADO, f"{_ALB}contrato_id"),
    "fecent": (PUBLICADO, f"{_ALB}fecha_entrega_prevista"),
    "feclim": (PUBLICADO, f"{_ALB}fecha_limite"),
    "fecrec": _VACIO,
    "diremp1": ("REDUNDANTE", "= `entres` (nombre en el documento) en el 99,95 %"),
    "diremp2": (
        "RESIDUAL",
        "línea 2 de la dirección del documento: 1,5 % (medido el 2026-10-18; "
        "el informe §5 no la recogía); la dirección del proveedor no se publica",
    ),
    "diremp3": (
        "RESIDUAL",
        "línea 3 de la dirección del documento: 1,7 % (medido el 2026-10-18; "
        "el informe §5 no la recogía); la dirección del proveedor no se publica",
    ),
    "estser": _VACIO,
    "estfac": (PUBLICADO, f"{_ALB}facturado_sigrid"),
    "antestser": _VACIO,
    "antestfac": ("INTERNO", "estado de facturación ANTERIOR; sin significado de negocio"),
    "ivadif": (PUBLICADO, f"{_ALB}iva_diferido"),
    "docoritip": _COPIA,
    "docoriide": _COPIA,
    "comide": (PUBLICADO, f"{_ALB}comparativo_id"),
    "pasdeside": _COPIA,
    "pasori": _COPIA,
    "divcod": _DIV,
    "divcam": _DIV,
    "emppreide": _RESIDUAL,
    "empconide": _VACIO,
    "docrelide": _VACIO,
    "cocide": (
        "CATALOGO_NO_INGERIDO",
        "tipo de contrato de compra; `auxobrcoc` no se ingiere (D5-A): F-143; 11,8 %",
    ),
    "paclis": _VACIO,
    "tipsininv": ("INTERNO", "marca de stock sin inventario (1,1 %)"),
    "prmide": _VACIO,
    "estped": _VACIO,
    "antestped": _VACIO,
    "empcif": _VACIO,
    "cveide": _VACIO,
    "alqide": _VACIO,
    "alqfec": _VACIO,
    "pexide": _VACIO,
    "divcamfec": _DIV,
    "ctdide": _VACIO,
    "totbasdiv": _DIV,
    "totivadiv": _DIV,
    "totdocdiv": _DIV,
    "totdiv": _DIV,
    "totpagdiv": _DIV,
    "cypnatide": _VACIO,
    "refarc": _VACIO,
    "horlim": _RESIDUAL,
    "pdpide": _VACIO,
    "ano": _VACIO,
    "mes": _VACIO,
    "refcom": _VACIO,
    "emnet": _VACIO,
    "eg3w": _VACIO,
    "dtumID": ("INTERNO", "dos valores, 9 %, sin catálogo ni significado medible"),
    "cptide": _VACIO,
    "eleenvio": _RESIDUAL,
    "tipisp": ("VACIO", "0 % en dca (en dcf es la inversión del sujeto pasivo)"),
    "delide": _VACIO,
    "banide": ("INTERNO", "cuenta de banco PROPIA sin resolver; 0,9 %"),
    "banban": (PUBLICADO, f"{_DCB}banco_id"),
    "bansuc": (PUBLICADO, f"{_DCB}sucursal_id"),
    "bandig": (PUBLICADO, f"{_DCB}digitos_control"),
    "bancue": (PUBLICADO, f"{_DCB}numero_cuenta"),
    "ban": (PUBLICADO, f"{_DCB}cuenta_bancaria"),
    "bantipide": (
        "CATALOGO_NO_INGERIDO",
        "tipo de cuenta; `auxcueban` no se ingiere y no predice el formato (D4-B)",
    ),
    "entciftip": (PUBLICADO, f"{_ALB}proveedor_tipo_identificacion"),
    "entcifpai": (PUBLICADO, f"{_ALB}proveedor_pais_identificacion"),
    "aoside": _VACIO,
    "PFID": _VACIO,
    "cadcod1": _CAD,
    "caddir1": _CAD,
    "cadcod2": _CAD,
    "caddir2": _CAD,
    "cadcod3": _CAD,
    "caddir3": _CAD,
    "cadcod4": _CAD,
    "caddir4": _CAD,
    "cpapai": _CPA,
    "cpaban": _CPA,
    "cpasuc": _CPA,
    "cpaswi": _CPA,
    "cpatip": _CPA,
    "cpadiv": _CPA,
    "cpacue1": _CPA,
    "cpacue2": _CPA,
    "ppoide": _VACIO,
    "fecfac": (PUBLICADO, f"{_ALB}fecha_facturacion"),
    "horfac": ("INTERNO", "hora de la facturación; la fecha se publica"),
    "idefac": (PUBLICADO, f"{_ALB}factura_cabecera_id"),
    "clabieser": _VACIO,
    "facoriide": _VACIO,
    "duaide": _VACIO,
    "numregcon": _VACIO,
    "fas": _VACIO,
    "periodo": _VACIO,
    "tipctr": _VACIO,
    "tipgar": ("INTERNO", "−1/0; no predice la retención"),
    "impavr": _VACIO,
    "synckey": _VACIO,
    # Excluidas en `tables_sigrid.yaml` (medidas en Sigrid el 2026-10-17).
    "eiotex": ("NO_INGERIDO", "0 documentos con texto"),
    "eittra": ("NO_INGERIDO", "0 documentos con texto"),
    "pagtex": (
        "NO_INGERIDO",
        "D3-A: 100 % informada pero 14,8 bytes de media; no se ingiere ni publica",
    ),
    "pagfor": (
        "NO_INGERIDO",
        "D3-A: 100 % informada pero 3,6 bytes de media; no se ingiere ni publica",
    ),
    "tex": ("NO_INGERIDO", "602 documentos; el memo de verdad es `con.tex` (F-080)"),
    "dircon1": ("NO_INGERIDO", "20.889 documentos; dirección de contacto"),
    "dirdir1": ("NO_INGERIDO", "309.683 documentos; dirección del proveedor"),
    "dircon2": ("NO_INGERIDO", "< 5.500 documentos; dirección de contacto"),
    "dirdir2": ("NO_INGERIDO", "< 5.500 documentos; dirección del proveedor"),
    "dircon3": ("NO_INGERIDO", "< 5.500 documentos; dirección de contacto"),
    "dirdir3": ("NO_INGERIDO", "< 5.500 documentos; dirección del proveedor"),
    "emptex": ("NO_INGERIDO", "0 documentos con texto"),
    "texent": ("NO_INGERIDO", "11 documentos"),
}

#: Los dos inventarios por su tabla de Sigrid.
INVENTARIOS: Final[dict[str, dict[str, tuple[str, str]]]] = {
    "dcf": INVENTARIO_DCF,
    "dca": INVENTARIO_DCA,
}


def rutas(nota: str) -> list[str]:
    """Las rutas `<esquema>.<objeto>.<columna>` de una nota de PUBLICADO."""
    return [r.strip() for r in nota.split(SEPARADOR_RUTAS.strip())]


def publicadas(inventario: Mapping[str, tuple[str, str]], objeto: str) -> list[str]:
    """Las columnas del objeto `objeto` (`esquema.objeto`) que publican una
    columna del inventario, en el orden del inventario."""
    salida: list[str] = []
    for motivo, nota in inventario.values():
        if motivo != PUBLICADO:
            continue
        for ruta in rutas(nota):
            destino, _, columna = ruta.rpartition(".")
            if destino == objeto:
                salida.append(columna)
    return salida


def columnas_origen(inventario: Mapping[str, tuple[str, str]], objeto: str) -> set[str]:
    """Las columnas de Sigrid que el inventario declara publicadas en `objeto`."""
    return {
        columna
        for columna, (motivo, nota) in inventario.items()
        if motivo == PUBLICADO
        and any(r.rpartition(".")[0] == objeto for r in rutas(nota))
    }


def errores_inventario(entradas: Sequence[tuple[str, tuple[str, str]]]) -> list[str]:
    """Lo que está mal en un inventario dado como lista de pares (para poder
    ver las claves repetidas, que un `dict` se traga): motivo fuera de
    `MOTIVOS`, nota vacía, ruta de PUBLICADO mal formada o columna repetida.
    Lista vacía si está bien."""
    errores: list[str] = []
    vistas: set[str] = set()
    for columna, (motivo, nota) in entradas:
        if columna in vistas:
            errores.append(f"{columna}: columna repetida")
        vistas.add(columna)
        if not (nota or "").strip():
            errores.append(f"{columna}: nota vacía")
            continue
        if motivo == PUBLICADO:
            malas = [r for r in rutas(nota) if not _RUTA.match(r)]
            if malas:
                errores.append(f"{columna}: ruta mal formada {malas}")
        elif motivo not in MOTIVOS:
            errores.append(f"{columna}: motivo {motivo!r} fuera de MOTIVOS")
    return errores
