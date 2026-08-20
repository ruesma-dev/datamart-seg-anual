# tests/test_f006_regla_de_oro.py
"""
`R-SIGRID-CON` no puede afirmar lo que no se sostiene (7ª y 8ª pasada).

Historia corta, porque explica por qué este fichero encogió:

* **7ª pasada.** La regla decía que `cod`, `res` y `fec` viven en `con` «no en
  la tabla específica». Falso: `obr.res` existe. Se reformuló con una lista de
  siete excepciones **escrita a mano** a partir del catálogo en PDF.
* **8ª pasada.** De esas siete, **una era correcta**. `cen.res` no existe —el
  «Reparto nombre» es de `cenrep`, que ni se ingiere—, `ctr`, `com`, `dca`,
  `dcf` y `prv` eran falsos positivos, y **faltaban dieciséis**, ocho de ellas
  leídas a diario sin unir a `con`, entre ellas `obrparpar`, de donde salen el
  código y la descripción de la partida.

El mecanismo que debía impedirlo estaba **en este fichero** y no podía: la lista
era una constante escrita a mano y el test que exigía que las fichas repitieran
la excepción se parametrizaba con `["obr", "prv"]` —**con `cen` dentro habría
fallado**—. El comentario que justificaba no derivar del PDF era cierto, y la
conclusión equivocada: **había una fuente derivable sin usar, nuestro propio
SQL**.

Así que la lista ya no vive aquí. Se **deriva** en
`tests/test_f006_fuente_que_gobierna.py`, barriendo `sql/**` en busca de cada
`alias.campo` de una tabla de `raw`: nuestro SQL no correría contra una columna
inexistente, así que lo que aparece ahí existe. Lo que queda en este fichero es
lo que sigue siendo suyo: que la regla **no vuelva a afirmar en absoluto**, y
que ubique el CIF donde el repositorio demuestra que está.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"


@lru_cache(maxsize=1)
def _regla():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    porcodigo = {r.codigo: r for r in dicc.reglas}
    assert "R-SIGRID-CON" in porcodigo
    return porcodigo["R-SIGRID-CON"]


def test_f006_r9_la_regla_no_afirma_en_absoluto_donde_vive_un_campo() -> None:
    """La formulación absoluta era falsa. No puede volver.

    Se mira **`regla`, no `motivo`**: `regla` es el imperativo que el agente
    obedece, y `motivo` es la explicación, que para contar por qué cambió tiene
    que citar la formulación equivocada.
    """
    texto = _regla().regla.lower()
    for prohibida in (
        "no en la tabla especifica",
        "no en la tabla específica",
        "nunca en la tabla",
        "siempre en `con`",
    ):
        assert prohibida not in texto, (
            f"la regla vuelve a afirmar en absoluto («{prohibida}»). Hay tablas "
            f"cuyos campos propios lee el ETL sin pasar por `con`: es un patrón, "
            f"no una ley"
        )


def test_f006_r9_la_regla_manda_comprobar_en_vez_de_asumir() -> None:
    """Lo que sustituye a la afirmación absoluta tiene que ser una instrucción."""
    texto = _regla().regla.lower()
    assert "no asumas" in texto, (
        "quitar la afirmación falsa no basta: la regla tiene que decir qué hacer "
        "en su lugar, que es comprobar de qué lado sale el campo"
    )


def test_f006_r9_la_regla_ubica_el_cif_donde_esta() -> None:
    """El caso que se estrella: buscar `con.cif`."""
    imperativo = _regla().regla
    assert "prv.cif" in imperativo, "la regla tiene que decir dónde está el CIF"
    if "con.cif" in imperativo:
        assert "inexistente" in imperativo, (
            "si la regla nombra `con.cif` tiene que ser para avisar de que no existe"
        )


def test_f006_r9_el_repositorio_confirma_que_el_cif_sale_de_prv() -> None:
    """Verificación de primera mano: lo que hace nuestro propio SQL.

    Es la única de las siete «excepciones» de la 7ª pasada que sobrevivió, y
    sobrevivió justamente porque tenía esta comprobación detrás y no el PDF.
    """
    sql = (DIR_SQL / "maestro" / "02_proveedores.sql").read_text(encoding="utf-8")
    linea = next(l for l in sql.split("\n") if re.search(r"\bAS\s+cif\s*,?\s*$", l))
    assert re.search(r"\bp\.cif\b", linea), (
        f"esperaba que el CIF saliera del alias de `raw.prv`: {linea.strip()}"
    )
    assert re.search(r"\bFROM\s+raw\.prv\s+p\b", sql), "y que `p` sea `raw.prv`"


def test_f006_r9_la_ficha_de_prv_no_ubica_el_cif_en_con() -> None:
    """La regla y la ficha decían lo mismo mal; que no se separen ahora."""
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    prv = dicc.por_nombre["raw.prv"]
    texto = f"{prv.descripcion} {prv.motivo_no_consumo}"
    assert "prv.cif" in texto, "tiene que decir dónde está el CIF, no callarlo"
    if "con.cif" in texto:
        assert "inexistente" in texto


def test_f006_r9_la_regla_no_promete_nada_del_catalogo_en_pdf() -> None:
    """Lo que solo dice el PDF no se afirma, y la regla lo declara como hueco.

    Dos revisiones seguidas produjeron una afirmación falsa por intentar derivar
    de `sigrid_tablas.md`. La regla ahora dice de dónde sale lo que afirma y qué
    deja fuera; sin esa declaración, el hueco parece un olvido.
    """
    motivo = _regla().motivo
    assert "sigrid_tablas.md" in motivo, (
        "la regla tiene que decir dónde está lo que ella no cubre"
    )
    assert "no se deja segmentar" in motivo or "no es verificable" in motivo, (
        "y por qué no lo afirma: el documento no es una fuente de la que derivar"
    )


def test_f006_r9_la_regla_numera_bien_sus_puntos() -> None:
    """Decía «cinco cosas» y numeraba seis; el punto nuevo quedaba anunciado
    como si no existiera."""
    texto = _regla().regla
    numerados = re.findall(r"\*\*(\d+)\.", texto)
    anunciados = re.search(r"(\w+) cosas", texto)
    assert anunciados, "la regla anuncia cuántos puntos trae"
    PALABRAS = {
        "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    }
    dice = PALABRAS.get(anunciados.group(1).lower())
    assert dice == len(numerados), (
        f"la regla anuncia «{anunciados.group(1)} cosas» y numera "
        f"{len(numerados)}: {numerados}"
    )
