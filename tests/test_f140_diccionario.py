# tests/test_f140_diccionario.py
"""
F-140 · El diccionario y los documentos de los ingredientes de caja (R22-R26).

Se leen los YAML y los Markdown como texto: ni red ni BBDD.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DICC = RAIZ / "config" / "diccionario"
RUTA_SETUP = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria" / "00_setup.sql"
RUTA_PLAZOS = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "tesoreria" / "04_plazos_forma_pago.sql"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_CLAUDE = RAIZ / "CLAUDE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

#: Las ocho tablas nuevas y la vista: con ficha, aviso de perfil y columnas.
TABLAS = (
    "hipotesis_caja", "hipotesis_caja_manual", "hipotesis_caja_obra",
    "condiciones_contrato_compra", "condiciones_contrato_cliente",
    "devengo_pendiente_partida", "devengo_pendiente_obra_mes", "devengo_corte_obra",
)
VISTA = "plazos_forma_pago"
FUNCIONES = ("fn_plazo_reconocido", "fn_plazo_dias", "fn_plazo_dias_retencion")
#: Las que enrutan: recomendadas, con dos preguntas (la manual no se consulta).
RECOMENDADAS = (*(t for t in TABLAS if t != "hipotesis_caja_manual"), VISTA)


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DICC / nombre).read_text(encoding="utf-8"))


def _fichas(nombre: str = "tesoreria.yaml") -> dict:
    return _yaml(nombre)["objetos"]


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", str(texto))


def _columnas_setup(tabla: str) -> list[str]:
    texto = re.sub(r"\s+", " ", "\n".join(
        linea for linea in RUTA_SETUP.read_text(encoding="utf-8").splitlines()
        if not linea.lstrip().startswith("--")
    ))
    m = re.search(rf"CREATE TABLE IF NOT EXISTS tesoreria\.{tabla} \((.*?)\);", texto)
    assert m, tabla
    columnas = []
    for trozo in re.split(r",(?![^()]*\))", m.group(1)):
        nombre = trozo.strip().split(" ")[0]
        if nombre and nombre.upper() != "PRIMARY":
            columnas.append(nombre)
    # F-150: las columnas que llegan con `ALTER TABLE ... ADD COLUMN IF NOT
    # EXISTS` quedan al final, en el orden del fichero.
    for nombre in re.findall(
        rf"ALTER TABLE tesoreria\.{tabla} ADD COLUMN IF NOT EXISTS (\w+)", texto
    ):
        if nombre not in columnas:
            columnas.append(nombre)
    return columnas


def _columnas_vista() -> list[str]:
    texto = RUTA_PLAZOS.read_text(encoding="utf-8").split("UNION ALL")[0]
    return re.findall(r"\bAS (\w+)\s*,?\s*$", texto, re.M)


def _reglas() -> dict[str, dict]:
    return {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}


# ===========================================================================
# R22 · las fichas de los objetos nuevos
# ===========================================================================

@pytest.mark.parametrize("tabla", TABLAS)
def test_f140_r22_cada_tabla_tiene_ficha_con_todas_sus_columnas(tabla: str) -> None:
    ficha = _fichas()[tabla]
    assert ficha["tipo"] == "tabla" and ficha["paso_etl"] == "build_tesoreria"
    assert list(ficha["columnas"]) == _columnas_setup(tabla), "todas, en el orden del setup"


def test_f140_r22_la_vista_tiene_ficha_con_sus_columnas() -> None:
    ficha = _fichas()[VISTA]
    assert ficha["tipo"] == "vista"
    assert list(ficha["columnas"]) == _columnas_vista()
    assert ficha["clave_negocio"] == ["sentido", "forma_id"]


@pytest.mark.parametrize("funcion", FUNCIONES)
def test_f140_r22_las_funciones_tienen_ficha_y_no_se_consumen(funcion: str) -> None:
    ficha = _fichas()[funcion]
    assert ficha["tipo"] == "funcion" and ficha["consumo_recomendado"] is False


@pytest.mark.parametrize("objeto", RECOMENDADAS)
def test_f140_r22_las_recomendadas_enrutan_con_dos_preguntas(objeto: str) -> None:
    ficha = _fichas()[objeto]
    assert ficha["consumo_recomendado"] is True
    assert len(ficha["ejemplos_preguntas"]) == 2
    assert ficha["clave_negocio"], "clave_negocio para check-unicidad"


def test_f140_r22_las_preguntas_que_enrutan_la_caja() -> None:
    assert _fichas()["devengo_corte_obra"]["ejemplos_preguntas"][0] == (
        "Que caja necesitara la obra X los proximos seis meses"
    )
    assert _fichas()["condiciones_contrato_compra"]["ejemplos_preguntas"][0] == (
        "Con que plazo pagamos al proveedor Y"
    )


@pytest.mark.parametrize("objeto", [t for t in TABLAS if t.startswith(("devengo", "condiciones"))])
def test_f140_r22_ninguna_ficha_presenta_el_devengo_como_caja(objeto: str) -> None:
    """El devengo y lo pactado son ingredientes: la ficha remite a la regla."""
    descripcion = _plano(_fichas()[objeto]["descripcion"])
    assert "R-CAJA-HIPOTESIS" in descripcion
    assert "No es caja" in descripcion or "Es un ingrediente" in descripcion


def test_f140_r22_efectos_ya_no_dice_que_la_fase_2_no_existe() -> None:
    for fichero in ("tesoreria.yaml", "tesoreria_restringida.yaml"):
        texto = _plano(_fichas(fichero)["efectos"]["descripcion"])
        assert "fase 2" not in texto.lower(), fichero
        assert "tesoreria.devengo_corte_obra" in texto, fichero


@pytest.mark.parametrize("fichero", ["tesoreria.yaml", "tesoreria_restringida.yaml"])
def test_f140_r17_obra_via_documentada_al_final(fichero: str) -> None:
    columnas = _fichas(fichero)["efectos"]["columnas"]
    assert list(columnas)[-1] == "obra_via"
    assert columnas["obra_via"]["valores"] == [
        "CENTRO", "CONTRATO", "FACTURA_CABECERA", "FACTURA_LINEAS"
    ]
    assert "SOLO por su centro" not in _plano(columnas["obra_id"]["significado"])


def test_f140_r22_compras_remite_a_tesoreria() -> None:
    compras = _fichas("compras.yaml")
    assert "`tesoreria.plazos_forma_pago`" in _plano(compras["formas_pago"]["descripcion"])
    assert "`tesoreria.condiciones_contrato_compra`" in _plano(compras["contratos"]["descripcion"])


# ===========================================================================
# R23, R24 · la regla dura y el resto de 00_global
# ===========================================================================

def test_f140_r23_la_regla_es_bloqueante_y_se_sirve_su_resumen() -> None:
    regla = _reglas()["R-CAJA-HIPOTESIS"]
    assert regla["severidad"] == "bloqueante"
    assert regla["entrega"] == "resumen"
    texto = _plano(regla["regla"])
    for dato in ("DECLARA TODAS", "USUARIO", "OBRA", "DEFECTO", "validado", "SIN IVA",
                 "cartera_viva", "cartera_emitida_tras_cierre", "albaranes"):
        assert dato in texto, f"la regla no dice «{dato}»"


def test_f140_r24_el_resumen_nombra_lo_que_obliga() -> None:
    resumen = _plano(_reglas()["R-CAJA-HIPOTESIS"]["resumen"]).strip()
    for dato in ("`tesoreria.hipotesis_caja_obra`", "hipótesis", "DEFECTO", "OBRA", "USUARIO"):
        assert dato in resumen, f"el resumen no dice «{dato}»"
    assert 40 <= len(resumen) <= 250


def test_f140_r24_el_ambito_son_los_objetos_nuevos_la_cartera_y_mart() -> None:
    ambito = set(_reglas()["R-CAJA-HIPOTESIS"]["ambito"])
    assert {f"tesoreria.{o}" for o in RECOMENDADAS} <= ambito
    assert {"tesoreria.efectos", "mart.fact_seguimiento_mensual"} <= ambito


def test_f140_r23_la_regla_de_la_cartera_remite_a_la_nueva() -> None:
    assert "R-CAJA-HIPOTESIS" in _plano(_reglas()["R-TESORERIA-ESTADO"]["regla"])


def test_f140_r26_version_62_con_su_comentario() -> None:
    glob = _yaml("00_global.yaml")
    assert int(glob["version"]) == 62
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 62 (F-140, 2026-10-25)" in texto
    assert glob["pendientes"] == []


def test_f140_r22_el_esquema_dice_para_que_sirve() -> None:
    esquema = _yaml("00_global.yaml")["esquemas"]["tesoreria"]
    texto = _plano(esquema["para_que_sirve"]).strip()
    assert "R-CAJA-HIPOTESIS" in texto and "devengo pendiente" in texto
    assert len(texto) <= 350


# ===========================================================================
# R26 · ARCHITECTURE, CLAUDE.md y azure-apps (docs)
# ===========================================================================

DATOS_DOCUMENTOS = ("F-140", "tesoreria.devengo_corte_obra", "tesoreria.hipotesis_caja_obra",
                    "config/hipotesis_caja.yaml", "R-CAJA-HIPOTESIS", "`auxcob`")


def test_f140_docs_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for dato in DATOS_DOCUMENTOS:
        assert dato in texto, f"ARCHITECTURE.md no dice «{dato}»"


def test_f140_docs_claude_md_mapa() -> None:
    texto = DOC_CLAUDE.read_text(encoding="utf-8")
    for dato in ("F-140", "hipotesis_caja.yaml", "R-CAJA-HIPOTESIS", "devengo"):
        assert dato in texto, f"CLAUDE.md no dice «{dato}»"


def test_f140_docs_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for dato in (*DATOS_DOCUMENTOS, "`auxefc`", "Control de Costes"):
        assert dato in texto, f"azure-apps no dice «{dato}»"


def test_f140_r22_p1a_la_ficha_de_hipotesis_por_obra_dice_las_23() -> None:
    """P1-a del review: la tabla trae las 23 del catálogo por obra, H17 a DEFECTO."""
    ficha = _fichas()["hipotesis_caja_obra"]
    assert "las 23 hipotesis del catalogo" in _plano(ficha["grano"])
    assert "H17" in _plano(ficha["descripcion"]) and "DEFECTO" in _plano(ficha["descripcion"])
