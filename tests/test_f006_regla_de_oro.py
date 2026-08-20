# tests/test_f006_regla_de_oro.py
"""
`R-SIGRID-CON` no puede afirmar en absoluto lo que solo es frecuente (7ª pasada).

La primera versión de la regla decía que `cod`, `res` y `fec` viven en `con`
«**no en la tabla específica**». Es un patrón dominante, no una ley, y como la
regla es **bloqueante** y va adjunta a las 31 fichas de `raw`, negaba un campo
que existe y está cargado:

* `sigrid_tablas.md` da `obr.res = "Nombre completo"`, y `raw.obr` se ingiere con
  `exclude_columns: []`, así que la columna está en Postgres.
* `prv.cif` = "CIF/NIF" y `prv.raz` = "Razón social" son de `raw.prv`, y lo
  confirma el repositorio por partida doble: `maestro/02_proveedores.sql` toma
  `p.cif` y `p.raz` de `raw.prv`, y solo `cod`/`res` de `raw.con`.

Una regla bloqueante que niega un campo real es peor que no tenerla: manda al
agente a buscar `con.cif`, que es exactamente el error que la regla existe para
evitar.

Este fichero fija la forma de la regla —que nombre sus excepciones y que no
afirme en absoluto— y contrasta las excepciones contra el SQL del repositorio,
que es la fuente de primera mano.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"

#: Tablas «Propiedades de `con`» que TIENEN campos propios con esos nombres, y
#: por tanto son la excepción que la regla debe nombrar. Salen de barrer las
#: filas de entidad de `azure-apps/sigrid_tablas.md`.
#:
#: No se derivan en tiempo de test a propósito: ese documento es la conversión
#: literal de un PDF de 380 páginas y **no se deja parsear de forma fiable** —lo
#: intenté y el segmentador daba resultados distintos según cómo se detectara la
#: fila de entidad—. Escribirlas aquí las convierte en una afirmación revisable,
#: que es más honesto que una derivación que no se sostiene.
CON_CAMPOS_PROPIOS = ("obr", "prv", "cen", "ctr", "com", "dca", "dcf")


@lru_cache(maxsize=1)
def _regla():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    porcodigo = {r.codigo: r for r in dicc.reglas}
    assert "R-SIGRID-CON" in porcodigo
    return porcodigo["R-SIGRID-CON"]


def _texto() -> str:
    r = _regla()
    return f"{r.regla}\n{r.motivo}"


def test_f006_r9_la_regla_no_niega_los_campos_propios_de_la_tabla() -> None:
    """La formulación absoluta era falsa. No puede volver.

    Se mira **`regla`, no `motivo`**: `regla` es el imperativo que el agente
    obedece, y `motivo` es la explicación, que para contar por qué cambió tiene
    que citar la formulación equivocada. Mismo criterio que ya se aplicó al
    ejemplo de `design.md`: la prosa puede nombrar el error, el contrato no.
    """
    texto = _regla().regla.lower()
    for prohibida in (
        "no en la tabla específica",
        "no en la tabla especifica",
        "nunca en la tabla",
    ):
        assert prohibida not in texto, (
            f"la regla vuelve a afirmar en absoluto («{prohibida}»). `obr.res` y "
            f"`prv.cif` existen y están cargados: es un patrón, no una ley"
        )


#: El marcador que separa «lista de tablas que son propiedades de `con`» de
#: «lista de tablas que ADEMÁS tienen campos propios». Sin él, comprobar que los
#: siete nombres aparecen en la regla pasaba por coincidencia: ya aparecían, en
#: la enumeración de las «Propiedades de `con`», que es otra cosa.
MARCADOR_EXCEPCIONES = "campos propios"


def test_f006_r9_la_regla_nombra_sus_excepciones() -> None:
    """Un patrón sin sus excepciones escritas se lee como ley."""
    texto = _texto()
    assert MARCADOR_EXCEPCIONES in texto, (
        f"la regla tiene que enumerar las tablas con {MARCADOR_EXCEPCIONES!r} "
        f"detrás de ese marcador, no solo mencionarlas de pasada"
    )
    despues = texto[texto.index(MARCADOR_EXCEPCIONES):]
    faltan = [t for t in CON_CAMPOS_PROPIOS if f"`{t}`" not in despues]
    assert faltan == [], (
        f"la regla no nombra como excepción a {faltan}: son tablas «Propiedades "
        f"de con» que tienen campos propios con esos nombres"
    )


def test_f006_r9_la_regla_ubica_el_cif_donde_esta() -> None:
    """El caso que se estrella: buscar `con.cif`.

    En el imperativo, `con.cif` solo puede aparecer para desaconsejarlo; se
    comprueba que si aparece sea junto a la advertencia.
    """
    imperativo = _regla().regla
    assert "prv.cif" in imperativo, "la regla tiene que decir dónde está el CIF"
    if "con.cif" in imperativo:
        assert "inexistente" in imperativo, (
            "si la regla nombra `con.cif` tiene que ser para avisar de que no existe"
        )


def test_f006_r9_el_repositorio_confirma_que_el_cif_sale_de_prv() -> None:
    """Verificación de primera mano, no del PDF: lo que hace nuestro propio SQL."""
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
        assert "inexistente" in texto, (
            "si la ficha nombra `con.cif` tiene que ser para avisar de que no existe, "
            "que es distinto de ubicar allí el campo"
        )


@pytest.mark.parametrize("tabla", ["obr", "prv"])
def test_f006_r26_las_fichas_de_las_excepciones_lo_advierten(tabla: str) -> None:
    """Quien lea solo la ficha de `obr` también tiene que enterarse."""
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    ficha = dicc.por_nombre[f"raw.{tabla}"]
    texto = f"{ficha.descripcion} {ficha.motivo_no_consumo}"
    assert MARCADOR_EXCEPCIONES in texto, (
        f"la ficha de raw.{tabla} tiene que decir que la tabla tiene "
        f"{MARCADOR_EXCEPCIONES!r} además de los de `con`; es una de las "
        f"excepciones de la regla, y quien lea solo la ficha también se estrella"
    )
