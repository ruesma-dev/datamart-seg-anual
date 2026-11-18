# tests/test_f164_diccionario.py
"""F-164 · Diccionario, `ARCHITECTURE.md` y el documento del ecosistema (R12, R13).

Sin red ni BBDD. Quien lee la ficha es un agente que no puede preguntar: tiene
que saber que REPARACION ya no es solo PV002 sino «parte firmado o posible
parte» (lista abierta + señales), que los partes de 2021-2023 cuelgan sin clase,
que `familia_documento` guarda la familia por documento y que los adjuntos de
unidad (707) movidos a REPARACION no tienen fila de origen en la restringida.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain import postventa as pv

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICC = RAIZ / "config" / "diccionario"
RUTA_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "postventa" / "06_adjuntos.sql"

VERSION_ANTERIOR = 78


def _azure_apps() -> Path | None:
    """`azure-apps/` es hermano del repositorio; desde un worktree, de un ancestro."""
    for padre in RAIZ.parents:
        candidato = padre / "azure-apps" / "datamart_seg_anual.md"
        if candidato.exists():
            return candidato
    return None


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"][objeto]


def _plano(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto))


def _regla(codigo: str) -> dict:
    return next(r for r in _yaml("00_global.yaml")["reglas"] if r["codigo"] == codigo)


# --- R12 · la ficha de postventa.documento_adjuntos -----------------------------


def test_f164_r12_la_ficha_dice_el_criterio() -> None:
    d = _plano(_ficha("postventa", "documento_adjuntos")["descripcion"])
    for clave in ("F-164", "PV001", "PV006", "PV004", "FIRMA", "codigo de la incidencia",
                  "familia_documento", "2021-2023", "sin clase"):
        assert clave in d, clave
    assert "parte firmado o posible parte" in d


def test_f164_r12_la_ficha_dice_lo_que_no_ve() -> None:
    d = _plano(_ficha("postventa", "documento_adjuntos")["descripcion"])
    assert "NO VE" in d
    assert "contenido" in d and "nombre generico" in d


def test_f164_r12_la_ficha_dice_los_huerfanos_de_707() -> None:
    d = _plano(_ficha("postventa", "documento_adjuntos")["descripcion"])
    assert "707" in d and "huerfan" in d


def test_f164_r12_columnas_familia_y_familia_documento() -> None:
    columnas = _ficha("postventa", "documento_adjuntos")["columnas"]
    assert list(columnas)[:3] == ["adjunto_id", "familia", "familia_documento"]
    assert columnas["familia"]["valores"] == list(pv.FAMILIAS_ADJUNTOS)
    assert columnas["familia_documento"]["valores"] == list(pv.FAMILIAS_ADJUNTOS)
    assert "F-164" in _plano(columnas["familia"]["significado"])
    assert "F-156" in _plano(columnas["familia_documento"]["significado"])


def test_f164_r12_la_ficha_documenta_todas_las_columnas_del_sql() -> None:
    sql = re.sub(r"\s+", " ", "\n".join(
        re.sub(r"--.*$", "", linea)
        for linea in RUTA_SQL.read_text(encoding="utf-8").splitlines()))
    create = sql[sql.index("CREATE TABLE postventa.documento_adjuntos AS"):]
    final = create[create.rindex("SELECT "):]
    final = final[: final.index(" FROM ")]
    publicadas = re.findall(r" AS (\w+)", final)
    assert list(_ficha("postventa", "documento_adjuntos")["columnas"]) == publicadas


def test_f164_r12_la_regla_restringida_alcanza_a_los_partes_reconocidos() -> None:
    regla = _plano(_regla("R-POSTVENTA-RESTRINGIDA")["regla"])
    assert "F-164" in regla
    assert "parte firmado o posible parte" in regla
    assert "no solo PV002" in regla


def test_f164_r12_contactos_incidencia_y_los_huerfanos_de_707() -> None:
    d = _plano(_ficha("postventa_restringida", "contactos_incidencia")["descripcion"])
    assert "F-164" in d and "707" in d and "huerfan" in d


def test_f164_r12_auxgra_pv002_ya_no_es_la_unica_marca() -> None:
    d = _plano(_ficha("raw", "auxgra")["descripcion"])
    assert "F-164" in d
    assert "no es la unica marca" in d


def test_f164_r12_la_version_sube_en_uno() -> None:
    glob = _yaml("00_global.yaml")
    assert glob["version"] >= VERSION_ANTERIOR + 1
    texto = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert f"# version {VERSION_ANTERIOR + 1} (F-164, " in texto


# --- R13 · ARCHITECTURE.md y azure-apps -----------------------------------------


def test_f164_r13_architecture_describe_la_regla() -> None:
    texto = _plano((RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8"))
    inicio = texto.index("**`postventa` (F-156, 2026-11-04)")
    parrafo = texto[inicio: texto.index("**`personal` (F-057", inicio)]
    for clave in ("F-164", "familia_documento", "PV001", "PV006", "PV004", "707",
                  "mcp-bbdd", "no cambia"):
        assert clave in parrafo, clave


def test_f164_r13_azure_apps_describe_la_regla() -> None:
    ruta = _azure_apps()
    if ruta is None:
        pytest.skip("azure-apps no está al lado del repositorio")
    texto = _plano(ruta.read_text(encoding="utf-8"))
    inicio = texto.index("### La postventa:")
    seccion = texto[inicio: texto.index("### ", inicio + 5)]
    # Desplegada el 2026-11-17 (T9-T10): el documento ya no dice «SIN DESPLEGAR».
    for clave in ("F-164", "familia_documento", "PV001", "PV006", "PV004", "707",
                  "desplegada el 2026-11-17"):
        assert clave in seccion, clave
    assert re.search(r"hu[eé]rfan", seccion), "los huérfanos de 707"
    assert "`mcp-bbdd` no cambia" in seccion
