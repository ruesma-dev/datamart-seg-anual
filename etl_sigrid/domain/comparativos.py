# etl_sigrid/domain/comparativos.py
"""
El comparativo de ofertas (F-038): qué oferta es ficticia y qué adjudicado es atípico.

POR QUÉ ESTE MÓDULO EXISTE SI LA REGLA LA EJECUTA SQL (R11). Las ofertas viven
en Postgres (`raw.dco`, 71.302 en comparativos) y se marcan en
`compras.comparativo_ofertas` con `compras.fn_familia_ficticia`, definida en
`sql/compras/00_setup.sql`. Lo que NO puede pasar es que los literales —los dos
CIF falsos, los seis patrones de familia, la exclusión y los umbrales del
atípico— vivan escritos en el SQL y en ningún otro sitio: ahí nadie los prueba.
Aquí están escritos **una sola vez**, probados sobre los nombres medidos en
`tests/test_f038_dominio.py`, y `tests/test_f038_sql.py` comprueba que el SQL
lleva **estos mismos**. Mismo patrón que `texto_comentarios.py` (F-080).

LOS PATRONES SON REGEX POSIX: los ejecuta Postgres con `~`. Nada de
lookarounds ni de `\\m`/`\\M` (que `re` no tiene): el nombre normalizado separa
palabras con UN espacio, así que `(^| )` hace de frontera de palabra en los dos
motores.

EL CRITERIO, medido el 2026-10-04 (`progress/spec_F-038.md` §2): el CIF falso
solo cubre 9.821 de 32.899 ficticias (30 %), porque 172 entidades ficticias
tienen el CIF VACÍO; y la entidad tampoco sirve, porque la 977371 firma como
OFICINA TECNICA, OBJETIVO y PLANIFICADO. La familia la dice el NOMBRE de la
oferta (`dco.entres`). Ficticia = CIF falso **o** (CIF vacío **y** nombre de
familia). Con CIF real, nunca.

FASE 2 (R27, R29, D4): el patrón del descuento de la línea (`dcopro.dto`, que
es TEXTO), la tolerancia con que el precio OBJETIVO «casa» con su base del
descompuesto y la regla de la base (ABC o ESTUDIOS). Los ejecuta
`sql/compras/09_comparativos_detalle.sql` con estos mismos literales.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from decimal import Decimal

#: Los dos CIF inventados y la familia que dan cuando el nombre no dice nada
#: (180 ofertas medidas con nombres como `º`, `OBJE`, `TRANIDE`).
CIF_FALSOS: dict[str, str] = {
    "A99999999": "OBJETIVO",
    "A00000000": "OFICINA_TECNICA",
}

#: (familia, patrón POSIX sobre el nombre normalizado), EN ORDEN (R9): gana la
#: primera que case. CUATRIMESTRAL, FASE_0 y ABC van antes que PLANIFICACION
#: porque sus nombres medidos empiezan casi todos por «PLANIFICACION».
#: `FASE ?0( |$)` y no `FASE ?0`: «FASE 05» no es la fase 0.
PATRONES_FAMILIA: tuple[tuple[str, str], ...] = (
    ("OBJETIVO", "(^| )OBJE"),
    ("OFICINA_TECNICA", "OFICINA TE"),
    ("CUATRIMESTRAL", "CUATRIM"),
    ("FASE_0", "FASE ?0( |$)|PLANIFICACION 0$"),
    ("ABC", "(^| )ABC( |$)"),
    ("PLANIFICACION", "PLANIF"),
)

#: Nombres (ya normalizados) que casan una familia y son proveedores REALES
#: (R10). Se buscan como subcadena del nombre normalizado. Medido: 3 ofertas
#: de «MAT Planificación de Espacios, S.L.» sin CIF.
EXCLUSIONES: tuple[str, ...] = ("PLANIFICACION DE ESPACIOS",)

#: Los literales de la normalización, los mismos que el `translate` y el
#: `regexp_replace` de `compras.fn_normalizar_nombre`.
TILDES_ORIGEN = "ÁÉÍÓÚÜÑ"
TILDES_DESTINO = "AEIOUUN"
NO_ALFANUMERICO = "[^A-Z0-9]+"

#: El adjudicado es atípico cuando supera FACTOR_ATIPICO veces la mayor oferta
#: del comparativo Y MINIMO_ATIPICO euros (R16). Medido: 52 comparativos que
#: suman 602,5 M€ de 1.246,2; con 3 veces en vez de 10 salen 65: el corte es
#: estable. Un corte y no una lista de ids, que se queda vieja la noche que
#: entra otro.
FACTOR_ATIPICO = 10
MINIMO_ATIPICO = Decimal("100000")

# ---------------------------------------------------------------------------
# FASE 2 · el porcentaje de la línea y la base del objetivo (R27, R29, D4)
# ---------------------------------------------------------------------------

#: El formato de `dcopro.dto`, que es TEXTO: coma decimal, signo opcional
#: (los negativos son recargos) y el `%` al final. Medido el 2026-10-04: las
#: 95.808 líneas que lo traen lo cumplen todas. Lo que no case es NULL, nunca
#: un error ni un cero; por eso `compras.fn_porcentaje_dto` no necesita
#: `EXCEPTION`: el patrón ya garantiza el cast.
PATRON_DTO = r"^-?[0-9]+(,[0-9]+)?%$"

#: «Casa» = base × (1 − %) da el precio de la línea OBJETIVO con 0,011 € más
#: el 0,2 % del precio de tolerancia: la de la medición de D4 (24.263 de
#: 83.329 líneas casan). La absoluta cubre el redondeo a céntimos de precios
#: de cuatro decimales; la relativa, los importes grandes (A2: 124.367,21
#: contra 124.367,19).
TOLERANCIA_ABS = Decimal("0.011")
TOLERANCIA_REL = Decimal("0.002")

#: Los orígenes de `descompuestos.lineas` que son ESTUDIOS: el master 0 o, en
#: las obras sin master 0, la Descomposición de coste (F-123). Es la única
#: base de una obra SIN primera ABC (D4: «en ese caso no casa; dependerá de
#: Negocio cambiarlo»).
ORIGENES_ESTUDIOS: tuple[str, ...] = ("MASTER_ESTUDIO", "ESTUDIO")

#: Lo que es ANTERIOR a la primera ABC en una obra que la tiene: Estudios y
#: las versiones del master previas a la ABC. NUNCA `MASTER_PLANIF_JO` (la ABC
#: y lo que viene detrás) salvo la propia ABC, ni la planificación de hoy
#: (`PLANIF_JO`): D4 dice «nunca una posterior».
ORIGENES_ANTERIORES_ABC: tuple[str, ...] = ORIGENES_ESTUDIOS + ("MASTER_PRE_ABC",)

_TABLA_TILDES = str.maketrans(TILDES_ORIGEN, TILDES_DESTINO)


def normalizar_nombre(texto: str | None) -> str:
    """Mayúsculas, sin tildes, todo lo que no sea `A-Z0-9` a un espacio.

    Equivale a `btrim(regexp_replace(translate(upper(coalesce(x, '')), ...)))`:
    `btrim` recorta solo espacios, y por eso aquí `strip(" ")`.
    """
    if texto is None:
        return ""
    mayusculas = texto.upper().translate(_TABLA_TILDES)
    return re.sub(NO_ALFANUMERICO, " ", mayusculas).strip(" ")


def familia_ficticia(cif: str | None, nombre: str | None) -> str | None:
    """La familia ficticia de una oferta, o None si la oferta es REAL.

    Orden (design §3): CIF real → real; nombre excluido → real; primera
    familia cuyo patrón case; si ninguna y el CIF es falso, la de su CIF.
    """
    cif_limpio = (cif or "").strip(" ").upper()
    if cif_limpio and cif_limpio not in CIF_FALSOS:
        return None
    normalizado = normalizar_nombre(nombre)
    if any(exclusion in normalizado for exclusion in EXCLUSIONES):
        return None
    for familia, patron in PATRONES_FAMILIA:
        if re.search(patron, normalizado):
            return familia
    return CIF_FALSOS.get(cif_limpio)


def es_adjudicado_atipico(
    adjudicado: Decimal | None, mayor_oferta: Decimal | None
) -> bool | None:
    """True si el adjudicado supera 10 veces la mayor oferta y 100.000 €.

    None —y no False— cuando no hay con qué juzgarlo: sin oferta con importe
    positivo (11 comparativos > 100.000 € medidos) o sin adjudicado (264
    comparativos sin líneas). Es lo que hace el `CASE ... END` sin `ELSE` del
    SQL, y el importe se publica igual (R16).
    """
    if adjudicado is None or mayor_oferta is None or mayor_oferta <= 0:
        return None
    return adjudicado > FACTOR_ATIPICO * mayor_oferta and adjudicado > MINIMO_ATIPICO


def parse_porcentaje_dto(texto: str | None) -> Decimal | None:
    """El porcentaje de `dcopro.dto` en tanto por cien, o None si no casa.

    `'10,08%'` → 10.08, `'-168%'` → −168 (un recargo). Sin recortar espacios,
    igual que el `~` de Postgres: `' 15%'` no casa. `fullmatch`, y no
    `search`, porque el `$` de `re` admite un salto de línea final y el de
    Postgres no.
    """
    if texto is None or re.fullmatch(PATRON_DTO, texto) is None:
        return None
    return Decimal(texto[:-1].replace(",", "."))


def casa_con_base(precio: Decimal, precio_base: Decimal, pct: Decimal) -> bool:
    """True si `precio_base × (1 − pct/100)` da `precio` con la tolerancia.

    La tolerancia es `TOLERANCIA_ABS + TOLERANCIA_REL × |precio|`, sobre el
    precio de la oferta, que es el dato que se intenta reproducir. Un `pct`
    negativo es un recargo y sube la base.
    """
    esperado = precio_base * (1 - pct / 100)
    return abs(precio - esperado) <= TOLERANCIA_ABS + TOLERANCIA_REL * abs(precio)


def base_regla(obra_tiene_primera_abc: bool) -> str:
    """La regla de la base de una obra (D2 del humano): `ABC` o `ESTUDIOS`."""
    return "ABC" if obra_tiene_primera_abc else "ESTUDIOS"
