# tests/test_f149_mcp_sin_reglas_no_publicadas.py
"""
F-149 · Lo que llega al MCP no nombra reglas que el MCP no puede leer.

Tras F-147, `R-SIGRID-CON` es `fuera_mcp`: no llega a `_meta.diccionario_reglas`.
Pero el bloque `identidad_sigrid` de `_meta.diccionario_contexto` y dos columnas
de `compras` la seguían citando, y la IA leía una referencia a una regla que no
podía consultar. Este fichero cierra la clase, no el caso: ningún texto que llega
al MCP puede citar un código de regla que no se publica o que no existe.

Qué es «lo que llega al MCP» se decide con el MISMO código que publica, no con
una copia:

* las filas de `filas_diccionario`, `filas_reglas` y `filas_contexto`, sobre el
  diccionario cargado y con `derivar_avisos` aplicado, como en
  `PublicarDiccionarioStep.run` (los `avisos` de una ficha también son texto que
  sirve `describir_tabla`);
* de las fichas, solo las de los esquemas que algún perfil del MCP puede leer:
  todos menos los que se vetan incluso al login total
  (`DEFAULT_TOTAL_VETOED_SCHEMAS`, hoy `raw`: «total no incluye raw, siempre
  fuera», F-136). Total ⊃ estándar ⊃ restringido, así que lo que el total no ve
  no lo ve nadie. Por eso la ficha de `raw`, que sí cita `R-SIGRID-CON`, queda
  fuera a propósito: es guía del ETL y el MCP no la sirve.

Una regla «se publica» si `Regla.publicable` (todas menos las `fuera_mcp`, D4 de
F-147). Ningún test abre red ni BBDD.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from functools import cache
from pathlib import Path

import yaml

from config.settings import DEFAULT_TOTAL_VETOED_SCHEMAS
from etl_sigrid.domain.diccionario import Diccionario, derivar_avisos
from etl_sigrid.infrastructure.postgres.diccionario_sql import (
    filas_contexto,
    filas_diccionario,
    filas_reglas,
)
from tests.test_f006_formato import _columna, _dicc, _ficha, _regla

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
GLOBAL = DIR_DICCIONARIO / "00_global.yaml"

#: Un código de regla tal como se escribe en el diccionario: `R-` y palabras en
#: mayúsculas separadas por guiones (`R-SIGRID-CON`, `R-PARTIDA-CODIGO-NO-UNICO`).
#: La primera letra tras `R-` es una letra para no confundirlo con un `R-1`.
CODIGO_DE_REGLA = re.compile(r"\bR-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*")


def esquemas_fuera_del_mcp() -> frozenset[str]:
    """Los esquemas que ningún perfil del MCP lee: los vetados al login total."""
    return frozenset(
        e.strip() for e in DEFAULT_TOTAL_VETOED_SCHEMAS.split(",") if e.strip()
    )


def textos_al_mcp(dicc: Diccionario) -> list[tuple[str, str]]:
    """(sitio, texto) de cada fila que la publicación deja al alcance del MCP.

    La fila entera se serializa: así entra cualquier campo de texto, también los
    que se añadan mañana a la ficha, a la regla o al bloque, sin tocar esto.
    """
    fuera = esquemas_fuera_del_mcp()
    textos: list[tuple[str, str]] = []
    for fila in filas_diccionario(dicc):
        if fila[0] not in fuera:
            textos.append((f"ficha {fila[0]}.{fila[1]}", _texto(fila)))
    for fila in filas_reglas(dicc):
        textos.append((f"regla {fila[0]}", _texto(fila)))
    for fila in filas_contexto(dicc):
        textos.append((f"contexto {fila[0]}.{fila[1]}", _texto(fila)))
    return textos


def _texto(fila: tuple) -> str:
    return json.dumps(fila, ensure_ascii=False, default=str)


def citas_no_publicadas(dicc: Diccionario) -> list[tuple[str, str]]:
    """(sitio, código) de cada cita a una regla que no está en el MCP."""
    publicadas = {r.codigo for r in dicc.reglas if r.publicable}
    return sorted(
        {
            (sitio, codigo)
            for sitio, texto in textos_al_mcp(dicc)
            for codigo in CODIGO_DE_REGLA.findall(texto)
            if codigo not in publicadas
        }
    )


@cache
def _publicado() -> Diccionario:
    """El diccionario real tal como lo publica `PublicarDiccionarioStep`."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    return derivar_avisos(cargar_diccionario(DIR_DICCIONARIO)[0])


# ---------------------------------------------------------------------------
# El diccionario real
# ---------------------------------------------------------------------------


def test_f149_nada_de_lo_que_llega_al_mcp_cita_una_regla_que_no_se_publica() -> None:
    """La aceptación entera, sobre el diccionario del repositorio."""
    citas = citas_no_publicadas(_publicado())

    assert citas == [], (
        "Texto servido por el MCP que cita una regla que el MCP no puede leer "
        f"(`fuera_mcp` o inexistente): {citas}"
    )


def test_f149_r_sigrid_con_no_aparece_en_nada_de_lo_que_llega_al_mcp() -> None:
    """El caso que abrió la feature, nombrado: tres textos lo citaban."""
    sitios = [s for s, t in textos_al_mcp(_publicado()) if "R-SIGRID-CON" in t]

    assert sitios == []


def test_f149_el_barrido_mira_lo_que_tiene_que_mirar() -> None:
    """Guarda contra un barrido vacío: si no viera fichas, reglas o bloques,
    el test de arriba saldría verde sin mirar nada."""
    sitios = [s for s, _ in textos_al_mcp(_publicado())]

    assert any(s == "ficha compras.facturas" for s in sitios)
    assert any(s == "contexto convenciones.identidad_sigrid" for s in sitios)
    assert any(s.startswith("regla ") for s in sitios)
    assert not any(s.startswith("ficha raw.") for s in sitios)
    assert esquemas_fuera_del_mcp() == {"raw"}


def test_f149_la_regla_sigue_en_el_yaml_como_guia_del_etl() -> None:
    """FUERA del alcance: la regla no se borra, solo deja de citarse."""
    regla = next(r for r in _publicado().reglas if r.codigo == "R-SIGRID-CON")

    assert regla.entrega == "fuera_mcp"


def test_f149_identidad_sigrid_dice_que_es_guia_interna_del_etl() -> None:
    texto = " ".join(yaml.safe_load(GLOBAL.read_text(encoding="utf-8"))
                     ["convenciones"]["identidad_sigrid"].split())

    assert "guia interna del ETL" in texto
    assert "no se consulta desde el MCP" in texto


def test_f149_version_61() -> None:
    assert int(yaml.safe_load(GLOBAL.read_text(encoding="utf-8"))["version"]) >= 61


# ---------------------------------------------------------------------------
# El detector, sobre diccionarios sintéticos: caza lo que tiene que cazar
# ---------------------------------------------------------------------------

_FUERA = replace(_regla("R-GUIA-ETL"), entrega="fuera_mcp")


def _con(*fichas, reglas=(), contexto=None) -> Diccionario:
    return _dicc(
        fichas=list(fichas) or [_ficha()],
        reglas=[_regla("R-FRESCURA"), _FUERA, *reglas],
        global_raw=contexto or {},
    )


def test_f149_caza_una_fuera_mcp_citada_en_una_columna() -> None:
    ficha = _ficha(
        esquema="compras",
        columnas=(_columna(significado="Codigo de obra (`R-GUIA-ETL`)."),),
    )

    assert citas_no_publicadas(_con(ficha)) == [
        ("ficha compras.fact_seguimiento_mensual", "R-GUIA-ETL")
    ]


def test_f149_caza_una_fuera_mcp_citada_en_un_bloque_de_contexto() -> None:
    contexto = {"convenciones": {"identidad": "Se lee como dice `R-GUIA-ETL`."}}

    assert citas_no_publicadas(_con(contexto=contexto)) == [
        ("contexto convenciones.identidad", "R-GUIA-ETL")
    ]


def test_f149_caza_una_fuera_mcp_citada_en_una_regla_publicada() -> None:
    otra = _regla("R-OTRA", motivo="Lo explica `R-GUIA-ETL`.")

    assert citas_no_publicadas(_con(reglas=[otra])) == [("regla R-OTRA", "R-GUIA-ETL")]


def test_f149_caza_un_codigo_que_no_existe() -> None:
    ficha = _ficha(descripcion="Ver la regla `R-NO-EXISTE-NINGUNA`.")

    assert citas_no_publicadas(_con(ficha)) == [
        ("ficha mart.fact_seguimiento_mensual", "R-NO-EXISTE-NINGUNA")
    ]


def test_f149_caza_un_aviso_derivado_de_una_fuera_mcp() -> None:
    """Una `fuera_mcp` con ámbito en un esquema servido pondría su código en los
    `avisos` de cada ficha de ese esquema, que también sirve `describir_tabla`."""
    dicc = derivar_avisos(
        _dicc(fichas=[_ficha()], reglas=[replace(_FUERA, ambito=("mart",))])
    )

    assert citas_no_publicadas(dicc) == [
        ("ficha mart.fact_seguimiento_mensual", "R-GUIA-ETL")
    ]


def test_f149_no_mira_las_fichas_de_raw_ni_las_reglas_que_no_se_publican() -> None:
    """`raw` no lo sirve ningún perfil, y la `fuera_mcp` no viaja: citarse a
    sí misma, o citarla desde `raw`, es guía del ETL y está bien."""
    ficha_raw = _ficha(esquema="raw", descripcion="Lease con `R-GUIA-ETL`.")
    propia = replace(_FUERA, regla="Como dice `R-GUIA-ETL`, la clave es `ide`.")

    assert citas_no_publicadas(
        _dicc(fichas=[ficha_raw], reglas=[_regla("R-FRESCURA"), propia])
    ) == []


def test_f149_una_cita_a_una_regla_publicada_no_es_un_hallazgo() -> None:
    ficha = _ficha(descripcion="No se suma entre meses (`R-FRESCURA`).")

    assert citas_no_publicadas(_con(ficha)) == []
