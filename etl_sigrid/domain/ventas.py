# etl_sigrid/domain/ventas.py
"""
VENTAS (F-040, fase 1): el lado de ingresos. La certificación es `cer`
(`con.tip` 54) con sus líneas `cerpro`; la factura de venta, `dvf` (`con.tip`
11) con `dvfpro`; el cliente, `cli` (`con.tip` 4); el efecto de cobro, `cob`,
ya publicado en `tesoreria.efectos`. Mediciones en solo lectura del 2026-11-06
y del 2026-11-07: `progress/spec_F-040.md`.

LA REGLA LA EJECUTA SQL (`sql/ventas/`) y la ingesta la recorta en origen
(`config/tables_sigrid.yaml`, listas blancas). Aquí está escrita **una sola
vez** como oráculo puro: quién es persona física (R6), si un CIF es válido
(R8), a qué columna va cada recargo (R11) y el estado del seguimiento de una
certificación (R18). `tests/test_f040_sql.py` comprueba que el SQL lleva LOS
MISMOS literales y `tests/test_f040_sandbox.py`, que da los mismos resultados.
Mismo patrón que `domain/postventa.py` (F-156).

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Final

# ---------------------------------------------------------------------------
# Tipos de documento (`con.tip`), destinos y estados
# ---------------------------------------------------------------------------

TIP_CERTIFICACION: Final[int] = 54
TIP_FACTURA_VENTA: Final[int] = 11
TIP_CLIENTE: Final[int] = 4
#: `cerprodes.docdestip`: el destino de una línea de certificación que es una
#: factura de venta (el 100 % de las 4.349 filas, medido el 2026-11-06).
DOCDESTIP_FACTURA_VENTA: Final[int] = 11
#: Estados de `conest` tip 54 que son certificación DE VERDAD: 2 Aprobada por
#: gerencia, 3 Emitida, 4 Aprobada por propiedad. El 1 (Pendiente de emisión)
#: es un borrador y no cuenta.
ESTADOS_CERT_CUENTAN: Final[tuple[int, ...]] = (2, 3, 4)

# ---------------------------------------------------------------------------
# R1-R3 · Lo que entra en `raw` (design_detalle.md § A)
# ---------------------------------------------------------------------------

COLUMNAS_CLI_NEGOCIO: Final[tuple[str, ...]] = (
    "ide", "tipcif", "cifpai", "cif", "raz", "perfis", "cenide", "taride", "secide",
    "pagide", "efeide", "cueide", "cueretide",
)
#: D6: el contacto del cliente entra en `raw`, pero solo se publica en
#: `ventas_restringida` (perfil total).
COLUMNAS_CLI_CONTACTO: Final[tuple[str, ...]] = (
    "dir1", "dir2", "dircpo", "dir", "tel", "tel2", "ele",
)
COLUMNAS_CLI: Final[tuple[str, ...]] = COLUMNAS_CLI_NEGOCIO + COLUMNAS_CLI_CONTACTO
#: Lo que de `cli` NUNCA entra: cuentas bancarias, fax, duplicados sin
#: formato, correos de facturación, nombres de persona (vacíos), contraseña.
PREFIJOS_PROHIBIDOS_CLI: Final[tuple[str, ...]] = (
    "ban", "fax", "telsin", "tel2sin", "fac", "nom", "g3w",
)
COLUMNAS_PROHIBIDAS_CLI: Final[frozenset[str]] = frozenset({
    "fecnac", "numseg", "clamai", "dirtex", "web", "dniper", "munide", "proide",
    "paiide", "g3wpas",
})

COLUMNAS_CER: Final[tuple[str, ...]] = (
    "ide", "cla", "entide", "cenide", "obride", "ctride", "expide", "fas", "fecdoc",
    "fecfac", "estfac", "idefac", "docoriide", "pagide", "efeide", "ivaide", "impbru",
    "impnet", "impdes", "imprec", "totbas", "totiva", "totdoc", "tot", "totpag",
    "totproori", "totprcori",
)
COLUMNAS_CERPRO: Final[tuple[str, ...]] = (
    "ide", "docide", "pos", "res", "can", "pre", "tot", "ivaide", "ivacuo", "cenide",
    "obride", "paride", "docoritip", "docoriide", "linoriide", "imporiori", "imporiant",
    "canoriori",
)
COLUMNAS_DVFPRO: Final[tuple[str, ...]] = (
    "ide", "docide", "pos", "res", "can", "pre", "tot", "ivaide", "ivacuo", "cenide",
    "obride", "paride", "docoritip", "docoriide", "linoriide", "unimed", "proide",
)
#: Las 9 de F-150 (delante y en su orden: `tesoreria` las lee) y 15 más.
COLUMNAS_DVF_NEGOCIO: Final[tuple[str, ...]] = (
    "ide", "cla", "entide", "cenide", "ctride", "fecdoc", "totbas", "totiva", "totdoc",
    "obride", "fas", "tot", "totpag", "impbru", "impnet", "impdes", "imprec", "ivaide",
    "pagide", "efeide", "estfac", "docoriide", "expide", "cueide",
)
#: D6: el nombre y el CIF de la cabecera y las nueve direcciones. Entran en
#: `raw` y solo se publican en `ventas_restringida.factura_cabecera`.
COLUMNAS_PERSONALES_DVF: Final[tuple[str, ...]] = (
    "entcif", "entres", "diremp1", "dircon1", "dirdir1", "diremp2", "dircon2",
    "dirdir2", "diremp3", "dircon3", "dirdir3",
)
COLUMNAS_DVF: Final[tuple[str, ...]] = COLUMNAS_DVF_NEGOCIO + COLUMNAS_PERSONALES_DVF
#: De `dvf` nunca entran, además de todo `ban*`.
COLUMNAS_PROHIBIDAS_DVF: Final[frozenset[str]] = frozenset({
    "emptex", "entcod", "entref", "entciftip", "entcifpai", "empcif",
})

#: R24: ninguna columna del esquema `ventas` empieza así. Los nombres de
#: `ventas_restringida` los usan A PROPÓSITO: la guarda los busca en `ventas`.
PREFIJOS_PROHIBIDOS_EN_VENTAS: Final[tuple[str, ...]] = (
    "direccion", "telefono", "correo", "cif_cabecera", "nombre_cabecera",
)

# ---------------------------------------------------------------------------
# R6 · persona física
# ---------------------------------------------------------------------------

#: Lo que se quita al normalizar: espacios, puntos y guiones. Escrito para que
#: valga IGUAL en Python y en el ARE de PostgreSQL (`ventas.fn_cif_normalizado`).
PATRON_SEPARADORES_CIF: Final[str] = r"[\s.-]"
#: NIF de persona: DNI (8 cifras), NIE (X/Y/Z) o K/L/M, más 7 cifras y letra.
PATRON_NIF_PERSONA: Final[str] = r"^[0-9KLMXYZ][0-9]{7}[A-Z]$"
#: R2-a (enmienda del humano, 2026-11-10): el mismo NIF con un prefijo de país
#: de dos letras delante (`ES12345678Z`). Un NIF nunca empieza por dos letras
#: (tras la K/L/M/X/Y/Z va una cifra), así que el prefijo no es ambiguo; y una
#: sociedad con prefijo (`ESB12345678`, `FR12345678901`) no casa y se queda igual.
PATRON_NIF_CON_PREFIJO_PAIS: Final[str] = r"^[A-Z]{2}[0-9KLMXYZ][0-9]{7}[A-Z]$"


def normalizar_cif(cif: str | None) -> str | None:
    """Mayúsculas, sin espacios, guiones ni puntos; vacío -> None (R5).

    R2-a: un prefijo de país se quita SOLO si lo que queda es un NIF de persona.
    """
    if cif is None:
        return None
    limpio = re.sub(PATRON_SEPARADORES_CIF, "", cif).upper()
    if re.match(PATRON_NIF_CON_PREFIJO_PAIS, limpio):
        return limpio[2:]
    return limpio or None


def es_persona_fisica(cif_normalizado: str | None, perfis: int | None) -> bool:
    """`perfis` <> 0 o un CIF con forma de NIF de persona (R6)."""
    if (perfis or 0) != 0:
        return True
    return bool(cif_normalizado and re.match(PATRON_NIF_PERSONA, cif_normalizado))


def persona_fisica_de_factura(persona_del_cliente: bool | None) -> bool:
    """La factura es de persona física si su cliente lo es o si no hay cliente
    que lo diga (no está en `raw.cli`, o `entide` a 0): R2-b, enmienda del
    humano del 2026-11-10. Su descripción va entonces a `ventas_restringida`."""
    return True if persona_del_cliente is None else persona_del_cliente


def codigo_cliente_publicado(codigo: str | None, persona_fisica: bool) -> str | None:
    """El código del cliente (`con.cod`) que se publica en `ventas` (R24, R1-H1).

    NULL si el cliente es persona física o si el código, normalizado como un
    CIF, tiene forma de NIF de persona: en Sigrid el código lo escribe quien da
    de alta al cliente y puede ser su DNI. El íntegro, en `ventas_restringida`.
    """
    if persona_fisica:
        return None
    normalizado = normalizar_cif(codigo)
    if normalizado and re.match(PATRON_NIF_PERSONA, normalizado):
        return None
    return codigo


# ---------------------------------------------------------------------------
# R8 · CIF válido
# ---------------------------------------------------------------------------

LETRAS_DNI: Final[str] = "TRWAGMYFPDXBNJZSQVHLCKE"
PATRON_DNI: Final[str] = r"^[0-9]{8}[A-Z]$"
PATRON_NIE: Final[str] = r"^[XYZ][0-9]{7}[A-Z]$"
PATRON_NIF_KLM: Final[str] = r"^[KLM][0-9]{7}[A-Z]$"
PATRON_CIF_SOCIEDAD: Final[str] = r"^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$"
_NIE_A_CIFRA: Final[dict[str, str]] = {"X": "0", "Y": "1", "Z": "2"}


def cif_valido(cif_normalizado: str | None) -> bool:
    """Letra de control en DNI y NIE; K/L/M y CIF de sociedad, por forma (R8)."""
    c = cif_normalizado or ""
    if re.match(PATRON_DNI, c):
        return LETRAS_DNI[int(c[:8]) % 23] == c[8]
    if re.match(PATRON_NIE, c):
        return LETRAS_DNI[int(_NIE_A_CIFRA[c[0]] + c[1:8]) % 23] == c[8]
    return bool(re.match(PATRON_NIF_KLM, c) or re.match(PATRON_CIF_SOCIEDAD, c))


# ---------------------------------------------------------------------------
# R11-R12 · las cuatro columnas de los recargos
# ---------------------------------------------------------------------------

#: Clase 0: los coeficientes (`COEF_RECGG`, `COEF_RECBI`, `COEF_DESADJ`).
CLASE_COEFICIENTES: Final[int] = 0
#: Clase 1: el `RETESP` «Retención 5% garantía (sin iva)», 16,78 M EUR en venta.
CLASE_RETESP: Final[int] = 1
#: D4 = A, PROVISIONAL (humano, 2026-11-07): garantía = clases 4 y 5, como en
#: compras (F-128). PREGUNTA PENDIENTE A JUAN ROMERO (Control de Costes, correo
#: del líder): ¿el `RETESP` de venta es garantía? Si dice que sí, ESTE es el
#: ÚNICO cambio: `(1, 4, 5)`, y el literal de `ventas.fn_clase_recargo` en
#: `sql/ventas/00_setup.sql`, que `tests/test_f040_sql.py` obliga a igualar.
#: El `RETESP` pasa entonces a `retencion_garantia` y su columna queda a 0.
CLASES_GARANTIA: tuple[int, ...] = (4, 5)
#: Las cuatro columnas, en el orden de su prioridad en `clase_recargo`.
CLASES_RECARGO: Final[tuple[str, ...]] = ("COEFICIENTES", "GARANTIA", "RETESP", "OTRAS")


def clase_recargo(reccla: int | None) -> str:
    """La columna de un recargo: coeficientes, garantía, `RETESP` u otras (R11)."""
    if reccla == CLASE_COEFICIENTES:
        return "COEFICIENTES"
    if reccla in CLASES_GARANTIA:
        return "GARANTIA"
    if reccla == CLASE_RETESP:
        return "RETESP"
    return "OTRAS"


def repartir_recargos(recargos: Iterable[tuple[int | None, Decimal]]) -> dict[str, Decimal]:
    """Suma las cuotas `(reccla, cuo)` en las cuatro columnas, sin solaparse (R11)."""
    columnas = {clase: Decimal("0") for clase in CLASES_RECARGO}
    for reccla, cuota in recargos:
        columnas[clase_recargo(reccla)] += cuota
    return columnas


# ---------------------------------------------------------------------------
# R18 · el seguimiento de una certificación hasta el cobro
# ---------------------------------------------------------------------------

ESTADOS_SEGUIMIENTO: Final[tuple[str, ...]] = (
    "BORRADOR", "SIN_FACTURA", "FACTURADA_SIN_EFECTO", "PENDIENTE_COBRO",
    "COBRADA_PARCIAL", "COBRADA",
)
#: Lo cobrado a menos de un céntimo de lo emitido es «cobrada».
TOLERANCIA_COBRO: Final[Decimal] = Decimal("0.01")

#: R20: los eslabones de `ventas.cobertura_enlace`. El cuarto, FACTURA_CLIENTE
#: (R2-b, enmienda del humano, 2026-11-10), cuenta las facturas cuyo cliente
#: está en `raw.cli`: las que no, se tratan como persona física.
ESLABONES_COBERTURA: Final[tuple[str, ...]] = (
    "CERTIFICACION_FACTURA", "FACTURA_EFECTO", "EFECTO_FACTURA", "FACTURA_CLIENTE",
)


def estado_seguimiento(
    estado_cert: int | None,
    num_facturas: int | None,
    num_efectos: int | None,
    emitido: Decimal | None,
    cobrado: Decimal | None,
) -> str:
    """El estado de una certificación, con esta precedencia (R18).

    `num_efectos`, `emitido` y `cobrado` son los de los efectos de COBRO NO BAJA
    de sus facturas (`R-TESORERIA-ESTADO`).
    """
    if estado_cert not in ESTADOS_CERT_CUENTAN:
        return "BORRADOR"
    if not num_facturas:
        return "SIN_FACTURA"
    if not num_efectos:
        return "FACTURADA_SIN_EFECTO"
    emitido = emitido or Decimal("0")
    cobrado = cobrado or Decimal("0")
    if cobrado <= 0:
        return "PENDIENTE_COBRO"
    if cobrado < emitido - TOLERANCIA_COBRO:
        return "COBRADA_PARCIAL"
    return "COBRADA"
