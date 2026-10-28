# etl_sigrid/domain/proyeccion_caja.py
"""
Los ingredientes para pasar el devengo de una obra a caja (F-140, fase 2 de la
cartera de F-037). Dominio puro: sin dependencias de infraestructura.

**EL DATAMART NO CONVIERTE DEVENGO EN CAJA** (regla del humano). Este módulo
lee la fórmula de plazo de Sigrid, calcula el pendiente de una partida y lo
reparte en el tiempo, y valida y resuelve las HIPÓTESIS de conversión; nunca
aplica un plazo, una retención o un IVA a un importe ni a una fecha. La
conversión la hace la IA en vivo, declarando cada hipótesis con su valor y su
nivel (`R-CAJA-HIPOTESIS`).

Es el ORÁCULO del SQL de `sql/tesoreria/` (patrón de F-135): el SQL no lo
llama, pero lleva los mismos literales (`REGEX_TOKEN_DIAS`,
`REGEX_TOKEN_RETENCION`, `SEPARADOR_TOKENS`, el orden de `resolver_hipotesis`)
y `tests/test_f140_sql.py` los compara.

**La fórmula de plazo** (`auxpag.formul`, `auxcob.formul`, medida en las 70 +
52 formas el 2026-10-24): tokens separados por blancos; `N` son los días de un
vencimiento y `NR` los del efecto de RETENCIÓN. `30 60 90` son tres
vencimientos; `120 450R`, uno a 120 días y la retención a 450. Lo que no casa
con esa gramática NO se interpreta: falla cerrado (R8).

**El pendiente de una partida** (R12, D3-A): máx(0, plan de la versión V desde
su mes - ejecutado real en el intervalo [mes de V, último cierre]). Lo
ejecutado de más es `sobre_ejecutado` y no resta a otras partidas.

**El reparto en el tiempo** (R14, D19-A): el pendiente de la partida, en
proporción al plan de V de cada mes posterior al cierre; el último mes del
perfil absorbe el redondeo. Sin perfil, todo al primer mes pendiente, marcado
como retraso.

**F-150, la receta** (R1, R7, R9, R22, R25): cada hipótesis dice en qué paso de
`PASOS_RECETA` se aplica; el perfil `PERFIL_MESES` reparte un importe entero
en meses; los coeficientes, el IVA y la retención salen del CONTRATO con el
cliente de cada partida (`leer_coeficientes_contrato`, `coeficiente_venta`),
y el hueco de facturación de H26 es NETO POR OBRA (`hueco_facturacion`). Sigue
sin aplicar nada a un importe de caja: publica ingredientes.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# La fórmula de plazo (R7, R8)
# ---------------------------------------------------------------------------

#: Un token de días de vencimiento: solo dígitos.
REGEX_TOKEN_DIAS = r"^[0-9]+$"
#: El token de la retención: dígitos y una `R` mayúscula final.
REGEX_TOKEN_RETENCION = r"^[0-9]+R$"
#: El separador de tokens, el de `regexp_split_to_array(btrim(f), '\s+')`.
SEPARADOR_TOKENS = r"\s+"
#: Lo que quita `btrim(f)` sin segundo argumento: solo espacios.
_BLANCO_DE_BTRIM = " "


class PlazoFormula(NamedTuple):
    """Lo que dice una fórmula: días de cada vencimiento, de la retención y si se reconoció.

    Una fórmula no reconocida da `((), None, False)`: no se adivina nada.
    """

    dias_vencimientos: tuple[int, ...]
    dias_retencion: int | None
    reconocida: bool


_NO_RECONOCIDA = PlazoFormula((), None, False)


def leer_formula_plazo(formula: str | None) -> PlazoFormula:
    """Lee una fórmula de plazo de Sigrid (R7) o falla cerrado (R8).

    Vacía, `None`, un token que no es `N` ni `NR` o dos `NR`: no reconocida.
    Los días van en el orden escrito. Blancos repetidos separan como uno.
    """
    if formula is None:
        return _NO_RECONOCIDA
    recortada = formula.strip(_BLANCO_DE_BTRIM)
    if not recortada:
        return _NO_RECONOCIDA
    dias: list[int] = []
    retenciones: list[int] = []
    for token in re.split(SEPARADOR_TOKENS, recortada):
        if re.search(REGEX_TOKEN_DIAS, token):
            dias.append(int(token))
        elif re.search(REGEX_TOKEN_RETENCION, token):
            retenciones.append(int(token[:-1]))
        else:
            return _NO_RECONOCIDA
    if len(retenciones) > 1:
        return _NO_RECONOCIDA
    return PlazoFormula(tuple(dias), retenciones[0] if retenciones else None, True)


# ---------------------------------------------------------------------------
# El pendiente de una partida y su reparto (R12, R14)
# ---------------------------------------------------------------------------

_CENTIMO = Decimal("0.01")
_CERO = Decimal(0)


def pendiente_partida(
    plan_desde_version: Decimal, ejecutado_intervalo: Decimal
) -> tuple[Decimal, Decimal]:
    """`(pendiente, sobre_ejecutado)` de una partida (R12).

    `pendiente = máx(0, plan - ejecutado)` y `sobre_ejecutado = máx(0,
    ejecutado - plan)`: nunca los dos a la vez, y su diferencia es la del plan
    y lo ejecutado.
    """
    diferencia = plan_desde_version - ejecutado_intervalo
    return max(_CERO, diferencia), max(_CERO, -diferencia)


def _redondear(valor: Decimal) -> Decimal:
    """`ROUND(numeric, 2)` de PostgreSQL: la mitad, lejos del cero."""
    return valor.quantize(_CENTIMO, rounding=ROUND_HALF_UP)


def repartir_pendiente(
    pendiente: Decimal,
    perfil: Sequence[tuple[date, Decimal]],
    primer_mes: date,
) -> list[tuple[date, Decimal, bool]]:
    """Reparte el pendiente de una partida en sus meses (R14, D19-A).

    `perfil` es el plan de V en cada mes posterior al último cierre. Los meses
    a cero no son perfil (la cola a cero no es plan, criterio de F-110). Si el
    perfil queda vacío o su suma no es positiva, todo va a `primer_mes` con
    `es_retraso` cierto: es lo planificado y no ejecutado que la versión ya no
    sitúa en ningún mes futuro. Si no, cada mes recibe `pendiente * plan_mes /
    plan_total` redondeado al céntimo y el ÚLTIMO mes, el resto: la suma
    iguala el pendiente exactamente. Sin pendiente, no hay reparto.

    Devuelve `[(mes, importe, es_retraso)]` en orden de mes.
    """
    if pendiente == 0:
        return []
    meses = sorted((mes, plan) for mes, plan in perfil if plan != 0)
    total = sum((plan for _mes, plan in meses), _CERO)
    if not meses or total <= 0:
        return [(primer_mes, pendiente, True)]
    reparto: list[tuple[date, Decimal, bool]] = []
    acumulado = _CERO
    for mes, plan in meses[:-1]:
        importe = _redondear(pendiente * plan / total)
        acumulado += importe
        reparto.append((mes, importe, False))
    reparto.append((meses[-1][0], pendiente - acumulado, False))
    return reparto


# ---------------------------------------------------------------------------
# El contrato con el cliente de una partida: coeficientes e IVA (F-150, R7, R18)
# ---------------------------------------------------------------------------

#: `raw.obrctr.coestr` es una LÍNEA por concepto (`\r\n`, medido el 2026-10-27).
SEPARADOR_LINEAS = r"\r?\n"
#: Cada línea: `CODIGO|etiqueta|valor||base`; código = campo 1, valor = campo 3.
SEPARADOR_CAMPOS = "|"
#: Un valor de coeficiente: número con punto decimal, con signo menos opcional.
REGEX_PORCENTAJE_COEF = r"^-?[0-9]+(\.[0-9]+)?$"
#: A qué clase va cada código (N10). Manda el CÓDIGO, nunca la etiqueta: la
#: combinada «Gastos Generales+Beneficio Industrial|23.79» lleva `COEF_RECGG`.
#: Las `RET*` son la retención declarada en el contrato: NO son coeficiente.
#: Un código fuera de aquí hace la fila NO reconocida (falla cerrado).
CLASE_POR_CODIGO: dict[str, str] = {
    "COEF_RECGG": "gg",
    "COEF_RECBI": "bi",
    "COEF_RECCC": "otros",
    "COEF_RECSYS": "otros",
    "COEF_DESADJ": "baja",
    "RETN": "retencion",
    "RETESP": "retencion",
    "RETNT": "retencion",
}
_CLASES_COEFICIENTE = ("gg", "bi", "otros", "baja")
_SEIS_DECIMALES = Decimal("0.000001")
_CUATRO_DECIMALES = Decimal("0.0001")


class CoeficientesContrato(NamedTuple):
    """Lo que dice el `coestr` de un contrato, en puntos porcentuales (R7).

    Cada clase es la SUMA de sus líneas, o `None` si no tiene ninguna. Vacío,
    `NULL`, un código desconocido o un valor no numérico: todo `None` y
    `reconocido` falso, sin quedarse con el trozo que sí se entiende.
    """

    gg: Decimal | None
    bi: Decimal | None
    otros: Decimal | None
    baja: Decimal | None
    retencion: Decimal | None
    reconocido: bool


_SIN_COEFICIENTES = CoeficientesContrato(None, None, None, None, None, False)


def leer_coeficientes_contrato(texto: str | None) -> CoeficientesContrato:
    """Lee `coestr` por líneas y por código (R7, N10) o falla cerrado.

    Las líneas se recortan de espacios (`btrim`) y las vacías se ignoran; el
    valor (campo 3) también se recorta. Sin ninguna línea: sin dato.
    """
    if texto is None:
        return _SIN_COEFICIENTES
    lineas = [ln.strip(_BLANCO_DE_BTRIM) for ln in re.split(SEPARADOR_LINEAS, texto)]
    lineas = [ln for ln in lineas if ln]
    if not lineas:
        return _SIN_COEFICIENTES
    sumas: dict[str, Decimal] = {}
    for linea in lineas:
        campos = linea.split(SEPARADOR_CAMPOS)
        clase = CLASE_POR_CODIGO.get(campos[0])
        valor = campos[2].strip(_BLANCO_DE_BTRIM) if len(campos) > 2 else ""
        if clase is None or not re.search(REGEX_PORCENTAJE_COEF, valor):
            return _SIN_COEFICIENTES
        sumas[clase] = sumas.get(clase, _CERO) + Decimal(valor)
    return CoeficientesContrato(
        sumas.get("gg"), sumas.get("bi"), sumas.get("otros"), sumas.get("baja"),
        sumas.get("retencion"), True,
    )


def factor_coeficientes(c: CoeficientesContrato) -> Decimal | None:
    """El coeficiente de venta del contrato, a 6 decimales (R7), o `None`.

    GG, BI y otros se SUMAN y la baja va en CASCADA sobre ese subtotal de
    contrata: `(1 + (gg + bi + otros) / 100) x (1 + baja / 100)`
    (1,19 x 0,8723 = 1,038037). Sin reconocer, o sin ningún coeficiente
    (solo retención), `None`: la partida cae al master.
    """
    if not c.reconocido or all(getattr(c, k) is None for k in _CLASES_COEFICIENTE):
        return None
    contrata = Decimal(1) + ((c.gg or _CERO) + (c.bi or _CERO) + (c.otros or _CERO)) / _CIEN
    factor = contrata * (Decimal(1) + (c.baja or _CERO) / _CIEN)
    return factor.quantize(_SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def porcentaje_iva(fraccion: Decimal | float | None) -> Decimal | None:
    """`raw.iva.iva` (tanto por uno) en porcentaje con 4 decimales (R18).

    0 es 0 (inversión del sujeto pasivo): un valor, no la falta de él.
    """
    if fraccion is None:
        return None
    return (Decimal(str(fraccion)) * _CIEN).quantize(_CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# El coeficiente de venta de una partida (F-150, R9) y sus importes (R11, R20)
# ---------------------------------------------------------------------------

#: De dónde sale el coeficiente de venta de una partida, en orden de mando.
FUENTES_COEFICIENTE: tuple[str, ...] = ("CONTRATO", "MASTER_CERT", "MASTER_VENTA", "SIN")
#: El ámbito de `stg.presupuesto` de cada fuente del master (D3).
AMBITO_COEFICIENTE: dict[str, int] = {"MASTER_CERT": 9, "MASTER_VENTA": 11}
#: De dónde sale el IVA y la retención de una partida: su contrato o nada.
FUENTES_DATO_CONTRATO: tuple[str, ...] = ("CONTRATO", "SIN")
#: El motivo con que `08` publica la H12 leída de la ficha de la obra (R21).
MOTIVO_H12_FICHA = "Ficha de la obra (tipo de IVA)"
#: La fuente de la venta real SIN coeficiente propio en el hueco (N9).
FUENTE_MEDIA_OBRA = "MEDIA_OBRA"


def _coeficiente_master(importe: Decimal | None, oficial: Decimal | None) -> Decimal | None:
    """`ROUND(oficial / importe, 6)`; sin importe (o a 0), `None`; sin oficial, el importe."""
    if importe is None or importe == 0:
        return None
    oficial = importe if oficial is None else oficial
    return (Decimal(oficial) / Decimal(importe)).quantize(_SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def coeficiente_venta(
    contrato: Decimal | None,
    importe_cert: Decimal | None,
    oficial_cert: Decimal | None,
    importe_venta: Decimal | None,
    oficial_venta: Decimal | None,
) -> tuple[Decimal | None, str]:
    """`(coeficiente, fuente)` de una partida de VENTA (R9).

    Manda el del CONTRATO; si no, el de certificación del master (ámbito 9)
    si su importe no es `None` ni 0; si no, el de venta (ámbito 11); si no,
    `(None, "SIN")`. Es el `COALESCE` de `07` en el mismo orden.
    """
    if contrato is not None:
        return contrato, "CONTRATO"
    cert = _coeficiente_master(importe_cert, oficial_cert)
    if cert is not None:
        return cert, "MASTER_CERT"
    venta = _coeficiente_master(importe_venta, oficial_venta)
    if venta is not None:
        return venta, "MASTER_VENTA"
    return None, "SIN"


def importe_con_coeficiente(importe: Decimal, coeficiente: Decimal | None) -> Decimal | None:
    """`ROUND(importe x coeficiente, 2)` (R11); sin coeficiente, `None`."""
    if coeficiente is None:
        return None
    return _redondear(importe * coeficiente)


def importe_por_porcentaje(base: Decimal, porcentaje: Decimal | None) -> Decimal | None:
    """`ROUND(base x porcentaje / 100, 2)` (R20); sin porcentaje, `None`."""
    if porcentaje is None:
        return None
    return _redondear(base * porcentaje / _CIEN)


# ---------------------------------------------------------------------------
# El hueco de facturación de H26 (F-150, R22, N6, N9)
# ---------------------------------------------------------------------------


def hueco_facturacion(
    real_con_coeficientes: Decimal | None, facturado: Decimal | None
) -> tuple[Decimal, Decimal]:
    """`(pendiente_facturar, facturado_por_delante)` de una OBRA, al céntimo (R22).

    `(máx(0, real - facturado), máx(0, facturado - real))`: nunca los dos
    positivos. Lo facturado por delante no se cobra: no resta a nada. `None`
    cuenta 0.
    """
    diferencia = (real_con_coeficientes or _CERO) - (facturado or _CERO)
    return _redondear(max(_CERO, diferencia)), _redondear(max(_CERO, -diferencia))


def coeficiente_medio(
    pares: Sequence[tuple[Decimal | None, Decimal | None]]
) -> Decimal | None:
    """Σ (real x coef) / Σ real de una obra, a 6 decimales (R22, `MEDIA_OBRA`).

    Solo cuentan los pares con real y coeficiente: los que no tienen
    coeficiente son los que RECIBEN la media. Σ real 0 (o nada): `None`.
    """
    validos = [(r, c) for r, c in pares if r is not None and c is not None]
    total = sum((r for r, _c in validos), _CERO)
    if total == 0:
        return None
    ponderado = sum((r * c for r, c in validos), _CERO)
    return (ponderado / total).quantize(_SEIS_DECIMALES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Lo que no se publica (R16)
# ---------------------------------------------------------------------------

#: El nombre de una columna de CAJA: una fecha, un mes o un importe que saldría
#: de APLICAR un plazo, una retención o un IVA a un devengo. Ninguna tabla de
#: F-140 la tiene (`tests/test_f140_sql.py`).
PATRON_COLUMNA_DE_CAJA = r"caja|flujo|previst|fecha_pago|fecha_cobro|con_iva"


def es_columna_de_caja(nombre: str) -> bool:
    """True si el nombre casa con `PATRON_COLUMNA_DE_CAJA`, sin distinguir mayúsculas."""
    return re.search(PATRON_COLUMNA_DE_CAJA, nombre, flags=re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# Las hipótesis de conversión (R1-R3, R5; D13, D14, D17, D18)
# ---------------------------------------------------------------------------

#: Las unidades de un valor de hipótesis (lista cerrada, R2).
#: `PERFIL_MESES` (F-150, R25) reparte un importe ENTERO en varios meses.
UNIDADES: tuple[str, ...] = (
    "DIAS", "MESES", "PORCENTAJE", "BOOLEANO", "OPCION", "MAPA_DIAS", "PERFIL_MESES",
)
#: Los pasos de la receta de la caja (F-150, R1, D7), en su orden: la IA pasa
#: el devengo a caja SIEMPRE así, y cada hipótesis dice en cuál se aplica.
PASOS_RECETA: tuple[str, ...] = (
    "DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA", "CARTERA",
)
#: El mes más lejano de un perfil (R25): diez años desde el hecho.
MAX_MESES_PERFIL = 120
#: El NIVEL de un valor declarado (`R-CAJA-HIPOTESIS`): el del catálogo, el de
#: la obra (personalizado o leído de Sigrid) o el que da el usuario en vivo.
NIVELES: tuple[str, ...] = ("DEFECTO", "OBRA", "USUARIO")
#: De dónde sale un valor publicado en `tesoreria.hipotesis_caja_obra`.
FUENTES: tuple[str, ...] = ("DEFECTO", "SIGRID", "MANUAL")
#: La precedencia de `resolver_hipotesis` y del `CASE` de `08` (R5).
ORDEN_FUENTES: tuple[str, ...] = ("MANUAL", "SIGRID", "DEFECTO")
#: A qué flujo afecta una hipótesis.
SENTIDOS: tuple[str, ...] = ("PAGO", "COBRO", "AMBOS")
#: El código de una hipótesis: `H` y dos cifras.
REGEX_CODIGO_HIPOTESIS = r"^H[0-9]{2}$"
#: La clave de obra del YAML: `empresa-codigo` (`R-CODIGO-POR-EMPRESA`).
REGEX_CLAVE_OBRA = r"^[0-9]+-\S.*$"
#: Las hipótesis que `08` resuelve como SIGRID: H09-H11 de los contratos con
#: el cliente (D18-A) y, desde F-150 (N2), H12 de la ficha de la obra.
CODIGOS_SIGRID: tuple[str, ...] = ("H09", "H10", "H11", "H12")

_CAMPOS_OBLIGATORIOS = (
    "codigo", "sentido", "descripcion", "unidad", "valor_defecto",
    "fuente_defecto", "ingrediente", "validado", "admite_obra", "paso_receta",
)
_CAMPOS_OPCIONALES = ("opciones", "fecha_validacion")
_CAMPOS_OBRA = ("clave_obra", "codigo", "valor", "motivo", "fecha")


@dataclass(frozen=True, slots=True)
class Hipotesis:
    """Una hipótesis del catálogo, ya validada (R1)."""

    codigo: str
    sentido: str
    descripcion: str
    unidad: str
    valor_defecto: Any
    fuente_defecto: str
    ingrediente: str | None
    validado: bool
    admite_obra: bool
    opciones: tuple[str, ...] = ()
    fecha_validacion: date | None = None
    #: F-150 (R1): al final y con defecto, para no romper a quien ya la construye.
    paso_receta: str = ""


def _es_entero(valor: Any) -> bool:
    """Entero de verdad: `True` no es un número de días."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool)


def _es_texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _es_fecha(valor: Any) -> bool:
    """Una fecha sin hora: YAML lee `2026-10-25` como `date`."""
    return isinstance(valor, date) and not isinstance(valor, datetime)


#: Los decimales que admite un porcentaje de perfil: céntimos de punto.
_DECIMALES_PERFIL = 2
_CIEN = Decimal(100)


def _errores_de_par(n: int, par: Any, meses_anterior: int | None) -> tuple[list[str], int | None]:
    """Los errores del par `n` de un perfil y los meses que deja como «anterior»."""
    meses, porcentaje = par
    errores: list[str] = []
    if not (_es_entero(meses) and 0 <= meses <= MAX_MESES_PERFIL):
        errores.append(f"PERFIL_MESES, par {n}: meses {meses!r} no es un entero de 0 a "
                       f"{MAX_MESES_PERFIL}")
    elif meses_anterior is not None and meses <= meses_anterior:
        errores.append(f"PERFIL_MESES, par {n}: meses {meses} no es mayor que el del par "
                       "anterior (creciente estricto)")
    else:
        meses_anterior = meses
    if not (_es_numero(porcentaje) and 0 < porcentaje <= 100):
        errores.append(f"PERFIL_MESES, par {n}: porcentaje {porcentaje!r} no es > 0 y <= 100")
    elif Decimal(str(porcentaje)).as_tuple().exponent < -_DECIMALES_PERFIL:
        errores.append(f"PERFIL_MESES, par {n}: porcentaje {porcentaje!r} tiene mas de "
                       f"{_DECIMALES_PERFIL} decimales")
    return errores, meses_anterior


def _errores_de_perfil(valor: Any) -> list[str]:
    """Un error por cada fallo de un `PERFIL_MESES` (R25); vacía si vale.

    Lista no vacía de pares `[meses, porcentaje]` (lista o tupla de dos):
    `meses` entero de 0 a `MAX_MESES_PERFIL` y estrictamente creciente,
    `porcentaje` > 0 y <= 100 con dos decimales como mucho, y la suma
    exactamente 100 en `Decimal` (en float, 0.1 + 0.2 no es 0.3). La suma
    solo se juzga si todos los pares son pares con porcentaje numérico.
    """
    if not (isinstance(valor, (list, tuple)) and valor):
        return [f"valor {valor!r} no es un PERFIL_MESES: una lista no vacia de pares "
                "[meses, porcentaje]"]
    errores: list[str] = []
    suma: Decimal | None = Decimal(0)
    meses_anterior: int | None = None
    for n, par in enumerate(valor, start=1):
        if not (isinstance(par, (list, tuple)) and len(par) == 2):
            errores.append(f"PERFIL_MESES, par {n} {par!r}: no es un par [meses, porcentaje]")
            suma = None
            continue
        errores_par, meses_anterior = _errores_de_par(n, par, meses_anterior)
        errores.extend(errores_par)
        if suma is not None and _es_numero(par[1]) and par[1] == par[1]:
            suma += Decimal(str(par[1]))
        else:
            suma = None
    if suma is not None and suma != _CIEN:
        errores.append(f"PERFIL_MESES: los porcentajes suman {suma.normalize():f}, no 100")
    return errores


def _errores_de_valor(valor: Any, unidad: str, opciones: Sequence[str]) -> list[str]:
    """Todos los errores de `valor` para `unidad`: el perfil da uno por fallo."""
    if unidad == "PERFIL_MESES":
        return _errores_de_perfil(valor)
    error = _error_de_valor(valor, unidad, opciones)
    return [error] if error else []


def _error_de_valor(valor: Any, unidad: str, opciones: Sequence[str]) -> str | None:
    """Por qué `valor` no vale para `unidad`, o `None` si vale (salvo el perfil)."""
    if unidad in ("DIAS", "MESES"):
        if not (_es_entero(valor) and valor >= 0):
            return f"valor {valor!r} no es un entero >= 0 de {unidad}"
    elif unidad == "PORCENTAJE":
        if not (_es_numero(valor) and 0 <= valor <= 100):
            return f"valor {valor!r} no es un PORCENTAJE entre 0 y 100"
    elif unidad == "BOOLEANO":
        if not isinstance(valor, bool):
            return f"valor {valor!r} no es BOOLEANO (true o false)"
    elif unidad == "OPCION":
        if not (isinstance(valor, str) and valor in opciones):
            return f"valor {valor!r} no es una de las opciones {list(opciones)}"
    elif unidad == "MAPA_DIAS":
        if not (isinstance(valor, dict) and valor):
            return f"valor {valor!r} no es un MAPA_DIAS no vacio"
        for clave, dias in valor.items():
            if not (_es_texto(clave) and _es_entero(dias) and dias >= 0):
                return f"valor {valor!r}: {clave!r} -> {dias!r} no es texto -> entero >= 0"
    return None


def _errores_de_opciones(fila: dict, unidad: Any) -> list[str]:
    opciones = fila.get("opciones")
    if unidad != "OPCION":
        return [] if opciones is None else ["opciones solo vale para la unidad OPCION"]
    if not isinstance(opciones, list) or not opciones:
        return ["la unidad OPCION exige opciones: una lista no vacia"]
    if not all(_es_texto(o) for o in opciones):
        return ["opciones tiene un elemento que no es texto"]
    if len(set(opciones)) != len(opciones):
        return ["opciones tiene elementos repetidos"]
    return []


def _errores_de_fila(fila: dict) -> list[str]:
    """Los errores de UNA hipótesis, sin el prefijo de su código."""
    errores: list[str] = []
    for campo in _CAMPOS_OBLIGATORIOS:
        if campo not in fila:
            errores.append(f"falta el campo {campo}")
    for campo in fila:
        if campo not in _CAMPOS_OBLIGATORIOS and campo not in _CAMPOS_OPCIONALES:
            errores.append(f"campo desconocido {campo}")
    codigo = fila.get("codigo")
    if "codigo" in fila and not (
        isinstance(codigo, str) and re.search(REGEX_CODIGO_HIPOTESIS, codigo)
    ):
        errores.append(f"codigo {codigo!r} no casa con {REGEX_CODIGO_HIPOTESIS}")
    if "sentido" in fila and fila["sentido"] not in SENTIDOS:
        errores.append(f"sentido {fila['sentido']!r} fuera de {list(SENTIDOS)}")
    if "paso_receta" in fila and fila["paso_receta"] not in PASOS_RECETA:
        errores.append(f"paso_receta {fila['paso_receta']!r} fuera de {list(PASOS_RECETA)}")
    unidad = fila.get("unidad")
    unidad_valida = unidad in UNIDADES
    if "unidad" in fila and not unidad_valida:
        errores.append(f"unidad {unidad!r} fuera de {list(UNIDADES)}")
    errores_opciones = _errores_de_opciones(fila, unidad)
    errores.extend(errores_opciones)
    if unidad_valida and "valor_defecto" in fila and not errores_opciones:
        errores.extend(
            _errores_de_valor(fila["valor_defecto"], unidad, fila.get("opciones") or ())
        )
    for campo in ("descripcion", "fuente_defecto"):
        if campo in fila and not _es_texto(fila[campo]):
            errores.append(f"{campo} tiene que ser un texto no vacio")
    ingrediente = fila.get("ingrediente")
    if ingrediente is not None and not _es_texto(ingrediente):
        errores.append("ingrediente tiene que ser un texto no vacio o null")
    for campo in ("validado", "admite_obra"):
        if campo in fila and not isinstance(fila[campo], bool):
            errores.append(f"{campo} tiene que ser true o false")
    fecha = fila.get("fecha_validacion")
    if fila.get("validado") is True and not _es_fecha(fecha):
        errores.append("validado: true exige fecha_validacion (AAAA-MM-DD)")
    if fila.get("validado") is not True and fecha is not None:
        errores.append("fecha_validacion solo vale con validado: true")
    return errores


def validar_catalogo(filas: Sequence[Any]) -> list[str]:
    """Todos los errores del catálogo (R2); la lista vacía es un catálogo válido.

    Junta los errores de todas las filas, no solo el primero: quien corrige el
    YAML ve la lista entera. Cada error lleva el código de su hipótesis (o el
    número de fila si el código no se puede leer).
    """
    if not filas:
        return ["el catalogo de hipotesis esta vacio"]
    errores: list[str] = []
    vistos: set[str] = set()
    for n, fila in enumerate(filas, start=1):
        if not isinstance(fila, dict):
            errores.append(f"fila {n}: no es un mapa de campos")
            continue
        codigo = fila.get("codigo")
        etiqueta = codigo if isinstance(codigo, str) and codigo else f"fila {n}"
        errores.extend(f"{etiqueta}: {e}" for e in _errores_de_fila(fila))
        if isinstance(codigo, str) and codigo:
            if codigo in vistos:
                errores.append(f"{etiqueta}: codigo repetido")
            vistos.add(codigo)
    return errores


def construir_catalogo(filas: Sequence[Any]) -> tuple[Hipotesis, ...]:
    """Las hipótesis del catálogo, en su orden; `ValueError` con TODOS los errores."""
    errores = validar_catalogo(filas)
    if errores:
        raise ValueError("catalogo de hipotesis no valido: " + "; ".join(errores))
    return tuple(
        Hipotesis(
            codigo=f["codigo"],
            sentido=f["sentido"],
            descripcion=f["descripcion"],
            unidad=f["unidad"],
            valor_defecto=copy.deepcopy(f["valor_defecto"]),
            fuente_defecto=f["fuente_defecto"],
            ingrediente=f["ingrediente"],
            validado=f["validado"],
            admite_obra=f["admite_obra"],
            opciones=tuple(f.get("opciones") or ()),
            fecha_validacion=f.get("fecha_validacion"),
            paso_receta=f["paso_receta"],
        )
        for f in filas
    )


def _errores_de_obra(fila: dict, catalogo: Mapping[str, Hipotesis]) -> list[str]:
    errores: list[str] = []
    for campo in _CAMPOS_OBRA:
        if campo not in fila:
            errores.append(f"falta el campo {campo}")
    for campo in fila:
        if campo not in _CAMPOS_OBRA:
            errores.append(f"campo desconocido {campo}")
    clave = fila.get("clave_obra")
    if "clave_obra" in fila and not (
        isinstance(clave, str) and re.search(REGEX_CLAVE_OBRA, clave)
    ):
        errores.append(f"clave_obra {clave!r} no es empresa-codigo (1-0704)")
    codigo = fila.get("codigo")
    hipotesis = catalogo.get(codigo) if isinstance(codigo, str) else None
    if "codigo" in fila and hipotesis is None:
        errores.append(f"codigo {codigo!r} no existe en el catalogo")
    elif hipotesis is not None and not hipotesis.admite_obra:
        errores.append(f"{codigo} no admite valor por obra (admite_obra: false)")
    elif hipotesis is not None and "valor" in fila:
        errores.extend(_errores_de_valor(fila["valor"], hipotesis.unidad, hipotesis.opciones))
    if "motivo" in fila and not _es_texto(fila["motivo"]):
        errores.append("motivo tiene que ser un texto no vacio")
    if "fecha" in fila and not _es_fecha(fila["fecha"]):
        errores.append(f"fecha {fila['fecha']!r} no es una fecha (AAAA-MM-DD)")
    return errores


def validar_valores_obra(
    filas: Sequence[Any], catalogo: Mapping[str, Hipotesis]
) -> list[str]:
    """Todos los errores de la sección `obras` del YAML (R3); vacía = válida.

    El código tiene que existir en el catálogo y admitir valor por obra, y el
    valor casar con SU unidad. Que la obra exista lo comprueba la guarda de
    `08_hipotesis_caja_obra.sql`: el dominio no conoce las obras.
    """
    errores: list[str] = []
    vistos: set[tuple[str, str]] = set()
    for n, fila in enumerate(filas, start=1):
        if not isinstance(fila, dict):
            errores.append(f"obras, fila {n}: no es un mapa de campos")
            continue
        etiqueta = f"obras, fila {n} ({fila.get('clave_obra')!r}, {fila.get('codigo')!r})"
        errores.extend(f"{etiqueta}: {e}" for e in _errores_de_obra(fila, catalogo))
        par = (fila.get("clave_obra"), fila.get("codigo"))
        if all(isinstance(x, str) for x in par):
            if par in vistos:
                errores.append(f"{etiqueta}: valor repetido para la misma obra e hipotesis")
            vistos.add(par)
    return errores


def resolver_hipotesis(defecto: Any, sigrid: Any, manual: Any) -> tuple[Any, str, str]:
    """`(valor, nivel, fuente)` de una hipótesis en una obra (R5).

    MANUAL (la sección `obras` del YAML) gana a SIGRID (leído de los contratos
    con el cliente, solo si es único, D18) y SIGRID al DEFECTO del catálogo.
    `None` es «no hay»; un 0 o un `False` son valores.
    """
    if manual is not None:
        return manual, "OBRA", "MANUAL"
    if sigrid is not None:
        return sigrid, "OBRA", "SIGRID"
    return defecto, "DEFECTO", "DEFECTO"
