# tests/test_f139_limite.py
"""
F-139 · El límite del índice de adjuntos y la guarda de este ETL (R1-R7, R9).

La IA abrirá el ORIGINAL de un adjunto por una herramienta de `mcp-bbdd`
(`abrir_adjunto`, pliego H1-H13 en `azure-apps/datamart_seg_anual.md`): este
repositorio solo publica el ÍNDICE (`compras.documento_adjuntos`, F-090) y la
regla de quién puede abrir cada fichero. Aquí se fija que la ficha y la
arquitectura lo dicen, con las cifras medidas el 2026-10-15
(`progress/spec_F-139.md`), y que este ETL no se pone a leer documentos.

Sin red ni BBDD.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain.documento_adjuntos import FAMILIAS_ADJUNTOS

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"

#: La tabla y la columna de origen de cada familia (R3). Es parte del contrato
#: con `mcp-bbdd` (R8): su `abrir_adjunto` comprueba el permiso con un
#: `LEFT JOIN` a esta tabla por esta columna.
ORIGEN_POR_FAMILIA: dict[str, tuple[str, str]] = {
    "FACTURA": ("facturas", "factura_id"),
    "CONTRATO": ("contratos", "contrato_id"),
    "COMPARATIVO": ("comparativos", "comparativo_id"),
    "OFERTA": ("comparativo_ofertas", "oferta_id"),
    "ALBARAN": ("albaranes", "albaran_id"),
}

#: Librerías de lectura de documentos o de IA que este ETL no importa (R7).
LIBRERIAS_PROHIBIDAS: tuple[str, ...] = (
    "pypdf", "pdfplumber", "fitz", "pdfminer", "openpyxl", "docx",
    "pytesseract", "anthropic", "openai", "google.genai", "google.generativeai",
)

#: La ÚNICA excepción a R7 (decisión del humano del 2026-10-15, opción A):
#: el paso de F-004 lee con `openpyxl` los tres Excels de configuración de
#: Negocio, que no son adjuntos. `openpyxl` sigue prohibida en cualquier otro
#: módulo, y si esta excepción sobra un test de control lo dice.
EXCEPCIONES: dict[str, str] = {
    "etl_sigrid/application/steps/load_excel_aux_step.py": "openpyxl",
}


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _adjuntos() -> dict:
    objetos = _yaml("compras.yaml")["objetos"]
    assert "documento_adjuntos" in objetos, "falta la ficha de compras.documento_adjuntos"
    return objetos["documento_adjuntos"]


def _descripcion() -> str:
    return _adjuntos()["descripcion"]


def _texto() -> str:
    return yaml.safe_dump(_adjuntos(), allow_unicode=True, width=10_000)


# ===========================================================================
# R1 · `filename_columns: ["cod"]` y el HTTP 500 de los nombres no ASCII
# ===========================================================================


def test_f139_r1_la_ficha_dice_como_pedir_el_fichero_sin_el_500() -> None:
    descripcion = _descripcion()
    for dato in ('filename_columns: ["cod"]', "HTTP 500", "no ASCII",
                 "11.262", "199.032", "5,7 %", "2026-10-15"):
        assert dato in descripcion, f"la ficha no dice «{dato}» (R1)"


# ===========================================================================
# R2 · El límite: el índice aquí, la apertura en `mcp-bbdd`, sin convertir
# ===========================================================================


def test_f139_r2_la_ficha_declara_el_limite() -> None:
    descripcion = _descripcion()
    for dato in ("mcp-bbdd", "F-139", "SIN CONVERTIR", "el ORIGINAL", "F-142",
                 "NO ESTA DESPLEGADA"):
        assert dato in descripcion, f"la ficha no dice «{dato}» (R2)"


def test_f139_r2_la_ficha_no_afirma_que_la_herramienta_exista() -> None:
    """Mientras `abrir_adjunto` no esté desplegada, la ficha no la nombra.

    Quien lee la ficha es una IA: si ve el nombre de una herramienta, la
    llamará. Cuando `mcp-bbdd` la despliegue, se cambian la ficha y este test.
    """
    assert "abrir_adjunto" not in _texto(), (
        "la ficha nombra `abrir_adjunto` y la herramienta aún no existe (R2)"
    )


# ===========================================================================
# R3 · Quién puede abrir el fichero, y quién ve las filas del índice (D1)
# ===========================================================================


def test_f139_r3_la_regla_de_permisos_con_la_tabla_de_cada_familia() -> None:
    descripcion = _descripcion()
    assert "QUIEN PUEDE ABRIR EL FICHERO" in descripcion, "R3"
    for familia, (tabla, columna) in ORIGEN_POR_FAMILIA.items():
        enlace = f"{familia} -> `compras.{tabla}.{columna}`"
        assert enlace in descripcion, f"la regla de permisos no dice «{enlace}» (R3)"


def test_f139_r3_la_regla_del_propio_indice() -> None:
    descripcion = _descripcion()
    for dato in ("LA MISMA REGLA VALE PARA ESTE INDICE", "F-141", "estandar y total",
                 "subido_por"):
        assert dato in descripcion, f"la regla del índice (D1) no dice «{dato}» (R3)"


# ===========================================================================
# R4 · Los ficheros grandes y las ofertas sin fila en su tabla
# ===========================================================================


def test_f139_r4_ficheros_grandes_y_ofertas_sin_fila() -> None:
    descripcion = _descripcion()
    for dato in ("17 ficheros", "20 MB", "facturas 8", "contratos 4", "ofertas 4",
                 "comparativos 1", "50 MB", "47 MB", "305 enlaces", "1,4 %"):
        assert dato in descripcion, f"la ficha no dice «{dato}» (R4)"


# ===========================================================================
# R5 · La versión del diccionario sube en uno (main publica la 52)
# ===========================================================================


def test_f139_r5_la_version_sube_sobre_la_de_main() -> None:
    """`main` publica la 52 (F-138); F-139 la sube en uno."""
    assert int(_yaml("00_global.yaml")["version"]) >= 53, "F-139 sube la versión a 53"
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "version 53 (F-139" in texto, "falta la entrada de la versión 53 en la historia"


# ===========================================================================
# R6 · `docs/ARCHITECTURE.md`, en el punto del índice de F-090
# ===========================================================================


def _punto_del_indice() -> str:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    inicio = texto.index("EL ÍNDICE DE DOCUMENTOS ADJUNTOS SALE DE `rcg` Y `gra` (F-090)")
    fin = texto.index("LAS ALARMAS Y LA MARCA «LIQUIDATORIA»", inicio)
    return texto[inicio:fin]


def test_f139_r6_la_arquitectura_declara_limite_aviso_y_permisos() -> None:
    punto = _punto_del_indice()
    for dato in ("F-139", "mcp-bbdd", 'filename_columns: ["cod"]', "HTTP 500",
                 "sin convertir", "tabla de origen", "F-141"):
        assert dato in punto, f"el punto de F-090 de ARCHITECTURE.md no dice «{dato}» (R6)"
    for tabla, columna in ORIGEN_POR_FAMILIA.values():
        assert f"`{tabla}`" in punto, f"ARCHITECTURE.md no nombra `{tabla}` (R6)"


# ===========================================================================
# R7 · Este ETL no importa librerías de lectura de documentos ni de IA
# ===========================================================================


def _modulos_importados(arbol: ast.AST) -> set[str]:
    """Todo nombre de módulo que el fichero importa, absoluto.

    `from google import genai` cuenta como `google` y como `google.genai`.
    Las importaciones relativas son de este repositorio y no cuentan.
    """
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos |= {alias.name for alias in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            modulos.add(nodo.module)
            modulos |= {f"{nodo.module}.{alias.name}" for alias in nodo.names}
    return modulos


def _es_de(modulo: str, libreria: str) -> bool:
    return modulo == libreria or modulo.startswith(f"{libreria}.")


def importaciones_prohibidas(
    ficheros: list[Path], raiz: Path, excepciones: dict[str, str] | None = None
) -> list[str]:
    """`modulo: libreria` por cada librería prohibida que importa cada fichero.

    Una excepción perdona UNA librería en UN fichero, nombrados los dos.
    """
    excepciones = EXCEPCIONES if excepciones is None else excepciones
    hallazgos: list[str] = []
    for fichero in ficheros:
        ruta = fichero.relative_to(raiz).as_posix()
        arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
        modulos = _modulos_importados(arbol)
        for libreria in LIBRERIAS_PROHIBIDAS:
            if excepciones.get(ruta) == libreria:
                continue
            if any(_es_de(m, libreria) for m in modulos):
                hallazgos.append(f"{ruta}: {libreria}")
    return hallazgos


def _ficheros_del_etl() -> list[Path]:
    return sorted((RAIZ / "etl_sigrid").rglob("*.py")) + [RAIZ / "main.py"]


def test_f139_r7_el_etl_no_importa_librerias_de_documentos_ni_de_ia() -> None:
    hallazgos = importaciones_prohibidas(_ficheros_del_etl(), RAIZ)
    assert not hallazgos, (
        "este ETL publica el índice, no lee documentos (F-139: la apertura es de "
        f"`mcp-bbdd`): {hallazgos}"
    )


def test_f139_r7_control_el_barrido_lee_el_etl_de_verdad() -> None:
    """Si el barrido no leyera nada, el test de arriba pasaría solo."""
    ficheros = _ficheros_del_etl()
    assert RAIZ / "main.py" in ficheros
    assert len(ficheros) >= 50
    modulos: set[str] = set()
    for fichero in ficheros:
        modulos |= _modulos_importados(ast.parse(fichero.read_text(encoding="utf-8")))
    assert "click" in modulos and "structlog" in modulos


def test_f139_r7_sabotaje_un_modulo_que_importa_pypdf_rompe_el_test(tmp_path: Path) -> None:
    """El caso de sabotaje: un módulo temporal con las formas de importar."""
    paquete = tmp_path / "etl_sigrid" / "infrastructure"
    paquete.mkdir(parents=True)
    (paquete / "lector.py").write_text(
        "import os\n"
        "import pypdf\n"
        "from pdfminer.high_level import extract_text\n"
        "from google import genai\n"
        "import openai as cliente\n"
        "from . import vecino\n",
        encoding="utf-8",
    )
    (paquete / "limpio.py").write_text(
        "import documento_adjuntos\nimport docxtpl_falso\nimport pypdfium\n",
        encoding="utf-8",
    )

    hallazgos = importaciones_prohibidas(sorted(paquete.glob("*.py")), tmp_path)

    assert hallazgos == [
        "etl_sigrid/infrastructure/lector.py: pypdf",
        "etl_sigrid/infrastructure/lector.py: pdfminer",
        "etl_sigrid/infrastructure/lector.py: openai",
        "etl_sigrid/infrastructure/lector.py: google.genai",
    ]


def test_f139_r7_sabotaje_la_excepcion_no_perdona_otro_fichero_ni_otra_libreria(
    tmp_path: Path,
) -> None:
    """`openpyxl` solo se perdona en el paso de F-004, y solo `openpyxl`."""
    pasos = tmp_path / "etl_sigrid" / "application" / "steps"
    pasos.mkdir(parents=True)
    (pasos / "load_excel_aux_step.py").write_text(
        "from openpyxl import load_workbook\nimport pypdf\n", encoding="utf-8"
    )
    (pasos / "otro_step.py").write_text("import openpyxl\n", encoding="utf-8")

    hallazgos = importaciones_prohibidas(sorted(pasos.glob("*.py")), tmp_path)

    assert hallazgos == [
        "etl_sigrid/application/steps/load_excel_aux_step.py: pypdf",
        "etl_sigrid/application/steps/otro_step.py: openpyxl",
    ]


def test_f139_r7_control_cada_excepcion_hace_falta() -> None:
    """Si el fichero desaparece o deja de importar la librería, la excepción sobra."""
    assert len(EXCEPCIONES) == 1, (
        "R7 admite UNA excepción (humano, 2026-10-15); otra más la decide el humano"
    )
    for ruta, libreria in EXCEPCIONES.items():
        fichero = RAIZ / ruta
        assert fichero.exists(), (
            f"la excepción de R7 para {ruta} sobra: el fichero ya no existe; quítala"
        )
        modulos = _modulos_importados(ast.parse(fichero.read_text(encoding="utf-8")))
        assert any(_es_de(m, libreria) for m in modulos), (
            f"la excepción de R7 para {ruta} sobra: ya no importa {libreria}; quítala"
        )
        hallazgos = importaciones_prohibidas([fichero], RAIZ, excepciones={})
        assert hallazgos == [f"{ruta}: {libreria}"], (
            f"sin su excepción, {ruta} debe ser exactamente un hallazgo de {libreria}"
        )


# ===========================================================================
# R9 · Las cinco tablas de origen existen y están en `relaciones` del índice
# ===========================================================================


def test_f139_r9_las_familias_son_las_del_dominio() -> None:
    assert set(ORIGEN_POR_FAMILIA) == set(FAMILIAS_ADJUNTOS.values())


def test_f139_r9_las_tablas_de_origen_existen_y_se_relacionan() -> None:
    objetos = _yaml("compras.yaml")["objetos"]
    destinos = {r["a"] for r in _adjuntos()["relaciones"] if r["de"] == "documento_id"}
    aviso = ("rompe el contrato de `abrir_adjunto` con `mcp-bbdd` "
             "(azure-apps/datamart_seg_anual.md, F-139 R8): avisa a su dueño")
    for familia, (tabla, columna) in ORIGEN_POR_FAMILIA.items():
        assert tabla in objetos, f"no existe compras.{tabla} ({familia}): {aviso}"
        assert columna in objetos[tabla]["columnas"], (
            f"no existe compras.{tabla}.{columna} ({familia}): {aviso}"
        )
        assert f"compras.{tabla}.{columna}" in destinos, (
            f"el índice no se relaciona con compras.{tabla}.{columna}: {aviso}"
        )
        porque = next(r["porque"] for r in _adjuntos()["relaciones"]
                      if r["a"] == f"compras.{tabla}.{columna}" and r["de"] == "documento_id")
        assert re.search(rf"familia = '{familia}'", porque), (
            f"la relación con compras.{tabla} no dice su familia {familia}"
        )
