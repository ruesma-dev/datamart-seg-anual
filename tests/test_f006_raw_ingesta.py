# tests/test_f006_raw_ingesta.py
"""
Lo que las fichas de `raw` dicen de la INGESTA se contrasta con la ingesta (7ª pasada).

La primera versión de este fichero contrastaba contra `config/tables_sigrid.yaml`,
y ese es **justo el documento que miente**: declara `incremental_column: tiemod`
en tablas que no tienen esa columna, y ninguna de las 31 se carga como decía la
ficha. Contrastar contra él dio 31 fichas en verde afirmando algo falso.

Lo que hace de verdad `IngestRawStep` (`ingest_raw_step.py`, paso 3 y 4):

    if self._full_refresh:
        pg.truncate_table("raw", spec.target_table)
        last_id_already = 0
    else:
        last_id_already = pg.get_max_id("raw", spec.target_table, spec.id_column)
    ...
    tiemod_col = spec.incremental_column if spec.incremental_column in col_names else None

Es decir, para las 31 y siempre igual:

* **Append por `MAX(ide)`**: se piden a Sigrid solo las filas con `ide` mayor que
  el máximo ya guardado. Una fila **modificada** en Sigrid no se refresca nunca,
  y una **borrada** en Sigrid se queda aquí para siempre.
* `incremental_column` **no gobierna la carga**. Se usa solo para volcar
  `_source_tiemod`, y solo si la columna existe entre las que se piden.
* El `TRUNCATE` únicamente ocurre con `full_refresh=True`, que `run-all` **no
  pasa**: hay que lanzarlo a mano.

La lección, que es la misma que ya nos costó dos rechazos: **derivar de la
fuente equivocada es tan malo como no derivar**. La fuente de «cómo se carga» es
el código que carga.
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

#: Cómo tiene que decirlo la ficha. Frase fija para poder comprobarla.
FRASE_APPEND = "append por `MAX(ide)`"

#: Y lo que ya no puede decir: las dos formulaciones falsas de la tanda anterior.
FRASES_PROHIBIDAS = ("incremental por `tiemod`", "recarga entera", "recarga entero")


@lru_cache(maxsize=1)
def _ingesta() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


@lru_cache(maxsize=1)
def _fichas() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


def _nombres() -> list[str]:
    return sorted(_fichas())


# ---------------------------------------------------------------------------
# Primero: que el código siga haciendo lo que las fichas dicen que hace
# ---------------------------------------------------------------------------


def test_f006_r13_la_ingesta_sigue_siendo_append_por_max_ide() -> None:
    """El ancla. Si el paso cambia de estrategia, las 31 fichas quedan obsoletas.

    Sin este test, las fichas podrían seguir describiendo un `append` mucho
    después de que la ingesta pasara a refrescar por `tiemod`, y nadie se
    enteraría: es la misma trampa que tener 31 fichas contrastadas contra un
    YAML de configuración que no gobierna la carga.
    """
    codigo = PASO_INGESTA.read_text(encoding="utf-8")

    assert re.search(
        r"last_id_already\s*=\s*pg\.get_max_id\(\s*[\"']raw[\"']", codigo
    ), "la ingesta ya no arranca el cursor en el MAX(ide) guardado"
    assert re.search(r"start_id\s*=\s*last_id_already", codigo), (
        "el cursor ya no se pasa como `start_id`"
    )
    assert re.search(r"if\s+self\._full_refresh:", codigo), (
        "ya no hay rama de `full_refresh`"
    )
    # `incremental_column` NO decide la carga: solo alimenta `_source_tiemod`.
    assert re.search(r"tiemod_col\s*=\s*spec\.incremental_column", codigo)
    assert re.search(r"tiemod_column\s*=\s*tiemod_col", codigo)


def test_f006_r13_run_all_no_pide_recarga_completa() -> None:
    """El `TRUNCATE` no ocurre de noche, y por eso las fichas no pueden decir
    que la tabla se recarga entera."""
    codigo = PASO_INGESTA.read_text(encoding="utf-8")
    assert re.search(r"full_refresh:\s*bool\s*=\s*False", codigo), (
        "si el valor por defecto pasara a True, `run-all` truncaría cada noche "
        "y las fichas dirían lo contrario de lo que ocurre"
    )


# ---------------------------------------------------------------------------
# Y después: que las fichas lo cuenten, y lo cuenten igual
# ---------------------------------------------------------------------------


def test_f006_r26_hay_una_ficha_por_tabla_ingerida() -> None:
    """Ni de más ni de menos: `raw` es exactamente lo que se ingiere."""
    assert set(_fichas()) == set(_ingesta())


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r13_la_ficha_dice_como_se_carga_la_tabla(nombre: str) -> None:
    """Las 31 se cargan igual, así que las 31 lo dicen igual."""
    texto = _fichas()[nombre]["descripcion"]

    assert FRASE_APPEND in texto, (
        f"la ficha de raw.{nombre} tiene que decir que la carga es «{FRASE_APPEND}»: "
        f"es como se cargan las 31, y significa que una fila modificada en Sigrid "
        f"no se refresca nunca"
    )
    dichas = [f for f in FRASES_PROHIBIDAS if f in texto]
    assert dichas == [], (
        f"la ficha de raw.{nombre} dice {dichas}, y eso no ocurre: lo dedujimos de "
        f"`config/tables_sigrid.yaml`, que declara una columna de corte que la "
        f"ingesta no usa para cargar (y que en muchas tablas ni existe)"
    )


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r13_la_ficha_avisa_de_que_lo_modificado_no_vuelve(nombre: str) -> None:
    """La consecuencia importa más que el mecanismo.

    «Append por MAX(ide)» es exacto y no le dice nada a quien no lo interprete.
    Lo que hay que saber al usar el dato es que **lo modificado en Sigrid no se
    refresca**, así que la ficha lo dice con todas las letras.
    """
    texto = _fichas()[nombre]["descripcion"].lower()
    assert "no se refresca" in texto or "no vuelve a leerse" in texto, (
        f"la ficha de raw.{nombre} explica el mecanismo pero no su consecuencia: "
        f"una fila cambiada en Sigrid se queda con el valor de cuando entró"
    )


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
