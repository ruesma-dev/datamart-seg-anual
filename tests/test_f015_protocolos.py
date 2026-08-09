# tests/test_f015_protocolos.py
"""F-015 · Protocolos de los agentes y línea base sobre código real (R8, R9, R18).

Análisis textual, como hizo F-003 con los `.ps1`: lo que se verifica es que el
protocolo escrito EXIGE la evidencia, no que un agente concreto la haya dado.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
IMPLEMENTER = RAIZ / ".claude" / "agents" / "implementer.md"
LINEA_BASE = RAIZ / "progress" / "mutacion_F-005.md"


def texto_de(ruta: Path) -> str:
    """Texto en minúsculas y con los espacios colapsados.

    Así el análisis textual no depende de dónde parta las líneas el Markdown.
    """
    return re.sub(r"\s+", " ", ruta.read_text(encoding="utf-8").lower())


# --- R8: fase RED con salida real -------------------------------------------


def test_f015_r8_implementer_exige_fase_red_con_salida_real() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "fase red" in protocolo
    # Qué hay que demostrar: que el test fallaba ANTES de existir el código.
    assert "antes" in protocolo
    assert "fallaba" in protocolo or "falla" in protocolo
    # Y con qué se demuestra: la salida real pegada en el informe.
    assert "salida real" in protocolo
    assert "progress/impl_f-xxx.md" in protocolo
    # La defensa que justifica la regla, escrita para que nadie la relaje.
    assert "a posteriori" in protocolo


def test_f015_r8_la_fase_red_se_exige_para_los_requisitos_centrales() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "requisitos centrales" in protocolo
    # Y se dice explícitamente qué NO vale como evidencia.
    assert "no vale" in protocolo


# --- R9: sección «Evidencias» con números reales ----------------------------


def test_f015_r9_implementer_exige_seccion_evidencias_con_numeros() -> None:
    protocolo = texto_de(IMPLEMENTER)

    assert "evidencias" in protocolo
    # Los cuatro números, comparables entre features.
    assert re.search(r"tests? ejecutados", protocolo)
    assert "cobertura de las líneas cambiadas" in protocolo
    assert "supervivientes" in protocolo
    assert "tiempo" in protocolo
    # Números reales, no impresiones.
    assert "debería funcionar" in protocolo or "numeros reales" in protocolo


# --- R18: la línea base sobre código real del repositorio -------------------


def test_f015_r18_existe_la_linea_base_de_f005_con_totales_reales() -> None:
    assert LINEA_BASE.is_file(), "falta la línea base de mutación sobre F-005"
    informe = LINEA_BASE.read_text(encoding="utf-8")

    # Totales, con números de verdad (no plantillas a cero).
    numeros = {}
    for etiqueta in ("Mutantes generados", "Muertos", "Supervivientes", "Timeouts"):
        fila = re.search(rf"\| {etiqueta} \| (\d+) \|", informe)
        assert fila, etiqueta
        numeros[etiqueta] = int(fila.group(1))

    assert numeros["Mutantes generados"] > 0, "una campaña sin mutantes no mide nada"
    assert numeros["Muertos"] + numeros["Supervivientes"] + numeros["Timeouts"] == (
        numeros["Mutantes generados"]
    )
    # El alcance se reconstruyó desde el commit de merge (R4).
    assert "**merge**" in informe
    assert re.search(r"\| \*\*Total\*\* \| \*\*\d+\*\* \|", informe)


def test_f015_r18_cada_superviviente_de_la_linea_base_esta_analizado() -> None:
    informe = LINEA_BASE.read_text(encoding="utf-8")
    supervivientes = int(re.search(r"\| Supervivientes \| (\d+) \|", informe).group(1))

    # Una sección de análisis por superviviente...
    assert informe.count("#### Análisis") == supervivientes
    assert informe.count("**Por qué ningún test lo caza:**") == supervivientes
    assert informe.count("**Veredicto:**") == supervivientes
    # ...y ninguna sin completar.
    assert "PENDIENTE" not in informe
