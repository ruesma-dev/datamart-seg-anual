# tests/test_f085_diccionario.py
"""
F-085 · Las fichas del diccionario y los documentos (R22-R28).

Quien consulta el datamart es un agente que no puede preguntar: lo que la ficha
no diga —la historia es NETA, el estado actual es el último paso, el nombre
falta cuando el login no tiene ficha, el DNI está en `personal`, la aprobación
de una factura no está en `confir`— lo va a suponer. Aquí se fija que lo dice,
con las cifras medidas el 2026-10-07 (`progress/spec_F-085.md`).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

COLUMNAS_PROCESOS = [
    "paso_id", "documento_id", "tipo_documento_codigo", "familia",
    "codigo_documento", "proceso_id", "proceso",
    "estado_origen_id", "estado_origen_codigo", "estado_origen",
    "estado_destino_id", "estado_destino_codigo", "estado_destino",
    "usuario", "nombre_usuario", "fecha", "hora", "momento", "asiento_id",
    "orden", "es_ultimo", "encaja_con_anterior", "dias_desde_anterior",
]
COLUMNAS_USUARIOS = [
    "usuario_id", "login", "nombre", "desactivado",
    "codigo_empleado", "empleado_id", "dni",
]


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    objetos = _yaml(f"{esquema}.yaml")["objetos"]
    assert objeto in objetos, f"falta la ficha de {esquema}.{objeto}"
    return objetos[objeto]


def _texto(ficha: dict) -> str:
    return yaml.safe_dump(ficha, allow_unicode=True, width=10_000)


# ===========================================================================
# R22-R23 · `compras.documento_procesos`
# ===========================================================================


def test_f085_r22_ficha_de_documento_procesos_con_todas_sus_columnas() -> None:
    ficha = _ficha("compras", "documento_procesos")
    assert ficha["tipo"] == "tabla"
    assert ficha["paso_etl"] == "build_compras"
    assert ficha["clave_negocio"] == ["paso_id"]
    assert list(ficha["columnas"]) == COLUMNAS_PROCESOS
    for nombre, columna in ficha["columnas"].items():
        assert columna.get("significado"), f"`{nombre}` sin significado"


@pytest.mark.parametrize(
    "dato",
    [
        # cobertura por familia y por qué faltan los demás
        "99,94", "97,1", "97,0", "72,2", "estado inicial",
        # historia NETA, la bruta en dbo.log
        "NETA", "Deshacer proceso", "dbo.log", "F-105",
        # estado actual = destino del último paso
        "99,96", "es_ultimo",
        # quién: login, nombre y su cobertura; el DNI en personal
        "LOGIN", "nombre_usuario", "93,0", "personal.usuarios_sigrid",
        # R23 · la factura no se aprueba en confir
        "DOCVAL", "3.474", "97,4", "compras.comparativo_firmas",
    ],
)
def test_f085_r22_la_ficha_dice(dato: str) -> None:
    descripcion = _ficha("compras", "documento_procesos")["descripcion"]
    assert dato in descripcion, f"la ficha de documento_procesos no dice «{dato}»"


def test_f085_r22_relaciones_a_las_tres_familias_de_compras() -> None:
    destinos = {r["a"] for r in _ficha("compras", "documento_procesos")["relaciones"]}
    assert destinos == {
        "compras.facturas.factura_id",
        "compras.contratos.contrato_id",
        "compras.comparativos.comparativo_id",
    }


def test_f085_r22_nombre_usuario_explica_su_nulo() -> None:
    columna = _ficha("compras", "documento_procesos")["columnas"]["nombre_usuario"]
    assert "ficha" in columna["nulo_significa"]


# ===========================================================================
# R24 · `personal.usuarios_sigrid`
# ===========================================================================


def test_f085_r24_ficha_de_usuarios_sigrid_con_todas_sus_columnas() -> None:
    ficha = _ficha("personal", "usuarios_sigrid")
    assert ficha["paso_etl"] == "build_personal"
    assert ficha["clave_negocio"] == ["usuario_id"]
    assert ficha["claves_alternativas"] == [["login"]]
    assert list(ficha["columnas"]) == COLUMNAS_USUARIOS


@pytest.mark.parametrize(
    "dato",
    [
        "DATOS PERSONALES", "2026-09-18", "2026-10-07", "DNI",
        "credencial", "correo",
        "211", "210", "189", "21 con varias", "empresa 1", "204",
        "personal.recursos", "mayusculas",
    ],
)
def test_f085_r24_la_ficha_dice(dato: str) -> None:
    descripcion = _ficha("personal", "usuarios_sigrid")["descripcion"]
    assert dato in descripcion, f"la ficha de usuarios_sigrid no dice «{dato}»"


def test_f085_r24_relacion_con_recursos_por_empleado() -> None:
    relaciones = _ficha("personal", "usuarios_sigrid")["relaciones"]
    assert [(r["de"], r["a"]) for r in relaciones] == [
        ("empleado_id", "personal.recursos.empleado_id"),
    ]


# ===========================================================================
# R25 · `raw.usu` y `raw.rac`
# ===========================================================================


def test_f085_r25_ficha_de_raw_usu() -> None:
    ficha = _ficha("raw", "usu")
    texto = ficha["descripcion"]
    assert ficha["consumo_recomendado"] is False
    assert re.search(r"No se traen\W{0,4}10\b", texto)
    for dato in ("SIN CREDENCIALES", "DNI", "correo", "MCP",
                 "compras.documento_procesos", "personal.usuarios_sigrid", "F-085"):
        assert dato in texto, f"la ficha de raw.usu no dice «{dato}»"


def test_f085_r25_raw_rac_ya_no_va_filtrada() -> None:
    texto = _ficha("raw", "rac")["descripcion"]
    assert "ESTA FILTRADA" not in texto
    # Review F-085 pasada 1: «Como se carga» decia «con el mismo filtro», cierto
    # con F-095 y falso desde F-085. Es lo que lee el MCP antes de contar pasos.
    assert "mismo filtro" not in texto, "raw.rac ya no lleva filtro de ingesta (R25)"
    for dato in ("F-085", "2.517.791", "asiide <> 0", "`usu`", "login",
                 "compras.documento_procesos", "retenciones.apuntes_contables"):
        assert dato in texto, f"la ficha de raw.rac no dice «{dato}»"
    assert "FILTRADO" not in _ficha("raw", "rac")["motivo_no_consumo"]


def test_f085_r25_la_ficha_de_confir_ya_no_niega_la_fecha_del_cambio() -> None:
    texto = _ficha("raw", "confir")["descripcion"]
    assert "ninguna tabla de Sigrid lo hace" not in texto
    assert "compras.documento_procesos" in texto


# ===========================================================================
# R26 · `compras.comparativos` y `compras.comparativo_firmas`
# ===========================================================================


def test_f085_r26_comparativos_ya_no_dice_que_sigrid_no_guarda_el_cambio() -> None:
    texto = _texto(_ficha("compras", "comparativos"))
    assert "Sigrid no guarda cuando cambio el estado" not in texto
    assert "(eso no se guarda)" not in texto
    columna = _ficha("compras", "comparativos")["columnas"]["fecha_aprobacion"]
    assert "compras.documento_procesos" in _texto(columna)


def test_f085_r26_comparativo_firmas_apunta_al_historial_de_procesos() -> None:
    texto = _ficha("compras", "comparativo_firmas")["descripcion"]
    assert "compras.documento_procesos" in texto
    assert "es F-085" not in texto


# ===========================================================================
# R27 · `00_global.yaml`
# ===========================================================================


def test_f085_r27_version_recuento_y_pendientes() -> None:
    glob = _yaml("00_global.yaml")
    assert int(glob["version"]) >= 45, "F-085 sube la versión del diccionario"
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "las 72 tablas" in texto
    assert "version 45 (F-085" in texto
    assert glob["pendientes"] == []


def test_f085_r27_la_regla_de_con_declara_los_campos_propios_nuevos() -> None:
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    for campo in ("`rac.fec`", "`rac.res`", "`usu.cod`", "`usu.res`"):
        assert campo in texto, f"R-SIGRID-CON no declara {campo}"


def test_f085_r25_raw_yaml_cuenta_72() -> None:
    texto = (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")
    assert "Son 72 tablas" in texto


# ===========================================================================
# R28 · ARCHITECTURE y azure-apps
# ===========================================================================


def test_f085_r28_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for dato in ("72 tablas", "F-085", "`usu`", "compras.documento_procesos",
                 "personal.usuarios_sigrid"):
        assert dato in texto, f"ARCHITECTURE.md no dice «{dato}»"
    assert "No hay histórico de cambios de estado" not in texto
    assert "**única que se trae filtrada**" not in texto


def test_f085_r28_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for dato in ("72 tablas", "F-085", "`usu`", "compras.documento_procesos",
                 "personal.usuarios_sigrid"):
        assert dato in texto, f"azure-apps no dice «{dato}»"
    assert "**filtrada** a `asiide <> 0`)" not in texto
