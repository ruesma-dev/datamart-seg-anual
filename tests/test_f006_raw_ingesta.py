# tests/test_f006_raw_ingesta.py
"""
Lo que las fichas de `raw` dicen de sus COLUMNAS EXCLUIDAS (7ª y 8ª pasada).

Este fichero nació contrastando también **cómo se carga** cada tabla, y esa
parte se equivocó dos veces seguidas:

* la 7ª pasada la derivó de `config/tables_sigrid.yaml` —«incremental por
  `tiemod`»—, un fichero de configuración que declara una columna de corte que
  la ingesta no usa para cargar;
* la 8ª la derivó de `ingest_raw_step.py` —«append por `MAX(ide)`, lo modificado
  no se refresca nunca»—, que describe cómo funciona el comando pero **no qué se
  ejecuta de noche**: el `Dockerfile` arranca `run-all --full`, o sea recarga
  entera.

Esa mitad **se ha retirado de aquí** y vive en
`tests/test_f006_fuente_que_gobierna.py`, contrastada contra el `Dockerfile`,
que es la fuente que gobierna el hecho. Dejarla aquí «arreglada» habría sido el
tercer intento de acertar por reconstrucción.

Lo que sí se queda es lo que este fichero siempre pudo derivar bien, porque su
fuente sí gobierna el hecho: **qué columnas no se ingieren**, que lo decide
`exclude_columns` de `config/tables_sigrid.yaml`, y la biyección entre fichas y
tablas ingeridas.

Y una comprobación que en su día pasaba en vacío: la primera versión solo exigía
`citadas <= excluidas`, que se cumple sola cuando la ficha no cita ninguna. De
31 fichas, 11 tenían exclusiones y no decían nada —`dca` y `dcf` con 23 columnas
cada una—. Ahora la ficha tiene que decir **cuántas** son: un número no se puede
escribir en vacío.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FICHERO_RAW = RAIZ / "config" / "diccionario" / "raw.yaml"
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
PASO_INGESTA = RAIZ / "etl_sigrid" / "application" / "steps" / "ingest_raw_step.py"


@lru_cache(maxsize=1)
def _ingesta() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


@lru_cache(maxsize=1)
def _fichas() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


def _nombres() -> list[str]:
    return sorted(_fichas())






def test_f006_r26_hay_una_ficha_por_tabla_ingerida() -> None:
    """Ni de más ni de menos: `raw` es exactamente lo que se ingiere."""
    assert set(_fichas()) == set(_ingesta())






# ---------------------------------------------------------------------------
# Las columnas excluidas: la comprobación que pasaba en vacío
# ---------------------------------------------------------------------------
#
# La primera versión solo exigía `citadas <= excluidas`, que se cumple sola
# cuando la ficha no cita ninguna. De 31 fichas, 11 tenían exclusiones y no
# decían nada —`dca` y `dcf` con 23 columnas cada una— y el test seguía verde.
#
# Ahora la ficha tiene que decir **cuántas** son. Un número no se puede escribir
# en vacío, y además es lo que un agente necesita para entender por qué una
# columna que ve en `sigrid_tablas.md` no está en Postgres.

MARCA_EXCLUIDAS = "No se traen"


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r26_la_ficha_dice_cuantas_columnas_no_se_traen(nombre: str) -> None:
    texto = _fichas()[nombre]["descripcion"]
    excluidas = _ingesta()[nombre]["exclude_columns"]

    if not excluidas:
        assert MARCA_EXCLUIDAS not in texto, (
            f"raw.{nombre} se ingiere entera y su ficha habla de exclusiones"
        )
        return

    assert MARCA_EXCLUIDAS in texto, (
        f"raw.{nombre} deja fuera {len(excluidas)} columnas y su ficha no lo dice. "
        f"Preguntar en `raw` por una columna excluida no devuelve nulo: devuelve "
        f"«columna inexistente»"
    )
    # Los `**` del énfasis van entre el marcador y el número: `**No se traen** 3`.
    assert re.search(rf"{MARCA_EXCLUIDAS}\W{{0,4}}{len(excluidas)}\b", texto), (
        f"la ficha de raw.{nombre} tiene que decir el número exacto "
        f"({len(excluidas)}) detrás de «{MARCA_EXCLUIDAS}»: sin un número, la "
        f"comprobación se cumple sola y la ficha puede callar"
    )


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r26_las_columnas_que_la_ficha_cita_estan_excluidas_de_verdad(
    nombre: str,
) -> None:
    """No se exige listarlas todas —hay tablas con 25— pero lo citado ha de ser cierto."""
    texto = _fichas()[nombre]["descripcion"]
    citadas: set[str] = set()
    for trozo in re.findall(rf"{MARCA_EXCLUIDAS}[^.]*", texto, re.S):
        citadas |= set(re.findall(r"`(\w+)`", trozo))

    excluidas = set(_ingesta()[nombre]["exclude_columns"])
    assert citadas <= excluidas, (
        f"la ficha de raw.{nombre} dice que no se traen "
        f"{sorted(citadas - excluidas)}, y esas columnas SÍ se ingieren"
    )


# ---------------------------------------------------------------------------
# La contrapartida de DA-2, donde el MCP la va a leer
# ---------------------------------------------------------------------------
#
# DA-2 documenta `raw` solo a nivel de objeto, y lo que lo hacía aceptable era
# remitir al diccionario de campos completo. El puntero estaba en la entrada de
# esquema de `00_global.yaml`, y un agente que pida `describir_tabla('raw.dca')`
# recibe **la ficha**, no el bloque de esquema: no lo veía nunca.
#
# Es la tercera vez en esta feature que algo cierto está escrito donde no llega
# —primero dos veces en comentarios YAML, ahora en el bloque equivocado—, así
# que se comprueba en la ficha, que es lo que se publica por objeto.

PUNTERO = "azure-apps/sigrid_tablas.md"


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r26_cada_ficha_de_raw_remite_al_diccionario_de_campos(nombre: str) -> None:
    ficha = _fichas()[nombre]
    texto = f"{ficha['descripcion']} {ficha.get('motivo_no_consumo', '')}"
    assert PUNTERO in texto, (
        f"raw.{nombre} no documenta columnas (DA-2) y tampoco dice dónde están: "
        f"el puntero a `{PUNTERO}` tiene que ir EN LA FICHA, que es lo que "
        f"recibe quien pide describir el objeto"
    )
    assert nombre in texto, (
        f"el puntero tiene que decir qué buscar allí: el código de tabla "
        f"`{nombre}`, que es como se llama el bloque en ese documento"
    )
