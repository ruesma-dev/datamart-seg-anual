# tests/_texto.py
"""
Comparar texto que alguien ha ajustado a 79 columnas (F-006, 13ª pasada).

Una frase escrita en prosa —un docstring, una `descripcion` de ficha, el
`motivo` de una regla— **se parte por donde caiga el ajuste de línea**, y
entonces `"sin implementar" in texto` da `False` aunque la frase esté ahí y el
lector la vea entera. Buscar una subcadena en texto envuelto es comparar contra
un accidente de formato.

Ha aparecido **tres veces** en esta feature:

1. 8ª pasada · la copia escondida en una cabecera YAML.
2. 10ª pasada · el barrido de frases rechazadas, ciego a las frases plegadas por
   un bloque `>-`. Se arregló **solo ahí**.
3. 13ª pasada · el guardián de R28, verde sosteniendo una afirmación falsa
   —`inventario.py` decía «está sin implementar» del comando que existe desde
   ese mismo commit— porque la frase estaba partida entre dos líneas.

La tercera es la que obliga a tratarlo como clase: ocurrió **dentro del
dispositivo escrito para evitar exactamente eso**, y sobre la función cuya única
red de seguridad es R28. Arreglar el caso no sirve; hay que quitar el formato de
la ecuación en todas las comparaciones de prosa.
"""

from __future__ import annotations

import re


def normalizado(texto: str) -> str:
    """El texto con todo espacio en blanco colapsado a un espacio simple.

    Saltos de línea, tabuladores, indentación y espacios dobles pasan a ser un
    único espacio, así que una frase encuentra a su gemela **esté envuelta como
    esté**. No toca mayúsculas ni tildes: eso es contenido, no formato.
    """
    return re.sub(r"\s+", " ", texto)


def contiene(texto: str, frase: str) -> bool:
    """¿Aparece `frase` en `texto`, ignorando cómo esté ajustado?

    Se normalizan **los dos** lados: la frase buscada también puede venir
    escrita en varias líneas dentro de un test.
    """
    return normalizado(frase) in normalizado(texto)


def cuales_de(frases, texto: str) -> list[str]:
    """Las de `frases` que aparecen en `texto`, ignorando el ajuste."""
    return [f for f in frases if contiene(texto, f)]
