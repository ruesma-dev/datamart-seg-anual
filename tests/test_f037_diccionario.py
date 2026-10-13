# tests/test_f037_diccionario.py
"""
F-037 · El diccionario y la documentación de la cartera de cobros y pagos (R24-R28).

Las fichas se cargan con el cargador real (`cargar_diccionario`) y se
contrastan con el SQL que construye cada objeto: una columna sin ficha es una
columna que el agente interpretará a ojo. Ningún test toca red ni BBDD.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests._texto import contiene
from tests.test_f037_sql import COLUMNAS_COMPLETO, COLUMNAS_GENERAL

RAIZ = Path(__file__).resolve().parents[1]
DICC = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_CLAUDE = RAIZ / "CLAUDE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"
DOC_MCP_BBDD = RAIZ.parent / "azure-apps" / "mcp_bbdd.md"


def _dicc():
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _errores = cargar_diccionario(DICC)
    return dicc


def _ficha(nombre: str):
    ficha = _dicc().por_nombre.get(nombre)
    assert ficha is not None, f"falta la ficha de {nombre}"
    return ficha


def _texto(ficha) -> str:
    partes = [ficha.descripcion or "", ficha.grano or ""]
    for c in ficha.columnas:
        partes += [c.significado or "", c.nulo_significa or ""]
    return "\n".join(partes)


def _global() -> dict:
    return yaml.safe_load((DICC / "00_global.yaml").read_text(encoding="utf-8"))


def _regla(codigo: str) -> dict:
    reglas = {r["codigo"]: r for r in _global()["reglas"]}
    assert codigo in reglas, f"falta la regla {codigo}"
    return reglas[codigo]


# ===========================================================================
# R24 · las fichas, con TODAS las columnas del SQL y en su orden
# ===========================================================================

@pytest.mark.parametrize(
    ("nombre", "columnas"),
    [
        ("tesoreria.efectos", COLUMNAS_GENERAL),
        ("tesoreria_restringida.efectos", COLUMNAS_COMPLETO),
        ("tesoreria.efectos_restringidos_mes",
         ("empresa_id", "sentido", "anio", "mes", "estado_tesoreria", "num_efectos")),
    ],
)
def test_f037_r24_cada_tabla_tiene_ficha_con_sus_columnas(nombre: str, columnas: tuple) -> None:
    ficha = _ficha(nombre)
    assert ficha.tipo == "tabla"
    assert ficha.consumo_recomendado is True
    assert ficha.paso_etl == "build_tesoreria" and ficha.refresco == "nocturno"
    assert [c.nombre for c in ficha.columnas] == list(columnas)


def test_f037_r24_las_claves_de_negocio() -> None:
    assert _ficha("tesoreria.efectos").clave_negocio == ("efecto_id",)
    assert _ficha("tesoreria_restringida.efectos").clave_negocio == ("efecto_id",)
    assert _ficha("tesoreria.efectos_restringidos_mes").clave_negocio == (
        "empresa_id", "sentido", "anio", "mes", "estado_tesoreria",
    )


@pytest.mark.parametrize("funcion", ["tesoreria.fn_fecha", "tesoreria.fn_serie"])
def test_f037_r24_las_funciones_locales_documentadas_fuera_de_consumo(funcion: str) -> None:
    ficha = _ficha(funcion)
    assert ficha.tipo == "funcion" and ficha.consumo_recomendado is False


def test_f037_r24_los_dos_esquemas_en_el_global_y_en_la_tupla() -> None:
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    esquemas = _global()["esquemas"]
    for esquema in ("tesoreria", "tesoreria_restringida"):
        assert esquema in ESQUEMAS_DEL_DATAMART
        assert esquemas[esquema]["pasos_etl"] == ["build_tesoreria"]
        assert esquemas[esquema]["refresco"] == "nocturno"
    assert "perfil total" in esquemas["tesoreria_restringida"]["titulo"]


def test_f037_r24_el_diccionario_valida_entero() -> None:
    """El validador real, con los pasos reales de la nocturna: cero errores."""
    from etl_sigrid.domain.diccionario import validar
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    assert validar(_dicc(), pasos_del_pipeline_nocturno()) == []


def test_f037_r24_la_version_sube_sobre_la_real() -> None:
    """La 50 la publicó F-136 el 2026-10-13: F-037 sube a la 51, «al menos»."""
    assert _global()["version"] >= 51


def test_f037_r24_compras_vencimientos_es_vista_y_cita_su_origen() -> None:
    ficha = _ficha("compras.vencimientos")
    assert ficha.tipo == "vista"
    texto = _texto(ficha)
    assert "tesoreria.efectos" in texto
    assert "build_tesoreria" in texto, "su frescura es la de build_tesoreria"
    assert ficha.paso_etl == "build_compras", "la vista la crea build_compras"


def test_f037_r24_la_restringida_empieza_por_el_aviso() -> None:
    descripcion = _ficha("tesoreria_restringida.efectos").descripcion
    assert descripcion.startswith("**ACCESO RESTRINGIDO: solo el perfil total del MCP.**")
    assert "`tesoreria.efectos`" in descripcion.split("\n")[0], "y adónde ir si no se tiene"


# ===========================================================================
# R25 y R25 bis · la regla del estado
# ===========================================================================

def test_f037_r25_regla_del_estado() -> None:
    regla = _regla("R-TESORERIA-ESTADO")
    assert regla["severidad"] == "bloqueante"
    assert set(regla["ambito"]) >= {"tesoreria", "tesoreria_restringida", "compras.vencimientos"}
    texto = regla["regla"]
    assert "BAJA" in texto and contiene(texto, "NO se suma nunca")
    assert contiene(texto, "`fecha_real IS NULL`") and "2020" in texto
    assert contiene(texto, "estado 10")
    assert "previsto_antiguo" in texto


def test_f037_r25bis_la_cartera_de_caja_excluye_lo_antiguo() -> None:
    texto = _regla("R-TESORERIA-ESTADO")["regla"]
    assert contiene(texto, "`estado_tesoreria = 'PREVISTO' AND NOT previsto_antiguo`")
    assert contiene(texto, "2 anos")


def test_f037_r25bis_la_columna_documentada() -> None:
    columna = {c.nombre: c for c in _ficha("tesoreria.efectos").columnas}["previsto_antiguo"]
    assert contiene(columna.significado, "2 anos") and "PREVISTO" in columna.significado


# ===========================================================================
# R26 · lo restringido, cubierto por una regla hermana
# ===========================================================================

def test_f037_r26_regla_hermana_de_la_contable() -> None:
    regla = _regla("R-TESORERIA-RESTRINGIDA")
    assert regla["severidad"] == "bloqueante"
    assert regla["titulo"].startswith("Usa tesoreria;")
    assert "tesoreria_restringida" in regla["titulo"]
    assert contiene(regla["titulo"], "perfil total")
    assert len(regla["titulo"]) <= 87, "como el título más largo ya publicado"
    assert set(regla["ambito"]) == {"tesoreria", "tesoreria_restringida"}
    texto = regla["regla"]
    assert "NUNCA" in texto and contiene(texto, "se suman"), "los dos esquemas no se suman"
    assert "efectos_restringidos_mes" in texto
    assert contiene(texto, "permission denied")


# ===========================================================================
# R27 · lo que la ficha de la general tiene que declarar
# ===========================================================================

def test_f037_r27_la_ficha_declara_cobros_flojos_retenciones_y_fase_2() -> None:
    texto = _texto(_ficha("tesoreria.efectos"))
    assert "21.914" in texto and "F-040" in texto, "cobertura floja de cobros"
    assert contiene(texto, "19,9 M EUR"), "la duda de las retenciones de cliente de baja"
    assert contiene(texto, "NO DEVENGO") and contiene(texto.lower(), "fase 2")


def test_f037_r30_la_ficha_publica_el_contraste_y_su_porque() -> None:
    texto = _texto(_ficha("tesoreria.efectos"))
    for cifra in ("80,1", "78,8", "40,2", "47,5", "3,9", "433", "434", "40+41"):
        assert cifra in texto, f"falta «{cifra}» del contraste (design §8 bis)"
    assert "pagare" in texto, "por qué no se cuadra cuenta a cuenta"


def test_f037_r27_la_general_dice_que_le_falta_el_personal() -> None:
    texto = _texto(_ficha("tesoreria.efectos"))
    assert "37.053" in texto and "efectos_restringidos_mes" in texto
    naturaleza = {c.nombre: c for c in _ficha("tesoreria.efectos").columnas}["naturaleza_pago_id"]
    assert "SIEMPRE" in naturaleza.significado


def test_f037_r27_sin_datos_personales_en_las_fichas() -> None:
    """Solo agregados: ni NIF ni nombres en el diccionario de tesorería."""
    import re

    for fichero in ("tesoreria.yaml", "tesoreria_restringida.yaml"):
        texto = (DICC / fichero).read_text(encoding="utf-8")
        assert not re.search(r"\b\d{8}[A-Z]\b", texto), f"{fichero}: parece un NIF"


# ===========================================================================
# R28 · la documentación, en el mismo trabajo (T10)
# ===========================================================================

def test_f037_docs_arquitectura_y_claude() -> None:
    arquitectura = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("tesoreria_restringida", "build_tesoreria", "tesoreria.efectos",
                    "compras.vencimientos"):
        assert termino in arquitectura, f"ARCHITECTURE.md no dice «{termino}»"
    claude = DOC_CLAUDE.read_text(encoding="utf-8")
    assert "tesoreria_restringida" in claude and "quince pasos" in claude


def test_f037_docs_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("F-037", "tesoreria_restringida", "tesoreria.efectos", "build_tesoreria"):
        assert termino in texto, f"azure-apps no dice «{termino}» (R28)"
    mcp = DOC_MCP_BBDD.read_text(encoding="utf-8")
    assert "tesoreria" in mcp and "datamart_seg_anual.md" in mcp, (
        "mcp_bbdd.md enlaza al contrato de lista blanca, sin copiarlo"
    )
