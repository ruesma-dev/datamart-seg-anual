# tests/test_f156_diccionario.py
"""F-156 · Diccionario y documentación de postventa (R22-R23, R31, R33-R35), sin red ni BBDD.

Las fichas de `postventa` y `postventa_restringida`, sus `valores` contra el
dominio, las reglas de `00_global.yaml` (versión, esquemas, `R-FRESCURA`,
`R-PERFILES`, `R-POSTVENTA-RESTRINGIDA`), las preguntas de aceptación y la
documentación de arquitectura.
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
DIR_PV = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "postventa"

VERSION_ANTERIOR = 70


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _fichas(esquema: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"]


def _global() -> dict:
    return _yaml("00_global.yaml")


def _regla(codigo: str) -> dict:
    return next(r for r in _global()["reglas"] if r["codigo"] == codigo)


def _texto(ficha: dict) -> str:
    return re.sub(r"\s+", " ", str(ficha))


def _objetos_del_sql() -> set[str]:
    """`esquema.objeto` de cada CREATE del SQL de postventa."""
    objetos: set[str] = set()
    for ruta in DIR_PV.glob("*.sql"):
        sql = "\n".join(re.sub(r"--.*$", "", l) for l in ruta.read_text(encoding="utf-8").splitlines())
        objetos |= set(re.findall(
            r"CREATE (?:OR REPLACE )?(?:TABLE|VIEW|FUNCTION) (postventa(?:_restringida)?\.\w+)", sql))
    return objetos


# ===========================================================================
# R33 · una ficha por objeto, con su paso y sus trampas
# ===========================================================================


def test_f156_r33_una_ficha_por_objeto_del_sql() -> None:
    fichados = {f"postventa.{n}" for n in _fichas("postventa")}
    fichados |= {f"postventa_restringida.{n}" for n in _fichas("postventa_restringida")}
    assert fichados == _objetos_del_sql()


@pytest.mark.parametrize("esquema", ["postventa", "postventa_restringida"])
def test_f156_r33_paso_y_refresco(esquema: str) -> None:
    for nombre, ficha in _fichas(esquema).items():
        assert ficha["paso_etl"] == "build_postventa", nombre
        assert ficha["refresco"] == "nocturno", nombre


def _columnas_publicadas(objeto: str) -> list[str]:
    """Las columnas del SELECT final del CREATE de `objeto` (los ` AS alias`)."""
    for ruta in sorted(DIR_PV.glob("*.sql")):
        sql = re.sub(r"\s+", " ", "\n".join(
            re.sub(r"--.*$", "", l) for l in ruta.read_text(encoding="utf-8").splitlines()))
        m = re.search(rf"CREATE (?:TABLE|VIEW) {re.escape(objeto)} AS (.*?);", sql)
        if m:
            cuerpo = m.group(1)
            final = cuerpo[cuerpo.rindex("SELECT "):]
            final = final[: final.index(" FROM ")]
            return re.findall(r" AS (\w+)", final)
    raise AssertionError(f"sin CREATE de {objeto}")


@pytest.mark.parametrize("objeto", sorted(o for o in _objetos_del_sql() if ".fn_" not in o))
def test_f156_r33_las_columnas_de_la_ficha_son_las_del_sql(objeto: str) -> None:
    esquema, nombre = objeto.split(".")
    ficha = _fichas(esquema)[nombre]
    assert list(ficha["columnas"]) == _columnas_publicadas(objeto)
    for columna, datos in ficha["columnas"].items():
        assert len(datos["significado"].strip()) >= 15, columna


def test_f156_r33_las_trampas_medidas_estan_en_las_fichas() -> None:
    incidencias = _texto(_fichas("postventa")["incidencias"])
    for cifra in ("1.502", "15.229", "Escrita"):
        assert cifra in incidencias, cifra
    assert "1.499" in _texto(_fichas("postventa")["incidencia_intervinientes"])
    assert "a 0" in _texto(_fichas("postventa")["tareas"]), "coste y venta de tar a 0"
    unidades = _texto(_fichas("postventa")["unidades"])
    assert "estructura" in unidades and "unidad de venta" in unidades
    assert "usuario_nombre" in _texto(_fichas("postventa")["incidencia_procesos"])
    coste = _texto(_fichas("postventa")["v_coste_obra"])
    assert "personal" in coste and "0004" in coste and "SIN_OBRA" in coste


# ===========================================================================
# Valores contra el dominio
# ===========================================================================


def test_f156_valores_contra_el_dominio() -> None:
    f = _fichas("postventa")
    assert f["v_estado_incidencias"]["columnas"]["origen_fecha"]["valores"] == list(pv.ORIGENES_FECHA)
    assert f["documento_adjuntos"]["columnas"]["familia"]["valores"] == list(pv.FAMILIAS_ADJUNTOS)
    assert f["partida_obra_origen"]["columnas"]["liga"]["valores"] == list(pv.LIGAS_COSTE)
    assert f["v_coste_obra"]["columnas"]["liga"]["valores"] == list(pv.LIGAS_COSTE)
    assert f["incidencia_procesos"]["columnas"]["origen"]["valores"] == ["RAC", pv.ORIGENES_FECHA[1]]
    assert sorted(f["documento_adjuntos"]["columnas"]["tipo_documento_codigo"]["valores"]) == \
        sorted(pv.TIPOS_POSTVENTA)
    assert f["incidencias"]["columnas"]["estado_id"]["valores"] == [1, 3, 5, 7, 9]


# ===========================================================================
# R22 · adjuntos: el origen de cada familia y quién abre qué
# ===========================================================================


def test_f156_r22_la_ficha_de_adjuntos_declara_el_origen_de_cada_familia() -> None:
    texto = _texto(_fichas("postventa")["documento_adjuntos"])
    origen = {
        "INCIDENCIA": "postventa.incidencias.incidencia_id",
        "UNIDAD": "postventa.unidades.unidad_id",
        "TAREA": "postventa.tareas.tarea_id",
        "REPARACION": "postventa_restringida.contactos_incidencia.incidencia_id",
    }
    assert set(origen) == set(pv.FAMILIAS_ADJUNTOS)
    for familia, tabla in origen.items():
        assert f"{familia} -> `{tabla}`" in texto, familia
    assert "DNI" in texto and "perfil postventa" in texto and "total" in texto


# ===========================================================================
# R23 · la autorización en las fichas restringidas
# ===========================================================================


def test_f156_r23_las_fichas_restringidas_citan_la_autorizacion() -> None:
    fichas = _fichas("postventa_restringida")
    assert set(fichas) == {"contactos_incidencia", "contactos_unidad", "textos"}
    for nombre, ficha in fichas.items():
        assert ficha["descripcion"].startswith("**ACCESO RESTRINGIDO"), nombre
        assert "d1 ok" in ficha["descripcion"] and "2026-11-03" in ficha["descripcion"], nombre
    cabecera = (DIR_DICC / "postventa_restringida.yaml").read_text(encoding="utf-8")
    assert "«d1 ok»" in cabecera and "chat del 2026-11-03" in cabecera


def test_f156_r11_el_general_no_documenta_columnas_personales() -> None:
    for nombre, ficha in _fichas("postventa").items():
        for columna in ficha.get("columnas") or {}:
            for palabra in pv.PALABRAS_PROHIBIDAS_GENERAL:
                assert palabra not in columna, f"{nombre}.{columna}"


# ===========================================================================
# R34 · 00_global.yaml
# ===========================================================================


def test_f156_r34_la_version_sube_en_uno() -> None:
    # F-158 subió a la v72: lo que fija F-156 es su v71 y su nota, no que sea la
    # última (el patrón de F-153 y F-155).
    assert _global()["version"] >= VERSION_ANTERIOR + 1
    texto = (RAIZ / "config" / "diccionario" / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 71 (F-156, 2026-11-" in texto.split("\nversion:", 1)[0]


def test_f156_r34_los_dos_esquemas() -> None:
    esquemas = _global()["esquemas"]
    for nombre in ("postventa", "postventa_restringida"):
        assert esquemas[nombre]["pasos_etl"] == ["build_postventa"], nombre
        assert esquemas[nombre]["refresco"] == "nocturno"
        assert len(esquemas[nombre]["para_que_sirve"].strip()) <= 350
    assert "perfil postventa" in esquemas["postventa_restringida"]["para_que_sirve"]


def test_f156_r31_esquemas_del_datamart() -> None:
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    assert {"postventa", "postventa_restringida"} <= set(ESQUEMAS_DEL_DATAMART)
    assert list(ESQUEMAS_DEL_DATAMART) == sorted(ESQUEMAS_DEL_DATAMART)


def test_f156_r34_frescura_alcanza_los_dos_esquemas() -> None:
    regla = _regla("R-FRESCURA")
    assert {"postventa", "postventa_restringida"} <= set(regla["ambito"])
    assert "build_postventa" in regla["regla"] and "build_postventa" in regla["motivo"]
    assert "postventa" in regla["resumen"]


def test_f156_r34_perfiles_con_el_cuarto() -> None:
    regla = _regla("R-PERFILES")
    assert "postventa_restringida" in regla["ambito"]
    assert "Cuatro perfiles" in regla["regla"] and "POSTVENTA" in regla["regla"]
    assert "F-156" in regla["motivo"]


def test_f156_r34_regla_postventa_restringida() -> None:
    regla = _regla("R-POSTVENTA-RESTRINGIDA")
    assert regla["severidad"] == "bloqueante"
    assert regla.get("entrega", "resumen") == "resumen"
    assert set(regla["ambito"]) == {"postventa", "postventa_restringida"}
    for cosa in ("postventa", "perfil postventa", "total", "nunca se suman"):
        assert cosa in regla["regla"], cosa


def test_f156_r34_ejemplos_preguntas() -> None:
    f = _fichas("postventa")
    assert any("oficio" in p for p in f["incidencias"]["ejemplos_preguntas"][:2])
    assert any("tiempo medio" in p for p in f["v_estado_incidencias"]["ejemplos_preguntas"][:2])
    assert any("garantia" in p for p in f["unidades"]["ejemplos_preguntas"][:2])
    assert any("coste" in p for p in f["v_coste_obra"]["ejemplos_preguntas"][:2])


# ===========================================================================
# R35 · documentación
# ===========================================================================


def test_f156_r35_architecture_describe_postventa() -> None:
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for cosa in ("postventa_restringida", "perfil postventa", "build_postventa", "F-156",
                 "pliego_mcp_bbdd.md"):
        assert cosa in texto, cosa


def test_f156_r35_claude_md_mapa() -> None:
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    assert "postventa/" in texto and "postventa_restringida" in texto and "F-156" in texto
