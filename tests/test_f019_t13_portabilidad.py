# tests/test_f019_t13_portabilidad.py
"""
F-019 · T13 · El nombre del mes no puede depender del locale del servidor.

`to_char(fecha, 'TMMonth YYYY')` traduce según `lc_time` del **servidor**: en
Azure (`en_US.utf8`) sale «May 2026» y en local «Mayo 2026». Como el texto
libre de las fases de Sigrid viene en castellano, las vistas que agrupan por
`nombre_mes` partían cada grupo en dos: `cierre.v_pbi_planif_vs_real` daba
26.155 filas en local y 38.407 en Azure con la MISMA tabla base.

Sin red ni BBDD: el SQL se comprueba como texto, igual que
`tests/test_f005_verificacion.py` hace con las consultas de la huella.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ_SQL = Path(__file__).resolve().parents[1] / "etl_sigrid"

MESES_ESPERADOS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

# Dónde se derivaba un nombre de mes, y cuántas veces en cada fichero.
DERIVACIONES_DE_MES = {
    "infrastructure/postgres/sql/cierre/02_build_fact.sql": 1,
    "infrastructure/postgres/sql/cierre/04_views_detalle.sql": 2,
    "infrastructure/postgres/sql/mart/02_build_fact.sql": 2,
    "infrastructure/postgres/sql/mart/04_view_periodificado.sql": 1,
    "infrastructure/postgres/sql/mart/05_views_powerbi.sql": 2,
}

# `(ARRAY[ ... ])[` con los doce nombres dentro.
PATRON_ARRAY_MESES = re.compile(r"\(\s*ARRAY\s*\[(.*?)\]\s*\)\s*\[", re.DOTALL)

# Cualquier máscara de to_char que empiece por TM (TMMonth, TMDay, TMMon...).
PATRON_TO_CHAR_TM = re.compile(r"to_char\s*\([^()]*'\s*TM", re.IGNORECASE)


def _ficheros_sql() -> list[Path]:
    return sorted(RAIZ_SQL.rglob("*.sql"))


# ---------------------------------------------------------------------------
# A · el nombre del mes no puede depender del locale del servidor
# ---------------------------------------------------------------------------

def test_f019_t13_ningun_sql_deriva_el_nombre_del_mes_con_el_locale() -> None:
    """
    Ni un solo `to_char(..., 'TM...')` en el árbol: el prefijo TM traduce con
    `lc_time` del servidor, que en Azure es `en_US.utf8`. Este es el test que
    impide que el patrón vuelva a entrar por otro sitio.
    """
    culpables = [
        f"{ruta.relative_to(RAIZ_SQL)}:{n}"
        for ruta in _ficheros_sql()
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
        if PATRON_TO_CHAR_TM.search(linea)
    ]
    assert culpables == [], (
        "el nombre del mes no puede depender de lc_time del servidor; "
        f"quedan máscaras TM en: {culpables}"
    )


@pytest.mark.parametrize(("relativo", "veces"), sorted(DERIVACIONES_DE_MES.items()))
def test_f019_t13_cada_derivacion_usa_el_array_de_meses(relativo: str, veces: int) -> None:
    """Cada sitio que antes llamaba a `to_char` con TM usa ahora el ARRAY."""
    texto = (RAIZ_SQL / relativo).read_text(encoding="utf-8")
    assert len(PATRON_ARRAY_MESES.findall(texto)) == veces


@pytest.mark.parametrize("relativo", sorted(DERIVACIONES_DE_MES))
def test_f019_t13_el_array_lleva_los_doce_meses_en_castellano(relativo: str) -> None:
    """
    Los doce, en orden y con la ortografía exacta que producía `TMMonth` con
    locale español: sin ella el dato cambia de forma silenciosa y Power BI
    parte los grupos igual que lo hacía Azure.
    """
    texto = (RAIZ_SQL / relativo).read_text(encoding="utf-8")
    listas = PATRON_ARRAY_MESES.findall(texto)
    assert listas, f"{relativo} no tiene ningún ARRAY de meses"

    for lista in listas:
        nombres = [n.strip().strip("'") for n in lista.split(",")]
        assert nombres == MESES_ESPERADOS, (
            f"{relativo}: el array debe llevar los doce meses en orden y en "
            f"castellano; se encontró {nombres}"
        )


def test_f019_t13_el_indice_del_array_es_el_mes_de_la_fecha() -> None:
    """
    El subíndice sale de `EXTRACT(MONTH FROM ...)`: un array indexado por otra
    cosa daría meses cruzados sin que nada falle.
    """
    for relativo in DERIVACIONES_DE_MES:
        texto = (RAIZ_SQL / relativo).read_text(encoding="utf-8")
        for hueco in re.findall(
            r"\)\s*\[(.*?)\]", texto.replace("\n", " ")
        ):
            if "EXTRACT" in hueco.upper() or "MONTH" in hueco.upper():
                assert re.search(
                    r"EXTRACT\s*\(\s*MONTH\s+FROM", hueco, re.IGNORECASE
                ), f"{relativo}: subíndice sospechoso «{hueco}»"


def test_f019_t13_el_mes_suelto_no_arrastra_el_anio() -> None:
    """
    `v_pbi_dim_fecha` expone el mes solo (`nombre_mes_solo`) y el mes con año
    (`nombre_mes_anio`): son columnas distintas y deben seguir siéndolo.
    """
    texto = (
        RAIZ_SQL / "infrastructure/postgres/sql/mart/05_views_powerbi.sql"
    ).read_text(encoding="utf-8")

    solo = _expresion_de_alias(texto, "nombre_mes_solo")
    anio = _expresion_de_alias(texto, "nombre_mes_anio")

    assert "YEAR" not in solo.upper(), "el mes suelto no lleva año"
    assert re.search(r"EXTRACT\s*\(\s*YEAR", anio, re.IGNORECASE), (
        "el mes con año sí lo lleva"
    )


def _expresion_de_alias(texto: str, alias: str) -> str:
    """Trozo de SELECT que termina en `AS <alias>`, para inspeccionarlo."""
    plano = texto.replace("\n", " ")
    fin = plano.index(f"AS {alias}")
    inicio = max(plano.rfind(",", 0, fin - 200 if fin > 200 else 0), 0)
    return plano[inicio:fin]
