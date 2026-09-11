# tests/test_f080_ingesta.py
"""
F-080 · La ingesta: `con.tex` deja de excluirse y entran tres tablas (R1, R2,
R3, R6).

La pestaña «Texto» de la factura de compra **no** sale de `dcf.tex` —474 de
165.658 facturas informadas, el 0,3 %— sino de `con.tex`, el memo de la
superclase: 108.527 de 165.759 facturas, el 65,5 %. La entrada de `con` en
`config/tables_sigrid.yaml` lo excluía con el comentario «texto libre largo, no
lo usamos en seguimiento», que es exactamente lo que la petición de
Administración desmiente. Mismo patrón que `prvcer.tex` en F-074.

Las tres altas (`auxnap`, `auxban` y `rpa`) son los catálogos que dan nombre al
bloque de pago del efecto y la tabla de remesas a la que apunta `pag.remide`.

**El `incremental_column` de las tres está MEDIDO en `INFORMATION_SCHEMA`**
(2026-09-11, solo lectura), nunca puesto por analogía: `auxnap` y `auxban`
tienen `tiemod` (float) y **`rpa` no tiene ninguna columna de fecha**. F-074
declaró tres `tiemod` inexistentes copiando del vecino, y por eso esto se mide.

Aquí no se abre ninguna conexión: se lee el YAML del árbol.
"""

from __future__ import annotations

import pathlib
from functools import lru_cache

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
FICHERO_RAW = RAIZ / "config" / "diccionario" / "raw.yaml"

#: Las tres altas con su `incremental_column` MEDIDO y su recuento del 2026-09-11.
ALTAS: dict[str, tuple[str | None, int]] = {
    "auxnap": ("tiemod", 3),
    "auxban": ("tiemod", 1_690),
    "rpa": (None, 3_919),
}

#: Lo que `dcf`, `dca` y `ctr` excluyen HOY. R2: F-080 no las toca. El texto de
#: la factura sale de `con`, así que recuperar `dcf.tex` no arreglaría nada y
#: costaría una columna memo más en una tabla de 145 columnas.
EXCLUSIONES_INTACTAS: dict[str, int] = {"dcf": 21, "dca": 23, "ctr": 2}


@lru_cache(maxsize=1)
def _tablas() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


@lru_cache(maxsize=1)
def _fichas_raw() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


# ---------------------------------------------------------------------------
# R1 · `con` se queda con UNA sola exclusión
# ---------------------------------------------------------------------------


def test_f080_r1_con_deja_de_excluir_tex() -> None:
    excluidas = _tablas()["con"]["exclude_columns"]

    assert "tex" not in excluidas, (
        "`con.tex` es la pestaña «Texto» del documento (65,5 % de las facturas "
        "informadas): sin ella, F-080 no tiene nada que publicar (R1)"
    )


def test_f080_r1_a_con_solo_le_queda_fuera_la_imagen() -> None:
    """`ima` es un binario pesado y se queda fuera; no queda ninguna más."""
    assert list(_tablas()["con"]["exclude_columns"]) == ["ima"], (
        "la entrada de `con` tiene que quedarse con UNA sola exclusión (R1)"
    )


def test_f080_r1_con_no_baja_su_page_size_sin_que_lo_decida_el_humano() -> None:
    """Medido en T3: la página más pesada con `tex` a 10.000 filas son 1,71 MB.

    El presupuesto de ventana es una REFERENCIA y no una puerta (R5, DA-5): el
    `page_size` de `con` lo decide el humano con la medición delante, y la
    medición dice que traer `tex` cuesta +26 % de tiempo de lectura sobre esa
    tabla, medio minuto en total. Bajarlo «por si acaso» sería justo la puerta
    automática que la spec retiró.
    """
    assert _tablas()["con"].get("page_size") is None, (
        "el page_size de `con` no se toca en esta feature (R5)"
    )


# ---------------------------------------------------------------------------
# R2 · `dcf`, `dca` y `ctr` no se tocan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("tabla", "cuantas"), sorted(EXCLUSIONES_INTACTAS.items()))
def test_f080_r2_las_otras_tablas_de_compra_no_cambian(tabla: str, cuantas: int) -> None:
    excluidas = _tablas()[tabla]["exclude_columns"]

    assert len(excluidas) == cuantas, (
        f"F-080 no toca las exclusiones de `{tabla}` (R2): el texto que pide "
        "Administración está en `con.tex`, no aquí"
    )
    assert "tex" in excluidas, (
        f"`{tabla}.tex` sigue excluido: recuperarlo no aporta el memo (0,3 % de "
        "las facturas informadas) y cuesta una columna ilimitada más (R2)"
    )


# ---------------------------------------------------------------------------
# R3 · las TRES altas, con su `incremental_column` medido
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(ALTAS))
def test_f080_r3_las_tres_tablas_nuevas_se_ingieren(tabla: str) -> None:
    assert tabla in _tablas(), (
        f"`{tabla}` no se ingiere y F-080 la necesita: sin ella el efecto se "
        "publica con identificadores desnudos en vez de nombres (R3)"
    )


@pytest.mark.parametrize("tabla", sorted(ALTAS))
def test_f080_r3_cada_alta_declara_el_incremental_column_medido(tabla: str) -> None:
    esperado = ALTAS[tabla][0]
    entrada = _tablas()[tabla]

    assert entrada["incremental_column"] == esperado, (
        f"`{tabla}` tiene que declarar `incremental_column: {esperado}`, que es "
        "lo MEDIDO en INFORMATION_SCHEMA el 2026-09-11 (R3). F-074 declaró tres "
        "`tiemod` inexistentes por analogía con la tabla de al lado"
    )
    assert entrada["id_column"] == "ide", f"`{tabla}` pagina por `ide` (R3)"


def test_f080_r3_rpa_no_finge_una_columna_de_fecha_que_no_tiene() -> None:
    """Sus 30 columnas están medidas: `fecrem` es un entero AAAAMMDD, no fecha."""
    assert _tablas()["rpa"]["incremental_column"] is None, (
        "`rpa` no tiene `tiemod` ni ninguna columna de tipo fecha: declarar una "
        "sería inventarla (R3)"
    )


def test_f080_r3_el_censo_de_tablas_ingeridas_sube_a_68() -> None:
    """65 + 3. El contador vive en `tests/test_f074_ingesta_censo.py`."""
    from tests.test_f074_ingesta_censo import TOTAL_TABLAS

    assert len(_tablas()) == 68 == TOTAL_TABLAS, (
        "F-080 añade tres tablas y el censo de F-074 tiene que contarlas (R3)"
    )


# ---------------------------------------------------------------------------
# R6 · las fichas de `raw`
# ---------------------------------------------------------------------------


def test_f080_r6_la_ficha_de_con_dice_que_solo_falta_una_columna() -> None:
    texto = _fichas_raw()["con"]["descripcion"]
    assert "No se traen" in texto, "la ficha de `raw.con` tiene exclusiones (R6)"
    cola = texto.split("No se traen")[1][:200]

    assert " 1 " in cola[:40], (
        "la ficha de `raw.con` decía que faltaban 2 columnas; ahora falta una "
        "sola, `ima`, y el número es lo que el lector usa (R6)"
    )
    assert "`tex`" not in cola, (
        "la ficha no puede seguir diciendo que `tex` no se trae: se trae (R6)"
    )


@pytest.mark.parametrize("tabla", sorted(ALTAS))
def test_f080_r6_cada_tabla_nueva_tiene_su_ficha(tabla: str) -> None:
    assert tabla in _fichas_raw(), (
        f"`raw.{tabla}` se publica en la base y sin ficha el agente que la vea "
        "en el catálogo se inventará su significado (R6)"
    )


@pytest.mark.parametrize("tabla", sorted(ALTAS))
def test_f080_r6_la_ficha_nueva_dice_su_recuento_medido(tabla: str) -> None:
    """Un número medido, no «pocas filas»: es el orden de magnitud del lector."""
    filas = ALTAS[tabla][1]
    texto = _fichas_raw().get(tabla, {}).get("descripcion", "")
    escrito = f"{filas:,}".replace(",", ".")

    assert escrito in texto, (
        f"la ficha de `raw.{tabla}` tiene que decir sus {escrito} filas "
        "medidas el 2026-09-11 (R6)"
    )
