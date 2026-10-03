# etl_sigrid/domain/categoria_partida.py
"""
F-113 · La categoría CD/CI/CP/OTRO de una partida. **Dominio puro.**

Es la misma regla que calcula el `WITH RECURSIVE` de `sql/stg/04_partidas.sql`
(columna `categoria`, en sus dos ramas), escrita aquí para probarla sin base de
datos; `tests/test_f113_sql.py` cruza los literales de los dos sitios.

## El defecto que arregla

Hasta F-113 la categoría se adivinaba con `LIKE '%CD%'`, `'%CI%'` y `'%CP%'`
sobre el código del capítulo **raíz**: letras sueltas en cualquier posición.
`AVDA_FRANCIA`, `P1414_PCI` y `P1414_PISCIN` caían en COSTE INDIRECTO (253
partidas de dos obras, medido el 2026-10-03). Sigrid no trae una marca mejor:
`obrparpar.tcaide` vale 0 en las 395.226 filas y `auxobrtca` son tres oficios.

## La regla (opción A, elegida por el humano el 2026-10-03)

* **Raíz** (nivel 0), por **prefijo** en mayúsculas: `CD…` → CD, `CI…` → CI,
  `CP…` → CP. Si no, numérica pura (`^[0-9]+$`) distinta de `34` y `99` → CD
  (la regla de siempre); el resto → OTRO.
* **Intermedio**: si su código, en mayúsculas y sin puntos ni espacios, es
  **exactamente** `CD`, `CI` o `CP` (también `C.I.`), esa categoría manda sobre
  su subárbol. Si no —incluido el nodo colapsado sin código de F-052—, hereda la
  de su padre. Como el recorrido baja de la raíz y cada nodo sobrescribe o
  arrastra, **el más cercano a la partida manda** sin más maquinaria.

Por qué exacto en los intermedios y prefijo en la raíz: las 15 variantes de raíz
medidas (`CD-FII`, `CI.F2`, `CIPD`, `CP.00`…) son todas capítulos CD/CI/CP por
su descripción; bajo raíces CD, en cambio, hay 391 nodos `CI…` y 191 `CP…` que
son partidas de **catálogo** (`CI10` acero, `CPI8001` pilote CPI-8, `CP110`
puerta). Con prefijo en los intermedios, 582 partidas de coste directo pasarían
a CI/CP.
"""

from __future__ import annotations

import re

#: Las tres categorías que un capítulo declara con su código, **en el orden** en
#: que el SQL las prueba. Los prefijos son mutuamente excluyentes, así que el
#: orden no cambia el resultado, pero el texto del SQL se cruza contra esta tupla.
CATEGORIAS_DE_CAPITULO: tuple[str, ...] = ("CD", "CI", "CP")

#: Raíces numéricas que NO son coste directo: `34` es la Orden de Cambio y `99`
#: el capítulo de varios. El resto de raíces numéricas puras, CD.
RAICES_NUMERICAS_FUERA: tuple[str, ...] = ("34", "99")

#: La categoría de una raíz numérica pura que no está en la lista anterior.
CATEGORIA_DE_RAIZ_NUMERICA = "CD"

#: Lo que se quita del código de un intermedio antes de compararlo: así
#: `C.I.` cuenta como `CI` (la 0462 RETAMAR lo escribe así).
CARACTERES_IGNORADOS_EN_INTERMEDIO: tuple[str, ...] = (".", " ")

#: La rama sin capítulo reconocible.
OTRO = "OTRO"

#: `^[0-9]+$`, como el SQL. **No** `str.isdigit`, que acepta `²`.
_NUMERICO_PURO = re.compile(r"[0-9]+")


def categoria_de_raiz(cod: str) -> str:
    """La categoría de un capítulo raíz (R1-R2)."""
    mayusculas = cod.upper()
    for categoria in CATEGORIAS_DE_CAPITULO:
        if mayusculas.startswith(categoria):
            return categoria
    if _NUMERICO_PURO.fullmatch(cod) and cod not in RAICES_NUMERICAS_FUERA:
        return CATEGORIA_DE_RAIZ_NUMERICA
    return OTRO


def categoria_heredada(cod: str, categoria_padre: str) -> str:
    """La categoría de un nodo no raíz (R4-R6): la suya si su código es
    exactamente `CD`/`CI`/`CP`; si no, la de su padre."""
    limpio = cod
    for caracter in CARACTERES_IGNORADOS_EN_INTERMEDIO:
        limpio = limpio.replace(caracter, "")
    limpio = limpio.upper()
    if limpio in CATEGORIAS_DE_CAPITULO:
        return limpio
    return categoria_padre
